#!/usr/bin/env bash
set -euo pipefail

# Single repo-native entrypoint for OpenCart image upload.
# Intended location in repo:
#   tools/run_opencart_image_upload.sh
# with:
#   tools/opencart_upload_images.py
#
# What it does:
# 1) Resolves the 6-digit model
# 2) Prefers the exact product file created in the current job when provided
# 3) Calls the Python uploader
#
# Resolution order:
#   1) first CLI arg:
#      - exact 6-digit model, or
#      - exact product file path from this job
#   2) CURRENT_JOB_PRODUCT_FILE
#   3) PRODUCT_FILE_PATH
#   4) PREV_OUTPUT_PATH
#   5) CI_PRODUCT_FILE
#   6) newest products/{model}.csv in repo
#   7) newest work/{model}/scrape/gallery/{model}-1.jpg in repo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Repo root detection: assume tools/ lives one level below repo root.
REPO_ROOT="${REPO_ROOT:-}"
if [[ -z "${REPO_ROOT}" ]]; then
  if [[ -d "${SCRIPT_DIR}/../work" || -d "${SCRIPT_DIR}/../products" || -d "${SCRIPT_DIR}/../.git" ]]; then
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
  else
    REPO_ROOT="$(pwd)"
  fi
fi

# ---- editable / CI-driven config ----
STORE_BASE="${OPENCART_STORE_BASE:-https://www.etranoulis.gr}"
ADMIN_PATH="${OPENCART_ADMIN_PATH:-/ipadmin/index.php}"
ADMIN_USER="${OPENCART_ADMIN_USER:-etranoulis}"
ADMIN_PASS="${OPENCART_ADMIN_PASS:-theo1019591019}"
DRY_RUN="${DRY_RUN:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHON_SCRIPT="${PYTHON_SCRIPT:-${SCRIPT_DIR}/opencart_upload_images.py}"
# ------------------------------------

REPO_ROOT_PY="${REPO_ROOT}"
PYTHON_SCRIPT_PY="${PYTHON_SCRIPT}"
if command -v cygpath >/dev/null 2>&1; then
  REPO_ROOT_PY="$(cygpath -w "${REPO_ROOT}")"
  PYTHON_SCRIPT_PY="$(cygpath -w "${PYTHON_SCRIPT}")"
fi

if [[ -z "${ADMIN_USER}" || -z "${ADMIN_PASS}" ]]; then
  echo "ERROR: missing OPENCART_ADMIN_USER or OPENCART_ADMIN_PASS" >&2
  exit 1
fi

if [[ ! -f "${PYTHON_SCRIPT}" ]]; then
  echo "ERROR: python uploader not found: ${PYTHON_SCRIPT}" >&2
  exit 1
fi

extract_model() {
  local input="${1:-}"
  local model=""

  [[ -z "${input}" ]] && return 1

  # exact model
  if [[ "${input}" =~ ^[0-9]{6}$ ]]; then
    printf '%s\n' "${input}"
    return 0
  fi

  # basename without extension
  local base
  base="$(basename "${input}")"
  base="${base%.*}"
  if [[ "${base}" =~ ^[0-9]{6}$ ]]; then
    printf '%s\n' "${base}"
    return 0
  fi

  # look for a standalone 6-digit token anywhere in the path/value
  model="$(printf '%s' "${input}" | grep -oE '(^|[^0-9])[0-9]{6}([^0-9]|$)' | grep -oE '[0-9]{6}' | tail -n1 || true)"
  if [[ -n "${model}" ]]; then
    printf '%s\n' "${model}"
    return 0
  fi

  return 1
}

