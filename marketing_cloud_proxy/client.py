import json
import os
import re
import time
from datetime import datetime

import boto3
import FuelSDK
import jwt
import pytz
import requests
from simple_salesforce import (
    format_soql,
    Salesforce,
    SalesforceAuthenticationFailed,
    SalesforceLogin,
)
from werkzeug.exceptions import BadRequestKeyError

from marketing_cloud_proxy import settings
from marketing_cloud_proxy.errors import InvalidDataError, NoDataProvidedError

REFRESH_TOKEN_TABLE = (
    os.environ.get("REFRESH_TOKEN_TABLE") or "MarketingCloudAuthTokenStore"
)
MC_SUPPORTING_CAST_DATA_EXTENSION = os.environ.get("MC_SUPPORTING_CAST_DATA_EXTENSION")
SUPPORTING_CAST_API_TOKEN = os.environ.get("SUPPORTING_CAST_API_TOKEN")
boto_client = boto3.client("dynamodb", region_name=settings.AWS_DEFAULT_REGION)

config = {
    "accountId": settings.MC_ACCOUNT_ID,
    "appsignature": settings.APP_SIGNATURE,
    "authenticationurl": settings.MC_AUTHENTICATION_URL,
    "baseapiurl": settings.MC_BASE_API_URL,
    "clientid": settings.MC_CLIENT_ID,
    "clientsecret": settings.MC_CLIENT_SECRET,
    "defaultwsdl": settings.MC_DEFAULT_WSDL,
    "soapendpoint": settings.MC_SOAP_ENDPOINT,
    "useOAuth2Authentication": settings.USE_OAUTH2,
    "wsdl_file_local_loc": settings.MC_WSDL_FILE_LOCAL_LOCATION,
}


def failure_response(message):
    return {
        "status": "failure",
        "detail": message,
    }, 400


class MarketingCloudAuthClient:
    @staticmethod
    def retrieve_token_data_from_dynamo():
        token_item = boto_client.get_item(
            TableName=REFRESH_TOKEN_TABLE,
            Key={"KeyName": {"S": "MarketingCloudAuthToken"}},
        )
        token_expiration_item = boto_client.get_item(
            TableName=REFRESH_TOKEN_TABLE,
            Key={"KeyName": {"S": "MarketingCloudAuthTokenExpiration"}},
        )

        try:
            token = token_item["Item"]["KeyValue"]["S"]
        except KeyError:
            return {}

        token_expiration = float(token_expiration_item["Item"]["KeyValue"]["N"])

        return {
            "oauthToken": token,
            "internalOauthToken": token,
            "expiresIn": token_expiration,
        }

    @classmethod
    def is_token_expired(cls, token_data):
        """Checks the expiration time for the current token and, if it is set to
        expire in less than 5 minutes, considers it 'expired' and returns
        True"""
        if not token_data:
            return True

        if (token_data["expiresIn"] - time.time()) < 300:
            return True

    @classmethod
    def instantiate_client(cls):
        token_data = cls.retrieve_token_data_from_dynamo()

        if cls.is_token_expired(token_data):
            fuel_client = FuelSDK.ET_Client(False, False, config)
            boto_client.put_item(
                TableName=REFRESH_TOKEN_TABLE,
                Item={
                    "KeyName": {"S": "MarketingCloudAuthToken"},
                    "KeyValue": {"S": fuel_client.authToken},
                },
            )
            boto_client.put_item(
                TableName=REFRESH_TOKEN_TABLE,
                Item={
                    "KeyName": {"S": "MarketingCloudAuthTokenExpiration"},
                    "KeyValue": {"N": str(fuel_client.authTokenExpiration)},
                },
            )
            return fuel_client

        jwt_token = jwt.encode(
            {"request": {"user": {**token_data}}},
            "none",
        )

        return FuelSDK.ET_Client(False, False, {"jwt": jwt_token, **config})


class SFClient(Salesforce):
    def __init__(self):
        """
        Authenticates with SF and initializes a Salesforce object
        """
        session_id, instance = SalesforceLogin(
            username=settings.SF_USERNAME,
            password=settings.SF_PASS,
            security_token=settings.SF_SECURITY_TOKEN,
            domain=settings.SF_DOMAIN,
        )
        super().__init__(instance=instance, session_id=session_id)


