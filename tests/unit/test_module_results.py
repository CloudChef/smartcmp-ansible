"""Cover failures after writes, read-only failure queries, and check mode semantics."""
import asyncio
from types import SimpleNamespace

import pytest

from ansible_collections.cloudchef.smartcmp.plugins.module_utils.smartcmp import Session, ModuleFailure, protect_result_values
from ansible_collections.cloudchef.smartcmp.plugins.modules import catalog_request


def session(wait=True, check=False):
    """Build a minimal test context without reading Ansible process input."""
    return Session(SimpleNamespace(check_mode=check, params=dict(wait=wait, wait_timeout=1, poll_interval=1)))


@pytest.mark.parametrize("wait,changed,raises", [(True, True, True), (False, False, False)])
def test_business_failure_retains_write_fact(wait, changed, raises):
    context = session(wait)
    context.result.update(changed=changed, submitted=changed, requests=[{"request_id": "r"}])
    async def read():
        return [dict(task_id="t", completed=True, succeeded=False, outcome="failed")]
    if raises:
        with pytest.raises(ModuleFailure):
            asyncio.run(context.poll(read, "tasks"))
    else:
        asyncio.run(context.poll(read, "tasks"))
    assert context.result["changed"] == changed
    assert context.result["requests"][0]["request_id"] == "r"
    assert context.result["outcome"] == "failed"


def test_timeout_keeps_receipt_and_changed():
    context = session()
    context.result.update(changed=True, submitted=True, requests=[{"request_id": "r"}])
    context.deadline = 0
    async def read():
        return [dict(task_id="t", completed=False, succeeded=False, outcome="running")]
    with pytest.raises(ModuleFailure):
        asyncio.run(context.poll(read, "tasks"))
    assert context.result["changed"] is True
    assert context.result["completed"] is False
    assert context.result["requests"] == [{"request_id": "r"}]


def test_catalog_check_mode_never_submits(monkeypatch):
    from smartcmp_provider.operations import catalogs
    context = session(check=True)
    context.params.update({key: None for key in catalog_request.SPEC})
    context.params.update(catalog_id="c", business_group_id="b", name="n")
    async def detail(*args):
        return SimpleNamespace(metadata={"id": "c"})
    monkeypatch.setattr(catalogs, "get_catalog_detail", detail)
    class ReadOnlyClient:
        async def request_json(self, *args, **kwargs):
            pytest.fail("check mode must not submit")
    asyncio.run(catalog_request.execute(context, ReadOnlyClient()))
    assert context.result["changed"] is True
    assert context.result["submitted"] is False


def test_dynamic_secrets_do_not_mask_recovery_ids():
    from ansible.module_utils.common.parameters import remove_values
    module = SimpleNamespace(params={"password": "login-secret", "resource_specs": [
        {"spec": {"networkParams": {"vlan": "0"}, "credentialPassword": "guest-secret"}}]},
        argument_spec={"password": {"no_log": True}, "resource_specs": {"no_log": True}},
        no_log_values={"0", "login-secret", "guest-secret"})
    invocation = protect_result_values(module)
    result = remove_values({"request_id": "req-001", "error": "password=guest-secret"}, module.no_log_values)
    assert result["request_id"] == "req-001"
    assert "guest-secret" not in result["error"]
    assert "guest-secret" not in str(invocation)
    assert "login-secret" not in str(invocation)
