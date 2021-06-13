import json
import os
import time

import boto3
import FuelSDK
import moto
import pytest
from marketing_cloud_proxy import app

from tests.conftest import MockFuelClient, dynamo_table


@pytest.fixture(autouse=True)
def patch_et_client(monkeypatch):
    dynamo_table()
    monkeypatch.setattr(FuelSDK, "ET_Client", MockFuelClient)
    monkeypatch.setattr(app, "ET_Client", MockFuelClient)


@moto.mock_dynamodb2
def test_healthcheck():
    """Tests being written in test branch, keeping a stub here for pytest to
    process"""
    with app.app.test_client() as client:
        res = client.get("/marketing-cloud-proxy/")
        assert res.status_code == 204


@moto.mock_dynamodb2
def test_get_fails():
    """Tests being written in test branch, keeping a stub here for pytest to
    process"""
    with app.app.test_client() as client:
        res = client.get("/marketing-cloud-proxy/subscribe")
        assert res.status_code == 405


@moto.mock_dynamodb2
def test_post_with_json():
    """Tests being written in test branch, keeping a stub here for pytest to
    process"""

    dynamo_table()
    with app.app.test_client() as client:
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            json={"email": "test-001@example.com", "list": "Stations"},
        )
        data = json.loads(res.data)
        assert data["status"] == "success"


@moto.mock_dynamodb2
def test_post_with_form():
    """Tests being written in test branch, keeping a stub here for pytest to
    process"""

    dynamo_table()
    with app.app.test_client() as client:
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test-001@example.com", "list": "Stations"},
        )
        data = json.loads(res.data)
        assert data["status"] == "success"


@moto.mock_dynamodb2
def test_post_with_no_data():
    """Tests being written in test branch, keeping a stub here for pytest to
    process"""

    dynamo_table()
    with app.app.test_client() as client:
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            data={},
        )
        data = json.loads(res.data)
        assert data["status"] == "failure"


@moto.mock_dynamodb2
def test_post_json_with_no_email():
    """Tests being written in test branch, keeping a stub here for pytest to
    process"""

    dynamo_table()
    with app.app.test_client() as client:
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            json={"list": "Stations"},
        )
        data = json.loads(res.data)
        assert data["status"] == "failure"


@moto.mock_dynamodb2
def test_post_json_with_no_list():
    """Tests being written in test branch, keeping a stub here for pytest to
    process"""

    dynamo_table()
    with app.app.test_client() as client:
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            json={"email": "test@example.com"},
        )
        data = json.loads(res.data)
        assert data["status"] == "failure"


@moto.mock_dynamodb2
def test_post_form_with_no_email():
    """Tests being written in test branch, keeping a stub here for pytest to
    process"""

    dynamo_table()
    with app.app.test_client() as client:
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"list": "Stations"},
        )
        data = json.loads(res.data)
        assert data["status"] == "failure"


@moto.mock_dynamodb2
def test_post_form_with_no_list():
    """Tests being written in test branch, keeping a stub here for pytest to
    process"""

    dynamo_table()
    with app.app.test_client() as client:
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test@example.com"},
        )
        data = json.loads(res.data)
        assert data["status"] == "failure"


@moto.mock_dynamodb2
def test_invalid_email():
    dynamo_table()
    with app.app.test_client() as client:
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "example.com"},
        )
        data = json.loads(res.data)
        assert data["status"] == "failure"


def test_migrated_mailchimp_list():
    pass


def test_unmigrated_mailchimp_list():
    pass
