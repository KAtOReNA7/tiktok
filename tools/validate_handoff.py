"""Validate the portable handoff; --refresh updates its explicit file manifest."""
import argparse
import csv
import hashlib
import json
import re
import struct
import sys
import zlib
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
    "spec/character_identity.json", "spec/narrative_retention.json",
    "spec/program_editorial.json", "spec/program_visuals.json",
    "assets/hosts_qin_reference/gugu_qin_edge.png",
    "assets/hosts_qin_reference/mambo_qin_edge.png",
    "episode/scene_map.csv",
)
COLUMNS = ["插图编号", "对应口播"]
PROGRAM_IDS = {"MAIN_ACCOUNT", "COUNTER_REPLY", "SAME_RULE_COMPARE"}
CAPTION_SLOT = [96, 1408, 776, 128]


def paths_for_manifest():
    paths = [ROOT / name for name in ROOT_FILES if (ROOT / name).is_file()]
    for name in DIRS:
        paths.extend(p for p in (ROOT / name).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    return sorted(paths, key=lambda p: p.relative_to(ROOT).as_posix())


def validate_rgba_png(name, canvas):
    """Validate PNG chunks and actual scanline data using only the standard library."""
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError("Missing current template asset: " + name)
    png = path.read_bytes()
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not a PNG: " + name)
    offset, chunks, image_data = 8, [], bytearray()
    while offset < len(png):
        if offset + 12 > len(png):
            raise ValueError("Truncated PNG chunk: " + name)
        length = struct.unpack(">I", png[offset:offset + 4])[0]
        kind = png[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(png):
            raise ValueError("Truncated PNG data: " + name)
        payload = png[offset + 8:offset + 8 + length]
        crc = struct.unpack(">I", png[offset + 8 + length:end])[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise ValueError("PNG checksum mismatch: " + name)
        if not chunks:
            if kind != b"IHDR" or length != 13:
                raise ValueError("Invalid PNG header: " + name)
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if ((width, height) != tuple(canvas) or depth != 8 or color != 6
                    or compression != 0 or filtering != 0 or interlace != 0):
                raise ValueError("Assets must be 8-bit noninterlaced full-canvas RGBA PNGs: " + name)
        elif kind == b"IHDR":
            raise ValueError("Duplicate PNG header: " + name)
        if kind == b"IDAT":
            image_data.extend(payload)
        chunks.append(kind)
        offset = end
        if kind == b"IEND":
            if length != 0 or offset != len(png):
                raise ValueError("Invalid PNG end: " + name)
            break
    if not chunks or chunks[-1] != b"IEND" or not image_data:
        raise ValueError("Incomplete PNG image: " + name)
    row_bytes = canvas[0] * 4 + 1
    expected_bytes = row_bytes * canvas[1]
    inflater = zlib.decompressobj()
    pixels = inflater.decompress(bytes(image_data), expected_bytes + 1)
    if (len(pixels) != expected_bytes or not inflater.eof
            or inflater.unused_data or inflater.unconsumed_tail
            or any(pixels[row * row_bytes] > 4 for row in range(canvas[1]))):
        raise ValueError("Invalid PNG scanline data: " + name)


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
    narrative = json.loads((ROOT / "spec/narrative_retention.json").read_text(encoding="utf-8"))
    editorial = json.loads((ROOT / "spec/program_editorial.json").read_text(encoding="utf-8"))
    program_visuals = json.loads((ROOT / "spec/program_visuals.json").read_text(encoding="utf-8"))
    if set(editorial["programs"]) != PROGRAM_IDS or set(program_visuals["programs"]) != PROGRAM_IDS:
        raise ValueError("Editorial and visual specs must define the same three program IDs")
    if (rules["program_editorial_spec"] != "spec/program_editorial.json"
            or rules["program_visual_spec"] != "spec/program_visuals.json"
            or editorial["visual_spec"] != "spec/program_visuals.json"
            or not rules["program_id_required"]):
        raise ValueError("Delivery instructions must reference both current program specs")
    if (rules["narrative_spec"] != "spec/narrative_retention.json"
            or rules["narrative_profile_id"] != narrative["profile_id"]):
        raise ValueError("Delivery instructions must reference the current narrative profile")
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
    if (slot != CAPTION_SLOT or slot != caption["background"]["bounds"]
            or slot != caption["delivery"]["placement_in_1080x1920"]["bounds"]
            or slot[2:] != [caption["delivery"]["video_width"], caption["delivery"]["video_height"]]):
        raise ValueError("Caption video must match the reserved slot exactly")
    if template["production"]["voice_subtitles_in_scene_plate"] or caption["scene_plate"]["bake_narration_text"]:
        raise ValueError("Scene plates must leave the caption slot empty")
    canvas = (template["canvas"]["width"], template["canvas"]["height"])
    shared = program_visuals["shared"]
    if (canvas != (1080, 1920) or tuple(shared["canvas"]) != canvas
            or shared["caption_slot_bounds"] != slot
            or shared["caption_slot_rgba"] != [28, 28, 28, 255]
            or shared["caption_example_visible"]
            or not shared["scene_plate_keeps_caption_empty"]):
        raise ValueError("Program layouts must preserve the full canvas and fixed empty caption slot")
    asset_paths = [template["characters"]["overlay_file"]]
    if set(template["variants"]) != {"cover_opening", "body", "closeup", "evidence"}:
        raise ValueError("V2 must include all four reusable layout variants")
    for variant in template["variants"].values():
        if variant["caption_slot_bounds"] != slot:
            raise ValueError("All V2 variants must share the same caption slot")
        asset_paths.append(variant["base_plate"])
    programs = program_visuals["programs"]
    if (programs["MAIN_ACCOUNT"]["spec_source"] != "spec/template.json"
            or programs["MAIN_ACCOUNT"]["template_id"] != template["template_id"]
            or set(programs["MAIN_ACCOUNT"]["variants"]) != set(template["variants"])):
        raise ValueError("Main program must retain the four current V2 layout variants")
    required_variants = {
        "COUNTER_REPLY": {"question", "reply"},
        "SAME_RULE_COMPARE": {"standard", "reveal_1", "reveal_2", "reveal_3"},
    }
    program_assets = []
    for program_id, variants in required_variants.items():
        if set(programs[program_id]["variants"]) != variants:
            raise ValueError("Program visual variants incomplete: " + program_id)
        program_assets.extend(variant["base_plate"]
                              for variant in programs[program_id]["variants"].values())
    if len(program_assets) != 6 or len(set(program_assets)) != 6:
        raise ValueError("Program visuals require six distinct exported base plates")
    asset_paths.extend(program_assets)
    for name in asset_paths:
        validate_rgba_png(name, canvas)
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data["layout_template"] != template["template_id"]:
        raise ValueError("Manifest points at the wrong default template")
    prd_title = (ROOT / "PRD_V7.md").read_text(encoding="utf-8").splitlines()[0]
    prd_match = re.search(r"\bPRD V(\d+\.\d+)\b", prd_title)
    if not prd_match:
        raise ValueError("PRD title must declare its current version")
    if len({prd_match.group(1), data["prd_version"], template["prd_version"],
            caption["prd_version"], rules["prd_version"], narrative["prd_version"],
            editorial["prd_version"]}) != 1:
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
    print("PASS: %d files, PRD version, three program IDs, six program bases, decoded RGBA assets, caption-slot compatibility, asset hashes, three-host references and two-column mapping verified. Image likeness and caption pixels require visual QA." % len(data["files"]))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, json.JSONDecodeError, zlib.error, struct.error) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        sys.exit(1)
