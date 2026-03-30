# Product-Agent Engineering Log

## Current milestone
M35 completed. The repo now uses a scrape-only prepare-stage core for the active prepare path, `prepare` no longer writes a scrape-stage CSV, `render` remains the sole owner of candidate and publish outputs, `scraper/pipeline/full_run.py` is reduced to a thin compatibility wrapper for explicit direct callers, and provider resolution now flows through the registry bootstrap and source-to-provider-id mapping seam.

Historical note:
- Sections below, including this M23 rename record, preserve `scrapper/` and `electronet_single_import` references only as execution evidence unless a section explicitly states current guidance.

## 2026-03-30 - Resolve providers through registry bootstrap

Goal:
- replace ad hoc provider-selection branches in orchestration with registry-driven resolution
- keep provider fetch and normalize behavior unchanged
- add public coverage for registry bootstrap and source-to-provider-id mapping

Files edited:
- `DOCUMENTATION.md`
- `scraper/pipeline/full_run.py`
- `scraper/pipeline/prepare_stage.py`
- `scraper/pipeline/providers/__init__.py`
- `scraper/pipeline/providers/registry.py`
- `scraper/pipeline/tests/test_provider_selection.py`
- `scraper/pipeline/tests/test_workflow.py`

Changes:
- extended `scraper/pipeline/providers/registry.py` with:
  - `bootstrap_runtime_provider_registry(...)`
  - `source_to_provider_id(...)`
- made `bootstrap_runtime_provider_registry(...)` the single runtime bootstrap point for the active providers:
  - `electronet`
  - `skroutz`
  - `manufacturer_tefal`
- updated `scraper/pipeline/prepare_stage.py` orchestration to:
  - build the provider registry once per run
  - map detected source to provider id through `source_to_provider_id(...)`
  - resolve the provider through `registry.require(...)`
- removed the active-path dependence on the old ad hoc provider-selection helper branches from orchestration
- kept the existing readable failure behavior for missing runtime providers by surfacing the registry-not-registered failure as a direct runtime error
- updated `scraper/pipeline/full_run.py` to pass the registry bootstrap and source-mapping functions through to the compatibility wrapper path
- re-exported the new bootstrap and mapping helpers from `scraper/pipeline/providers/__init__.py`
- updated tests so public registry behavior is what is asserted now:
  - bootstrap coverage
  - source mapping coverage
  - orchestration tests inject a registry instead of anchoring on private branch-selection internals

Intentional behavior changes:
- no provider fetch or normalize behavior changed
- no provider ids changed
- orchestration now depends on the public registry bootstrap plus mapping seam instead of private branch selection code

Commands run:
- `Get-Content -Raw scraper/pipeline/providers/registry.py`
- `Get-Content -Raw scraper/pipeline/prepare_stage.py`
- `Get-Content -Raw scraper/pipeline/tests/test_provider_selection.py`
- `rg -n "_resolve_provider_for_source|ProviderRegistry|provider_id|detect_source\\(|require\\(" scraper/pipeline scraper/pipeline/tests -S`
- `Get-Content -Raw scraper/pipeline/providers/__init__.py`
- `Get-Content -Raw scraper/pipeline/providers/electronet_provider.py`
- `Get-Content -Raw scraper/pipeline/providers/skroutz_provider.py`
- `Get-Content -Raw scraper/pipeline/providers/manufacturer_tefal_provider.py`
- `py -3.12 -m pytest -q pipeline/tests/test_provider_selection.py pipeline/tests/test_workflow.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_provider_selection.py pipeline/tests/test_workflow.py pipeline/tests/test_services.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_skroutz_sections.py` from `scraper/`
- `rg -n "_resolve_provider_for_source|bootstrap_runtime_provider_registry|source_to_provider_id|registry.require\\(" scraper/pipeline scraper/pipeline/tests -S`

Validation:
- targeted provider/orchestration subset first:
  - `py -3.12 -m pytest -q pipeline/tests/test_provider_selection.py pipeline/tests/test_workflow.py` from `scraper/`
  - passed, `26 passed`
- broader affected suite:
  - `py -3.12 -m pytest -q pipeline/tests/test_provider_selection.py pipeline/tests/test_workflow.py pipeline/tests/test_services.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_skroutz_sections.py` from `scraper/`
  - passed, `47 passed`

Deferred:
- no error taxonomy changes were made
- no CI changes were made
- no provider fetch/normalize internals were changed

## 2026-03-30 - Make prepare scrape-only under the split-task workflow

Goal:
- finish the prepare/render execution seam after the split-LLM refactor
- make `prepare` scrape-only plus split-task handoff-only
- keep `render` as the sole owner of final candidate outputs and publish copy

Files added:
- `scraper/pipeline/prepare_stage.py`

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`
- `README.md`
- `scraper/pipeline/full_run.py`
- `scraper/pipeline/services/prepare_execution.py`
- `scraper/pipeline/services/prepare_service.py`
- `scraper/pipeline/services/render_service.py`
- `scraper/pipeline/workflow.py`
- `scraper/pipeline/tests/test_services.py`
- `scraper/pipeline/tests/test_skroutz_integration.py`
- `scraper/pipeline/tests/test_workflow.py`

Changes:
- extracted the scrape-only execution core into `scraper/pipeline/prepare_stage.py`
- moved the active prepare-stage behavior there:
  - provider-backed fetch and normalization
  - scrape artifact writes under `work/{model}/scrape/`
  - deterministic normalization used by the split-task handoff
  - report generation
- kept candidate CSV generation out of the new prepare-stage core
- updated `scraper/pipeline/services/prepare_execution.py` so the active prepare path now calls `execute_prepare_stage(...)` directly instead of `execute_full_run(...)`
- removed the old nested scrape-dir workaround from prepare because the new core now writes directly to `work/{model}/scrape/`
- kept `scraper/pipeline/services/render_execution.py` as the only owner of:
  - `work/{model}/candidate/{model}.csv`
  - `work/{model}/candidate/{model}.normalized.json`
  - `work/{model}/candidate/{model}.validation.json`
  - `work/{model}/candidate/description.html`
  - `work/{model}/candidate/characteristics.html`
  - `products/{model}.csv`
- reduced `scraper/pipeline/full_run.py` to a thin compatibility wrapper:
  - it now delegates to `execute_prepare_stage(...)`
  - it performs the legacy direct CSV write only for explicit callers of `execute_full_run(...)`
  - it is no longer part of the active workflow prepare path
- updated `scraper/pipeline/workflow.py` so `prepare_workflow(...)` no longer imports or passes through `execute_full_run(...)`
- fixed `scraper/pipeline/services/prepare_service.py` so prepare result details come from the actual scrape result payload
- fixed `scraper/pipeline/services/render_service.py` so an unpublished render result can map `published_csv_path` as `None` safely
- updated `README.md` to describe the steady-state boundary:
  - prepare writes scrape plus split-task handoff artifacts only
  - render owns candidate outputs and publish copy

Intentional behavior changes:
- `python -m pipeline.workflow prepare ...` no longer creates `work/{model}/scrape/{model}.csv`
- `python -m pipeline.workflow prepare ...` does not create `work/{model}/candidate/{model}.csv`
- explicit compatibility calls to `execute_full_run(...)` still write a direct CSV for callers and tests that intentionally exercise the legacy full-run helper

Commands run:
- `Get-Content -Raw scraper/pipeline/services/prepare_execution.py`
- `Get-Content -Raw scraper/pipeline/services/render_execution.py`
- `Get-Content -Raw scraper/pipeline/services/prepare_service.py`
- `Get-Content -Raw scraper/pipeline/services/render_service.py`
- `Get-Content -Raw scraper/pipeline/services/run_execution.py`
- `Get-Content -Raw scraper/pipeline/workflow.py`
- `Get-Content -Raw scraper/pipeline/full_run.py`
- `Get-Content -Raw README.md`
- `Get-Content -Raw scraper/pipeline/tests/test_workflow.py`
- `Get-Content -Raw scraper/pipeline/tests/test_services.py`
- `Get-Content -Raw scraper/pipeline/tests/test_skroutz_integration.py`
- `Get-Content -Raw scraper/pipeline/cli.py`
- `rg -n "execute_full_run\\(|prepare_workflow\\(|execute_prepare_workflow\\(|candidate_csv_path|published_csv_path|work/\\{model\\}/scrape/\\{model\\}\\.csv|llm_output\\.json|intro_text\\.output|seo_meta\\.output" scraper/pipeline scraper/pipeline/tests README.md -S`
- `rg -n "_select_skroutz_image_backed_sections" scraper/pipeline/tests scraper/pipeline -S`
- `py -3.12 -m pytest -q pipeline/tests/test_workflow.py pipeline/tests/test_services.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_workflow.py pipeline/tests/test_services.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_skroutz_sections.py pipeline/tests/test_provider_selection.py` from `scraper/`

Validation:
- smallest relevant subset first:
  - `py -3.12 -m pytest -q pipeline/tests/test_workflow.py pipeline/tests/test_services.py` from `scraper/`
  - passed, `27 passed`
- broader affected suite:
  - `py -3.12 -m pytest -q pipeline/tests/test_workflow.py pipeline/tests/test_services.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_skroutz_sections.py pipeline/tests/test_provider_selection.py` from `scraper/`
  - passed, `47 passed`

Deferred:
- no provider registry refactor was attempted
- no service error taxonomy work was attempted
- no CI changes were attempted
- `execute_full_run(...)` remains available as a thin compatibility wrapper for explicit direct callers rather than being removed entirely in this milestone

## 2026-03-30 - Define post-split prepare/render execution seam cleanup scope

Goal:
- document the complete post-split branch scope before any runtime code changes
- keep this commit docs-only and record the actual current prepare/render seam versus the intended steady-state ownership boundary
- avoid implying that the seam cleanup is already implemented

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`
- `IMPLEMENT.md`

Current state:
- `README.md` still documents the two-stage `prepare` / `render` workflow under `scraper/`, including prepare handoff artifacts under `work/{model}/llm/` and render candidate artifacts under `work/{model}/candidate/`
- `scraper/pipeline/services/prepare_execution.py` still routes prepare through `execute_full_run(...)`
- `scraper/pipeline/full_run.py` still writes `{model}.csv` into the output root it is given, so the active prepare path still produces a scrape-stage CSV side effect under `work/{model}/scrape/`
- `scraper/pipeline/services/render_execution.py` already consumes split-task outputs:
  - `work/{model}/llm/intro_text.output.txt`
  - `work/{model}/llm/seo_meta.output.json`
- `scraper/pipeline/services/render_execution.py` already writes candidate-stage artifacts and publish copy:
  - `work/{model}/candidate/{model}.csv`
  - `work/{model}/candidate/{model}.validation.json`
  - `work/{model}/candidate/description.html`
  - `work/{model}/candidate/characteristics.html`
  - `products/{model}.csv` when validation passes

Target state:
- prepare owns scrape-only execution plus task handoff artifact creation
- render owns all final candidate and publish outputs
- the active prepare path no longer depends on `execute_full_run(...)`
- `full_run.py` is reduced to explicit full-run composition only, or retired from the active prepare path entirely

Ownership boundary after split-LLM:
- prepare-owned artifacts:
  - `work/{model}/scrape/{model}.raw.html`
  - `work/{model}/scrape/{model}.source.json`
  - `work/{model}/scrape/{model}.normalized.json`
  - `work/{model}/scrape/{model}.report.json`
  - scrape-stage downloaded assets and supporting scrape artifacts under `work/{model}/scrape/`
  - `work/{model}/llm/task_manifest.json`
  - `work/{model}/llm/intro_text.context.json`
  - `work/{model}/llm/intro_text.prompt.txt`
  - `work/{model}/llm/seo_meta.context.json`
  - `work/{model}/llm/seo_meta.prompt.txt`
- render-owned artifacts:
  - `work/{model}/candidate/{model}.csv`
  - `work/{model}/candidate/{model}.normalized.json`
  - `work/{model}/candidate/{model}.validation.json`
  - `work/{model}/candidate/description.html`
  - `work/{model}/candidate/characteristics.html`
  - `products/{model}.csv`
- LLM-stage handoff note:
  - the LLM still writes `work/{model}/llm/intro_text.output.txt` and `work/{model}/llm/seo_meta.output.json`, but prepare owns the contract and handoff scaffolding for those files rather than render owning their creation

Intended fate of `full_run.py`:
- `scraper/pipeline/full_run.py` should stop being the active implementation seam behind workflow prepare
- acceptable end states for this branch are:
  - a narrowed explicit full-run composition wrapper above scrape-only prepare plus render
  - retirement from the active prepare path if service-owned composition fully replaces it
- unacceptable end state:
  - any remaining prepare-stage dependency that keeps candidate CSV generation or other render/publish side effects inside the active prepare path

Out of scope for this branch:
- provider bootstrap changes
- service error taxonomy redesign
- CI changes

Commands run:
- `Get-Content -Raw PLAN.md`
- `Get-Content -Raw DOCUMENTATION.md`
- `Get-Content -Raw IMPLEMENT.md`
- `Get-Content -Raw scraper/pipeline/services/prepare_execution.py`
- `Get-Content -Raw scraper/pipeline/services/render_execution.py`
- `Get-Content -Raw scraper/pipeline/full_run.py`
- `Get-Content -Raw scraper/pipeline/workflow.py`
- `Get-Content -Raw README.md`
- `rg -n "execute_full_run\\(|llm_output\\.json|intro_text\\.output|seo_meta\\.output|candidate|validation|publish|csv_path" scraper/pipeline/services scraper/pipeline/full_run.py scraper/pipeline/workflow.py README.md -S`
- `rg --files scraper/pipeline/tests`
- `git status --short`
- `git diff --check -- PLAN.md DOCUMENTATION.md IMPLEMENT.md`

Validation:
- docs-only commit
- `git diff --check -- PLAN.md DOCUMENTATION.md IMPLEMENT.md` passed
- no runtime tests were run because this commit only updates control docs and must not include runtime or test changes

Deferred:
- no runtime code, tests, or README changes were made in this commit
- the prepare/render seam cleanup remains planned work only at this stage
- earlier M34 records remain preserved below as historical execution evidence for the split-task contract, even though the post-split execution seam cleanup is now tracked separately as pending work

## 2026-03-30 - Remove legacy combined LLM handoff and finalize split-task workflow

Goal:
- remove the temporary combined LLM compatibility path from prepare, render, validators, tests, and runtime docs
- leave the branch in its final steady state with split `intro_text` and `seo_meta` artifacts only
- align operator-facing docs with deterministic section rendering and the final failure policy

Files edited:
- `AGENTS.md`
- `README.md`
- `PLAN.md`
- `IMPLEMENT.md`
- `DOCUMENTATION.md`
- `scraper/pipeline/llm_contract.py`
- `scraper/pipeline/repo_paths.py`
- `scraper/pipeline/workflow.py`
- `scraper/pipeline/services/models.py`
- `scraper/pipeline/services/prepare_execution.py`
- `scraper/pipeline/services/prepare_service.py`
- `scraper/pipeline/services/render_execution.py`
- `scraper/pipeline/services/render_service.py`
- `scraper/pipeline/services/run_execution.py`
- `scraper/pipeline/tests/test_llm_contract.py`
- `scraper/pipeline/tests/test_services.py`
- `scraper/pipeline/tests/test_skroutz_integration.py`
- `scraper/pipeline/tests/test_skroutz_sections.py`
- `scraper/pipeline/tests/test_utils_support_paths.py`
- `scraper/pipeline/tests/test_workflow.py`

Files removed:
- `resources/prompts/master_prompt+.txt`
- `resources/schemas/compact_response.schema.json`

Changes:
- removed legacy combined prepare artifact generation:
  - `work/{model}/llm_context.json`
  - `work/{model}/prompt.txt`
- removed the legacy combined render input path:
  - `work/{model}/llm_output.json`
- simplified the active LLM contract in `scraper/pipeline/llm_contract.py` to split-task-only helpers and validators:
  - kept `build_intro_text_context(...)`
  - kept `build_seo_meta_context(...)`
  - kept `build_task_manifest(...)`
  - kept `validate_intro_text_output(...)`
  - kept `validate_seo_meta_output(...)`
  - removed the old combined-context builder and combined/legacy validators
- updated `scraper/pipeline/services/prepare_execution.py` so prepare now writes only:
  - `work/{model}/llm/task_manifest.json`
  - `work/{model}/llm/intro_text.context.json`
  - `work/{model}/llm/intro_text.prompt.txt`
  - `work/{model}/llm/seo_meta.context.json`
  - `work/{model}/llm/seo_meta.prompt.txt`
- updated the manifest to steady-state mode:
  - `prepare_mode: split_tasks`
  - removed compatibility metadata for legacy combined artifacts
- updated `scraper/pipeline/services/render_execution.py` so render now requires:
  - `work/{model}/llm/intro_text.output.txt`
  - `work/{model}/llm/seo_meta.output.json`
- removed the render fallback to legacy combined payloads and changed the missing-artifact error to the split-task-only path
- removed legacy artifact fields from service-layer artifact models and service result mapping
- retired the obsolete combined prompt/schema resources and removed their centralized path constants
- updated workflow CLI output to print only the split-task artifact paths
- updated `AGENTS.md` and `README.md` to describe the final runtime:
  - split prepare outputs
  - split LLM outputs
  - deterministic section rendering
  - section warning/failure policy
  - no LLM section-copy generation
- updated tests so final steady-state behavior is the only active runtime expectation

Legacy behavior removed:
- prepare no longer writes combined `llm_context.json` or `prompt.txt`
- render no longer accepts combined `llm_output.json`
- the LLM no longer owns:
  - `presentation.intro_html`
  - `presentation.sections[].title`
  - `presentation.sections[].body_html`
- the reduced combined prompt/schema resources are no longer part of the runtime

