import asyncio
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest

import json

from token_iq import gateway
from token_iq.gateway.integrations.custom_logger import CustomLogger
from token_iq.gateway.llms.custom_httpx.http_handler import AsyncHTTPHandler
from token_iq.gateway.types.llms.openai import (
    IncompleteDetails,
    ResponseAPIUsage,
    ResponseCompletedEvent,
    ResponsesAPIResponse,
)
from token_iq.gateway.types.utils import StandardLoggingPayload








