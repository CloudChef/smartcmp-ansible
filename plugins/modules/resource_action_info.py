# -*- coding: utf-8 -*-
# Copyright: CloudChef
# SPDX-License-Identifier: Apache-2.0
"""Read available resource actions."""

DOCUMENTATION = r'''
module: resource_action_info
short_description: Read available resource actions
description:
- Read available resource actions using the caller's SmartCMP permissions.
version_added: 0.1.0
author:
- CloudChef (@cc-fangli)
extends_documentation_fragment:
- cloudchef.smartcmp.auth
requirements:
- Python >= 3.14
- Matching smartcmp-provider package
options:
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
'''

EXAMPLES = r'''
- name: Read available resource actions
  cloudchef.smartcmp.resource_action_info:
    base_url: "{{ cmp_base_url }}"
    auth_type: credential
    username: "{{ cmp_username }}"
    password: "{{ cmp_password }}"
    resource_id: "{{ cmp_resource_id }}"
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

SPEC = dict(resource_id=dict(type="str"), category=dict(type="str", default="virtual-machines"), deployment_id=dict(type="str"))


async def execute(session, client):
    """Read actions available to the caller without applying the Agent display allowlist."""
    from smartcmp_provider.models.operations import ResourceActionTarget
    from smartcmp_provider.operations.resource_actions import list_resource_actions
    from smartcmp_provider.models.requests import redact_request_secrets
    p = session.params
    target = ResourceActionTarget(category="deployments" if p["deployment_id"] else p["category"], resource_id=p["deployment_id"] or p["resource_id"])
    session.result.update(actions=redact_request_secrets(await list_resource_actions(client, target)), completed=True, outcome="succeeded")


def main():
    """Run the Ansible module."""
    run_module(SPEC, execute, mutually_exclusive=[("resource_id", "deployment_id")], required_one_of=[("resource_id", "deployment_id")])


if __name__ == "__main__":
    main()
