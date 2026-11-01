"""Guard against duplicate power writes and deletion scope expansion."""
import asyncio
from types import SimpleNamespace

import pytest

from ansible_collections.cloudchef.smartcmp.plugins.module_utils.smartcmp import Session, ModuleFailure
from ansible_collections.cloudchef.smartcmp.plugins.modules import vm_power, deployment


def context(**values):
    """Create a module context with the shared wait policy."""
    return Session(SimpleNamespace(check_mode=False, params=dict(wait=True, wait_timeout=10, poll_interval=1, **values)))


def test_power_at_target_does_not_write(monkeypatch):
    from smartcmp_provider.operations import resources
    async def detail(*args):
        return SimpleNamespace(payload={"id": "r", "status": "started"})
    monkeypatch.setattr(resources, "get_resource_detail", detail)
    state = context(resource_id="r", state="started")
    asyncio.run(vm_power.execute(state, None))
    assert state.result["changed"] is False
    assert state.result["completed"] is True


def test_power_completion_after_delayed_resource_refresh(monkeypatch):
    from smartcmp_provider.operations import resources, resource_actions, tasks
    states = iter(["stopped", "starting", "started"])
    async def detail(*args):
        return SimpleNamespace(payload={"id": "r", "status": next(states)})
    async def submit(*args):
        return SimpleNamespace(targets=[SimpleNamespace(task_ids=["t"])],
            model_dump=lambda **kwargs: {"targets": [{"task_ids": ["t"], "outcome": "submitted"}]})
    async def task(*args):
        return dict(task_id="t", completed=True, succeeded=True, outcome="succeeded")
    async def pause():
        pass
    monkeypatch.setattr(resources, "get_resource_detail", detail)
    monkeypatch.setattr(resource_actions, "submit_resource_operation", submit)
    monkeypatch.setattr(tasks, "get_task", task)
    state = context(resource_id="r", state="started")
    state.pause = pause
    asyncio.run(vm_power.execute(state, None))
    assert state.result["changed"] is True
    assert state.result["completed"] is True
    assert state.result["outcome"] == "succeeded"


@pytest.mark.parametrize("proven", [True, False])
def test_deleted_tombstone_requires_proof(monkeypatch, proven):
    from smartcmp_provider.operations import deployments
    async def read(*args):
        return dict(resource_ids=["r"], permanently_deleted=proven, deleted=True)
    monkeypatch.setattr(deployments, "get_deployment", read)
    state = context(deployment_id="d", state="absent")
    if proven:
        asyncio.run(deployment.execute(state, None))
        assert state.result["completed"] is True
    else:
        with pytest.raises(ModuleFailure):
            asyncio.run(deployment.execute(state, None))
    assert state.result["changed"] is False


@pytest.mark.parametrize("scope_changed", [False, True])
def test_deletion_phases_keep_original_scope(monkeypatch, scope_changed):
    from smartcmp_provider.operations import deployments, resource_actions, recycle_bin, tasks
    writes = []
    snapshots = iter([
        dict(resource_ids=["r"], permanently_deleted=False, deleted=False, recycled=False, tasks=[], last_task_id=""),
        dict(resource_ids=["r", "unexpected"] if scope_changed else ["r"], permanently_deleted=False,
             deleted=False, recycled=True, tasks=[], last_task_id=""),
        dict(resource_ids=["r"], permanently_deleted=True, deleted=True, recycled=True, tasks=[], last_task_id=""),
    ])
    async def facts(*args):
        return next(snapshots)
    async def actions(*args):
        return [dict(id="Tear Down", name="TEAR_DOWN_APP", enabled=True, webOperation=False)]
    def receipt():
        return SimpleNamespace(targets=[SimpleNamespace(task_ids=["t"])],
            model_dump=lambda **kwargs: {"targets": [{"task_ids": ["t"], "outcome": "submitted"}]})
    async def teardown(*args):
        writes.append("teardown")
        return receipt()
    async def recycled(*args):
        return SimpleNamespace(items=[dict(resource_id="r")])
    async def permanent(client, request):
        assert request.expected_resource_ids == ("r",)
        writes.append("permanent")
        return receipt()
    async def task(*args):
        return dict(task_id="t", completed=True, succeeded=True, outcome="succeeded")
    monkeypatch.setattr(deployments, "get_deployment", facts)
    monkeypatch.setattr(resource_actions, "list_resource_actions", actions)
    monkeypatch.setattr(resource_actions, "submit_resource_operation", teardown)
    monkeypatch.setattr(recycle_bin, "list_recycled_resources", recycled)
    monkeypatch.setattr(recycle_bin, "submit_permanent_removal", permanent)
    monkeypatch.setattr(tasks, "get_task", task)
    state = context(deployment_id="d", state="absent")
    if scope_changed:
        with pytest.raises(ModuleFailure, match="resource scope changed"):
            asyncio.run(deployment.execute(state, None))
        assert writes == ["teardown"]
        assert state.result["completed"] is False
    else:
        asyncio.run(deployment.execute(state, None))
        assert writes == ["teardown", "permanent"]
        assert state.result["completed"] is True
    assert state.result["changed"] is True
