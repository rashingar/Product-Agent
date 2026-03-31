#!/usr/bin/env bash
set -euo pipefail

# Repo-native wrapper for pipeline usage.
# Place this file in your repo, e.g. tools/run_opencart_image_upload.sh
# Secrets are loaded from .secrets/opencart.env if present.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.secrets/opencart.env}"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
fi

MODEL="${1:-${MODEL:-}}"
STORE_BASE="${OPENCART_STORE_BASE:-https://www.etranoulis.gr}"
ADMIN_PATH="${OPENCART_ADMIN_PATH:-/ipadmin/index.php}"
ADMIN_USER="${OPENCART_ADMIN_USER:-}"
ADMIN_PASS="${OPENCART_ADMIN_PASS:-}"
DRY_RUN="${DRY_RUN:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHON_SCRIPT="${PYTHON_SCRIPT:-${SCRIPT_DIR}/opencart_upload_images.py}"

if [[ -z "${MODEL}" ]]; then
  echo "ERROR: missing model. Usage: $0 123456" >&2
  exit 1
fi

if [[ -z "${ADMIN_USER}" || -z "${ADMIN_PASS}" ]]; then
  echo "ERROR: missing OPENCART_ADMIN_USER or OPENCART_ADMIN_PASS" >&2
  exit 1
fi

CMD=(
  "${PYTHON_BIN}" "${PYTHON_SCRIPT}"
  --model "${MODEL}"
  --repo-root "${REPO_ROOT}"
  --store-base "${STORE_BASE}"
  --admin-path "${ADMIN_PATH}"
  --username "${ADMIN_USER}"
  --password "${ADMIN_PASS}"
)

if [[ "${DRY_RUN}" == "1" ]]; then
  CMD+=(--dry-run)
fi

echo "[opencart-upload] repo_root=${REPO_ROOT} model=${MODEL} admin_path=${ADMIN_PATH} dry_run=${DRY_RUN}"
"${CMD[@]}"
