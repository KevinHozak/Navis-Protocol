import pytest

import main


def test_vault_asset_url_quotes_special_characters(monkeypatch):
    vault = r"C:\Vault Root"
    asset = vault + r"\Companions\Ava & Echo\Portrait.png"
    monkeypatch.setattr(main, "NAVIS_ROOT", vault)

    assert main.vault_asset_url(str(asset)) == "/api/vault/Companions/Ava%20%26%20Echo/Portrait.png"


def test_resolve_vault_path_rejects_traversal(monkeypatch):
    monkeypatch.setattr(main, "NAVIS_ROOT", r"C:\Vault Root")

    with pytest.raises(main.HTTPException) as exc_info:
        main.resolve_vault_path("../outside.txt")

    assert exc_info.value.status_code == 400


def test_resolve_vault_path_decodes_spaces(monkeypatch):
    monkeypatch.setattr(main, "NAVIS_ROOT", r"C:\Vault Root")
    expected = r"C:\Vault Root\Companions\Ava & Echo\Portrait.png"

    assert main.resolve_vault_path("Companions/Ava%20%26%20Echo/Portrait.png") == expected