Commands run:
- `rg -n "llm_context\\.json|prompt\\.txt|llm_output\\.json|presentation\\.intro_html|presentation\\.sections|validate_llm_output|legacy|split_tasks_with_legacy_compatibility|intro_text\\.output|seo_meta\\.output|task_manifest" README.md PLAN.md DOCUMENTATION.md IMPLEMENT.md AGENTS.md scraper resources -S`
- `Get-Content scraper/pipeline/llm_contract.py`
- `Get-Content scraper/pipeline/services/prepare_execution.py`
- `Get-Content scraper/pipeline/services/render_execution.py`
- `Get-Content scraper/pipeline/services/models.py`
- `Get-Content scraper/pipeline/services/prepare_service.py`
- `Get-Content scraper/pipeline/services/render_service.py`
- `Get-Content scraper/pipeline/services/run_execution.py`
- `Get-Content scraper/pipeline/workflow.py`
- `Get-Content README.md`
- `Get-Content AGENTS.md`
- `Get-Content IMPLEMENT.md`
- `Get-Content scraper/pipeline/tests/test_llm_contract.py`
- `Get-Content scraper/pipeline/tests/test_services.py`
- `Get-Content scraper/pipeline/tests/test_workflow.py`
- `Get-Content scraper/pipeline/tests/test_skroutz_integration.py`
- `Get-Content scraper/pipeline/tests/test_skroutz_sections.py`
- `py -3.12 -m pytest -q pipeline/tests/test_llm_contract.py pipeline/tests/test_workflow.py pipeline/tests/test_services.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_skroutz_sections.py pipeline/tests/test_utils_support_paths.py` from `scraper/`
- `py -3.12 -m pytest -q` from `scraper/`

Validation:
- targeted cleanup-facing subset first:
  - `py -3.12 -m pytest -q pipeline/tests/test_llm_contract.py pipeline/tests/test_workflow.py pipeline/tests/test_services.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_skroutz_sections.py pipeline/tests/test_utils_support_paths.py` from `scraper/`
  - passed, `46 passed`
- full suite:
  - `py -3.12 -m pytest -q` from `scraper/`
  - passed, `120 passed`

Deferred:
- no provider-registry, CI, or unrelated service-layer refactors were attempted in this cleanup commit
- historical documentation below still mentions old combined artifacts as prior-state evidence and was not rewritten wholesale

## 2026-03-30 - Assemble description HTML from `intro_text` and deterministic sections

Goal:
- migrate render to the split-task outputs introduced in M30
- make final description HTML code-owned and assembled from plain-text `intro_text`, deterministic CTA data, and deterministic cleaned presentation sections
- keep the compatibility phase active by accepting legacy combined `llm_output.json` until final cleanup

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`
- `scraper/pipeline/html_builders.py`
- `scraper/pipeline/llm_contract.py`
- `scraper/pipeline/mapping.py`
- `scraper/pipeline/services/render_execution.py`
- `scraper/pipeline/tests/test_llm_contract.py`
- `scraper/pipeline/tests/test_skroutz_integration.py`
- `scraper/pipeline/tests/test_skroutz_sections.py`
- `scraper/pipeline/tests/test_workflow.py`

Changes:
- updated `scraper/pipeline/services/render_execution.py` so render now prefers split-task outputs from `work/{model}/llm/`:
  - `intro_text.output.txt`
  - `seo_meta.output.json`
- kept compatibility with legacy `work/{model}/llm_output.json`:
  - legacy `product.meta_description` and `product.meta_keywords` are still accepted
  - legacy `presentation.intro_html` is reduced to plain text for the active render path
  - legacy section title/body content is no longer required or used for final description assembly
- replaced the active render-time LLM validation path in `scraper/pipeline/llm_contract.py`:
  - added split validators for `intro_text` and `seo_meta`
  - removed render-time dependence on LLM-owned section title/body validation
  - kept the old combined validator available only as legacy compatibility support for older tests and artifacts
- added `build_description_html_from_intro_and_sections(...)` in `scraper/pipeline/html_builders.py`
- updated `scraper/pipeline/mapping.py` so final description HTML is now assembled in code from:
  - plain-text `intro_text`
  - deterministic CTA text
  - deterministic cleaned presentation sections
- kept wrappers, classes, styles, and CTA/link rendering code-owned
- enforced deterministic section failure policy during render:
  - hard fail when source sections are missing entirely and sections were requested
  - hard fail when usable section count is `0` and sections were requested
  - hard fail when more than one requested section is classified `missing`
  - warn and continue when sections are `weak`
  - warn and continue when exactly one requested section is `missing`
- passed only `usable` deterministic sections into the final HTML renderer
- preserved source titles and sanitized source wording for section bodies; no section rewriting or LLM section generation remains in the active path
- normalized SEO keywords in `scraper/pipeline/mapping.py` so render now:
  - guarantees brand and model/MPN are present
  - collapses duplicate keywords
  - collapses singular/plural variants in code before CSV serialization
- preserved section-image wiring by original `source_index` so skipped weak sections do not shift later Besco image assignments
- wrote split/legacy mode details into render normalized artifacts and run metadata:
  - `llm_mode`
  - `llm_artifact_paths`
  - `presentation_sections`

Behavior changes:
- final `description` HTML is no longer sourced from LLM HTML sections in the active render path
- the intro paragraph now comes from plain-text LLM `intro_text` and is escaped into the existing wrapper structure in code
- deterministic section warnings now surface in render validation reports, including reduced-section cases during the compatibility phase
- legacy combined LLM outputs remain accepted intentionally, but only for intro/meta compatibility; section rendering is deterministic even when legacy artifacts are present
- compatibility fixture coverage now expects legacy render inputs to succeed when the active split-compatible validation rules are satisfied

Commands run:
- `rg -n "validate_llm_output|meta_keywords|build_description_html_from_llm|build_description_html|extract_presentation_blocks" scraper/pipeline -S`
- `Get-Content scraper/pipeline/services/render_execution.py`
- `Get-Content scraper/pipeline/html_builders.py`
- `Get-Content scraper/pipeline/mapping.py`
- `Get-Content scraper/pipeline/llm_contract.py`
- `Get-Content scraper/pipeline/presentation_sections.py`
- `Get-Content scraper/pipeline/tests/test_workflow.py`
- `Get-Content scraper/pipeline/tests/test_skroutz_sections.py`
- `Get-Content scraper/pipeline/tests/test_skroutz_integration.py`
- `py -3.12 -m pytest -q pipeline/tests/test_workflow.py pipeline/tests/test_llm_contract.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_skroutz_sections.py::test_143481_rendered_description_preserves_locked_wrappers pipeline/tests/test_skroutz_integration.py::test_prepare_and_render_workflow_with_skroutz_fixtures` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_workflow.py pipeline/tests/test_llm_contract.py pipeline/tests/test_services.py pipeline/tests/test_skroutz_sections.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_presentation_sections.py` from `scraper/`

Validation:
- render-focused subset first:
  - `py -3.12 -m pytest -q pipeline/tests/test_workflow.py pipeline/tests/test_llm_contract.py` from `scraper/`
  - passed, `27 passed`
- targeted compatibility regressions after the image-mapping fix:
  - `py -3.12 -m pytest -q pipeline/tests/test_skroutz_sections.py::test_143481_rendered_description_preserves_locked_wrappers pipeline/tests/test_skroutz_integration.py::test_prepare_and_render_workflow_with_skroutz_fixtures` from `scraper/`
  - passed, `2 passed`
- broader affected suite:
  - `py -3.12 -m pytest -q pipeline/tests/test_workflow.py pipeline/tests/test_llm_contract.py pipeline/tests/test_services.py pipeline/tests/test_skroutz_sections.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_presentation_sections.py` from `scraper/`
  - passed, `57 passed`

Deferred:
- final cleanup is still pending:
  - legacy `work/{model}/llm_output.json` is still accepted
  - legacy `work/{model}/llm_context.json` and `work/{model}/prompt.txt` still exist as compatibility artifacts from prepare
  - `README.md` has not been updated to the final steady-state split-output flow yet
- no LLM prompt split changes were made in this commit beyond consuming the split outputs already introduced in prepare

## 2026-03-30 - Split prepare into `intro_text` and `seo_meta` task artifacts

Goal:
- make split task-specific LLM handoff artifacts the primary prepare outputs
- keep the branch mergeable by preserving the legacy combined prepare files and legacy render input path during the transition
- remove section title/body generation from the new task ownership model without changing render to consume the new task outputs yet

Files added:
- `resources/prompts/intro_text_prompt.txt`
- `resources/prompts/seo_meta_prompt.txt`

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`
- `scraper/pipeline/repo_paths.py`
- `scraper/pipeline/llm_contract.py`
- `scraper/pipeline/services/models.py`
- `scraper/pipeline/services/prepare_execution.py`
- `scraper/pipeline/services/prepare_service.py`
- `scraper/pipeline/services/run_execution.py`
- `scraper/pipeline/workflow.py`
- `scraper/pipeline/tests/test_llm_contract.py`
- `scraper/pipeline/tests/test_services.py`
- `scraper/pipeline/tests/test_utils_support_paths.py`
- `scraper/pipeline/tests/test_workflow.py`

Changes:
- added two task-specific prompt resources under `resources/prompts/`:
  - `intro_text_prompt.txt`
  - `seo_meta_prompt.txt`
- added new prompt path constants in `scraper/pipeline/repo_paths.py`
- extended `scraper/pipeline/llm_contract.py` with split-task builders:
  - `build_intro_text_context(...)`
  - `build_seo_meta_context(...)`
  - `build_task_manifest(...)`
- kept the existing combined `build_llm_context(...)` and legacy prompt rendering path in place strictly for compatibility
- updated `scraper/pipeline/services/prepare_execution.py` so prepare now writes these primary artifacts:
  - `work/{model}/llm/intro_text.context.json`
  - `work/{model}/llm/intro_text.prompt.txt`
  - `work/{model}/llm/seo_meta.context.json`
  - `work/{model}/llm/seo_meta.prompt.txt`
  - `work/{model}/llm/task_manifest.json`
- reserved expected task output targets in the manifest for the later render migration:
  - `work/{model}/llm/intro_text.output.txt`
  - `work/{model}/llm/seo_meta.output.json`
- preserved these compatibility artifacts intentionally:
  - `work/{model}/llm_context.json`
  - `work/{model}/prompt.txt`
  - `work/{model}/llm_output.json`
- updated prepare metadata and service-layer artifact models so run metadata now records:
  - `llm_dir`
  - `llm_task_manifest_path`
  - `intro_text_*` paths
  - `seo_meta_*` paths
- updated workflow prepare CLI output to print the new primary task artifact paths plus the legacy compatibility paths

Task ownership changes:
- `intro_text` now owns only the intro paragraph prompt/output contract:
  - plain text only
  - one paragraph
  - Greek
  - 120-180 words
  - no HTML
  - no bullets
  - no CTA language
- `seo_meta` now owns only:
  - `product.meta_description`
  - `product.meta_keywords`
- the new task contexts do not include section title/body generation instructions
- deterministic `presentation_source_sections` remain outside the split task contexts and stay in deterministic artifacts instead of being passed as a required `intro_text` writing input

Compatibility behavior intentionally preserved:
- prepare still writes the legacy combined context and prompt files because render has not been migrated yet
- render still reads legacy `work/{model}/llm_output.json` in this commit
- the task manifest explicitly marks the prepare mode as `split_tasks_with_legacy_compatibility`

Commands run:
- `Get-Content scraper/pipeline/repo_paths.py`
- `Get-Content scraper/pipeline/services/models.py`
- `rg -n "llm_context_path|prompt_path|llm_output_path|MASTER_PROMPT_PATH|prompt.txt|llm_context.json|task_manifest|intro_text|seo_meta" scraper/pipeline scraper/pipeline/tests resources -S`
- `Get-Content scraper/pipeline/services/prepare_service.py`
- `Get-Content scraper/pipeline/services/metadata.py`
- `Get-Content scraper/pipeline/workflow.py`
- `rg -n "meta_description_draft|differentiator|key_specs|deterministic_product" scraper/pipeline/deterministic_fields.py scraper/pipeline/tests/test_workflow.py scraper/pipeline/tests/test_skroutz_integration.py -S`
- `Get-Content scraper/pipeline/deterministic_fields.py`
- `Get-Content scraper/pipeline/tests/test_utils_support_paths.py`
- `Get-Content scraper/pipeline/services/run_execution.py`
- `Get-Content scraper/pipeline/tests/test_workflow.py | Select-Object -First 170`
- `Get-Content scraper/pipeline/tests/test_workflow.py | Select-Object -Skip 900 -First 60`
- `Get-Content scraper/pipeline/tests/test_services.py | Select-Object -First 240`
- `Get-Content scraper/pipeline/tests/test_llm_contract.py`
- `py -3.12 -m pytest -q pipeline/tests/test_llm_contract.py pipeline/tests/test_workflow.py pipeline/tests/test_services.py pipeline/tests/test_utils_support_paths.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_presentation_sections.py pipeline/tests/test_llm_contract.py pipeline/tests/test_workflow.py pipeline/tests/test_services.py pipeline/tests/test_utils_support_paths.py pipeline/tests/test_skroutz_sections.py pipeline/tests/test_skroutz_integration.py` from `scraper/`

Validation:
- targeted prepare-facing subset first:
  - `py -3.12 -m pytest -q pipeline/tests/test_llm_contract.py pipeline/tests/test_workflow.py pipeline/tests/test_services.py pipeline/tests/test_utils_support_paths.py` from `scraper/`
  - passed, `30 passed`
- broader affected tests:
  - `py -3.12 -m pytest -q pipeline/tests/test_presentation_sections.py pipeline/tests/test_llm_contract.py pipeline/tests/test_workflow.py pipeline/tests/test_services.py pipeline/tests/test_utils_support_paths.py pipeline/tests/test_skroutz_sections.py pipeline/tests/test_skroutz_integration.py` from `scraper/`
  - passed, `52 passed`

Deferred:
- render was not changed to consume `intro_text` or `seo_meta` outputs in this commit
- legacy combined `llm_context.json`, `prompt.txt`, and `llm_output.json` remain intentionally present for the transition
- section title/body generation is still part of the legacy combined compatibility prompt only; the new split task artifacts do not assign that work to the LLM

## 2026-03-30 - Deterministic presentation section cleaning and quality classification foundation

Goal:
- add a deterministic normalization and quality-classification seam for extracted `presentation_source_sections`
- keep the current single-prompt LLM handoff intact for now while making section cleaning and section-state evaluation code-owned
- avoid changing final HTML assembly in this step

Files added:
- `scraper/pipeline/presentation_sections.py`
- `scraper/pipeline/tests/test_presentation_sections.py`

Files edited:
- `DOCUMENTATION.md`
- `scraper/pipeline/models.py`
- `scraper/pipeline/llm_contract.py`
- `scraper/pipeline/tests/test_workflow.py`

Changes:
- added `scraper/pipeline/presentation_sections.py` as the deterministic section normalization module
- introduced normalized presentation section dataclasses in `scraper/pipeline/models.py`:
  - `NormalizedPresentationSection`
  - `NormalizedPresentationSectionMetrics`
- implemented deterministic section normalization with these behaviors:
  - preserves source order
  - preserves source wording while stripping markup, URLs, and non-content tags
  - preserves source titles when present
  - classifies each section as `usable`, `weak`, or `missing`
  - emits reason codes including:
    - `missing_extraction`
    - `missing_empty_after_clean`
    - `missing_image_only`
    - `weak_short_body`
    - `weak_missing_title`
    - `weak_noisy_body`
    - `weak_duplicate`
    - `usable_clean`
  - applies the agreed word-count and alphabetic-character thresholds
  - detects duplicates against previously accepted non-missing section bodies
- updated `scraper/pipeline/llm_contract.py` so `build_llm_context(...)` now writes normalized deterministic `presentation_source_sections` into `work/{model}/llm_context.json`
- kept the current LLM output contract unchanged in this commit:
  - `presentation.intro_html`
  - `presentation.sections[].title`
  - `presentation.sections[].body_html`
  - `product.meta_description`
  - `product.meta_keywords`
- did not change render HTML assembly in this step

Behavior changes:
- `prepare` now exposes normalized section records in LLM context instead of raw extracted title/paragraph pairs
- each section record now includes:
  - `source_index`
  - `title`
  - `body_text`
  - `image_url`
  - `quality`
  - `reason`
  - `metrics`
- when fewer extracted sections exist than requested, `build_llm_context(...)` pads the deterministic section list with `missing_extraction` placeholders up to `sections_required`

Commands run:
- `rg -n "presentation_source_sections|sections|rendered_sections|section" scraper/pipeline -S`
- `Get-Content scraper/pipeline/llm_contract.py`
- `Get-Content scraper/pipeline/services/render_execution.py`
- `Get-Content scraper/pipeline/html_builders.py`
- `Get-Content scraper/pipeline/models.py`
- `Get-Content scraper/pipeline/mapping.py`
- `Get-Content scraper/pipeline/tests/test_llm_contract.py`
- `Get-Content scraper/pipeline/tests/test_workflow.py | Select-Object -First 180`
- `Get-Content scraper/pipeline/services/prepare_execution.py`
- `Get-Content scraper/pipeline/tests/test_services.py`
- `Get-Content resources/prompts/master_prompt+.txt`
- `rg -n "presentation_source_sections|paragraph|image_url|title" resources/prompts/master_prompt+.txt scraper/pipeline/tests/test_workflow.py scraper/pipeline/tests/test_skroutz_integration.py scraper/pipeline/tests/test_skroutz_sections.py -S`
- `Get-Content scraper/pipeline/normalize.py`
- `py -3.12 -m pytest -q pipeline/tests/test_presentation_sections.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_presentation_sections.py pipeline/tests/test_workflow.py pipeline/tests/test_llm_contract.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_services.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_presentation_sections.py pipeline/tests/test_workflow.py pipeline/tests/test_llm_contract.py pipeline/tests/test_services.py` from `scraper/`

Validation:
- smallest relevant subset first:
  - `py -3.12 -m pytest -q pipeline/tests/test_presentation_sections.py` from `scraper/`
  - passed, `10 passed`
- broader affected tests:
  - `py -3.12 -m pytest -q pipeline/tests/test_presentation_sections.py pipeline/tests/test_workflow.py pipeline/tests/test_llm_contract.py` from `scraper/`
  - passed, `29 passed`
  - `py -3.12 -m pytest -q pipeline/tests/test_services.py` from `scraper/`
  - passed, `8 passed`
  - final rerun:
  - `py -3.12 -m pytest -q pipeline/tests/test_presentation_sections.py pipeline/tests/test_workflow.py pipeline/tests/test_llm_contract.py pipeline/tests/test_services.py` from `scraper/`
  - passed, `37 passed`

Deferred:
- no LLM task split was attempted in this commit
- no prompt-template change was attempted in this commit
- no render-side deterministic section consumption was attempted in this commit
- no README change was made in this commit

## 2026-03-30 - Branch scope design note for split-LLM `intro_text` and deterministic presentation

Purpose:
- document the full planned scope of the split-LLM deterministic-presentation branch before runtime code changes
- keep this commit docs-only and avoid implying that any runtime or test work is already complete

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`
- `IMPLEMENT.md`

