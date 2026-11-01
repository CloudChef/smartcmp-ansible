# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
"""Authentication and wait options shared by all modules."""


class ModuleDocFragment:
    """Shared Ansible documentation fragment."""

    DOCUMENTATION = r'''
options:
  base_url:
    description:
    - SmartCMP instance URL.
    type: str
    required: true
  auth_type:
    description:
    - Explicit credential type.
    type: str
    required: true
    choices:
    - user_token
    - provider_token
    - cookie
    - credential
  token:
    description:
    - Raw token for user_token or provider_token; omit the Bearer prefix.
    type: str
  cookie:
    description:
    - Complete session credential for cookie authentication.
    type: str
  username:
    description:
    - Username for credential authentication.
    type: str
  password:
    description:
    - Plain password or 32-character MD5 digest for credential authentication; supply through Ansible Vault.
    type: str
  validate_certs:
    description:
    - Whether to verify TLS certificates; explicitly disable only for untrusted development certificates.
    type: bool
    default: true
  ca_path:
    description:
    - Optional trusted CA file used for both login and API requests.
    type: path
  timeout:
    description:
    - Timeout in seconds for one HTTP request.
    type: int
    default: 60
  wait:
    description:
    - Whether to wait for a terminal state; defaults to true for mutating modules and false for query modules.
    type: bool
    default: false
  wait_timeout:
    description:
    - Maximum wait in seconds shared by the entire invocation.
    type: int
    default: 1800
  poll_interval:
    description:
    - Status polling interval in seconds.
    type: int
    default: 10
'''
