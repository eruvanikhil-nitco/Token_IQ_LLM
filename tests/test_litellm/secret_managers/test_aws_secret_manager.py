import pytest

from litellm.secret_managers.aws_secret_manager import AWSKeyManagementService_V2


@pytest.fixture
def kms_environment(monkeypatch):
    monkeypatch.setenv("AWS_REGION_NAME", "us-east-1")
    monkeypatch.delenv("LITELLM_LICENSE", raising=False)
    monkeypatch.delenv("LITELLM_SECRET_AWS_KMS_LITELLM_LICENSE", raising=False)


def _service_without_aws_client() -> AWSKeyManagementService_V2:
    return AWSKeyManagementService_V2.__new__(AWSKeyManagementService_V2)


def test_aws_kms_v2_is_usable_on_a_token_iq_plan_without_a_litellm_licence(monkeypatch, kms_environment):
    from litellm.proxy import proxy_server

    monkeypatch.setattr(proxy_server, "premium_user", True)

    _service_without_aws_client().validate_environment()


def test_aws_kms_v2_off_plan_is_refused_with_the_token_iq_plan_named(monkeypatch, kms_environment):
    from litellm.proxy import proxy_server

    monkeypatch.setattr(proxy_server, "premium_user", False)

    with pytest.raises(ValueError, match="Token IQ plan") as refused:
        _service_without_aws_client().validate_environment()

    assert "LITELLM_LICENSE" not in str(refused.value)
