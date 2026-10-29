import os
import json
import sqlite3
import csv
import glob
import shutil
import tempfile
import requests
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import sys
import argparse

# --- Encoding Fix for Windows ---
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# Google Auth Libraries
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

# --- Configuration ---
AGENTS_DIR = r"C:\Projects\Agents"
CLIENT_SECRETS_FILE = os.environ.get(
    "NAVIS_BIOMETRICS_CLIENT_SECRETS_FILE", os.path.join(AGENTS_DIR, "credentials.json")
)
BIOMETRICS_TOKEN_FILE = os.environ.get(
    "NAVIS_BIOMETRICS_TOKEN_FILE", os.path.join(AGENTS_DIR, "biometrics_token.json")
)

FITBIT_GLOBAL_DIR = r"G:\My Drive\Inbox\Fitbit\Global Export Data"
FITBIT_STRESS_CSV = r"G:\My Drive\Inbox\Fitbit\Stress Score\Stress Score.csv"
HC_DB_PATH = r"G:\My Drive\Inbox\HealthConnect_Temp\health_connect_export.db"
NAVIS_ROOT = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
FINAL_DB_PATH = os.path.join(NAVIS_ROOT, "Keeper", "FitbitChronicle.db")
LOCAL_DB_PATH = os.path.join(tempfile.gettempdir(), "FitbitChronicle.db")

# Scopes for Google Health API (2026 Unified Platform)
SCOPES = [
    'https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly',
    'https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly',
    'https://www.googleapis.com/auth/googlehealth.sleep.readonly'
]

