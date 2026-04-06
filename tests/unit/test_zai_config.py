"""Tests for zai_config module using bigfoot mocking framework."""

import pytest

import bigfoot


class TestGetZaiDefaultModel:
    """Tests for get_zai_default_model()."""

    def test_returns_configured_model(self) -> None:
        """Returns model from config when set.

        ESCAPE: test_returns_configured_model
          CLAIM: get_zai_default_model returns the value stored in config
          PATH:  config_get("zai_default_model") returns "glm-5", function returns it
          CHECK: result == "glm-5"
          MUTATION: Hardcoding return "glm-4.7" ignores config -> assertion fails
          ESCAPE: None — exact equality on a value distinct from the default
          IMPACT: Wrong model used for all z.AI API calls
        """
        mock_cg = bigfoot.mock("spellbook.core.zai_config:config_get")
        mock_cg.returns("glm-5")

        with bigfoot:
            from spellbook.core.zai_config import get_zai_default_model

            result = get_zai_default_model()

        assert result == "glm-5"
        mock_cg.assert_call(args=("zai_default_model",), kwargs={})

    def test_returns_default_when_not_configured(self) -> None:
        """Returns 'glm-4.7' when config has no value.

        ESCAPE: test_returns_default_when_not_configured
          CLAIM: get_zai_default_model returns 'glm-4.7' when config_get returns None
          PATH:  config_get returns None, function falls back to hardcoded default
          CHECK: result == "glm-4.7"
          MUTATION: Changing default to "glm-5" or returning None -> assertion fails
          ESCAPE: None — exact string equality on the specific default
          IMPACT: Incorrect default model used across all features
        """
        mock_cg = bigfoot.mock("spellbook.core.zai_config:config_get")
        mock_cg.returns(None)

        with bigfoot:
            from spellbook.core.zai_config import get_zai_default_model

            result = get_zai_default_model()

        assert result == "glm-4.7"
        mock_cg.assert_call(args=("zai_default_model",), kwargs={})


class TestSetZaiDefaultModel:
    """Tests for set_zai_default_model()."""

    def test_calls_config_set_with_model_id(self) -> None:
        """Stores model ID under zai_default_model key.

        ESCAPE: test_calls_config_set_with_model_id
          CLAIM: set_zai_default_model delegates to config_set with correct key and value
          PATH:  config_set("zai_default_model", "glm-5") is invoked
          CHECK: config_set called with exact positional args
          MUTATION: Using wrong key like "default_model" -> assert_call fails
          ESCAPE: None — assert_call verifies both key name and model ID
          IMPACT: Model preference lost across sessions
        """
        mock_cs = bigfoot.mock("spellbook.core.zai_config:config_set")
        mock_cs.returns({"status": "ok", "config": {"zai_default_model": "glm-5"}})

        with bigfoot:
            from spellbook.core.zai_config import set_zai_default_model

            set_zai_default_model("glm-5")

        mock_cs.assert_call(args=("zai_default_model", "glm-5"), kwargs={})


