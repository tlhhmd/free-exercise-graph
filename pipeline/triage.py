"""
pipeline/triage.py

Interactive CLI triage queue for possible_matches.

Shows each open pair side by side with name, source, equipment, and muscles.
Records a decision for each pair; merge decisions are applied immediately.

Decisions:
  m   merge  — entity_a absorbs entity_b (b's source records reassigned, b deleted)
  s   sep    — confirmed separate exercises (different movement)
  v   var    — variant_of  (same movement, different equipment/context; kept as peers)
  ?   skip   — defer to next session
  q   quit   — exit (progress is saved)

After merges, re-run pipeline/reconcile.py to regenerate resolved_claims.

Usage:
    python3 pipeline/triage.py
    python3 pipeline/triage.py --pending   # count open pairs, no interaction
"""

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.db import DB_PATH, get_connection


# ─── Display helpers ─────────────────────────────────────────────────────────


def _entity_info(conn, entity_id: str) -> dict:
    """Return display data for one entity."""
    row = conn.execute(
        "SELECT display_name FROM entities WHERE entity_id = ?", (entity_id,)
    ).fetchone()
    display_name = row["display_name"] if row else entity_id

    # Source(s)
    sources = conn.execute(
        "SELECT source FROM entity_sources WHERE entity_id = ?", (entity_id,)
    ).fetchall()
    source_labels = [r["source"].replace("functional-fitness-db", "ffdb")
                                .replace("free-exercise-db", "fed")
                     for r in sources]

    # Resolved claims
    claims = conn.execute(
        "SELECT predicate, value FROM resolved_claims WHERE entity_id = ? ORDER BY predicate, value",
        (entity_id,),
    ).fetchall()

    equipment = [r["value"] for r in claims if r["predicate"] == "equipment"]
    muscles   = [r["value"] for r in claims if r["predicate"] == "muscle"]
    patterns  = [r["value"] for r in claims if r["predicate"] == "movement_pattern"]
    laterality = next((r["value"] for r in claims if r["predicate"] == "laterality"), "—")

    return {
        "entity_id":  entity_id,
        "name":       display_name,
        "sources":    source_labels,
        "equipment":  equipment or ["—"],
        "muscles":    muscles or ["—"],
        "patterns":   patterns or ["—"],
        "laterality": laterality,
    }


def _fmt(items: list, max_items: int = 4) -> str:
    shown = items[:max_items]
    suffix = f" +{len(items) - max_items}" if len(items) > max_items else ""
    return ", ".join(shown) + suffix


def _show_pair(idx: int, total: int, pair: dict, info_a: dict, info_b: dict) -> None:
    score = pair["score"]
    w = 40

    print()
    print(f"─── Pair {idx}/{total}  score={score:.2f} " + "─" * 30)
    print(f"  {'A':3} {info_a['name']:<{w}}  B  {info_b['name']}")
    print(f"  {'':3} [{', '.join(info_a['sources'])}]{' '*(w - len(', '.join(info_a['sources'])) - 2)}     [{', '.join(info_b['sources'])}]")
    print()
    print(f"  {'Equipment':<12} A: {_fmt(info_a['equipment']):<{w}}  B: {_fmt(info_b['equipment'])}")
    print(f"  {'Muscles':<12} A: {_fmt(info_a['muscles']):<{w}}  B: {_fmt(info_b['muscles'])}")
    print(f"  {'Patterns':<12} A: {_fmt(info_a['patterns']):<{w}}  B: {_fmt(info_b['patterns'])}")
    print(f"  {'Laterality':<12} A: {info_a['laterality']:<{w}}  B: {info_b['laterality']}")
    print()


# ─── Decision application ─────────────────────────────────────────────────────


def _apply_merge(conn, entity_id_a: str, entity_id_b: str) -> None:
    """Absorb entity_b into entity_a.

    - Reassign entity_b's entity_sources rows to entity_a (skip if already present).
    - Delete entity_b's resolved_claims (reconcile.py will regenerate from source_claims).
    - Delete entity_b from entities.
    """
    with conn:
        # Reassign entity_sources for entity_b → entity_a
        b_sources = conn.execute(
            "SELECT source, source_id, confidence FROM entity_sources WHERE entity_id = ?",
            (entity_id_b,),
        ).fetchall()
        existing_a = {
            (r["source"], r["source_id"])
            for r in conn.execute(
                "SELECT source, source_id FROM entity_sources WHERE entity_id = ?",
                (entity_id_a,),
            ).fetchall()
        }
        for r in b_sources:
            if (r["source"], r["source_id"]) not in existing_a:
                conn.execute(
                    "UPDATE entity_sources SET entity_id = ? WHERE entity_id = ? AND source = ? AND source_id = ?",
                    (entity_id_a, entity_id_b, r["source"], r["source_id"]),
                )
            else:
                conn.execute(
                    "DELETE FROM entity_sources WHERE entity_id = ? AND source = ? AND source_id = ?",
                    (entity_id_b, r["source"], r["source_id"]),
                )

        # Remove entity_b's resolved_claims (reconcile regenerates them)
        conn.execute("DELETE FROM resolved_claims WHERE entity_id = ?", (entity_id_b,))
        conn.execute("DELETE FROM inferred_claims WHERE entity_id = ?", (entity_id_b,))
        conn.execute("DELETE FROM enrichment_stamps WHERE entity_id = ?", (entity_id_b,))
        conn.execute("DELETE FROM conflicts WHERE entity_id = ?", (entity_id_b,))

        # Delete entity_b
        conn.execute("DELETE FROM entities WHERE entity_id = ?", (entity_id_b,))


