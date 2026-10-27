"""S012 retains the existing atomic append/readback and recovery authority."""
from services import journal_entry as service
import pytest


def test_post_replace_readback_mismatch_is_unverified_and_exact_retry_recovers(tmp_path, monkeypatch):
    path = tmp_path / "Journal/2026/10/2026-10-26.md"
    other = path.with_name("2026-10-27.md")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xef\xbb\xbf# A\r\n## \xf0\x9f\x8f\xb0 The Sanctum\r\n- [ ] Existing\r\n")
    other.write_bytes(b"# B must remain unchanged\r\n")
    before, other_before = path.read_bytes(), other.read_bytes()
    request = {"date": "2026-10-26", "section": "sanctum", "entry": "Synthetic saved entry"}
    snapshot, replace = service._snapshot, service.atomic_bytes
    state = {"replaced": False, "mismatched": False}
    awards = []
    def write(target, raw):
        replace(target, raw)
        state["replaced"] = True
    def read(*args, **kwargs):
        result = snapshot(*args, **kwargs)
        if state["replaced"] and not state["mismatched"]:
            state["mismatched"] = True
            return result[0], result[1], "0" * 64, result[3]
        return result
    with monkeypatch.context() as patch:
        patch.setattr(service, "atomic_bytes", write)
        patch.setattr(service, "_snapshot", read)
        with pytest.raises(service.JournalError, match="recovery_required"):
            service.append(tmp_path, request, award=lambda *args: awards.append(args))
    committed = path.read_bytes()
    assert committed.count(b"- [x] Synthetic saved entry") == 1
    assert before in committed.replace(b"\r\n- [x] Synthetic saved entry\r\n", b"")
    assert other.read_bytes() == other_before and awards == []
    recovered = service.append(tmp_path, request, award=lambda *args: awards.append(args))
    assert recovered["saved"] is True and recovered["replayed"] is True
    assert recovered["xp_status"] == "complete"
    assert recovered["content"] == committed.decode("utf-8-sig")
    again = service.append(tmp_path, request, award=lambda *args: awards.append(args))
    assert again["request_id"] == recovered["request_id"]
    assert len(awards) == 1 and path.read_bytes() == committed
    assert other.read_bytes() == other_before
