import json
import re

import requests

from marketing_cloud_proxy.settings import MAILCHIMP_PROXY_ENDPOINT

migrated_lists = ['65dbec786b', 'edd6b58c0d', '8c376c6dff', '178fa0b138', '4b20cc9d05']

mailchip_id_to_marketingcloud_list = {
    "8c376c6dff": "We the Commuters",
    "b463fe1dbc": "WNYC Membership",
    "3b5ed831b1": "Werk It",
    "edd6b58c0d": "WNYC Daily Newsletter",
    "901cd87236": "The New Yorker Radio Hour",
    "2fe8150dd6": "Radiolab Newsletter",
    "178fa0b138": "On The Media",
    "0e08e3bf02": "Radiolab Membership",
    "7730d9adc4": "Open Ears Project",
    "566f296761": "Death Sex and Money",
    "0ea8a9e52a": "Operavore",
    "86919b8734": "WQXR Patrons Circle",
    "aa1c2a6097": "This Week In WQXR",
    "48a53a67ac": "Podcast Sustainers 2021",
    "fa9d482354": "New Sounds",
    "7faa833e53": "WNYC Sustainers 2021",
    "78a66ba4f6": "WQXR Membership",
    "65dbec786b": "Gothamist",
    "058457038f": "Politics Brief Newsletter",
    "ba3160706a": "WQXR Daily Playlist",
    "eb961e9695": "American Standards and Songbook",
    "d58ab29b8a": "La Brega Spanish",
    "4b20cc9d05": "Stations",
    "04e4233ec0": "WNYC Producers Circle",
    "c2c9a536bb": "The Green Space",
    "fedeff63ea": "La Brega English",
    "0b754ca387": "Sponsorship Client Contacts",
    "7d6cb8fe13": "NYPR History Notes",
    "e38e85dd0a": "WQXR Sustainers 2021",
    "0473b3d0b8": "This Week On WNYC",
    "04ba4787d5": "Radio Rookies",
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
        return self.email_list in migrated_lists

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
        return mailchip_id_to_marketingcloud_list[self.email_list]
