# Dashboard and Holocron read freshness

S010 repairs confirmed S009 findings T03/T04. Dashboard status reads are serialized:
a pending read disables manual refresh, and non-OK, malformed and transport failures
retain the previous data and successful-read timestamp. Startup, polling, Vault
notifications and rollover use the same status-read path. Retry is user-triggered;
the existing 30-second status poll remains unchanged.

The cockpit shows the last successful read in UTC and its age, separately from the
saved operational marker. Date-only markers explicitly have unknown timezone;
missing or timezone-free timestamps remain unknown. The marker and a successful
read do not prove freshness of underlying inputs.

Holocron reads validate the payload week against the requested week. Selection,
new requests and unmount invalidate obsolete success/failure callbacks, including
regeneration and AI debrief callbacks. Switching weeks clears the previous payload
and read timestamp. Failed refresh of the same week retains that week's data and
last read with a failed/retained signal. Retry targets the selected week, never an
unrelated latest cycle. Existing generated_at is displayed independently in UTC;
input freshness remains unknown. A partial AI debrief response does not advance
the full-data read timestamp. GET refreshes use the existing API adapter and a
10-second AbortSignal; native bridge deadlines remain owned by that adapter.

## Verification

Mounted production Home, WeeklyHolocronView and ReadFreshness checks use controlled
web/native transport doubles. They exercise initial reads, same-week failure and
recovery, unchanged last-read time after failure, retained operational marker,
wrong-week receipt rejection, late read success/failure, late regeneration and late
AI replies after week changes. No provider is called. The existing Bestiary fixture
now supplies a valid week identity and loads the real freshness component.

The frontend suite passed 51 adapter checks and the full regression runner.
33 isolated Python Holocron/evidence/native-operation checks passed. Physical
controlled-delay races and clean-machine installation remain unclaimed under S015.
75 serial native unit tests and one parity test passed, excluding the personal-Vault probe. Frontend build/lint passed with existing warnings.

## Packaged release fixture - 1.11.24

All 38 bundled resources matched source. The release executable reports
FileVersion/ProductVersion 1.11.24; its isolated smoke copy had the same hash.
The dashboard displayed the UTC successful read separately from its date-only
operational marker. Malformed synthetic status JSON showed failure and retained
the prior read time/marker; retry while still malformed kept that state. Restoring
the fixture recovered a successful read through the existing refresh flow.

The Holocron selector loaded W40 consistently with its debrief and source period.
Its existing backend revalidated the synthetic legacy cache, producing a current
generated_at independently of the frontend read time. Temporarily renaming only
the copied fixture native_holocron.py produced visible refreshing, then failed
refresh, while retaining W40 and both prior timestamps. Restoring that copied file
and clicking Retry refresh recovered W40 with a new successful read. The copied
bridge was restored and the fixture app closed. No personal Vault or provider
was used. No physical delayed-response race or installer execution is claimed.

Release executable SHA-256:
`8c15f077f01da3e8ade43dfa1f225bb6dcfaaf8a74731d4e8a771a0172f4913c`.
NSIS installer SHA-256:
`42993a75880961a3494a7141d88e4850be4d73a049e6460ebc0fbbad72150917`.

Source-level scoped audit found no remaining actionable defect. Independent
external review is unavailable. Broader physical web/native journeys remain S015.
