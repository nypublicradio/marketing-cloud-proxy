import os

import jwt
import boto3
import FuelSDK
import time

REFRESH_TOKEN_TABLE = (
    os.environ.get("REFRESH_TOKEN_TABLE") or "MarketingCloudAuthTokenStore"
)
client = boto3.client("dynamodb")

config = {
    'accountId': os.environ.get('MC_ACCOUNT_ID'),
    'appsignature': 'none',
    'authenticationurl': os.environ.get('MC_AUTHENTICATION_URL'),
    'baseapiurl': os.environ.get('MC_BASE_API_URL'),
    'clientid': os.environ.get('MC_CLIENT_ID'),
    'clientsecret': os.environ.get('MC_CLIENT_SECRET'),
    'defaultwsdl': os.environ.get('MC_DEFAULT_WSDL'),
    'soapendpoint': os.environ.get('MC_SOAP_ENDPOINT'),
    'useOAuth2Authentication': 'True',
    'wsdl_file_local_loc': os.environ.get("MC_WSDL_FILE_LOCAL_LOCATION")
}


class MarketingCloudAuthManager:
    @staticmethod
    def retrieve_token_data_from_dynamo():
        token_item = client.get_item(
            TableName=REFRESH_TOKEN_TABLE,
            Key={"KeyName": {"S": "MarketingCloudAuthToken"}},
        )
        token_expiration_item = client.get_item(
            TableName=REFRESH_TOKEN_TABLE,
            Key={"KeyName": {"S": "MarketingCloudAuthTokenExpiration"}},
        )
        token = token_item["Item"]["KeyValue"]["S"]
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
        if (token_data["expiresIn"] - time.time()) < 300:
            return True

    @classmethod
    def instantiate_client(cls):
        token_data = cls.retrieve_token_data_from_dynamo()
        jwt_token = jwt.encode(
            {"request": {"user": {**token_data}}},
            "none",
        )
        if cls.is_token_expired(token_data):
            fuel_client = FuelSDK.ET_Client(False, False, config)
            client.put_item(
                TableName=REFRESH_TOKEN_TABLE,
                Item={
                    "KeyName": {"S": "MarketingCloudAuthToken"},
                    "KeyValue": {"S": fuel_client.authToken},
                },
            )
            client.put_item(
                TableName=REFRESH_TOKEN_TABLE,
                Item={
                    "KeyName": {"S": "MarketingCloudAuthTokenExpiration"},
                    "KeyValue": {"N": str(fuel_client.authTokenExpiration)},
                },
            )
            return fuel_client

        return FuelSDK.ET_Client(False, False, {"jwt": jwt_token, **config})


