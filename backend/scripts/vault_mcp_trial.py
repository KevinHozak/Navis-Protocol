"""S020 synthetic, model-free retrieval comparison and real Codex MCP probe."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import tomllib

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from services.vault_access import VaultPolicy
from services.vault_index import rebuild_index

TOOLS = {"read_note", "search_vault", "get_journal_range", "get_mission"}
SERVER = "navis_vault_trial"


class TrialError(Exception):
    pass


def require(condition, code):
    if not condition:
        raise TrialError(code)


def settings_fingerprint():
    path = Path.home() / ".codex" / "config.toml"
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def source_identity():
    paths = [BACKEND / "scripts/vault_mcp_trial.py", BACKEND / "navis_vault_mcp.py",
             *[BACKEND / "services" / name for name in ("vault_access.py", "vault_index.py", "vault_retrieval.py", "vault_paths.py", "recurrence.py")]]
    return {p.relative_to(BACKEND.parent).as_posix(): hashlib.sha256(
        p.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")).hexdigest() for p in paths}


class CodexPeer:
    """Actual installed app-server client. Never sends turn/start or model input."""
    ALLOWED = {"initialize", "thread/start", "mcpServerStatus/list", "mcpServer/tool/call"}

    def __init__(self, executable, root, state):
        overrides = []
        config = Path.home() / ".codex" / "config.toml"
        existing = tomllib.loads(config.read_text(encoding="utf-8-sig")) if config.exists() else {}
        for name in existing.get("mcp_servers", {}):
            if "." in name:
                raise TrialError("unsupported_dotted_server_config_key")
            overrides.extend(["-c", f"mcp_servers.{name}.enabled=false"])
        for name, value in existing.get("plugins", {}).items():
            if isinstance(value, dict):
                if "." in name:
                    raise TrialError("unsupported_dotted_plugin_config_key")
                overrides.extend(["-c", f"plugins.{name}.enabled=false"])
        values = {
            "command": sys.executable, "args": [str(BACKEND / "navis_vault_mcp.py")],
            "cwd": str(root.parent), "env.NAVIS_ROOT": str(root),
            "env.NAVIS_MCP_TIMEZONE": "America/Chicago", "env.NAVIS_MCP_STATE_DIR": str(state),
        }
        for key, value in values.items():
            overrides.extend(["-c", f"mcp_servers.{SERVER}.{key}={json.dumps(value)}"])
        overrides.extend(["-c", "analytics.enabled=false"])
        self.process = subprocess.Popen([str(executable), *overrides, "app-server", "--stdio"],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, encoding="utf-8", cwd=root.parent)
        self.messages, self.counter, self.calls = queue.Queue(), 0, []
        self.stderr_digest = hashlib.sha256()
        self.stderr_bytes = 0
        self.diagnostics = []

        def read_stdout():
            for line in self.process.stdout:
                self.messages.put(line)
            self.messages.put(None)

        def read_stderr():
            for line in self.process.stderr:
                data = line.encode("utf-8")
                self.stderr_digest.update(data)
                self.stderr_bytes += len(data)
                if "error" in line.casefold() and len(self.diagnostics) < 4:
                    safe = re.sub(r'"[^"\n]*"|\x27[^\x27\n]*\x27', "<quoted>", line.strip())
                    safe = re.sub(r"\S*[\\/]\S*|\S{35,}", "<path-or-long-value>", safe)
                    safe = re.sub(r"(?i)(token|password|secret|api.key)\s*[:=].*", "<redacted>", safe)
                    self.diagnostics.append(safe[:300])

        threading.Thread(target=read_stdout, daemon=True).start()
        self.stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        self.stderr_thread.start()
        try:
            self.rpc("initialize", {"clientInfo": {"name": "navis_s020_fixture", "version": "1"},
                                    "capabilities": {"experimentalApi": True}})
            self.send({"method": "initialized", "params": {}})
            started = self.rpc("thread/start", {"cwd": str(root.parent), "ephemeral": True,
                                                "approvalPolicy": "never", "sandbox": "read-only"})
            self.thread = started["thread"]["id"]
            self.ephemeral_path_is_null = started["thread"].get("path") is None
            require(self.ephemeral_path_is_null, "context_was_not_ephemeral")
            status = self.rpc("mcpServerStatus/list", {"threadId": self.thread, "serverName": SERVER})
            entries = [s for s in status.get("data", []) if s["name"] == SERVER]
            if len(entries) != 1 or set(entries[0].get("tools", {})) != TOOLS:
                raise TrialError("codex_tool_discovery_failed")
            self.status = {"runtime_status": entries[0].get("runtimeStatus"),
                           "server_info": entries[0].get("serverInfo"), "tools": sorted(entries[0]["tools"])}
            if self.status["runtime_status"] != "connected":
                raise TrialError("codex_server_not_connected")
        except BaseException:
            self.close()
            print(json.dumps({"client_startup_diagnostics": self.diagnostics,
                              "stderr_bytes": self.stderr_bytes, "exit_code": self.process.returncode}), file=sys.stderr)
            raise

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def rpc(self, method, params):
        if method not in self.ALLOWED:
            raise TrialError("rpc_method_not_allowed")
        self.counter += 1
        request_id = self.counter
        self.calls.append(method)
        self.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + 40
        while True:
            try:
                line = self.messages.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                raise TrialError("codex_rpc_timeout_" + method.replace("/", "_")) from None
            if line is None:
                raise TrialError("codex_process_ended")
            try:
                message = json.loads(line)
            except ValueError:
                raise TrialError("codex_invalid_json") from None
            if message.get("id") == request_id:
                if "error" in message:
                    raise TrialError("codex_rpc_error_" + method.replace("/", "_") + "_" + str(message["error"].get("code")))
                return message.get("result", {})
            if "method" in message and "id" in message:
                self.send({"id": message["id"], "error": {"code": -32601, "message": "unsupported_trial_request"}})
            if time.monotonic() >= deadline:
                raise TrialError("codex_rpc_timeout")

    def tool(self, name, arguments):
        if name not in TOOLS:
            raise TrialError("non_read_tool_requested")
        result = self.rpc("mcpServer/tool/call", {"threadId": self.thread, "server": SERVER,
                                                "tool": name, "arguments": arguments})
        data = result.get("structuredContent")
        if not isinstance(data, dict):
            raise TrialError("codex_missing_structured_content")
        return data

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], capture_output=True)
                else:
                    self.process.kill()
                self.process.wait(timeout=5)
        self.stderr_thread.join(timeout=2)


def fixture(root):
    files = {
        "Documentation/Decisions/relay.md": "# Relay decision\n## Approved\nLYRA-Z42: keep relay checks offline.\n",
        "Documentation/distractor.md": "# Another decision\nA fictional unrelated choice.\n",
        "Operations/Sanctum/Main/Signal Trial/Mission.md": "# Signal Trial\nRead the [[Documentation/Trial Context]] before the exercise.\n",
        "Documentation/Trial Context.md": "# Trial Context\nThe synthetic relay has three checkpoints.\n",
        "Keeper/xp-state.json": '{"synthetic_xp":123}',
    }
    for i in range(12, 19):
        files[f"Journal/2026/10/2026-10-{i}.md"] = f"# Day {i}\n## Work\nSynthetic checkpoint {i}.\n## Other\nUnrelated fixture text.\n"
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")
    return files


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def baseline(root):
    rg = shutil.which("rg")
    if not rg:
        raise TrialError("rg_unavailable")
    found = subprocess.run([rg, "-l", "--glob", "*.md", "LYRA-Z42", str(root / "Documentation")],
                           capture_output=True, text=True, encoding="utf-8", timeout=10)
    if found.returncode != 0:
        raise TrialError("baseline_discovery_failed")
    paths = [Path(p) for p in found.stdout.splitlines()]
    if len(paths) != 1:
        raise TrialError("baseline_decision_ambiguous")
    decision = paths[0].read_text(encoding="utf-8-sig")
    days = [(root / f"Journal/2026/10/2026-10-{i}.md").read_text(encoding="utf-8-sig") for i in range(12, 19)]
    mission = (root / "Operations/Sanctum/Main/Signal Trial/Mission.md").read_text(encoding="utf-8-sig")
    links = __import__("re").findall(r"\[\[([^]|]+)", mission)
    context = [(root / (link + ".md")).read_text(encoding="utf-8-sig") for link in links]
    return {"decision": decision, "days": days, "context": context,
            "paths": [p.relative_to(root).as_posix() for p in paths]}


def candidate(peer):
    found = peer.tool("search_vault", {"query": "LYRA-Z42"})
    if found.get("status") != "ok" or len(found["data"]["matches"]) != 1:
        raise TrialError("candidate_discovery_failed")
    decision = peer.tool("read_note", {"path": found["data"]["matches"][0]["path"], "section": "Approved"})
    days = peer.tool("get_journal_range", {"start_date": "2026-10-12", "end_date": "2026-10-18", "section": "Work"})
    mission = peer.tool("get_mission", {"name": "Signal Trial"})
    if any(result.get("status") != "ok" for result in (decision, days, mission)):
        raise TrialError("candidate_workflow_failed")
    return {"search": found, "decision": decision, "days": days, "mission": mission}


def verify(root, expected, direct, mcp):
    decision_path = "Documentation/Decisions/relay.md"
    mission_path = "Operations/Sanctum/Main/Signal Trial/Mission.md"
    context_path = "Documentation/Trial Context.md"
    days = [f"Journal/2026/10/2026-10-{i}.md" for i in range(12, 19)]
    require(direct["paths"] == [decision_path] and direct["decision"] == expected[decision_path], "baseline_decision_incorrect")
    require(direct["days"] == [expected[p] for p in days] and direct["context"] == [expected[context_path]], "baseline_context_incorrect")
    sources = [mcp["decision"]["data"], *mcp["days"]["data"]["journals"],
               mcp["mission"]["data"]["mission"], *mcp["mission"]["data"]["related"]]
    require(len(sources) == 10 and {s["path"] for s in sources} == {decision_path, mission_path, context_path, *days}, "candidate_sources_incorrect")
    for source in sources:
        data = (root / source["path"]).read_bytes()
        require(source["sha256"] == hashlib.sha256(expected[source["path"]].encode("utf-8")).hexdigest(), "candidate_digest_incorrect")
        lines = data.decode("utf-8-sig").splitlines(keepends=True)
        selected = "".join(lines[source["start_line"] - 1:source["end_line"]])
        expected_range = (1, 2) if source["path"] in {mission_path, context_path} else (2, 3)
        require((source["start_line"], source["end_line"]) == expected_range and source["content"] == selected
                and bool(source["content"]) and not source.get("truncated", False), "candidate_excerpt_incorrect")
    require([day["date"] for day in mcp["days"]["data"]["journals"]] == [f"2026-10-{i}" for i in range(12, 19)]
            and not mcp["days"]["data"]["missing_dates"], "candidate_dates_incorrect")
    require(len(mcp["mission"]["data"]["related"]) == 1 and mcp["mission"]["data"]["related"][0]["path"] == context_path, "candidate_related_incorrect")
    require(mcp["decision"]["data"]["content"] == "## Approved\nLYRA-Z42: keep relay checks offline.\n", "candidate_decision_incorrect")
    hit = mcp["search"]["data"]["matches"][0]
    require(hit["path"] == decision_path and hit["sha256"] == hashlib.sha256(expected[decision_path].encode("utf-8")).hexdigest(), "search_source_incorrect")
    require(hit["start_line"] == 3 and hit["snippet"] == "LYRA-Z42: keep relay checks offline.\n", "search_excerpt_incorrect")


def summary(values):
    ordered = sorted(values)
    return {"samples_ms": [round(v * 1000, 3) for v in values],
            "median_ms": round(statistics.median(values) * 1000, 3),
            "p95_ms": round(ordered[math.ceil(0.95 * len(values)) - 1] * 1000, 3)}


def run(executable, work_directory):
    sources_before = source_identity()
    settings_before = settings_fingerprint()
    version_result = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=10)
    version_match = re.search(r"^codex-cli ([\w.+-]+)$", version_result.stdout.strip())
    if version_result.returncode or not version_match:
        raise TrialError("codex_version_unavailable")
    work = Path(work_directory).resolve()
    if work == BACKEND.parent or BACKEND.parent in work.parents:
        raise TrialError("trial_state_must_be_outside_checkout")
    configured_vault = os.environ.get("NAVIS_ROOT")
    if configured_vault:
        boundary = Path(configured_vault).resolve()
        require(work != boundary and boundary not in work.parents, "trial_state_must_be_outside_configured_vault")
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="s020-synthetic-", dir=work) as temporary:
        root = Path(temporary) / "fixture-vault"
        expected = fixture(root)
        before = hashes(root)
        state = Path(temporary) / "private-index"
        policy = VaultPolicy.from_env({"NAVIS_ROOT": str(root), "NAVIS_MCP_TIMEZONE": "America/Chicago"})
        started = time.perf_counter()
        rebuild_index(policy, str(state))
        index_seconds = time.perf_counter() - started
        started = time.perf_counter()
        peer = CodexPeer(executable, root, state)
        connect_seconds = time.perf_counter() - started
        try:
            direct_times, mcp_times = [], []
            for i in range(5):
                results = {}
                for route in (("baseline", "mcp") if i % 2 == 0 else ("mcp", "baseline")):
                    started = time.perf_counter()
                    results[route] = baseline(root) if route == "baseline" else candidate(peer)
                    (direct_times if route == "baseline" else mcp_times).append(time.perf_counter() - started)
                verify(root, expected, results["baseline"], results["mcp"])
            if hashes(root) != before:
                raise TrialError("unexpected_fixture_mutation")
            changed = root / "Documentation/Decisions/relay.md"
            decision_path = changed.relative_to(root).as_posix()
            changed.write_text(expected["Documentation/Decisions/relay.md"].replace("offline.", "offline for the trial."), encoding="utf-8", newline="")
            stale = peer.tool("search_vault", {"query": "LYRA-Z42"})
            if stale.get("error", {}).get("code") != "index_stale" or "data" in stale:
                raise TrialError("stale_result_not_rejected")
            started = time.perf_counter()
            rebuild_index(policy, str(state))
            recovered = peer.tool("search_vault", {"query": "LYRA-Z42"})
            recovery_seconds = time.perf_counter() - started
            require(recovered["status"] == "ok" and "offline for the trial." in recovered["data"]["matches"][0]["snippet"], "freshness_recovery_failed")
            after = hashes(root)
            require({p: digest for p, digest in after.items() if p != decision_path} == {p: digest for p, digest in before.items() if p != decision_path}, "unexpected_recovery_mutation")
            record = {"schema_version": 1, "fixture_only": True, "codex_version": version_match[1],
                      "python_version": sys.version.split()[0], "sqlite_version": sqlite3.sqlite_version,
                      "platform": sys.platform,
                      "source_identity": [{"sha256": digest, "path": path} for path, digest in sources_before.items()],
                      "primary_runtime": peer.status,
                      "ephemeral_context_path_is_null": peer.ephemeral_path_is_null,
                      "baseline": summary(direct_times), "codex_mcp": summary(mcp_times),
                      "index_build_ms": round(index_seconds * 1000, 3), "client_connect_ms": round(connect_seconds * 1000, 3),
                      "correct_sources_per_repetition": 10, "unexpected_omissions": 0, "repetitions": 5,
                      "stale_rejected": True, "scripted_recovery_ms": round(recovery_seconds * 1000, 3),
                      "recovery_operator_actions": 2, "human_correction_time": None,
                      "integrity": "only deliberately changed decision differs", "rpc_methods_used": sorted(set(peer.calls)),
                      "secondary_client": "Claude Desktop unverified; unsupported in this trial's adoption scope",
                      "desktop_ui": "not exercised; desktop-bundled app-server runtime is recorded separately"}
        finally:
            peer.close()
        record["client_exit_code"] = peer.process.returncode
        record["client_stderr_bytes_not_retained"] = peer.stderr_bytes
        record["client_stderr_sha256"] = peer.stderr_digest.hexdigest()
        require(settings_fingerprint() == settings_before, "persistent_config_changed_during_trial")
        require(source_identity() == sources_before, "trial_source_changed_during_run")
        require(peer.process.returncode == 0, "codex_shutdown_failed")
        record["persistent_mcp_config_unchanged"] = True
        record["gates"] = {"primary_codex_runtime": True, "source_correctness": True, "zero_omissions": True,
                           "freshness": True, "integrity": True, "fixture_latency": record["codex_mcp"]["p95_ms"] <= 2000}
        record["decision"] = "adopt_read_only_pilot" if all(record["gates"].values()) else "revise"
        record["adoption_scope"] = "Verified desktop-bundled Codex app-server runtime on synthetic corpus; UI setup, human quality and personal-Vault scale unverified. No write enablement."
        return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-executable", required=True)
    parser.add_argument("--work-directory", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        result = run(Path(args.codex_executable).resolve(), args.work_directory)
        Path(args.report).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
        return 0
    except (TrialError, AssertionError) as error:
        print(json.dumps({"status": "failed", "code": str(error) if isinstance(error, TrialError) else "golden_verification_failed"}))
        return 1
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print('{"status":"failed","code":"trial_environment_error"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
