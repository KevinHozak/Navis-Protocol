"""Talent tree constellation and specialization ledger service."""

import json
from services import progression_db


def calculate_available_points(current_level: int, total_allocated_ranks: int) -> int:
    """Calculate available skill points: current Keeper level minus spent points."""
    return max(0, current_level - total_allocated_ranks)


def parse_prerequisites(raw_prereqs) -> list:
    """Parse JSON or comma-separated prerequisite specifications."""
    if isinstance(raw_prereqs, list):
        return raw_prereqs
    if isinstance(raw_prereqs, str):
        raw_str = raw_prereqs.strip()
        if raw_str.startswith("["):
            try:
                parsed = json.loads(raw_str)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return []
        return [p.strip() for p in raw_str.split(",") if p.strip()]
    return []


def _prereq_satisfied(prereq, alloc_map: dict) -> bool:
    if isinstance(prereq, str):
        return alloc_map.get(prereq, 0) >= 1
    if isinstance(prereq, dict):
        req_node = prereq.get("node_id")
        req_rank = prereq.get("min_rank", 1)
        return alloc_map.get(req_node, 0) >= req_rank
    return True


def get_talent_nodes(root=None) -> list:
    """Return all defined talent nodes ordered by branch, tier, and ID."""
    conn = progression_db.get_connection(root)
    try:
        rows = conn.execute(
            "SELECT id, branch, tier, prerequisites, max_rank, perk_key, name, description FROM talent_nodes ORDER BY branch ASC, tier ASC, id ASC"
        ).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            item["prerequisites"] = parse_prerequisites(item.get("prerequisites", "[]"))
            result.append(item)
        return result
    finally:
        conn.close()


def get_talent_state(entity_id: str = "keeper", root=None) -> dict:
    """Return comprehensive constellation state, points balance, and allocations for an entity."""
    if entity_id != "keeper" and not (entity_id.startswith("companion:") and entity_id.removeprefix("companion:").strip()):
        raise progression_db.ProgressionValidationError("entity_id must be keeper or companion:<stable-name>")

    conn = progression_db.get_connection(root)
    try:
        total_xp = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_ledger WHERE entity_id=?",
            (entity_id,)
        ).fetchone()[0]
        current_level = progression_db.level_for_total(total_xp)

        alloc_rows = conn.execute(
            "SELECT entity_id, node_id, rank, allocated_at FROM talent_allocations WHERE entity_id=? ORDER BY allocated_at ASC",
            (entity_id,)
        ).fetchall()
        allocations = [dict(r) for r in alloc_rows]
        alloc_map = {r["node_id"]: r["rank"] for r in allocations}
        total_allocated_ranks = sum(alloc_map.values())
        available_points = calculate_available_points(current_level, total_allocated_ranks)

        node_rows = conn.execute(
            "SELECT id, branch, tier, prerequisites, max_rank, perk_key, name, description FROM talent_nodes ORDER BY branch ASC, tier ASC, id ASC"
        ).fetchall()
        nodes = []
        for r in node_rows:
            node = dict(r)
            prereqs = parse_prerequisites(node.get("prerequisites", "[]"))
            node["prerequisites"] = prereqs
            node["current_rank"] = alloc_map.get(node["id"], 0)
            node["unlocked"] = all(_prereq_satisfied(p, alloc_map) for p in prereqs)
            nodes.append(node)

        return {
            "entity_id": entity_id,
            "level": current_level,
            "current_level": current_level,
            "total_xp": total_xp,
            "total_allocated_ranks": total_allocated_ranks,
            "available_points": available_points,
            "allocations": allocations,
            "nodes": nodes,
        }
    finally:
        conn.close()


