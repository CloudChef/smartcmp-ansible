# -*- coding: utf-8 -*-
# Copyright: CloudChef
# SPDX-License-Identifier: Apache-2.0
"""Read catalog configuration options."""

DOCUMENTATION = r'''
module: reference_info
short_description: Query catalog configuration options
description:
- Query catalog configuration options using the caller's SmartCMP permissions.
version_added: 0.1.0
author:
- CloudChef (@cc-fangli)
extends_documentation_fragment:
- cloudchef.smartcmp.auth
requirements:
- Python >= 3.14
- Matching smartcmp-provider package
options:
  kind:
    description:
    - The type of configuration options to query.
    type: str
    required: true
    choices:
    - business_groups
    - resource_pools
    - profiles
    - logical_templates
    - physical_templates
  context:
    description:
    - Explicit context for the Provider query model; see README. URLs are not accepted.
    type: dict
    required: true
'''

EXAMPLES = r'''
- name: Query catalog configuration options
  cloudchef.smartcmp.reference_info:
    base_url: "{{ cmp_base_url }}"
    auth_type: credential
    username: "{{ cmp_username }}"
    password: "{{ cmp_password }}"
    kind: "{{ cmp_kind }}"
    context: "{{ cmp_context }}"
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

SPEC = dict(kind=dict(type="str", required=True, choices=["business_groups", "resource_pools", "profiles", "logical_templates", "physical_templates"]),
            context=dict(type="dict", required=True))


async def execute(session, client):
    """Reuse Provider option queries with the context required by each option kind."""
    from smartcmp_provider.models.catalogs import BusinessGroupQuery, ResourceBundleQuery, FlavorQuery, LogicalTemplateQuery, PhysicalTemplateQuery
    from smartcmp_provider.operations.catalogs import list_available_business_groups, list_request_resource_pools, list_flavors, list_logical_templates, list_physical_templates
    from smartcmp_provider.models.requests import redact_request_secrets
    from ansible_collections.cloudchef.smartcmp.plugins.module_utils.smartcmp import ModuleFailure
    operations = {
        "business_groups": (BusinessGroupQuery, list_available_business_groups),
        "resource_pools": (ResourceBundleQuery, list_request_resource_pools),
        "profiles": (FlavorQuery, list_flavors),
        "logical_templates": (LogicalTemplateQuery, list_logical_templates),
        "physical_templates": (PhysicalTemplateQuery, list_physical_templates),
    }
    model, read = operations[session.params["kind"]]
    context = session.params["context"]
    if set(context) - model.model_fields.keys():
        raise ModuleFailure("context contains fields unsupported by the selected kind.")
    result = await read(client, model(**context))
    session.result.update(redact_request_secrets(result.model_dump(mode="json")), completed=True, outcome="succeeded")


def main():
    """Run the Ansible module."""
    run_module(SPEC, execute)


if __name__ == "__main__":
    main()
