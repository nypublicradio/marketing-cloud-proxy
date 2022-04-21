import os
import time
from collections import OrderedDict

import boto3
import moto
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
        BillingMode='PAY_PER_REQUEST',
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
    post_response = DotMap({"results": [{"StatusCode": "OK"}]})
    patch_response = DotMap({"results": [{"StatusCode": "OK"}]})

    def __init__(*args, **kwargs):
        pass

    @classmethod
    def ET_DataExtension_Row(cls, *args, **kwargs):
        mocked_properties = DotMap(
            {"post": lambda: cls.post_response, "patch": lambda: cls.patch_response}
        )

        return mocked_properties

    @classmethod
    def ET_Client(cls, *args, **kwargs):
        return DotMap(
            {"authToken": cls.authToken, "authTokenExpiration": cls.authTokenExpiration}
        )


class MockFuelClientPatchFailure(MockFuelClient):
    patch_response = DotMap({"results": [{"StatusCode": "Error"}]})


class MockSFType:
    def __init__(self, name):
        self.name = name

    @staticmethod
    def create(self):
        return OrderedDict([('id', 'abc123xyz'), ('success', True), ('errors', [])])


class MockSFClient:
    def __init__(self):
        pass

    def __getattr__(self, name):
        return MockSFType(name)

    def query(self, query, include_deleted=False, **kwargs):
        return OrderedDict([
            ('totalSize', 1),
            ('done', True),
            ('records', [
                OrderedDict([
                    ('attributes', OrderedDict([
                        ('type', 'cfg_Subscription__c'),
                        ('url', '/services/data/v52.0/sobjects/cfg_Subscription__c/abc123xyz')
                    ])),
                    ('Id', 'abc123xyz')])
            ])
        ])

    def query_all(self, query, include_deleted=False, **kwargs):
        return {
            'records': [
                OrderedDict([
                    ('attributes', OrderedDict([
                        ('type', 'cfg_Subscription__c'),
                        ('url', '/services/data/v52.0/sobjects/cfg_Subscription__c/jkl456qrs')
                    ])),
                    ('Name', 'Gothamist')
                ]),
                OrderedDict([
                    ('attributes', OrderedDict([
                        ('type', 'cfg_Subscription__c'),
                        ('url', '/services/data/v52.0/sobjects/cfg_Subscription__c/def789nop')
                    ])),
                    ('Name', 'Radiolab')
                ])
            ],
            'totalSize': 2,
            'done': True
        }
