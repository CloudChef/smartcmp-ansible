# cloudchef.smartcmp

An Ansible collection for provisioning and managing resources through existing SmartCMP service catalogs. Modules use the caller's SmartCMP identity and permissions. Requests follow the platform's approval workflow; the collection does not approve requests automatically.

## Requirements and installation

Install the collection and its Python dependencies on the control node or in the execution environment that runs the modules:

- Python 3.14
- ansible-core 2.21
- smartcmp-provider 1.1.0
- Network access to the SmartCMP API and a user with permissions for the requested operations

Install the supplied Provider wheel and collection archive:

```sh
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install 'ansible-core==2.21.5' ./smartcmp_provider-1.1.0-py3-none-any.whl
ansible-galaxy collection install ./cloudchef-smartcmp-0.1.0.tar.gz
ansible-doc cloudchef.smartcmp.catalog_request
```

Run API modules locally and set `ansible_python_interpreter: "{{ ansible_playbook_python }}"` so they use the environment containing the Provider. SSH or WinRM access to provisioned VMs is not required for CMP API operations.

To build distribution packages from source, run `python -m build --wheel` in the SmartCMP-Provider project (with the Python `build` package installed) and `ansible-galaxy collection build` in this repository. Deliver both packages together; the Provider wheel must be installed in the module interpreter, not just the shell used to launch Ansible. Custom execution environments must include both dependencies and the collection.

## Authentication

Select one authentication mode explicitly. Do not combine credentials from different modes.

| `auth_type` | Parameters | Behavior |
| --- | --- | --- |
| `credential` | `username`, `password` | Logs in and uses the returned session for API calls |
| `user_token` | `token` | Uses a SmartCMP user API token; `cmp_tk_` tokens are sent as Bearer credentials |
| `provider_token` | `token` | Uses a provider token as a Bearer credential |
| `cookie` | `cookie` | Uses an existing SmartCMP session credential |

For `credential`, `password` accepts a plain password or its 32-character MD5 digest. The Provider converts plain passwords to MD5 before login and sends an existing digest unchanged. MD5 is the CMP login protocol's password representation; HTTPS protects the connection.

For token authentication, pass the raw token without the `Bearer ` prefix. The Provider adds the appropriate authorization header. Supply secrets through Ansible Vault or runtime variables.

TLS certificate verification is enabled by default. Use `ca_path` for a private CA. Set `validate_certs: false` only when intentionally using an untrusted development certificate.

## Quick start

This playbook reads a catalog using a user token supplied through the `CMP_TOKEN` environment variable:

```yaml
---
- name: Read a SmartCMP catalog
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    ansible_python_interpreter: "{{ ansible_playbook_python }}"
  module_defaults:
    group/cloudchef.smartcmp.smartcmp:
      base_url: "{{ cmp_base_url }}"
      auth_type: user_token
      token: "{{ lookup('ansible.builtin.env', 'CMP_TOKEN') }}"
  tasks:
    - name: Get catalog details
      cloudchef.smartcmp.catalog_info:
        catalog_id: "{{ cmp_catalog_id }}"
      register: catalog
```

For username/password authentication, replace the authentication options with:

```yaml
auth_type: credential
username: "{{ cmp_username }}"
password: "{{ cmp_password }}"
```

Use [provision.yml](examples/provision.yml) to submit a request, [recover.yml](examples/recover.yml) to resume waiting by request ID, and [delete.yml](examples/delete.yml) to remove a deployment. Supply environment-specific IDs and credentials through variables. The examples use username/password authentication; replace their authentication options as shown above to use a token.

Resource configuration examples are available for [Linux](examples/linux-vars.example.yml) and [Windows](examples/windows-vars.example.yml). Match node names, fields, templates, networks and storage to the selected catalog. Examples are not universal defaults.

## Modules