class EmailSignupRequestHandler:
    def __init__(self, request):
        try:
            if not request.form and not request.data:
                raise NoDataProvidedError

            if request.data:
                # POST submitted via api
                request_dict = json.loads(request.data)
            else:
                # POST submitted via form
                request_dict = request.form

            self.lists = request_dict["list"].split("++")
            self.email = request_dict["email"]
            self.source = request_dict.get("source", "")

        except NoDataProvidedError:
            raise InvalidDataError("No email or list was provided")
        except (BadRequestKeyError, KeyError):
            raise InvalidDataError("Requires both an email and a list")

    def is_email_valid(self):
        return bool(re.match(r"[^@]+@[^@]+\.[^@]+", self.email))

    def subscribe(self):
        '''
        Checks that the email list from the request exists and subscribes the
        email from the request to the list, creating a new Salesforce "Contact"
        if one doesn't exist and creating/updating the "Subscription Member".
        '''
        try:
            client = SFClient()
        except SalesforceAuthenticationFailed as e:
            return failure_response(e.__str__())

        contacts = client.query_all(
            format_soql(
                """SELECT Id, LastModifiedDate from Contact WHERE Email = '{}'
            ORDER BY LastModifiedDate, Id ASC""".format(
                    self.email
                )
            )
        )

        try:
            # get the most recent Contact for this email, if one exists
            contact_id = contacts["records"][-1]["Id"]
        except IndexError:
            contact_dict = {
                "LastName": getattr(self, "last_name", "NoLastName"),
                "FirstName": getattr(self, "first_name", ""),
                "Email": format_soql(self.email),
            }
            if getattr(self, "validity_status", None) and getattr(
                self, "validity_name", None
            ):
                contact_dict["cfg_Email_Verification_Score__c"] = (
                    f"{self.validity_name.title()}: {self.validity_status.title()}",
                )
            contact = client.Contact.create(contact_dict)
            if contact["errors"]:
                return failure_response(
                    "User could not be subscribed; error adding Contact"
                )

            contact_id = contact.get("id")

        subscription = {}
        for email_list in self.lists:
            subscription = self._subscribe_to_each(client, email_list, contact_id)
            if "status" not in subscription or subscription.get("status") == "failure":
                break

        return subscription

    def _subscribe_to_each(self, client, email_list, contact_id):
        canonical_email_list = client.query(
            format_soql(
                "SELECT Id FROM cfg_Subscription__c WHERE Name = {}",
                "{}".format(email_list),
            )
        )

        try:
            list_id = canonical_email_list["records"][0]["Id"]
        except IndexError:
            return failure_response("User could not be subscribed; list does not exist")

        subscription_members = client.query_all(
            format_soql(
                """SELECT Id, LastModifiedDate FROM cfg_Subscription_Member__c
               WHERE cfg_Subscription__c = '{}' AND cfg_Contact__c = '{}'
               ORDER BY LastModifiedDate, Id ASC""".format(
                    list_id, contact_id
                )
            )
        )

        try:
            # get the most recent Subscription Member, if one exists
            sub_member_id = subscription_members["records"][-1]["Id"]
        except IndexError:
            new_sub = client.cfg_Subscription_Member__c.create(
                {
                    "cfg_Subscription__c": list_id,
                    "cfg_Contact__c": contact_id,
                    "cfg_Active__c": True,
                    "nypr_Subscription_Source__c": self.source,
                    "cfg_Opt_In_Date__c": datetime.now(pytz.timezone("UTC")).strftime(
                        "%Y-%m-%d"
                    ),
                }
            )
            if new_sub["errors"]:
                failure_response(
                    "User could not be subscribed; error adding subscription member"
                )

            return {"status": "subscribed", "detail": "Email successfully added"}

        update_sub_status = client.cfg_Subscription_Member__c.update(
            "Id/{}".format(sub_member_id),
            {
                "nypr_Subscription_Source__c": self.source,
                "cfg_Active__c": True,
                "cfg_Opt_In_Date__c": datetime.now(pytz.timezone("UTC")).strftime(
                    "%Y-%m-%d"
                ),
            },
        )

        if update_sub_status != 200:
            failure_response("Error updating subscription")

        return {"status": "subscribed", "detail": "Subscription successfully updated"}