is_path_like() {
  local input="${1:-}"
  [[ "${input}" == */* || "${input}" == *\\* || "${input}" == *.csv || "${input}" == *.jpg || "${input}" == *.jpeg ]]
}

normalize_path() {
  local input="${1:-}"

  [[ -z "${input}" ]] && return 1

  if [[ "${input}" = /* ]]; then
    printf '%s\n' "${input}"
    return 0
  fi

  if [[ -e "${input}" ]]; then
    printf '%s\n' "$(cd "$(dirname "${input}")" && pwd)/$(basename "${input}")"
    return 0
  fi

  if [[ -e "${REPO_ROOT}/${input}" ]]; then
    printf '%s\n' "${REPO_ROOT}/${input}"
    return 0
  fi

  printf '%s\n' "${REPO_ROOT}/${input}"
}

resolve_from_explicit_value() {
  local label="${1:-}"
  local value="${2:-}"
  local normalized=""
  local model=""

  [[ -z "${value}" ]] && return 1

  # Exact model passed directly
  if model="$(extract_model "${value}" 2>/dev/null)" && [[ "${value}" =~ ^[0-9]{6}$ ]]; then
    RESOLVED_FROM="${label}:model"
    RESOLVED_INPUT="${value}"
    printf '%s\n' "${model}"
    return 0
  fi

  # Exact path from current job or CLI path
  if is_path_like "${value}"; then
    normalized="$(normalize_path "${value}")"
    if [[ ! -f "${normalized}" ]]; then
      echo "ERROR: ${label} was provided but file does not exist: ${normalized}" >&2
      exit 1
    fi

    model="$(extract_model "${normalized}" || true)"
    if [[ -z "${model}" ]]; then
      echo "ERROR: could not extract a 6-digit model from ${label}: ${normalized}" >&2
      exit 1
    fi

    RESOLVED_FROM="${label}:file"
    RESOLVED_INPUT="${normalized}"
    printf '%s\n' "${model}"
    return 0
  fi

  # Generic string containing a model token
  model="$(extract_model "${value}" || true)"
  if [[ -n "${model}" ]]; then
    RESOLVED_FROM="${label}:token"
    RESOLVED_INPUT="${value}"
    printf '%s\n' "${model}"
    return 0
  fi

  return 1
}

resolve_from_latest_products_csv() {
  local products_dir="${REPO_ROOT}/products"
  local latest=""
  local model=""

  [[ -d "${products_dir}" ]] || return 1

  latest="$(find "${products_dir}" -maxdepth 1 -type f -name '*.csv' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2- || true)"
  [[ -n "${latest}" ]] || return 1

  model="$(extract_model "${latest}" || true)"
  [[ -n "${model}" ]] || return 1

  RESOLVED_FROM="latest_products_csv"
  RESOLVED_INPUT="${latest}"
  printf '%s\n' "${model}"
}

resolve_from_latest_gallery() {
  local latest=""
  local model=""

  latest="$(find "${REPO_ROOT}/work" -type f -path '*/scrape/gallery/*.jpg' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2- || true)"
  [[ -n "${latest}" ]] || return 1

  model="$(extract_model "${latest}" || true)"
  [[ -n "${model}" ]] || return 1

  RESOLVED_FROM="latest_gallery"
  RESOLVED_INPUT="${latest}"
  printf '%s\n' "${model}"
}

resolve_model() {
  local arg1="${1:-}"
  local model=""

  # Highest priority: explicit arg
  if model="$(resolve_from_explicit_value "arg" "${arg1}" 2>/dev/null)"; then
    printf '%s\n' "${model}"
    return 0
  fi

  # Prefer the exact file created in this job when provided
  if model="$(resolve_from_explicit_value "CURRENT_JOB_PRODUCT_FILE" "${CURRENT_JOB_PRODUCT_FILE:-}" 2>/dev/null)"; then
    printf '%s\n' "${model}"
    return 0
  fi

  if model="$(resolve_from_explicit_value "PRODUCT_FILE_PATH" "${PRODUCT_FILE_PATH:-}" 2>/dev/null)"; then
    printf '%s\n' "${model}"
    return 0
  fi

  if model="$(resolve_from_explicit_value "PREV_OUTPUT_PATH" "${PREV_OUTPUT_PATH:-}" 2>/dev/null)"; then
    printf '%s\n' "${model}"
    return 0
  fi

  if model="$(resolve_from_explicit_value "CI_PRODUCT_FILE" "${CI_PRODUCT_FILE:-}" 2>/dev/null)"; then
    printf '%s\n' "${model}"
    return 0
  fi

  # Fallbacks only when no exact current-job output is provided
  if model="$(resolve_from_latest_products_csv 2>/dev/null)"; then
    printf '%s\n' "${model}"
    return 0
  fi

  if model="$(resolve_from_latest_gallery 2>/dev/null)"; then
    printf '%s\n' "${model}"
    return 0
  fi

  return 1
}

RESOLVED_FROM=""
RESOLVED_INPUT=""
MODEL="$(resolve_model "${1:-}" || true)"

if [[ -z "${MODEL}" ]]; then
  echo "ERROR: could not resolve a 6-digit model." >&2
  echo "Tried: arg -> CURRENT_JOB_PRODUCT_FILE -> PRODUCT_FILE_PATH -> PREV_OUTPUT_PATH -> CI_PRODUCT_FILE -> latest products/*.csv -> latest gallery image" >&2
  exit 1
fi

CMD=(
  "${PYTHON_BIN}" "${PYTHON_SCRIPT_PY}"
  --model "${MODEL}"
  --repo-root "${REPO_ROOT_PY}"
  --store-base "${STORE_BASE}"
  --admin-path "${ADMIN_PATH}"
  --username "${ADMIN_USER}"
  --password "${ADMIN_PASS}"
)

if [[ "${DRY_RUN}" == "1" ]]; then
  CMD+=(--dry-run)
fi

echo "[opencart-upload] repo_root=${REPO_ROOT} model=${MODEL} resolved_from=${RESOLVED_FROM} admin_path=${ADMIN_PATH} dry_run=${DRY_RUN}"
if [[ -n "${RESOLVED_INPUT}" ]]; then
  echo "[opencart-upload] resolved_input=${RESOLVED_INPUT}"
fi

# Prevent Git Bash / MSYS from rewriting the OpenCart web admin path such as
# `/ipadmin/index.php` into a local Windows path before Python receives it.
export MSYS2_ARG_CONV_EXCL="${ADMIN_PATH}"

exec "${CMD[@]}"
