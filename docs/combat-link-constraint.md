# Combat task links

A task can have only one active combat link. A second link returns HTTP 400 with
`Task already linked; resolve or cancel it before relinking.` in `detail`.
Validation runs before source binding or card changes. The existing link,
proposed cards, discard, lost pile, and saved state remain unchanged.

Web and Tauri use the same locked combat dispatcher through FastAPI and the
native Rust subprocess bridge respectively. The link dialog displays the error,
keeps the selected cards, and refreshes battle state to show the current link.

There is no implicit replacement or unlink operation. Complete the current link
or cancel it using the existing resolution action before linking again.
Cancellation releases the link by resolving its cards to discard or lost
according to their burn flags; it does not return them directly to the hand.
