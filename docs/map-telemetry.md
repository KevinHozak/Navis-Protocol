# Overworld telemetry contract

The existing shared desktop adapter supplies `/api/status` from `Bridge/status.json` on web and native. SectorView passes this status into the map. The map does not fetch a second status source or infer coordinates from nodes. No existing producer is assumed to know physical positions; absent coordinates remain unavailable.

An optional `map_telemetry` object uses `version: 1` and `coordinate_space: "canvas-1024x576"`. Optional `player`, `antagonist`, `beast`, and `squad` objects each require `realm`, numeric `x` and `y`, and `observed_at` as an ISO timestamp with timezone. Coordinates refer to the displayed 1024 by 576 canvas, including its cropped background, with origin at top left. Bounds are inclusive. Threat entries also require `target` matching `current_antagonist` or `current_beast`. Squad entries require `members` matching the current `squad` names in order. See `frontend/scripts/fixtures/map-telemetry.json` for a complete example.

Only the authoritative telemetry producer should write these fields when it has measured coordinates. Realm navigation alone cannot provide player coordinates. Records older than five minutes, future records, malformed records, mismatched realms/targets/squads, and unsupported contracts are omitted with visible reasons. Threat clearing removes its marker immediately. The wrapper checks expiry every second even when status does not change. Realm changes recreate the scene and clear destination selection. Status changes replace the complete overlay layer.

The cyan player, red antagonist, amber beast, and purple squad markers have labels and a text legend containing coordinates or omission reasons. The text details are accessible outside the canvas.

## Verification

Run `npm run test:map-telemetry`, `npm run test:map-node-validation`, `npm run test:map-realm-navigation`, and `npm run test:moongate-loading` in frontend.

Manual runtime procedure (not yet executed): use a disposable Vault with fixture status and realm assets, start the standard web stack, open Overworld, and confirm labels and text details agree. Update coordinates through the status source, clear each threat, change squad, and hop realm through Moongate. Confirm old markers vanish. Supply stale, future, malformed, missing and out-of-bounds positions and inspect omission reasons. Wait five minutes without status changes and confirm expiry. Repeat in native with the disposable Vault configured, test keyboard destination navigation, missing optional art, and small viewport readability. Never modify the production Vault just to test coordinates.
