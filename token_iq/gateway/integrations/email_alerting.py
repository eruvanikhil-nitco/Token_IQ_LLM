"""
Functions for sending Email Alerts
"""

import os
from typing import Final

from token_iq.gateway._logging import verbose_logger, verbose_proxy_logger
from token_iq.gateway.integrations.email_templates.email_footer import email_support_line, email_tag
from token_iq.gateway.proxy._types import WebhookEvent
from token_iq.gateway.repositories.team_repository import TeamRepository

# we use this for the email header, please send a test email if you change this. verify it looks good on email


async def get_all_team_member_emails(team_id: str | None = None) -> list:
    verbose_logger.debug("Email Alerting: Getting all team members for team_id=%s", team_id)
    if team_id is None:
        return []
    from token_iq.gateway.proxy.proxy_server import prisma_client

    if prisma_client is None:
        raise Exception("Not connected to DB!")

    team_row: Final = await TeamRepository(prisma_client).table.find_unique(
        where={
            "team_id": team_id,
        }
    )

    if team_row is None:
        return []

    _team_members: Final = team_row.members_with_roles
    verbose_logger.debug(
        "Email Alerting: Got team members for team_id=%s Team Members: %s",
        team_id,
        _team_members,
    )
    _team_member_user_ids: Final[list[str]] = []
    for member in _team_members:
        if member and isinstance(member, dict):
            _user_id = member.get("user_id")
            if _user_id and isinstance(_user_id, str):
                _team_member_user_ids.append(_user_id)

    sql_query: Final = """
        SELECT user_email
        FROM "LiteLLM_UserTable"
        WHERE user_id = ANY($1::TEXT[]);
    """

    _result: Final = await prisma_client.db.query_raw(sql_query, _team_member_user_ids)

    verbose_logger.debug("Email Alerting: Got all Emails for team, emails=%s", _result)

    if _result is None:
        return []

    emails: Final = []
    for user in _result:
        if user and isinstance(user, dict) and user.get("user_email", None) is not None:
            emails.append(user.get("user_email"))
    return emails


async def send_team_budget_alert(webhook_event: WebhookEvent) -> bool:
    """
    Send an Email Alert to All Team Members when the Team Budget is crossed
    Returns -> True if sent, False if not.
    """
    from token_iq.gateway.proxy.utils import send_email

    _team_id: Final = webhook_event.team_id
    team_alias: Final = webhook_event.team_alias
    verbose_logger.debug("Email Alerting: Sending Team Budget Alert for team=%s", team_alias)

    email_logo_url = os.getenv("SMTP_SENDER_LOGO", os.getenv("EMAIL_LOGO_URL", None))
    email_support_contact = os.getenv("EMAIL_SUPPORT_CONTACT", None)

    # await self._check_if_using_premium_email_feature(
    #     premium_user, email_logo_url, email_support_contact
    # )

    # No default for either. They used to fall back to another company's logo, served from that
    # company's S3 bucket, and to its support address, so an installation that configured neither sent
    # its team a mail fetching an image from a third party and telling them to write to a company they
    # have no relationship with. Unset now means the line is left out.
    logo_tag: Final = email_tag(email_logo_url)
    support_line: Final = email_support_line(email_support_contact)
    recipient_emails: Final = await get_all_team_member_emails(_team_id)
    recipient_emails_str: Final[str] = ",".join(recipient_emails)
    verbose_logger.debug("Email Alerting: Sending team budget alert to %s", recipient_emails_str)

    event_name: Final = webhook_event.event_message
    max_budget: Final = webhook_event.max_budget
    email_html_content = "Alert from Token IQ"

    if recipient_emails_str is None:
        verbose_proxy_logger.warning(
            "Email Alerting: Trying to send email alert to no recipient, got recipient_emails=%s",
            recipient_emails_str,
        )

    email_html_content = f"""
    {logo_tag}
    Budget Crossed for Team <b> {team_alias} </b> <br/> <br/>

    Your team's LLM API usage has crossed its <b> budget of ${max_budget} </b>, current spend is <b>${webhook_event.spend}</b><br /> <br />

    API requests will be rejected until either (a) you increase your budget or (b) your budget gets reset <br /> <br />

    {support_line}
    Best, <br />
    The Token IQ team <br />
    """

    email_event: Final = {
        "to": recipient_emails_str,
        "subject": f"LiteLLM {event_name} for Team {team_alias}",
        "html": email_html_content,
    }

    await send_email(
        receiver_email=email_event["to"],
        subject=email_event["subject"],
        html=email_event["html"],
    )

    return False
