import sys
from pathlib import Path

# Setup environment
backend_path = str(Path(__file__).resolve().parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

# Verify the imports work
try:
    from services.sync_engine import execute_git_backup

    print("✅ All services imported successfully.")

    # Test Backup execution natively
    print("Running backup test...")
    res = execute_git_backup()
    print(res)

except Exception as e:
    print(f"❌ Verification failed: {e}")
