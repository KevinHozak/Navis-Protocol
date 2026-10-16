import os
import re
import sys
import argparse
import json

# Ensure backend path is in sys.path so we can import services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.progression_db import add_achievement
from services import xp_reconciliation

NAVIS_ROOT = os.getenv("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")
ACHIEVEMENTS_MD = os.path.join(NAVIS_ROOT, "Keeper", "Achievements.md")


def migrate_xp(root=None, manifest=None, apply=False, backup_dir=None, allow_configured_vault=False):
    if not apply:
        return xp_reconciliation.dry_run(root, manifest)
    return xp_reconciliation.apply_migration(root, manifest, backup_dir, allow_configured_vault)


def migrate_achievements():
    if not os.path.exists(ACHIEVEMENTS_MD):
        print(f"Achievements.md not found at {ACHIEVEMENTS_MD}")
        return

    # Regex to match: - **[CODE] Name:** Description (Date) or without date
    ach_pattern = re.compile(
        r"-\s*\*\*\[(.*?)\]\s*(.*?):\*\*\s*(.*?)(?:\s*\((\d{4}-\d{2}-\d{2})\))?$"
    )

    current_category = "Uncategorized"
    count = 0

    with open(ACHIEVEMENTS_MD, "r", encoding="utf-8-sig") as f:
        for line in f:
            if line.startswith("## "):
                current_category = line[3:].strip()
                continue

            match = ach_pattern.search(line)
            if match:
                code = match.group(1).strip()
                name = match.group(2).strip()
                description = match.group(3).strip()
                date = match.group(4) if match.group(4) else None

                add_achievement(code, name, description, date, current_category)
                count += 1

    print(f"Migrated {count} Achievements.")

    # Rename to .archive
    os.rename(ACHIEVEMENTS_MD, ACHIEVEMENTS_MD + ".archive")
    print("Renamed Achievements.md to Achievements.md.archive")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inventory and conservatively reconcile historical Navis XP.")
    parser.add_argument("--root", help="Vault root (defaults to NAVIS_ROOT)")
    parser.add_argument("--manifest", help="Reviewed JSON mapping manifest; without --apply this only previews proposed changes")
    parser.add_argument("--apply", action="store_true", help="Apply reviewed mappings after creating and verifying backups")
    parser.add_argument("--backup-dir", help="New directory for verified pre-migration backups (required with --apply)")
    parser.add_argument("--allow-configured-vault", action="store_true", help="Permit --apply against the configured NAVIS_ROOT")
    parser.add_argument("--rollback", metavar="RUN_ID", help="Restore verified backups for a reconciliation run; stop app writers first")
    parser.add_argument("--report", help="Write the aggregate report to this local JSON file")
    parser.add_argument("--achievements", action="store_true", help="Run the separate legacy achievement migration")
    args = parser.parse_args()
    if args.rollback:
        result = xp_reconciliation.rollback_migration(args.root, args.rollback)
    else:
        result = migrate_xp(args.root, args.manifest, args.apply, args.backup_dir, args.allow_configured_vault)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.report and not args.apply and not args.rollback:
        report_path = os.path.abspath(args.report)
        vault_path = os.path.abspath(args.root or NAVIS_ROOT)
        try:
            report_is_in_vault = os.path.commonpath([report_path, vault_path]) == vault_path
        except ValueError:
            report_is_in_vault = False
        if report_is_in_vault:
            parser.error("--report must be outside the Vault root so dry run remains non-mutating")
        with open(args.report, "w", encoding="utf-8") as report_file:
            report_file.write(rendered + "\n")
    if args.achievements:
        migrate_achievements()
    print(rendered)
