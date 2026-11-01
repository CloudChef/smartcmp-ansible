# -*- coding: utf-8 -*-
# Copyright: CloudChef
# SPDX-License-Identifier: Apache-2.0
"""Submit a fixed service catalog request."""

DOCUMENTATION = r'''
module: catalog_request
short_description: Submit a fixed service catalog request
description:
- Submit a fixed service catalog request using the caller's SmartCMP permissions.
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
  catalog_id:
    description:
    - Exact service catalog ID.
    type: str
  business_group_id:
    description:
    - Exact business group ID.
    type: str
  name:
    description:
    - Request name; it is not used to deduplicate submissions.
    type: str
  project_id:
    description:
    - Exact project ID.
    type: str
  description:
    description:
    - Request description.
    type: str
  count:
    description:
    - Number of requests with the same configuration; when omitted, use request_body.count if present, otherwise 1.
    type: int
  params:
    description:
    - Catalog workflow parameters, preserving platform field names and types.
    type: dict
  resource_specs:
    description:
    - Node configurations containing node, type, resource_pool_id and spec; mutually exclusive with request_body.resourceSpecs.
    type: list
    elements: dict
  request_body:
    description:
    - Additional standard request fields; explicit module parameters take precedence and the requester is bound to the current credentials.
    type: dict
'''

EXAMPLES = r'''
- name: Submit a fixed service catalog request
  cloudchef.smartcmp.catalog_request:
    base_url: "{{ cmp_base_url }}"
    auth_type: credential
    username: "{{ cmp_username }}"
    password: "{{ cmp_password }}"
    catalog_id: "{{ cmp_catalog_id }}"
    business_group_id: "{{ cmp_business_group_id }}"
    name: "{{ cmp_request_name }}"
    resource_specs: "{{ cmp_resource_specs }}"
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

SPEC = {key: dict(type="str") for key in ("catalog_id", "business_group_id", "name", "project_id", "description")}
SPEC.update(count=dict(type="int"), params=dict(type="dict", no_log=True),
            resource_specs=dict(type="list", elements="dict", no_log=True), request_body=dict(type="dict", no_log=True))


async def execute(session, client):
    """Submit fixed configuration once; check mode performs reads and structural validation only."""
    from smartcmp_provider.models.requests import CatalogRequestSpec
    from smartcmp_provider.operations.requests import build_catalog_request_payload, submit_catalog_request, get_request, get_request_outputs
    spec = CatalogRequestSpec(**{key: session.params[key] for key in SPEC if session.params[key] is not None})
    body = build_catalog_request_payload(spec)
    if session.check_mode:
        from smartcmp_provider.models.catalogs import CatalogDetailQuery
        from smartcmp_provider.operations.catalogs import get_catalog_detail
        await get_catalog_detail(client, CatalogDetailQuery(catalog_id=body["catalogId"]))
        session.result.update(changed=True, submitted=False, completed=False, outcome="predicted")
        return
    receipt = await submit_catalog_request(client, spec)
    session.submitted(receipt)
    if not session.params["wait"]:
        return
    ids = [item.request_id for item in receipt.requests]

    async def read():
        return [(await get_request(client, {"request_id": value})).model_dump(mode="json") for value in ids]
    await session.poll(read, "requests")
    outputs = (await get_request_outputs(client, ids)).model_dump(mode="json")["requests"]
    session.result["request_outputs"] = outputs
    session.result["deployment_ids"] = list(dict.fromkeys(d for row in outputs for d in row["deployment_ids"]))
    session.result["resources"] = [r for row in outputs for r in row["resources"]]
    if body.get("resourceSpecs") and any(not row["deployment_ids"] or not row["resources"] for row in outputs):
        session.result.update(completed=False, outcome="unknown")
        raise ModuleFailure("The request has finished without complete deployment and resource outputs; provisioning success cannot be confirmed.")


def main():
    """Run the Ansible module."""
    run_module(SPEC, execute, mutating=True)


if __name__ == "__main__":
    main()
