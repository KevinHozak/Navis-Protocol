import os
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
import main


@pytest.fixture
def test_vault(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    monkeypatch.setattr(main, "NAVIS_ROOT", str(vault))
    return vault, outside


def test_resolve_vault_path_strict_rejection(test_vault):
    vault, outside = test_vault

    # Empty or whitespace paths
    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("")
    assert exc_info.value.status_code == 400

    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("   ")
    assert exc_info.value.status_code == 400

    # Path pointing to root itself
    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path(".")
    assert exc_info.value.status_code == 400

    # Directory traversal
    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("../outside.txt")
    assert exc_info.value.status_code == 400

    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("foo/../../bar.txt")
    assert exc_info.value.status_code == 400

    # URL-encoded directory traversal
    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("%2e%2e/outside.txt")
    assert exc_info.value.status_code == 400

    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("%2e%2e%2foutside.txt")
    assert exc_info.value.status_code == 400

    # Windows drive-qualified / absolute paths
    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path(r"C:\Windows\System32\drivers\etc\hosts")
    assert exc_info.value.status_code == 400

    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("C:/temp/outside.txt")
    assert exc_info.value.status_code == 400

    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("D:/other_drive/file.txt")
    assert exc_info.value.status_code == 400

    # Root-relative paths
    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("/etc/passwd")
    assert exc_info.value.status_code == 400

    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path(r"\Windows\System32")
    assert exc_info.value.status_code == 400

    # UNC paths
    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path(r"\\server\share\file.txt")
    assert exc_info.value.status_code == 400

    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("//server/share/file.txt")
    assert exc_info.value.status_code == 400


def test_resolve_vault_path_symlink_containment(test_vault):
    vault, outside = test_vault
    outside_target = outside / "secret.md"
    outside_target.write_text("secret outside", encoding="utf-8-sig")

    symlink_dir = vault / "linked_dir"
    created = False
    try:
        os.symlink(str(outside), str(symlink_dir), target_is_directory=True)
        created = True
    except (OSError, NotImplementedError):
        try:
            import _winapi

            _winapi.CreateJunction(str(outside), str(symlink_dir))
            created = True
        except Exception:
            pass

    if not created:
        pytest.skip("Symlink/Junction creation not permitted in this environment")

    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("linked_dir/secret.md")
    assert exc_info.value.status_code == 400
    assert "escapes Vault root" in exc_info.value.detail or "symlink" in exc_info.value.detail


def test_resolve_vault_path_valid_resolutions(test_vault):
    vault, _ = test_vault

    # Normal relative path
    resolved = main.resolve_vault_path("Operations/The Sanctum/Tasks.md")
    assert resolved == os.path.abspath(str(vault / "Operations" / "The Sanctum" / "Tasks.md"))

    # Mixed separators
    resolved_mixed = main.resolve_vault_path(r"Operations\The Sanctum/Tasks.md")
    assert resolved_mixed == resolved

    # URL-encoded spaces and characters
    resolved_encoded = main.resolve_vault_path("Companions/Ava%20%26%20Echo/Profile.md")
    assert resolved_encoded == os.path.abspath(str(vault / "Companions" / "Ava & Echo" / "Profile.md"))


def test_toggle_task_rejects_out_of_root_and_preserves_external_file(test_vault):
    vault, outside = test_vault
    outside_task = outside / "critical_tasks.md"
    original_content = "- [ ] Outside sensitive task\n- [ ] Second item\n"
    outside_task.write_text(original_content, encoding="utf-8-sig")
    initial_bytes = outside_task.read_bytes()

    client = TestClient(main.app)

    malicious_paths = [
        "../outside/critical_tasks.md",
        "%2e%2e/outside/critical_tasks.md",
        "%2e%2e%2foutside%2fcritical_tasks.md",
        str(outside_task),
        f"/{outside_task.name}",
        r"\\fake-server\share\critical_tasks.md",
    ]

    for bad_path in malicious_paths:
        payload = {
            "file_path": bad_path,
            "target_text": "Outside sensitive task",
            "is_checked": True,
            "line_number": 1,
        }
        response = client.post("/api/tasks/toggle", json=payload)
        assert response.status_code == 400, f"Expected 400 for {bad_path}, got {response.status_code}"

    # Critical check: Outside target remains byte-identical
    assert outside_task.read_bytes() == initial_bytes
    assert outside_task.read_text(encoding="utf-8-sig") == original_content


def test_toggle_task_resolves_directory_profile_and_toggles(test_vault):
    vault, _ = test_vault
    sanctum = vault / "Operations" / "The Sanctum"
    sanctum.mkdir(parents=True)
    profile = sanctum / "Profile.md"
    profile.write_text("# Sanctum Profile\n\n- [ ] Deploy defense network\n", encoding="utf-8-sig")

    client = TestClient(main.app)

    with patch("services.rpg_engine.calculate_and_apply_xp", return_value=None):
        # 1. Toggle via directory path
        payload = {
            "file_path": "Operations/The Sanctum",
            "target_text": "Deploy defense network",
            "expected_content": profile.read_bytes().decode("utf-8-sig"),
            "is_checked": True,
        }
        res1 = client.post("/api/tasks/toggle", json=payload)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "success"
        assert data1["modified"] is True
        assert "- [x] Deploy defense network" in data1["content"]

        # Verify on disk
        disk_content = profile.read_text(encoding="utf-8-sig")
        assert "- [x] Deploy defense network" in disk_content

        # 2. Toggle back via URL-encoded directory path
        payload_encoded = {
            "file_path": "Operations/The%20Sanctum",
            "target_text": "Deploy defense network",
            "expected_content": profile.read_bytes().decode("utf-8-sig"),
            "is_checked": False,
        }
        res2 = client.post("/api/tasks/toggle", json=payload_encoded)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "success"
        assert data2["modified"] is True
        assert "- [ ] Deploy defense network" in data2["content"]

        disk_content2 = profile.read_text(encoding="utf-8-sig")
        assert "- [ ] Deploy defense network" in disk_content2


def test_toggle_task_in_vault_preserves_utf8_sig_and_emojis(test_vault):
    vault, _ = test_vault
    journal_dir = vault / "Journal" / "2026" / "10"
    journal_dir.mkdir(parents=True)
    journal_file = journal_dir / "2026-10-01.md"
    initial_text = "# Daily Chronicle 🛡️\n\n## 🏰 The Sanctum\n- [ ] Inspect shields ⚡\n"
    journal_file.write_text(initial_text, encoding="utf-8-sig")

    client = TestClient(main.app)

    with patch("services.rpg_engine.calculate_and_apply_xp", return_value=None):
        payload = {
            "file_path": "Journal/2026/10/2026-10-01.md",
            "target_text": "Inspect shields ⚡",
            "expected_content": journal_file.read_bytes().decode("utf-8-sig"),
            "is_checked": True,
            "line_number": 4,
        }
        res = client.post("/api/tasks/toggle", json=payload)
        assert res.status_code == 200
        assert res.json()["modified"] is True

        # Check BOM and content
        raw_bytes = journal_file.read_bytes()
        assert raw_bytes.startswith(b"\xef\xbb\xbf")
        saved_text = journal_file.read_text(encoding="utf-8-sig")
        assert "- [x] Inspect shields ⚡" in saved_text
