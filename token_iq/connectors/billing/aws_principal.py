"""Which AWS principal this Token IQ installation runs as.

The CloudFormation template a customer deploys takes two parameters. One is the external ID, which
Token IQ mints. The other is this: the principal their new role will trust. Nothing configured it,
so the connect dialog could only say "ask whoever deployed this", which is an answer a customer
cannot act on at the moment they need it.

AWS already knows. `sts:GetCallerIdentity` needs no permission at all, and it answers for whichever
way the installation holds credentials: a task role, an instance profile, an IAM user, or keys in
the environment.

The part worth care is that the ARN it returns is not always a principal a trust policy accepts. A
role-based deployment gets a session ARN, `arn:aws:sts::…:assumed-role/Name/session`, and pasting
that into the template is rejected by its own pattern. What the trust policy needs is the role
behind the session. Getting that wrong is the worst kind of wrong here: the stack deploys, the role
trusts a principal that will never present itself, and every sync afterwards fails with an
AccessDenied that names nothing on either side.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable
from typing import Final, Protocol, TypeAlias, runtime_checkable

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

_IAM_PRINCIPAL: Final = re.compile(r"^arn:aws[a-zA-Z-]*:iam::[0-9]{12}:(root|user/.+|role/.+)$")
"""The shapes the template accepts, which is the same pattern the template itself declares."""

_ASSUMED_ROLE: Final = re.compile(r"^arn:(?P<partition>aws[a-zA-Z-]*):sts::(?P<account>[0-9]{12}):assumed-role/(?P<role>[^/]+)/")


@dataclasses.dataclass(frozen=True, slots=True)
class PrincipalKnown:
    """AWS answered with an ARN a trust policy takes as it stands."""

    arn: str


@dataclasses.dataclass(frozen=True, slots=True)
class PrincipalDerived:
    """AWS answered with a role session, so the role behind it is the principal.

    The session ARN carries the role's name but not its IAM path, and the two cannot be told apart
    from here. A deployment whose role sits at the root path, which is the usual case, gets the
    right ARN; one under a path has to say so, which is what `note` is for.
    """

    arn: str
    session_arn: str
    note: str


@dataclasses.dataclass(frozen=True, slots=True)
class PrincipalUnknown:
    """Nobody can say, and the reason is the useful part."""

    reason: str


InstallationPrincipal: TypeAlias = PrincipalKnown | PrincipalDerived | PrincipalUnknown

NO_CREDENTIALS: Final = (
    "This installation holds no AWS credentials, so AWS cannot say which principal it runs as. "
    "Whoever deployed it can give you the ARN of the role or user it signs in with."
)

_PATH_NOTE: Final = (
    "Taken from the role session this installation runs as. If that role sits under an IAM path, "
    "use the role's full ARN, which includes the path."
)


def principal_from_caller_arn(arn: str) -> InstallationPrincipal:
    """The principal a customer's role should trust, from what `GetCallerIdentity` returned.

    An identity that cannot be a trust principal at all, a federated user for instance, is reported
    as unknown with its own ARN in the reason rather than converted into something that looks
    plausible.
    """
    if _IAM_PRINCIPAL.match(arn):
        return PrincipalKnown(arn=arn)
    session: Final = _ASSUMED_ROLE.match(arn)
    if session is None:
        return PrincipalUnknown(
            reason=(
                f"This installation signs in to AWS as {arn}, which an IAM trust policy cannot name. "
                "Whoever deployed it can give you the ARN of a role or user to trust instead."
            )
        )
    partition: Final = session.group("partition")
    account: Final = session.group("account")
    role: Final = session.group("role")
    return PrincipalDerived(
        arn=f"arn:{partition}:iam::{account}:role/{role}",
        session_arn=arn,
        note=_PATH_NOTE,
    )


class _CallerIdentity(BaseModel):
    """The one field this needs out of `GetCallerIdentity`, typed rather than read as a mapping.

    boto3 returns an untyped dict. Validating it here means a response that does not carry an ARN
    raises instead of becoming an empty string the dialog would then offer as a parameter.
    """

    arn: str = Field(alias="Arn")


_CALLER_IDENTITY: Final = TypeAdapter(_CallerIdentity)


class _AwsError(BaseModel):
    code: str = Field(alias="Code")


class _AwsErrorResponse(BaseModel):
    error: _AwsError = Field(alias="Error")


_AWS_ERROR: Final = TypeAdapter(_AwsErrorResponse)


@runtime_checkable
class _CarriesAwsResponse(Protocol):
    """What a botocore client error looks like from here.

    Checked by shape rather than by importing botocore's generated exception classes, which is the
    same reason the Bedrock connector catches broadly: those classes are generated at runtime.
    """

    @property
    def response(self) -> object: ...


def _aws_error_code(exc: BaseException) -> str | None:
    """The AWS error code on a client error, or None when the failure is not one.

    The code is the actionable half and carries nothing secret. The message is deliberately not
    read: it can quote the access key id that failed, and this reaches a browser.
    """
    if not isinstance(exc, _CarriesAwsResponse):
        return None
    try:
        return _AWS_ERROR.validate_python(exc.response).error.code or None
    except ValidationError:
        return None


def _reason_for(exc: BaseException) -> str:
    if type(exc).__name__ in ("NoCredentialsError", "PartialCredentialsError"):
        return NO_CREDENTIALS
    code: Final = _aws_error_code(exc)
    if code is not None:
        return (
            f"AWS refused to say who this installation is: {code}. The credentials this deployment "
            "signs in with are missing, expired or rejected, which is for whoever deployed it to fix."
        )
    return (
        f"AWS could not be reached to ask who this installation is: {type(exc).__name__}. "
        "Whoever deployed it can give you the ARN of the role or user it signs in with."
    )


class _Sts(Protocol):
    def get_caller_identity(self) -> object: ...


def _sts_client() -> _Sts:
    """Ambient credentials on purpose, with nothing passed in: the question is which identity Token
    IQ itself holds, which is the same identity `build_cost_explorer` assumes a customer's role
    with."""
    import boto3

    return boto3.client(  # pyright: ignore[reportReturnType, reportUnknownMemberType]  # boto3 types every service client as Unknown
        "sts"
    )


def caller_identity_arn() -> str:
    """What AWS says this installation signs in as.

    `GetCallerIdentity` requires no permission, so an installation that can reach AWS at all can
    answer it.
    """
    return _CALLER_IDENTITY.validate_python(_sts_client().get_caller_identity()).arn


def installation_principal(read_arn: Callable[[], str] = caller_identity_arn) -> InstallationPrincipal:
    """The principal a customer's role should trust, or why nobody can say.

    The read is injected so every branch is testable without AWS, and because the failure branches
    are the ones a fresh installation actually hits.
    """
    try:
        arn: Final = read_arn()
    except Exception as exc:  # noqa: BLE001  # boto3 raises generated classes this module must not import
        return PrincipalUnknown(reason=_reason_for(exc))
    return principal_from_caller_arn(arn)
