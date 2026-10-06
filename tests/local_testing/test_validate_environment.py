#### What this tests ####
#    This tests the validate environment function

import sys, os
import traceback

import time
from token_iq import gateway as litellm

print(litellm.validate_environment("openai/gpt-3.5-turbo"))
