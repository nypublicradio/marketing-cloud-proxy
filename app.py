from datetime import datetime
import os
import FuelSDK as ET_Client
from flask import Flask, request, Response
from werkzeug.exceptions import BadRequestKeyError

from client import MarketingCloudAuthManager

app = Flask(__name__)

path_prefix = os.environ.get("APP_NAME")

client = MarketingCloudAuthManager.instantiate_client()


@app.route("/")
def healthcheck():
    return Response(status=204)


@app.route(f"/{path_prefix}/subscribe", methods=["GET", "POST"])
def subscribe():
    stubObj = client

    de4 = ET_Client.ET_DataExtension_Row()
    de4.CustomerKey = os.environ.get("MC_DATA_EXTENSION")
    de4.auth_stub = stubObj

    if request.method == "POST":
        try:
            list = request.form["list"]
            email = request.form["email"]
        except BadRequestKeyError as e:
            raise Exception(e)
    if request.method == "GET":
        try:
            list = request.args["list"]
            email = request.args["email"]
        except BadRequestKeyError as e:
            raise Exception(e)

    # First attempt to add email to overall Master Preferences data extension
    de4.props = {
        "email_address": email,
        "creation_date": datetime.now().strftime("%-m/%-d/%Y %H:%M:%S %p"),
    }
    de4.post()

    # Then flip the list columns to indicate they have signed up
    de4.props = {
        "email_address": email,
        list: "true",
        f"{list} Opt In Date": datetime.now().strftime("%-m/%-d/%Y %H:%M:%S %p"),
        f"{list} Opt out Date": "",
    }
    de4.patch()

    return "Added"


@app.route(f"/{path_prefix}/update")
def update():
    stubObj = client

    de4 = ET_Client.ET_DataExtension_Row()
    de4.CustomerKey = os.environ.get("MC_DATA_EXTENSION")
    de4.auth_stub = stubObj

    de4.props = {
        "email_address": "0000000001-apitest-wnyc@mikehearn.net",
        "Stations Opt In Date": "",
    }

    postResponse = de4.patch()
    print("Patch Status: " + str(postResponse.status))
    print("Code: " + str(postResponse.code))
    print("Message: " + str(postResponse.message))
    print("Results: " + str(postResponse.results))

    return "Updated"


@app.route(f"/{path_prefix}/lists")
def lists():
    stubObj = client

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
