# -*- coding: utf-8 -*-
# Copyright: CloudChef
# SPDX-License-Identifier: Apache-2.0
"""Permanently delete an explicitly identified deployment."""

DOCUMENTATION = r'''
module: deployment
short_description: Permanently delete an explicit deployment
description:
- Permanently delete an explicit deployment using the caller's SmartCMP permissions.
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
  deployment_id:
    description:
    - Exact deployment ID; deletion affects all resources in that deployment.
    type: str
    required: true
  state:
    description:
    - Target state.
    type: str
    default: absent
    choices:
    - absent
'''

EXAMPLES = r'''
- name: Permanently delete an explicit deployment
  cloudchef.smartcmp.deployment:
    base_url: "{{ cmp_base_url }}"
    auth_type: credential
    username: "{{ cmp_username }}"
    password: "{{ cmp_password }}"
    deployment_id: "{{ cmp_deployment_id }}"
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

SPEC = dict(deployment_id=dict(type="str", required=True), state=dict(type="str", default="absent", choices=["absent"]))


async def execute(session, client):
    """Bind the full deployment scope and advance teardown and permanent deletion under one deadline."""
    from smartcmp_provider.models.operations import ResourceActionTarget, ResourceOperationInput
    from smartcmp_provider.models.resources import PermanentResourceRemovalInput, RecycledResourceQuery
    from smartcmp_provider.operations.deployments import get_deployment
    from smartcmp_provider.operations.recycle_bin import list_recycled_resources, submit_permanent_removal
    from smartcmp_provider.operations.resource_actions import list_resource_actions, submit_resource_operation
    from smartcmp_provider.operations.tasks import get_task
    p = session.params
    target = ResourceActionTarget(category="deployments", resource_id=p["deployment_id"])
    expected_scope = None
    submitted_phases = set()
    session.result.update(deployment_id=p["deployment_id"], stages=[])
    while True:
        facts = await get_deployment(client, p["deployment_id"])
        session.result["deployment"] = facts
        scope = tuple(facts["resource_ids"])
        if expected_scope is None:
            expected_scope = scope
        elif scope != expected_scope:
            raise ModuleFailure("The deployment resource scope changed. Further deletion was stopped; review the complete scope.")
        if facts["permanently_deleted"]:
            session.result.update(completed=True, outcome="succeeded", phase="absent", requires_continuation=False)
            return
        if facts["deleted"]:
            raise ModuleFailure("Only a tombstone is available, without reliable evidence of successful permanent deletion. Deletion was not resubmitted.")
        active = [item for item in facts["tasks"] if item["task_id"] == facts["last_task_id"] and not item["completed"]]
        if active:
            session.result.update(tasks=active, phase="waiting", requires_continuation=True, outcome="running")
            if not p["wait"] or session.check_mode:
                return
            async def read():
                return [await get_task(client, item["task_id"]) for item in active]
            await session.poll(read, "tasks")
            session.result.update(completed=False, outcome="running")
            continue
        phase = "permanent_removal" if facts["recycled"] else "teardown"
        session.result["phase"] = phase
        if phase in submitted_phases:
            await session.pause()
            continue
        if session.check_mode:
            session.result.update(changed=True, outcome="predicted", requires_continuation=True)
            return
        if facts["recycled"]:
            rows = (await list_recycled_resources(client, RecycledResourceQuery(deployment_id=p["deployment_id"]))).items
            recycled_scope = tuple(sorted({row["resource_id"] for row in rows if row.get("resource_id")}))
            if recycled_scope != expected_scope:
                raise ModuleFailure("The complete recycled resource scope differs from the initial deployment. Permanent deletion was not submitted.")
            receipt = await submit_permanent_removal(client, PermanentResourceRemovalInput(
                deployment_id=p["deployment_id"], expected_deployment_id=p["deployment_id"],
                expected_resource_ids=expected_scope, confirmed=True))
        else:
            actions = await list_resource_actions(client, target)
            action = next((item for item in actions if item.get("name") == "TEAR_DOWN_APP" and item.get("enabled") and not item.get("webOperation")), None)
            if action is None:
                raise ModuleFailure("No executable normal teardown action is available for this deployment. The platform workflow was not bypassed.")
            receipt = await submit_resource_operation(client, ResourceOperationInput(targets=(target,), operation_id=action["id"]))
        session.result["stages"].append(dict(phase=phase, receipt=receipt.model_dump(mode="json")))
        session.submitted(receipt)
        submitted_phases.add(phase)
        session.result["requires_continuation"] = True
        if not p["wait"]:
            return
        async def read():
            return [await get_task(client, value) for row in receipt.targets for value in row.task_ids]
        await session.poll(read, "tasks")
        session.result.update(completed=False, outcome="running")


def main():
    """Run the Ansible module."""
    run_module(SPEC, execute, mutating=True)


if __name__ == "__main__":
    main()
