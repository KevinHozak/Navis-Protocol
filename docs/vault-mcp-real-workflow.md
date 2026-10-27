# Controlled read-only adoption: real-workflow trial

On 2026-10-27 the user explicitly accepted controlled read-only adoption with
the documented limits and authorized MCP epic closeout. Adoption covers the
verified local Codex connection and four read tools on MCP 0.4.2. Personal writes
remain disabled. This decision accepts limitations; it does not turn unmeasured
or unsupported cases into passed checks.

## Observed workflows

[Sanitized results](trials/vault-mcp-real-workflow-2026-10-27.json) record actual
calls through the existing chat connection after merged PR #14.

- A generic Documentation query found no decision matches (319 ms). A subsequent
  user-selected topic search under Journal returned ten matches in 19,317 ms,
  explicitly truncated. Refinement returned two matches in about 20 seconds.
  Bounded reads succeeded and the user confirmed the intended tentative
  game-selection source. This is a user-confirmed relevant match, not a blinded
  accuracy test or exhaustive recall measurement. Topic wording and scope matter.
- The October 20–26 journal call returned all seven dates in 2,050 ms. Five days
  were truncated at the requested budget; five continuation reads completed them
  in another 1,428 ms. No dates were missing. This verifies retrieval, not a
  human-reviewed summary of the week.
- Mission retrieval took 19,863 ms with one related note, completed through one
  continuation. A later review call took 8,380 ms and reported the same omissions.

## Reviewed mission omissions

| Link index | Classification | Disposition |
| --- | --- | --- |
| 0 | Non-Markdown target | Outside local Markdown retrieval. |
| 2 | External URI | Outside local Markdown retrieval. |
| 3 | External URI | Outside local Markdown retrieval. |
| 4 | Missing Markdown basename | No matching file found in the Vault. |

These targets were not fetched or repaired. No policy expansion was performed.
The missing note is a retained content gap; the others are unsupported target
kinds. None is counted as successfully retrieved context.

## Maintenance and accepted limits

The first search failed closed with index_stale. The configured 60-second
operator rebuild failed after 60,676 ms. One retry using a temporary supported
120-second operator budget succeeded after 66,143 ms and indexed 2,161 notes.
Saved client settings were unchanged. The first attempt overlapped a read-only
inventory-selection probe, so this is not an isolated Drive benchmark. Explicit
rebuild/retry remains a real operating cost; no background auto-rebuild is added.

The user reported useful retrieval with no corrections needed, but supplied no
correction-time estimate. Human correction time remains unmeasured. Prior fixture
and pilot baseline/source-verification evidence is retained separately; this run
adds no direct-workflow timing baseline or whole-Vault before/after integrity
measurement. Automatic approval review rejected private-text evidence duplication
and candidate-line output; those operations were not pursued. Sanitized link
classification succeeded. No fresh direct digest/excerpt comparison is claimed.

Claude Desktop, simultaneous clients, cold hydration, multi-device Drive races
and personal-data writes remain unverified. Broad searches retain exhaustive
validation and noticeable latency. Root-filtered searches certify only their
stated validated scope. No new implementation is required by this closeout.

## Closeout

NAVIS-S016 through S021 and follow-ups S025/S026 are done. NAVIS-E003 is done
within the explicitly accepted controlled read-only scope. The trial criterion
is accepted with a documented exception for human timing and the above evidence
limits. Guarded append integrity is fixture-verified under S021; it does not
constitute personal write enablement. Private source text, titles, paths and
client configuration are excluded from this report. This closeout changes only
issue records and sanitized documentation, with no app version bump.
