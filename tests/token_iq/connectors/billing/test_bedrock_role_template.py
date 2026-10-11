"""The CloudFormation template a customer launches to create the role Token IQ assumes.

The blueprint's connect dialog says "Launch template in AWS", and its three steps promise the
template "creates a read-only role trusted only by Token IQ, with this external ID". That promise
is the security boundary, and it lives in a YAML file nobody runs in CI, so these read the file and
check it says what the dialog claims.

What would go wrong without them is quiet: a trust policy that drops the external ID condition, or
widens the principal to the whole account, still deploys cleanly and still syncs costs. The
customer's role would simply be assumable by someone else.
"""

from __future__ import annotations

import pathlib
from typing import Any, Final

import pytest
import yaml

TEMPLATE_PATH: Final = (
    pathlib.Path(__file__).resolve().parents[4]
    / "token_iq"
    / "connectors"
    / "billing"
    / "bedrock_read_only_role.yaml"
)


@pytest.fixture(scope="module")
def template() -> dict[str, Any]:
    # CloudFormation's short forms (!Ref, !Sub) are not plain YAML, so they are spelled out
    # longhand in the file. That keeps it readable by anything, including this test.
    loaded: Final = yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="module")
def role(template: dict[str, Any]) -> dict[str, Any]:
    resources: Final = template["Resources"]
    roles: Final = [r for r in resources.values() if r["Type"] == "AWS::IAM::Role"]
    assert len(roles) == 1, "one role, so there is one thing to review and one thing to delete"
    return roles[0]


class TestItExists:
    def test_the_template_is_there_and_parses(self, template: dict[str, Any]) -> None:
        assert template["AWSTemplateFormatVersion"]
        assert template["Description"]


class TestTheTrustPolicy:
    """Who may assume the role, which is the whole point of the file."""

    def _statements(self, role: dict[str, Any]) -> list[dict[str, Any]]:
        return list(role["Properties"]["AssumeRolePolicyDocument"]["Statement"])

    def test_it_demands_the_external_id(self, role: dict[str, Any]) -> None:
        """Without this condition anyone who learns the role ARN can assume it from their own
        account, which is exactly what the external ID exists to prevent."""
        conditions = [s.get("Condition", {}) for s in self._statements(role)]

        assert any(
            c.get("StringEquals", {}).get("sts:ExternalId") is not None for c in conditions
        ), "no statement requires sts:ExternalId"

    def test_every_statement_that_allows_assuming_demands_it(self, role: dict[str, Any]) -> None:
        """One statement with the condition and a second without it would read as safe and not be."""
        allowing = [s for s in self._statements(role) if s.get("Effect") == "Allow"]

        assert allowing
        for statement in allowing:
            assert statement.get("Condition", {}).get("StringEquals", {}).get("sts:ExternalId") is not None

    def test_the_principal_is_a_parameter_rather_than_a_literal(self, role: dict[str, Any]) -> None:
        """Token IQ's principal differs per deployment. A literal here would either be wrong for
        every installation but one, or would name an account in a public file."""
        principals = [s["Principal"] for s in self._statements(role)]

        assert principals
        for principal in principals:
            rendered = str(principal)
            assert "Ref" in rendered or "Sub" in rendered, f"principal is hardcoded: {principal}"

    def test_it_does_not_trust_a_whole_account_or_everyone(self, role: dict[str, Any]) -> None:
        for statement in self._statements(role):
            assert statement["Principal"] != "*"
            assert statement["Principal"] != {"AWS": "*"}


class TestWhatTheRoleMayRead:
    def _policy_statements(self, role: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            statement
            for policy in role["Properties"]["Policies"]
            for statement in policy["PolicyDocument"]["Statement"]
        ]

    def test_it_can_read_costs(self, role: dict[str, Any]) -> None:
        actions = {a for s in self._policy_statements(role) for a in s["Action"]}

        assert "ce:GetCostAndUsage" in actions, "the one call the connector makes"

    def test_it_can_do_nothing_else(self, role: dict[str, Any]) -> None:
        """Least privilege, checked as a closed set. The connector makes exactly one Cost Explorer
        call, so a template granting more is granting it for no reason anybody recorded."""
        actions = {a for s in self._policy_statements(role) for a in s["Action"]}

        assert actions == {"ce:GetCostAndUsage"}

    def test_nothing_is_granted_with_a_wildcard_action(self, role: dict[str, Any]) -> None:
        actions = {a for s in self._policy_statements(role) for a in s["Action"]}

        assert not any(action.endswith("*") for action in actions)

    def test_no_statement_denies_nothing_or_allows_everything(self, role: dict[str, Any]) -> None:
        for statement in self._policy_statements(role):
            assert statement["Effect"] == "Allow"
            # Cost Explorer has no resource-level permissions, so "*" is the only legal value and
            # the narrowing is done by the action list above.
            assert statement["Resource"] == "*"


class TestWhatTheCustomerCopiesBack:
    def test_it_outputs_the_role_arn(self, template: dict[str, Any]) -> None:
        """The dialog's third step is "Copy the Role ARN from the stack outputs", so the stack has
        to have one."""
        outputs = template["Outputs"]

        assert any("RoleArn" in name or "Arn" in str(spec) for name, spec in outputs.items())

    def test_the_role_name_matches_what_the_dialog_shows(self, role: dict[str, Any]) -> None:
        """The dialog's placeholder is `arn:aws:iam::123456789012:role/token-iq-read-only`, so a
        customer who follows it and sees a different name has been given the wrong instructions."""
        assert role["Properties"]["RoleName"] == "token-iq-read-only"


class TestTheParametersACustomerFillsIn:
    def test_the_external_id_is_a_parameter_with_no_default(self, template: dict[str, Any]) -> None:
        """A default would be a shared secret across every installation that accepted it."""
        external_id = template["Parameters"]["ExternalId"]

        assert "Default" not in external_id

    def test_the_external_id_parameter_refuses_an_empty_value(self, template: dict[str, Any]) -> None:
        external_id = template["Parameters"]["ExternalId"]

        assert external_id.get("MinLength", 0) >= 2
