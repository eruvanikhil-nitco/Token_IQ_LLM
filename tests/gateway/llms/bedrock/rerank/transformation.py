import json

import pytest
from fastapi.testclient import TestClient

from unittest.mock import MagicMock, patch

from token_iq.gateway import rerank
from token_iq.gateway.llms.custom_httpx.http_handler import HTTPHandler
