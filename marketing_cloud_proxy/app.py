import os
import FuelSDK as ET_Client
from flask import Flask, request, Response
from werkzeug.exceptions import BadRequestKeyError

import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
from sentry_sdk.integrations.flask import FlaskIntegration

from marketing_cloud_proxy.client import EmailSignupRequestHandler, ListRequestHandler
from marketing_cloud_proxy.mailchimp import MailchimpForwarder
from marketing_cloud_proxy.errors import InvalidDataError


sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    integrations=[AwsLambdaIntegration(), FlaskIntegration()],
    environment=os.environ.get("ENV"),
    release=os.environ.get("SENTRY_RELEASE"),
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0
)

app = Flask(__name__)

path_prefix = os.environ.get("APP_NAME")


@app.route(f"/{path_prefix}/", methods=["GET"])
def healthcheck():
    return Response(status=204)

@app.route(f"/{path_prefix}/sentry", methods=["GET"])
def test_sentry():
    division_by_zero = 1 / 0

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
