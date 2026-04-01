"""
Validate schema template files for the Electronet schema registry.

Purpose
-------
This tool validates every template JSON file under the schema-template registry
against the shared JSON schema contract and repository-specific invariants.

This is a pre-build quality gate. It must fail fast when template files are
malformed, inconsistent, duplicated, or structurally unsafe to compile into
runtime schema artifacts.

Primary responsibilities
------------------------
1. Discover all template JSON files in the configured template directory.
2. Load the shared JSON schema definition.
3. Validate each template file against the shared schema.
4. Enforce additional repo-level invariants that are not fully captured by the
   JSON schema.
5. Print a readable validation report.
6. Exit non-zero on validation failure.

Expected inputs
---------------
- Template root directory, for example:
  resources/schemas/templates/electronet/
- Shared schema file, for example:
  resources/schemas/templates/schema_template.schema.json

Expected outputs
----------------
- Human-readable stdout/stderr validation summary.
- Process exit code:
  - 0 when all templates are valid
  - non-zero when any template fails validation

Repo-level invariants to enforce
--------------------------------
The JSON schema handles basic structure. This tool must also enforce:

1. File name consistency
   - The file stem should match the template id exactly, or match a clearly
     defined repo naming rule.
   - Reject silent drift between filename and internal template id.

2. Unique ids
   - Every template id must be globally unique.

3. Unique category/template mapping
   - Detect suspicious duplicates where multiple template files appear to
     represent the same category and source without a clear versioning reason.

4. Non-empty sections and labels
   - Every section must contain at least one label.
   - Labels must be non-empty after trim.

5. No duplicate labels inside a section unless explicitly allowed
   - Default behavior should flag duplicates.
   - If duplicate labels are allowed for a special case, require an explicit
     allowlist or justification mechanism.

6. No duplicate section names within the same template unless explicitly allowed.

7. Fingerprint format sanity
   - Fingerprint must exist and match the expected format.
   - This tool does not need to recompute the fingerprint unless that behavior
     is explicitly added later.

8. Electronet example URL sanity
   - URLs should be non-empty strings if present.
   - Prefer validating that example URLs are unique within a template.

9. Category/title sanity
   - category_gr and cta_map_key should not be blank.
   - Flag obvious category mismatches or placeholder values.

10. Stable ordering checks
    - Preserve section order and label order exactly as authored.
    - Never auto-sort authored template content.

Non-goals
---------
- Do not compile templates into runtime artifacts here.
- Do not mutate template files.
- Do not fetch live webpages.
- Do not silently fix invalid data.

Suggested CLI behavior
----------------------
Support a simple command-line interface such as:

    python -m tools.schema_registry.validate_templates

Optional future flags:
- --template-root
- --schema-path
- --strict
- --json-report

Implementation notes for Codex
------------------------------
- Keep this tool deterministic.
- Prefer small pure functions:
  - discover_templates(...)
  - load_schema(...)
  - validate_json_schema(...)
  - validate_repo_invariants(...)
  - render_report(...)
- Return structured errors internally, then render them for humans at the end.
- Make validation failures specific and actionable.
- Do not stop at the first invalid file unless a dedicated fail-fast mode is added.

Suggested report shape
----------------------
For each file:
- status: OK / ERROR
- template id
- category
- short issue list

Final summary:
- total files checked
- valid files
- invalid files
- total issues

Future extension points
-----------------------
- Recompute and verify template fingerprints
- Cross-check template coverage against catalog taxonomy
- Emit machine-readable JSON validation reports for CI
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