class TestGetZaiApiKey:
    """Tests for get_zai_api_key()."""

    def test_returns_env_var_when_set(self, monkeypatch) -> None:
        """Returns ZAI_API_KEY env var when set, ignoring config.

        ESCAPE: test_returns_env_var_when_set
          CLAIM: Environment variable takes priority over config for API key
          PATH:  os.environ["ZAI_API_KEY"] = "env-key-123", function returns it
          CHECK: result == "env-key-123"
          MUTATION: Checking config first and returning config value -> assertion fails
                   because env var value differs from what config would return
          ESCAPE: None — the env var value is unique; if config were checked first
                  and returned something different, the assertion would catch it.
                  The real config_get returns None (no file), which is also != "env-key-123".
          IMPACT: ZAI_API_KEY env override silently ignored
        """
        monkeypatch.setenv("ZAI_API_KEY", "env-key-123")

        # No mock for config_get: the implementation must short-circuit on env var.
        # If it incorrectly calls config_get, the real function returns None,
        # and the assertion still catches the bug (None != "env-key-123").
        with bigfoot:
            from spellbook.core.zai_config import get_zai_api_key

            result = get_zai_api_key()

        assert result == "env-key-123"

    def test_returns_config_when_env_not_set(self, monkeypatch) -> None:
        """Returns config value when env var is not set.

        ESCAPE: test_returns_config_when_env_not_set
          CLAIM: Falls back to config when ZAI_API_KEY env var is absent
          PATH:  os.environ has no ZAI_API_KEY, config_get("zai_api_key") returns value
          CHECK: result == "config-key-456"
          MUTATION: Not falling back to config (returning None) -> assertion fails
          ESCAPE: None — exact value verified, distinct from env var test value
          IMPACT: API key stored in config never used
        """
        monkeypatch.delenv("ZAI_API_KEY", raising=False)

        mock_cg = bigfoot.mock("spellbook.core.zai_config:config_get")
        mock_cg.returns("config-key-456")

        with bigfoot:
            from spellbook.core.zai_config import get_zai_api_key

            result = get_zai_api_key()

        assert result == "config-key-456"
        mock_cg.assert_call(args=("zai_api_key",), kwargs={})

    def test_returns_none_when_neither_set(self, monkeypatch) -> None:
        """Returns None when neither env var nor config has API key.

        ESCAPE: test_returns_none_when_neither_set
          CLAIM: Function returns None when no API key is available anywhere
          PATH:  os.environ has no ZAI_API_KEY, config_get returns None
          CHECK: result is None
          MUTATION: Returning empty string "" instead of None -> assertion fails
          ESCAPE: A function returning any falsy non-None value (0, False, "")
                  would pass an "is not None" check but fails "is None" check
          IMPACT: Cannot distinguish unconfigured from misconfigured
        """
        monkeypatch.delenv("ZAI_API_KEY", raising=False)

        mock_cg = bigfoot.mock("spellbook.core.zai_config:config_get")
        mock_cg.returns(None)

        with bigfoot:
            from spellbook.core.zai_config import get_zai_api_key

            result = get_zai_api_key()

        assert result is None
        mock_cg.assert_call(args=("zai_api_key",), kwargs={})


class TestSetZaiApiKey:
    """Tests for set_zai_api_key()."""

    def test_calls_config_set_with_api_key(self) -> None:
        """Stores API key under zai_api_key config key.

        ESCAPE: test_calls_config_set_with_api_key
          CLAIM: set_zai_api_key delegates to config_set with correct key and value
          PATH:  config_set("zai_api_key", "sk-abc123") is invoked
          CHECK: config_set called with exact positional args
          MUTATION: Using wrong key like "api_key" -> assert_call fails
          ESCAPE: None — assert_call verifies both key name and value
          IMPACT: API key stored under wrong key, never retrieved
        """
        mock_cs = bigfoot.mock("spellbook.core.zai_config:config_set")
        mock_cs.returns({"status": "ok", "config": {"zai_api_key": "sk-abc123"}})

        with bigfoot:
            from spellbook.core.zai_config import set_zai_api_key

            set_zai_api_key("sk-abc123")

        mock_cs.assert_call(args=("zai_api_key", "sk-abc123"), kwargs={})


