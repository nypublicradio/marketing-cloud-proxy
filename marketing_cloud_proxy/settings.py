import os

# Endpoint for domain for NYPR's main API, e.g. api.wnyc.org
MAILCHIMP_PROXY_ENDPOINT = (
    f"{os.environ.get('NYPR_API_ENDPOINT')}/opt-in/v1/subscribe/mailchimp"
)

APP_SIGNATURE = "none"
MC_ACCOUNT_ID = os.environ.get("MC_ACCOUNT_ID")
MC_AUTHENTICATION_URL = os.environ.get("MC_AUTHENTICATION_URL")
MC_BASE_API_URL = os.environ.get("MC_BASE_API_URL")
MC_CLIENT_ID = os.environ.get("MC_CLIENT_ID")
MC_CLIENT_SECRET = os.environ.get("MC_CLIENT_SECRET")
MC_DEFAULT_WSDL = os.environ.get("MC_DEFAULT_WSDL")
MC_SOAP_ENDPOINT = os.environ.get("MC_SOAP_ENDPOINT")
MC_WSDL_FILE_LOCAL_LOCATION = os.environ.get("MC_WSDL_FILE_LOCAL_LOCATION")
USE_OAUTH2 = "True"