Current state:
- `README.md` still documents single prepare outputs:
  - `work/{model}/llm_context.json`
  - `work/{model}/prompt.txt`
- `scraper/pipeline/llm_contract.py` currently marks these fields as LLM-owned:
  - `presentation.intro_html`
  - `presentation.sections[].title`
  - `presentation.sections[].body_html`
  - `product.meta_description`
  - `product.meta_keywords`
- `scraper/pipeline/services/prepare_execution.py` still builds one LLM context and one prompt
- `scraper/pipeline/services/render_execution.py` still reads `work/{model}/llm_output.json`

Target state:
- prepare emits two task-specific LLM handoffs:
  - `intro_text`
  - `seo_meta`
- `intro_text` returns plain text only, one paragraph, 120-180 words
- `seo_meta` returns:
  - `meta_description`
  - `meta_keywords`
- presentation section title/body generation is removed from the LLM
- presentation sections are built deterministically from `presentation_source_sections`
- existing source section titles are kept when present
- deterministic section handling is limited to cleaning/sanitizing unsafe or noisy markup while preserving wording
- final description HTML is rendered in code from:
  - the LLM `intro_text` paragraph
  - deterministic CTA data
  - cleaned deterministic source sections
- HTML wrappers, CTA block, image wiring, section layout, classes, and styles become code-owned

Compatibility phase:
- render will first look for task-specific outputs:
  - `work/{model}/intro_text.llm_output.json`
  - `work/{model}/seo_meta.llm_output.json`
- render will continue to accept legacy combined `work/{model}/llm_output.json` during the compatibility phase
- final cleanup removes the combined-output fallback and the single-prompt artifact contract

Deterministic ownership boundaries:
- LLM-owned in the target branch:
  - `intro_text`
  - `product.meta_description`
  - `product.meta_keywords`
- code-owned in the target branch:
  - presentation section selection, classification, and cleaning
  - section titles when sourced
  - CTA text and CTA block wiring
  - description wrappers, classes, and styles
  - image wiring
  - section layout
  - keyword deduplication
  - singular/plural keyword collapsing
  - final HTML assembly

Section quality classifier:
- `usable`: the source section has enough preserved text or media-backed structure to render as a deterministic feature block
- `weak`: the source section exists but is too thin, noisy, or redundant to count confidently; warn and continue if remaining sections are sufficient
- `missing`: the requested section slot cannot be filled from source data after extraction and cleaning

Failure policy:
- if `presentation_source_sections` are missing entirely, fail the run
- if sections are `weak`, warn and continue with fewer sections
- if exactly one requested section is `missing`, warn and continue with fewer sections
- do not add a fallback that asks the LLM to regenerate missing deterministic section copy

SEO rules planned for code ownership:
- `intro_text` stays plain text only and is converted to HTML in code
- `seo_meta` must return `meta_description` and `meta_keywords`
- brand and model must always appear in `meta_keywords`
- duplicate keywords and singular/plural variants are collapsed in code before CSV mapping

Commands run:
- `Get-Location | Select-Object -ExpandProperty Path`
- `git status --short`
- `Get-Content -Raw PLAN.md`
- `Get-Content -Raw IMPLEMENT.md`
- `Get-Content -Raw DOCUMENTATION.md`
- `rg -n "intro_html|meta_description|meta_keywords|sections\\[\\]\\.title|sections\\[\\]\\.body_html|llm_output\\.json|prompt\\.txt|llm_context\\.json|prepare_execution|render_execution|presentation_source_sections" scraper resources README.md -S`
- `rg --files scraper/pipeline/tests`
- `rg -n "llm_contract|compact_response.schema.json|master_prompt\\+\\.txt|prompt.txt|llm_context.json" scraper/pipeline resources -S`
- `Get-Content DOCUMENTATION.md | Select-Object -First 140`
- `rg -n "Phase 3|M29|Validation rules|Stop conditions|Current milestone" PLAN.md DOCUMENTATION.md IMPLEMENT.md -S`
- `git diff --check`
- `git diff -- PLAN.md IMPLEMENT.md DOCUMENTATION.md`

Validation:
- docs-only commit
- `git diff --check` passed
- no runtime tests were run because this commit only updates control docs and must not include runtime or test changes

Deferred:
- no runtime code, tests, or README changes were made in this commit
- the compatibility phase, deterministic section pipeline, and final cleanup remain planned work only at this stage

## M29 — make run_service the true owner of full-run orchestration

Goal:
- move the real full-run orchestration body out of `scraper/pipeline/services/run_service.py` into a service-owned execution module
- keep CLI commands, workflow adapter behavior, artifact paths, validation semantics, publish gating, output semantics, and provider behavior unchanged
- finish the full-run ownership inversion without widening scope into workflow or provider redesign

Files added:
- `scraper/pipeline/services/run_execution.py`

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`
- `scraper/pipeline/services/run_service.py`
- `scraper/pipeline/tests/test_services.py`

Changes:
- extracted the full-run composition body from `scraper/pipeline/services/run_service.py::run_product(...)` into `scraper/pipeline/services/run_execution.py::execute_run_workflow(...)`
- kept the full-run composition service-owned by having the new executor compose `prepare_product(...)` and `render_product(...)` and return the same aggregated `ServiceResult` shape as before
- reduced `scraper/pipeline/services/run_service.py` to a thin service wrapper that directly calls the new service-owned full-run executor and preserves the existing exception-wrapping behavior
- updated `scraper/pipeline/tests/test_services.py` to prove:
  - service-owned modules involved in prepare/render/full-run execution do not import `workflow.py`
  - the new full-run executor still composes prepare/render results in order with unchanged aggregation semantics
  - `run_product(...)` now delegates to the service-owned full-run executor and still wraps executor errors

Commands run:
- `Get-ChildItem -Force`
- `rg -n "run_product|FullRunRequest|prepare_product|render_product|run_execution|workflow" scraper/pipeline -S`
- `Get-Content PLAN.md`
- `Get-Content DOCUMENTATION.md`
- `Get-Content scraper/pipeline/services/run_service.py`
- `Get-Content scraper/pipeline/tests/test_services.py`
- `Get-Content scraper/pipeline/workflow.py`
- `Get-Content scraper/pipeline/services/models.py`
- `Get-Content scraper/pipeline/cli.py`
- `Get-Content scraper/pipeline/services/__init__.py`
- `rg -n "run_product\\(|prepare_product\\(|render_product\\(" scraper/pipeline/tests/test_workflow.py scraper/pipeline/tests/test_services.py scraper/pipeline/cli.py -S`
- `git status --short`
- `Get-Content scraper/pipeline/services/prepare_service.py`
- `Get-Content scraper/pipeline/services/render_service.py`
- `Get-Content scraper/pipeline/services/prepare_execution.py`
- `Get-Content scraper/pipeline/services/render_execution.py`
- `rg -n "Current milestone|M28|M29|Phase 2 milestones" PLAN.md DOCUMENTATION.md -S`
- `Get-Content scraper/pipeline/tests/test_workflow.py | Select-Object -Skip 940 -First 40`
- `python -m compileall pipeline` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_services.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_workflow.py` from `scraper/`
- `py -3.12 -m pytest -q` from `scraper/`

Validation:
- compile validation:
  - `python -m compileall pipeline` from `scraper/`
  - passed
- exact requested pytest commands:
  - `py -3.12 -m pytest -q pipeline/tests/test_services.py` from `scraper/`
  - passed
  - `py -3.12 -m pytest -q pipeline/tests/test_workflow.py` from `scraper/`
  - passed
  - `py -3.12 -m pytest -q` from `scraper/`
  - passed

Risks:
- `run_product(...)` remains the stable service entrypoint while the real full-run composition now lives one layer lower in `run_execution.py`; this is intentional and keeps the service contract unchanged
- `cli.py` still owns standalone full-run metadata emission, while M29 only moves service-layer orchestration ownership

Deferred:
- no provider migration, CLI redesign, workflow redesign, artifact-path change, validation-contract change, or publish-gating change was attempted
- `scraper/pipeline/tests/test_workflow.py` did not require edits because the workflow layer remains an unchanged adapter for prepare/render-only commands
- `IMPLEMENT.md`, `AGENTS.md`, `README.md`, and `RULES.md` were left unchanged because M29 did not add a new durable operator rule or change the accepted runtime interface

## M28 — make services the true owner of prepare/render orchestration

Goal:
- move the real prepare/render orchestration bodies out of `scraper/pipeline/workflow.py` and into service-owned execution modules
- keep CLI/workflow commands, artifact paths, validation semantics, publish gating, and provider behavior unchanged
- finish the prepare/render ownership inversion without widening scope into provider changes or full-run redesign

Files added:
- `scraper/pipeline/services/prepare_execution.py`
- `scraper/pipeline/services/render_execution.py`

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`
- `scraper/pipeline/workflow.py`
- `scraper/pipeline/services/prepare_service.py`
- `scraper/pipeline/services/render_service.py`
- `scraper/pipeline/tests/test_services.py`
- `scraper/pipeline/tests/test_workflow.py`

Changes:
- extracted the prepare orchestration body from `workflow.prepare_workflow(...)` into `scraper/pipeline/services/prepare_execution.py::execute_prepare_workflow(...)`, including scrape artifact normalization, prompt/context generation, and prepare metadata writes
- extracted the render orchestration body from `workflow.render_workflow(...)` into `scraper/pipeline/services/render_execution.py::execute_render_workflow(...)`, including LLM output loading, candidate generation, validation, publish gating, and render metadata writes
- updated `scraper/pipeline/services/prepare_service.py` so `prepare_product(...)` now calls the service-owned prepare executor directly and no longer imports `workflow.py`
- updated `scraper/pipeline/services/render_service.py` so `render_product(...)` now calls the service-owned render executor directly and no longer imports `workflow.py`
- reduced `scraper/pipeline/workflow.py` to thin prepare/render adapters that inject the existing `WORK_ROOT`, `PRODUCTS_ROOT`, and `execute_full_run(...)` dependencies while keeping the CLI entrypoint behavior unchanged
- updated `scraper/pipeline/tests/test_services.py` to assert the services no longer import `workflow.py` and to mock the new service-owned executors instead of workflow-owned orchestration
- updated `scraper/pipeline/tests/test_workflow.py` with focused adapter-delegation coverage while preserving the existing prepare/render behavior tests at the current baseline

Commands run:
- `Get-Content scraper/pipeline/workflow.py`
- `Get-Content scraper/pipeline/services/prepare_service.py`
- `Get-Content scraper/pipeline/services/render_service.py`
- `Get-Content scraper/pipeline/tests/test_services.py`
- `Get-Content scraper/pipeline/tests/test_workflow.py`
- `Get-Content PLAN.md`
- `Get-Content DOCUMENTATION.md`
- `rg -n "prepare_workflow|render_workflow|prepare_product\\(|render_product\\(" scraper/pipeline -S`
- `Get-Content scraper/pipeline/services/models.py`
- `Get-Content scraper/pipeline/services/__init__.py`
- `git status --short`
- `Get-Content scraper/pipeline/tests/test_skroutz_integration.py -TotalCount 40`
- `Get-Content scraper/pipeline/tests/test_skroutz_sections.py -TotalCount 40`
- `Get-Content scraper/pipeline/workflow.py | Select-Object -First 220`
- `Get-Content scraper/pipeline/workflow.py | Select-Object -Skip 220`
- `Get-Content scraper/pipeline/workflow.py`
- `Get-Content scraper/pipeline/services/prepare_execution.py`
- `Get-Content scraper/pipeline/services/render_execution.py`
- `Get-Content scraper/pipeline/tests/test_services.py`
- `Get-Content scraper/pipeline/tests/test_workflow.py | Select-Object -First 140`
- `python -m compileall pipeline` from `scraper/`
- `python -m pytest -q pipeline/tests/test_services.py` from `scraper/`
- `python -m pytest -q pipeline/tests/test_workflow.py` from `scraper/`
- `python -m pytest -q` from `scraper/`
- `py -0p`
- `where.exe python`
- `py -3.12 -m pytest -q pipeline/tests/test_services.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_workflow.py` from `scraper/`
- `py -3.12 -m pytest -q` from `scraper/`

Validation:
- compile validation:
  - `python -m compileall pipeline` from `scraper/`
  - passed
- exact requested pytest commands:
  - `python -m pytest -q pipeline/tests/test_services.py` from `scraper/`
  - `python -m pytest -q pipeline/tests/test_workflow.py` from `scraper/`
  - `python -m pytest -q` from `scraper/`
  - all three failed before test discovery because the active `python` resolved to `C:\Users\Rashingar\AppData\Local\Programs\Python\Python310\python.exe`, which does not have `pytest` installed
- executed pytest validation on the installed interpreter:
  - `py -3.12 -m pytest -q pipeline/tests/test_services.py` from `scraper/`
  - passed, `7 passed`
  - `py -3.12 -m pytest -q pipeline/tests/test_workflow.py` from `scraper/`
  - passed, `15 passed`
  - `py -3.12 -m pytest -q` from `scraper/`
  - passed, `103 passed`

Risks:
- `workflow.prepare_workflow(...)` and `workflow.render_workflow(...)` remain as compatibility adapters for existing tests and callers; M28 intentionally changes ownership, not the public callable surface
- service-layer path constants still exist in both workflow adapters and service-owned executors by design so the workflow layer can continue injecting the current roots without changing runtime semantics

Deferred:
- no provider changes, full-run service redesign, CLI UX changes, artifact-path changes, or validation-contract changes were attempted
- `IMPLEMENT.md`, `AGENTS.md`, `README.md`, and `RULES.md` were left unchanged because M28 did not introduce a new durable operator rule or change the accepted runtime interface

## M27 — retire legacy runtime source branches and close the migration phase

Goal:
- remove the now-obsolete legacy source-routing fallback branches left behind after provider parity was proven
- keep provider-backed execution as the single active internal seam for all currently supported runtime sources
- preserve CLI/workflow commands, accepted inputs, outputs, artifact paths, and validation semantics while closing Phase 2 cleanly

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`
- `scraper/pipeline/full_run.py`
- `scraper/pipeline/tests/test_provider_selection.py`
- `scraper/pipeline/tests/test_workflow.py`

Files moved:
- none

Before/after summary:
- before:
  - all supported sources already had provider adapters, but `scraper/pipeline/full_run.py` still carried direct fetch/parser fallback branches that could bypass the provider seam if provider selection returned `None`
  - `full_run.py` also still contained one dead pre-migration section-routing branch under `if cli.sections > 0 and source != "skroutz":` that could never execute
- after:
  - `execute_full_run(...)` now fails fast with `No provider configured for supported source: ...` instead of falling back to legacy per-source fetch/parser logic
  - the dead non-provider section-routing branch was removed, leaving the live non-Skroutz section extraction path and the existing Skroutz-specific post-enrichment path intact
  - tests now lock both the supported provider map and the fail-fast no-provider behavior so the migration boundary does not regress silently

Changes:
- updated `scraper/pipeline/full_run.py` to remove the legacy direct fetch/parse branches for supported sources and require provider selection before normalization proceeds
- removed the unreachable dead source-branch duplication in the non-Skroutz section extraction block of `scraper/pipeline/full_run.py`
- added `test_resolve_provider_for_source_returns_none_for_unsupported_source` in `scraper/pipeline/tests/test_provider_selection.py` so the supported-provider map stays explicit
- added `test_execute_full_run_fails_fast_when_supported_source_has_no_provider` in `scraper/pipeline/tests/test_workflow.py` so a missing provider can no longer silently reactivate legacy runtime routing
- updated `PLAN.md` to mark M27 completed, mark Phase 2 completed, and add the Phase 3 handoff header without starting new implementation work

Commands run:
- `Get-ChildItem`
- `Get-Content PLAN.md`
- `Get-Content IMPLEMENT.md`
- `Get-Content DOCUMENTATION.md`
- `Get-Content scraper\\pipeline\\full_run.py`
- `Get-Content scraper\\pipeline\\tests\\test_workflow.py`
- `Get-Content scraper\\pipeline\\tests\\test_provider_selection.py`
- `rg -n '_resolve_provider_for_source|provider is not None|provider seam|provider-backed|legacy branch|legacy routing|source == "skroutz"|source == "manufacturer_tefal"|return None' scraper\\pipeline PLAN.md README.md IMPLEMENT.md -S`
- `rg -n 'fetch_httpx\\(|fetch_playwright\\(|ManufacturerProductParser\\(|SkroutzProductParser\\(|ElectronetProductParser\\(' scraper\\pipeline\\full_run.py scraper\\pipeline\\providers scraper\\pipeline\\tests -S`
- `Get-Content scraper\\pipeline\\source_detection.py`
- `Get-Content scraper\\pipeline\\tests\\conftest.py`
- `Get-Content scraper\\pipeline\\providers\\registry.py`
- `Get-Content scraper\\pipeline\\providers\\electronet_provider.py`
- `Get-Content scraper\\pipeline\\providers\\skroutz_provider.py`
- `Get-Content scraper\\pipeline\\providers\\manufacturer_tefal_provider.py`
- `git diff -- scraper/pipeline/full_run.py scraper/pipeline/tests/test_provider_selection.py scraper/pipeline/tests/test_workflow.py`
- `py -3.12 -m pytest -q pipeline/tests/test_provider_selection.py pipeline/tests/test_workflow.py` from `scraper/`
- `py -3.12 -m pytest -q` from `scraper/`

Validation:
- targeted migration-closure validation:
  - `py -3.12 -m pytest -q pipeline/tests/test_provider_selection.py pipeline/tests/test_workflow.py` from `scraper/`
  - passed, `21 passed`
- full suite validation:
  - `py -3.12 -m pytest -q` from `scraper/`
  - passed, `100 passed`

Risks:
- provider resolution still uses the existing private helper `_resolve_provider_for_source(...)`; M27 intentionally closes the migration by removing fallback routing rather than redesigning provider registration or widening the contract

