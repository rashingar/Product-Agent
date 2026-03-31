#!/usr/bin/env python3
"""
Repo-native OpenCart image uploader.

Intended pipeline step:
- product generation creates work/{model}/scrape/gallery/*.jpg
- optional Besco generation creates work/{model}/scrape/bescos/*.jpg
- this script uploads both sets into OpenCart admin filemanager:
    image/catalog/01_main/{model}/
    image/catalog/01_bescos/{model}/

Default local layout is inferred from the repo root instead of hardcoded absolute paths.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import requests

TIMEOUT = 60
ALLOWED_EXTS = {".jpg", ".jpeg"}
DEFAULT_ADMIN_PATH = "/ipadmin/index.php"


class UploadError(RuntimeError):
    pass


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def natural_key(name: str) -> list[Any]:
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", name)]


def discover_repo_root(explicit_repo_root: str | None) -> Path:
    """
    Repo-native discovery order:
    1) --repo-root
    2) OPENCART_PIPELINE_REPO_ROOT env
    3) walk up from this file until a directory containing 'work' or '.git' is found
    4) walk up from cwd with same rule
    """
    candidates: list[Path] = []

    if explicit_repo_root:
        candidates.append(Path(explicit_repo_root).expanduser().resolve())

    env_repo_root = os.environ.get("OPENCART_PIPELINE_REPO_ROOT")
    if env_repo_root:
        candidates.append(Path(env_repo_root).expanduser().resolve())

    def walk_up(start: Path) -> list[Path]:
        out = [start]
        out.extend(start.parents)
        return out

    candidates.extend(walk_up(Path(__file__).resolve().parent))
    candidates.extend(walk_up(Path.cwd().resolve()))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "work").is_dir() or (candidate / ".git").exists():
            return candidate

    raise UploadError(
        "Could not auto-detect repo root. Pass --repo-root or set OPENCART_PIPELINE_REPO_ROOT."
    )


def build_admin_index(store_base: str, admin_path: str) -> str:
    return f"{store_base.rstrip('/')}/{admin_path.lstrip('/')}"


def is_valid_model(value: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", value or ""))


def validate_gallery_files(model: str, gallery_dir: Path) -> list[Path]:
    if not gallery_dir.is_dir():
        raise UploadError(f"Gallery directory not found: {gallery_dir}")

    files = sorted(
        [p for p in gallery_dir.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_EXTS],
        key=lambda p: natural_key(p.name),
    )
    if not files:
        raise UploadError(f"No JPG/JPEG gallery images found in: {gallery_dir}")

    expected = [f"{model}-{idx}.jpg" for idx in range(1, len(files) + 1)]
    actual = [p.name for p in files]

    if actual != expected:
        raise UploadError(
            "Gallery files must be contiguous and match the repo convention exactly.\n"
            f"Expected: {expected}\n"
            f"Actual:   {actual}"
        )

    return files


def validate_besco_files(besco_dir: Path) -> list[Path]:
    if not besco_dir.exists():
        return []
    if not besco_dir.is_dir():
        raise UploadError(f"Besco path exists but is not a directory: {besco_dir}")

    files = sorted(
        [p for p in besco_dir.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_EXTS],
        key=lambda p: natural_key(p.name),
    )

    if not files:
        return []

    expected = [f"besco{idx}.jpg" for idx in range(1, len(files) + 1)]
    actual = [p.name for p in files]

    if actual != expected:
        raise UploadError(
            "Besco files must be contiguous and match the repo convention exactly.\n"
            f"Expected: {expected}\n"
            f"Actual:   {actual}"
        )

    return files


def build_plan(repo_root: Path, model: str) -> dict[str, Any]:
    if not is_valid_model(model):
        raise UploadError("Model must be exactly 6 digits.")

    work_dir = repo_root / "work" / model
    scrape_dir = work_dir / "scrape"
    gallery_dir = scrape_dir / "gallery"
    besco_dir = scrape_dir / "bescos"

    gallery_files = validate_gallery_files(model, gallery_dir)
    besco_files = validate_besco_files(besco_dir)

    main_remote_dir = f"01_main/{model}"
    besco_remote_dir = f"01_bescos/{model}"

    return {
        "repo_root": str(repo_root),
        "model": model,
        "work_dir": str(work_dir),
        "gallery_dir": str(gallery_dir),
        "bescos_dir": str(besco_dir),
        "gallery": {
            "local_files": [str(p) for p in gallery_files],
            "remote_dir": main_remote_dir,
            "remote_files": [f"catalog/{main_remote_dir}/{p.name}" for p in gallery_files],
            "count": len(gallery_files),
            "main_image": f"catalog/01_main/{model}/{model}-1.jpg",
            "additional_image": ":::".join(
                f"catalog/01_main/{model}/{model}-{idx}.jpg"
                for idx in range(2, len(gallery_files) + 1)
            ),
        },
        "bescos": {
            "local_files": [str(p) for p in besco_files],
            "remote_dir": besco_remote_dir,
            "remote_files": [f"catalog/{besco_remote_dir}/{p.name}" for p in besco_files],
            "count": len(besco_files),
            "html_base": f"https://www.etranoulis.gr/image/catalog/01_bescos/{model}/",
        },
    }


def _extract_user_token_from_url(url: str) -> str | None:
    if not url:
        return None
    return parse_qs(urlparse(url).query).get("user_token", [None])[0]


def _is_permission_denied_error(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    markers = [
        "permission",
        "denied",
        "δεν έχετε άδεια",
        "δεν εχετε αδεια",
        "άδεια",
        "αδεια",
        "permission denied",
    ]
    return any(marker in lowered for marker in markers)


def _is_missing_directory_error(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    markers = [
        "directory",
        "folder",
        "does not exist",
        "not found",
        "δεν υπάρχει ο φάκελος",
        "δεν υπαρχει ο φακελος",
        "φάκελος",
        "φακελος",
    ]
    return any(marker in lowered for marker in markers)


def _is_already_exists_error(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    markers = [
        "already exists",
        "exists",
        "υπάρχει ήδη",
        "υπαρχει ηδη",
        "ίδιο όνομα",
        "ιδιο ονομα",
    ]
    return any(marker in lowered for marker in markers)


def login(session: requests.Session, admin_index: str, username: str, password: str) -> str:
    login_url = f"{admin_index}?route=common/login"

    # Browser-like defaults help with some hosts/WAFs.
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )

    # 1) Warm the session first so PHPSESSID / cookies are established.
    warm = session.get(login_url, allow_redirects=True, timeout=TIMEOUT)

    # If already authenticated for some reason, the token may already be present.
    token = _extract_user_token_from_url(str(warm.url))
    if token:
        return token

    # 2) Submit login without auto-following redirects so we can inspect the raw redirect.
    resp = session.post(
        login_url,
        data={
            "username": username,
            "password": password,
        },
        headers={
            "Referer": login_url,
            "Origin": admin_index.rsplit("/index.php", 1)[0],
        },
        allow_redirects=False,
        timeout=TIMEOUT,
    )

    # Primary success path: stock OpenCart redirects with user_token in Location.
    location = resp.headers.get("Location", "")
    token = _extract_user_token_from_url(location)
    if token:
        return token

    # 3) Fallback: some setups may redirect in a second hop or normalize the URL.
    # Follow once manually using the same session/cookies.
    if resp.is_redirect and location:
        follow = session.get(location, allow_redirects=True, timeout=TIMEOUT)
        token = _extract_user_token_from_url(str(follow.url))
        if token:
            return token

    # 4) If we are here, login did not complete as expected.
    body_preview = (resp.text or "")[:800].replace("\n", " ")
    cookie_names = sorted(session.cookies.keys())

    raise UploadError(
        "Login failed: no user_token returned.\n"
        f"POST {login_url}\n"
        f"HTTP={resp.status_code}\n"
        f"Location={location!r}\n"
        f"ResponseURL={resp.url!r}\n"
        f"Cookies={cookie_names}\n"
        f"BodyPreview={body_preview!r}"
    )


def permission_probe(session: requests.Session, admin_index: str, user_token: str) -> dict[str, Any]:
    url = (
        f"{admin_index}?route=common/filemanager/folder"
        f"&user_token={quote(user_token)}&directory=__dryrun_invalid_directory__"
    )
    resp = session.post(url, data={"folder": "dryrunprobe"}, timeout=TIMEOUT)
    resp.raise_for_status()

    try:
        data = resp.json()
    except Exception as exc:  # pragma: no cover
        raise UploadError(f"Permission probe did not return JSON: {exc}") from exc

    error_text = str(data.get("error", ""))
    return {
        "raw": data,
        "permission_denied": _is_permission_denied_error(error_text),
        "directory_probe_hit": _is_missing_directory_error(error_text),
        "can_modify": (not _is_permission_denied_error(error_text)) and _is_missing_directory_error(error_text),
    }


def create_folder(session: requests.Session, admin_index: str, user_token: str, parent_dir: str, folder_name: str) -> None:
    url = (
        f"{admin_index}?route=common/filemanager/folder"
        f"&user_token={quote(user_token)}&directory={quote(parent_dir)}"
    )
    resp = session.post(url, data={"folder": folder_name}, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if data.get("error"):
        err = str(data["error"])
        if _is_already_exists_error(err):
            return
        raise UploadError(
            f"Folder create failed. parent={parent_dir!r}, folder={folder_name!r}, response={data}"
        )


def ensure_remote_nested_dir(session: requests.Session, admin_index: str, user_token: str, remote_dir: str) -> None:
    parent = ""
    for part in [p for p in remote_dir.split("/") if p]:
        create_folder(session, admin_index, user_token, parent, part)
        parent = f"{parent}/{part}".strip("/")


def upload_files(
    session: requests.Session,
    admin_index: str,
    user_token: str,
    remote_dir: str,
    file_paths: list[str],
) -> dict[str, Any]:
    url = (
        f"{admin_index}?route=common/filemanager/upload"
        f"&user_token={quote(user_token)}&directory={quote(remote_dir)}"
    )

    handles = []
    files = []
    try:
        for path_str in file_paths:
            path = Path(path_str)
            fh = open(path, "rb")
            handles.append(fh)
            files.append(("file[]", (path.name, fh, "image/jpeg")))

        resp = session.post(url, files=files, timeout=300)
        resp.raise_for_status()
        data = resp.json()

        if data.get("error"):
            raise UploadError(f"Upload failed for {remote_dir}: {data}")

        return data
    finally:
        for fh in handles:
            fh.close()


def write_report(report_path: Path, payload: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload repo-native product images to OpenCart filemanager.")
    parser.add_argument("--model", required=True, help="6-digit model, e.g. 123456")
    parser.add_argument("--repo-root", default=None, help="Optional explicit repo root")
    parser.add_argument("--store-base", default=os.environ.get("OPENCART_STORE_BASE", "https://www.etranoulis.gr"))
    parser.add_argument("--admin-path", default=os.environ.get("OPENCART_ADMIN_PATH", DEFAULT_ADMIN_PATH))
    parser.add_argument("--username", default=os.environ.get("OPENCART_ADMIN_USER"))
    parser.add_argument("--password", default=os.environ.get("OPENCART_ADMIN_PASS"))
    parser.add_argument("--dry-run", action="store_true", help="Validate and auth-check only, do not upload")
    parser.add_argument(
        "--report-file",
        default=None,
        help="Optional explicit report path. Default: work/{model}/upload.opencart.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.username or not args.password:
        raise UploadError(
            "Missing admin credentials. Pass --username/--password or set OPENCART_ADMIN_USER and OPENCART_ADMIN_PASS."
        )

    repo_root = discover_repo_root(args.repo_root)
    plan = build_plan(repo_root, args.model)
    admin_index = build_admin_index(args.store_base, args.admin_path)

    report_path = (
        Path(args.report_file).expanduser().resolve()
        if args.report_file
        else (repo_root / "work" / args.model / "upload.opencart.json")
    )

    result: dict[str, Any] = {
        "ok": False,
        "dry_run": bool(args.dry_run),
        "admin_index": admin_index,
        "plan": plan,
    }

    print(json.dumps({
        "model": plan["model"],
        "repo_root": plan["repo_root"],
        "gallery_count": plan["gallery"]["count"],
        "bescos_count": plan["bescos"]["count"],
        "gallery_remote_dir": plan["gallery"]["remote_dir"],
        "bescos_remote_dir": plan["bescos"]["remote_dir"],
        "main_image": plan["gallery"]["main_image"],
        "additional_image": plan["gallery"]["additional_image"],
    }, ensure_ascii=False, indent=2))

    session = requests.Session()
    user_token = login(session, admin_index, args.username, args.password)
    result["login"] = {"ok": True, "user_token_present": bool(user_token)}

    probe = permission_probe(session, admin_index, user_token)
    result["permission_probe"] = probe

    if probe["permission_denied"]:
        raise UploadError("Logged in, but the admin user lacks modify permission on common/filemanager.")
    if not probe["can_modify"]:
        raise UploadError(
            "Could not confirm modify permission cleanly. Expected an invalid-directory error from the dry-run probe."
        )

    if args.dry_run:
        result["ok"] = True
        result["message"] = "Dry run passed. No folders created, no files uploaded."
        write_report(report_path, result)
        print(f"Dry run OK. Report written to: {report_path}")
        return 0

    uploads: dict[str, Any] = {}

    ensure_remote_nested_dir(session, admin_index, user_token, plan["gallery"]["remote_dir"])
    uploads["gallery"] = upload_files(
        session=session,
        admin_index=admin_index,
        user_token=user_token,
        remote_dir=plan["gallery"]["remote_dir"],
        file_paths=plan["gallery"]["local_files"],
    )

    if plan["bescos"]["count"] > 0:
        ensure_remote_nested_dir(session, admin_index, user_token, plan["bescos"]["remote_dir"])
        uploads["bescos"] = upload_files(
            session=session,
            admin_index=admin_index,
            user_token=user_token,
            remote_dir=plan["bescos"]["remote_dir"],
            file_paths=plan["bescos"]["local_files"],
        )
    else:
        uploads["bescos"] = {"skipped": True, "reason": "No besco images found."}

    result["uploads"] = uploads
    result["ok"] = True
    write_report(report_path, result)
    print(f"Upload OK. Report written to: {report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except UploadError as exc:
        eprint(f"ERROR: {exc}")
        raise SystemExit(1)