def allocate_talent(entity_id: str = "keeper", node_id: str = "", rank: int | None = None, root=None) -> dict:
    """Atomically allocate talent points to a node, enforcing prerequisites and point limits."""
    if entity_id != "keeper" and not (entity_id.startswith("companion:") and entity_id.removeprefix("companion:").strip()):
        raise progression_db.ProgressionValidationError("entity_id must be keeper or companion:<stable-name>")
    if not str(node_id).strip():
        raise progression_db.ProgressionValidationError("node_id required")
    node_id = str(node_id).strip()

    conn = progression_db.get_connection(root)
    try:
        conn.execute("BEGIN IMMEDIATE")
        progression_db._assert_reconciliation_unlocked(conn)

        node_row = conn.execute(
            "SELECT id, branch, tier, prerequisites, max_rank, perk_key, name, description FROM talent_nodes WHERE id=?",
            (node_id,)
        ).fetchone()
        if not node_row:
            raise progression_db.ProgressionValidationError(f"Talent node '{node_id}' does not exist")

        node = dict(node_row)
        alloc_rows = conn.execute(
            "SELECT node_id, rank, allocated_at FROM talent_allocations WHERE entity_id=?",
            (entity_id,)
        ).fetchall()
        alloc_map = {r["node_id"]: r["rank"] for r in alloc_rows}
        alloc_date_map = {r["node_id"]: r["allocated_at"] for r in alloc_rows}

        current_rank = alloc_map.get(node_id, 0)
        if rank is None:
            target_rank = current_rank + 1
        else:
            if isinstance(rank, bool) or not isinstance(rank, int) or rank <= 0:
                raise progression_db.ProgressionValidationError("rank must be a positive integer")
            target_rank = rank

        total_allocated_ranks = sum(alloc_map.values())
        total_xp = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM xp_ledger WHERE entity_id=?",
            (entity_id,)
        ).fetchone()[0]
        current_level = progression_db.level_for_total(total_xp)
        available_points = calculate_available_points(current_level, total_allocated_ranks)

        # Idempotency check: already at requested rank
        if target_rank == current_rank:
            conn.rollback()
            return {
                "status": "success",
                "entity_id": entity_id,
                "node_id": node_id,
                "allocated_rank": current_rank,
                "ranks_added": 0,
                "available_points": available_points,
                "total_allocated_ranks": total_allocated_ranks,
                "current_level": current_level,
                "allocated_at": alloc_date_map.get(node_id, progression_db._now()),
            }

        if target_rank < current_rank:
            raise progression_db.ProgressionValidationError(f"Cannot decrease talent rank (current rank is {current_rank})")

        if target_rank > node["max_rank"]:
            raise progression_db.ProgressionValidationError(
                f"Requested rank {target_rank} exceeds max rank {node['max_rank']} for node '{node_id}'"
            )

        # Check prerequisites
        prereqs = parse_prerequisites(node.get("prerequisites", "[]"))
        for prereq in prereqs:
            if isinstance(prereq, str):
                req_node = prereq
                req_rank = 1
            elif isinstance(prereq, dict):
                req_node = prereq.get("node_id", "")
                req_rank = prereq.get("min_rank", 1)
            else:
                continue
            if alloc_map.get(req_node, 0) < req_rank:
                raise progression_db.ProgressionValidationError(f"Prerequisite node '{req_node}' is not unlocked")

        points_needed = target_rank - current_rank
        if available_points < points_needed:
            raise progression_db.ProgressionValidationError(
                f"Insufficient talent points: requires {points_needed}, but only {available_points} available"
            )

        now = progression_db._now()
        conn.execute(
            """INSERT INTO talent_allocations (entity_id, node_id, rank, allocated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(entity_id, node_id) DO UPDATE SET rank=excluded.rank, allocated_at=excluded.allocated_at""",
            (entity_id, node_id, target_rank, now),
        )
        conn.commit()

        new_total_allocated = total_allocated_ranks + points_needed
        new_available = available_points - points_needed
        return {
            "status": "success",
            "entity_id": entity_id,
            "node_id": node_id,
            "allocated_rank": target_rank,
            "ranks_added": points_needed,
            "available_points": new_available,
            "total_allocated_ranks": new_total_allocated,
            "current_level": current_level,
            "allocated_at": now,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_active_perks(entity_id: str = "keeper", root=None) -> dict:
    """Return dictionary of perk_key -> allocated rank for the entity."""
    if entity_id != "keeper" and not (entity_id.startswith("companion:") and entity_id.removeprefix("companion:").strip()):
        raise progression_db.ProgressionValidationError("entity_id must be keeper or companion:<stable-name>")

    conn = progression_db.get_connection(root)
    try:
        rows = conn.execute(
            """SELECT tn.perk_key, ta.rank
            FROM talent_allocations ta
            JOIN talent_nodes tn ON ta.node_id = tn.id
            WHERE ta.entity_id = ? AND ta.rank > 0""",
            (entity_id,)
        ).fetchall()
        return {r["perk_key"]: r["rank"] for r in rows}
    finally:
        conn.close()


PERK_DEFINITIONS = {
    "high_velocity_xp_bonus": {
        "manor": "HIGH_VELOCITY_FRONT",
        "rate_per_rank": 0.10,
        "max_multiplier": 0.50,
        "combat_xp_bonus_per_rank": 0.10,
        "max_combat_xp_bonus": 0.50,
        "type": "manor_xp_bonus",
    },
    "focus_deep_work_multiplier": {
        "manor": "SANCTUM",
        "rate_per_rank": 0.10,
        "max_multiplier": 0.50,
        "type": "manor_xp_bonus",
    },
    "kinetic_stamina_efficiency": {
        "manor": "KINETIC_OUTLAND",
        "rate_per_rank": 0.10,
        "max_multiplier": 0.50,
        "type": "manor_xp_bonus",
    },
    "library_harvest_bonus": {
        "manor": "BUREAUCRATIC_GAUNTLET",
        "rate_per_rank": 0.10,
        "max_multiplier": 0.50,
        "type": "manor_xp_bonus",
    },
    "daily_outland_surge": {
        "manor": "KINETIC_OUTLAND",
        "flat_bonus_per_rank": 2,
        "max_bonus": 5,
        "type": "flat_surge_bonus",
    },
    "reduced_rollover_penalty": {
        "shield_boost_per_rank": 10,
        "max_shield_boost": 30,
        "debuff_reduction_per_rank": 1,
        "max_debuff_reduction": 5,
        "type": "combat_mitigation",
    },
    "focus_stamina_boost": {
        "shield_boost_per_rank": 10,
        "max_shield_boost": 20,
        "type": "combat_stamina",
    },
    "neural_arbiter_synergy": {
        "telemetry_bonus_per_rank": 0.05,
        "max_telemetry_bonus": 0.25,
        "type": "telemetry_synergy",
    },
}


def calculate_perk_multiplier(perk_key: str, rank: int, additional_bonus: float = 0.0) -> float:
    """Calculate stacked perk multiplier enforcing non-negativity and boundary caps."""
    if rank <= 0:
        return 0.0
    config = PERK_DEFINITIONS.get(perk_key, {})
    rate = config.get("rate_per_rank", 0.0)
    max_cap = config.get("max_multiplier", 0.50)
    raw = rank * rate + additional_bonus
    return round(min(max_cap, max(0.0, raw)), 4)


def calculate_combat_perk_modifiers(active_perks: dict) -> dict:
    """Calculate combat modifiers with stacking and boundary caps from active perks."""
    shield_boost_rrp = active_perks.get("reduced_rollover_penalty", 0) * 10
    shield_boost_fsb = active_perks.get("focus_stamina_boost", 0) * 10
    total_shield_boost = min(50, max(0, shield_boost_rrp + shield_boost_fsb))

    debuff_reduction = min(5, max(0, active_perks.get("reduced_rollover_penalty", 0) * 1))

    combat_xp_bonus = min(0.50, max(0.0, active_perks.get("high_velocity_xp_bonus", 0) * 0.10))

    return {
        "shield_percent_bonus": total_shield_boost,
        "debuff_reduction": debuff_reduction,
        "combat_xp_bonus": combat_xp_bonus,
    }


def evaluate_task_perk_awards(manor_counts: dict, active_perks: dict) -> list:
    """Dynamically evaluate active perks against manor task completions and return bonus award specs."""
    import math

    awards = []
    for perk_key, rank in active_perks.items():
        if rank <= 0 or perk_key not in PERK_DEFINITIONS:
            continue
        config = PERK_DEFINITIONS[perk_key]
        perk_type = config.get("type")
        target_manor = config.get("manor")
        task_count = manor_counts.get(target_manor, 0)

        if task_count <= 0:
            continue

        if perk_type == "manor_xp_bonus":
            multiplier = calculate_perk_multiplier(perk_key, rank)
            base_xp = task_count * 2
            bonus_amount = math.floor(base_xp * multiplier)
            if bonus_amount > 0:
                awards.append({
                    "perk_key": perk_key,
                    "amount": bonus_amount,
                    "reason": f"talent_perk:{perk_key}",
                    "multiplier": multiplier,
                    "rank": rank,
                    "manor": target_manor,
                    "tasks_count": task_count,
                    "details": f"Talent perk {perk_key} (+{int(multiplier * 100)}%): +{bonus_amount} XP",
                })
        elif perk_type == "flat_surge_bonus":
            max_bonus = config.get("max_bonus", 5)
            flat_rate = config.get("flat_bonus_per_rank", 2)
            surge_amount = min(max_bonus, max(0, rank * flat_rate))
            if surge_amount > 0:
                awards.append({
                    "perk_key": perk_key,
                    "amount": surge_amount,
                    "reason": f"talent_perk:{perk_key}",
                    "multiplier": 1.0,
                    "rank": rank,
                    "manor": target_manor,
                    "tasks_count": task_count,
                    "details": f"Talent perk {perk_key} expedition surge: +{surge_amount} XP",
                })

    return awards