Deferred:
- no provider-registry runtime rewrite, hybrid RAG work, service-layer redesign, CLI UX change, README change, or source-scope expansion was attempted
- `IMPLEMENT.md`, `README.md`, `AGENTS.md`, and `RULES.md` were left unchanged because no durable process rule or user-facing runtime behavior changed

## M26 — migrate supported manufacturer flows behind provider adapters

Goal:
- route the currently supported manufacturer runtime flow behind the existing provider seam without changing CLI/workflow inputs, artifact locations, metadata filenames, service contracts, or validation semantics
- address the current manufacturer enrichment weak spot reflected in the failing test baseline

Files added:
- `scraper/pipeline/providers/manufacturer_tefal_provider.py`
- `scraper/pipeline/tests/fixtures/providers/manufacturer_tefal/344709/product.html`

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`
- `scraper/pipeline/full_run.py`
- `scraper/pipeline/manufacturer_enrichment.py`
- `scraper/pipeline/providers/__init__.py`
- `scraper/pipeline/tests/test_manufacturer_enrichment.py`
- `scraper/pipeline/tests/test_provider_selection.py`
- `scraper/pipeline/tests/test_workflow.py`

Changes:
- added `ManufacturerTefalProvider` under `scraper/pipeline/providers/` as the production adapter for the currently supported manufacturer source:
  - preserves the existing live fetch order of HTTPX first, then Playwright fallback
  - reuses the existing `ManufacturerProductParser`
  - supports optional fixture HTML overrides for deterministic provider tests
- updated `scraper/pipeline/full_run.py` so `_resolve_provider_for_source(...)` now selects `ManufacturerTefalProvider` for `manufacturer_tefal` while leaving the rest of the prepare/render pipeline unchanged
- exported `ManufacturerTefalProvider` from `scraper/pipeline/providers/__init__.py`
- added a committed manufacturer provider fixture at `scraper/pipeline/tests/fixtures/providers/manufacturer_tefal/344709/product.html` so provider normalization can be tested against a stable Tefal product page sample
- updated `scraper/pipeline/tests/test_provider_selection.py` to prove:
  - Electronet, Skroutz, and the supported manufacturer source all resolve through the production provider seam
  - `ManufacturerTefalProvider.fetch_snapshot()` reads the committed fixture
  - `ManufacturerTefalProvider.normalize()` returns the expected provider/runtime result shape
- updated `scraper/pipeline/tests/test_workflow.py` so the manufacturer default-flow regression now proves provider-backed execution in production instead of the legacy direct parser branch
- made one narrow compatibility fix in `scraper/pipeline/manufacturer_enrichment.py`:
  - enrichment now tolerates official-doc adapters whose `discover(...)` implementation does not accept the optional `fetcher` keyword
  - this preserves the current enrichment contract while resolving the previously failing manufacturer framework tests
- updated `scraper/pipeline/tests/test_manufacturer_enrichment.py` to keep the manufacturer regression explicit, including the no-`fetcher` discover-signature compatibility path
- left `scraper/pipeline/parser_product_manufacturer.py`, workflow metadata, CLI/service entrypoints, output locations, and validation semantics unchanged

Commands run:
- `Get-Content PLAN.md | Select-Object -First 90`
- `Get-Content IMPLEMENT.md`
- `Get-Content DOCUMENTATION.md | Select-Object -First 180`
- `rg -n "manufacturer_tefal|ManufacturerProductParser|enrich_source_from_manufacturer_docs|provider|supported manufacturer|adapter" scraper/pipeline PLAN.md DOCUMENTATION.md -S`
- `git status --short`
- `Get-Content scraper/pipeline/full_run.py`
- `Get-Content scraper/pipeline/manufacturer_enrichment.py`
- `Get-Content scraper/pipeline/parser_product_manufacturer.py`
- `Get-Content scraper/pipeline/source_detection.py`
- `Get-Content scraper/pipeline/tests/test_manufacturer_enrichment.py`
- `Get-Content scraper/pipeline/tests/test_workflow.py | Select-Object -Skip 380 -First 140`
- `Get-Content scraper/pipeline/tests/conftest.py`
- `Get-ChildItem -Recurse scraper/pipeline/tests/fixtures/providers/manufacturer_tefal`
- `Get-Content scraper/pipeline/providers/__init__.py`
- `Get-Content scraper/pipeline/tests/test_manufacturer_enrichment_tefal.py`
- `Get-Content scraper/pipeline/tests/test_provider_selection.py`
- `Get-Content scraper/pipeline/models.py | Select-String -Pattern "class FetchResult|class ParsedProduct|class SourceProductData" -Context 0,60`
- `rg -n "_resolve_provider_for_source\\(" scraper/pipeline/tests scraper/pipeline -S`
- `python -m compileall scraper/pipeline`
- `py -3.12 -m pytest -q pipeline/tests/test_manufacturer_enrichment.py pipeline/tests/test_manufacturer_enrichment_tefal.py pipeline/tests/test_parser_product_manufacturer.py pipeline/tests/test_provider_selection.py pipeline/tests/test_workflow.py::test_execute_full_run_routes_manufacturer_tefal_through_provider_by_default` from `scraper/`
- `py -3.12 -m pytest -q` from `scraper/`
- `git status --short`
- `git diff --stat`

Validation:
- compile validation:
  - `python -m compileall scraper/pipeline`
  - passed
- targeted manufacturer validation:
  - `py -3.12 -m pytest -q pipeline/tests/test_manufacturer_enrichment.py pipeline/tests/test_manufacturer_enrichment_tefal.py pipeline/tests/test_parser_product_manufacturer.py pipeline/tests/test_provider_selection.py pipeline/tests/test_workflow.py::test_execute_full_run_routes_manufacturer_tefal_through_provider_by_default` from `scraper/`
  - passed, `17 passed`
- full suite validation:
  - `py -3.12 -m pytest -q` from `scraper/`
  - passed, `98 passed`

Risks:
- only the currently supported manufacturer runtime source is provider-backed in M26; broader manufacturer-provider expansion remains future work
- the manufacturer fixture coverage is intentionally narrow and focused on the committed Tefal regression sample, so future manufacturer providers should add their own fixture roots rather than overloading this one

Deferred:
- no service-layer redesign, workflow metadata redesign, CLI change, README change, or source-scope expansion was attempted
- no legacy manufacturer code was removed beyond the smallest runtime-routing change needed for this milestone
- `IMPLEMENT.md`, `AGENTS.md`, `RULES.md`, and `README.md` were left unchanged because no new durable process rule or accepted runtime I/O change was introduced

## M25 — route Skroutz through the provider seam in production

Goal:
- promote Skroutz from the M22 test-injected provider proof to normal runtime provider selection without changing CLI/workflow inputs, artifact locations, metadata filenames, or validation semantics

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`
- `scraper/pipeline/full_run.py`
- `scraper/pipeline/providers/skroutz_provider.py`
- `scraper/pipeline/tests/test_provider_selection.py`
- `scraper/pipeline/tests/test_skroutz_integration.py`
- `scraper/pipeline/tests/test_workflow.py`

Changes:
- updated `scraper/pipeline/full_run.py` so `_resolve_provider_for_source(...)` now selects `SkroutzProvider` for supported Skroutz product URLs in normal production flow while leaving Electronet and manufacturer routing unchanged
- extended `scraper/pipeline/providers/skroutz_provider.py` from a fixture-only proof into a production-capable provider adapter:
  - live fetch path uses the existing Skroutz runtime order of Playwright first, then HTTPX fallback
  - fixture HTML overrides remain supported for deterministic tests
  - provider metadata now reports live fetch capability while preserving the same downstream `FetchResult` and `ParsedProduct` conversion contract
- updated provider-selection tests to assert that:
  - Electronet and Skroutz both resolve through the provider seam
  - manufacturer sources still do not
  - `SkroutzProvider` can still normalize fixture-backed snapshots
  - `SkroutzProvider` uses the live fetcher path when no fixture override is configured
- updated the default workflow regression in `scraper/pipeline/tests/test_workflow.py` so Skroutz now proves provider-seam execution by default instead of the legacy branch
- updated `scraper/pipeline/tests/test_skroutz_integration.py` to assert prepare/render parity still holds for fixture-backed Skroutz workflow runs with `playwright` fetch mode preserved in the emitted report
- left `scraper/pipeline/tests/test_skroutz_sections.py` and `scraper/pipeline/tests/test_skroutz_taxonomy.py` unchanged because they already cover downstream section extraction and taxonomy behavior; they were rerun as targeted regression validation for this milestone

Commands run:
- `Get-Content PLAN.md`
- `Get-Content IMPLEMENT.md`
- `Get-Content DOCUMENTATION.md`
- `rg -n "M25|Skroutz|provider seam|_resolve_provider_for_source|SkroutzProvider|provider selection" PLAN.md IMPLEMENT.md DOCUMENTATION.md scraper -S`
- `Get-Content scraper/pipeline/full_run.py`
- `Get-Content scraper/pipeline/providers/skroutz_provider.py`
- `Get-Content scraper/pipeline/providers/__init__.py`
- `Get-Content scraper/pipeline/tests/test_provider_selection.py`
- `Get-Content scraper/pipeline/tests/test_skroutz_integration.py`
- `Get-Content scraper/pipeline/tests/test_skroutz_sections.py`
- `Get-Content scraper/pipeline/tests/test_skroutz_taxonomy.py`
- `Get-Content scraper/pipeline/tests/test_workflow.py`
- `Get-Content scraper/pipeline/providers/base.py`
- `Get-Content scraper/pipeline/providers/models.py`
- `Get-Content scraper/pipeline/providers/electronet_provider.py`
- `rg -n "provider_id|ProviderKind|FIXTURE|VENDOR_SITE|supports_identity|fetch_snapshot\\(|normalize\\(" scraper/pipeline/providers -S`
- `rg -n "_resolve_provider_for_source|legacy Skroutz|by default|skroutz provider|fetch_mode" scraper/pipeline/tests -S`
- `git status --short`
- `rg -n "_resolve_provider_for_source\\(" scraper/pipeline -S`
- `python -m compileall scraper/pipeline`
- `py -3.12 -m pytest -q pipeline/tests/test_provider_selection.py pipeline/tests/test_workflow.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_skroutz_sections.py pipeline/tests/test_skroutz_taxonomy.py` from `scraper/`
- `py -3.12 -m pytest -q` from `scraper/`
- `git status --short`

Validation:
- compile validation:
  - `python -m compileall scraper/pipeline`
  - passed
- targeted provider and Skroutz validation:
  - `py -3.12 -m pytest -q pipeline/tests/test_provider_selection.py pipeline/tests/test_workflow.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_skroutz_sections.py pipeline/tests/test_skroutz_taxonomy.py` from `scraper/`
  - passed, `34 passed`
- full suite validation:
  - `py -3.12 -m pytest -q` from `scraper/`
  - returned the accepted baseline for this milestone: `93 passed, 2 failed`
  - unchanged accepted failures:
    - `pipeline/tests/test_manufacturer_enrichment.py::test_enrichment_framework_supports_pdf_candidates`
    - `pipeline/tests/test_manufacturer_enrichment.py::test_enrichment_framework_supports_html_candidates`

Risks:
- `SkroutzProvider` now owns both live and fixture-backed fetch paths; future provider migrations should keep fixture overrides narrow so production routing changes stay observable in runtime tests
- the repo still carries the two pre-existing manufacturer-enrichment failures outside M25 scope

Deferred:
- no manufacturer provider migration was attempted
- no provider-contract redesign, registry-driven runtime rewrite, CLI change, publish-semantics change, or opportunistic cleanup was performed
- `AGENTS.md`, `IMPLEMENT.md`, `RULES.md`, and `README.md` were left unchanged because operator-facing behavior and accepted runtime I/O did not change

## M24 — stabilize the post-workdir test baseline

