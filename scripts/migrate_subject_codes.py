"""Regenerate join codes for EXISTING subjects using the secrets-based scheme.

The random-code generation in POST /api/subjects only affects subjects created
after that change; rows already in the DB keep their old guessable codes
(e.g. "CS101"). This migration rewrites every existing subject_code to a fresh
8-char code, guaranteeing uniqueness within the run.

Reusable core: regenerate_all_codes(client, ...) takes any object exposing the
supabase-style .table().select()/.update().eq().execute() chain, so it can be
driven against the real DB or a fake in tests.

Run against the real DB:
    SUPABASE_URL=... SUPABASE_KEY=... python scripts/migrate_subject_codes.py
    # add --dry-run to preview the old -> new mapping without writing
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.subject_codes import generate_subject_code


def regenerate_all_codes(client, code_generator=generate_subject_code, dry_run=False):
    """Assign a fresh unique code to every subject.

    Returns a list of {subject_id, old_code, new_code}. When dry_run is True,
    the mapping is computed but no update is written.
    """
    subjects = client.table("subjects").select(
        "subject_id, subject_code, name, section, teacher_id"
    ).execute().data or []

    assigned: set[str] = set()
    mapping = []
    for sub in subjects:
        new_code = code_generator()
        while new_code in assigned:
            new_code = code_generator()
        assigned.add(new_code)

        mapping.append(
            {
                "subject_id": sub["subject_id"],
                "old_code": sub.get("subject_code"),
                "new_code": new_code,
            }
        )

        if not dry_run:
            client.table("subjects").update({"subject_code": new_code}).eq(
                "subject_id", sub["subject_id"]
            ).execute()

    return mapping


def main():
    parser = argparse.ArgumentParser(description="Regenerate subject join codes")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    from src.database.config import supabase

    mapping = regenerate_all_codes(supabase, dry_run=args.dry_run)

    mode = "DRY RUN (no writes)" if args.dry_run else "MIGRATED"
    print(f"== {mode}: {len(mapping)} subjects ==")
    for m in mapping:
        print(f"  subject_id={m['subject_id']}: {m['old_code']!r} -> {m['new_code']!r}")


if __name__ == "__main__":
    main()
