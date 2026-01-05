"""Tests for coordination backend base class."""
import pytest
from abc import ABC
from spellbook_mcp.coordination.backends.base import (
    CoordinationBackend,
    BACKENDS,
    register_backend,
    get_backend
)


class TestCoordinationBackendAbstractClass:
    """Test the abstract CoordinationBackend base class."""

    def test_coordination_backend_is_abstract(self):
        """CoordinationBackend should be an abstract base class."""
        assert issubclass(CoordinationBackend, ABC)

    def test_cannot_instantiate_coordination_backend_directly(self):
        """Cannot instantiate CoordinationBackend without implementing abstract methods."""
        with pytest.raises(TypeError) as exc_info:
            CoordinationBackend()

        error_msg = str(exc_info.value)
        assert "abstract" in error_msg.lower()

    def test_coordination_backend_has_create_swarm_method(self):
        """CoordinationBackend must define create_swarm abstract method."""
        assert hasattr(CoordinationBackend, "create_swarm")
        assert getattr(CoordinationBackend.create_swarm, "__isabstractmethod__", False)

    def test_coordination_backend_has_register_worker_method(self):
        """CoordinationBackend must define register_worker abstract method."""
        assert hasattr(CoordinationBackend, "register_worker")
        assert getattr(CoordinationBackend.register_worker, "__isabstractmethod__", False)

    def test_coordination_backend_has_report_progress_method(self):
        """CoordinationBackend must define report_progress abstract method."""
        assert hasattr(CoordinationBackend, "report_progress")
        assert getattr(CoordinationBackend.report_progress, "__isabstractmethod__", False)

    def test_coordination_backend_has_report_complete_method(self):
        """CoordinationBackend must define report_complete abstract method."""
        assert hasattr(CoordinationBackend, "report_complete")
        assert getattr(CoordinationBackend.report_complete, "__isabstractmethod__", False)

    def test_coordination_backend_has_report_error_method(self):
        """CoordinationBackend must define report_error abstract method."""
        assert hasattr(CoordinationBackend, "report_error")
        assert getattr(CoordinationBackend.report_error, "__isabstractmethod__", False)

    def test_coordination_backend_has_get_status_method(self):
        """CoordinationBackend must define get_status abstract method."""
        assert hasattr(CoordinationBackend, "get_status")
        assert getattr(CoordinationBackend.get_status, "__isabstractmethod__", False)

    def test_coordination_backend_has_subscribe_events_method(self):
        """CoordinationBackend must define subscribe_events abstract method."""
        assert hasattr(CoordinationBackend, "subscribe_events")
        assert getattr(CoordinationBackend.subscribe_events, "__isabstractmethod__", False)


class TestBackendRegistry:
    """Test backend registry functions."""

    def test_backends_dict_exists(self):
        """BACKENDS should be a dictionary."""
        assert isinstance(BACKENDS, dict)

    def test_register_backend_adds_to_registry(self):
        """register_backend should add backend class to BACKENDS dict."""
        # Create a mock backend class
        class MockBackend(CoordinationBackend):
            async def create_swarm(self, feature, manifest_path, auto_merge):
                return "mock-swarm-id"

            async def register_worker(self, swarm_id, packet_id, packet_name, tasks_total, worktree):
                return {}

            async def report_progress(self, swarm_id, packet_id, task_id, task_name, status, tasks_completed, tasks_total, commit=None):
                return {}

            async def report_complete(self, swarm_id, packet_id, final_commit, tests_passed, review_passed):
                return {}

            async def report_error(self, swarm_id, packet_id, task_id, error_type, message, recoverable):
                return {}

            async def get_status(self, swarm_id):
                return {}

            async def subscribe_events(self, swarm_id):
                yield {"event": "test"}

        # Clear registry to avoid test pollution
        BACKENDS.clear()

        # Register backend
        register_backend("mock", MockBackend)

        # Verify registration
        assert "mock" in BACKENDS
        assert BACKENDS["mock"] is MockBackend

    def test_register_backend_overwrites_existing(self):
        """register_backend should overwrite existing backend with same name."""
        class MockBackend1(CoordinationBackend):
            async def create_swarm(self, feature, manifest_path, auto_merge):
                return "mock1"

            async def register_worker(self, swarm_id, packet_id, packet_name, tasks_total, worktree):
                return {}

            async def report_progress(self, swarm_id, packet_id, task_id, task_name, status, tasks_completed, tasks_total, commit=None):
                return {}

            async def report_complete(self, swarm_id, packet_id, final_commit, tests_passed, review_passed):
                return {}

            async def report_error(self, swarm_id, packet_id, task_id, error_type, message, recoverable):
                return {}

            async def get_status(self, swarm_id):
                return {}

            async def subscribe_events(self, swarm_id):
                yield {"event": "test1"}

        class MockBackend2(CoordinationBackend):
            async def create_swarm(self, feature, manifest_path, auto_merge):
                return "mock2"

            async def register_worker(self, swarm_id, packet_id, packet_name, tasks_total, worktree):
                return {}

            async def report_progress(self, swarm_id, packet_id, task_id, task_name, status, tasks_completed, tasks_total, commit=None):
                return {}

            async def report_complete(self, swarm_id, packet_id, final_commit, tests_passed, review_passed):
                return {}

            async def report_error(self, swarm_id, packet_id, task_id, error_type, message, recoverable):
                return {}

            async def get_status(self, swarm_id):
                return {}

            async def subscribe_events(self, swarm_id):
                yield {"event": "test2"}

        BACKENDS.clear()
        register_backend("test", MockBackend1)
        register_backend("test", MockBackend2)

        assert BACKENDS["test"] is MockBackend2


class TestGetBackendFactory:
    """Test get_backend factory function."""

    def test_get_backend_returns_backend_instance(self):
        """get_backend should return an instance of registered backend."""
        class MockBackend(CoordinationBackend):
            def __init__(self, config):
                self.config = config

            async def create_swarm(self, feature, manifest_path, auto_merge):
                return "mock-swarm-id"

            async def register_worker(self, swarm_id, packet_id, packet_name, tasks_total, worktree):
                return {}

            async def report_progress(self, swarm_id, packet_id, task_id, task_name, status, tasks_completed, tasks_total, commit=None):
                return {}

            async def report_complete(self, swarm_id, packet_id, final_commit, tests_passed, review_passed):
                return {}

            async def report_error(self, swarm_id, packet_id, task_id, error_type, message, recoverable):
                return {}

            async def get_status(self, swarm_id):
                return {}

            async def subscribe_events(self, swarm_id):
                yield {"event": "test"}

        BACKENDS.clear()
        register_backend("test", MockBackend)

        config = {"backend": "test", "host": "localhost"}
        backend = get_backend(config)

        assert isinstance(backend, MockBackend)
        assert backend.config == config

    def test_get_backend_raises_on_unknown_backend(self):
        """get_backend should raise ValueError for unknown backend type."""
        BACKENDS.clear()

        config = {"backend": "nonexistent"}

        with pytest.raises(ValueError) as exc_info:
            get_backend(config)

        assert "unknown backend" in str(exc_info.value).lower()
        assert "nonexistent" in str(exc_info.value)

    def test_get_backend_raises_on_missing_backend_key(self):
        """get_backend should raise ValueError if config missing 'backend' key."""
        config = {"host": "localhost"}

        with pytest.raises(ValueError) as exc_info:
            get_backend(config)

        assert "backend" in str(exc_info.value).lower()
