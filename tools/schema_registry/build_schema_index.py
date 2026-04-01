"""
Build the schema index CSV from the compiled Electronet schema library.

Purpose
-------
This tool generates a lightweight tabular index for quick inspection,
cross-checking, and downstream tooling support.

The schema index is not the primary runtime artifact.
It is a derived support artifact that makes the compiled library easier to
search, diff, and audit.

Primary responsibilities
------------------------
1. Read the compiled Electronet schema library JSON.
2. Flatten each compiled schema entry into a single CSV row.
3. Emit a stable schema index CSV with predictable columns and ordering.

Expected input
--------------
- Compiled runtime schema library, for example:
  resources/schemas/electronet_schema_library.json

Expected output
---------------
- CSV schema index, for example:
  resources/schemas/schema_index.csv

Why this tool exists
--------------------
The compiled library is optimized for runtime structure.
The index is optimized for:
- human review
- quick filtering
- coverage checks
- debugging schema selection
- small diffs in pull requests

Suggested columns
-----------------
Use the repo's existing index contract if one already exists.
If the format is still being finalized, likely columns include:

- schema_id
- category_gr
- cta_map_key
- template_file
- fingerprint
- n_sections
- n_labels_total
- last_section
- last_label
- example_count
- electronet_example_1 (optional)
- status or source marker if needed

General rules:
- Keep column order stable.
- Prefer plain scalar values.
- Avoid stuffing large JSON blobs into CSV cells unless truly necessary.

Deterministic behavior
----------------------
1. The same compiled library must always yield the same CSV rows and order.
2. Preserve stable row ordering, ideally sorted by schema_id or category path.
3. Avoid incidental formatting churn.

Non-goals
---------
- Do not validate templates here.
- Do not compile templates here.
- Do not generate coverage markdown here.
- Do not fetch live data.

Suggested CLI behavior
----------------------
Support a simple command-line interface such as:

    python -m tools.schema_registry.build_schema_index

Optional future flags:
- --library-path
- --output
- --sort-by
- --include-examples

Implementation notes for Codex
------------------------------
- Keep CSV writing explicit and stable.
- Escape values correctly.
- Preserve UTF-8 encoding.
- Use a fixed field order constant.
- Fail clearly if required library fields are missing.

Recommended implementation shape
--------------------------------
- load_compiled_library(...)
- flatten_schema_entry(...)
- build_rows(...)
- write_csv(...)

Quality checks
--------------
Before writing output:
- ensure no duplicate schema_id rows
- ensure required columns are present
- ensure section/label count fields are numeric and consistent

Future extension points
-----------------------
- Add optional markdown or HTML index output
- Add diff mode between two schema libraries
- Add category coverage summaries
"""
"""
Codex implementation guardrails
------------------------------
- Keep functions small and pure where possible.
- Fail loudly on invalid inputs.
- Do not fetch live web data.
- Do not mutate source templates unless the tool explicitly says so.
- Preserve stable ordering and deterministic output.
"""