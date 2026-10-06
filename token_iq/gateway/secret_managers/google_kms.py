"""
This is a file for the Google KMS integration

Relevant issue

Requires:
* `os.environ["GOOGLE_APPLICATION_CREDENTIALS"], os.environ["GOOGLE_KMS_RESOURCE_NAME"]`
* `pip install google-cloud-kms`
"""

import os
from typing import Final

from token_iq import gateway
from token_iq.gateway.proxy._types import KeyManagementSystem


def validate_environment():
    if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
        raise ValueError("Missing required environment variable - GOOGLE_APPLICATION_CREDENTIALS")
    if "GOOGLE_KMS_RESOURCE_NAME" not in os.environ:
        raise ValueError("Missing required environment variable - GOOGLE_KMS_RESOURCE_NAME")


def load_google_kms(use_google_kms: bool | None):
    if use_google_kms is None or use_google_kms is False:
        return
    try:
        from google.cloud import kms_v1

        validate_environment()

        # Create the KMS client
        client: Final = kms_v1.KeyManagementServiceClient()
        gateway.secret_manager_client = client
        gateway._key_management_system = KeyManagementSystem.GOOGLE_KMS
        gateway._google_kms_resource_name = os.getenv("GOOGLE_KMS_RESOURCE_NAME")
    except Exception as e:
        raise e