class TestGetZaiTaskRouting:
    """Tests for get_zai_task_routing()."""

    def test_returns_configured_routing(self) -> None:
        """Returns task routing config when set.

        ESCAPE: test_returns_configured_routing
          CLAIM: Returns the routing dict from config when present
          PATH:  config_get("zai_task_routing") returns routing dict
          CHECK: result == expected routing dict with exact keys and values
          MUTATION: Returning {} always -> assertion fails
          ESCAPE: None — full dict equality on a non-trivial dict
          IMPACT: Task-to-model routing not applied
        """
        expected = {"coding": "glm-5", "review": "glm-4.7", "vision": "glm-4.6v"}
        mock_cg = bigfoot.mock("spellbook.core.zai_config:config_get")
        mock_cg.returns(expected)

        with bigfoot:
            from spellbook.core.zai_config import get_zai_task_routing

            result = get_zai_task_routing()

        assert result == expected
        mock_cg.assert_call(args=("zai_task_routing",), kwargs={})

    def test_returns_empty_dict_when_not_configured(self) -> None:
        """Returns empty dict when config has no routing.

        ESCAPE: test_returns_empty_dict_when_not_configured
          CLAIM: Returns {} when config_get returns None
          PATH:  config_get("zai_task_routing") returns None
          CHECK: result == {}
          MUTATION: Returning None instead of {} -> assertion fails
          ESCAPE: None — {} is falsy but distinct from None
          IMPACT: Callers get None, causing AttributeError on dict operations
        """
        mock_cg = bigfoot.mock("spellbook.core.zai_config:config_get")
        mock_cg.returns(None)

        with bigfoot:
            from spellbook.core.zai_config import get_zai_task_routing

            result = get_zai_task_routing()

        assert result == {}
        mock_cg.assert_call(args=("zai_task_routing",), kwargs={})


class TestSetZaiTaskRouting:
    """Tests for set_zai_task_routing()."""

    def test_calls_config_set_with_routing(self) -> None:
        """Stores routing dict under zai_task_routing key.

        ESCAPE: test_calls_config_set_with_routing
          CLAIM: set_zai_task_routing delegates to config_set with correct key and value
          PATH:  config_set("zai_task_routing", routing) is invoked
          CHECK: config_set called with exact args
          MUTATION: Using wrong key -> assert_call fails
          ESCAPE: None — both key and value verified
          IMPACT: Routing stored under wrong key, never applied
        """
        routing = {"coding": "glm-5", "review": "glm-4.7"}
        mock_cs = bigfoot.mock("spellbook.core.zai_config:config_set")
        mock_cs.returns({"status": "ok", "config": {"zai_task_routing": routing}})

        with bigfoot:
            from spellbook.core.zai_config import set_zai_task_routing

            set_zai_task_routing(routing)

        mock_cs.assert_call(args=("zai_task_routing", routing), kwargs={})


class TestGetZaiConcurrencyLimits:
    """Tests for get_zai_concurrency_limits()."""

    def test_returns_configured_limits(self) -> None:
        """Returns concurrency limits from config when set.

        ESCAPE: test_returns_configured_limits
          CLAIM: Returns the concurrency limits dict from config
          PATH:  config_get("zai_concurrency_limits") returns limits dict
          CHECK: result == expected limits dict
          MUTATION: Returning {} always -> assertion fails
          ESCAPE: None — full dict equality on non-trivial dict
          IMPACT: Custom concurrency limits ignored
        """
        expected = {"max_concurrent_per_model": 5, "global_max_concurrent": 20}
        mock_cg = bigfoot.mock("spellbook.core.zai_config:config_get")
        mock_cg.returns(expected)

        with bigfoot:
            from spellbook.core.zai_config import get_zai_concurrency_limits

            result = get_zai_concurrency_limits()

        assert result == expected
        mock_cg.assert_call(args=("zai_concurrency_limits",), kwargs={})

    def test_returns_empty_dict_when_not_configured(self) -> None:
        """Returns empty dict when config has no limits.

        ESCAPE: test_returns_empty_dict_when_not_configured
          CLAIM: Returns {} when config_get returns None
          PATH:  config_get("zai_concurrency_limits") returns None
          CHECK: result == {}
          MUTATION: Returning None -> assertion fails
          ESCAPE: None — {} != None
          IMPACT: Callers get None instead of dict
        """
        mock_cg = bigfoot.mock("spellbook.core.zai_config:config_get")
        mock_cg.returns(None)

        with bigfoot:
            from spellbook.core.zai_config import get_zai_concurrency_limits

            result = get_zai_concurrency_limits()

        assert result == {}
        mock_cg.assert_call(args=("zai_concurrency_limits",), kwargs={})