def _apply_decision(conn, pair_id: int, entity_id_a: str, entity_id_b: str, decision: str) -> None:
    if decision == "m":
        _apply_merge(conn, entity_id_a, entity_id_b)
        status = "merged"
    elif decision == "s":
        status = "separate"
    elif decision == "v":
        status = "variant_of"
    else:
        return  # skip

    with conn:
        conn.execute(
            "UPDATE possible_matches SET status = ? WHERE id = ?",
            (status, pair_id),
        )


# ─── Main loop ───────────────────────────────────────────────────────────────


def triage(conn) -> None:
    pairs = conn.execute(
        """
        SELECT pm.id, pm.entity_id_a, pm.entity_id_b, pm.score
        FROM possible_matches pm
        WHERE pm.status = 'open'
        ORDER BY pm.score DESC, pm.id
        """
    ).fetchall()

    total = len(pairs)
    if total == 0:
        print("No open pairs in triage queue.")
        return

    print(f"\n{total} open pair(s) in triage queue.")
    print("Decisions: m=merge  s=separate  v=variant_of  ?=skip  q=quit\n")

    merges = 0
    for idx, pair in enumerate(pairs, 1):
        # Re-check status — a previous merge may have deleted one of these entities
        still_open = conn.execute(
            "SELECT status FROM possible_matches WHERE id = ?", (pair["id"],)
        ).fetchone()
        if not still_open or still_open["status"] != "open":
            continue

        # Check both entities still exist
        ea_exists = conn.execute("SELECT 1 FROM entities WHERE entity_id = ?", (pair["entity_id_a"],)).fetchone()
        eb_exists = conn.execute("SELECT 1 FROM entities WHERE entity_id = ?", (pair["entity_id_b"],)).fetchone()
        if not ea_exists or not eb_exists:
            # One side was merged away — mark as resolved
            with conn:
                conn.execute("UPDATE possible_matches SET status = 'merged' WHERE id = ?", (pair["id"],))
            continue

        info_a = _entity_info(conn, pair["entity_id_a"])
        info_b = _entity_info(conn, pair["entity_id_b"])
        _show_pair(idx, total, pair, info_a, info_b)

        while True:
            try:
                raw = input("  Decision [m/s/v/?/q]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nInterrupted — progress saved.")
                if merges:
                    print(f"\n{merges} merge(s) applied. Re-run pipeline/reconcile.py.")
                return

            if raw in ("m", "s", "v", "?"):
                _apply_decision(conn, pair["id"], pair["entity_id_a"], pair["entity_id_b"], raw)
                if raw == "m":
                    merges += 1
                    print(f"  → merged: {pair['entity_id_b']} absorbed into {pair['entity_id_a']}")
                break
            elif raw == "q":
                print("Quit — progress saved.")
                if merges:
                    print(f"\n{merges} merge(s) applied. Re-run pipeline/reconcile.py.")
                return
            else:
                print("  Enter m, s, v, ?, or q.")

    remaining = conn.execute(
        "SELECT COUNT(*) FROM possible_matches WHERE status = 'open'"
    ).fetchone()[0]
    print(f"\nDone. {remaining} pair(s) still open.")
    if merges:
        print(f"{merges} merge(s) applied. Re-run pipeline/reconcile.py to regenerate resolved_claims.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive triage queue for near-duplicate exercise pairs.")
    parser.add_argument("--pending", action="store_true", help="Print count of open pairs and exit")
    args = parser.parse_args()

    conn = get_connection(DB_PATH)

    if args.pending:
        n = conn.execute("SELECT COUNT(*) FROM possible_matches WHERE status = 'open'").fetchone()[0]
        print(f"{n} open pair(s) in triage queue.")
        conn.close()
        return

    triage(conn)
    conn.close()


if __name__ == "__main__":
    main()
