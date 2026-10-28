import json
import os
import subprocess
import sys
from pathlib import Path

from services.holocron_engine import build_weekly_holocron, export_standalone_html


def make_day(root, day, text):
    path = root / f"Journal/2026/09/{day}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_decision_observations_and_export(tmp_path):
    (tmp_path / "Bridge").mkdir()
    make_day(tmp_path, "2026-09-28", "- [ ] Review <fixture>\n- [ ] Deferred\n")
    make_day(tmp_path, "2026-09-30", "- [x] Review <fixture> <!-- navis-task:fixture:done -->\n- [ ] Deferred\n")
    result = build_weekly_holocron(str(tmp_path), "2026-W40")
    review = result["decision_review"]
    assert "unchecked (2026-09-28) to checked (2026-09-30)" in review["changed"]
    assert "Deferred" in review["unresolved"]
    assert "unknown" in review["unresolved"]
    assert review["kind"] == "deterministic_review_prompt"
    assert len(review["source_ids"]) == 2
    assert "navis-task" not in json.dumps(review)
    html = export_standalone_html(result)
    assert "Review &lt;fixture&gt;" in html and "Review <fixture>" not in html
    assert 'href="#source-journal-2026-09-30"' in html
    assert 'id="source-journal-2026-09-30"' in html
    assert str(tmp_path) not in html
    # Re-read current evidence, never retain stale decision text from cache.
    (tmp_path / "Journal/2026/09/2026-09-30.md").unlink()
    assert "Unknown" in build_weekly_holocron(str(tmp_path), "2026-W40")["decision_review"]["changed"]


def test_missing_evidence_never_invents_blocker(tmp_path):
    result = build_weekly_holocron(str(tmp_path / "absent"), "2026-W40")
    assert result["decision_review"]["source_ids"] == []
    assert result["decision_review"]["unresolved"].startswith("Unknown")
    assert not (tmp_path / "absent").exists()


def test_native_read_and_export_share_decision_review(tmp_path):
    (tmp_path / "Bridge").mkdir()
    make_day(tmp_path, "2026-09-28", "- [ ] Synthetic pending\n")
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, "NAVIS_ROOT": str(tmp_path)}
    for suffix in ("", "/html"):
        request = json.dumps({"path": "/api/holocron/weekly/2026-W40" + suffix, "method": "GET"})
        process = subprocess.run([sys.executable, str(backend / "native_holocron.py")], input=request, text=True, encoding="utf-8", capture_output=True, env=env, check=True)
        result = json.loads(process.stdout)
        assert "Synthetic pending" in json.dumps(result)
