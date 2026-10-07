"""
LiteLLM Skills Hook - Proxy integration for skills

This module provides the CustomLogger hook for skills processing.
The actual skill logic is in token_iq/gateway/llms/litellm_proxy/skills/.

Usage:
    from token_iq.gateway.proxy.hooks.litellm_skills import SkillsInjectionHook

    # Register hook in proxy
    token_iq.callbacks.append(SkillsInjectionHook())
"""

# Re-export from the SDK location for convenience
from token_iq.gateway.llms.litellm_proxy.skills import (
    LITELLM_CODE_EXECUTION_TOOL,
    CodeExecutionHandler,
    GatewayInternalTools,
    SkillPromptInjectionHandler,
    SkillsSandboxExecutor,
    code_execution_handler,
    get_litellm_code_execution_tool,
)
from token_iq.gateway.proxy.hooks.litellm_skills.main import (
    SkillsInjectionHook,
    skills_injection_hook,
)

__all__ = [
    "LITELLM_CODE_EXECUTION_TOOL",
    "CodeExecutionHandler",
    "GatewayInternalTools",
    "SkillPromptInjectionHandler",
    "SkillsInjectionHook",
    "SkillsSandboxExecutor",
    "code_execution_handler",
    "get_litellm_code_execution_tool",
    "skills_injection_hook",
]
