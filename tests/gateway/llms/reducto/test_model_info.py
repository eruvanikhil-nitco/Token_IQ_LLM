import uuid

from token_iq import gateway

from token_iq.gateway.utils import _invalidate_model_cost_lowercase_map


def test_reducto_provider_registration():
    model, custom_llm_provider, _, _ = gateway.get_llm_provider(
        model="reducto/parse-v3"
    )

    assert model == "parse-v3"
    assert custom_llm_provider == "reducto"


def test_get_model_info_preserves_ocr_cost_per_credit():
    test_model_name = f"reducto/test-cost-propagation-{uuid.uuid4().hex[:12]}"
    previous_model_entry = gateway.model_cost.get(test_model_name)
    _invalidate_model_cost_lowercase_map()

    try:
        gateway.register_model(
            {
                test_model_name: {
                    "litellm_provider": "reducto",
                    "mode": "ocr",
                    "ocr_cost_per_credit": 0.003,
                }
            }
        )

        model_info = gateway.get_model_info(
            model=test_model_name,
            custom_llm_provider="reducto",
        )

        assert model_info.get("ocr_cost_per_credit") == 0.003
    finally:
        if previous_model_entry is None:
            gateway.model_cost.pop(test_model_name, None)
        else:
            gateway.model_cost[test_model_name] = previous_model_entry
        _invalidate_model_cost_lowercase_map()
