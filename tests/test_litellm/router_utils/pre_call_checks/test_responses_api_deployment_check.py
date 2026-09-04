import asyncio
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest

import json

import litellm
from litellm.integrations.custom_logger import CustomLogger
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
from litellm.types.llms.openai import (
    IncompleteDetails,
    ResponseAPIUsage,
    ResponseCompletedEvent,
    ResponsesAPIResponse,
)
from litellm.types.utils import StandardLoggingPayload








