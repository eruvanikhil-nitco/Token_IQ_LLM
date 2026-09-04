import pytest
import asyncio
import os
from litellm import Router


# Mark as async test


if __name__ == "__main__":
    asyncio.run(test_router_uses_correct_redis_db())
