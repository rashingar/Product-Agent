from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from product_pipeline import (
    ROOT,
    build_csv_row,
    load_csv_header,
    read_json,
    render_chat_output,
    validate_response_payload,
    write_csv,
)


def load_response_payload(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8-sig").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render Product-Agent artifacts from compact LLM JSON output.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--work-root", default=str(ROOT / "work"))
    parser.add_argument("--response", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    work_dir = Path(args.work_root) / args.model
    context_path = work_dir / "context.json"
    response_path = Path(args.response) if args.response else work_dir / "llm_output.json"
    context = read_json(context_path)
    response = load_response_payload(response_path)
    validate_response_payload(response, int(context["input"]["sections"]))
    header = load_csv_header()
    row = build_csv_row(context, response)
    csv_path = ROOT / "products" / f"{args.model}.csv"
    write_csv(csv_path, header, row)
    chat_path = work_dir / "chat_output.txt"
    chat_path.parent.mkdir(parents=True, exist_ok=True)
    chat_path.write_text(render_chat_output(args.model, context["auto_filters"]), encoding="utf-8")
    (work_dir / "description.html").write_text(row["description"], encoding="utf-8")
    (work_dir / "characteristics.html").write_text(row["characteristics"], encoding="utf-8")
    print(f"CSV written: {csv_path}")
    print(f"Chat output written: {chat_path}")
    print(f"Description HTML written: {work_dir / 'description.html'}")
    print(f"Characteristics HTML written: {work_dir / 'characteristics.html'}")


if __name__ == "__main__":
    main()
