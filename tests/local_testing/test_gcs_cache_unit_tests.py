from cache_unit_tests import LLMCachingUnitTests
from token_iq.gateway.caching import GatewayCacheType


class TestGCSCacheUnitTests(LLMCachingUnitTests):
    def get_cache_type(self) -> GatewayCacheType:
        return GatewayCacheType.GCS
