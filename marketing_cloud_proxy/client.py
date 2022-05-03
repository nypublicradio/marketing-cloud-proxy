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
from simple_salesforce import format_soql, Salesforce, SalesforceLogin
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
        '''
        Authenticates with SF and initializes a Salesforce object
        '''
        session_id, instance = SalesforceLogin(
            username=settings.SF_USERNAME,
            password=settings.SF_PASS,
            security_token=settings.SF_SECURITY_TOKEN,
            domain=settings.SF_DOMAIN
        )
        super().__init__(instance=instance, session_id=session_id)


class EmailSignupRequestHandler:
    def __init__(self, request):
        self.email = self.__extract_email_from_request(request)
        self.list = self.__extract_list_from_request(request)
        self.client = SFClient()

    def is_email_valid(self):
        return bool(re.match(r"[^@]+@[^@]+\.[^@]+", self.email))

    def __extract_email_from_request(self, request):
        [_, email_address] = self.__extract_email_and_list_from_request(request)
        return email_address

    def __extract_list_from_request(self, request):
        [email_list, _] = self.__extract_email_and_list_from_request(request)
        return email_list

    def __extract_email_and_list_from_request(self, request):
        try:
            if not request.form and not request.data:
                raise NoDataProvidedError

            # POST submitted via api
            if request.data:
                request_dict = json.loads(request.data)
                email_list = request_dict["list"]
                email_address = request_dict["email"]

            # POST submitted via form
            else:
                email_list = request.form["list"]
                email_address = request.form["email"]
        except NoDataProvidedError:
            raise InvalidDataError("No email or list was provided")
        except (BadRequestKeyError, KeyError):
            raise InvalidDataError("Requires both an email and a list")
        return [email_list, email_address]

    def subscribe(self):
        '''
        Checks that the email list from the request exists and subscribes the
        email from the request to the list, creating a new Salesforce Contact
        if there isn't an existing one.
        '''
        email_list = self.client.query(format_soql(
            "SELECT Id FROM cfg_Subscription__c WHERE Name = {}", "{}".format(self.list)))

        try:
            list_id = email_list['records'][0]['Id']
        except IndexError:
            return {
                "status": "failure",
                "detail": "User could not be subscribed; list does not exist"
            }, 400

        contacts = self.client.query_all(format_soql(
            "SELECT Id, LastModifiedDate from Contact WHERE Email = {} ORDER BY LastModifiedDate, Id ASC", "{}".format(self.email)
        ))

        try:
            # get the most recent Contact for this email, if one exists
            contact_id = contacts['records'][-1]['Id']
        except IndexError:
            contact = self.client.Contact.create({'LastName': 'NoLastName',
                                                  'Email': format_soql(self.email)})
            if contact['errors']:
                return {
                    "status": "failure",
                    "detail": "User could not be subscribed; error adding Contact"
                }, 400

            contact_id = contact.get('id')

        subscription_member = self.client.cfg_Subscription_Member__c.create({
            'cfg_Subscription__c': list_id,
            'cfg_Contact__c': contact_id
        })
        if subscription_member['errors']:
            return {"status": "failure", "detail": "User could not be subscribed"}, 400

        return {"status": "subscribed", "detail": "Email successfully added to list"}

    @staticmethod
    def failure_response(message):
        return {
            "status": "failure",
            "detail": message,
        }, 400


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
            "creation_date": creation_date
        }
        self.de_row.post()

        # Then, flip the list columns to indicate they have signed up
        self.de_row.props = {
            "email_address": email_address,
            "first_name": first_name,
            "last_name": last_name,
            "plan": plan,
            "plan_status": plan_status,
            "updated_date": updated_date
        }
        patch_response = self.de_row.patch()

        self.response = {"status": "success"}

        if patch_response.results[0].StatusCode == "Error":
            return {"status": "failure"}, 400


class ListRequestHandler:
    def __init__(self):
        self.client = SFClient()

    def lists_json(self):
        list_records = self.client.query_all("SELECT Name FROM cfg_Subscription__c")
        lists = [x['Name'] for x in list_records['records']]
        return {"lists": lists}
