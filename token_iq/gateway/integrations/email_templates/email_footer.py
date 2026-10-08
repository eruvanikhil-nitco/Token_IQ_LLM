from typing import Final

EMAIL_FOOTER: Final = """
<div class="footer">
            <p>© 2026 Token IQ. All rights reserved.</p>
</div>
"""
"""No social links. The three here pointed at another company's Twitter and website under a Token IQ
copyright line, and the GitHub one had an empty href, so a recipient either left for somewhere unrelated
or went nowhere. There is nothing of Token IQ's to link to yet."""


def email_tag(logo_url: str | None) -> str:
    """The logo image for an email, or nothing when the operator has not set one.

    There used to be a default pointing at another company's logo in that company's S3 bucket, so an
    installation that configured nothing fetched a third party's image every time a recipient opened the
    mail, and showed them a brand that is not the one they bought.
    """
    if not logo_url:
        return ""
    return f'<img src="{logo_url}" alt="Token IQ" width="150" height="50" />'


def email_support_line(support_contact: str | None) -> str:
    """The "any questions" line, or nothing when no support address is configured.

    The default used to be another company's address, so a recipient with a question was sent to people
    who have never heard of them.
    """
    if not support_contact:
        return ""
    return f"<p>If you have any questions, please send an email to {support_contact}.</p>"
