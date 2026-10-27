# S020 retrieval trial rubric

Defined before collecting trial measurements. Applies to synthetic disposable
Vault fixtures; it does not authorize indexing personal data or calling a model.

## Cases and baseline

Use one fixed fixture corpus with an independent golden manifest:

1. Find a past decision by a unique synthetic identifier and read its source.
2. Review an inclusive seven-day journal interval and a selected section.
3. Retrieve a canonical mission and its explicitly linked context note.

The baseline is the existing direct file/search workflow: `rg` keyword discovery,
explicit note reads, canonical dated journal reads, and mission/context file
reads. It is scripted and deterministic, not a measurement of human cognition or
agent answer quality. The candidate uses the same fixture over the stdio MCP
tools. Neither route receives the golden expected answer as retrieval input.

## Measurements and gates

| Measure | Method | Passing gate |
| --- | --- | --- |
| Source correctness | Compare returned relative paths, original-byte digests, physical line references and required content to the independent manifest. | Every required source correct; no excluded source returned. |
| Omissions | Count missing golden evidence items/days/context notes, including pagination. | Zero unexpected omissions. |
| Latency | Record whole-workflow wall time, separate cold connection/index setup from warm calls; run five alternating baseline/candidate repetitions. | Warm candidate p95 at most 2 seconds on the fixture; no claim about real-Vault scale. |
| Correction/recovery | Change one indexed note after rebuild, observe the error, explicitly rebuild, repeat the lookup and verify the new source. Record scripted elapsed time and required actions. | Stale result rejected; recovery succeeds in two operator actions (rebuild, retry). |
| Freshness | Search must reject modified/added/removed sources or changed policy rather than return stale evidence. | Explicit error, no stale excerpt. Existing unit acceptance covers individual mutation classes. |
| Setup/maintenance | Record runtime/client versions, installation prerequisites, index-build time and required configuration/restart steps. | Instructions reproducible; unknown effort remains unknown. |
| Client compatibility | Use an actual intended local Codex client connection, list the four tools and exercise retrieval. Record the exact client/runtime, not merely SDK protocol success. | Primary client genuinely connected; second client verified or explicitly unsupported/unverified. Desktop UI and CLI/app-server observations are separate. |
| Integrity | Hash fixture files before and after both workflows and freshness recovery. | Only the deliberately changed synthetic note differs; no journal/XP writes. |

`p95` uses the nearest-rank value for five samples (therefore the maximum).
Raw private text, credentials, complete client configurations and real journal
content must not appear in committed evidence. Use counts, relative synthetic
paths, hashes and bounded timings. Human correction time and user preference are
**not measured** by automation; do not report zero as though they were observed.

## Decision rule

- **Adopt** only if the primary-client gate and correctness/integrity/freshness
  gates pass, fixture latency is acceptable and operating costs are explicit.
  Adoption is limited to the verified client/runtime and corpus; it does not
  establish production quality or enable writes.
- **Revise** when fixture retrieval works but actual primary-client verification,
  operating effort or required evidence is incomplete. Keep S020 open and S021
  writes disabled.
- **Stop** if source disclosure/integrity is unacceptable or the intended client
  cannot support the selected transport without changing the agreed scope.

Record one decision with observed evidence and remaining manual checks. Do not
silently replace the intended desktop client with a test harness or claim
cross-client support from shared protocol types.
