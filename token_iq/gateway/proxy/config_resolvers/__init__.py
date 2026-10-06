"""Typed, provenance-aware resolution of proxy settings from DB then env."""

from token_iq.gateway.proxy.config_resolvers._descriptors import (
    FieldDescriptor,
    FieldSource,
    resolve_fields,
)

__all__ = ["FieldDescriptor", "FieldSource", "resolve_fields"]
