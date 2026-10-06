# What is this?
## This tests the braintrust integration

import asyncio
import random
import time
import traceback
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Request

load_dotenv()

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from token_iq import gateway as litellm
from token_iq.gateway.llms.custom_httpx.http_handler import HTTPHandler


def test_braintrust_logging():

    litellm.set_verbose = True

    http_client = HTTPHandler()

    with patch(
        "token_iq.gateway.integrations.braintrust_logging.HTTPHandler.post",
        new=MagicMock(),
    ) as mock_client:
        # set braintrust as a callback, litellm will send the data to braintrust
        litellm.callbacks = ["braintrust"]

        # openai call
        response = litellm.completion(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hi 👋 - i'm openai"}],
        )

        time.sleep(2)
        mock_client.assert_called()


def test_braintrust_logging_specific_project_id():

    litellm.set_verbose = True

    with patch(
        "token_iq.gateway.integrations.braintrust_logging.HTTPHandler.post",
        new=MagicMock(),
    ) as mock_client:
        # set braintrust as a callback, litellm will send the data to braintrust
        litellm.callbacks = ["braintrust"]

        response = litellm.completion(
            model="openai/gpt-4o",
            messages=[{"content": "Hello, how are you?", "role": "user"}],
            metadata={"project_id": "123"},
        )

        time.sleep(2)

        # Check that the log was inserted into the correct project
        mock_client.assert_called()
        _, kwargs = mock_client.call_args
        assert "url" in kwargs
        assert (
            kwargs["url"] == "https://api.braintrustdata.com/v1/project_logs/123/insert"
        )
