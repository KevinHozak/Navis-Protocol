"""Journal evidence -> canonical XP awards; JSON/Markdown are projections only."""

import json
import os
import re
from datetime import datetime, timezone

NAVIS_ROOT = os.environ.get("NAVIS_ROOT", r"G:\My Drive\Navis-Vault")


def combat_bonus_event(resolution_id, source, tactical):
    """Snapshot a Keeper bonus alongside the durable round before task writes.

    The normal checked-task award is 2 XP. Only its bonus portion is added;
    daily and companion awards are unchanged. Multiple critical cards do not stack.
    """
    multiplier = tactical["xp_multiplier"]
    if multiplier <= 1:
        return None
    from math import floor
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    date = os.path.basename(source["path"]).removesuffix(".md")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        with open(os.path.join(NAVIS_ROOT, "Bridge", "status.json"), encoding="utf-8-sig") as stream:
            date = json.load(stream)["last_updated"]
    return {"award_id": f"combat:{resolution_id}:keeper:critical", "entity_id": "keeper",
            "amount": floor(2 * (multiplier - 1)), "source_type": "combat_critical",
            "source_ref": resolution_id, "source_event_at": now, "local_date": date,
            "rule_version": "combat-elements-v1",
            "provenance": {"source": source, "base_task_xp": 2, "multiplier": multiplier,
                           "critical_hits": tactical["critical_hits"]},
            "details": f"Critical strike: checked-task XP x{multiplier}"}


def apply_combat_bonus(event):
    from services.progression_db import record_award
    return record_award(event)


def combat_talent_bonus_events(resolution_id, source, tactical, root=None):
    """Snapshot distinct talent perk bonus XP awards alongside combat resolution."""
    talent_perks = tactical.get("talent_perks")
    vault_root = root or NAVIS_ROOT
    if talent_perks is None:
        try:
            from services.talent_service import get_active_perks
            talent_perks = get_active_perks("keeper", root=vault_root)
        except Exception:
            talent_perks = {}

    from math import floor
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    date = os.path.basename(source["path"]).removesuffix(".md")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        bridge_status = os.path.join(vault_root, "Bridge", "status.json")
        if os.path.isfile(bridge_status):
            with open(bridge_status, encoding="utf-8-sig") as stream:
                date = json.load(stream).get("last_updated", date)

    events = []
    # High-Velocity Striker combat operation XP bonus
    hv_rank = talent_perks.get("high_velocity_xp_bonus", 0)
    if hv_rank > 0:
        from services.talent_service import calculate_perk_multiplier
        multiplier = calculate_perk_multiplier("high_velocity_xp_bonus", hv_rank)
        base_xp = 2
        amount = max(1, floor(base_xp * multiplier))
        events.append({
            "award_id": f"combat:{resolution_id}:keeper:talent:high_velocity_xp_bonus",
            "entity_id": "keeper",
            "amount": amount,
            "source_type": "talent_perk",
            "source_ref": resolution_id,
            "source_event_at": now,
            "local_date": date,
            "rule_version": "talents-v1",
            "reason": "talent_perk:high_velocity_xp_bonus",
            "provenance": {
                "source": source,
                "perk_key": "high_velocity_xp_bonus",
                "rank": hv_rank,
                "multiplier": multiplier,
                "base_task_xp": base_xp,
                "resolution_id": resolution_id,
            },
            "details": f"Combat operation perk bonus: +{amount} XP (Rank {hv_rank})",
        })

    return events