Goal:
- stabilize the post-M23 pytest baseline without changing runtime behavior by moving touched test baselines under `scraper/pipeline/tests/fixtures/...` and aligning workflow assertions with the live render contract

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`
- `scraper/pipeline/tests/conftest.py`
- `scraper/pipeline/tests/test_skroutz_integration.py`
- `scraper/pipeline/tests/test_skroutz_sections.py`
- `scraper/pipeline/tests/test_workflow.py`

Files added:
- `scraper/pipeline/tests/fixtures/golden_outputs/skroutz/143481.csv`
- `scraper/pipeline/tests/fixtures/golden_outputs/skroutz/307497.csv`
- `scraper/pipeline/tests/fixtures/golden_outputs/skroutz/341490.csv`
- `scraper/pipeline/tests/fixtures/golden_outputs/skroutz/344317.csv`

Changes:
- added `skroutz_golden_outputs_root` as the shared pytest fixture root for committed Skroutz golden CSV baselines
- removed the touched test-layer dependency on repo-level `products/*.csv` by copying the four committed Skroutz baseline CSVs into `scraper/pipeline/tests/fixtures/golden_outputs/skroutz/`
- updated `test_skroutz_integration.py` to seed temporary publish baselines from fixture-owned golden outputs only and to assert the live render contract:
  - candidate CSV still exists when validation fails
  - `published_csv_path` is `None` when validation is not ok
  - publish-skip warnings are surfaced in the validation report
- updated `test_skroutz_sections.py` to build its LLM payload and temporary baseline only from fixture-owned golden outputs
- updated `test_workflow.py` to assert that render still writes the full candidate bundle even when validation fails and publish is skipped
- left runtime modules unchanged because the failing behavior was test-expectation drift, not a proven workflow bug

Commands run:
- `Get-Content PLAN.md`
- `Get-Content DOCUMENTATION.md`
- `Get-Content IMPLEMENT.md`
- `rg --files scraper/pipeline/tests`
- `Get-Content scraper/pipeline/tests/conftest.py`
- `Get-Content scraper/pipeline/tests/test_workflow.py`
- `Get-Content scraper/pipeline/tests/test_skroutz_integration.py`
- `Get-Content scraper/pipeline/workflow.py`
- `Get-Content scraper/pipeline/services/run_service.py`
- `git ls-files products work scraper/work`
- `rg -n "products_root|products/.*csv|golden_outputs/skroutz" scraper/pipeline/tests`
- `py -3.12 -m pytest -q pipeline/tests/test_workflow.py::test_render_workflow_writes_candidate_bundle pipeline/tests/test_skroutz_integration.py::test_prepare_and_render_workflow_with_skroutz_fixtures pipeline/tests/test_skroutz_sections.py::test_143481_rendered_description_preserves_locked_wrappers` from `scraper/`
- `Get-Content` for the generated `233541.validation.json`, `143481.validation.json`, and matching `render.run.json` files under the temporary pytest workdirs
- `py -3.12 -m pytest -q pipeline/tests/test_workflow.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_skroutz_sections.py` from `scraper/`
- `py -3.12 -m pytest -q` from `scraper/`
- `git status --short`

Validation:
- focused failing-contract reproduction before the test updates:
  - `py -3.12 -m pytest -q pipeline/tests/test_workflow.py::test_render_workflow_writes_candidate_bundle pipeline/tests/test_skroutz_integration.py::test_prepare_and_render_workflow_with_skroutz_fixtures pipeline/tests/test_skroutz_sections.py::test_143481_rendered_description_preserves_locked_wrappers` from `scraper/`
  - result: `2 failed, 1 passed`
  - failures:
    - `pipeline/tests/test_workflow.py::test_render_workflow_writes_candidate_bundle`
    - `pipeline/tests/test_skroutz_integration.py::test_prepare_and_render_workflow_with_skroutz_fixtures`
  - both failures were stale publish expectations against a real `published_csv_path is None` contract when validation was not ok
- targeted touched-test validation after the fix:
  - `py -3.12 -m pytest -q pipeline/tests/test_workflow.py pipeline/tests/test_skroutz_integration.py pipeline/tests/test_skroutz_sections.py` from `scraper/`
  - passed, `24 passed`
- full suite validation after the fix:
  - `py -3.12 -m pytest -q` from `scraper/`
  - returned the accepted baseline: `92 passed, 2 failed`
  - unchanged accepted failures:
    - `pipeline/tests/test_manufacturer_enrichment.py::test_enrichment_framework_supports_pdf_candidates`
    - `pipeline/tests/test_manufacturer_enrichment.py::test_enrichment_framework_supports_html_candidates`

Risks:
- the committed deliverable CSVs under `products/` still exist in the repo by design; M24 only removed the touched tests' baseline dependency on them
- the full-suite baseline still includes the two long-standing manufacturer-enrichment failures outside M24 scope

Deferred:
- no runtime-code, workflow-contract, provider-routing, or CLI changes were made
- no additional fixture migration beyond the touched baseline CSVs was attempted in this milestone

## M23 — rename `scrapper/electronet_single_import` to `scraper/pipeline`

Goal:
- rename the active runtime directory and package from `scrapper/electronet_single_import` to `scraper/pipeline` without changing runtime behavior, provider behavior, CLI flags, artifact roots, metadata filenames, or workflow semantics

Directories moved:
- `scrapper/` -> `scraper/`
- `scraper/electronet_single_import/` -> `scraper/pipeline/`

Files edited:
- `README.md`
- `AGENTS.md`
- `RULES.md`
- `IMPLEMENT.md`
- `PLAN.md`
- `DOCUMENTATION.md`
- `docs/runbooks/repo-layout.md`
- `docs/checkpoints/IMPLEMENTATION_CHECKPOINT.md`
- `docs/specs/2026-03-22-pipeline-optimization-design.md`
- `scraper/README.md`
- `scraper/pipeline/cli.py`
- `scraper/pipeline/workflow.py`
- `scraper/pipeline/tests/*.py`
- `tools/capture_skroutz_fixture.py`

Changes:
- updated active runtime commands and current-state guidance from `scrapper/` plus `electronet_single_import` to `scraper/` plus `pipeline`
- updated runtime `prog=` strings so the CLI/help surface now shows `python -m pipeline.cli` and `python -m pipeline.workflow`
- updated tracked test imports and the active Skroutz fixture helper script to import from `pipeline`
- updated `IMPLEMENT.md` current path rules to `scraper/pipeline/...` and removed the stale reference to the no-longer-present `scrapper/requirements.txt` from the active dependency guardrail
- updated `PLAN.md` current repo facts, active phase summary paths, and root policy to the renamed layout and marked M23 completed
- kept prior audit and milestone evidence intact; only added a short historical clarification where needed so remaining old-name references stay explicitly historical
- added no compatibility shim because the renamed package executed cleanly with the narrow path/import updates

Commands run:
- `rg -n "scrapper/electronet_single_import|electronet_single_import|cd scrapper|python -m electronet_single_import|scrapper/" .`
- `rg -n "from electronet_single_import|import electronet_single_import|prog=\"python -m electronet_single_import|prog='python -m electronet_single_import" .`
- `rg -n "scrapper/|electronet_single_import|cd scrapper|python -m electronet_single_import" README.md AGENTS.md RULES.md PLAN.md IMPLEMENT.md DOCUMENTATION.md docs/ scraper/ scrapper/`
- `git status --short`
- directory rename command moving `scrapper/` to `scraper/` and `scraper/electronet_single_import/` to `scraper/pipeline/`
- `cd scraper && python -m pipeline.workflow --help`
- `cd scraper && python -m pipeline.cli --help`
- `python -m compileall scraper/pipeline`
- `cd scraper && python -m pytest -q`
- post-rename `rg` sweeps for active and historical references
- `git status --short`

Validation:
- `cd scraper && python -m pipeline.workflow --help`
  - passed
- `cd scraper && python -m pipeline.cli --help`
  - passed
- `python -m compileall scraper/pipeline`
  - passed
- `cd scraper && python -m pytest -q`
  - passed at the accepted baseline: `92 passed, 2 failed`
- the only accepted failing tests remained:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- post-rename sweeps confirmed active commands/docs now use `scraper/` and `pipeline`; remaining old-name hits are preserved historical references only
- the active-surface sweep over `README.md`, `AGENTS.md`, `RULES.md`, `IMPLEMENT.md`, `docs/runbooks/repo-layout.md`, `docs/checkpoints/IMPLEMENTATION_CHECKPOINT.md`, `scraper/`, and `tools/capture_skroutz_fixture.py` returned no old-name matches
- the remaining broad-sweep hits were limited to this M23 rename record, the top-level historical notes, older milestone logs, and already-labeled historical spec/audit material

Risks:
- historical docs and milestone logs still contain pre-M23 names by design; future sweeps should continue treating those sections as preserved evidence, not active guidance

Deferred:
- no compatibility shim was added
- no provider, workflow, dependency, or output-semantics changes were made

## M22 — add provider selection and one second provider proof

Goal:
- add the smallest private provider-selection seam needed to prove a second provider behind the M20 contract without changing CLI/workflow behavior, source detection, default production Skroutz routing, artifact locations, or validation semantics
- keep Electronet as the only production-selected provider and prove `SkroutzProvider` only through deterministic test injection

Files created:
- `scrapper/electronet_single_import/providers/skroutz_provider.py`
- `scrapper/electronet_single_import/tests/test_provider_selection.py`

Files edited:
- `scrapper/electronet_single_import/full_run.py`
- `scrapper/electronet_single_import/providers/__init__.py`
- `scrapper/electronet_single_import/tests/test_workflow.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Changes:
- added `SkroutzProvider` as a fixture-only provider adapter with constructor-injected fixture HTML paths only:
  - no built-in production fixture URL map
  - no live HTTP fetching
  - no Playwright fetching
- added a private `_resolve_provider_for_source(...)` helper in `scrapper/electronet_single_import/full_run.py`
- kept default production routing unchanged:
  - `electronet` resolves to `ElectronetProvider`
  - `skroutz` resolves to no provider by default and continues through the legacy Skroutz branch
  - manufacturer handling remains on the existing non-provider branch
- generalized the existing provider execution block in `full_run.py` so any resolved provider still converts back into the current `FetchResult` and `ParsedProduct` runtime shapes before downstream processing
- exported `SkroutzProvider` from `scrapper/electronet_single_import/providers/__init__.py`
- added focused provider tests that cover:
  - default resolver behavior selecting Electronet only
  - `SkroutzProvider.fetch_snapshot()` reading deterministic fixture HTML
  - `SkroutzProvider.normalize()` returning the expected provider/runtime shapes
  - test-only injection of `SkroutzProvider` through the private resolver seam
- added a workflow regression test proving Skroutz still uses the legacy runtime path by default when no override is applied
- did not change `cli.py`, `workflow.py`, `source_detection.py`, `providers/registry.py`, `providers/base.py`, `providers/models.py`, dependency files, README files, `AGENTS.md`, `RULES.md`, or `IMPLEMENT.md`

Validation:
- `python -m compileall scrapper/electronet_single_import`
  - passed
- `python -m pytest -q electronet_single_import/tests/test_provider_selection.py`
  - passed, `4 passed`
- `python -m pytest -q electronet_single_import/tests/test_workflow.py`
  - passed, `12 passed`
- `python -m pytest -q electronet_single_import/tests/test_skroutz_integration.py`
  - passed, `7 passed`
- `python -m pytest -q electronet_single_import/tests/test_skroutz_sections.py`
  - passed, `5 passed`
- `python -m pytest -q`
  - expected baseline only, `92 passed` and `2 failed`
- the only accepted failing tests remained:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`

Risks:
- the second-provider proof is intentionally test-only for Skroutz routing; production Skroutz execution still depends on the legacy branch until a later milestone adds a live provider path
- the repo still carries the two pre-existing manufacturer enrichment failures

Deferred:
- production Skroutz provider routing remains deferred
- broader provider routing for manufacturer sources remains deferred
- registry-driven runtime routing remains deferred

## M21 — extract the current primary source into a provider adapter

Goal:
- extract exactly one current primary source flow behind the M20 provider contract by routing the Electronet primary path through a concrete provider adapter without changing runtime inputs, workflow/CLI behavior, artifact locations, validation semantics, or non-Electronet execution paths

Files created:
- `scrapper/electronet_single_import/providers/electronet_provider.py`

Files edited:
- `scrapper/electronet_single_import/full_run.py`
- `scrapper/electronet_single_import/tests/test_workflow.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Primary source extracted:
- `electronet`

Integration points changed:
- `scrapper/electronet_single_import/full_run.py` now routes only the Electronet source branch through `ElectronetProvider`
- `scrapper/electronet_single_import/full_run.py` converts the provider result back into the existing `FetchResult` and `ParsedProduct` runtime shapes before the rest of the pipeline continues
- non-Electronet branches in `full_run.py` continue using the existing Skroutz and manufacturer fetch/parse logic
- `scrapper/electronet_single_import/tests/test_workflow.py` now verifies the Electronet path uses the provider adapter while preserving the existing mismatch-warning and downstream report behavior

Changes:
- added `ElectronetProvider` as the single concrete M21 adapter, with provider metadata aligned to the M20 contract:
  - provider id `electronet`
  - source name `electronet`
  - provider kind `vendor_site`
  - capabilities `url_input`, `live_fetch`, `html_snapshot`, and `normalized_product`
- moved the existing Electronet-only fetch/normalize seam into the provider without widening the M20 contract
- preserved the current Electronet fetch order inside the provider:
  - try HTTPX first
  - fall back to Playwright on fetch failure
- preserved the current Electronet critical-missing recovery inside the provider:
  - if the initial parse still has `critical_missing`, rerun a Playwright fetch and reparse
  - only replace the first parse when the fallback reduces the critical-missing count
- stored fetch-only details not modeled directly by `ProviderSnapshot` in `snapshot.metadata`, specifically `fetch_method` and `fallback_used`
- kept the downstream runtime behavior unchanged by translating the provider result back into the existing local execution models before taxonomy resolution, schema matching, artifact writing, and validation
- left source detection, URL-scope validation, workflow entrypoints, CLI/service entrypoints, Skroutz extraction, and manufacturer enrichment behavior unchanged
- did not add provider selection, registry-driven runtime routing, or a second provider

Commands run:
- `Get-ChildItem -Force`
- `rg --files AGENTS.md RULES.md IMPLEMENT.md PLAN.md DOCUMENTATION.md scrapper/electronet_single_import`
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content IMPLEMENT.md`
- `rg -n "M20|M21|provider" PLAN.md DOCUMENTATION.md scrapper/electronet_single_import/providers scrapper/electronet_single_import/full_run.py scrapper/electronet_single_import/services/run_service.py scrapper/electronet_single_import/workflow.py`
- `Get-Content scrapper/electronet_single_import/providers/models.py`
- `Get-Content scrapper/electronet_single_import/providers/base.py`
- `Get-Content scrapper/electronet_single_import/providers/registry.py`
- `Get-Content scrapper/electronet_single_import/providers/__init__.py`
- `Get-Content scrapper/electronet_single_import/full_run.py`
- `Get-Content scrapper/electronet_single_import/source_detection.py`
- `Get-Content scrapper/electronet_single_import/services/run_service.py`
- `Get-Content scrapper/electronet_single_import/workflow.py`
- `Get-Content scrapper/electronet_single_import/parser_product_electronet.py`
- `Get-Content scrapper/electronet_single_import/fetcher.py`
- `Get-Content scrapper/electronet_single_import/parser_product_skroutz.py`
- `Get-Content scrapper/electronet_single_import/parser_product_manufacturer.py`
- `rg -n "execute_full_run|detect_source\(|manufacturer_tefal" scrapper/electronet_single_import`
- `rg -n "electronet" scrapper/electronet_single_import/tests`
- `Get-Content scrapper/electronet_single_import/tests/test_workflow.py`
- `Get-Content scrapper/electronet_single_import/tests/test_services.py`
- `Get-Content PLAN.md | Select-Object -First 120`
- `Get-Content DOCUMENTATION.md | Select-Object -First 120`
- `git status --short`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q scrapper/electronet_single_import/tests/test_workflow.py`
- `python -m pytest -q` from `scrapper/`
- `python -m pytest -q scrapper/electronet_single_import/tests/test_workflow.py scrapper/electronet_single_import/tests/test_skroutz_integration.py scrapper/electronet_single_import/tests/test_skroutz_sections.py`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q` from `scrapper/`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded before and after the final fix
- targeted validation succeeded:
  - `python -m pytest -q scrapper/electronet_single_import/tests/test_workflow.py` returned `11 passed`
  - `python -m pytest -q scrapper/electronet_single_import/tests/test_workflow.py scrapper/electronet_single_import/tests/test_skroutz_integration.py scrapper/electronet_single_import/tests/test_skroutz_sections.py` returned `23 passed`
- `python -m pytest -q` from `scrapper/` returned `87 passed, 2 failed`
- the only accepted failing tests remained:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- one intermediate M21 regression in the Skroutz branch was introduced during extraction and then fixed in `full_run.py`; no new failures remained after the fix

Risks:
- the provider seam is still only proven for the Electronet primary source; runtime provider selection and secondary-provider support remain unimplemented until M22
- the repo still carries the two pre-existing manufacturer enrichment failures

Deferred:
- provider selection and registry-driven runtime routing remain M22 work
- adding a second concrete provider remains M22 work
- expanding provider-based routing beyond the Electronet branch remains deferred
- no changes were made to `cli.py`, `input_validation.py`, `source_detection.py`, dependency files, README files, `AGENTS.md`, `RULES.md`, or `IMPLEMENT.md`

## M20 — define provider contract and registry

Goal:
- define a narrow internal provider abstraction and registration seam for future manufacturer, vendor-site, and fixture-backed adapters without changing current runtime behavior, source detection, workflow wiring, or CLI entrypoints

Files created:
- `scrapper/electronet_single_import/providers/__init__.py`
- `scrapper/electronet_single_import/providers/base.py`
- `scrapper/electronet_single_import/providers/models.py`
- `scrapper/electronet_single_import/providers/registry.py`

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`

Contract elements added:
- `ProviderDefinition` with provider identifier, emitted `source_name`, provider kind, and capability declaration
- `ProviderInputIdentity` with typed optional identity fields for `model`, `url`, `sku`, `brand`, `vendor_code`, `mpn`, and extensible extras
- `ProviderSnapshot` with fetch/snapshot fields for requested and final URL, snapshot kind, content type, status, headers, and text/byte payloads
- `ProviderResult` with normalized product output anchored to current `SourceProductData` plus provenance, field diagnostics, missing-field tracking, warnings, and overall confidence
- `ProviderErrorInfo` and `ProviderError` with structured provider error code, stage, retryability, and details
- `ProductProvider` abstract base contract with `fetch_snapshot(...)` and `normalize(...)`
- `ProviderRegistry` with explicit provider registration, lookup, required lookup, and definition listing

Changes:
- added a new standalone `scrapper/electronet_single_import/providers/` package so the provider seam exists without touching current execution modules
- kept the normalized provider output aligned to the current parser/runtime shape by reusing `SourceProductData` and `FieldDiagnostic` instead of inventing a second normalization model
- separated provider type from runtime source naming via `ProviderKind` and `ProviderDefinition.source_name`
- made the contract broad enough for future vendor-site, manufacturer-site, and fixture-backed adapters through explicit kind, capability, identity, and snapshot enums
- added structured provider error metadata for identity, fetch, normalize, and registry stages
- added a simple in-memory registry for provider registration and lookup only
- did not add any concrete provider adapters
- did not route source detection, `full_run.py`, CLI entrypoints, workflow entrypoints, or the service layer through the new provider package

Commands run:
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content IMPLEMENT.md`
- `Get-Content PLAN.md`
- `Get-Content DOCUMENTATION.md`
- `Get-Content scrapper/electronet_single_import/source_detection.py`
- `Get-Content scrapper/electronet_single_import/full_run.py`
- `Get-Content scrapper/electronet_single_import/input_validation.py`
- `Get-Content scrapper/electronet_single_import/services/models.py`
- `Get-Content scrapper/electronet_single_import/services/errors.py`
- `Get-Content scrapper/electronet_single_import/services/run_service.py`
- `Get-ChildItem scrapper/electronet_single_import -File | Select-Object -ExpandProperty Name`
- `rg -n "class Parsed|class .*Source|@dataclass|provenance|confidence|page_type|source_name|critical_missing|field_diagnostics|spec_sections|gallery_images|presentation_source_html|manufacturer_enrichment" scrapper/electronet_single_import -g "*.py"`
- `Get-Content scrapper/electronet_single_import/models.py`
- `Get-Content scrapper/electronet_single_import/manufacturer_enrichment.py`
- `Get-Content scrapper/electronet_single_import/parser_product_electronet.py`
- `Get-Content scrapper/electronet_single_import/parser_product_skroutz.py`
- `Get-Content scrapper/electronet_single_import/parser_product_manufacturer.py`
- `Get-Content scrapper/electronet_single_import/providers/models.py`
- `Get-Content scrapper/electronet_single_import/providers/base.py`
- `Get-Content scrapper/electronet_single_import/providers/registry.py`
- `Get-Content scrapper/electronet_single_import/providers/__init__.py`
- `rg -n "Current milestone|M20|Phase 2 milestones" PLAN.md DOCUMENTATION.md`
- `Get-Content PLAN.md | Select-Object -First 90`
- `Get-Content DOCUMENTATION.md | Select-Object -First 80`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q` from `scrapper/`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q` from `scrapper/` returned `87 passed, 2 failed`
- the only accepted failing tests remained:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- no new failures were introduced by M20

Risks:
- the new provider contract is intentionally unwired, so it still depends on later milestones to prove adapter extraction and runtime selection
- the repo still carries the two pre-existing manufacturer enrichment failures

Deferred:
- extracting the current Electronet/Skroutz/manufacturer logic into concrete provider adapters remains M21+
- wiring provider selection into runtime behavior remains M22
- provider-contract tests were intentionally deferred in M20 to keep the milestone inside the approved file scope and because the package is currently import-safe and unused by runtime code

## M19a — remove remaining cross-layer imports after service routing

Goal:
- remove the remaining cross-layer imports between `cli.py`, `workflow.py`, and `full_run.py` without changing commands, flags, validation behavior, artifact paths, metadata filenames, or exit semantics

Files created:
- `scrapper/electronet_single_import/input_validation.py`

Files edited:
- `scrapper/electronet_single_import/cli.py`
- `scrapper/electronet_single_import/full_run.py`
- `scrapper/electronet_single_import/tests/test_skroutz_sections.py`
- `scrapper/electronet_single_import/workflow.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Changes:
- moved shared `FAIL_MESSAGE` and `validate_input(...)` into the neutral module `scrapper/electronet_single_import/input_validation.py`
- updated `cli.py` to import validation from the neutral module and removed its unused import of `_select_skroutz_image_backed_sections` from `full_run.py`
- updated `workflow.py` to import `FAIL_MESSAGE` and `validate_input(...)` from the neutral module instead of from `cli.py`
- updated `full_run.py` to import `FAIL_MESSAGE` from the neutral module so it remains an execution module rather than a shared constants bucket
- updated `test_skroutz_sections.py` to import `_select_skroutz_image_backed_sections` from its actual lower-layer owner, `full_run.py`
- kept `execute_full_run(...)` in `full_run.py` and left service-layer contracts unchanged

Cross-layer imports removed:
- `scrapper/electronet_single_import/cli.py` no longer imports `FAIL_MESSAGE` or `_select_skroutz_image_backed_sections` from `scrapper/electronet_single_import/full_run.py`
- `scrapper/electronet_single_import/workflow.py` no longer imports `FAIL_MESSAGE` or `validate_input(...)` from `scrapper/electronet_single_import/cli.py`

Commands run:
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content IMPLEMENT.md`
- `Get-Content scrapper/electronet_single_import/cli.py`
- `Get-Content scrapper/electronet_single_import/workflow.py`
- `Get-Content scrapper/electronet_single_import/full_run.py`
- `Get-Content scrapper/electronet_single_import/services/run_service.py`
- `Get-Content scrapper/electronet_single_import/models.py`
- `Get-Content PLAN.md`
- `Get-Content DOCUMENTATION.md`
- `rg -n "FAIL_MESSAGE|validate_input|_select_skroutz_image_backed_sections|execute_full_run|from \\.cli|from \\.full_run" scrapper/electronet_single_import -g "*.py"`
- `Get-Content scrapper/electronet_single_import/tests/test_workflow.py`
- `Get-Content scrapper/electronet_single_import/tests/test_services.py`
- `Get-Content scrapper/electronet_single_import/tests/test_skroutz_sections.py`
- `Get-Content scrapper/electronet_single_import/tests/test_skroutz_integration.py`
- `rg -n "from electronet_single_import\\.cli import _select_skroutz_image_backed_sections|from \\.full_run import FAIL_MESSAGE|from \\.cli import FAIL_MESSAGE, validate_input" scrapper/electronet_single_import/tests scrapper/electronet_single_import -g "*.py"`
- `rg -n "Current milestone|M19 —|M20|M19a" PLAN.md DOCUMENTATION.md`
- `Get-Content PLAN.md -TotalCount 80`
- `Get-Content DOCUMENTATION.md -TotalCount 120`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q electronet_single_import/tests/test_workflow.py electronet_single_import/tests/test_services.py electronet_single_import/tests/test_skroutz_integration.py electronet_single_import/tests/test_skroutz_sections.py` from `scrapper/`
- `python -m pytest -q` from `scrapper/`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_workflow.py electronet_single_import/tests/test_services.py electronet_single_import/tests/test_skroutz_integration.py electronet_single_import/tests/test_skroutz_sections.py` from `scrapper/` passed with `29 passed`
- `python -m pytest -q` from `scrapper/` returned `87 passed, 2 failed`
- the only accepted failing tests remained:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- `git status --short` showed only the expected M19a edits plus the new neutral helper module

Risks:
- the repo still carries the two pre-existing manufacturer enrichment failures
- `cli.py` still re-exports `validate_input(...)` by import for backward-compatible test and caller access, but the implementation now lives in the neutral module rather than in the CLI layer

Deferred:
- no service-layer files were changed because the boundary cleanup did not require contract adjustments
- no provider abstraction work was started; that remains M20

## M19 — route CLI through the service layer

Goal:
- refactor the CLI-facing entrypoints to call the M18 service layer instead of duplicating orchestration logic, while preserving command names, flags, exit semantics, artifact locations, metadata filenames, and provider behavior

Files edited:
- `scrapper/electronet_single_import/cli.py`
- `scrapper/electronet_single_import/full_run.py`
- `scrapper/electronet_single_import/services/run_service.py`
- `scrapper/electronet_single_import/tests/test_services.py`
- `scrapper/electronet_single_import/tests/test_workflow.py`
- `scrapper/electronet_single_import/workflow.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Changes:
- extracted the pre-existing standalone full-run implementation into the lower-layer module `scrapper/electronet_single_import/full_run.py`
- changed `run_cli_input()` into a thin CLI adapter that builds `FullRunRequest` and calls `run_product()`
- restored `run_product()` to orchestrate below the CLI layer through `prepare_product()` and `render_product()` rather than calling anything in `cli.py`
- kept `FullRunRequest.out` so the CLI adapter can pass output-root intent into the service layer without inverting module dependencies
- routed `python -m electronet_single_import.workflow prepare` through `prepare_product()` and `python -m electronet_single_import.workflow render` through `render_product()`
- updated `prepare_workflow()` to use the extracted lower-layer executor instead of importing standalone CLI orchestration
- added focused tests that verify CLI-to-service routing and that the service layer composes stage services without importing `cli.py`

Commands run:
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content scrapper/electronet_single_import/cli.py`
- `Get-Content scrapper/electronet_single_import/workflow.py`
- `Get-ChildItem scrapper/electronet_single_import/services -Recurse -File | Select-Object -ExpandProperty FullName`
- `Get-Content PLAN.md`
- `Get-Content DOCUMENTATION.md`
- `Get-Content scrapper/electronet_single_import/services/prepare_service.py`
- `Get-Content scrapper/electronet_single_import/services/render_service.py`
- `Get-Content scrapper/electronet_single_import/services/run_service.py`
- `Get-Content scrapper/electronet_single_import/services/models.py`
- `rg -n "run_cli_input\\(|prepare_workflow\\(|render_workflow\\(|prepare_product\\(|render_product\\(|run_product\\(" scrapper/electronet_single_import -g "*.py"`
- `Get-Content scrapper/electronet_single_import/services/__init__.py`
- `Get-Content scrapper/electronet_single_import/services/errors.py`
- `Get-Content scrapper/electronet_single_import/tests/test_services.py`
- `Get-Content scrapper/electronet_single_import/tests/test_workflow.py`
- `rg -n "def test_.*main|cli\\.main\\(|workflow\\.main\\(" scrapper/electronet_single_import/tests -g "*.py"`
- `git status --short`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q electronet_single_import/tests/test_services.py electronet_single_import/tests/test_workflow.py` from `scrapper/`
- `python -m pytest -q` from `scrapper/`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_services.py electronet_single_import/tests/test_workflow.py` from `scrapper/` passed with `17 passed`
- `python -m pytest -q` from `scrapper/` returned `87 passed, 2 failed`
- the only accepted failing tests remained:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- no new unexpected failures were introduced by M19

Risks:
- the repo still carries the two pre-existing manufacturer enrichment failures
- standalone CLI metadata emission still remains a CLI concern because the service layer intentionally does not emit `full.run.json`

Deferred:
- no provider-contract work was started; that remains M20
- no dependency files, provider logic, README files, `AGENTS.md`, `RULES.md`, or `IMPLEMENT.md` were changed

## M18 — add service layer models/errors/wrappers

Goal:
- add a thin internal service layer around the existing prepare/render workflow stages using the M15 contract and M16/M17 stage metadata, without rerouting CLI entrypoints, changing workflow semantics, or introducing new runtime artifact or metadata filenames

Files created:
- `scrapper/electronet_single_import/services/errors.py`
- `scrapper/electronet_single_import/services/prepare_service.py`
- `scrapper/electronet_single_import/services/render_service.py`
- `scrapper/electronet_single_import/services/run_service.py`
- `scrapper/electronet_single_import/tests/test_services.py`

Files edited:
- `scrapper/electronet_single_import/services/__init__.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Service entrypoints added:
- `prepare_product(request: PrepareRequest) -> ServiceResult`
- `render_product(request: RenderRequest) -> ServiceResult`
- `run_product(request: FullRunRequest) -> ServiceResult`

Changes:
- added a small internal `ServiceError` wrapper with stable `code`, `message`, and optional `cause`
- added `prepare_product()` as a thin wrapper over `workflow.prepare_workflow()` that converts the M15 request into `CLIInput`, reuses the existing prepare-stage metadata file, and returns a `ServiceResult` with scrape/prompt artifact paths
- added `render_product()` as a thin wrapper over `workflow.render_workflow()` that reuses the existing render-stage metadata file and returns a `ServiceResult` with candidate and validation artifact paths
- added `run_product()` as an internal composition layer over `prepare_product()` then `render_product()` and kept full-run aggregation inside `ServiceResult.details`
- did not emit `full.run.json` from the new service layer
- did not modify `cli.py`
- did not modify `workflow.py`
- kept runtime behavior unchanged by leaving CLI entrypoints, workflow semantics, output locations, provider logic, and metadata filenames untouched

Commands run:
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content scrapper/electronet_single_import/workflow.py`
- `Get-Content scrapper/electronet_single_import/services/__init__.py`
- `Get-Content scrapper/electronet_single_import/services/models.py`
- `Get-Content scrapper/electronet_single_import/services/metadata.py`
- `Get-Content scrapper/electronet_single_import/models.py`
- `Get-Content scrapper/electronet_single_import/tests/test_workflow.py`
- `rg -n "class CLIInput|@dataclass\\(.*CLIInput|CLIInput\\(" scrapper/electronet_single_import/models.py scrapper/electronet_single_import -g "*.py"`
- `rg --files scrapper/electronet_single_import/tests`
- `rg -n "class .*Error|ServiceError|error_code|run_status" scrapper/electronet_single_import -g "*.py"`
- `Get-Content PLAN.md -TotalCount 90`
- `Get-Content DOCUMENTATION.md -TotalCount 120`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q electronet_single_import/tests/test_services.py` from `scrapper/`
- `python -m pytest -q` from `scrapper/`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_services.py` from `scrapper/` passed with `6 passed`
- `python -m pytest -q` from `scrapper/` returned `84 passed, 2 failed`
- the only known failing tests remained:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- no new unexpected test failures were introduced by M18

Risks:
- the full suite still has the two pre-existing manufacturer enrichment failures
- the service layer currently returns aggregated full-run metadata paths through `ServiceResult.details`, not a dedicated full-run metadata artifact, by design for M18

Deferred:
- routing CLI entrypoints through the service layer remains deferred to M19
- no new runtime metadata file is emitted for `run_product()` in M18
- no workflow or CLI refactor beyond the additive service wrapper layer was performed in M18

## M17 — make CLI/workflow emit metadata

Goal:
- make the current CLI and workflow surfaces emit a structured run status and metadata file path without changing command names, flags, exit codes, workflow semantics, or existing artifact locations

Files edited:
- `scrapper/electronet_single_import/cli.py`
- `scrapper/electronet_single_import/services/metadata.py`
- `scrapper/electronet_single_import/workflow.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Changes:
- promoted the metadata write helper into `scrapper/electronet_single_import/services/metadata.py` so both CLI and workflow can reuse the same run-status and metadata serialization path
- kept `prepare_workflow()` and `render_workflow()` additive-only by returning `run_status` alongside the existing result fields
- updated `python -m electronet_single_import.workflow prepare` to print the completed run status and the emitted `prepare.run.json` path after the existing scrape/prompt artifact lines
- updated `python -m electronet_single_import.workflow render` to print the completed run status and the emitted `render.run.json` path after the existing candidate/validation lines
- added best-effort standalone CLI metadata emission as `full.run.json` in the current CLI output model directory and surfaced its run status plus metadata path in the CLI output
- kept existing CLI flags, command names, exit-code behavior, workflow artifact locations, provider behavior, and validation semantics unchanged

Commands run:
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content scrapper/electronet_single_import/cli.py`
- `Get-Content scrapper/electronet_single_import/workflow.py`
- `Get-Content scrapper/electronet_single_import/services/models.py`
- `Get-Content scrapper/electronet_single_import/services/metadata.py`
- `Get-Content PLAN.md`
- `Get-Content DOCUMENTATION.md`
- `rg -n "metadata_path|RunStatus|prepare_workflow\\(|render_workflow\\(|Validation ok|LLM context:|Candidate CSV:" scrapper/electronet_single_import/tests scrapper/electronet_single_import`
- `Get-Content scrapper/electronet_single_import/tests/test_workflow.py`
- `rg -n "M17|emit metadata|run status|metadata path" PLAN.md DOCUMENTATION.md scrapper/electronet_single_import -g "*.md" -g "*.py"`
- `rg -n "electronet_single_import\\.cli|python -m electronet_single_import\\.cli|--out" README.md scrapper/README.md scrapper/electronet_single_import/tests -g "*.md" -g "*.py"`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q` from `scrapper/`
- `python -m pytest -q electronet_single_import/tests/test_workflow.py` from `scrapper/`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_workflow.py` from `scrapper/` passed with `8 passed`
- `python -m pytest -q` from `scrapper/` returned `78 passed, 2 failed`
- unchanged accepted failing tests:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- `git status --short` showed only the expected M17 edits

Risks:
- no new test failures were introduced by M17
- standalone CLI metadata now adds one new sidecar file, `full.run.json`, under the existing CLI output model directory; existing artifacts and paths remain unchanged

Deferred:
- no CLI UX redesign beyond the additive status and metadata-path lines
- service-layer wrappers and CLI routing through that layer remain deferred to M18-M19
- no test-file changes were made in M17; coverage for the new surface lines still relies on compile, existing workflow tests, and the unchanged full-suite baseline

## M16 — write structured run metadata alongside current files

Goal:
- emit structured metadata sidecar files for the current prepare and render workflow stages without changing existing artifact contents or runtime semantics

Files created:
- `scrapper/electronet_single_import/services/metadata.py`

Files edited:
- `scrapper/electronet_single_import/workflow.py`
- `scrapper/electronet_single_import/tests/test_workflow.py`
- `PLAN.md`
- `DOCUMENTATION.md`

Metadata files emitted by stage:
- `work/{model}/prepare.run.json`
- `work/{model}/render.run.json`

Changes:
- added metadata serialization and writing helpers in `scrapper/electronet_single_import/services/metadata.py`
- used the M15 run contract models as the metadata source shape
- wrote prepare metadata after prompt artifacts are emitted and render metadata after candidate artifacts are emitted
- added best-effort failed-run metadata emission when prepare or render raise after the model work directory is known
- kept existing workflow artifact filenames, locations, and CLI output formatting unchanged
- updated `PLAN.md` to mark M16 complete and note metadata emission

Commands run:
- `Get-Content scrapper/electronet_single_import/workflow.py`
- `Get-Content scrapper/electronet_single_import/cli.py`
- `Get-Content scrapper/electronet_single_import/services/models.py`
- `Get-Content scrapper/electronet_single_import/tests/test_workflow.py`
- `python -m pytest -q electronet_single_import/tests/test_workflow.py` from `scrapper/`
- `python -m pytest -q` from `scrapper/`
- `python -m compileall scrapper/electronet_single_import`
- `git status --short`

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_workflow.py` from `scrapper/` passed
- `python -m pytest -q` from `scrapper/` returned `78 passed, 2 failed`
- unchanged failing tests:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
- `git status --short` confirmed the expected M16 file changes

Risks:
- no new M16 failures were introduced; the only remaining failures are the pre-existing manufacturer enrichment tests
- the full-suite pass count increased from `76` to `78` because M16 added two focused workflow metadata tests while keeping the same two known failing tests

Deferred:
- CLI-facing metadata output changes remain deferred to M17
- service-layer wrappers and routing remain deferred to later milestones
- no metadata is emitted for failures that occur before a model work directory can be determined
  - this preserves current runtime behavior while keeping metadata writing best-effort

## M15 — define run contract

Goal:
- add import-safe run contract models for future service, metadata, CLI, and API seams without changing current runtime behavior

Files created:
- `scrapper/electronet_single_import/services/__init__.py`
- `scrapper/electronet_single_import/services/models.py`

Files edited:
- `PLAN.md`
- `DOCUMENTATION.md`

Models added:
- `RunType`
- `RunStatus`
- `PrepareRequest`
- `RenderRequest`
- `FullRunRequest`
- `RunArtifacts`
- `RunMetadata`
- `ServiceResult`

Changes:
- created the new `scrapper/electronet_single_import/services/` package as import-safe package setup only
- added contract-only dataclass and enum definitions in `scrapper/electronet_single_import/services/models.py`
- included the planned `metadata_path` artifact field so M16 can emit metadata without reshaping the contract
- kept metadata-facing warnings and error fields on `RunMetadata`
- kept `ServiceResult` lean with only `run`, `artifacts`, and `details`
- updated `PLAN.md` to mark M15 complete and note that the run contract exists but is not wired into runtime behavior

Validation:
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q` from `scrapper/` did not match the requested baseline and finished at `69 passed, 9 failed`
- failing tests:
  - `test_enrichment_framework_supports_pdf_candidates`
  - `test_enrichment_framework_supports_html_candidates`
  - `test_skroutz_parser_and_deterministic_fields_cover_supported_families`
  - `test_prepare_and_render_workflow_with_skroutz_fixtures`
  - `test_143481_html_fixture_resolves_9_sections_in_stable_order`
  - `test_placeholder_urls_are_rejected_for_resolved_section_images`
  - `test_143481_rendered_description_preserves_locked_wrappers`
  - `test_taxonomy_regression_fixture_resolves_expected_categories`
  - `test_representative_taxonomy_html_fixtures_cover_supported_skroutz_combos`
- `git status --short` confirmed only the expected milestone files changed, alongside the pre-existing untracked `.claude/worktrees/`

Risks:
- the current repo test baseline does not match the milestone's expected `75 passed, 2 failed` result
- seven additional Skroutz fixture-path failures are present in `test_skroutz_integration.py`, `test_skroutz_sections.py`, and `test_skroutz_taxonomy.py`, all failing with `FileNotFoundError` against hardcoded absolute fixture paths outside the current workspace
- the two existing manufacturer enrichment failures remain in `test_manufacturer_enrichment.py`

Deferred:
- metadata emission and file writing remain deferred to M16
- runtime wiring for CLI and workflow remains deferred to later milestones
- serializers, validators, helper methods, and service wrappers remain intentionally out of scope for M15

## Pre-M15 control-doc refresh

Goal:
- align repository control documents with the post-cleanup architecture phase
- remove cleanup-only ambiguity before M15-M22
- separate milestone governance from runtime execution guidance

Files edited:
- `PLAN.md`
- `IMPLEMENT.md`
- `DOCUMENTATION.md`
- `AGENTS.md`
- `RULES.md`

Changes:
- promoted `PLAN.md` from cleanup-only framing to full active roadmap framing
- added the Phase 2 architecture milestones M15-M22
- added explicit hybrid-RAG gating
- updated `IMPLEMENT.md` to govern milestone execution for the new phase
- updated `AGENTS.md` and `RULES.md` so runtime input scope matches the actual code-supported source scope
- marked M15 as the next active milestone

Validation:
- docs-only review
- no runtime files changed
- no dependency files changed

Risks:
- none for runtime behavior; this commit changes guidance only

Deferred:
- `README.md` refresh
- any user-facing architecture overview
- milestone-specific implementation entries starting at M15

## Historical reference note
- Completed milestone entries, audit summaries, and command logs below preserve prior-state file paths intentionally.
- When older sections mention paths such as `docs/superpowers/specs/...`, `work/IMPLEMENTATION_CHECKPOINT.md`, root support-asset filenames, `RULES_legacy.md`, `master_prompt_legacy.txt`, or `scrapper/requirements.txt`, read them as historical pre-M4, pre-M5, pre-M6, or pre-M10 references unless the section explicitly states current guidance.

## Repo invariants
- Active runnable code lives under `scrapper/electronet_single_import/`.
- `products/` remains the final CSV/output area.
- `work/{model}/...` remains the runtime artifact area.
- Legacy files must be archived, not deleted casually.
- Shared support assets now live under `resources/` and remain centrally resolved through `scrapper/electronet_single_import/repo_paths.py`.

## Milestone log

### M1 — Control files and cleanup directories
Status: completed
Goal:
- add approved scaffolding directories and log the milestone without changing runtime behavior

Changes:
- created `docs/audits/`, `docs/runbooks/`, `docs/checkpoints/`, `docs/specs/`, `archive/legacy/`, `resources/mappings/`, `resources/prompts/`, `resources/schemas/`, and `resources/templates/`
- added `.gitkeep` in each created target directory because it would otherwise remain empty and would not appear in Git status
- updated `PLAN.md` to mark M1 complete and record that the control docs already existed before execution
- updated `DOCUMENTATION.md` with milestone results, commands, validation, risks, and follow-up

Validation:
- pre-creation filesystem check confirmed all nine approved target directories were absent
- post-creation filesystem check confirmed all nine approved target directories exist, each contains `.gitkeep`, and no extra contents were added
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- `PLAN.md`, `IMPLEMENT.md`, and `DOCUMENTATION.md` already existed before M1; this milestone did not recreate them
- `IMPLEMENT.md` was intentionally not edited because no new recurring execution rule was discovered
- scraper smoke validation was intentionally skipped because pathing and runtime behavior were unchanged
- current repo-root support assets remain in place as source-of-truth files
- empty directories alone would not appear in Git status without `.gitkeep`

### M2 — Repo cleanup audit
Status: completed
Goal:
- classify root files and cleanup candidates

Changes:
- created `docs/audits/repo_cleanup_audit.md`
- classified every current root-level file into `keep in root`, `move later after path centralization`, `archive as legacy`, or `uncertain`
- explicitly classified `schemas/compact_response.schema.json` as `move later after path centralization`
- explicitly classified `docs/specs/2026-03-22-pipeline-optimization-design.md` and `docs/checkpoints/IMPLEMENTATION_CHECKPOINT.md` as safe `move now` candidates
- documented evidence for non-obvious classifications from runtime path callsites and current repo docs
- updated `PLAN.md` to mark M2 complete

Validation:
- root inventory and candidate existence checks completed
- `rg` evidence sweep completed for every explicitly named file or candidate
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no requested classification was downgraded to `uncertain` due to contradictory live evidence in this pass
- `requirements.txt` remains `uncertain` and is intentionally postponed to the dependency audit milestone
- scraper smoke validation was intentionally skipped because pathing and runtime behavior were unchanged
- no files were moved or deleted in this milestone

### M3 — Path centralization
Status: completed
Goal:
- add `repo_paths.py` and remove scattered support-file path assumptions

Changes:
- created `scrapper/electronet_single_import/repo_paths.py`
- replaced these approved direct support-asset path constructions in `scrapper/electronet_single_import/utils.py`: `PRODUCT_TEMPLATE_PATH`, `PRESENTATION_TEMPLATE_PATH`, `CATALOG_TAXONOMY_PATH`, `SCHEMA_LIBRARY_PATH`, `CHARACTERISTICS_TEMPLATES_PATH`, `FILTER_MAP_PATH`, `NAME_RULES_PATH`, `DIFFERENTIATOR_PRIORITY_MAP_PATH`, `MASTER_PROMPT_PATH`, `COMPACT_RESPONSE_SCHEMA_PATH`, and `MANUFACTURER_SOURCE_MAP_PATH`
- kept the existing path constant names available from `utils.py` so downstream modules did not need churn
- updated `scrapper/electronet_single_import/tests/test_utils_support_paths.py` to validate centralized path resolution from `repo_paths.py`
- updated `PLAN.md` to mark M3 complete without changing the asset locations

Validation:
- pre-edit `rg` confirmed the approved direct support-asset callsites were in `scrapper/electronet_single_import/utils.py`
- post-edit `rg` confirmed the approved support-asset filename literals are now owned by `scrapper/electronet_single_import/repo_paths.py`
- `python -m pytest -q electronet_single_import/tests/test_utils_support_paths.py` from `scrapper/` passed
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- unresolved out-of-scope direct path assumptions remain in `scrapper/electronet_single_import/workflow.py` for `work/` and `products/`
- hardcoded absolute repo paths remain in some tests and were intentionally left out of scope for this milestone
- scraper smoke validation was intentionally skipped because pytest plus code inspection was sufficient for this path-only change
- no support assets were moved or renamed

### M4 — Safe docs/checkpoint moves
Status: completed
Goal:
- move the two approved non-runtime documentation and planning files out of their old locations without changing runtime behavior

Changes:
- moved the pipeline optimization design doc into `docs/specs/2026-03-22-pipeline-optimization-design.md`
- moved the implementation checkpoint into `docs/checkpoints/IMPLEMENTATION_CHECKPOINT.md`
- updated path references in `PLAN.md`, `DOCUMENTATION.md`, and `docs/audits/repo_cleanup_audit.md`

Validation:
- pre-move checks confirmed both source files existed and both destination files were absent
- post-move checks confirmed the old source files no longer exist and the new destination files do exist
- `rg` for the old paths returned no remaining references after the updates
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no runtime code was edited
- no support assets were moved
- scraper smoke validation was intentionally skipped because no runtime pathing or behavior changed
- empty directories were intentionally left in place because they may still be part of the intended docs/work scaffolding
- the remaining old-path mentions are intentionally preserved in the command log as historical execution records

### M5 — Legacy archive move
Status: completed
Goal:
- archive the two approved historical reference files without changing runtime behavior

Changes:
- moved `RULES_legacy.md` to `archive/legacy/RULES_legacy.md`
- moved `master_prompt_legacy.txt` to `archive/legacy/master_prompt_legacy.txt`
- removed `archive/legacy/.gitkeep` because the archive directory now contains real files
- updated path references in `PLAN.md`, `DOCUMENTATION.md`, `RULES.md`, `docs/audits/repo_cleanup_audit.md`, and `archive/legacy/master_prompt_legacy.txt`

Validation:
- pre-move checks confirmed both source files existed and both archive destinations were absent
- post-move checks confirmed the old source files no longer exist and the new archive paths do exist
- `rg` for the old paths returned no remaining references outside intentional historical command-log mentions
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no runtime code was edited
- no active support assets were moved
- scraper smoke validation was intentionally skipped because no runtime pathing or behavior changed
- no additional files were archived in this milestone

### M6 — Support asset relocation into `resources/`
Status: completed

### M7 — Documentation normalization
Status: completed

### M8 — Dependency audit
Status: completed

### M9 — Final health pass
Status: completed

## M6 detail
Goal:
- move the approved shared support assets into `resources/` without changing runtime behavior

Changes:
- moved `MANUFACTURER_SOURCE_MAP.json`, `catalog_taxonomy.json`, `filter_map.json`, `name_rules.json`, `differentiator_priority_map.csv`, and `taxonomy_mapping_template.csv` into `resources/mappings/`
- moved `electronet_schema_library.json`, `schema_index.csv`, and `compact_response.schema.json` into `resources/schemas/`
- moved `TEMPLATE_presentation.html`, `characteristics_templates.json`, and `product_import_template.csv` into `resources/templates/`
- moved `master_prompt+.txt` into `resources/prompts/`
- updated `scrapper/electronet_single_import/repo_paths.py` so the centralized support-asset constants resolve from `resources/`
- updated `scrapper/electronet_single_import/tests/test_utils_support_paths.py` to validate the `resources/` layout
- updated active path references in `README.md`, `RULES.md`, `AGENTS.md`, `scrapper/README.md`, `docs/audits/repo_cleanup_audit.md`, and `PLAN.md`
- removed `.gitkeep` from `resources/mappings/`, `resources/schemas/`, `resources/templates/`, and `resources/prompts/` after those directories became non-empty
- removed the old `schemas/` directory after `compact_response.schema.json` moved and the directory became empty

Validation:
- pre-move checks confirmed every approved source existed and every approved destination was absent
- post-move checks confirmed the old source paths no longer contain the moved files and the new `resources/` paths do contain them
- `rg` for the old asset paths confirmed active references were updated, with old basenames preserved only in historical records where intentionally retained
- `rg` for the new `resources/` paths confirmed runtime and active guidance ownership moved to `resources/`
- `python -m pytest -q electronet_single_import/tests/test_utils_support_paths.py` from `scrapper/` passed
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no runtime code outside `scrapper/electronet_single_import/repo_paths.py` was changed
- downstream runtime imports remained stable because existing constant names were preserved
- scraper smoke validation was intentionally skipped because the targeted path test, full pytest run, and code inspection were sufficient for this relocation-only milestone
- archived legacy files and historical command-log entries still contain old basenames intentionally and were not rewritten as part of M6

## M7 detail
Goal:
- normalize repo layout documentation after the M6 `resources/` move without changing runtime behavior

Changes:
- updated `README.md` to describe the post-M6 repo layout and current directory responsibilities
- created `docs/runbooks/repo-layout.md` as the practical repo-specific layout guide
- updated `PLAN.md` to mark M7 completed after the documentation normalization pass
- corrected documentation drift in active layout guidance without changing `AGENTS.md`, `RULES.md`, `IMPLEMENT.md`, or runtime code

Validation:
- `rg` over repo docs confirmed active layout guidance now points to `resources/` for shared support assets
- `rg` over repo docs confirmed `docs/checkpoints/IMPLEMENTATION_CHECKPOINT.md` and `docs/specs/2026-03-22-pipeline-optimization-design.md` are the current post-M4 locations in active guidance, with old-path mentions retained only in historical command logs
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- `AGENTS.md`, `RULES.md`, and runtime Python files were intentionally left unchanged because no broken active layout reference was found in them during M7
- scraper smoke validation was intentionally skipped because this was a docs-only milestone

## M8 detail
Goal:
- audit dependency ownership for `requirements.txt` and `scrapper/requirements.txt` without changing dependency files or runtime behavior

Changes:
- created `docs/audits/dependency_audit.md`
- recorded a side-by-side comparison of the two dependency files
- documented current live usage evidence from install instructions, control docs, and import scans
- updated `PLAN.md` to mark M8 completed with an audit-only result

Validation:
- file inspection completed for `requirements.txt` and `scrapper/requirements.txt`
- `rg` captured current references to dependency files and install commands across repo docs
- live import scans confirmed scraper/runtime imports for `httpx`, `playwright`, `beautifulsoup4`, `pypdf`, `PIL`, and `pillow_avif`, while no live `requests` import was found
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- the audit concludes that `scrapper/requirements.txt` is the only currently documented install target, but not yet the only file that appears required by live evidence
- dependency ownership remains audit-only and no dependency file was modified
- scraper smoke validation was intentionally skipped because this milestone did not change runtime behavior

## M9 detail
Goal:
- record a final post-cleanup repo health pass without changing runtime behavior

Changes:
- created `docs/audits/post_cleanup_health_pass.md`
- recorded the final repo-health summary, confirmed remaining issues, safe follow-up items, risky postponed items, and the recommended next action
- updated `PLAN.md` to mark M9 completed with an audit-only result

Validation:
- targeted `rg` searches confirmed no active guidance drift for the approved M4, M5, and M6 path changes
- targeted searches confirmed the main remaining issues are deferred items: dependency ownership, redundant `.gitkeep` files in non-empty `docs/` directories, `workflow.py` output-root assumptions, and hardcoded absolute repo paths in some tests
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no files were moved or deleted in M9
- no dependency files were changed
- no runtime code was edited
- scraper smoke validation was intentionally skipped because this was an audit-only milestone

## M10 detail
Goal:
- consolidate dependency ownership to one canonical repo-root `requirements.txt` without changing runtime behavior

Changes:
- updated repo-root `requirements.txt` to the verified canonical dependency union:
  - kept the scraper pins for `httpx`, `beautifulsoup4`, `lxml`, `playwright`, `pytest`, and `pypdf`
  - retained `pillow` and `pillow-avif-plugin` because live scraper imports still require them
  - removed `requests` because no live import evidence remained and clean-environment verification succeeded without it
- removed `scrapper/requirements.txt` after clean-environment verification succeeded
- updated `scrapper/README.md` so dependency installation now points to the canonical repo-root `requirements.txt`
- updated `PLAN.md` to mark M10 completed

Validation:
- captured the pre-edit dependency overlap between root and scraper files
- created a clean temporary virtual environment outside the repo
- installed dependencies from repo-root `requirements.txt` only
- import checks passed for `httpx`, `playwright`, `bs4`, `pypdf`, `PIL`, and `pillow_avif`
- full `python -m pytest -q` from `scrapper/` under the clean environment remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`
- active install guidance no longer depends on `scrapper/requirements.txt`

Notes:
- runtime behavior remained unchanged because no runtime code was modified
- remaining `scrapper/requirements.txt` mentions are preserved in audit/history docs as prior-state evidence
- the temporary verification environment was created outside the repo and removed after validation

## M11 detail
Goal:
- consolidate README ownership to one canonical repo-root `README.md` without changing runtime behavior

Changes:
- updated repo-root `README.md` so it now includes the current project summary, repo layout, canonical install from root `requirements.txt`, current scraper workflow commands, runtime artifact locations, output locations, and test instructions
- reduced `scrapper/README.md` to a minimal pointer to the repo-root `README.md`
- updated `PLAN.md` to mark M11 completed

Validation:
- inspected both README files and merged the still-useful scraper setup and workflow content into root `README.md`
- `rg` confirmed there is no active conflicting setup guidance between the root README and the reduced `scrapper/README.md`
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- `scrapper/README.md` was reduced to a pointer instead of being removed so existing historical or cross-doc references do not break
- no runtime code, dependency files, or project structure changed
- scraper smoke validation was intentionally skipped because this was a docs-only milestone

## M12 detail
Goal:
- remove stale old-file and old-path references from active guidance only without changing runtime behavior

Changes:
- inspected the active guidance set for stale references to pre-M4, M5, M6, and M10 file paths
- confirmed that the remaining old-file references are confined to historical milestone logs, audits, specs, and archive material
- reduced `scrapper/README.md` further so it acts only as a concise pointer to the canonical repo-root `README.md`
- updated `PLAN.md` to mark M12 completed with an active-guidance-only normalization result

Validation:
- `rg` across active guidance confirmed no stale old-file references remain in current guidance, aside from clearly historical mentions in control-doc history sections
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no runtime code, dependency files, or project structure changed
- current guidance redundancy was reduced only where it was safe to do so, without rewriting historical material
- scraper smoke validation was intentionally skipped because this was a docs-only milestone

## M13 detail
Goal:
- normalize historical old-file and old-path references in audits, specs, logs, and archive material while preserving provenance

Changes:
- added short historical-context notes to the affected audit, spec, and archived legacy files so pre-move paths are now explicitly labeled as prior-state references
- clarified in this engineering log that old file paths in completed milestone sections and command logs are intentional historical references rather than current guidance
- updated `PLAN.md` to mark M13 completed with provenance-preserving historical normalization

Validation:
- `rg` across `docs/audits/`, `docs/specs/`, `archive/legacy/`, and `DOCUMENTATION.md` confirmed the known old paths now remain either explicitly labeled as historical or already sit inside clearly historical records
- `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- no runtime code, dependency files, or project structure changed
- provenance was preserved by adding clarification notes instead of rewriting the underlying historical outcomes
- scraper smoke validation was intentionally skipped because this was a docs-only milestone

## M14 detail
Goal:
- reduce proven runtime-code redundancy and improve concision without changing behavior

Changes:
- switched the confirmed support-asset path consumers from `utils.py` compatibility re-exports to direct imports from `scrapper/electronet_single_import/repo_paths.py`
- removed the dead `RULES_PATH` constant from `scrapper/electronet_single_import/utils.py`
- removed the one-callsite `build_model_output_dir()` wrapper and inlined its exact current behavior in `scrapper/electronet_single_import/cli.py`
- simplified `scrapper/electronet_single_import/utils.py` so it now keeps only actual utility helpers rather than mixed utility and path-ownership responsibilities
- made a small concision cleanup in `scrapper/electronet_single_import/deterministic_fields.py` by collapsing duplicate typing imports while touching the file for the path-import change

Validation:
- confirmed before editing that `RULES_PATH` had no callsites, `build_model_output_dir()` had exactly one caller in `scrapper/electronet_single_import/cli.py`, and the path-constant compatibility seam was limited to the edited runtime modules
- `python -m compileall scrapper/electronet_single_import` succeeded
- `python -m pytest -q electronet_single_import/tests/test_utils_support_paths.py` from `scrapper/` passed
- `python -m pytest -q electronet_single_import/tests/test_workflow.py electronet_single_import/tests/test_csv_writer.py electronet_single_import/tests/test_validator.py electronet_single_import/tests/test_taxonomy.py electronet_single_import/tests/test_schema_matcher.py` from `scrapper/` passed
- `python -m pytest -q electronet_single_import/tests/test_characteristics_pipeline.py electronet_single_import/tests/test_deterministic_fields.py electronet_single_import/tests/test_deterministic_fields_ice_cream_maker.py electronet_single_import/tests/test_manufacturer_enrichment_tefal.py` from `scrapper/` passed
- full `python -m pytest -q` from `scrapper/` remained at the expected baseline: `75 passed, 2 failed`
- unchanged failing tests: `test_enrichment_framework_supports_pdf_candidates`, `test_enrichment_framework_supports_html_candidates`

Notes:
- runtime behavior remained unchanged because this pass only reduced a dead constant, a one-callsite wrapper, and the `utils.py` path-compatibility seam
- no tests needed edits because the path values and behavior under test stayed the same
- higher-risk cleanup remains deferred, including `workflow.py` output-root refactors, hardcoded absolute repo paths in some tests, and broader utility API reshaping

## Commands run
- `rg -n "M15|Current milestone|Phase 2 milestones|M14 detail|Next active milestone" PLAN.md DOCUMENTATION.md`
- `Get-Content AGENTS.md`
- `Get-Content RULES.md`
- `Get-Content IMPLEMENT.md`
- `git status --short`
- `Get-Content PLAN.md | Select-Object -First 90`
- `Get-Content PLAN.md | Select-Object -Skip 180`
- `Get-Content DOCUMENTATION.md | Select-Object -First 60`
- `Get-Content DOCUMENTATION.md | Select-Object -Skip 350`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q` from `scrapper/`
- pre-creation filesystem check for `docs/audits/`, `docs/runbooks/`, `docs/checkpoints/`, `docs/specs/`, `archive/legacy/`, `resources/mappings/`, `resources/prompts/`, `resources/schemas/`, and `resources/templates/`
- directory creation for the same approved target paths only when absent
- post-creation filesystem check for approved target paths, `.gitkeep` presence, and empty-directory state
- `python -m pytest -q` from `scrapper/`
- `git status --short`
- `Get-ChildItem -Force -File` at repo root
- `Get-ChildItem docs/audits`
- `Get-ChildItem docs/superpowers/specs,work`
- `rg` sweep for each explicitly named file or candidate to capture runtime code references, docs or planning references, or absence of references
- `Get-Content scrapper/electronet_single_import/utils.py`
- `Get-Content RULES.md`
- `Get-Content AGENTS.md`
- `Get-Content README.md`
- `Get-Content scrapper/README.md`
- pre-edit `rg` over `scrapper/electronet_single_import/` for approved support-asset filenames
- `Get-Content scrapper/electronet_single_import/tests/test_utils_support_paths.py`
- `Get-Content scrapper/electronet_single_import/repo_paths.py`
- post-edit `rg` over `scrapper/electronet_single_import/*.py` for approved support-asset filenames
- `python -m pytest -q electronet_single_import/tests/test_utils_support_paths.py` from `scrapper/`
- source/destination existence checks for the two approved M4 moves
- `Move-Item` for `docs/superpowers/specs/2026-03-22-pipeline-optimization-design.md` to `docs/specs/2026-03-22-pipeline-optimization-design.md`
- `Move-Item` for `work/IMPLEMENTATION_CHECKPOINT.md` to `docs/checkpoints/IMPLEMENTATION_CHECKPOINT.md`
- `rg` for old and new M4 paths before and after the move
- source/destination existence checks for `RULES_legacy.md` and `master_prompt_legacy.txt`
- `Move-Item` for `RULES_legacy.md` to `archive/legacy/RULES_legacy.md`
- `Move-Item` for `master_prompt_legacy.txt` to `archive/legacy/master_prompt_legacy.txt`
- `Remove-Item` for `archive/legacy/.gitkeep` after the archive directory became non-empty
- `rg` for old and new M5 legacy paths before and after the move
- pre-move source and destination existence checks for every approved M6 support asset
- `rg` for old and new M6 support-asset paths before and after the move
- `Move-Item` for the approved M6 support assets into `resources/mappings/`, `resources/schemas/`, `resources/templates/`, and `resources/prompts/`
- `Remove-Item` for `.gitkeep` in `resources/mappings/`, `resources/schemas/`, `resources/templates/`, and `resources/prompts/` after those directories became non-empty
- `Remove-Item` for the old `schemas/` directory after it became empty
- `Get-Content README.md`
- existence check for `docs/runbooks/repo-layout.md`
- `rg` over repo docs for pre-M6 support-asset paths and post-M4 moved doc paths
- `Get-Content requirements.txt`
- `Get-Content scrapper/requirements.txt`
- `rg` over repo docs for dependency-file references and install/setup commands
- live import scans for packages declared in either dependency file
- root directory inventory
- recursive search for remaining `.gitkeep` files
- targeted `rg` for pre-M4, M5, and M6 paths and known deferred runtime/path issues
- dependency overlap comparison between root and scraper requirement files
- clean temporary virtual environment creation outside the repo
- dependency install from canonical repo-root `requirements.txt`
- clean-environment import validation for `httpx`, `playwright`, `bs4`, `pypdf`, `PIL`, and `pillow_avif`
- full `python -m pytest -q` from `scrapper/` under the clean environment
- `rg` for `scrapper/requirements.txt` after consolidation
- temporary verification-environment removal
- README inspection for root and scraper README ownership
- `rg` for `scrapper/README.md` references after README consolidation
- targeted `rg` for stale old-file references across current guidance docs
- targeted `rg` for stale old-file references across `docs/audits/`, `docs/specs/`, `archive/legacy/`, and `DOCUMENTATION.md`
- `Get-ChildItem -Recurse -File scrapper/electronet_single_import`
- `rg` over `scrapper/electronet_single_import/` for `REPO_ROOT`, path constants, `build_model_output_dir`, `RULES_PATH`, and utility callsites
- `Get-Content` inspection for `scrapper/electronet_single_import/utils.py`, `repo_paths.py`, `cli.py`, `workflow.py`, `csv_writer.py`, `validator.py`, `taxonomy.py`, `schema_matcher.py`, `manufacturer_enrichment.py`, `characteristics_pipeline.py`, and `deterministic_fields.py`
- `python -m compileall scrapper/electronet_single_import`
- `python -m pytest -q electronet_single_import/tests/test_utils_support_paths.py` from `scrapper/`
- `python -m pytest -q electronet_single_import/tests/test_workflow.py electronet_single_import/tests/test_csv_writer.py electronet_single_import/tests/test_validator.py electronet_single_import/tests/test_taxonomy.py electronet_single_import/tests/test_schema_matcher.py` from `scrapper/`
- `python -m pytest -q electronet_single_import/tests/test_characteristics_pipeline.py electronet_single_import/tests/test_deterministic_fields.py electronet_single_import/tests/test_deterministic_fields_ice_cream_maker.py electronet_single_import/tests/test_manufacturer_enrichment_tefal.py` from `scrapper/`

## Open risks
- direct path assumptions may exist in multiple scraper modules
- docs may drift during file moves if not updated in the same commit
- baseline pytest failures remain in `electronet_single_import/tests/test_manufacturer_enrichment.py`
- `schema_index.csv` and `taxonomy_mapping_template.csv` have weaker direct runtime evidence than the hardcoded support assets
- `workflow.py` still contains out-of-scope `REPO_ROOT` output-root assumptions for `work/` and `products/`
- some tests still use hardcoded absolute repo paths and were intentionally deferred
- historical docs and archived legacy files intentionally retain some old support-asset basenames as prior-state evidence
- redundant `.gitkeep` files remain in non-empty `docs/audits/`, `docs/checkpoints/`, `docs/runbooks/`, and `docs/specs/` directories
- broader runtime utility/API reshaping beyond the current path-ownership seam remains intentionally deferred to avoid behavior risk

## Next approved action
No cleanup follow-up is scheduled by default. If approved, open a narrowly scoped follow-up for deferred path assumptions, test path cleanup, or redundant `.gitkeep` removal.

## 2026-03-28 - Skroutz mixed-section pipeline fix and live run for model 123456

## What changed
- fixed Skroutz section selection in `scrapper/electronet_single_import/cli.py` so prepare selects the first requested image-backed rich-description sections instead of blindly slicing the first parsed sections when text-only `one-column` blocks appear mid-stream
- added a regression test in `scrapper/electronet_single_import/tests/test_skroutz_sections.py` covering the mixed image/text section ordering case
- ran the live Product-Agent pipeline for model `123456` against the provided Skroutz product URL and authored `work/123456/llm_output.json` using the reduced LLM contract

## Files and directories affected
- `scrapper/electronet_single_import/cli.py`
- `scrapper/electronet_single_import/tests/test_skroutz_sections.py`
- `work/123456/`
- `products/123456.csv`

## Commands run
- `Get-ChildItem -Force`
- `git status --short`
- `rg --files AGENTS.md PLAN.md IMPLEMENT.md DOCUMENTATION.md`
- `python -m electronet_single_import.workflow prepare --model 123456 --url "https://www.skroutz.gr/s/60276903/tcl-smart-tileorasi-115-4k-uhd-mini-led-c7k-hdr-2025-115c7k.html" --photos 7 --sections 7 --skroutz-status 1 --boxnow 0 --price 9999` from `scrapper/`
- `rg -n "Skroutz section image could not be resolved|section image could not be resolved|section_image|section image" scrapper`
- `Get-Content` inspection for `scrapper/electronet_single_import/cli.py`, `fetcher.py`, `skroutz_sections.py`, `workflow.py`, `html_builders.py`, `work/123456/llm_context.json`, `work/123456/prompt.txt`, `work/123456/scrape/123456.source.json`, `work/123456/scrape/123456.report.json`, `resources/prompts/master_prompt+.txt`, `resources/schemas/compact_response.schema.json`, `resources/mappings/filter_map.json`, and `products/123456.csv`
- `python -m pytest scrapper/electronet_single_import/tests/test_skroutz_sections.py -q`
- `python -m pytest scrapper/electronet_single_import/tests/test_skroutz_integration.py -q`
- `python -m electronet_single_import.workflow render --model 123456` from `scrapper/`

## Validation results
- initial live `prepare` failed with `Skroutz section image could not be resolved for section 6`
- focused tests passed after the fix:
  - `scrapper/electronet_single_import/tests/test_skroutz_sections.py`: 5 passed
  - `scrapper/electronet_single_import/tests/test_skroutz_integration.py`: 7 passed
- first live `render` failed validation with `llm_intro_word_count_invalid`
- adjusted `work/123456/llm_output.json` intro length to satisfy the reduced contract
- final live `render` passed with `Validation ok: True`
- final validation warnings remained:
  - `characteristics_template_used:schema:sha1:954c8413f2da941e78f3ddce65df522654336c8c`
  - `characteristics_template_unresolved_fields:12`

## Risks, blockers, or skipped items
- the live product still relies on the characteristics template for some unresolved spec fields; this is reported but not a blocking validation failure
- no durable process-rule update was required in `IMPLEMENT.md`
- no milestone-plan change was required in `PLAN.md`

## 2026-03-28 - Portable test fixture path centralization

## What changed
- created `scrapper/electronet_single_import/tests/conftest.py` as the canonical test-layer path source of truth
- added shared pytest fixtures for `tests_root`, `fixtures_root`, `skroutz_fixtures_root`, and `products_root`
- removed machine-specific absolute path assumptions from the affected Skroutz tests and switched them to the shared fixtures
- kept the change test-only; no runtime module outside `scrapper/electronet_single_import/tests/` was edited

## Files edited
- `scrapper/electronet_single_import/tests/conftest.py`
- `scrapper/electronet_single_import/tests/test_skroutz_integration.py`
- `scrapper/electronet_single_import/tests/test_skroutz_sections.py`
- `scrapper/electronet_single_import/tests/test_skroutz_taxonomy.py`
- `DOCUMENTATION.md`

## Normalized path assumptions
- `test_skroutz_integration.py`
  - replaced hard-coded absolute `REPO_ROOT`
  - replaced per-file `FIXTURES_ROOT` and `PRODUCTS_ROOT`
  - switched fetcher and baseline-copy helpers to accept shared fixture paths
- `test_skroutz_sections.py`
  - replaced hard-coded absolute `REPO_ROOT`
  - replaced per-file `FIXTURES_ROOT` and `PRODUCTS_ROOT`
  - switched fixture fetcher helper and baseline CSV reads to shared fixture paths
- `test_skroutz_taxonomy.py`
  - replaced hard-coded absolute `REPO_ROOT`
  - replaced derived `REGRESSION_FIXTURE` and `TAXONOMY_CASES_ROOT`
  - switched taxonomy fixture reads to shared fixture paths

## Commands run
- `rg --files scrapper/electronet_single_import/tests`
- `Get-Content scrapper/conftest.py`
- `Get-Content scrapper/electronet_single_import/tests/test_skroutz_integration.py`
- `Get-Content scrapper/electronet_single_import/tests/test_skroutz_sections.py`
- `Get-Content scrapper/electronet_single_import/tests/test_skroutz_taxonomy.py`
- `rg -n "Users\\\\|VS_Projects|Product-Agent|__file__|parents\\[|parent.parent|fixtures|FIXTURES_ROOT|PRODUCTS_ROOT|REPO_ROOT" scrapper/electronet_single_import/tests`
- `python -m pytest -q electronet_single_import/tests/test_skroutz_integration.py` from `scrapper/`
- `python -m pytest -q electronet_single_import/tests/test_skroutz_sections.py` from `scrapper/`
- `python -m pytest -q electronet_single_import/tests/test_skroutz_taxonomy.py` from `scrapper/`
- `python -m pytest -q` from `scrapper/`
- `python -m compileall scrapper/electronet_single_import`
- `git status --short`

## Validation results
- targeted tests after the path fix:
  - `electronet_single_import/tests/test_skroutz_integration.py`: `7 passed`
  - `electronet_single_import/tests/test_skroutz_sections.py`: `5 passed`
  - `electronet_single_import/tests/test_skroutz_taxonomy.py`: `5 passed`
- full suite after the path fix:
  - `76 passed, 2 failed`
  - remaining failures:
    - `test_enrichment_framework_supports_pdf_candidates`
    - `test_enrichment_framework_supports_html_candidates`
- `python -m compileall scrapper/electronet_single_import` succeeded
- `git status --short` showed only the expected test-layer edits and `DOCUMENTATION.md`

## Risks, blockers, or skipped items
- no runtime behavior risk is expected because the change is confined to test path resolution
- no `PLAN.md` update was needed because this is a test-baseline stabilization task rather than a milestone-order change

## 2026-03-30 - Phase 2 test fixture hierarchy migration

## What changed
- migrated the committed Skroutz test fixtures from the legacy flat `scraper/pipeline/tests/fixtures/skroutz/` layout into the explicit provider hierarchy under `scraper/pipeline/tests/fixtures/providers/skroutz/`
- added the new shared pytest fixture roots in `scraper/pipeline/tests/conftest.py` and kept `skroutz_fixtures_root` as a backward-compatible alias to the new Skroutz provider fixture root
- updated the touched Skroutz tests to read fixture HTML, rendered-sections JSON, and taxonomy-case assets from the new hierarchy
- created empty committed placeholder directories for the requested explicit fixture tree with `.gitkeep` files where no tracked fixture content exists yet
- made one minimal stale-guidance fix in `AGENTS.md` and one additive fixture-location rule in `IMPLEMENT.md`
- left `work/` and `scraper/work/` untouched because `git ls-files work scraper/work` returned no tracked files in this checkout

## Files and directories affected
- edited:
  - `scraper/pipeline/tests/conftest.py`
  - `scraper/pipeline/tests/test_provider_selection.py`
  - `scraper/pipeline/tests/test_skroutz_integration.py`
  - `scraper/pipeline/tests/test_skroutz_sections.py`
  - `scraper/pipeline/tests/test_skroutz_taxonomy.py`
  - `AGENTS.md`
  - `IMPLEMENT.md`
  - `DOCUMENTATION.md`
- moved:
  - `scraper/pipeline/tests/fixtures/skroutz/*.html` -> `scraper/pipeline/tests/fixtures/providers/skroutz/html/`
  - `scraper/pipeline/tests/fixtures/skroutz/143481.rendered_sections.json` -> `scraper/pipeline/tests/fixtures/providers/skroutz/rendered_sections/`
  - `scraper/pipeline/tests/fixtures/skroutz/skroutz_taxonomy_regression.csv` -> `scraper/pipeline/tests/fixtures/providers/skroutz/taxonomy_cases/`
  - `scraper/pipeline/tests/fixtures/skroutz/taxonomy_cases/*` -> `scraper/pipeline/tests/fixtures/providers/skroutz/taxonomy_cases/`
- added placeholder directories:
  - `scraper/pipeline/tests/fixtures/providers/skroutz/json/`
  - `scraper/pipeline/tests/fixtures/providers/electronet/html/`
  - `scraper/pipeline/tests/fixtures/providers/electronet/json/`
  - `scraper/pipeline/tests/fixtures/providers/manufacturer_tefal/344709/`
  - `scraper/pipeline/tests/fixtures/pipeline_runs/`
  - `scraper/pipeline/tests/fixtures/golden_outputs/`

## Commands run
- `git ls-files work scraper/work`
- `New-Item -ItemType Directory -Force ...` for the new fixture hierarchy roots
- `git mv` for the explicit Skroutz fixture moves into `providers/skroutz/...`
- `Remove-Item scraper/pipeline/tests/fixtures/skroutz` after the legacy directory became empty
- `Get-Content` inspection for `AGENTS.md`, `IMPLEMENT.md`, `DOCUMENTATION.md`, and the touched test files
- `git status --short`
- `rg -n "def .*fixtures_root|skroutz_fixtures_root|fixtures/skroutz|work/|scraper/work/|active regression samples" scraper/pipeline/tests AGENTS.md IMPLEMENT.md .gitignore`
- `python -m pytest -q pipeline/tests/test_provider_selection.py` from `scraper/`
- `python -m pytest -q pipeline/tests/test_skroutz_integration.py` from `scraper/`
- `python -m pytest -q pipeline/tests/test_skroutz_sections.py` from `scraper/`
- `python -m pytest -q pipeline/tests/test_skroutz_taxonomy.py` from `scraper/`
- `where.exe python`
- `py -0p`
- `py -3.12 -m pytest --version`
- `py -3.12 -m pytest -q pipeline/tests/test_provider_selection.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_skroutz_integration.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_skroutz_sections.py` from `scraper/`
- `py -3.12 -m pytest -q pipeline/tests/test_skroutz_taxonomy.py` from `scraper/`
- `py -3.12 -m pytest -q` from `scraper/`

## Validation results
- initial validation command path using `python -m pytest` could not run because the active `python` interpreter did not have `pytest` installed
- focused touched-test results using `py -3.12 -m pytest`:
  - `pipeline/tests/test_provider_selection.py`: `4 passed`
  - `pipeline/tests/test_skroutz_sections.py`: `5 passed`
  - `pipeline/tests/test_skroutz_taxonomy.py`: `5 passed`
  - `pipeline/tests/test_skroutz_integration.py`: `6 passed, 1 failed`
- the touched integration failure was `test_prepare_and_render_workflow_with_skroutz_fixtures`, failing on `render_result["published_csv_path"] is None` after fixture loading had already succeeded from the new hierarchy
- full suite result: `90 passed, 4 failed`
- unchanged baseline failures from the earlier documented suite baseline:
  - `pipeline/tests/test_manufacturer_enrichment.py::test_enrichment_framework_supports_pdf_candidates`
  - `pipeline/tests/test_manufacturer_enrichment.py::test_enrichment_framework_supports_html_candidates`
- additional currently failing workflow publication tests:
  - `pipeline/tests/test_skroutz_integration.py::test_prepare_and_render_workflow_with_skroutz_fixtures`
  - `pipeline/tests/test_workflow.py::test_render_workflow_writes_candidate_bundle`
- no new fixture-path lookup failures were observed in the focused path-migration assertions

## Risks, blockers, or skipped items
- `scraper/work/344709/debug_manufacturer/` was absent in this checkout, so no manufacturer repro assets were promoted in this phase
- `work/229957_skroutz_debug.html` exists only as an ignored local file and was intentionally left untracked
- no `.gitignore` change was needed or made
- the remaining test failures are outside this migration's edit scope; the fixture path migration stopped at test-layer changes and the minimal allowed control-file updates
