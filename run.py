import os

import jwt
import boto3
import FuelSDK
import time

REFRESH_TOKEN_TABLE = (
    os.environ.get("REFRESH_TOKEN_TABLE") or "MarketingCloudAuthTokenStore"
)
client = boto3.client("dynamodb")

config = {}


class MarketingCloudClient:
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
            fuel_client = FuelSDK.ET_Client()
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

        return FuelSDK.ET_Client(False, False, {"jwt": jwt_token})


client = MarketingCloudClient.instantiate_client()

import FuelSDK as ET_Client

stubObj = client
NameOfDE = "ThisWillBeDeleted-Test"

de2 = ET_Client.ET_DataExtension()
de2.auth_stub = stubObj
de2.props = {"Name": NameOfDE, "CustomerKey": NameOfDE}
de2.columns = [
    {
        "Name": "Name",
        "FieldType": "Text",
        "IsPrimaryKey": "true",
        "MaxLength": "100",
        "IsRequired": "true",
    },
    {"Name": "OtherField", "FieldType": "Text"},
]
postResponse = de2.post()
print("Post Status: " + str(postResponse.status))
print("Code: " + str(postResponse.code))
print("Message: " + str(postResponse.message))
print("Results: " + str(postResponse.results))

myDEColumn = ET_Client.ET_DataExtension_Column()
myDEColumn.auth_stub = stubObj
myDEColumn.props = ["Name"]
myDEColumn.search_filter = {
    "Property": "CustomerKey",
    "SimpleOperator": "equals",
    "Value": NameOfDE,
}
getResponse = myDEColumn.get()


print("We did it")
