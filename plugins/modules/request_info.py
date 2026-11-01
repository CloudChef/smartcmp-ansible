# -*- coding: utf-8 -*-
# Copyright: CloudChef
# SPDX-License-Identifier: Apache-2.0
"""Read or wait for requests."""

DOCUMENTATION = r'''
module: request_info
short_description: Read or wait for a request
description:
- Read or wait for a request using the caller's SmartCMP permissions.
version_added: 0.1.0
author:
- CloudChef (@cc-fangli)
extends_documentation_fragment:
- cloudchef.smartcmp.auth
requirements:
- Python >= 3.14
- Matching smartcmp-provider package
options:
  request_id:
    description:
    - Internal CMP request ID.
    type: str
  request_number:
    description:
    - User-visible request number; mutually exclusive with request_id.
    type: str
  include_outputs:
    description:
    - Whether to read deployment and resource outputs associated with the request.
    type: bool
    default: true
'''

EXAMPLES = r'''
- name: Read or wait for a request
  cloudchef.smartcmp.request_info:
    base_url: "{{ cmp_base_url }}"
    auth_type: credential
    username: "{{ cmp_username }}"
    password: "{{ cmp_password }}"
    request_id: "{{ cmp_request_id }}"
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

SPEC = dict(request_id=dict(type="str"), request_number=dict(type="str"), include_outputs=dict(type="bool", default=True))


async def execute(session, client):
    """Resume request queries by explicit identifiers without creating requests."""
    from smartcmp_provider.operations.requests import get_request, get_request_outputs
    ref = {key: session.params[key] for key in ("request_id", "request_number") if session.params[key]}
    async def read():
        row = await get_request(client, ref)
        ref.clear()
        ref["request_id"] = row.request_id
        return [row.model_dump(mode="json")]
    rows = await session.poll(read, "requests")
    if session.params["include_outputs"]:
        session.result["request_outputs"] = (await get_request_outputs(client, [rows[0]["request_id"]])).model_dump(mode="json")["requests"]


def main():
    """Run the Ansible module."""
    run_module(SPEC, execute, mutually_exclusive=[("request_id", "request_number")], required_one_of=[("request_id", "request_number")])


if __name__ == "__main__":
    main()
