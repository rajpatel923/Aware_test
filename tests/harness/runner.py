"""Scenario runner: drives harness clients through a spec/*.json fixture."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client import ClientProcess
    from .server import ServerProcess


class AssertionFailure(AssertionError):
    pass


class ScenarioRunner:
    def __init__(
        self,
        scenario: dict,
        clients: dict[str, "ClientProcess"],
        server: "ServerProcess",
    ) -> None:
        self._scenario = scenario
        self._clients = clients
        self._server = server
        self._bindings: dict[str, Any] = {}

    def run(self) -> None:
        for step in self._scenario["steps"]:
            self._run_step(step)

    def _run_step(self, step: dict) -> None:
        cmd = step["cmd"]
        client_name = step.get("client")

        if cmd == "restart" and client_name:
            self._clients[client_name].restart()
            return

        if cmd == "server_restart":
            self._server.restart()
            for c in self._clients.values():
                c._base_url = self._server.base_url
            return

        assert client_name in self._clients, f"Unknown client: {client_name!r}"
        client = self._clients[client_name]

        args = self._substitute(step.get("args") or {})
        resp = client.command(cmd, args if args else None)

        if "bind" in step and resp.get("ok"):
            self._bind_result(step["bind"], resp.get("result", {}))

        if "expect" in step:
            self._check(step["expect"], resp, step)

    def _bind_result(self, name: str, result: dict) -> None:
        if "client_message_id" in result:
            self._bindings[name] = result["client_message_id"]
        self._bindings[f"_full_{name}"] = result

    def _substitute(self, obj: Any) -> Any:
        if isinstance(obj, str) and obj.startswith("$"):
            key = obj[1:]
            if key not in self._bindings:
                raise KeyError(f"Unbound variable {obj!r}")
            return self._bindings[key]
        if isinstance(obj, dict):
            return {k: self._substitute(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._substitute(v) for v in obj]
        return obj

    def _check(self, expect: dict, resp: dict, step: dict) -> None:
        ctx = f"step cmd={step.get('cmd')!r} client={step.get('client')!r}"

        if "ok" in expect:
            if resp.get("ok") != expect["ok"]:
                raise AssertionFailure(
                    f"{ctx}: expected ok={expect['ok']}, got ok={resp.get('ok')} — {resp}"
                )

        if not resp.get("ok"):
            if "error_code" in expect:
                got = resp.get("error", {}).get("code")
                if got != expect["error_code"]:
                    raise AssertionFailure(
                        f"{ctx}: expected error_code={expect['error_code']!r}, got {got!r}"
                    )
            return

        result = resp.get("result", {})

        if "result" in expect:
            for k, v in expect["result"].items():
                if k == "note":
                    continue
                got = result.get(k)
                exp_v = self._substitute(v)
                if got != exp_v:
                    raise AssertionFailure(
                        f"{ctx}: result.{k}: expected {exp_v!r}, got {got!r}"
                    )

        messages = result.get("messages", [])

        if "contains" in expect:
            for pattern in expect["contains"]:
                pattern = {k: v for k, v in pattern.items() if k != "note"}
                pattern = self._substitute(pattern)
                matches = [m for m in messages if all(m.get(k) == v for k, v in pattern.items())]
                if len(matches) != 1:
                    raise AssertionFailure(
                        f"{ctx}: expected exactly one message matching {pattern!r}, "
                        f"found {len(matches)} in {[m.get('client_message_id') for m in messages]}"
                    )

        if "absent" in expect:
            present_ids = {m.get("client_message_id") for m in messages}
            for ref in expect["absent"]:
                absent_id = self._substitute(ref)
                if absent_id in present_ids:
                    raise AssertionFailure(
                        f"{ctx}: expected {absent_id!r} to be absent, but it appears in the snapshot"
                    )
