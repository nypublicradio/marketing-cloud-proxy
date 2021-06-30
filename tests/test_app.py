import json

import moto
import pytest
import requests
from dotmap import DotMap
from marketing_cloud_proxy import app, client, mailchimp

from tests.conftest import (MockFuelClient, MockFuelClientPatchFailure,
                            dynamo_table)


@pytest.fixture(autouse=True)
def patch_et_client(monkeypatch):
    dynamo_table()
    monkeypatch.setattr(client, "FuelSDK", MockFuelClient)


@moto.mock_dynamodb2
def test_healthcheck():
    with app.app.test_client() as client:
        res = client.get("/marketing-cloud-proxy/")
        assert res.status_code == 204


@moto.mock_dynamodb2
def test_get_fails():
    with app.app.test_client() as client:
        res = client.get("/marketing-cloud-proxy/subscribe")
        assert res.status_code == 405


@moto.mock_dynamodb2
def test_post_with_json():
    dynamo_table()
    with app.app.test_client() as client:
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            json={"email": "test-001@example.com", "list": "Stations"},
        )
        data = json.loads(res.data)
        assert data["status"] == "subscribed"


@moto.mock_dynamodb2
def test_post_with_form():
    dynamo_table()
    with app.app.test_client() as client:
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test-001@example.com", "list": "Stations"},
        )
        data = json.loads(res.data)
        assert data["status"] == "subscribed"


@moto.mock_dynamodb2
def test_post_with_no_data():
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


class ResponseMock:
    def __init__(self, is_ok, response):
        self.ok = is_ok
        self.response = response

    @property
    def ok(self):
        return self.is_ok

    def post(self):
        return self.response


@moto.mock_dynamodb2
def test_unmigrated_mailchimp_list_success(monkeypatch):
    dynamo_table()
    with app.app.test_client() as client:
        expected_response = b'{"status":"subscribed","email_address":"YWFxoC9mCv-wnyc@mikehearn.net","list_id":"65dbec786b", "detail": "Email successfully added"}'
        monkeypatch.setattr(
            requests,
            "post",
            lambda *args, **kwargs: DotMap({"ok": True, "content": expected_response}),
        )
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test@example.com", "list": "1234567890"},
        )
        data = json.loads(res.data)
        assert {**json.loads(expected_response), "additional_detail": "proxied"} == data


@moto.mock_dynamodb2
def test_unmigrated_mailchimp_list_failure(monkeypatch):
    dynamo_table()
    with app.app.test_client() as client:
        expected_response = b'{"detail":"test@example.com looks fake or invalid, please enter a real email address.","instance":"d5ebfbe4-a25e-2956-7e72-09574da7a6e2","status":400,"title":"Invalid Resource","type":"https://mailchimp.com/developer/marketing/docs/errors/"}'
        monkeypatch.setattr(
            requests,
            "post",
            lambda *args, **kwargs: DotMap({"ok": False, "content": expected_response}),
        )
        res = client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test@example.com", "list": "12345abcde"},
        )
        data = json.loads(res.data)
        assert {**json.loads(expected_response), "additional_detail": "proxied"} == data


@moto.mock_dynamodb2
def test_migrated_mailchimp_list(monkeypatch, mocker):
    dynamo_table()
    with app.app.test_client() as test_client:
        monkeypatch.setattr(
            mailchimp, "mailchimp_id_to_marketingcloud_list", {"12345abcde": "Stations"}
        )
        spy = mocker.spy(client.EmailSignupRequestHandler, 'subscribe')
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test@example.com", "list": "12345abcde"},
        )
        data = json.loads(res.data)
        assert spy.call_args[0][0].list == 'Stations'
        assert data["status"] == "subscribed"


@moto.mock_dynamodb2
def test_error_from_marketingcloud(monkeypatch):
    dynamo_table()
    with app.app.test_client() as test_client:
        monkeypatch.setattr(client, "FuelSDK", MockFuelClientPatchFailure)
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test@example.com", "list": "Stations"},
        )
        data = json.loads(res.data)
        assert res.status_code == 400
        assert data["status"] == "failure"
