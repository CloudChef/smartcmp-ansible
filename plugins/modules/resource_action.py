# -*- coding: utf-8 -*-
# Copyright: CloudChef
# SPDX-License-Identifier: Apache-2.0
"""Execute an explicitly selected resource action."""

DOCUMENTATION = r'''
module: resource_action
short_description: Execute an explicit resource action
description:
- Execute an explicit resource action using the caller's SmartCMP permissions.
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
  category:
    description:
    - Platform resource category; defaults to virtual-machines for an individual resource.
    type: str
    default: virtual-machines
  deployment_id:
    description:
    - Exact deployment ID; deletion affects all resources in that deployment.
    type: str
  operation_id:
    description:
    - Explicit operation ID returned by resource_action_info.
    type: str
    required: true
  parameters:
    description:
    - API parameter dictionary for the operation; prerequisite actions are not inferred.
    type: dict
'''

EXAMPLES = r'''
- name: Execute an explicit resource action
  cloudchef.smartcmp.resource_action:
    base_url: "{{ cmp_base_url }}"
    auth_type: credential
    username: "{{ cmp_username }}"
    password: "{{ cmp_password }}"
    resource_id: "{{ cmp_resource_id }}"
    operation_id: "{{ cmp_operation_id }}"
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

SPEC = dict(resource_id=dict(type="str"), category=dict(type="str", default="virtual-machines"), deployment_id=dict(type="str"),
            operation_id=dict(type="str", required=True), parameters=dict(type="dict", no_log=True))


async def execute(session, client):
    """Execute the selected action; event actions such as reboot report changed on every submission."""
    from smartcmp_provider.models.operations import ResourceActionTarget, ResourceOperationInput
    from smartcmp_provider.operations.resource_actions import list_resource_actions, submit_resource_operation
    from smartcmp_provider.operations.tasks import get_task
    p = session.params
    target = ResourceActionTarget(category="deployments" if p["deployment_id"] else p["category"], resource_id=p["deployment_id"] or p["resource_id"])
    if session.check_mode:
        actions = await list_resource_actions(client, target)
        selected = next((item for item in actions if item.get("id") == p["operation_id"]), None)
        if not selected or not selected.get("enabled") or selected.get("webOperation"):
            raise ModuleFailure("The current identity or target state does not allow this action.")
        if p["operation_id"] in {"permanently_delete_deployment", "delete_metadata_in_resource"}:
            raise ModuleFailure("Use the deployment module for deletion.")
        session.result.update(changed=True, outcome="predicted")
        return
    receipt = await submit_resource_operation(client, ResourceOperationInput(targets=(target,), operation_id=p["operation_id"], parameters=p["parameters"]))
    session.submitted(receipt)
    if p["wait"]:
        task_ids = [task_id for item in receipt.targets for task_id in item.task_ids]
        async def read():
            return [await get_task(client, task_id) for task_id in task_ids]
        await session.poll(read, "tasks")


def main():
    """Run the Ansible module."""
    run_module(SPEC, execute, mutating=True, mutually_exclusive=[("resource_id", "deployment_id")], required_one_of=[("resource_id", "deployment_id")])


if __name__ == "__main__":
    main()
