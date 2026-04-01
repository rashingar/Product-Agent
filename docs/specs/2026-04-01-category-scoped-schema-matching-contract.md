# Category-Scoped Schema Matching Contract

Date: 2026-04-01
Status: planned

## Purpose

This document freezes the branch contract for category-scoped schema matching before runtime behavior changes land.

The branch is limited to:
- schema/template compilation
- compiled runtime metadata
- runtime schema selection safety

This branch does not change:
- category resolution behavior
- public workflow entrypoints
- unrelated prepare/render orchestration

## Problem statement

The current failure mode is not that canonical category resolution is always wrong. The real safety gap is that category resolution can be correct while runtime schema selection still drifts to an unrelated template because matching is too global or too weakly constrained.

The concrete failure class to prevent is a washing-machine product resolving to the correct category while still inheriting meat-grinder-like characteristics from an unrelated template family.

## Required design

1. Runtime schema selection must be category-scoped, not global.
2. Compiled runtime metadata must include category binding and hard-gating fields.
3. If a category has exactly one active safe template, runtime selection must use deterministic direct selection.
4. If multiple templates exist in the same category family, only sibling templates in that family may compete.
5. If hard gates fail, the matcher must fail closed instead of borrowing another category's schema.

## Compiled runtime metadata contract

Every compiled template entry introduced by this branch must include the following fields:

| Field | Contract |
| --- | --- |
| `source_system` | Source family the compiled template belongs to. |
| `template_id` | Stable identifier for the compiled template entry. |
| `category_path` | Canonical full category path the template is bound to. |
| `parent_category` | Canonical parent category segment used for category-family scoping. |
| `leaf_category` | Canonical leaf category segment. |
| `sub_category` | Canonical optional sub-category segment when present. |
| `cta_map_key` | Deterministic CTA mapping key already used elsewhere in the pipeline. |
| `template_status` | Eligibility status for runtime auto-selection. Required values: `active`, `manual_only`, `deprecated`, `incomplete`. |
| `match_mode` | Runtime selection mode. Required values: `direct_only`, `sibling_scored`. |
| `section_names_exact` | Exact section names preserved from the source template. |
| `section_names_normalized` | Normalized section names used for bounded matching. |
| `label_set_exact` | Exact label set preserved from the source template. |
| `label_set_normalized` | Normalized label set used for bounded matching. |
| `section_label_pairs_normalized` | Normalized section-plus-label pairs used for stronger within-family discrimination. |
| `discriminator_labels` | Labels that strongly distinguish one sibling template from another. |
| `required_labels_any` | Labels where at least one must be present for the template to remain eligible. |
| `required_labels_all` | Labels that must all be present for the template to remain eligible. |
| `forbidden_labels` | Labels that immediately disqualify the template at runtime. |
| `min_section_overlap` | Minimum allowed section overlap before scoring can proceed. |
| `min_label_overlap` | Minimum allowed label overlap before scoring can proceed. |
| `sibling_template_ids` | Closed list of sibling templates in the same category family that may compete with this template. |
| `fingerprint` | Stable compiled fingerprint for deterministic change tracking and diagnostics. |
| `source_template_file` | Source template file path used to produce the compiled entry. |

Additional contract rules:
- Only `template_status = active` entries may enter the automatic runtime candidate pool.
- `manual_only`, `deprecated`, and `incomplete` entries must be compiled for visibility and diagnostics, but must be excluded from automatic runtime selection.
- `match_mode = direct_only` means the compiled entry is eligible only for deterministic direct selection after category scoping.
- `match_mode = sibling_scored` means the compiled entry may participate only in bounded competition against `sibling_template_ids` from the same category family.
- `sibling_template_ids` must never contain templates from a different `category_path` family.

## Runtime matcher decision flow

The runtime matcher contract for this branch is:

1. Resolve canonical category.
2. Build a category-scoped candidate pool from compiled metadata using the resolved category binding.
3. Drop any candidate with `template_status` of `manual_only`, `deprecated`, or `incomplete`.
4. If exactly one active safe template remains, select it directly.
5. If multiple active safe templates remain in the same category family, apply only intra-category hard gates:
   - reject candidates missing `required_labels_all`
   - reject candidates missing all of `required_labels_any` when that field is populated
   - reject candidates containing any `forbidden_labels`
   - reject candidates below `min_section_overlap`
   - reject candidates below `min_label_overlap`
6. Score only the remaining sibling candidates in that same category family using bounded within-family signals such as normalized section names, normalized label sets, section-label pairs, and discriminator labels.
7. If no candidate survives the hard gates, return `no_safe_template_match`.

## Fail-closed safety rules

- No global fuzzy fallback is allowed.
- No cross-category schema rescue is allowed.
- A category mismatch discovered at matcher time must not be "healed" by borrowing a template from another category family.
- `no_safe_template_match` is the correct runtime result when the category-scoped pool cannot satisfy the hard gates safely.

## Non-goals

- no global fuzzy fallback
- no cross-category schema rescue
- no category taxonomy rewrite in this branch
- no category resolution behavior change in this branch
- no public workflow entrypoint change in this branch
- no unrelated prepare/render orchestration refactor in this branch

## Current branch state

This document is a scope and contract freeze only. It does not, by itself, change runtime behavior.
