import json
import re

import requests

from marketing_cloud_proxy.settings import MAILCHIMP_PROXY_ENDPOINT

mailchimp_id_to_marketingcloud_list = {
    "8c376c6dff": "We the Commuters",
    "b463fe1dbc": "WNYC Membership",
    "edd6b58c0d": "WNYC Daily Newsletter",
    "901cd87236": "The New Yorker Radio Hour",
    "2fe8150dd6": "Radiolab Newsletter",
    "178fa0b138": "On The Media",
    "0e08e3bf02": "Radiolab Membership",
    "566f296761": "Death, Sex & Money",
    "86919b8734": "WQXR Patrons Circle",
    "aa1c2a6097": "This Week on WQXR",
    "fa9d482354": "New Sounds",
    "78a66ba4f6": "WQXR Membership",
    "65dbec786b": "Gothamist",
    "058457038f": "Politics Brief Newsletter",
    "ba3160706a": "WQXR Daily Playlist",
    "04e4233ec0": "WNYC Producers Circle",
    "c2c9a536bb": "The Greene Space",
    "7d6cb8fe13": "NYPR History Notes",
    "0473b3d0b8": "This Week On WNYC",
    "afb6c01328": "Gothamist Membership",
    "0123456789": "Non-existent List",
}


class MailchimpForwarder:
    """Handles the forwarding of any Mailchimp list id to our Mailchimp opt-in
    endpoint. This only will forward an email address in the event that the list
    id has not been migrated to Marketing Cloud, which is tracked in the
    `migrated_lists` list and verified in the `is_list_migrated` method."""

    def __init__(self, email_address, email_list):
        self.email_address = email_address
        self.email_list = email_list

    @property
    def is_mailchimp_address(self):
        return re.match(r"^[0-9a-fA-F]{10}$", self.email_list)

    @property
    def is_list_migrated(self):
        return mailchimp_id_to_marketingcloud_list.get(self.email_list)

    def proxy_to_mailchimp(self):
        res = requests.post(
            MAILCHIMP_PROXY_ENDPOINT,
            json={"list": self.email_list, "email": self.email_address},
        )
        if res.ok:
            return {
                **json.loads(res.content),
                "additional_detail": "proxied",
                "detail": "Email successfully added"}
        return {
            **json.loads(res.content),
            "additional_detail": "proxied",
        }, res.status_code

    def to_marketing_cloud_list(self):
        return mailchimp_id_to_marketingcloud_list[self.email_list]
