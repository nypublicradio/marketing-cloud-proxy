import os

import jwt
import boto3
import FuelSDK
import time

REFRESH_TOKEN_TABLE = os.environ.get("REFRESH_TOKEN_TABLE") or "KeyStore"
client = boto3.client("dynamodb")

config = {}


class MarketingCloudClient:
    def __init__(self):
        self.token_data = self.retrieve_token_data_from_dynamo()
        self.client = self.instantiate_client()

    def retrieve_token_data_from_dynamo(self):
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

    def is_token_expired(self):
        """Checks the expiration time for the current token and, if it is set to
        expire in less than 5 minutes, considers it 'expired' and returns
        True"""
        if (self.token_data["expiresIn"] - time.time()) < 300:
            return True

    def instantiate_client(self):
        jwt_token = jwt.encode(
            {"request": {"user": {**self.token_data}}},
            "none",
        )
        if self.is_token_expired():
            client = FuelSDK.ET_Client()
            # client.authToken
            # client.authTokenExpiration
            # put the auth tokens in dynamo
            return client

        return FuelSDK.ET_Client(False, False, {"jwt": jwt_token})


client = MarketingCloudClient.instantiate_client()
print("We did it")
