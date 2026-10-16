import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
START_BACKEND_VBS = BACKEND_DIR / "start_backend.vbs"
START_ALL_VBS = REPO_ROOT / "start_all.vbs"
STOP_NAVIS_BAT = REPO_ROOT / "Stop_Navis.bat"
VERIFY_BATTLE_PY = BACKEND_DIR / "verify_battle.py"
VERIFY_SERVICES_PY = BACKEND_DIR / "verify_services.py"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop launcher")
@pytest.mark.parametrize("runtime", ["missing", "broken", "unsupported", "crashed", "supported"])
def test_desktop_launcher_validates_automatic_virtualenv(tmp_path, runtime):
    # Run the actual batch selection code in a disposable checkout. Replace only
    # the final app launch with an observation; never start the user's desktop.
    checkout = tmp_path / "Desktop checkout"
    checkout.mkdir()
    script = checkout / "Start_Navis_Desktop.bat"
    source = (REPO_ROOT / script.name).read_text(encoding="utf-8")
    script.write_text(source.replace('start "Navis Protocol" "%APP%"',
                                     'echo SELECTED_PYTHON=%NAVIS_PYTHON%'), encoding="utf-8")
    app = checkout / "frontend/src-tauri/target/release/navis-protocol.exe"
    app.parent.mkdir(parents=True)
    app.write_bytes(b"not launched")
    interpreter = checkout / "backend/.venv/Scripts/python.exe"
    if runtime == "supported":
        subprocess.run([sys.executable, "-m", "venv", "--without-pip",
                        str(checkout / "backend/.venv")], check=True, timeout=30)
    elif runtime == "broken":
        interpreter.parent.mkdir(parents=True)
        interpreter.write_bytes(b"not an executable")
    elif runtime in ("unsupported", "crashed"):
        # A runnable interpreter fixture rejecting the launcher's version probe.
        compiler = Path(os.environ["SystemRoot"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        assert compiler.is_file(), "Windows .NET compiler is needed for the unsupported-runtime fixture"
        interpreter.parent.mkdir(parents=True)
        fixture = checkout / "unsupported.cs"
        exit_code = -1 if runtime == "crashed" else 1
        fixture.write_text(f"class Fixture {{ static int Main(string[] args) {{ return {exit_code}; }} }}", encoding="utf-8")
        subprocess.run([str(compiler), "/nologo", f"/out:{interpreter}", str(fixture)],
                       check=True, capture_output=True, timeout=30)
    environment = {**os.environ, "NAVIS_PYTHON": ""}
    result = subprocess.run(["cmd.exe", "/d", "/c", str(script)], cwd=checkout,
                            env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = str(interpreter) if runtime == "supported" else ""
    assert f"SELECTED_PYTHON={expected}" in result.stdout.splitlines()

    # Explicit overrides remain authoritative, even when invalid. They must not
    # be silently replaced by the automatic virtualenv or system interpreter.
    override = str(checkout / "explicit override.exe")
    environment["NAVIS_PYTHON"] = override
    result = subprocess.run(["cmd.exe", "/d", "/c", str(script)], cwd=checkout,
                            env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"SELECTED_PYTHON={override}" in result.stdout.splitlines()


def run_cscript(script_path: Path, extra_env: dict = None) -> tuple[int, str]:
    """Execute a VBScript with cscript //NoLogo under a controlled environment."""
    env = os.environ.copy()
    env["NAVIS_LAUNCH_DRY_RUN"] = "1"
    if extra_env:
        env.update(extra_env)
    res = subprocess.run(
        ["cscript", "//NoLogo", str(script_path)],
        cwd=str(script_path.parent),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    return res.returncode, res.stdout + res.stderr


def parse_dry_run_output(output: str) -> dict[str, str]:
    result = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("DRY_RUN:"):
            parts = line[len("DRY_RUN:") :].strip().split("=", 1)
            if len(parts) == 2:
                result[parts[0].strip()] = parts[1].strip()
    return result


def test_no_obsolete_paths_in_launchers_and_scripts():
    """Verify that obsolete project/vault paths are completely removed."""
    files_to_check = [
        START_BACKEND_VBS,
        START_ALL_VBS,
        STOP_NAVIS_BAT,
        VERIFY_BATTLE_PY,
        VERIFY_SERVICES_PY,
    ]
    for path in files_to_check:
        assert path.is_file(), f"Expected file {path} to exist"
        content = path.read_text(encoding="utf-8")
        assert "Navis-Web" not in content, f"Obsolete 'Navis-Web' found in {path.name}"
        assert "Navis-Protocol" not in content or "G:\\My Drive\\Navis-Protocol" not in content, (
            f"Obsolete vault path 'Navis-Protocol' found in {path.name}"
        )


def test_window_hidden_convention():
    """Ordinary startup must keep console windows hidden (0, False)."""
    for vbs in [START_BACKEND_VBS, START_ALL_VBS]:
        content = vbs.read_text(encoding="utf-8")
        assert ", 0, False" in content, f"{vbs.name} should use ', 0, False' to hide windows"


def test_start_backend_vbs_dry_run_defaults():
    """Verify start_backend.vbs default directory, NAVIS_ROOT, and uvicorn command."""
    clean_env = {
        "NAVIS_ROOT": "",
        "NAVIS_PYTHON": "",
    }
    code, out = run_cscript(START_BACKEND_VBS, clean_env)
    assert code == 0, f"Script failed with code {code}: {out}"
    parsed = parse_dry_run_output(out)

    assert Path(parsed["BACKEND_DIR"]).resolve() == BACKEND_DIR.resolve()
    assert parsed["NAVIS_ROOT"] == r"G:\My Drive\Navis-Vault"
    assert "uvicorn main:app" in parsed["BACKEND_CMD"]
    assert "--host 127.0.0.1 --port 8000" in parsed["BACKEND_CMD"]


def test_start_backend_vbs_synthetic_overrides(tmp_path):
    """Verify start_backend.vbs honors custom NAVIS_ROOT and NAVIS_PYTHON without clobbering."""
    synthetic_vault = tmp_path / "SyntheticVault"
    synthetic_vault.mkdir()
    synthetic_python = tmp_path / "mock_python.exe"
    synthetic_python.write_text("#!mock", encoding="utf-8")

    override_env = {
        "NAVIS_ROOT": str(synthetic_vault),
        "NAVIS_PYTHON": str(synthetic_python),
    }
    code, out = run_cscript(START_BACKEND_VBS, override_env)
    assert code == 0, f"Script failed: {out}"
    parsed = parse_dry_run_output(out)

    assert parsed["NAVIS_ROOT"] == str(synthetic_vault)
    assert parsed["PYTHON_EXE"] == str(synthetic_python)
    assert str(synthetic_python) in parsed["BACKEND_CMD"]


def test_start_all_vbs_dry_run_defaults():
    """Verify start_all.vbs default directory resolution, NAVIS_ROOT, and both targets."""
    clean_env = {
        "NAVIS_ROOT": "",
        "NAVIS_PYTHON": "",
    }
    code, out = run_cscript(START_ALL_VBS, clean_env)
    assert code == 0, f"Script failed with code {code}: {out}"
    parsed = parse_dry_run_output(out)

    assert Path(parsed["ROOT_DIR"]).resolve() == REPO_ROOT.resolve()
    assert Path(parsed["BACKEND_DIR"]).resolve() == BACKEND_DIR.resolve()
    assert Path(parsed["FRONTEND_DIR"]).resolve() == (REPO_ROOT / "frontend").resolve()
    assert parsed["NAVIS_ROOT"] == r"G:\My Drive\Navis-Vault"
    assert "uvicorn main:app" in parsed["BACKEND_CMD"]
    assert parsed["FRONTEND_CMD"] == "cmd.exe /c npm run dev"


def test_start_all_vbs_synthetic_overrides(tmp_path):
    """Verify start_all.vbs honors custom NAVIS_ROOT and NAVIS_PYTHON."""
    synthetic_vault = tmp_path / "SyntheticVault"
    synthetic_vault.mkdir()
    synthetic_python = tmp_path / "custom_python.exe"
    synthetic_python.write_text("#!mock", encoding="utf-8")

    override_env = {
        "NAVIS_ROOT": str(synthetic_vault),
        "NAVIS_PYTHON": str(synthetic_python),
    }
    code, out = run_cscript(START_ALL_VBS, override_env)
    assert code == 0, f"Script failed: {out}"
    parsed = parse_dry_run_output(out)

    assert parsed["NAVIS_ROOT"] == str(synthetic_vault)
    assert parsed["PYTHON_EXE"] == str(synthetic_python)
    assert str(synthetic_python) in parsed["BACKEND_CMD"]


def test_stop_navis_bat_dry_run():
    """Verify Stop_Navis.bat dry-run targets ports 8000, 3000 and navis-protocol.exe."""
    env = os.environ.copy()
    env["NAVIS_LAUNCH_DRY_RUN"] = "1"
    res = subprocess.run(
        ["cmd.exe", "/c", str(STOP_NAVIS_BAT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert res.returncode == 0
    parsed = parse_dry_run_output(res.stdout)
    assert parsed["STOP_PORTS"] == "8000,3000"
    assert parsed["STOP_PROCESSES"] == "navis-protocol.exe"


def test_runtime_prerequisites():
    """Verify runtime prerequisites: Python >= 3.11 and core backend packages."""
    assert sys.version_info >= (3, 11), f"Python 3.11+ required, got {sys.version}"
    import fastapi
    import uvicorn
    assert fastapi.__file__ is not None
    assert uvicorn.__file__ is not None
