import os

from flask import Flask, Response, request

# TODO: Remove this CORS situation before we push to demo
from flask_cors import CORS

from marketing_cloud_proxy.client import EmailSignupRequestHandler
from marketing_cloud_proxy.mailchimp import MailchimpForwarder
from marketing_cloud_proxy.errors import InvalidDataError

# TODO: Remove this CORS situation before we push to demo
app = Flask(__name__)
CORS(app)

path_prefix = os.environ.get("APP_NAME")


@app.route(f"/{path_prefix}/", methods=["GET"])
def healthcheck():
    return Response(status=204)


@app.route(f"/{path_prefix}/subscribe", methods=["POST"])
def subscribe():
    try:
        email_handler = EmailSignupRequestHandler(request)
    except InvalidDataError as e:
        return EmailSignupRequestHandler.failure_response(e.args[0])

    if not email_handler.is_email_valid():
        return EmailSignupRequestHandler.failure_response("Email address is invalid")

    mf = MailchimpForwarder(email_handler.email, email_handler.list)
    if mf.is_mailchimp_address:
        if mf.is_list_migrated:
            email_handler.list = mf.to_marketing_cloud_list()
        else:
            return mf.proxy_to_mailchimp()

    return email_handler.subscribe()


# @app.route(f"/{path_prefix}/lists")
# def lists():
#     stubObj = get_client()

#     myDEColumn = ET_Client.ET_DataExtension_Column()
#     myDEColumn.auth_stub = stubObj
#     myDEColumn.props = ["Name"]
#     myDEColumn.search_filter = {
#         "Property": "CustomerKey",
#         "SimpleOperator": "like",
#         "Value": os.environ.get("MC_DATA_EXTENSION"),
#     }
#     getResponse = myDEColumn.get()

#     # Reduces response to just fields that contain the phrase "Opt In" (i.e.
#     # Radiolab Newsletter Opt In Date) - this will remove non-list fields - then
#     # we split on the phrase "Opt In" so it returns *only* the list names
#     lists = [
#         str(x.Name).split("Opt In")[0]
#         for x in getResponse.results
#         if "Opt In" in x.Name
#     ]
#     return {"lists": lists}
