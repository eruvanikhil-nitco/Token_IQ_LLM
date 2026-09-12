from __future__ import annotations

import pytest

from litellm.proxy.pass_through_endpoints.llm_passthrough_endpoints import (
    _resolve_bedrock_agent_runtime_region,
)


def test_the_primary_region_variable_is_used(monkeypatch):
    monkeypatch.setenv("AWS_REGION_NAME", "eu-west-1")
    assert _resolve_bedrock_agent_runtime_region() == "eu-west-1"


@pytest.mark.parametrize("variable", ["AWS_REGION", "AWS_DEFAULT_REGION"])
def test_the_standard_aws_variables_are_honoured_too(monkeypatch, variable):
    """The model path and the comprehend-medical path both fall back to these. Reading
    only AWS_REGION_NAME meant a deployment configured the standard AWS way got no
    region at all, and the failure showed up as a malformed hostname rather than a
    configuration error."""
    for name in ("AWS_REGION_NAME", "AWS_REGION", "AWS_DEFAULT_REGION"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(variable, "ap-south-1")
    assert _resolve_bedrock_agent_runtime_region() == "ap-south-1"


def test_the_primary_variable_wins_over_the_others(monkeypatch):
    monkeypatch.setenv("AWS_REGION_NAME", "eu-west-1")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    assert _resolve_bedrock_agent_runtime_region() == "eu-west-1"


def test_no_region_configured_is_an_explicit_error(monkeypatch):
    """Previously this produced the hostname bedrock-agent-runtime.None.amazonaws.com,
    so an unset region surfaced as a DNS failure against a host containing the word
    None rather than as a configuration problem anyone could act on."""
    for name in ("AWS_REGION_NAME", "AWS_REGION", "AWS_DEFAULT_REGION"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(Exception) as exc:
        _resolve_bedrock_agent_runtime_region()

    message = str(exc.value)
    assert "region" in message.lower()
    assert "AWS_REGION_NAME" in message
