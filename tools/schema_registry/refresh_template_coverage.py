"""
Refresh the template coverage report for the Electronet schema template registry.

Purpose
-------
This tool generates a human-readable coverage report showing which categories
have template support, which are still missing, and which examples back each
template.

This report is for audit and planning, not runtime execution.

Primary responsibilities
------------------------
1. Read the template registry.
2. Optionally read category/taxonomy source files used to define expected
   coverage.
3. Compare expected category coverage against existing template files.
4. Generate or refresh a markdown coverage report.

Expected inputs
---------------
- Template directory, for example:
  resources/schemas/templates/electronet/
- Taxonomy/category source of truth, likely one or more of:
  - catalog taxonomy data
  - CTA map / category map data
  - any existing category registry inputs used by the repo

Expected output
---------------
- Coverage markdown report, for example:
  docs/audits/electronet_template_coverage.md

Coverage questions this tool should answer
------------------------------------------
1. Which Electronet categories currently have template files?
2. Which categories are missing templates?
3. Which categories are marked manual-only or unresolved?
4. Which example URLs are attached to each template?
5. Which template files appear stale, incomplete, or weakly exemplified?

Suggested report columns
------------------------
Keep the markdown report compact and reviewable. Good columns include:
- CTA Leaf Category
- File
- Status
- Electronet Examples

Possible status values:
- OK
- NEEDS_MANUAL
- MISSING
- DUPLICATE
- STALE
- REVIEW

Deterministic rules
-------------------
1. The report must be reproducible from repository inputs only.
2. Never depend on live web fetches.
3. Keep row ordering stable.
4. Do not silently drop categories from coverage expectations.

Status rules
------------
At minimum:
- OK:
  category has a valid template file and looks complete enough for registry use
- NEEDS_MANUAL:
  category is known but intentionally unresolved or requires manual design
- MISSING:
  expected category has no template file
- REVIEW:
  template exists but has suspicious gaps, duplicates, or weak examples

Implementation notes for Codex
------------------------------
- Separate "expected categories" from "observed templates".
- Build a clean comparison layer.
- Render markdown at the end from structured rows.
- Keep formatting stable so PR diffs are clean.

Suggested implementation shape
------------------------------
- load_expected_categories(...)
- load_templates(...)
- assess_template_coverage(...)
- build_markdown_table(...)
- write_report(...)

Non-goals
---------
- Do not compile runtime schema artifacts here.
- Do not modify template files.
- Do not validate JSON schema beyond light sanity checks unless explicitly added.
- Do not fetch live Electronet pages.

Suggested CLI behavior
----------------------
Support a simple command-line interface such as:

    python -m tools.schema_registry.refresh_template_coverage

Optional future flags:
- --template-root
- --taxonomy-path
- --output
- --strict

Quality checks
--------------
- Flag duplicate category mappings
- Flag missing or empty example lists where examples are expected
- Flag categories that exist in taxonomy but not in templates
- Flag template files present in repo but not tied to expected category coverage

Future extension points
-----------------------
- Emit JSON coverage for CI
- Add stale-template detection using change-log timestamps
- Include counts by parent category
- Generate a compact summary section at the top of the markdown report
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