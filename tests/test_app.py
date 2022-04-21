import json

import moto
import pytest
import requests
from dotmap import DotMap
from marketing_cloud_proxy import app, client

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


@moto.mock_dynamodb2
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

