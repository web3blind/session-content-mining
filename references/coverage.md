# Coverage and resume contract

Example only; substitute the agreed end-exclusive boundary and timezone:

```text
python3 <skill_dir>/scripts/inventory.py --db <profile_home>/state.db --profile default --start 2026-08-10 --end-exclusive <ISO-end> --timezone <IANA-zone> --out <run-dir>/manifest-default.json
```

The script writes only a new manifest and never overwrites one. Database connection is `mode=ro` plus `PRAGMA query_only=ON`; it is closed explicitly. No transcript text or credentials are exported. A pinned read transaction sets max message ID and captures every message in the interval, including rows from sessions created earlier and archived/short/tool-only sessions. It does not rebuild indexes or invoke SessionDB. It reports unplaceable timestamps globally: investigate them before claiming complete temporal coverage, do not guess their dates.

Do not bypass a platform/tool guard to access live state. If direct read-only access is refused, use a supported read-only export or an authorized snapshot, preserving completeness and recording the limitation; do not quietly fall back to a few search hits.

`manifest` contains exact selected message IDs/roles/timestamps per session. `inventory_only: true` and `review_status: pending` deliberately prevent treating enumeration as completed analysis. This is a snapshot of available records, not a promise to include future messages, subsequently imported history or in-place edits. The source files themselves remain canonical. On resume after a changed corpus, detect additions/edits in the agreed interval and add a separately identified delta manifest; never mark new material reviewed because its session was previously closed.

Maintain a separate progress ledger keyed by profile + session + message ID/range:
- pending / reading / reviewed / triaged / excluded / blocked;
- completed message IDs and long-message offset ranges;
- evidence/artifact path, candidate IDs, exclusion or blocker reason;
- reviewer and last checkpoint.

Completion checks:
- Reviewed, triaged, excluded and pending/blocked sets are disjoint and reconcile exactly to the manifest; no duplicate IDs conceal gaps.
- Every exclusion has an explicit reason; exclusions do not count as 'read'.
- A nonempty bookend/search result is not full-session coverage. Resolve `truncated` and `content_truncated`; include messages that were hidden/inactivated by compression when reviewing historical canonical records.
- FTS availability affects discovery, not the inventory. Never mutate production FTS for content mining.
- A reviewed session with no useful topic still gets a recorded outcome.
- Inspect underlying messages for facts, especially dates, author corrections and whether a task actually succeeded. Tool evidence may be retrieved selectively; label the chosen depth honestly.
- Report pending/blocked work plainly. Do not say 'all sessions fully read' when some were only triaged or excluded.

Fixture validation performed for the helper: earlier-started, archived and short sessions; all roles; inclusive/exclusive date edges; named timezone; missing timestamps; unchanged source hash; CLI output; no overwrite; owner-only output; invalid interval rejected. This verifies enumeration, not editorial model quality or a completed review of real history.
