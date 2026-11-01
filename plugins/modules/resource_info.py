# -*- coding: utf-8 -*-
# Copyright: CloudChef
# SPDX-License-Identifier: Apache-2.0
"""Read cloud resources."""

DOCUMENTATION = r'''
module: resource_info
short_description: Read cloud resources
description:
- Read cloud resources using the caller's SmartCMP permissions.
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
  business_group_id:
    description:
    - Exact business group ID.
    type: str
  resource_pool_id:
    description:
    - Exact resource pool ID.
    type: str
  query_value:
    description:
    - Platform search keyword.
    type: str
  page:
    description:
    - Page number starting at 1.
    type: int
    default: 1
  size:
    description:
    - Number of items per page, up to 100.
    type: int
    default: 20
'''

EXAMPLES = r'''
- name: Read cloud resources
  cloudchef.smartcmp.resource_info:
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

from ansible_collections.cloudchef.smartcmp.plugins.module_utils.smartcmp import run_module, ModuleFailure

SPEC = dict(resource_id=dict(type="str"), category=dict(type="str"), business_group_id=dict(type="str"),
            resource_pool_id=dict(type="str"), query_value=dict(type="str"), page=dict(type="int", default=1), size=dict(type="int", default=20))


async def execute(session, client):
    """Read exact resource IDs or one page using explicit filters."""
    from smartcmp_provider.models.resources import ResourceDetailQuery, ResourceListQuery
    from smartcmp_provider.operations.resources import get_resource_detail, list_resources
    from smartcmp_provider.models.requests import redact_request_secrets
    p = session.params
    if p["resource_id"]:
        result = await get_resource_detail(client, ResourceDetailQuery(resource_id=p["resource_id"], category=p["category"] or "virtual-machines"))
        session.result["resource"] = redact_request_secrets(result.payload)
    else:
        if not any(p[key] for key in ("category", "business_group_id", "resource_pool_id", "query_value")):
            raise ModuleFailure("Resource list queries require explicit filters.")
        result = await list_resources(client, ResourceListQuery(**{key: p[key] for key in SPEC if key != "resource_id" and p[key] is not None}))
        session.result.update(resources=list(result.items), total=result.total, page=p["page"], size=p["size"])
    session.result.update(completed=True, outcome="succeeded")


def main():
    """Run the Ansible module."""
    run_module(SPEC, execute, mutually_exclusive=[("resource_id", key) for key in ("business_group_id", "resource_pool_id", "query_value")])


if __name__ == "__main__":
    main()
