# -*- coding: utf-8 -*-
# Copyright: CloudChef
# SPDX-License-Identifier: Apache-2.0
"""Read or wait for tasks."""

DOCUMENTATION = r'''
module: task_info
short_description: Read or wait for a task
description:
- Read or wait for a task using the caller's SmartCMP permissions.
version_added: 0.1.0
author:
- CloudChef (@cc-fangli)
extends_documentation_fragment:
- cloudchef.smartcmp.auth
requirements:
- Python >= 3.14
- Matching smartcmp-provider package
options:
  task_id:
    description:
    - Internal CMP task ID.
    type: str
    required: true
'''

EXAMPLES = r'''
- name: Read or wait for a task
  cloudchef.smartcmp.task_info:
    base_url: "{{ cmp_base_url }}"
    auth_type: credential
    username: "{{ cmp_username }}"
    password: "{{ cmp_password }}"
    task_id: "{{ cmp_task_id }}"
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

from ansible_collections.cloudchef.smartcmp.plugins.module_utils.smartcmp import run_module

SPEC = dict(task_id=dict(type="str", required=True))


async def execute(session, client):
    """Read or wait for tasks without advancing subsequent write stages such as deletion."""
    from smartcmp_provider.operations.tasks import get_task
    async def read():
        return [await get_task(client, session.params["task_id"])]
    await session.poll(read, "tasks")


def main():
    """Run the Ansible module."""
    run_module(SPEC, execute)


if __name__ == "__main__":
    main()
