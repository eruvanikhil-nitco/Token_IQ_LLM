"""Reading the invoice forwarding address out of the installation's environment.

Three states rather than two. An address that cannot receive mail is not the same as no address:
shown as though it worked, a typo sends a finance team's invoices nowhere and nothing says so until
a month-end close has nothing to reconcile against. Treated as unset, the same typo hides that
somebody already configured it and makes the next administrator set it twice.
"""

from __future__ import annotations

from typing import Final

from token_iq.ledger.invoice_forwarding import (
    FORWARDING_SETTING,
    ForwardingAddress,
    NoForwardingAddress,
    UnusableForwardingAddress,
    address_problem,
    invoice_forwarding,
)


def _environ(value: str | None) -> dict[str, str]:
    return {} if value is None else {FORWARDING_SETTING: value}


class TestWhenAnAddressIsConfigured:
    def test_the_address_is_reported_as_it_was_set(self) -> None:
        forwarding: Final = invoice_forwarding(_environ("invoices@example.com"))

        assert forwarding == ForwardingAddress(address="invoices@example.com")

    def test_a_trailing_newline_is_not_a_misconfiguration(self) -> None:
        # A value set from a shell or read out of a secret store routinely arrives with one, and
        # refusing it would be pedantry about a character nobody typed.
        forwarding: Final = invoice_forwarding(_environ("  invoices@example.com\n"))

        assert forwarding == ForwardingAddress(address="invoices@example.com")

    def test_a_subdomain_address_is_accepted(self) -> None:
        forwarding: Final = invoice_forwarding(_environ("invoices@billing.example.co.uk"))

        assert forwarding == ForwardingAddress(address="invoices@billing.example.co.uk")

    def test_a_plus_tag_is_accepted_because_that_is_how_these_are_routed(self) -> None:
        forwarding: Final = invoice_forwarding(_environ("invoices+azure@example.com"))

        assert forwarding == ForwardingAddress(address="invoices+azure@example.com")


class TestWhenNoAddressIsConfigured:
    def test_an_unset_setting_names_itself_so_somebody_can_set_it(self) -> None:
        forwarding: Final = invoice_forwarding(_environ(None))

        assert forwarding == NoForwardingAddress(setting=FORWARDING_SETTING)

    def test_an_empty_setting_is_the_same_as_no_setting(self) -> None:
        assert invoice_forwarding(_environ("   ")) == NoForwardingAddress(setting=FORWARDING_SETTING)


class TestWhenTheAddressCannotReceiveMail:
    def test_a_value_with_no_at_sign_is_reported_as_unusable(self) -> None:
        forwarding: Final = invoice_forwarding(_environ("invoices"))

        assert isinstance(forwarding, UnusableForwardingAddress)
        assert forwarding.value == "invoices"
        assert "@" in forwarding.problem

    def test_the_setting_is_named_alongside_the_problem(self) -> None:
        # Without it, the reader knows an address is wrong and not where to go and fix it.
        forwarding: Final = invoice_forwarding(_environ("invoices@localhost"))

        assert isinstance(forwarding, UnusableForwardingAddress)
        assert forwarding.setting == FORWARDING_SETTING

    def test_two_addresses_pasted_into_one_setting_are_refused(self) -> None:
        problem: Final = address_problem("invoices@example.com, bills@example.com")

        assert problem is not None

    def test_a_domain_with_no_dot_is_refused(self) -> None:
        problem: Final = address_problem("invoices@localhost")

        assert problem is not None
        assert "dot" in problem

    def test_a_mailbox_with_no_name_is_refused(self) -> None:
        assert address_problem("@example.com") is not None

    def test_a_space_inside_the_address_is_refused(self) -> None:
        assert address_problem("invoices @example.com") is not None

    def test_a_usable_address_has_no_problem(self) -> None:
        assert address_problem("invoices@example.com") is None

    def test_the_problem_is_a_sentence_about_this_value_and_not_a_code(self) -> None:
        problem: Final = address_problem("invoices")

        assert problem is not None
        assert problem.endswith(".")
        assert "invoices" in problem
