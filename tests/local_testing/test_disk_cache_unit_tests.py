from cache_unit_tests import LLMCachingUnitTests
from token_iq.gateway.caching import GatewayCacheType


class TestDiskCacheUnitTests(LLMCachingUnitTests):
    def get_cache_type(self) -> GatewayCacheType:
        return GatewayCacheType.DISK


# if __name__ == "__main__":
#     pytest.main([__file__, "-v", "-s"])