def calculate_and_apply_xp(date_override=None, root=None, journal_content=None):
    vault_root = root or NAVIS_ROOT
    status_path = os.path.join(vault_root, "Bridge", "status.json")
    stats_path = os.path.join(vault_root, "Bridge", "CompanionStats.json")
    if not os.path.isfile(status_path):
        raise FileNotFoundError(f"status.json unavailable at {status_path}; no XP was awarded")
    if not os.path.isfile(stats_path):
        raise FileNotFoundError(f"CompanionStats.json unavailable at {stats_path}; no XP was awarded")
    with open(status_path, "r", encoding="utf-8-sig") as stream:
        status = json.load(stream)
    date_str = date_override or status.get("last_updated")
    if not date_str:
        raise ValueError("Navis local award date is unavailable; no XP was awarded")
    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    journal_path = os.path.join(vault_root, "Journal", date.strftime("%Y"), date.strftime("%m"), f"{date_str}.md")
    if journal_content is not None:
        lines = journal_content.splitlines(keepends=True)
    else:
        if not os.path.isfile(journal_path):
            raise FileNotFoundError(f"journal evidence unavailable at {journal_path}; no XP was awarded")
        with open(journal_path, "r", encoding="utf-8-sig") as stream:
            lines = stream.readlines()

    from services.holocron_engine import resolve_manor, DEFAULT_MANOR
    manor_completed = {}
    current_manor = DEFAULT_MANOR
    completed = []
    for line in lines:
        sline = line.strip()
        if sline.startswith("## "):
            current_manor = resolve_manor(sline)
            continue
        if re.match(r"^[-*+]\s+\[[xX]\](?=\s|$)", sline):
            completed.append(sline)
            m_id = current_manor["id"]
            manor_completed[m_id] = manor_completed.get(m_id, 0) + 1
    task_xp = len(completed) * 2

    squad = status.get("squad")
    if not isinstance(squad, list):
        raise ValueError("active squad data is unavailable; no XP was awarded")
    members = []
    for member in squad:
        name = member.get("name") if isinstance(member, dict) else None
        if name and name != "Keeper" and name not in members:
            members.append(name)
    names = ["Keeper", *members]
    event_at = datetime.fromtimestamp(
        os.path.getmtime(journal_path) if os.path.isfile(journal_path) else datetime.now(timezone.utc).timestamp(), tz=timezone.utc
    ).isoformat(timespec="seconds")
    source_ref = f"Journal/{date.strftime('%Y/%m/%d')}.md#daily-xp"

    # Preserve the original award-time cohort and fixed daily/native portion on
    # replay. Only checked-task evidence can change its earned amount later.
    from services.progression_db import get_source_states, apply_source_batch
    states = get_source_states("journal_daily", source_ref)
    if states:
        # Historical awards keep their original recipients if the live squad changes.
        names = ["Keeper", *sorted(key.removeprefix("companion:") for key in states if key.startswith("companion:"))]
    realm = status.get("current_realm", "Unknown")
    events = []
    for name in names:
        entity_id = "keeper" if name == "Keeper" else f"companion:{name}"
        previous = states.get(entity_id)
        if previous:
            old_task_count = int(previous["provenance"].get("task_count", 0))
            baseline = previous["amount"] - old_task_count * 2
        else:
            profile = os.path.join(vault_root, "Companions", name, "Profile.md")
            native_bonus = 0
            if name != "Keeper" and os.path.isfile(profile):
                with open(profile, "r", encoding="utf-8-sig") as stream:
                    profile_text = stream.read()
                match = re.search(r"Status:.*?(?:🗼|\])\s*(.*)", profile_text, re.IGNORECASE)
                if match and realm.upper() in match.group(1).upper():
                    native_bonus = 5
            baseline = 10 + native_bonus
        amount = baseline + task_xp
        events.append({
            "award_id": f"journal:{date_str}:{entity_id}:daily",
            "entity_id": entity_id,
            "amount": amount,
            "source_type": "journal_daily",
            "source_ref": source_ref,
            "source_event_at": event_at,
            "local_date": date_str,
            "rule_version": "xp-v1",
            "provenance": {"journal_path": f"Journal/{date.strftime('%Y/%m/%d')}.md", "task_count": len(completed), "task_xp": task_xp, "daily_base": 10, "native_bonus": baseline - 10, "award_cohort": names},
            "details": f"Daily 10, checked tasks {task_xp}, native {baseline - 10}",
        })
    applied = apply_source_batch(events)

    # Dynamic active talent perk evaluation for Keeper
    talent_awards_applied = []
    try:
        from services.talent_service import get_active_perks, evaluate_task_perk_awards
        active_perks = get_active_perks("keeper", root=vault_root)
        perk_specs = evaluate_task_perk_awards(manor_completed, active_perks)
        for spec in perk_specs:
            perk_key = spec["perk_key"]
            amount = spec["amount"]
            perk_event = {
                "award_id": f"journal:{date_str}:keeper:talent:{perk_key}",
                "entity_id": "keeper",
                "amount": amount,
                "source_type": "talent_perk",
                "source_ref": f"{source_ref}#talent-{perk_key}",
                "source_event_at": event_at,
                "local_date": date_str,
                "rule_version": "talents-v1",
                "reason": f"talent_perk:{perk_key}",
                "provenance": {
                    "journal_path": f"Journal/{date.strftime('%Y/%m/%d')}.md",
                    "perk_key": perk_key,
                    "rank": spec["rank"],
                    "multiplier": spec["multiplier"],
                    "manor": spec["manor"],
                    "tasks_count": spec["tasks_count"],
                },
                "details": spec["details"],
            }
            applied_perks = apply_source_batch([perk_event])
            if applied_perks:
                talent_awards_applied.append(perk_key)
    except Exception:
        pass

    return {
        "status": "success",
        "date": date_str,
        "task_count": len(completed),
        "entities_updated": applied,
        "talent_perks_awarded": talent_awards_applied,
    }


if __name__ == "__main__":
    print(calculate_and_apply_xp())