def get_authenticated_session():
    """Handles the OAuth2 flow and returns a valid credentials object."""
    creds = None
    if os.path.exists(BIOMETRICS_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(BIOMETRICS_TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                print("⚠️ Google biometrics credentials need renewal. Run sync_biometrics.py --reauthorize-only.")
                return None
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"⚠️ client_secrets.json not found in {AGENTS_DIR}. API sync skipped.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        _persist_credentials_atomically(creds, BIOMETRICS_TOKEN_FILE)

    return creds


def _persist_credentials_atomically(creds, token_path):
    """Replace a token file only after complete credentials JSON is available."""
    token_json = creds.to_json()
    token_dir = os.path.dirname(os.path.abspath(token_path))
    fd, temporary_path = tempfile.mkstemp(prefix=".biometrics-token-", suffix=".tmp", dir=token_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as token:
            token.write(token_json)
            token.flush()
            os.fsync(token.fileno())
        os.replace(temporary_path, token_path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise


def reauthorize_only():
    """Run a fresh, bounded Google authorization and save only on success."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print("⚠️ Google client configuration is unavailable; reauthorization was not started.")
        return False

    try:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        creds = flow.run_local_server(
            host="127.0.0.1",
            bind_addr="127.0.0.1",
            port=0,
            timeout_seconds=300,
            prompt="consent",
            access_type="offline",
            authorization_prompt_message="Complete Google authorization in your browser.",
            success_message="Google authorization complete. You may close this window.",
        )
    except (Exception, KeyboardInterrupt) as exc:
        # Avoid printing exception details, which can contain an auth URL or code.
        print(f"⚠️ Google reauthorization did not complete ({type(exc).__name__}). Existing credentials were kept.")
        return False

    if not creds or not creds.valid or not creds.refresh_token or not creds.has_scopes(SCOPES):
        print("⚠️ Google reauthorization did not return complete refreshable Health credentials. Existing credentials were kept.")
        return False

    try:
        _persist_credentials_atomically(creds, BIOMETRICS_TOKEN_FILE)
    except Exception as exc:
        print(f"⚠️ Could not save the new biometrics credentials ({type(exc).__name__}).")
        return False
    print("✅ Google biometrics authorization saved.")
    return True

def fetch_api_data(creds, daily_data, cursor):
    """Fetches the last 14 days of data from Google Health API to fill gaps."""
    if not creds: return

    print("📡 Synchronizing with Google Health API (v4)...")
    headers = {'Authorization': f'Bearer {creds.token}', 'Accept': 'application/json'}
    base_url = "https://health.googleapis.com/v4/users/me/dataTypes"

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=13)

    start_str = start_time.strftime("%Y-%m-%dT00:00:00Z")
    end_str = end_time.strftime("%Y-%m-%dT23:59:59Z")

    # --- 1. RollUp Metrics (Steps, Calories, Heart Rate Summary) ---
    metrics = {
        "steps": "steps",
        "calories": "total-calories",
        "heart_rate": "heart-rate"
    }

    for key, data_type in metrics.items():
        try:
            url = f"{base_url}/{data_type}/dataPoints:rollUp"
            payload = {"range": {"startTime": start_str, "endTime": end_str}, "windowSize": "86400s"}
            response = requests.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                points = response.json().get('rollupDataPoints', [])
                for p in points:
                    dt = p['startTime'].split('T')[0]
                    if key == "steps":
                        val = int(p.get('steps', {}).get('countSum', 0))
                        daily_data[dt]["steps"] = max(daily_data[dt]["steps"], val)
                    elif key == "calories":
                        val = float(p.get('totalCalories', {}).get('kcalSum', 0))
                        daily_data[dt]["calories"] = max(daily_data[dt]["calories"], val)
                    elif key == "heart_rate":
                        hr_stats = p.get('heartRate', {})
                        if hr_stats:
                            # v4 heart-rate rollup uses these specific field names
                            daily_data[dt]["avg_hr"] = int(round(float(hr_stats.get('beatsPerMinuteAvg', 0))))
                            daily_data[dt]["hr_min"] = int(hr_stats.get('beatsPerMinuteMin', 0))
                            daily_data[dt]["hr_max"] = int(hr_stats.get('beatsPerMinuteMax', 0))
            else:
                print(f"   ❌ API error for {key}: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error fetching {key}: {e}")

    # --- 2. Special Case: Sleep (List DataPoints) ---
    try:
        sleep_url = f"{base_url}/sleep/dataPoints"
        params = {
            "filter": f'sleep.interval.end_time >= "{start_str}"',
            "pageSize": 50
        }
        response = requests.get(sleep_url, headers=headers, params=params)
        if response.status_code == 200:
            points = response.json().get('dataPoints', [])
            for p in points:
                sleep_obj = p.get('sleep', {})
                summary = sleep_obj.get('summary', {})
                interval = sleep_obj.get('interval', {})

                dt = interval.get('endTime', '').split('T')[0]
                if dt:
                    asleep_min = int(summary.get('minutesAsleep', 0))
                    if asleep_min > 0:
                        daily_data[dt]["sleep_min"] = max(daily_data[dt]["sleep_min"], asleep_min)
                        total_period = int(summary.get('minutesInSleepPeriod', 0))
                        if total_period > 0:
                            eff = int((asleep_min / total_period) * 100)
                            daily_data[dt]["sleep_eff_sum"] += eff
                            daily_data[dt]["sleep_count"] += 1
        else:
            print(f"   ❌ API error for sleep: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error fetching sleep: {e}")
    # --- 3. Special Case: Exercises (List DataPoints) ---
    try:
        ex_url = f"{base_url}/exercise/dataPoints"
        ex_params = {"pageSize": 100}
        ex_res = requests.get(ex_url, headers=headers, params=ex_params)
        if ex_res.status_code == 200:
            ex_points = ex_res.json().get('dataPoints', [])
            for p in ex_points:
                ex_obj = p.get('exercise', {})
                name_id_str = p.get('name', '').split('/')[-1]
                try:
                    log_id = int(name_id_str)
                except ValueError:
                    continue # Ignore if we can't parse log_id

                interval = ex_obj.get('interval', {})
                dt_str = interval.get('startTime', '')
                if not dt_str: continue
                dt = dt_str.split('T')[0]

                metrics = ex_obj.get('metricsSummary', {})
                activity_name = ex_obj.get('displayName', ex_obj.get('exerciseType', 'Unknown'))

                duration_s_str = ex_obj.get('activeDuration', '0s').replace('s', '')
                try:
                    duration_minutes = int(float(duration_s_str)) // 60
                except:
                    duration_minutes = 0

                calories = int(metrics.get('caloriesKcal', 0))
                distance_mm = int(metrics.get('distanceMillimeters', 0))
                distance_mi = round(distance_mm / 1609344.0, 2)
                avg_hr = int(metrics.get('averageHeartRateBeatsPerMinute', 0))
                steps = int(metrics.get('steps', 0))

                cursor.execute('''
                    INSERT INTO exercise_logs (log_id, date, activity_name, duration_minutes, calories, distance, avg_hr, steps)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(log_id) DO NOTHING
                ''', (log_id, dt, activity_name, duration_minutes, calories, distance_mi, avg_hr, steps))
        else:
            print(f"   ❌ API error for exercise: {ex_res.status_code}")
    except Exception as e:
        print(f"   ❌ Error fetching exercise: {e}")

def init_db():
    if os.path.exists(LOCAL_DB_PATH):
        try: os.remove(LOCAL_DB_PATH)
        except: pass

    if os.path.exists(FINAL_DB_PATH):
        try: shutil.copy2(FINAL_DB_PATH, LOCAL_DB_PATH)
        except: pass

    conn = sqlite3.connect(LOCAL_DB_PATH)
    cursor = conn.cursor()

    # Core Tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_vitals (
            date TEXT PRIMARY KEY,
            steps INTEGER DEFAULT 0,
            calories REAL DEFAULT 0,
            sleep_minutes INTEGER DEFAULT 0,
            sleep_efficiency INTEGER DEFAULT 0,
            avg_hr REAL DEFAULT 0,
            min_hr INTEGER DEFAULT 0,
            max_hr INTEGER DEFAULT 0,
            stress_score INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exercise_logs (
            log_id INTEGER PRIMARY KEY,
            date TEXT,
            activity_name TEXT,
            duration_minutes INTEGER,
            calories INTEGER,
            distance REAL,
            avg_hr INTEGER,
            steps INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weight_logs (
            log_id TEXT PRIMARY KEY,
            date TEXT,
            weight_lbs REAL,
            fat_percent REAL,
            bmi REAL,
            source TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS physiological_vitals (
            log_id TEXT PRIMARY KEY,
            date TEXT,
            hrv_rmssd REAL,
            source TEXT
        )
    ''')

    # New Intelligence Tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vo2_max_logs (
            date TEXT PRIMARY KEY,
            vo2_max REAL,
            source TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_intensity (
            date TEXT PRIMARY KEY,
            sedentary_min INTEGER DEFAULT 0,
            lightly_active_min INTEGER DEFAULT 0,
            moderately_active_min INTEGER DEFAULT 0,
            very_active_min INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS badges (
            badge_id TEXT PRIMARY KEY,
            date TEXT,
            name TEXT,
            description TEXT,
            category TEXT,
            times_achieved INTEGER
        )
    ''')

    conn.commit()
    return conn

def import_data():
    print("🛡️ Initializing Master Vitals Vault...")
    conn = init_db()
    cursor = conn.cursor()

    daily_data = defaultdict(lambda: {
        "steps": 0, "calories": 0.0,
        "sleep_min": 0, "sleep_eff_sum": 0, "sleep_count": 0,
        "hr_sum": 0, "hr_count": 0, "hr_min": 999, "hr_max": 0,
        "stress": 0, "avg_hr": 0
    })

    # --- 📂 Legacy Local File Parsing (Fall-back) ---
    if os.path.exists(FITBIT_GLOBAL_DIR):
        print(f"📂 Parsing Daily Metrics from {FITBIT_GLOBAL_DIR}...")

        # Steps
        for f in glob.glob(os.path.join(FITBIT_GLOBAL_DIR, "steps-*.json")):
            try:
                with open(f, 'r', encoding='utf-8') as jf:
                    for entry in json.load(jf):
                        dt = datetime.strptime(entry["dateTime"], "%m/%d/%y %H:%M:%S").strftime("%Y-%m-%d")
                        daily_data[dt]["steps"] += int(entry["value"])
            except: pass

        # Calories
        for f in glob.glob(os.path.join(FITBIT_GLOBAL_DIR, "calories-*.json")):
            try:
                with open(f, 'r', encoding='utf-8') as jf:
                    for entry in json.load(jf):
                        dt = datetime.strptime(entry["dateTime"], "%m/%d/%y %H:%M:%S").strftime("%Y-%m-%d")
                        daily_data[dt]["calories"] += float(entry["value"])
            except: pass

        # Sleep
        for f in glob.glob(os.path.join(FITBIT_GLOBAL_DIR, "sleep-*.json")):
            try:
                with open(f, 'r', encoding='utf-8') as jf:
                    for entry in json.load(jf):
                        date = entry.get("dateOfSleep")
                        if date:
                            daily_data[date]["sleep_min"] += entry.get("minutesAsleep", 0)
                            daily_data[date]["sleep_eff_sum"] += entry.get("efficiency", 0)
                            daily_data[date]["sleep_count"] += 1
            except: pass

        # Heart Rate
        print("💓 Parsing Heart Rate...")
        for f in glob.glob(os.path.join(FITBIT_GLOBAL_DIR, "heart_rate-*.json")):
            try:
                with open(f, 'r', encoding='utf-8') as jf:
                    for entry in json.load(jf):
                        dt = datetime.strptime(entry["dateTime"], "%m/%d/%y %H:%M:%S").strftime("%Y-%m-%d")
                        bpm = int(entry["value"]["bpm"])
                        daily_data[dt]["hr_sum"] += bpm
                        daily_data[dt]["hr_count"] += 1
                        if bpm < daily_data[dt]["hr_min"]: daily_data[dt]["hr_min"] = bpm
                        if bpm > daily_data[dt]["hr_max"]: daily_data[dt]["hr_max"] = bpm
            except: pass

        # Stress
        print("🧘 Parsing Stress Scores...")
        if os.path.exists(FITBIT_STRESS_CSV):
            try:
                with open(FITBIT_STRESS_CSV, 'r', encoding='utf-8') as cf:
                    reader = csv.DictReader(cf)
                    for row in reader:
                        dt = row["DATE"].split("T")[0]
                        score = int(row.get("STRESS_SCORE", 0))
                        if score > 0: daily_data[dt]["stress"] = score
            except: pass

    # --- 📡 API Sync (New Intelligence) ---
    creds = get_authenticated_session()
    if creds:
        fetch_api_data(creds, daily_data, cursor)

    # --- 🧠 Advanced Intelligence ---
    if os.path.exists(FITBIT_GLOBAL_DIR):
        print("🧠 Parsing VO2 Max...")
        for f in glob.glob(os.path.join(FITBIT_GLOBAL_DIR, "demographic_vo2_max*.json")):
            try:
                with open(f, 'r', encoding='utf-8') as jf:
                    for entry in json.load(jf):
                        dt = datetime.strptime(entry["dateTime"], "%m/%d/%y %H:%M:%S").strftime("%Y-%m-%d")
                        val = entry["value"].get("demographicVO2Max")
                        if val: cursor.execute("INSERT OR REPLACE INTO vo2_max_logs (date, vo2_max, source) VALUES (?, ?, ?)", (dt, val, "Fitbit"))
            except: pass

        print("⚡ Parsing Activity Intensity...")
        intensity_data = defaultdict(lambda: {"sedentary": 0, "lightly": 0, "moderately": 0, "very": 0})
        for prefix in ["sedentary", "lightly_active", "moderately_active", "very_active"]:
            for f in glob.glob(os.path.join(FITBIT_GLOBAL_DIR, f"{prefix}_minutes-*.json")):
                try:
                    with open(f, 'r', encoding='utf-8') as jf:
                        for entry in json.load(jf):
                            dt = datetime.strptime(entry["dateTime"], "%m/%d/%y %H:%M:%S").strftime("%Y-%m-%d")
                            key = prefix.split('_')[0]
                            intensity_data[dt][key] += int(entry["value"])
                except: pass
        for dt, v in intensity_data.items():
            cursor.execute('''
                INSERT INTO activity_intensity (date, sedentary_min, lightly_active_min, moderately_active_min, very_active_min)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET sedentary_min=excluded.sedentary_min, lightly_active_min=excluded.lightly_active_min, moderately_active_min=excluded.moderately_active_min, very_active_min=excluded.very_active_min
            ''', (dt, v["sedentary"], v["lightly"], v["moderately"], v["very"]))

        print("🏆 Parsing Badges...")
        BADGE_PATH = os.path.join(FITBIT_GLOBAL_DIR, "badge.json")
        if os.path.exists(BADGE_PATH):
            try:
                with open(BADGE_PATH, 'r', encoding='utf-8') as jf:
                    for entry in json.load(jf):
                        cursor.execute('''
                            INSERT OR REPLACE INTO badges (badge_id, date, name, description, category, times_achieved)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (entry["encodedId"], entry["dateTime"], entry["name"], entry["description"], entry["category"], entry["timesAchieved"]))
            except: pass

        # --- ⚖️ Composition & Recovery ---
        print("⚖️ Parsing Weight Logs...")
        for f in glob.glob(os.path.join(FITBIT_GLOBAL_DIR, "weight-*.json")):
            try:
                with open(f, 'r', encoding='utf-8') as jf:
                    for entry in json.load(jf):
                        log_id = str(entry["logId"])
                        dt = datetime.strptime(entry["date"], "%m/%d/%y").strftime("%Y-%m-%d")
                        cursor.execute('''
                            INSERT INTO weight_logs (log_id, date, weight_lbs, fat_percent, bmi, source)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(log_id) DO UPDATE SET weight_lbs=excluded.weight_lbs, fat_percent=excluded.fat_percent, bmi=excluded.bmi
                        ''', (log_id, dt, entry.get("weight"), entry.get("fat"), entry.get("bmi"), "Fitbit"))
            except: pass

    if os.path.exists(HC_DB_PATH):
        print("⚖️ Parsing Health Connect (Weight & HRV)...")
        try:
            hc_conn = sqlite3.connect(HC_DB_PATH)
            hc_cur = hc_conn.cursor()
            hc_cur.execute("SELECT uuid, time, weight FROM weight_record_table")
            for row in hc_cur.fetchall():
                uid, ts, w_g = row
                dt = datetime.fromtimestamp(ts / 1000.0).strftime("%Y-%m-%d")
                w_lb = round((w_g / 1000.0) * 2.20462, 1)
                cursor.execute("INSERT INTO weight_logs (log_id, date, weight_lbs, source) VALUES (?, ?, ?, ?) ON CONFLICT(log_id) DO NOTHING", (f"hc_{uid.hex() if isinstance(uid, bytes) else uid}", dt, w_lb, "HealthConnect"))
            hc_cur.execute("SELECT time, percentage FROM body_fat_record_table")
            for row in hc_cur.fetchall():
                ts, fat = row
                dt = datetime.fromtimestamp(ts / 1000.0).strftime("%Y-%m-%d")
                cursor.execute("UPDATE weight_logs SET fat_percent = ? WHERE date = ? AND source = 'HealthConnect'", (round(fat, 1), dt))
            hc_cur.execute("SELECT uuid, time, heart_rate_variability_millis FROM heart_rate_variability_rmssd_record_table")
            for row in hc_cur.fetchall():
                uid, ts, hrv = row
                dt = datetime.fromtimestamp(ts / 1000.0).strftime("%Y-%m-%d")
                cursor.execute("INSERT INTO physiological_vitals (log_id, date, hrv_rmssd, source) VALUES (?, ?, ?, ?) ON CONFLICT(log_id) DO NOTHING", (f"hc_{uid.hex() if isinstance(uid, bytes) else uid}", dt, round(hrv, 2), "HealthConnect"))
            hc_conn.close()
        except: pass

    # --- ⚔️ Combat Logs ---
    if os.path.exists(FITBIT_GLOBAL_DIR):
        print("⚔️ Parsing Exercise Logs...")
        for f in glob.glob(os.path.join(FITBIT_GLOBAL_DIR, "exercise-*.json")):
            try:
                with open(f, 'r', encoding='utf-8') as jf:
                    for entry in json.load(jf):
                        log_id = entry["logId"]
                        dt_str = entry.get("startTime")
                        if not dt_str: continue
                        dt = datetime.strptime(dt_str, "%m/%d/%y %H:%M:%S").strftime("%Y-%m-%d")
                        cursor.execute('''
                            INSERT INTO exercise_logs (log_id, date, activity_name, duration_minutes, calories, distance, avg_hr, steps)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(log_id) DO NOTHING
                        ''', (log_id, dt, entry.get("activityName"), entry.get("duration", 0)//60000, entry.get("calories", 0), entry.get("distance", 0.0), entry.get("averageHeartRate", 0), entry.get("steps", 0)))
            except: pass

    # --- Final Commit ---
    print("💾 Committing Daily Vitals Summary...")
    for dt, m in daily_data.items():
        eff = m["sleep_eff_sum"] // m["sleep_count"] if m["sleep_count"] > 0 else 0

        # Priority: hr_sum (Legacy parsing) > avg_hr (API rollup)
        avg_hr = m["avg_hr"]
        if m["hr_count"] > 0:
            avg_hr = round(m["hr_sum"] / m["hr_count"])

        cursor.execute('''
            INSERT INTO daily_vitals (date, steps, calories, sleep_minutes, sleep_efficiency, avg_hr, min_hr, max_hr, stress_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(date) DO UPDATE SET steps=excluded.steps, calories=excluded.calories, sleep_minutes=excluded.sleep_minutes, sleep_efficiency=excluded.sleep_efficiency, avg_hr=excluded.avg_hr, min_hr=excluded.min_hr, max_hr=excluded.max_hr, stress_score=excluded.stress_score
        ''', (dt, m["steps"], m["calories"], m["sleep_min"], eff, avg_hr, m["hr_min"] if m["hr_min"] != 999 else 0, m["hr_max"], m["stress"]))

    conn.commit()
    conn.close()
    print("🚀 Deploying Unified Vitals Vault...")
    shutil.copy2(LOCAL_DB_PATH, FINAL_DB_PATH)
    print(f"✅ Master Vitals Database successfully forged at: {FINAL_DB_PATH}")

def main(argv=None):
    parser = argparse.ArgumentParser(description="Synchronize local biometrics data.")
    parser.add_argument(
        "--reauthorize-only",
        action="store_true",
        help="Authorize Google Health access and save credentials without importing data.",
    )
    args = parser.parse_args(argv)
    if args.reauthorize_only:
        return 0 if reauthorize_only() else 1
    return import_data()


if __name__ == "__main__":
    raise SystemExit(main())
