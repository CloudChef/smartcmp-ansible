# -*- coding: utf-8 -*-
# Copyright: CloudChef
# SPDX-License-Identifier: Apache-2.0
"""Reuse Provider authentication and transport; adapt Ansible results and bounded waits."""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

from ansible.module_utils.basic import AnsibleModule


def argument_spec(mutating=False):
    """Define shared options with mutually exclusive credentials and TLS verification enabled."""
    return dict(
        base_url=dict(type="str", required=True),
        auth_type=dict(type="str", required=True, choices=["user_token", "provider_token", "cookie", "credential"]),
        token=dict(type="str", no_log=True), cookie=dict(type="str", no_log=True),
        username=dict(type="str"), password=dict(type="str", no_log=True),
        validate_certs=dict(type="bool", default=True), ca_path=dict(type="path"),
        timeout=dict(type="int", default=60), wait=dict(type="bool", default=mutating),
        wait_timeout=dict(type="int", default=1800), poll_interval=dict(type="int", default=10),
    )


class ModuleFailure(Exception):
    """Represent a known failure while Session retains submitted receipts."""


def protect_result_values(module):
    """Hide dynamic inputs but redact only actual secrets from results so VLAN 0 cannot mask recovery IDs."""
    from smartcmp_provider.models.requests import redact_request_secrets
    secrets = set()

    def collect(raw, redacted, sensitive=False):
        sensitive = sensitive or redacted == "***"
        if isinstance(raw, dict):
            for key, value in raw.items():
                collect(value, redacted.get(key) if isinstance(redacted, dict) else None, sensitive)
        elif isinstance(raw, (list, tuple)):
            for index, value in enumerate(raw):
                collect(value, redacted[index] if isinstance(redacted, (list, tuple)) else None, sensitive)
        elif sensitive and raw is not None and str(raw):
            secrets.add(str(raw))

    collect(module.params, redact_request_secrets(module.params))
    module.no_log_values.clear()
    module.no_log_values.update(secrets)
    return {"module_args": {key: "VALUE_SPECIFIED_IN_NO_LOG_PARAMETER"
            if module.argument_spec.get(key, {}).get("no_log") else value
            for key, value in module.params.items()}}


class Session:
    """Keep one invocation deadline and result without persisting credentials or cross-task state."""

    def __init__(self, module):
        """Bind Ansible options and initialize a result with no submitted writes."""
        self.module = module
        self.params = module.params
        self.check_mode = module.check_mode
        self.deadline = time.monotonic() + self.params["wait_timeout"]
        self.result = dict(changed=False, submitted=False, completed=False, outcome="unknown")

    def submitted(self, receipt):
        """Retain all receipts before waiting; never replay partial failures or unknown writes."""
        self.result.update(changed=True, submitted=True, completed=False)
        data = receipt.model_dump(mode="json")
        self.result.update(data)
        rows = data.get("targets", [])
        outcomes = {item["outcome"] for item in rows}
        if "unknown" in outcomes or data.get("outcome") == "unknown":
            self.result["outcome"] = "unknown"
            raise ModuleFailure("The submission receipt is incomplete and the outcome is unknown. Inspect known IDs; do not automatically resubmit.")
        if "failed" in outcomes:
            self.result["outcome"] = "failed"
            raise ModuleFailure("Submission failed for some targets. Inspect each target receipt; do not resubmit the entire operation.")
        self.result["outcome"] = "submitted"

    async def poll(self, read, key):
        """Read all related objects under one deadline and preserve writes when waiting fails."""
        while True:
            rows = await read()
            self.result[key] = rows
            completed = bool(rows) and all(row["completed"] for row in rows)
            succeeded = bool(rows) and all(row["succeeded"] for row in rows)
            failed = any(row["outcome"] == "failed" for row in rows)
            self.result.update(completed=completed, outcome="succeeded" if succeeded else "failed" if failed else "running")
            if not self.params["wait"]:
                return rows
            if failed:
                raise ModuleFailure("An associated operation failed. All known IDs and states have been retained.")
            if completed:
                return rows
            await self.pause()

    async def pause(self):
        """Wait for the next read without cancelling or retrying writes on timeout."""
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.result["completed"] = False
            raise ModuleFailure("Waiting timed out. Resume queries using the known request or task IDs.")
        await asyncio.sleep(min(self.params["poll_interval"], remaining))


def run_module(spec, handler, *, mutating=False, **module_options):
    """Run one handler, close the client, and convert known errors to redacted Ansible results."""
    module = AnsibleModule(argument_spec={**argument_spec(mutating), **spec}, supports_check_mode=True, **module_options)
    session = Session(module)
    try:
        from pydantic import ValidationError
        from smartcmp_provider.auth.login import login_with_password, resolve_auth_url
        from smartcmp_provider.auth.models import SmartCmpAuthenticationContext
        from smartcmp_provider.auth.resolver import resolve_integration_request
        from smartcmp_provider.instance import SmartCmpInstance, TlsSettings
        from smartcmp_provider.transport.client import SmartCmpClient
        from smartcmp_provider.errors import SmartCmpError, SmartCmpUnknownOutcomeError
    except ImportError:
        module.fail_json(msg="The module interpreter is missing the required smartcmp-provider version or dependencies. Install the matching wheel.", **session.result)
    p = module.params
    try:
        session.result["invocation"] = protect_result_values(module)
        if min(p["timeout"], p["wait_timeout"], p["poll_interval"]) <= 0:
            raise ModuleFailure("timeout, wait_timeout and poll_interval must be positive integers.")
        fields = {key for key in ("token", "cookie", "username", "password") if p.get(key) is not None}
        expected = {"username", "password"} if p["auth_type"] == "credential" else {"cookie"} if p["auth_type"] == "cookie" else {"token"}
        if fields != expected or any(not p[key] for key in expected):
            raise ModuleFailure("Credential parameters must match auth_type and must not be mixed.")
        credential = p.get("cookie") or p.get("token")
        auth_type = p["auth_type"]
        if auth_type == "credential":
            credential = login_with_password(resolve_auth_url(p["base_url"]), p["username"], p["password"],
                timeout_seconds=p["timeout"], tls_verify=(p["ca_path"] or True) if p["validate_certs"] else False)
            auth_type = "cookie"
        request = resolve_integration_request(
            instance=SmartCmpInstance(name="ansible", base_url=p["base_url"], timeout_seconds=p["timeout"],
                tls=TlsSettings(verify=p["validate_certs"], ca_bundle=p["ca_path"])),
            authentication=SmartCmpAuthenticationContext.provided(subject=p.get("username") or "ansible",
                actor_type="user", auth_type=auth_type, credential_value=credential), trace_id=uuid4().hex)

        async def execute():
            async with SmartCmpClient(request) as client:
                await handler(session, client)
        asyncio.run(execute())
    except SmartCmpUnknownOutcomeError as exc:
        session.result.update(changed=True, completed=False, outcome="unknown", trace_id=exc.trace_id)
        module.fail_json(msg="The write outcome is unknown. Do not automatically resubmit; inspect platform operation records.", **session.result)
    except SmartCmpError as exc:
        session.result.update(error_type=type(exc).__name__, trace_id=exc.trace_id, http_status=exc.http_status)
        module.fail_json(msg="The SmartCMP operation failed. Inspect platform logs using the related IDs and error type.", **session.result)
    except ValidationError as exc:
        module.fail_json(msg="Parameter validation failed.", errors=[{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()], **session.result)
    except ModuleFailure as exc:
        module.fail_json(msg=str(exc), **session.result)
    module.exit_json(**session.result)
