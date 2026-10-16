import os
import json
import subprocess
from datetime import datetime

NAVIS_VAULT_ROOT = os.getenv("NAVIS_VAULT_ROOT", r"G:\My Drive\Navis-Vault")
BIOMETRICS_PATH = os.path.join(NAVIS_VAULT_ROOT, "Bridge", "biometrics.json")
STATUS_PATH = os.path.join(NAVIS_VAULT_ROOT, "Bridge", "status.json")

# In-memory tracking of the last trigger time to avoid spamming alerts
last_trigger_time = None


def check_biometrics_and_intervene():
    global last_trigger_time
    if not os.path.exists(BIOMETRICS_PATH):
        print(f"Daemon: biometrics.json not found at {BIOMETRICS_PATH}")
        return

    try:
        with open(BIOMETRICS_PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Daemon: Error reading biometrics.json: {e}")
        return

    biometrics = data.get("biometrics", {})
    suds_val = biometrics.get("suds", {}).get("value", 0)
    focus_val = biometrics.get("focus", {}).get("value", 10)

    # Trigger threshold: SUDs >= 7 or Focus <= 3
    if suds_val >= 7 or focus_val <= 3:
        now = datetime.now()
        # Cooldown check: 30 minutes (1800 seconds)
        if last_trigger_time is not None:
            delta = (now - last_trigger_time).total_seconds()
            if delta < 1800:
                print(
                    f"Daemon: Distress condition active but within cooldown ({int(delta)}s elapsed)."
                )
                return

        last_trigger_time = now
        print(f"Daemon: STRAIN DETECTED! SUDs: {suds_val}, Focus: {focus_val}")

        # 1. Update status.json context
        if os.path.exists(STATUS_PATH):
            try:
                with open(STATUS_PATH, "r", encoding="utf-8-sig") as f:
                    status = json.load(f)

                status["active_bridge_context"] = "FRIDR_HALL"
                status["location"] = "Friðr Hall"

                with open(STATUS_PATH, "w", encoding="utf-8-sig") as f:
                    json.dump(status, f, indent=4)
                print("Daemon: Updated status.json location to Friðr Hall")
            except Exception as e:
                print(f"Daemon: Failed to update status.json: {e}")

        # 2. Append to daily Reflection Chamber log
        fridr_dir = os.path.join(NAVIS_VAULT_ROOT, "Reflection Chamber", "Fridr Hall")
        os.makedirs(fridr_dir, exist_ok=True)
        today_str = datetime.now().strftime("%Y-%m-%d")
        log_path = os.path.join(fridr_dir, f"{today_str}.md")

        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = (
            f"\n### [{timestamp}] Autonomous Intervention Alert\n"
            f"- **Trigger:** Elevated mental strain detected.\n"
            f"- **SUDs:** {suds_val}/10\n"
            f"- **Focus:** {focus_val}/10\n"
            f"- **Action:** Spoken alert triggered. Active bridge context set to Friðr Hall.\n\n"
        )
        try:
            with open(log_path, "a", encoding="utf-8-sig") as f:
                f.write(entry)
            print(f"Daemon: Logged intervention alert to {log_path}")
        except Exception as e:
            print(f"Daemon: Failed to append to intervention log: {e}")

        # 3. Voice TTS Alert (Microsoft Zira voice)
        alert_msg = f"Keeper, Reid has detected elevated mental strain. SUDs are at {suds_val}, focus is at {focus_val}. Let us enter Friðr Hall to restore balance."
        trigger_voice_alert(alert_msg)


def trigger_voice_alert(message: str):
    script_path = r"C:\Projects\Agents\speak.ps1"
    cmd = [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script_path,
        "-Message",
        message,
    ]
    try:
        subprocess.run(cmd, check=True)
        print("Daemon: Successfully triggered voice alert.")
    except Exception as e:
        print(f"Daemon: Error running speak.ps1: {e}")
