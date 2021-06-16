import json
import os
import re
import time
from datetime import datetime

import boto3
import FuelSDK
import jwt
import pytz
from werkzeug.exceptions import BadRequestKeyError

from marketing_cloud_proxy import settings
from marketing_cloud_proxy.errors import InvalidDataError, NoDataProvidedError

REFRESH_TOKEN_TABLE = (
    os.environ.get("REFRESH_TOKEN_TABLE") or "MarketingCloudAuthTokenStore"
)
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
    "wsdl_file_local_loc": settings.MC_WSDL_FILE_LOCAL_LOCATION
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


class EmailSignupRequestHandler:
    def __init__(self, request):
        self.email = self.__extract_email_from_request(request)
        self.list = self.__extract_list_from_request(request)
        self.auth_client = MarketingCloudAuthClient.instantiate_client()
        self.de_row = self.__create_data_extension_row_stub()

    def is_email_valid(self):
        return bool(re.match(r"[^@]+@[^@]+\.[^@]+", self.email))

    def __create_data_extension_row_stub(self):
        de_row = FuelSDK.ET_DataExtension_Row()
        de_row.CustomerKey = os.environ.get("MC_DATA_EXTENSION")
        de_row.auth_stub = self.auth_client
        return de_row

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
        # First attempt to add email to overall Master Preferences data extension
        self.de_row.props = {
            "email_address": self.email,
            "creation_date": datetime.now(pytz.timezone("America/New_York")).strftime("%-m/%-d/%Y %H:%M:%S %p"),
        }
        self.de_row.post()

        # Then flip the list columns to indicate they have signed up
        self.de_row.props = {
            "email_address": self.email,
            self.list: "true",
            f"{self.email} Opt In Date": datetime.now(pytz.timezone("America/New_York")).strftime(
                "%-m/%-d/%Y %H:%M:%S %p"
            ),
            f"{self.email} Opt out Date": "",
        }
        patch_response = self.de_row.patch()
        if patch_response.results[0].StatusCode == "Error":
            return {"status": "failure", "message": "User could not be subscribed"}, 400

        return {"status": "subscribed", "message": "Email successfully added"}

    @staticmethod
    def failure_response(message):
        return {
            "status": "failure",
            "message": message,
        }, 400


class ListRequestHandler:
    def __init__(self):
        self.auth_client = MarketingCloudAuthClient.instantiate_client()
        self.de_column_object = self.__create_data_extension_column_stub()

    def __create_data_extension_column_stub(self):
        de_column = FuelSDK.ET_DataExtension_Column()
        de_column.CustomerKey = os.environ.get("MC_DATA_EXTENSION")
        de_column.auth_stub = self.auth_client
        return de_column

    def lists_json(self):
        self.de_column_object.props = ["Name"]
        self.de_column_object.search_filter = {
            "Property": "CustomerKey",
            "SimpleOperator": "like",
            "Value": os.environ.get("MC_DATA_EXTENSION"),
        }
        get_response = self.de_column_object.get()

        # Reduces response to just fields that contain the phrase "Opt In" (i.e.
        # Radiolab Newsletter Opt In Date) - this will remove non-list fields - then
        # we split on the phrase "Opt In" so it returns *only* the list names
        lists = [
            str(x.Name).split("Opt In")[0]
            for x in get_response.results
            if "Opt In" in x.Name
        ]
        return {"lists": lists}
