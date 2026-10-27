"""Golden-oracle and no-model guard tests; actual Codex connection is a trial."""
import copy

import pytest

from scripts.vault_mcp_trial import (
    CodexPeer, TrialError, baseline, candidate, fixture, summary, verify,
)
from services.vault_access import VaultPolicy, read_note
from services.vault_index import rebuild_index, search_vault
from services.vault_retrieval import get_journal_range, get_mission


@pytest.fixture
def observed(tmp_path):
    root = tmp_path / "fixture-vault"
    expected = fixture(root)
    state = str(tmp_path / "private-state")
    policy = VaultPolicy.from_env({"NAVIS_ROOT": str(root), "NAVIS_MCP_TIMEZONE": "America/Chicago"})
    rebuild_index(policy, state)

    class LocalPeer:
        def tool(self, name, arguments):
            if name == "search_vault":
                return search_vault(policy, state, arguments)
            return {"read_note": read_note, "get_journal_range": get_journal_range,
                    "get_mission": get_mission}[name](policy, arguments)

    return root, expected, baseline(root), candidate(LocalPeer())


def test_golden_trial_accepts_correct_sources(observed):
    verify(*observed)


@pytest.mark.parametrize("mutation", ["wrong_path", "wrong_digest", "empty_content", "wrong_lines", "omitted_day"])
def test_golden_trial_rejects_incorrect_or_omitted_evidence(observed, mutation):
    root, expected, direct, actual = observed
    actual = copy.deepcopy(actual)
    if mutation == "omitted_day":
        actual["days"]["data"]["journals"].pop()
    else:
        source = actual["days"]["data"]["journals"][0]
        if mutation == "wrong_path":
            source["path"] = "Documentation/Decisions/relay.md"
        elif mutation == "wrong_digest":
            source["sha256"] = "0" * 64
        elif mutation == "wrong_lines":
            source["start_line"] = 1
        else:
            source["content"] = ""
    with pytest.raises(TrialError):
        verify(root, expected, direct, actual)


def test_probe_rejects_model_turns_before_transport_access():
    peer = CodexPeer.__new__(CodexPeer)
    with pytest.raises(TrialError, match="rpc_method_not_allowed"):
        peer.rpc("turn/start", {"input": "not sent"})


def test_reported_p95_uses_predefined_nearest_rank():
    got = summary([0.2, 0.1, 0.4, 0.3, 0.5])
    assert got["median_ms"] == 300 and got["p95_ms"] == 500
