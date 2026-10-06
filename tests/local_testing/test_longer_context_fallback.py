#### What this tests ####
#    This tests context fallback dict

import sys, os
import traceback
import pytest

from token_iq import gateway
from token_iq.gateway import longer_context_model_fallback_dict

print(longer_context_model_fallback_dict)
