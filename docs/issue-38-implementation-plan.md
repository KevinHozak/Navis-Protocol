# Issue #38 Implementation Plan

## Scope

Add a dedicated Synthesis Lab viewport around the existing Forge panel while preserving the existing archival file renderer and navigation state.

## Acceptance Criteria

- Lab navigation renders a complete view.
- Lab entries remain selectable and open their content.
- Loading, empty-data, and request-error states are explicit.
- Forge controls remain available without archive entries.
- Regression coverage verifies the Lab path and backend archival source.

## Verification

Run `npm run test:synthesis-lab`, the existing navigation checks, `npm run lint`, and `npm run build` from `frontend`.
