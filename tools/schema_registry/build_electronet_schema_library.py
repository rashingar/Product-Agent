"""
Build the compiled Electronet runtime schema library from editable schema templates.

Purpose
-------
This tool transforms the editable Electronet template registry into the compact
runtime artifact consumed by the product-mapping pipeline.

The editable templates are the source-of-truth authoring layer.
The compiled schema library is the runtime layer.

This tool must be deterministic: the same validated template inputs must always
produce the same compiled output.

Primary responsibilities
------------------------
1. Read all validated Electronet template files.
2. Normalize authored template content into the runtime library shape.
3. Build the final compiled Electronet schema library JSON file.
4. Preserve enough metadata for downstream matching while keeping the runtime
   artifact compact.

Expected input
--------------
- Template directory, for example:
  resources/schemas/templates/electronet/
- Shared schema contract:
  resources/schemas/templates/schema_template.schema.json

Expected output
---------------
- Compiled runtime schema library, for example:
  resources/schemas/electronet_schema_library.json

Compilation intent
------------------
The compiled runtime library should support fast deterministic schema matching.
It should preserve the structural signals needed by runtime consumers without
carrying every authoring-only field.

The compiler should therefore separate:
- authoring metadata
- runtime matching data

Fields likely to preserve in compiled output
--------------------------------------------
Adjust final shape to match the runtime contract already used by the repo, but
the compiler will likely need to derive or preserve at least:

- schema_id
- category or category path reference
- section titles
- section label order
- section count
- total label count or row count
- sentinel information for last section / last label
- source/template file reference
- fingerprint
- example/source provenance if needed for debugging

Fields that may stay authoring-only
-----------------------------------
These fields may be excluded from the runtime artifact if they are not needed
downstream:
- verbose examples
- coverage-only notes
- report-oriented metadata
- change-log references

Deterministic rules
-------------------
1. Input order must not affect semantic output.
2. Compilation must not depend on network access.
3. Preserve authored section order and label order.
4. Do not auto-rename labels.
5. Do not auto-translate or normalize Greek strings unless the runtime contract
   explicitly requires it.
6. If compilation detects invalid or conflicting inputs, fail clearly rather
   than guessing.

Important build steps
---------------------
1. Discover template files.
2. Validate them or assume they were pre-validated.
3. Load each template.
4. Convert each template to the runtime schema entry shape.
5. Derive summary fields such as:
   - number of sections
   - total number of labels
   - sentinel last_section / last_label
6. Assemble the final JSON structure.
7. Write the compiled output atomically.

Sentinel derivation
-------------------
If the runtime library uses sentinel fields, derive them from the final section
and final label of the authored template, preserving exact string values.

Example:
- last_section = sections[-1].section
- last_label = sections[-1].labels[-1]

Non-goals
---------
- Do not fetch live Electronet pages.
- Do not edit template source files.
- Do not generate coverage documentation here.
- Do not regenerate unrelated runtime assets.

Suggested CLI behavior
----------------------
Support a simple command-line interface such as:

    python -m tools.schema_registry.build_electronet_schema_library

Optional future flags:
- --template-root
- --output
- --pretty
- --validate-first

Implementation notes for Codex
------------------------------
- Keep the transformation pipeline explicit:
  - discover_templates(...)
  - load_templates(...)
  - compile_template(...)
  - assemble_library(...)
  - write_output(...)
- Prefer typed intermediate objects or dataclasses if useful.
- Make compilation failures loud and actionable.
- Write to a temp file and replace atomically to avoid partial outputs.

Output stability
----------------
The compiled JSON should be stable across runs. Avoid unnecessary churn in:
- key ordering
- array ordering
- formatting
- whitespace

Future extension points
-----------------------
- Incremental builds
- Fingerprint verification
- Compile multiple vendor registries, not just Electronet
- Emit compile diagnostics for debugging matcher regressions
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