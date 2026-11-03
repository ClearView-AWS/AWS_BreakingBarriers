"""SES sandbox mailer. Without credentials it only records the message.

Sandbox mode can deliver only to verified addresses. School addresses in the
data are on example.org, so a real school cannot be reached by mistake.
"""

from __future__ import annotations

import os


def send_school_question(item: dict) -> dict:
    preview = {
        "to": item.get("email_to"),
        "subject": f"Question from families about {item.get('school_name')}",
        "body": item.get("question"),
        "delivered": False,
        "mode": "recorded",
    }
    if os.environ.get("SES_ENABLED", "").lower() not in {"1", "true", "yes"}:
        return preview
    try:
        import boto3

        client = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        client.send_email(
            Source=os.environ["SES_SOURCE"],
            Destination={"ToAddresses": [os.environ["SES_VERIFIED_TO"]]},
            Message={
                "Subject": {"Data": preview["subject"]},
                "Body": {"Text": {"Data": preview["body"]}},
            },
        )
        preview["delivered"] = True
        preview["mode"] = "ses-sandbox"
    except Exception as exc:
        preview["error"] = str(exc)
    return preview
