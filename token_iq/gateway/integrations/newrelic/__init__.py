"""
New Relic AI Monitoring Integration for LiteLLM

This module provides integration with New Relic's AI Monitoring feature to track
LLM requests, responses, and usage metrics.
"""

from token_iq.gateway.integrations.newrelic.newrelic import NewRelicLogger

__all__ = ["NewRelicLogger"]
