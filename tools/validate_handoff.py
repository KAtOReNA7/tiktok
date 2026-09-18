"""Validate the portable handoff; --refresh updates its explicit file manifest."""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.json"
ROOT_FILES = (
    ".gitattributes", ".gitignore", "README.md", "AGENTS.md", "START_HERE.md",
    "PRD_V7.md", "PROJECT_STATE.md", "CHANGELOG.md", "CHAT_HANDOFF.md",
)
DIRS = ("assets", "refs", "spec", "episode", "episodes", "archive", "tools")
REQUIRED = (
    "PRD_V7.md", "START_HERE.md", "PROJECT_STATE.md",
    "assets/template/base_plate_1080x1920.png",
    "refs/identity/doro_primary_user.png", "refs/identity/doro_expression_user.png",
    "spec/template.json", "spec/caption_style.json", "spec/delivery_rules.json",
    "episode/scene_map.csv",
)
COLUMNS = ["插图编号", "对应口播"]


def paths_for_manifest():
    paths = [ROOT / name for name in ROOT_FILES if (ROOT / name).is_file()]
    for name in DIRS:
        paths.extend(p for p in (ROOT / name).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    return sorted(paths, key=lambda p: p.relative_to(ROOT).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    for name in REQUIRED:
        if not (ROOT / name).is_file():
            raise ValueError("Missing required file: " + name)
    with (ROOT / "episode/scene_map.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] != COLUMNS or any(len(r) != 2 for r in rows):
        raise ValueError("scene_map.csv must have exactly two columns")
    rules = json.loads((ROOT / "spec/delivery_rules.json").read_text(encoding="utf-8"))
    if rules["scene_map"]["columns"] != COLUMNS or rules["scene_map"]["extra_columns_allowed"]:
        raise ValueError("delivery_rules.json has a conflicting scene-map schema")
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.refresh:
        data["files"] = []
        for path in paths_for_manifest():
            content = path.read_bytes()
            data["files"].append({"path": path.relative_to(ROOT).as_posix(),
                                  "bytes": len(content),
                                  "sha256": hashlib.sha256(content).hexdigest()})
        MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    seen = set()
    for entry in data["files"]:
        name = entry["path"]
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or name in seen:
            raise ValueError("Invalid or duplicate manifest path: " + name)
        seen.add(name)
        content = path.read_bytes()
        if len(content) != entry["bytes"] or hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError("Manifest mismatch: " + name)
        if path.suffix.lower() == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Not a PNG: " + name)
    if any(name not in seen for name in REQUIRED):
        raise ValueError("Manifest omits required handoff files")
    print("PASS: %d files, asset hashes and two-column mapping verified." % len(data["files"]))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        sys.exit(1)
