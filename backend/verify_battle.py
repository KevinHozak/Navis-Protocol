import sys
from pathlib import Path

backend_path = str(Path(__file__).resolve().parent)
if backend_path not in sys.path:
    sys.path.append(backend_path)

from services.battle_engine import get_engine

try:
    engine = get_engine()
    state = engine.get_full_state()
    print("✅ Battle Engine initialized.")
    print(f"Hand size: {len(state['hand'])}")
    print(f"Discard size: {len(state['discard'])}")
    print(f"Active links: {len(state['active_links'])}")
except Exception as e:
    print(f"❌ Error: {e}")
