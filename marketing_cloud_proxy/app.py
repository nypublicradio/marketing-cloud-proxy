import os

from flask import Flask, Response, request

from marketing_cloud_proxy.client import EmailSignupRequestHandler, ListRequestHandler
from marketing_cloud_proxy.mailchimp import MailchimpForwarder
from marketing_cloud_proxy.errors import InvalidDataError

app = Flask(__name__)

path_prefix = os.environ.get("APP_NAME")


@app.route(f"/{path_prefix}/", methods=["GET"])
def healthcheck():
    return Response(status=204)


@app.route(f"/{path_prefix}/subscribe", methods=["POST"])
def subscribe():
    try:
        email_handler = EmailSignupRequestHandler(request)
    except InvalidDataError as e:
        return EmailSignupRequestHandler.failure_response(e.message)

    if not email_handler.is_email_valid():
        return EmailSignupRequestHandler.failure_response("Email address is invalid")

    mf = MailchimpForwarder(email_handler.email, email_handler.list)
    if mf.is_mailchimp_address:
        if mf.is_list_migrated:
            email_handler.list = mf.to_marketing_cloud_list()
        else:
            return mf.proxy_to_mailchimp()

    return email_handler.subscribe()


@app.route(f"/{path_prefix}/lists")
def lists():

    lqh = ListRequestHandler()
    return lqh.lists_json()
