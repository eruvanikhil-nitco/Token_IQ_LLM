"""An email the gateway sends names nobody else and fetches nothing from anybody else.

Every alert email used to carry three things belonging to the company this was forked from: a logo fetched
from that company's S3 bucket whenever a recipient opened the mail, its support address under a sentence
inviting the reader to write there, and footer links to its Twitter and website beneath a Token IQ
copyright line. An installation that configured nothing sent all three to its own team.

Decision 0021 saw the first two and left them, weighing "keep theirs" against "invent ours" and refusing to
invent on an operator's behalf. There is a third option, which is to render neither, and these say it holds:
unset produces no image and no support line, rather than an empty `src` or a dangling sentence.
"""

from __future__ import annotations

import re
from typing import Final

import pytest

from token_iq.gateway.integrations.email_templates.email_footer import (
    EMAIL_FOOTER,
    email_support_line,
    email_tag,
)
from token_iq.gateway.integrations.email_templates.key_created_email import (
    KEY_CREATED_EMAIL_TEMPLATE as MODERN_KEY_CREATED,
)
from token_iq.gateway.integrations.email_templates.templates import (
    KEY_CREATED_EMAIL_TEMPLATE,
    MAX_BUDGET_ALERT_EMAIL_TEMPLATE,
    SOFT_BUDGET_ALERT_EMAIL_TEMPLATE,
    TEAM_SOFT_BUDGET_ALERT_EMAIL_TEMPLATE,
    USER_INVITED_EMAIL_TEMPLATE,
)

OURS: Final = "gateway.example.test"
UPSTREAM: Final = re.compile(r"litellm|berri", re.I)
URL: Final = re.compile(r"https?://[^\s\"'<>]+")

FIELDS: Final[dict[str, str]] = {
    "recipient_email": "person@customer.example",
    "key_budget": "10",
    "key_token": "sk-example",
    "base_url": f"https://{OURS}",
    "team_name": "Platform",
    "user_name": "person",
    "max_budget": "10",
    "spend": "9",
    "team_alias": "Platform",
    "soft_limit": "8",
    "key_alias": "a-key",
    "projected_spend": "11",
    "projected_exceeded_date": "2026-11-01",
}


def _render(template: str, *, logo: str | None, support: str | None) -> str:
    """One template filled in, with only the placeholders it actually asks for."""
    asked: Final = set(re.findall(r"{(\w+)}", template))
    values: Final = {name: FIELDS.get(name, "x") for name in asked}
    return (
        template.format(**{**values, "logo_tag": email_tag(logo), "support_line": email_support_line(support)})
        + EMAIL_FOOTER
    )


EVERY_TEMPLATE: Final = (
    KEY_CREATED_EMAIL_TEMPLATE,
    USER_INVITED_EMAIL_TEMPLATE,
    SOFT_BUDGET_ALERT_EMAIL_TEMPLATE,
    TEAM_SOFT_BUDGET_ALERT_EMAIL_TEMPLATE,
    MAX_BUDGET_ALERT_EMAIL_TEMPLATE,
    MODERN_KEY_CREATED,
)


@pytest.mark.parametrize("template", EVERY_TEMPLATE)
def test_nothing_is_fetched_from_anybody_else(template: str) -> None:
    """With nothing configured, the whole mail reaches out to no host at all."""
    rendered: Final = _render(template, logo=None, support=None)
    outside: Final = tuple(url for url in URL.findall(rendered) if OURS not in url)

    assert not outside, f"these leave for somewhere else: {outside}"


@pytest.mark.parametrize("template", EVERY_TEMPLATE)
def test_no_email_names_the_company_this_was_forked_from(template: str) -> None:
    rendered: Final = _render(template, logo=f"https://{OURS}/logo.png", support=f"help@{OURS}")

    assert not UPSTREAM.search(rendered), "an email names the old product or its support domain"


@pytest.mark.parametrize("template", EVERY_TEMPLATE)
def test_an_unset_logo_renders_no_image_rather_than_an_empty_one(template: str) -> None:
    """`<img src="">` is what a naive default would leave, and some clients draw a broken-image icon."""
    rendered: Final = _render(template, logo=None, support=None)

    assert "<img" not in rendered
    assert 'src=""' not in rendered


@pytest.mark.parametrize("template", EVERY_TEMPLATE)
def test_a_configured_logo_is_rendered(template: str) -> None:
    """Guards the test above, which passes just as well against a template that never shows a logo."""
    rendered: Final = _render(template, logo=f"https://{OURS}/logo.png", support=None)

    assert f'<img src="https://{OURS}/logo.png"' in rendered


@pytest.mark.parametrize("template", EVERY_TEMPLATE)
def test_an_unset_support_address_leaves_no_dangling_sentence(template: str) -> None:
    rendered: Final = _render(template, logo=None, support=None)

    assert "please send an email to" not in rendered
    assert "please contact us at" not in rendered


@pytest.mark.parametrize("template", EVERY_TEMPLATE)
def test_a_configured_support_address_is_rendered(template: str) -> None:
    """The other half: omission is for the unset case only."""
    rendered: Final = _render(template, logo=None, support=f"help@{OURS}")

    assert f"help@{OURS}" in rendered


def test_the_footer_links_nowhere_rather_than_somewhere_wrong() -> None:
    """It carried a Token IQ copyright over another company's Twitter and website, and a GitHub link with
    an empty href, so a reader either left for somewhere unrelated or went nowhere."""
    assert not URL.findall(EMAIL_FOOTER)
    assert 'href=""' not in EMAIL_FOOTER
    assert "Token IQ" in EMAIL_FOOTER


def test_the_leak_check_can_detect_a_leak() -> None:
    """Said against a string that must trip it, because every assertion above is an absence."""
    planted: Final = '<img src="https://someone-else.example/logo.png" />'

    assert tuple(url for url in URL.findall(planted) if OURS not in url)
