from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .repo_paths import PRODUCT_TEMPLATE_PATH
from .utils import load_template_headers



def write_csv_row(row: dict[str, Any], out_path: str | Path, template_path: str | Path = PRODUCT_TEMPLATE_PATH) -> tuple[list[str], dict[str, Any]]:
    headers = load_template_headers(template_path)
    ordered = {header: row.get(header, "") for header in headers}
    with open(out_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerow(ordered)
    return headers, ordered
