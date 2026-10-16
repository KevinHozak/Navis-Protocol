import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


def test_append_journal_entry_preserves_existing_utf8_bom_and_line_endings(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "NAVIS_ROOT", str(tmp_path))
    journal_dir = tmp_path / "Journal" / "2026" / "09"
    journal_dir.mkdir(parents=True)
    journal_path = journal_dir / "2026-09-21.md"
    journal_path.write_bytes(
        b"\xef\xbb\xbf# Journal\r\n\r\n"
        b"## \xf0\x9f\x8f\xb0 The Sanctum\r\n- [ ] Existing item\r\n\r\n"
        b"## \xf0\x9f\x8f\xa0 The Domestic Breach\r\n- [ ] House task\r\n"
    )

    result = asyncio.run(
        main.append_journal_entry(
            main.JournalEntryRequest(
                date="2026-09-21",
                section="sanctum",
                entry="Continued migration of Navis Protocol to Tauri. Testing out this journal entry through the GUI.",
            )
        )
    )

    saved_bytes = journal_path.read_bytes()
    saved_text = saved_bytes.decode("utf-8-sig")
    assert saved_bytes.startswith(b"\xef\xbb\xbf")
    assert "- [ ] Existing item\r\n\r\n- [x] Continued migration of Navis Protocol to Tauri. Testing out this journal entry through the GUI.\r\n" in saved_text
    assert "## 🏠 The Domestic Breach\r\n- [ ] House task" in saved_text
    assert result["path"] == "Journal/2026/09/2026-09-21.md"
    assert result["content"] == saved_text


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ("Plain journal text", "- [x] Plain journal text"),
        ("- [ ] Unchecked item", "- [x] Unchecked item"),
        ("- [x] Already checked", "- [x] Already checked"),
        ("* [/] In progress", "- [x] In progress"),
        ("- Existing list item", "- [x] Existing list item"),
    ],
)
def test_checked_journal_list_item_normalizes_markdown(entry, expected):
    assert main.checked_journal_list_item(entry) == expected


@pytest.mark.parametrize(
    ("date", "section", "entry", "status_code"),
    [
        ("2026-02-30", "sanctum", "Entry", 422),
        ("2026-09-21", "unknown", "Entry", 422),
        ("2026-09-21", "sanctum", "   ", 422),
        ("2026-09-21", "sanctum", "Entry", 404),
    ],
)
def test_append_journal_entry_rejects_invalid_or_missing_target(
    tmp_path, monkeypatch, date, section, entry, status_code
):
    monkeypatch.setattr(main, "NAVIS_ROOT", str(tmp_path))
    if date == "2026-09-21":
        journal_dir = tmp_path / "Journal" / "2026" / "09"
        journal_dir.mkdir(parents=True)
        if entry == "   ":
            (journal_dir / "2026-09-21.md").write_text(
                "## 🏰 The Sanctum\n", encoding="utf-8-sig"
            )

    with pytest.raises(main.HTTPException) as error:
        asyncio.run(
            main.append_journal_entry(
                main.JournalEntryRequest(date=date, section=section, entry=entry)
            )
        )
    assert error.value.status_code == status_code
