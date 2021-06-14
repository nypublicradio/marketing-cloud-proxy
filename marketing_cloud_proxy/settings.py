import os

# Endpoint for domain for NYPR's main API, e.g. api.wnyc.org
MAILCHIMP_PROXY_ENDPOINT = (
    f"{os.environ.get('NYPR_API_ENDPOINT')}/opt-in/v1/subscribe/mailchimp"
)
