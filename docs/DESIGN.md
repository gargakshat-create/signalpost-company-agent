# Design notes

## Identity-first publication

The registry lookup is the authoritative identity anchor. Web-derived information is only accepted from the hostname declared by that registry record. The agent never searches arbitrary sites for a company name and then assumes the result is the same company.

## Evidence model

A fact is a tuple of:

`(organisation_number, field, value, source_url, source_type, period, retrieved_at, normalized_value_hash)`

This makes it possible to preserve earlier evidence while keeping the latest value in `current_facts`.

## Refresh semantics

Re-running against an unchanged source snapshot is idempotent. A new fact is inserted only when its value hash is new. A `change` object is emitted only when the latest value differs from the stored current value.

## Missing data

No placeholder zeros are used. Unknown information appears in the `unknown` list, while the top-level state remains `available` when the company identity was successfully resolved.

## Request budget

The default global budget is 1,800 paid/cache-miss requests. This leaves practical headroom below the 2,000 outbound-request competition limit. Cached responses do not consume the budget.