class SupportingCastWebhookHandler:
    """Handles the Supporting Cast webhook events, such as when a user's
    subscription is activated or deactivated, and upates that information a
    MarketingCloud data extension."""

    def __init__(self, request):
        self.auth_client = MarketingCloudAuthClient.instantiate_client()
        self.de_row = self._create_data_extension_row_stub()
        self.webhook_info = self._extract_info_from_webhook_event(request)
        self.response = None

        self.subscribe()

    def _extract_info_from_webhook_event(self, request):
        if not request.data:
            raise InvalidDataError("No webhook info was provided")

        event_info_dict = request.get_json()
        member_id = event_info_dict["subscription"]["member_id"]
        plan_id = event_info_dict["subscription"]["plan_id"]
        member_info_dict = self._get_member_info_from_id(member_id)
        plan_info_dict = self._get_plan_info_from_id(plan_id)

        return {
            "email_address": member_info_dict["email"],
            "first_name": member_info_dict["first_name"],
            "last_name": member_info_dict["last_name"],
            "plan": plan_info_dict["name"],
            "plan_status": event_info_dict["subscription"]["status"],
        }

    def _create_data_extension_row_stub(self):
        de_row = FuelSDK.ET_DataExtension_Row()
        de_row.CustomerKey = os.environ.get("MC_SUPPORTING_CAST_DATA_EXTENSION")
        de_row.auth_stub = self.auth_client
        return de_row

    def _get_member_info_from_id(self, id):
        """Hits SC API to get member info"""
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {SUPPORTING_CAST_API_TOKEN}",
        }
        response = requests.get(
            f"https://api.supportingcast.fm/v1/memberships/id={id}", headers=headers
        )
        return response.json()

    def _get_plan_info_from_id(self, id):
        """Hits SC API to get plan info"""
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {SUPPORTING_CAST_API_TOKEN}",
        }
        response = requests.get(
            f"https://api.supportingcast.fm/v1/plans/{id}", headers=headers
        )
        return response.json()

    def subscribe(self):
        email_address = self.webhook_info["email_address"]
        first_name = self.webhook_info["first_name"]
        last_name = self.webhook_info["last_name"]
        plan = self.webhook_info["plan"]
        plan_status = self.webhook_info["plan_status"]
        creation_date = datetime.now(pytz.timezone("America/New_York")).strftime(
            "%-m/%-d/%Y %H:%M:%S %p"
        )
        updated_date = datetime.now(pytz.timezone("America/New_York")).strftime(
            "%-m/%-d/%Y %H:%M:%S %p"
        )

        # First, attempt to add email to overall Master Preferences data
        # extension
        self.de_row.props = {
            "email_address": email_address,
            "creation_date": creation_date,
        }
        self.de_row.post()

        # Then, flip the list columns to indicate they have signed up
        self.de_row.props = {
            "email_address": email_address,
            "first_name": first_name,
            "last_name": last_name,
            "plan": plan,
            "plan_status": plan_status,
            "updated_date": updated_date,
        }
        patch_response = self.de_row.patch()

        self.response = {"status": "success"}

        if patch_response.results[0].StatusCode == "Error":
            return {"status": "failure"}, 400


class OptinmonsterWebhookHandler(EmailSignupRequestHandler):
    """Handles the OptinMonster webhook events and adds or updates the contact
    in Salesforce.

    Example webhook payload (see tests for more):

    payload = {
        "lead": {
            "email": "hello@optinmonster.com",
            "firstName": "Archie",
            "lastName": "Monster",
            "phone": "888-888-8888",
            "ipAddress": "1.2.3.4",
            "referrer": "https://optinmonster.com",
            "timestamp": 1623701598
        },
        "lead_options": {
            "list": "Politics Brief",
            "tags": [],
            "data": None
        },
        "campaign": {
            "id": "nppjcagohkl4bx3w1zln",
            "title": "Demo (Popup)"
        },
        "meta": {},
        "smart_tags": {
            "page_url": "",
            "referrer_url": "",
            "pages_visited": "",
            "time_on_site": "",
            "visit_timestamp": "",
            "page_title": "",
            "campaign_name": "",
            "form_email": "",
            "coupon_label": "",
            "coupon_code": ""
        }
    }
    """

    def __init__(self, request):
        try:
            if not request.form and not request.data:
                raise NoDataProvidedError
        except NoDataProvidedError:
            raise InvalidDataError("No email or list was provided")
        else:
            if request.data:
                # POST submitted via api
                request_dict = json.loads(request.data)
            else:
                # POST submitted via form
                request_dict = request.form

            try:
                self.email = request_dict["lead"]["email"]
                self.lists = request_dict["lead_options"]["list"].split("++")
            except (BadRequestKeyError, KeyError):
                raise InvalidDataError("Requires both an email and a list")

            self.source = request_dict["campaign"]["title"]
            self.first_name = request_dict["lead"]["firstName"]
            self.last_name = request_dict["lead"]["lastName"]

        # check validity of email
        try:
            headers = {}
            headers["X-API-KEY"] = os.environ.get("EVEREST_API_KEY")
            response = requests.get(
                f"https://api.everest.validity.com/api/2.0/validation/address/{self.email}",
                headers=headers,
            )

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Everest API: {e}")

        else:
            try:
                validity_response = response.json()
                self.validity_status = validity_response["results"][
                    "status"
                ]  # valid/invalid
                self.validity_name = validity_response["results"][
                    "name"
                ]  # e.g. Valid, Domain Invalid, etc.
            except KeyError:
                print("Error parsing Everest API response")

    def subscribe(self):
        """OptInMonster needs a special case for its test code; the test code
        does not send an list, which we typically would reject, but for it to
        accept the webhook it needs a successful response to its sample data.

        We give a successful response if the email is hello@optinmonster.com,
        otherwise we defer to the superclass."""
        if self.email == "hello@optinmonster.com":
            # return a 200 response
            return {"status": "subscribed"}
        return super().subscribe()

class ListRequestHandler:
    def lists_json(self):
        try:
            client = SFClient()
        except SalesforceAuthenticationFailed as e:
            return failure_response(e.__str__())

        list_records = client.query_all("SELECT Name FROM cfg_Subscription__c")
        lists = [x["Name"] for x in list_records["records"]]
        return {"lists": lists}
