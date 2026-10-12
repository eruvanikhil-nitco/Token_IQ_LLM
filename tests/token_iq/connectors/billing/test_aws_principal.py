"""Which AWS principal this installation runs as, which is the template's other parameter.

The one that matters is the role session. A deployment that holds a task role or an instance
profile is told by AWS that it is `arn:aws:sts::…:assumed-role/Name/session`, and that is not a
principal an IAM trust policy can name. Offered as the parameter it is rejected by the template's
own pattern, and if it were not, the stack would deploy a role trusting a principal that never
presents itself and every sync afterwards would fail with an AccessDenied naming nothing.
"""

from __future__ import annotations

from typing import Final

from token_iq.connectors.billing.aws_principal import (
    NO_CREDENTIALS,
    PrincipalDerived,
    PrincipalKnown,
    PrincipalUnknown,
    installation_principal,
    principal_from_caller_arn,
)

TEMPLATE_PATTERN: Final = r"^arn:aws[a-zA-Z-]*:iam::[0-9]{12}:(root|user/.+|role/.+)$"


class _ClientError(Exception):
    """Shaped like botocore's, which is all `_aws_error_code` reads. Importing the real generated
    class is what the connector deliberately avoids."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code, "Message": f"key AKIAEXAMPLE is not valid: {code}"}}


class _NoCredentialsError(Exception):
    pass


_NoCredentialsError.__name__ = "NoCredentialsError"


class TestAnIdentityATrustPolicyCanName:
    def test_a_role_arn_is_the_principal_as_it_stands(self) -> None:
        arn: Final = "arn:aws:iam::123456789012:role/token-iq-task"

        assert principal_from_caller_arn(arn) == PrincipalKnown(arn=arn)

    def test_a_user_arn_is_the_principal_as_it_stands(self) -> None:
        arn: Final = "arn:aws:iam::123456789012:user/token-iq"

        assert principal_from_caller_arn(arn) == PrincipalKnown(arn=arn)

    def test_a_role_under_a_path_keeps_its_path(self) -> None:
        arn: Final = "arn:aws:iam::123456789012:role/service-role/token-iq-task"

        assert principal_from_caller_arn(arn) == PrincipalKnown(arn=arn)

    def test_a_partition_other_than_commercial_aws_is_kept(self) -> None:
        # An installation in GovCloud or China reports arn:aws-us-gov or arn:aws-cn, and rewriting
        # the partition would name an account in a partition the customer cannot reach.
        arn: Final = "arn:aws-us-gov:iam::123456789012:role/token-iq-task"

        assert principal_from_caller_arn(arn) == PrincipalKnown(arn=arn)


class TestARoleSession:
    def test_the_role_behind_the_session_is_the_principal(self) -> None:
        found: Final = principal_from_caller_arn("arn:aws:sts::123456789012:assumed-role/token-iq-task/abc123")

        assert isinstance(found, PrincipalDerived)
        assert found.arn == "arn:aws:iam::123456789012:role/token-iq-task"

    def test_the_derived_arn_is_one_the_template_accepts(self) -> None:
        # The template declares this pattern itself, so a value failing it is a stack that refuses
        # to deploy with nothing to say about why.
        import re

        found: Final = principal_from_caller_arn("arn:aws:sts::123456789012:assumed-role/token-iq-task/i-0abc")

        assert isinstance(found, PrincipalDerived)
        assert re.match(TEMPLATE_PATTERN, found.arn)

    def test_what_it_was_worked_out_from_is_reported_too(self) -> None:
        session: Final = "arn:aws:sts::123456789012:assumed-role/token-iq-task/abc123"

        found: Final = principal_from_caller_arn(session)

        assert isinstance(found, PrincipalDerived)
        assert found.session_arn == session

    def test_the_one_thing_it_cannot_know_is_said_out_loud(self) -> None:
        """A session ARN carries the role's name and not its IAM path, and the two cannot be told
        apart from here. Silence would hand a path-deployed installation a plausible wrong ARN."""
        found: Final = principal_from_caller_arn("arn:aws:sts::123456789012:assumed-role/token-iq-task/abc")

        assert isinstance(found, PrincipalDerived)
        assert "path" in found.note

    def test_a_session_name_with_a_slash_does_not_become_part_of_the_role(self) -> None:
        # EC2 instance profiles use the instance id as the session name, and a session name may
        # itself contain characters that look like a path separator.
        found: Final = principal_from_caller_arn("arn:aws:sts::123456789012:assumed-role/token-iq-task/i-0a/b")

        assert isinstance(found, PrincipalDerived)
        assert found.arn == "arn:aws:iam::123456789012:role/token-iq-task"

    def test_a_govcloud_session_keeps_its_partition(self) -> None:
        found: Final = principal_from_caller_arn("arn:aws-us-gov:sts::123456789012:assumed-role/tiq/abc")

        assert isinstance(found, PrincipalDerived)
        assert found.arn == "arn:aws-us-gov:iam::123456789012:role/tiq"


class TestAnIdentityNobodyCanTrust:
    def test_a_federated_user_is_refused_rather_than_converted(self) -> None:
        """A trust policy cannot name one. Converting it into something that looks like a role ARN
        would be inventing an identity that does not exist."""
        found: Final = principal_from_caller_arn("arn:aws:sts::123456789012:federated-user/bob")

        assert isinstance(found, PrincipalUnknown)
        assert "federated-user/bob" in found.reason

    def test_the_reason_says_who_to_ask(self) -> None:
        found: Final = principal_from_caller_arn("not-an-arn")

        assert isinstance(found, PrincipalUnknown)
        assert "deployed" in found.reason


class TestWhenAwsCannotBeAsked:
    def test_no_credentials_says_so_and_who_can_supply_the_value(self) -> None:
        found: Final = installation_principal(read_arn=_raise(_NoCredentialsError()))

        assert found == PrincipalUnknown(reason=NO_CREDENTIALS)

    def test_a_refusal_names_the_aws_error_code(self) -> None:
        found: Final = installation_principal(read_arn=_raise(_ClientError("InvalidClientTokenId")))

        assert isinstance(found, PrincipalUnknown)
        assert "InvalidClientTokenId" in found.reason

    def test_a_refusal_does_not_repeat_the_message_aws_sent(self) -> None:
        """The code is the actionable half. The message can quote the access key id that failed,
        and this reaches a browser."""
        found: Final = installation_principal(read_arn=_raise(_ClientError("SignatureDoesNotMatch")))

        assert isinstance(found, PrincipalUnknown)
        assert "AKIAEXAMPLE" not in found.reason

    def test_an_unreachable_aws_names_what_went_wrong_without_a_code(self) -> None:
        found: Final = installation_principal(read_arn=_raise(TimeoutError()))

        assert isinstance(found, PrincipalUnknown)
        assert "TimeoutError" in found.reason

    def test_a_working_read_is_turned_into_the_principal(self) -> None:
        found: Final = installation_principal(read_arn=lambda: "arn:aws:iam::123456789012:role/tiq")

        assert found == PrincipalKnown(arn="arn:aws:iam::123456789012:role/tiq")


def _raise(exc: BaseException):
    def read() -> str:
        raise exc

    return read
