# -*- coding: utf-8 -*-
# Copyright: CloudChef
# SPDX-License-Identifier: Apache-2.0
"""Read service catalogs."""

DOCUMENTATION = r'''
module: catalog_info
short_description: Read service catalogs
description:
- Read service catalogs using the caller's SmartCMP permissions.
version_added: 0.1.0
author:
- CloudChef (@cc-fangli)
extends_documentation_fragment:
- cloudchef.smartcmp.auth
requirements:
- Python >= 3.14
- Matching smartcmp-provider package
options:
  catalog_id:
    description:
    - Exact service catalog ID.
    type: str
  keyword:
    description:
    - Catalog search keyword.
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
    default: 50
'''

EXAMPLES = r'''
- name: Read service catalogs
  cloudchef.smartcmp.catalog_info:
    base_url: "{{ cmp_base_url }}"
    auth_type: credential
    username: "{{ cmp_username }}"
    password: "{{ cmp_password }}"
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

SPEC = dict(catalog_id=dict(type="str"), keyword=dict(type="str", no_log=False), page=dict(type="int", default=1), size=dict(type="int", default=50))


async def execute(session, client):
    """Read an exact catalog or one page of published catalogs with pagination metadata."""
    from smartcmp_provider.models.catalogs import CatalogDetailQuery, CatalogListQuery
    from smartcmp_provider.operations.catalogs import get_catalog_detail, list_catalogs
    from smartcmp_provider.models.requests import redact_request_secrets
    p = session.params
    if p["catalog_id"]:
        result = await get_catalog_detail(client, CatalogDetailQuery(catalog_id=p["catalog_id"]))
        session.result["catalog"] = redact_request_secrets(result.metadata)
    else:
        result = await list_catalogs(client, CatalogListQuery(keyword=p["keyword"] or "", page=p["page"], size=p["size"]))
        session.result.update(redact_request_secrets(result.model_dump(mode="json")), page=p["page"], size=p["size"])
    session.result.update(completed=True, outcome="succeeded")


def main():
    """Run the Ansible module."""
    run_module(SPEC, execute, mutually_exclusive=[("catalog_id", "keyword")])


if __name__ == "__main__":
    main()
