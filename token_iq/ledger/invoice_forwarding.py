"""The address a customer forwards a bill to, when no API publishes it.

Almost no provider publishes invoices through an API, so a bill reaches Token IQ as a person
typing it in or as a PDF arriving in a mailbox somebody watches. The address of that mailbox is
installation configuration, not product data, which is why it is read from the environment rather
than stored per customer.

A value that is not an address is its own state rather than a blank. Shown as though it worked, a
typo sends a finance team's invoices nowhere and nobody finds out until a month-end close has
nothing to reconcile against; treated as not configured, the same typo hides the fact that somebody
already tried to set it.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Final, TypeAlias

FORWARDING_SETTING: Final = "TOKEN_IQ_INVOICE_FORWARDING_ADDRESS"


@dataclasses.dataclass(frozen=True, slots=True)
class ForwardingAddress:
    address: str


@dataclasses.dataclass(frozen=True, slots=True)
class NoForwardingAddress:
    setting: str


@dataclasses.dataclass(frozen=True, slots=True)
class UnusableForwardingAddress:
    setting: str
    value: str
    problem: str


InvoiceForwarding: TypeAlias = ForwardingAddress | NoForwardingAddress | UnusableForwardingAddress


def address_problem(value: str) -> str | None:
    """What is wrong with this address, in words an administrator can act on.

    Deliberately short of a full RFC 5322 check, which accepts things no mail system here would
    route and rejects nothing a person actually mistypes. These are the mistakes that happen: a
    name with no domain, a domain with no dot, two addresses pasted into one setting, and a value
    that arrived with the quoting still around it.
    """
    local, separator, domain = value.partition("@")
    if not separator:
        return f"{value!r} is not an email address: it has no @."
    if "@" in domain:
        return "There is more than one address here. The setting holds one mailbox."
    if local == "" or domain == "":
        return "An address needs a mailbox name and a domain, either side of the @."
    if any(character.isspace() for character in value):
        return "There is a space in the address."
    if "." not in domain:
        return f"{domain!r} is not a domain name: it has no dot."
    return None


def invoice_forwarding(environ: Mapping[str, str]) -> InvoiceForwarding:
    """Where invoices may be forwarded, or why nowhere.

    Surrounding whitespace is trimmed because a value set from a shell or a secret store routinely
    arrives with a trailing newline, and refusing that as unusable would be pedantry about a
    character nobody typed.
    """
    raw: Final = environ.get(FORWARDING_SETTING, "").strip()
    if raw == "":
        return NoForwardingAddress(setting=FORWARDING_SETTING)
    problem: Final = address_problem(raw)
    if problem is not None:
        return UnusableForwardingAddress(setting=FORWARDING_SETTING, value=raw, problem=problem)
    return ForwardingAddress(address=raw)
