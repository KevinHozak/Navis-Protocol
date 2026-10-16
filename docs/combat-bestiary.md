# Beast Bestiary

Codex → Beasts displays catalog profiles and recorded tactical history. Weekly
Holocron threat names open this dashboard with the matching beast highlighted.
The profile/Forge cards remain below the analytics grid.

`GET /api/battle/bestiary` is a read-only projection shared by FastAPI and the
desktop local combat adapter. Desktop packaging includes `services/bestiary.py`;
viewing requires the packaged Python runtime and local Vault, not HTTP.

Completed tactical task resolutions persist round snapshots in the progression
database's `combat_rounds` table. The resolution key prevents retry duplication;
the encounter history ID survives subsequent rounds. A failure leaves the
existing completion operation recoverable. Older pending operations without
before-round snapshots still finish through their original recovery path.

Encounter frequency counts distinct encounters per beast. Win and defeat rates
use resolved encounters only; active encounters appear separately. Slayings
count living-to-zero HP transitions; highest turn damage sums actual HP loss
against that beast within a turn, excluding overkill. Trophies are derived at
1 (First Slaying), 10 (Beast Hunter), and 50 (Master Hunter) slayings.

Elemental profiles come from `Codex/Beasts/<name>/Combat.json`, falling back to
`Obstacles/Beasts`. Affinity is displayed as the documented elemental strength;
it does not imply resistance. Invalid definitions display an unavailable state.
Catalog-only beasts have zero counts and undefined rates. History-only beasts
retain their names with unknown elemental profiles.

Legacy XP logs and critical awards do not establish complete battle outcomes,
so they are excluded rather than converted into invented victories or damage.
Viewing creates no database, schema, projection, or trophy writes.

Validation: `python -m pytest` for the focused Bestiary/combat/Holocron suites;
`node --experimental-vm-modules scripts/test-bestiary.mjs` for HUD retry,
selection and Holocron links; client transport regressions cover native routing.
