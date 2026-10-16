"""Print a no-network plan or explicitly run a bounded synthetic benchmark."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.ai_benchmark import plan, run
from services.online_ai import OnlineAIError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run-local", action="store_true", help="Run only the local baseline")
    mode.add_argument("--enable-online", action="store_true", help="Explicitly enable this paid synthetic experiment plus local baseline")
    parser.add_argument("--repeats", type=int, default=2, choices=(2, 3))
    parser.add_argument("--experiment-limit-usd", type=float, default=0.05)
    parser.add_argument("--output", type=Path, help="JSON report outside the Vault; required for execution")
    args = parser.parse_args()
    try:
        if not args.run_local and not args.enable_online:
            print(json.dumps(plan(args.repeats, args.experiment_limit_usd), indent=2))
            return 0
        if not args.output:
            raise OnlineAIError("Execution requires --output for a recoverable report.")
        target = args.output.resolve()
        vault = Path(os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")).resolve()
        if target == vault or vault in target.parents:
            raise OnlineAIError("Benchmark reports must be saved outside the Vault.")
        target.parent.mkdir(parents=True, exist_ok=True)

        def checkpoint(report):
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            temporary.replace(target)

        report = asyncio.run(run(enable_online=args.enable_online, repeats=args.repeats,
                                 experiment_limit=args.experiment_limit_usd, checkpoint=checkpoint))
        print(json.dumps({"status": report["status"], "report": str(target), "proposal": report["proposal"]}, indent=2))
        return 0 if report["status"] == "complete" else 1
    except OnlineAIError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Benchmark interrupted; inspect the checkpoint and retained ledger reservations before rerunning.", file=sys.stderr)
        return 130
    except Exception:
        print("Benchmark failed; inspect saved metadata and ledger reservations. Provider details suppressed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
