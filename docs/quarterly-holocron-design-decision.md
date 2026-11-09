# NAVIS-S029 design decision — draft

Date: 2026-11-07. Baseline: local main `a304f3b`.
Status: **proposed design selected for review; implementation and verification
blocked**. This is not an accepted runtime guarantee or implementation authority.
See the [issue](../issues/NAVIS-S029.md),
[contract/matrix](quarterly-holocron-preview-contract.md) and
[source reuse review](quarterly-holocron-reuse-review.md).

No helpers or databases were executed/opened for this draft. No application
launch, personal-Vault access, provider call, test run or tool installation occurred.

## Decision 1: SQLite input states and read strategy

Select a **bounded source-byte snapshot followed by a private in-memory SQLite
reader**, instead of opening the supplied database path with SQLite. The command
must never copy the DB to disk, repair it or initialize a missing ledger. This
removes direct file-backed SQLite access from the intended query path; it does
not itself prove that the native engine cannot create temporary files.

| Source state | Initial disposition |
| --- | --- |
| Missing canonical DB | `missing_ledger`, null totals; no initialization. |
| Settled, regular, safe rollback-mode DB without sidecars/recovery indicators | Eligible for one accepted byte snapshot and in-memory query; support remains **blocked** pending proof. |
| WAL-mode header or any `-wal`, `-shm`, `-journal` sibling | Refuse as `unsafe_database_state`, even if apparently empty, stale or checkpointed. No main-file-only fallback or mode change. |
| Unknown mode, incomplete image or changing source | `invalid_ledger`, `unsafe_database_state` or `changed_during_read`, according to the validated failure class; no partial sum. |
| Unsupported canonical columns or invalid Keeper rows | `unsupported_schema` or `invalid_ledger`; no schema repair or coercion. |
| Unsafe/inaccessible root or source | Existing safe root error or unavailable `unsafe_path`/`read_error`; no alternate-root discovery. |

Propose a **64 MiB main-image cap** and **5-second in-memory query deadline**.
These are resource-budget proposals, not measured performance promises. Over-cap
input yields `unsafe_database_state`; deadline exhaustion yields `read_error`,
without partial totals. Gate G1 must confirm these limits before implementation
and incorporate any agreed changes into the contract/matrix.

Intended sequence, not implemented:

1. Validate the explicit root/canonical path without following links. Read one
   bounded buffer through noncreating access, with root, ancestor and handle
   identity checks before/open/after. Inspect source/sidecar state around the read.
   Sidecar absence or a size/time match alone is not a concurrency barrier.
2. Accept the image only when the required source-consistency checks succeed.
   If safe consistency cannot be established, return unavailable; never reuse a
   stale image after a detected replacement or same-size rewrite.
3. Load that image into a private `:memory:` connection using a verified
   deserialization API. **Runtime API availability and native behavior are
   unverified.** If unavailable, block support; do not switch to file-backed access.
4. Configure memory-only temporary storage, disable extension loading and use
   supported query-only/trusted-schema defenses. Allow only required private
   setup, schema inspection and canonical reads; no user SQL, optional achievement
   queries, virtual-table execution or persistent schema/ledger mutations.
5. Strictly validate required columns and Keeper row values; compute count and
   signed sum from this same image, with recorded local-date quarter boundaries.
   Close the private connection. Do not hand it to progression services.

Private in-memory setup/deserialization is a narrowly permitted memory operation,
not permission to repair source data or issue arbitrary writes. Guards must
distinguish it from prohibited file-backed writable opens. Memory-only temporary
storage and SELECT/query-only flags remain defenses requiring native calibration,
not evidence that no native write attempt can occur.

The first supported input class is a settled synthetic rollback-mode fixture.
No live/WAL production ledger, Drive behavior or transactionally atomic snapshot
across the quarter is qualified. Copying a DB to disk is excluded by the no-file-
write contract. `immutable=1` on a possibly live file is not selected: neither a
filename nor a one-time no-WAL probe establishes immutable input.

## Decision 2: journal-reader reuse

Select a narrow bounded-read seam based on
[`vault_access._snapshot`](../backend/services/vault_access.py) and
[`vault_io.read_binary`](../backend/services/vault_io.py), under an explicit
application-note root context. Do not call MCP environment discovery, weekly
builders or the existing journal parser's independent file-open path.

The future seam must accept an explicit byte limit and noncreating opener.
Keep **existing consumers at 1 MiB** and S029 at **2 MiB**, preserving current
default behavior and transport policies. Do not globally raise limits or broaden
the Markdown resolver to admit database files. Private helpers are not already
a reviewed public API; the seam's interface and error mapping need review.