class TestGetZaiModelsConfig:
    """Tests for get_zai_models_config()."""

    def test_returns_configured_models(self) -> None:
        """Returns user model definitions from config.

        ESCAPE: test_returns_configured_models
          CLAIM: Returns the raw model config list from config
          PATH:  config_get("zai_models") returns list of model dicts
          CHECK: result == expected list with exact structure
          MUTATION: Returning {} always -> assertion fails (list != dict)
          ESCAPE: None — full list equality with non-trivial content
          IMPACT: User-configured models not loaded into registry
        """
        expected = [
            {
                "id": "zai-coding-plan/custom-model",
                "name": "custom-model",
                "display_name": "Custom Model",
                "max_concurrent": 3,
                "context_size": 128000,
                "description": "A custom model",
                "use_cases": ["custom"],
            }
        ]
        mock_cg = bigfoot.mock("spellbook.core.zai_config:config_get")
        mock_cg.returns(expected)

        with bigfoot:
            from spellbook.core.zai_config import get_zai_models_config

            result = get_zai_models_config()

        assert result == expected
        mock_cg.assert_call(args=("zai_models",), kwargs={})

    def test_returns_empty_list_when_not_configured(self) -> None:
        """Returns empty list when config has no user models.

        ESCAPE: test_returns_empty_list_when_not_configured
          CLAIM: Returns [] when config_get returns None
          PATH:  config_get("zai_models") returns None
          CHECK: result == []
          MUTATION: Returning None -> assertion fails
          ESCAPE: None — [] != None
          IMPACT: Callers must handle None instead of empty list
        """
        mock_cg = bigfoot.mock("spellbook.core.zai_config:config_get")
        mock_cg.returns(None)

        with bigfoot:
            from spellbook.core.zai_config import get_zai_models_config

            result = get_zai_models_config()

        assert result == []
        mock_cg.assert_call(args=("zai_models",), kwargs={})


class TestIsZaiConfigured:
    """Tests for is_zai_configured()."""

    def test_returns_true_when_api_key_set(self) -> None:
        """Returns True when API key is available.

        ESCAPE: test_returns_true_when_api_key_set
          CLAIM: is_zai_configured returns True when get_zai_api_key returns a value
          PATH:  get_zai_api_key() returns "sk-test-key", function returns True
          CHECK: result is True
          MUTATION: Always returning False -> assertion fails
          ESCAPE: None — True is checked explicitly with `is True`
          IMPACT: ZAI features disabled even when properly configured
        """
        mock_get_key = bigfoot.mock("spellbook.core.zai_config:get_zai_api_key")
        mock_get_key.returns("sk-test-key")

        with bigfoot:
            from spellbook.core.zai_config import is_zai_configured

            result = is_zai_configured()

        assert result is True
        mock_get_key.assert_call(args=(), kwargs={})

    def test_returns_false_when_no_api_key(self) -> None:
        """Returns False when no API key is configured.

        ESCAPE: test_returns_false_when_no_api_key
          CLAIM: is_zai_configured returns False when get_zai_api_key returns None
          PATH:  get_zai_api_key() returns None, function returns False
          CHECK: result is False
          MUTATION: Always returning True -> assertion fails
          ESCAPE: None — False is checked explicitly with `is False`
          IMPACT: ZAI features enabled without authentication, causing API errors
        """
        mock_get_key = bigfoot.mock("spellbook.core.zai_config:get_zai_api_key")
        mock_get_key.returns(None)

        with bigfoot:
            from spellbook.core.zai_config import is_zai_configured

            result = is_zai_configured()

        assert result is False
        mock_get_key.assert_call(args=(), kwargs={})
