import json

import moto
import pytest
import requests
from dotmap import DotMap
from marketing_cloud_proxy import app, client, mailchimp

from tests.conftest import (
    dynamo_table, MockFuelClient, MockFuelClientPatchFailure, MockSFClient
)


@pytest.fixture
def patch_et_client(monkeypatch):
    dynamo_table()
    monkeypatch.setattr(client, "FuelSDK", MockFuelClient)

@pytest.fixture(autouse=True)
def patch_sf_client(monkeypatch):
    monkeypatch.setattr(client, "SFClient", MockSFClient)

def test_healthcheck():
    with app.app.test_client() as test_client:
        res = test_client.get("/marketing-cloud-proxy/")
        assert res.status_code == 204

def test_get_fails():
    with app.app.test_client() as test_client:
        res = test_client.get("/marketing-cloud-proxy/subscribe")
        assert res.status_code == 405

def test_post_with_json():
    with app.app.test_client() as test_client:
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            json={"email": "test-002@example.com", "source": "test", "list": "Radiolab"},
        )
        data = json.loads(res.data)
        assert data["status"] == "subscribed"

def test_post_with_json_no_source():
    with app.app.test_client() as test_client:
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            json={"email": "test-002@example.com", "list": "Radiolab"},
        )
        data = json.loads(res.data)
        assert data["status"] == "subscribed"

def test_post_with_form():
    with app.app.test_client() as test_client:
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test-003@example.com", "list": "Radiolab"},
        )
        data = json.loads(res.data)
        assert data["status"] == "subscribed"

def test_post_with_no_existing_contact(monkeypatch):
    with app.app.test_client() as test_client:
        monkeypatch.setattr(MockSFClient, "query_all", MockSFClient.query_all_no_results)
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test-new-sub@example.com", "list": "Radiolab"},
        )
        data = json.loads(res.data)
        assert data["status"] == "subscribed"

def test_post_with_no_data():
    with app.app.test_client() as test_client:
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            data={},
        )
        data = json.loads(res.data)
        assert data["status"] == "failure"

def test_post_json_with_no_email():
    with app.app.test_client() as test_client:
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            json={"list": "Stations"},
        )
        data = json.loads(res.data)
        assert data["status"] == "failure"

def test_post_json_with_no_list():
    with app.app.test_client() as test_client:
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            json={"email": "test@example.com"},
        )
        data = json.loads(res.data)
        assert data["status"] == "failure"

def test_post_with_multiple_lists():
    with app.app.test_client() as test_client:
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            json={"email": "test-002@example.com",
                  "source": "test source",
                  "list": "Radiolab++Gothamist"},
        )
        data = json.loads(res.data)
        assert data["status"] == "subscribed"

def test_post_form_with_no_email():
    with app.app.test_client() as test_client:
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"list": "Stations"},
        )
        data = json.loads(res.data)
        assert data["status"] == "failure"

def test_post_form_with_no_list():
    with app.app.test_client() as test_client:
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test@example.com"},
        )
        data = json.loads(res.data)
        assert data["status"] == "failure"

def test_invalid_email():
    with app.app.test_client() as test_client:
        res = test_client.post(
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


def test_unmigrated_mailchimp_list_success(monkeypatch):
    with app.app.test_client() as test_client:
        expected_response = b'{"status":"subscribed","email_address":"YWFxoC9mCv-wnyc@mikehearn.net","list_id":"65dbec786b", "detail": "Email successfully added"}'
        monkeypatch.setattr(
            requests,
            "post",
            lambda *args, **kwargs: DotMap({"ok": True, "content": expected_response}),
        )
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test@example.com", "list": "1234567890"},
        )
        data = json.loads(res.data)
        assert {**json.loads(expected_response), "additional_detail": "proxied"} == data

def test_unmigrated_mailchimp_list_failure(monkeypatch):
    with app.app.test_client() as test_client:
        expected_response = b'{"detail":"test@example.com looks fake or invalid, please enter a real email address.","instance":"d5ebfbe4-a25e-2956-7e72-09574da7a6e2","status":400,"title":"Invalid Resource","type":"https://mailchimp.com/developer/marketing/docs/errors/"}'
        monkeypatch.setattr(
            requests,
            "post",
            lambda *args, **kwargs: DotMap({"ok": False, "content": expected_response}),
        )
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test@example.com", "list": "12345abcde"},
        )
        data = json.loads(res.data)
        assert {**json.loads(expected_response), "additional_detail": "proxied"} == data

def test_migrated_mailchimp_list(monkeypatch, mocker):
    with app.app.test_client() as test_client:
        monkeypatch.setattr(
            mailchimp, "mailchimp_id_to_marketingcloud_list", {"12345abcde": "Stations"}
        )
        spy = mocker.spy(client.EmailSignupRequestHandler, "subscribe")
        res = test_client.post(
            "/marketing-cloud-proxy/subscribe",
            data={"email": "test@example.com", "list": "12345abcde"},
        )
        data = json.loads(res.data)
        assert spy.call_args[0][0].lists == ["Stations"]
        assert data["status"] == "subscribed"

@moto.mock_dynamodb
def test_sc_subscription_update(monkeypatch, mocker, patch_et_client):
    dynamo_table()
    with app.app.test_client() as test_client:
        monkeypatch.setattr(client, "FuelSDK", MockFuelClientPatchFailure)
        spy = mocker.spy(client.SupportingCastWebhookHandler, "subscribe")

        # Mock Supporting Cast API responses
        monkeypatch.setattr(
            client.SupportingCastWebhookHandler,
            "_get_member_info_from_id",
            lambda *args, **kwargs: {
                "id": 607420,
                "email": "supportingcast-test-vHCoXHhYrX@mikehearn.net",
                "first_name": "Test",
                "last_name": "McTesterson",
                "external_id": None,
                "status": "suspended",
                "plan_id": 1025,
                "plan_ids": [1025],
                "product_ids": [],
                "login_token": "abc123",
            },
        )
        monkeypatch.setattr(
            client.SupportingCastWebhookHandler,
            "_get_plan_info_from_id",
            lambda *args, **kwargs: {
                "id": 1025,
                "plan_group_id": 315,
                "name": "Butterflies",
                "benefits": {
                    "benefit1": "Ad Free + Audio Extras",
                    "benefit2": "Monthly Audio/Video BTS",
                    "benefit3": "Annual Trivia Night Event + Invitation-Only Virtual Events + Quarterly AMA",
                    "benefit4": "Radiolab Patch",
                    "benefit5": "Early Access to Digital Pop-Up Store + 10% Off",
                },
                "live": True,
                "free": 0,
                "amount": 1000,
                "currency": "usd",
                "interval": "month",
                "interval_count": 1,
                "stripe_pricing_plan_id": "price_1IdGzqJqYS3zuGzpJ9IJlTgh",
                "mailchimp_id": None,
                "private": 0,
            },
        )

        res = test_client.post(
            "/marketing-cloud-proxy/supporting-cast",
            json={
                "event": "subscription.updated",
                "event_id": 586,
                "webhook_id": 34,
                "timestamp": "2021-10-19T14:33:35+00:00",
                "subscription": {
                    "id": 541150,
                    "status": "suspended",
                    "plan_id": "1025",
                    "member_id": 607420,
                },
            },
        )
        assert json.loads(res.data)["status"] == "success"

def test_list_request_handler():
    with app.app.test_client() as test_client:
        res = test_client.get("/marketing-cloud-proxy/lists")
        data = json.loads(res.data)
        assert isinstance(data["lists"], list)