| Module | Purpose |
| --- | --- |
| `catalog_info` | Read an exact catalog or a page of published catalogs |
| `reference_info` | Query business groups, resource pools, compute profiles and templates |
| `catalog_request` | Submit fixed catalog configuration once and retain all request identifiers |
| `request_info` | Read or wait for a request by internal ID or display number |
| `task_info` | Read or wait for a task without advancing subsequent write stages |
| `resource_info` | Read an exact resource or a filtered page of resources |
| `resource_action_info` | Discover available actions, disabled reasons and parameter definitions |
| `resource_action` | Execute an explicit action with parameters |
| `vm_power` | Converge to `started` or `stopped` without resubmitting when already at the target |
| `deployment` | Tear down and permanently delete the complete scope of an explicit deployment |

Use `ansible-doc cloudchef.smartcmp.<module>` for parameter details.

### Reference query context

`reference_info.context` uses the Provider's query fields. It does not accept arbitrary URLs or select targets automatically.

| Kind | Context fields |
| --- | --- |
| `business_groups` | `catalog_id` |
| `resource_pools` | `business_group_id`, `component_type`, `node_type`, `catalog_id`, `node_template_name`; optional filters: `resource_bundle_id`, `cloud_entry_type_id`, `resource_bundle_tags` |
| `profiles` | `resource_bundle_id`, `compute_profile_id`, `catalog_id`, `node_template_name`, `query_value`, `page`, `size` |
| `logical_templates` | `resource_bundle_id`, `catalog_id`, `node_template_name`, `os_type`, `query_value` |
| `physical_templates` | `resource_bundle_id`, `logic_template_id` |

Resource-pool lookup does not depend on Agent instructions or interactive placement fields.

## Provisioning behavior

`catalog_request` creates a new request on every invocation; a matching name does not prevent a duplicate request.

- Explicit `count` takes precedence over `request_body.count`; the default is 1 when neither is supplied.
- `resource_specs` and `request_body.resourceSpecs` are mutually exclusive.
- Each resource specification contains `node`, `type`, `resource_pool_id` and `spec`. The wrapper fields override corresponding fields in `spec`; other CMP field names and types are preserved.
- The requester is bound to the authenticated identity.
- A response can contain multiple requests, deployments and resources. Retain every identifier for recovery.

FusionCompute uses the same modules with existing FC pools, images, networks and storage. Its system disk is cloned from the selected image; provisioning does not expand it according to `systemDisk.size`. Omit that field for FC and use the image's disk size as the expected size. The collection does not add an implicit resize operation.

## Waiting, recovery and check mode

Mutating modules wait by default; query modules do not. Shared timing options are:

| Option | Default | Meaning |
| --- | --- | --- |
| `timeout` | 60 seconds | Timeout for one HTTP request |
| `wait_timeout` | 1800 seconds | Shared wait deadline for one module invocation |
| `poll_interval` | 10 seconds | Interval between status reads |

`submitted` indicates a submission receipt, while `completed` indicates a terminal state, not necessarily success. Inspect `outcome` as well. A `SUBMITTED` platform state does not mean the operation has finished.

If waiting fails after a write, the module fails the Ansible task while preserving known identifiers and `changed=true`. Resume queries with `request_info` or `task_info`. If the write outcome is unknown, inspect platform records before taking further action; do not automatically resubmit.

Check mode reads current state and predicts `changed` without submitting business changes. It does not validate capacity, approvals or every platform parameter. Event actions such as reboot report `changed=true` on each submission.

## Permanent deletion

`deployment` with `state: absent` affects every resource in the specified deployment. It follows normal teardown and then invokes `permanently_delete_deployment`; it does not substitute metadata-only removal.

With `wait: false`, a call advances only the current phase. When `requires_continuation` is true, invoke the same module again with the same deployment ID. Within one invocation, a change from the initial resource snapshot stops further deletion.

A 404 response or a tombstone alone is not proof of permanent deletion. The module requires matching task and final-state evidence; otherwise it fails without repeating deletion.

## License

Licensed under [Apache-2.0](LICENSE).
