import pytest

from src.adapters.langfuse_tracker import LangfuseTracker


class _FakeStep:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.ended = False

    def end(self) -> None:
        self.ended = True


class _FakeRoot(_FakeStep):
    def __init__(self, fail_step: bool = False, fail_end: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.children: list[_FakeStep] = []
        self.fail_step = fail_step
        self.fail_end = fail_end

    def start_observation(self, **kwargs) -> _FakeStep:
        if self.fail_step:
            raise RuntimeError("step unavailable")
        child = _FakeStep(**kwargs)
        self.children.append(child)
        return child

    def end(self) -> None:
        self.ended = True
        if self.fail_end:
            raise RuntimeError("end unavailable")


class _FakeClient:
    def __init__(self) -> None:
        self.roots: list[_FakeRoot] = []
        self.seeds: list[str] = []
        self.start_calls = 0
        self.fail_start = False
        self.fail_step = False
        self.fail_end = False

    def create_trace_id(self, *, seed: str) -> str:
        self.seeds.append(seed)
        return "a" * 32

    def start_observation(self, **kwargs) -> _FakeRoot:
        self.start_calls += 1
        if self.fail_start:
            raise RuntimeError("Langfuse unavailable")
        root = _FakeRoot(
            fail_step=self.fail_step,
            fail_end=self.fail_end,
            **kwargs,
        )
        self.roots.append(root)
        return root


def _tracker(client: _FakeClient) -> LangfuseTracker:
    return LangfuseTracker("pk-lf-test", "sk-lf-test", "https://langfuse.example", client=client)


def test_tracker_creates_root_child_and_finishes_trace():
    client = _FakeClient()
    tracker = _tracker(client)

    tracker.start_trace(
        "trace-1",
        {"service_name": "payment-service", "environment": "production"},
    )
    root = client.roots[0]

    assert client.seeds == ["trace-1"]
    assert root.kwargs["trace_context"] == {"trace_id": "a" * 32}
    assert root.kwargs["name"] == "sentinel.incident"
    assert root.kwargs["metadata"]["trace_id"] == "trace-1"

    tracker.record_step("trace-1", "analysis_node", {"audit": {"is_anomaly": True}})

    assert len(root.children) == 1
    assert root.children[0].kwargs["name"] == "sentinel.node.analysis_node"
    assert root.children[0].kwargs["output"] == {"is_anomaly": True}
    assert root.children[0].ended is True

    tracker.finish_trace("trace-1")

    assert root.ended is True

    tracker.record_step("trace-1", "response_node", {"audit": {}})

    assert len(root.children) == 1


def test_tracker_ignores_unknown_trace():
    tracker = _tracker(_FakeClient())

    tracker.record_step("missing", "analysis_node", {"audit": {}})
    tracker.finish_trace("missing")


def test_tracker_degrades_when_start_fails():
    client = _FakeClient()
    client.fail_start = True
    tracker = _tracker(client)

    tracker.start_trace("trace-1", {"service_name": "payment-service"})
    tracker.start_trace("trace-2", {"service_name": "payment-service"})

    assert client.start_calls == 1
    assert client.roots == []


def test_tracker_degrades_when_step_fails():
    client = _FakeClient()
    client.fail_step = True
    tracker = _tracker(client)
    tracker.start_trace("trace-1", {"service_name": "payment-service"})
    root = client.roots[0]

    tracker.record_step("trace-1", "analysis_node", {"audit": {}})

    assert root.children == []
    assert root.ended is True


def test_tracker_survives_finish_failure():
    client = _FakeClient()
    client.fail_end = True
    tracker = _tracker(client)
    tracker.start_trace("trace-1", {"service_name": "payment-service"})

    tracker.finish_trace("trace-1")

    assert client.roots[0].ended is True


@pytest.mark.parametrize("event", [{"service_name": None}, {}])
def test_tracker_accepts_minimal_event(event):
    client = _FakeClient()
    tracker = _tracker(client)

    tracker.start_trace("trace-1", event)

    assert client.roots[0].kwargs["metadata"]["service_name"] is None
