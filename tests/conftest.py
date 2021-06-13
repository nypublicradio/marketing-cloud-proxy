import os
import time

import boto3
import moto
import pytest
from dotmap import DotMap


@moto.mock_dynamodb2
def dynamo_table():
    DYNAMO_TABLE_NAME = (
        os.environ.get("REFRESH_TOKEN_TABLE") or "MarketingCloudAuthTokenStore"
    )
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.create_table(
        TableName=DYNAMO_TABLE_NAME,
        KeySchema=[{"AttributeName": "KeyName", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "KeyName", "AttributeType": "S"}],
    )
    table.put_item(
        TableName=DYNAMO_TABLE_NAME,
        Item={
            "KeyName": "MarketingCloudAuthToken",
            "KeyValue": "1234567",
        },
    )
    table.put_item(
        TableName=DYNAMO_TABLE_NAME,
        Item={
            "KeyName": "MarketingCloudAuthTokenExpiration",
            "KeyValue": int(time.time()),
        },
    )
    return table


class MockFuelClient:
    authToken = "12345"
    authTokenExpiration = time.time() + 600

    def __init__(*args):
        pass

    @staticmethod
    def ET_DataExtension_Row(*args, **kwargs):
        mocked_properties = DotMap({"post": lambda: True, "patch": lambda: True})

        return mocked_properties
