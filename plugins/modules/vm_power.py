# -*- coding: utf-8 -*-
# Copyright: CloudChef
# SPDX-License-Identifier: Apache-2.0
"""Converge virtual machine power state."""

DOCUMENTATION = r'''
module: vm_power
short_description: Converge virtual machine power state
description:
- Converge virtual machine power state using the caller's SmartCMP permissions.
version_added: 0.1.0
author:
- CloudChef (@cc-fangli)
extends_documentation_fragment:
- cloudchef.smartcmp.auth
requirements:
- Python >= 3.14
- Matching smartcmp-provider package
options:
  wait:
    description:
    - Whether to wait for the operation to reach a terminal state.
    type: bool
    default: true
  resource_id:
    description:
    - Exact resource ID.
    type: str
    required: true
  state:
    description:
    - Target state.
    type: str
    required: true
    choices:
    - started
    - stopped
'''

EXAMPLES = r'''
- name: Converge virtual machine power state
  cloudchef.smartcmp.vm_power:
    base_url: "{{ cmp_base_url }}"
    auth_type: credential
    username: "{{ cmp_username }}"
    password: "{{ cmp_password }}"
    resource_id: "{{ cmp_resource_id }}"
    state: "{{ cmp_state }}"
'''

RETURN = r'''
submitted:
  description: Whether this invocation received a submission receipt.
  returned: always
  type: bool
completed:
  description: Whether the associated operation has finished; this does not imply success.
  returned: always
  type: bool
outcome:
  description: Operation outcome, including unknown and failed states.
  returned: always
  type: str
'''

from ansible_collections.cloudchef.smartcmp.plugins.module_utils.smartcmp import run_module, ModuleFailure

SPEC = dict(resource_id=dict(type="str", required=True), state=dict(type="str", required=True, choices=["started", "stopped"]))


async def execute(session, client):
    """Converge from CMP power state and reject transitional states to prevent duplicate submissions."""
    from smartcmp_provider.models.resources import ResourceDetailQuery
    from smartcmp_provider.models.operations import ResourceActionTarget, ResourceOperationInput
    from smartcmp_provider.operations.resources import get_resource_detail
    from smartcmp_provider.operations.resource_actions import submit_resource_operation
    from smartcmp_provider.operations.tasks import get_task
    p = session.params
    query = ResourceDetailQuery(resource_id=p["resource_id"])
    detail = (await get_resource_detail(client, query)).payload
    state = str(detail.get("status") or "").lower()
    session.result.update(resource_id=p["resource_id"], current_state=state, desired_state=p["state"])
    if state == p["state"]:
        session.result.update(completed=True, outcome="succeeded")
        return
    if state not in {"started", "stopped"}:
        raise ModuleFailure("The resource state is transitional or unknown. No duplicate power operation was submitted.")
    if session.check_mode:
        session.result.update(changed=True, outcome="predicted")
        return
    receipt = await submit_resource_operation(client, ResourceOperationInput(
        targets=(ResourceActionTarget(category="virtual-machines", resource_id=p["resource_id"]),),
        operation_id="start" if p["state"] == "started" else "stop"))
    session.submitted(receipt)
    if p["wait"]:
        async def read():
            return [await get_task(client, value) for row in receipt.targets for value in row.task_ids]
        await session.poll(read, "tasks")
        session.result.update(completed=False, outcome="running")
        while True:
            detail = (await get_resource_detail(client, query)).payload
            state = str(detail.get("status") or "").lower()
            session.result["current_state"] = state
            if state == p["state"]:
                session.result.update(completed=True, outcome="succeeded")
                return
            session.result.update(completed=False, outcome="running")
            await session.pause()


def main():
    """Run the Ansible module."""
    run_module(SPEC, execute, mutating=True)


if __name__ == "__main__":
    main()
