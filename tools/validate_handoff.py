"""Validate the portable handoff; --refresh updates its explicit file manifest."""
import argparse
import csv
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifest.json"
ROOT_FILES = (
    ".gitattributes", ".gitignore", "README.md", "AGENTS.md", "START_HERE.md",
    "PRD_V7.md", "PROJECT_STATE.md", "CHANGELOG.md", "CHAT_HANDOFF.md",
)
DIRS = ("assets", "refs", "spec", "episode", "tools")
LOCAL_ONLY_DIRS = {"episodes", "research", "archive", "交付", "素材", "选题", "runs", "tmp", "exports", "local"}
REQUIRED = (
    "PRD_V7.md", "START_HERE.md", "PROJECT_STATE.md",
    "assets/template/base_plate_1080x1920.png",
    "refs/identity/doro_primary_user.png", "refs/identity/doro_expression_user.png",
    "spec/template.json", "spec/caption_style.json", "spec/delivery_rules.json",
    "spec/character_identity.json",
    "assets/hosts_qin_reference/gugu_qin_edge.png",
    "assets/hosts_qin_reference/mambo_qin_edge.png",
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
    identity = json.loads((ROOT / "spec/character_identity.json").read_text(encoding="utf-8"))
    if not identity["all_hosts_must_be_chibi"] or not identity["actual_reference_input_for_each_visible_host"]:
        raise ValueError("All three hosts require Q-version identity and actual reference inputs")
    if set(identity["characters"]) != {"doro", "gugu", "mambo"}:
        raise ValueError("Identity specification must cover all three hosts")
    for character in identity["characters"].values():
        ref = (ROOT / character["identity_reference"]).resolve()
        if not ref.is_relative_to(ROOT) or not ref.is_file():
            raise ValueError("Missing or invalid host identity reference")
    if identity["qa"]["rejected_or_unverified_deliverable"]:
        raise ValueError("Rejected or unverified identity cannot be delivered as approved")
    if rules["character_identity_spec"] != "spec/character_identity.json":
        raise ValueError("Delivery rules must reference the current identity specification")
    correction = identity["correction"]
    if (correction["user_character_approval_required"]
            or correction["one_user_confirmation_before_batch_after_reported_drift"]
            or correction["approval_for_every_stable_image"]
            or rules["character_acceptance"]["user_approval_required"]):
        raise ValueError("Character checks must not require user approval")
    if not (correction["continue_after_internal_pass"]
            and rules["character_acceptance"]["continue_after_internal_identity_pass"]):
        raise ValueError("Continue production after internal character validation")
    template = json.loads((ROOT / "spec/template.json").read_text(encoding="utf-8"))
    caption = json.loads((ROOT / "spec/caption_style.json").read_text(encoding="utf-8"))
    if template["template_id"] != caption["template_id"] or template["template_id"] != rules["default_template_id"]:
        raise ValueError("Template, caption and delivery defaults disagree")
    slot = template["fields"]["字幕视频预留槽"]["bounds"]
    if (slot != caption["background"]["bounds"]
            or slot != caption["delivery"]["placement_in_1080x1920"]["bounds"]
            or slot[2:] != [caption["delivery"]["video_width"], caption["delivery"]["video_height"]]):
        raise ValueError("Caption video must match the reserved slot exactly")
    if template["production"]["voice_subtitles_in_scene_plate"] or caption["scene_plate"]["bake_narration_text"]:
        raise ValueError("Scene plates must leave the caption slot empty")
    canvas = (template["canvas"]["width"], template["canvas"]["height"])
    asset_paths = [template["characters"]["overlay_file"]]
    if set(template["variants"]) != {"cover_opening", "body", "closeup", "evidence"}:
        raise ValueError("V2 must include all four reusable layout variants")
    for variant in template["variants"].values():
        if variant["caption_slot_bounds"] != slot:
            raise ValueError("All V2 variants must share the same caption slot")
        asset_paths.append(variant["base_plate"])
    for name in asset_paths:
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError("Missing current template asset: " + name)
        png = path.read_bytes()
        if (png[:8] != b"\x89PNG\r\n\x1a\n" or png[12:16] != b"IHDR"
                or struct.unpack(">II", png[16:24]) != canvas or png[25] != 6):
            raise ValueError("V2 assets must be full-canvas RGBA PNGs: " + name)
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data["layout_template"] != template["template_id"]:
        raise ValueError("Manifest points at the wrong default template")
    if len({data["prd_version"], template["prd_version"], caption["prd_version"], rules["prd_version"]}) != 1:
        raise ValueError("PRD versions disagree across active specs")
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
        if Path(name).parts[0] in LOCAL_ONLY_DIRS:
            raise ValueError("Local-only content must not enter the handoff manifest: " + name)
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
    if any(name not in seen for name in asset_paths):
        raise ValueError("Manifest omits current template assets")
    print("PASS: %d files, V2 RGBA assets, caption-slot compatibility, asset hashes, three-host references and two-column mapping verified. Image likeness requires visual QA." % len(data["files"]))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        sys.exit(1)
