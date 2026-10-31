import pystray
from PIL import Image, ImageDraw
import subprocess
import os


def create_image(width, height, color1, color2):
    # Generate a simple abstract placeholder icon
    image = Image.new("RGB", (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 4, height // 4, width * 3 // 4, height * 3 // 4), fill=color2
    )
    return image


# Setup paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

# Launch processes
backend_env = os.environ.copy()
backend_env["NAVIS_ROOT"] = "G:\\My Drive\\Navis-Vault"
backend_exe = os.path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe")

# Using CREATE_NO_WINDOW so the console windows do not appear
CREATE_NO_WINDOW = 0x08000000

# Kill old processes before startup to prevent port collisions
subprocess.run(
    [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "Get-NetTCPConnection -LocalPort 8000, 3000 -ErrorAction SilentlyContinue | ForEach-Object { if ($_.OwningProcess -gt 0) { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }",
    ],
    creationflags=CREATE_NO_WINDOW,
)

import time

time.sleep(1.5)

backend_proc = subprocess.Popen(
    [backend_exe, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=BACKEND_DIR,
    env=backend_env,
    creationflags=CREATE_NO_WINDOW,
)

# Start npm hidden
frontend_proc = subprocess.Popen(
    ["cmd.exe", "/c", "npm", "run", "dev"],
    cwd=FRONTEND_DIR,
    creationflags=CREATE_NO_WINDOW,
)



def launch_portal(icon, item):
    subprocess.Popen(
        ["cmd.exe", "/c", "start", "chrome", "--app=http://localhost:3000"],
        creationflags=CREATE_NO_WINDOW,
    )


def restart_backend(icon, item):
    global backend_proc
    try:
        backend_proc.terminate()
        backend_proc.wait(timeout=3)
    except:
        pass

    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { if ($_.OwningProcess -gt 0) { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }",
        ],
        creationflags=CREATE_NO_WINDOW,
    )

    backend_proc = subprocess.Popen(
        [
            backend_exe,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=BACKEND_DIR,
        env=backend_env,
        creationflags=CREATE_NO_WINDOW,
    )


def exit_action(icon, item):
    icon.stop()
    # Terminate child processes
    try:
        backend_proc.terminate()
    except:
        pass

    try:
        # Since npm run dev spawns child node processes, we should kill by port or process tree
        # For simplicity, terminating the cmd process and invoking Stop_Navis.bat logic
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "Get-NetTCPConnection -LocalPort 8000, 3000 -ErrorAction SilentlyContinue | ForEach-Object { if ($_.OwningProcess -gt 0) { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }",
            ],
            creationflags=CREATE_NO_WINDOW,
        )
    except:
        pass


# Attempt to load custom icon, otherwise generate one
icon_path = os.path.join(FRONTEND_DIR, "public", "icon.png")
if os.path.exists(icon_path):
    try:
        image = Image.open(icon_path)
    except:
        image = create_image(64, 64, "black", "white")
else:
    image = create_image(64, 64, "black", "white")

menu = pystray.Menu(
    pystray.MenuItem("🚀 Launch Navis Portal", launch_portal, default=True),
    pystray.MenuItem("🔄 Restart Backend", restart_backend),
    pystray.MenuItem("🛑 Shutdown Navis", exit_action),
)

icon = pystray.Icon("Navis-Protocol", image, "Navis Bridge", menu)

# Blocking call to run the system tray
icon.run()
