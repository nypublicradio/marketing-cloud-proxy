import os
from flask import Flask, request, Response

import sentry_sdk
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration
from sentry_sdk.integrations.flask import FlaskIntegration

from marketing_cloud_proxy.client import (
    EmailSignupRequestHandler,
    failure_response,
    ListRequestHandler,
    SupportingCastWebhookHandler,
    OptinmonsterWebhookHandler
)
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
    traces_sample_rate=1.0,
)

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
        return failure_response(e.message)

    if not email_handler.is_email_syntactically_valid():
        return failure_response("Email address is invalid")

    mf_list = map(
        lambda x: MailchimpForwarder(email_handler.email, x), email_handler.lists
    )
    for mf in mf_list:
        if mf.is_mailchimp_address:
            if mf.is_list_migrated:
                email_handler.lists.append(mf.to_marketing_cloud_list())
                email_handler.lists.remove(mf.email_list)
            else:
                return mf.proxy_to_mailchimp()

    return email_handler.subscribe()


@app.route(f"/{path_prefix}/lists")
def lists():
    lqh = ListRequestHandler()
    return lqh.lists_json()


@app.route(f"/{path_prefix}/supporting-cast", methods=["POST"])
def supporting_cast():
    handler = SupportingCastWebhookHandler(request)
    return handler.response


@app.route(f"/{path_prefix}/optinmonster", methods=["POST"])
def optinmonster():
    handler = OptinmonsterWebhookHandler(request)
    response = handler.subscribe()
    return response
