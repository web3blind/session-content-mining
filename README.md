# Session Content Mining (public skill)

A Hermes/agent skill for mining a period's conversation sessions for post or content ideas without confusing a keyword search with a complete review. It bundles a read-only SQLite inventory script that enumerates every in-period message by **message timestamp** (not session start), so archived, short, untitled, cron and tool-only sessions cannot silently drop out. Python 3.10+; standard library only.

The skill text carries the full workflow: scope resolution, the inventory-first rule, one-launch full passes, read/extract/resume, checkpoints, and the editorial pass. `references/coverage.md` is the coverage-and-resume contract for the manifest and progress ledger; `references/large-corpus.md` is for multi-gigabyte `state.db` files (bounded keyset reads, deduplication, privacy scrubbing, ledger resume).

## Install

Copy this directory into your agent's skills folder. The skill assumes a Hermes-style session database (`state.db` with `sessions` and `messages` tables, `timestamp` stored as Unix epoch). If your agent stores sessions differently, use the same workflow with your own read-only enumeration step.

## Example

```bash
python3 scripts/inventory.py \
  --db /path/to/profile/state.db \
  --profile default \
  --start 2026-07-01 \
  --end-exclusive 2026-08-10 \
  --timezone Europe/Moscow \
  --out /path/to/run/manifest-default.json
```

`--start` is inclusive and `--end-exclusive` is exclusive, in `--timezone` (IANA name; naive ISO values are interpreted in that zone). The script opens the database in read-only mode (`mode=ro` plus `PRAGMA query_only=ON`), pins the max message ID in one read transaction, and writes a manifest of exact message IDs, roles and timestamps per session. It never overwrites an existing manifest, never writes to the database, and exports no transcript text. `inventory_only: true` and `review_status: pending` in the manifest are deliberate: enumeration is not review.

`unplaced_timestamp_rows` reports rows with missing or non-numeric timestamps inside the snapshot: investigate them before claiming complete temporal coverage.

## Privacy

The script exports message IDs, roles and timestamps only — never message text. A session inventory of a personal history is still sensitive (timestamps and session shapes reveal activity patterns): keep manifests local, and review any candidates for private data before sharing or publishing them. There is no network access or telemetry.

**Accuracy:** A nonempty search result is not full-session coverage, and `inventory.py` enumerates records but does not read them. The completeness claims in the skill text only hold if the read and reconcile steps are actually done.

## Test

```bash
python3 -m unittest discover -s tests -v
```

MIT licensed; see `LICENSE`.
