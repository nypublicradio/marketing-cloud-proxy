import json
import os
import re
from datetime import datetime

import FuelSDK as ET_Client
import requests
from flask import Flask, Response, request
# TODO: Remove this CORS situation before we push to demo
from flask_cors import CORS
from werkzeug.exceptions import BadRequestKeyError

from marketing_cloud_proxy.client import MarketingCloudAuthManager
from marketing_cloud_proxy.errors import InvalidEmail, NoDataProvidedError
from marketing_cloud_proxy.lists import (
    mailchip_id_to_marketingcloud_list,
    migrated_lists,
)
from marketing_cloud_proxy.settings import MAILCHIMP_PROXY_ENDPOINT

# TODO: Remove this CORS situation before we push to demo
app = Flask(__name__)
CORS(app)

path_prefix = os.environ.get("APP_NAME")


def get_client():
    return MarketingCloudAuthManager.instantiate_client()


def is_valid_email(email):
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))


@app.route(f"/{path_prefix}/", methods=["GET"])
def healthcheck():
    return Response(status=204)


@app.route(f"/{path_prefix}/subscribe", methods=["POST"])
def subscribe():
    stubObj = get_client()

    de4 = ET_Client.ET_DataExtension_Row()
    de4.CustomerKey = os.environ.get("MC_DATA_EXTENSION")
    de4.auth_stub = stubObj

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
    except (BadRequestKeyError, KeyError, NoDataProvidedError) as e:
        return {
            "status": "failure",
            "message": "List or email was not provided",
        }, 400

    # Fail on invalid email
    if not is_valid_email(email_address):
        return {"status": "failure", "message": "Email address is invalid"}, 400

    # Check if list is a Mailchimp ID
    # If it's a mailchimp ID, check if it's been migrated
    # If migrated, convert to Marketing Cloud list and move on in process
    # If not, proxy it to the Mailchimp signup form
    is_mailchimp_id = re.match(r"^[0-9a-fA-F]{10}$", email_list)
    if is_mailchimp_id and email_list in migrated_lists:
        email_list = mailchip_id_to_marketingcloud_list[email_list]
    elif is_mailchimp_id and email_list not in migrated_lists:
        res = requests.post(
            MAILCHIMP_PROXY_ENDPOINT,
            json={"list": email_list, "email": email_address},
        )
        if res.ok:
            return {**json.loads(res.content), "additional_detail": "proxied"}
        else:
            return {
                **json.loads(res.content),
                "additional_detail": "proxied",
            }, res.status_code

    # First attempt to add email to overall Master Preferences data extension
    de4.props = {
        "email_address": email_address,
        "creation_date": datetime.now().strftime("%-m/%-d/%Y %H:%M:%S %p"),
    }
    post_response = de4.post()

    # Then flip the list columns to indicate they have signed up
    de4.props = {
        "email_address": email_address,
        email_list: "true",
        f"{email_list} Opt In Date": datetime.now().strftime("%-m/%-d/%Y %H:%M:%S %p"),
        f"{email_list} Opt out Date": "",
    }
    patch_response = de4.patch()

    return {"status": "success", "message": "Email successfully added"}


@app.route(f"/{path_prefix}/lists")
def lists():
    stubObj = get_client()

    myDEColumn = ET_Client.ET_DataExtension_Column()
    myDEColumn.auth_stub = stubObj
    myDEColumn.props = ["Name"]
    myDEColumn.search_filter = {
        "Property": "CustomerKey",
        "SimpleOperator": "like",
        "Value": os.environ.get("MC_DATA_EXTENSION"),
    }
    getResponse = myDEColumn.get()

    # Reduces response to just fields that contain the phrase "Opt In" (i.e.
    # Radiolab Newsletter Opt In Date) - this will remove non-list fields - then
    # we split on the phrase "Opt In" so it returns *only* the list names
    lists = [
        str(x.Name).split("Opt In")[0]
        for x in getResponse.results
        if "Opt In" in x.Name
    ]
    return {"lists": lists}
