from token_iq.policy.capture import should_capture


def test_off_when_nothing_is_configured() -> None:
    # Recording what people typed is not something to start doing by default.
    assert should_capture({}, team_id="t1", provider="openrouter") is False


def test_the_global_switch_still_decides_when_no_override_exists() -> None:
    assert should_capture({"store_prompts_in_spend_logs": True}, team_id="t1") is True
    assert should_capture({"store_prompts_in_spend_logs": False}, team_id="t1") is False


def test_a_team_can_be_excluded_while_the_gateway_captures_everything_else() -> None:
    settings = {
        "store_prompts_in_spend_logs": True,
        "store_prompts_by_team": {"hr": False},
    }

    # The reason this feature exists: one department's traffic is sensitive.
    assert should_capture(settings, team_id="hr") is False
    assert should_capture(settings, team_id="sales") is True


def test_a_team_can_be_captured_while_the_gateway_captures_nothing_else() -> None:
    settings = {
        "store_prompts_in_spend_logs": False,
        "store_prompts_by_team": {"support": True},
    }

    assert should_capture(settings, team_id="support") is True
    assert should_capture(settings, team_id="sales") is False


def test_team_beats_provider_because_privacy_rules_follow_people() -> None:
    settings = {
        "store_prompts_by_team": {"hr": False},
        "store_prompts_by_provider": {"openrouter": True},
    }

    # HR calling a captured provider must still not be captured.
    assert should_capture(settings, team_id="hr", provider="openrouter") is False
    assert should_capture(settings, team_id="sales", provider="openrouter") is True


def test_provider_decides_when_the_team_has_no_rule() -> None:
    settings = {
        "store_prompts_in_spend_logs": True,
        "store_prompts_by_provider": {"bedrock": False},
    }

    assert should_capture(settings, team_id="sales", provider="bedrock") is False
    assert should_capture(settings, team_id="sales", provider="openrouter") is True


def test_a_team_set_to_false_does_not_fall_through_to_the_provider_rule() -> None:
    settings = {
        "store_prompts_by_team": {"hr": False},
        "store_prompts_by_provider": {"openrouter": True},
    }

    # False must stay distinguishable from "not configured", or an exclusion silently
    # reverts to whatever the provider says.
    assert should_capture(settings, team_id="hr", provider="openrouter") is False


def test_a_team_alias_works_so_rules_can_be_written_against_a_readable_name() -> None:
    settings = {"store_prompts_by_team": {"nitco_dev": True}}

    assert should_capture(settings, team_id="9f3c-uuid", team_alias="nitco_dev") is True


def test_an_id_rule_wins_over_an_alias_rule() -> None:
    settings = {"store_prompts_by_team": {"9f3c-uuid": False, "nitco_dev": True}}

    # The id is the unambiguous one; aliases can be renamed or repeated.
    assert should_capture(settings, team_id="9f3c-uuid", team_alias="nitco_dev") is False


def test_settings_written_as_strings_are_honoured() -> None:
    # YAML and the settings UI both hand these back as strings often enough to matter.
    assert should_capture({"store_prompts_in_spend_logs": "true"}) is True
    assert should_capture({"store_prompts_by_team": {"hr": "false"}}, team_id="hr") is False
    assert should_capture({"store_prompts_by_team": {"hr": "TRUE"}}, team_id="hr") is True


def test_nonsense_values_fall_through_rather_than_being_treated_as_on() -> None:
    settings = {"store_prompts_by_team": {"hr": "maybe"}, "store_prompts_in_spend_logs": False}

    assert should_capture(settings, team_id="hr") is False


def test_a_request_with_no_team_still_resolves() -> None:
    settings = {"store_prompts_in_spend_logs": True, "store_prompts_by_team": {"hr": False}}

    # Keys can exist without a team; they must not crash or silently match the "hr" rule.
    assert should_capture(settings, team_id=None, provider="openrouter") is True


def test_the_environment_variable_is_the_last_word_when_nothing_else_is_set() -> None:
    assert should_capture({}, env_default=True) is True


def test_the_legacy_global_key_keeps_its_env_var_fallback() -> None:
    # Upstream semantics, pinned by its own tests: only an explicit true short circuits, and
    # a global false still defers to the environment variable. Changing that would alter
    # behaviour for every deployment using the env var as an override.
    assert should_capture({"store_prompts_in_spend_logs": False}, env_default=True) is True


def test_a_team_rule_overrides_the_environment_variable() -> None:
    # Unlike the legacy global key, a rule naming a specific team has to mean it. An
    # environment variable must not silently re-enable capture for an excluded department.
    settings = {"store_prompts_by_team": {"hr": False}}

    assert should_capture(settings, team_id="hr", env_default=True) is False


def test_a_malformed_table_is_ignored_instead_of_raising() -> None:
    # A hand-edited config should not take request logging down.
    assert should_capture({"store_prompts_by_team": "not-a-mapping"}, team_id="hr") is False
