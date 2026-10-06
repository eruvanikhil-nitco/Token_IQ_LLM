from cache_unit_tests import LLMCachingUnitTests
from token_iq.gateway.caching import LiteLLMCacheType


class TestDiskCacheUnitTests(LLMCachingUnitTests):
    def get_cache_type(self) -> LiteLLMCacheType:
        return LiteLLMCacheType.DISK


# if __name__ == "__main__":
#     pytest.main([__file__, "-v", "-s"])
