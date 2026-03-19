from __future__ import annotations

import argparse
from pathlib import Path

from product_pipeline import ROOT, build_context_record, read_text, write_json


def min_int(value: str, minimum: int, name: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{name} must be an integer") from exc
    if number < minimum:
        raise argparse.ArgumentTypeError(f"{name} must be >= {minimum}")
    return number


def photos_arg(value: str) -> int:
    return min_int(value, 1, "photos")


def sections_arg(value: str) -> int:
    return min_int(value, 0, "sections")


def flag_arg(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("flags must be 0 or 1") from exc
    if number not in {0, 1}:
        raise argparse.ArgumentTypeError("flags must be 0 or 1")
    return number


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact LLM context for Product-Agent.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--photos", type=photos_arg, default=1)
    parser.add_argument("--sections", type=sections_arg, default=0)
    parser.add_argument("--skroutz-status", type=flag_arg, default=0)
    parser.add_argument("--boxnow", type=flag_arg, default=0)
    parser.add_argument("--price", default="0")
    parser.add_argument("--work-root", default=str(ROOT / "work"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    context = build_context_record(
        model=args.model,
        url=args.url,
        photos=args.photos,
        sections=args.sections,
        skroutz_status=args.skroutz_status,
        boxnow=args.boxnow,
        price=str(args.price),
    )
    work_dir = Path(args.work_root) / args.model
    context_path = work_dir / "context.json"
    llm_context_path = work_dir / "llm_context.json"
    prompt_path = work_dir / "prompt.txt"
    write_json(context_path, context)
    write_json(llm_context_path, context["llm_context"])
    prompt_template = read_text(ROOT / "master_prompt+.txt")
    prompt_text = prompt_template.replace(
        "{{LLM_CONTEXT_JSON}}",
        llm_context_path.read_text(encoding="utf-8"),
    )
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt_text, encoding="utf-8")
    print(f"Context written: {context_path}")
    print(f"LLM context written: {llm_context_path}")
    print(f"Prompt written: {prompt_path}")


if __name__ == "__main__":
    main()