Quarterly discovery distinguishes absence from unreadable/unsafe preferred paths
before considering the flat layout. Derive coverage, source identity and exact
supported checkbox-prefix counts from one accepted UTF-8-sig buffer. No second
read for counts, deduplication by text, or silent fallback from a bad preferred
candidate. Map changed/encoding/size failures to the contract's safe reason codes;
an existing conflated not-found error cannot automatically mean a missing day.

Gate G2 requires future checks for short reads, exact/over-limit input, unchanged
legacy consumer limits, root/handle replacement, links/junctions, BOM/CRLF and
preferred-path refusal. Existing test source provides patterns, not new passes.

## Decision 3: native zero-write verification

Select a **fixture-scoped Windows file-I/O trace, write-denied disposable sandbox
and complete inventories**, alongside Python/SQL guards. Process Monitor is the
proposed native trace tool. Its installed version, capture configuration,
privilege availability and coverage are **unverified**. This document authorizes
no installation, tracing, system-setting changes or worker launch.

Bind the measured command's PID and creation time, observe it from startup and
detect/refuse descendants. Configure capture so unrelated processes and personal
activity are not recorded. Global unfiltered capture is not authorized. Late
attachment or successful-write-only filtering cannot establish the contract.
If complete, safely scoped capture cannot be arranged, native proof stays blocked.

The verifier must cover native create/open requests and results, writes,
delete/rename, truncation and metadata mutation, including denied attempts.
Memory-mapped write coverage must be demonstrated or remain blocked. Record only
test-owned execution; runtime library reads are distinct from permitted Vault
content reads and do not authorize personal data discovery.

Use isolated test-owned root, working, home, temp and cache directories. The
external verifier may prepare fixtures/permissions and write receipts outside
measurement. The measured command may not create logs, traces, `.pyc`, SQLite
temp files, locks or artifacts. OS read-access timestamps remain the documented
exception, not permission for application metadata writes.

Required calibration before accepting any zero-write result:

- Separate synthetic controls intentionally attempt write, create/delete,
  rename/truncate, metadata mutation and mapped writes in the sandbox. Every
  applicable attempt must be detected and fail verification, including denied
  attempts. These controls are not preview success cases.
- Demonstrate process-lifetime attribution, startup coverage and detection of
  incomplete/dropped trace events. Capture failure blocks proof.
- Require a benign bounded read and a known signed-XP in-memory query to return
  correct available results under guards. Blocking every SQLite operation and
  returning unavailable is not a happy-path pass.
- Each feature case needs zero forbidden native attempts, zero forbidden Python,
  SQL, process or network effects, and unchanged complete inventories. Catch
  create-then-delete effects through native observation, not only final hashes.
- Repeat with writes denied where supported. Unsupported permission/link/trace
  cases remain blocked or skipped, never passed. Record exact source, runtime,
  tool/version, configuration, guard results and inventories in the receipt.

If the proposed tool cannot demonstrate safe attribution and attempted-write
coverage, stop and revise this decision to select a demonstrably adequate native
or VFS mechanism. Do not weaken the contract to fit incomplete tooling. Python
`open` mocks do not cover native SQLite/ctypes I/O; process-only guards from other
work are not file-I/O proof.

## Blocking gates

| Gate | State | Evidence needed |
| --- | --- | --- |
| G1: SQLite snapshot path | **BLOCKED — unverified** | Runtime deserialization, resource-budget agreement, mode/sidecar classification, strict row/schema validation, correct empty/signed/count output and no file-backed fallback. |
| G2: journal seam | **BLOCKED — design only** | Reviewed narrow API/error mapping and future synthetic evidence retaining legacy limits/policies with quarterly 2 MiB snapshot semantics. |
| G3: native verification | **BLOCKED — unverified** | Safe trace tool/version/profile and positive/negative calibration for startup, denied/transient/mapped effects and capture completeness. |
| G4: feature acceptance | **BLOCKED — not implemented** | Executed contract/matrix cases with correct JSON, preserved inventories and all guard results; honest refusal of unsupported states. |

No gate is unblocked by this draft, a documentation check, historical weekly
tests or previous process-only guards. No waiver is inferred. The issue remains
open with all acceptance criteria unchecked. A future implementation request is
required, and a successful synthetic result would not qualify a live ledger.

## Consequences and alternatives

Legitimate WAL-mode databases may return unavailable XP in this first slice.
That is an explicit support boundary, not permission to checkpoint or alter them.
Native proof may block acceptance even when example metrics look correct. If
proof infrastructure is disproportionate, revisit scope explicitly rather than
marking an unproven promise complete.

Not selected: schema-initializing progression connections, full weekly builders,
disk snapshots/exports, direct file-backed `mode=ro` plus Python mocks alone,
global journal-limit changes or whole-quarter atomicity claims. All issue
exclusions remain: no UI, annual/comparative analytics, AI/inferred metrics,
exports/caches, scheduling, task/journal/XP writes, sync/rollover, personal-Vault
qualification, production migration or provider configuration/calls.
