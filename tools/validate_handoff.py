"""Validate the portable handoff; --refresh updates its explicit file manifest."""
import argparse
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path
from validate_mapping_csv import COLUMNS, validate_mapping_csv

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
    "tools/validate_mapping_csv.py", "tools/validate_caption_pages.py",
    "spec/legacy/v2/template.json", "spec/legacy/v2/caption_style.json",
    "spec/legacy/v2/program_visuals.json",
)
PROGRAM_IDS = {"MAIN_ACCOUNT", "COUNTER_REPLY", "SAME_RULE_COMPARE"}
TITLE_BOUNDS = [64, 208, 810, 160]
STORY_BOUNDS = [40, 400, 1000, 1240]
CAPTION_PANEL = [80, 1398, 820, 170]
CAPTION_TEXT = [100, 1420, 760, 128]
CAPTION_PROFILE = "STATIC_CAPTION_PAGES_V1"
EDGE_HOSTS = {"doro": [870, 368, 230, 230], "gugu": [-30, 790, 220, 220],
              "mambo": [680, 1190, 220, 220]}


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
    validate_mapping_csv(ROOT / "episode/scene_map.csv", allow_header_only=True)
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
    csv_export = rules["scene_map"]["csv_export"]
    if (csv_export["encoding_profile_id"] != "CSV_EXCEL_UTF8_BOM_V1"
            or csv_export["encoding"] != "utf-8-sig" or csv_export["bom_hex"] != "EF BB BF"
            or csv_export["bom_count"] != 1 or csv_export["record_separator"] != "CRLF"
            or csv_export["delimiter"] != "," or csv_export["quotechar"] != '"'
            or not csv_export["strict_decode"] or not csv_export["readback_actual_file"]
            or not csv_export["preserve_cells_exactly"]):
        raise ValueError("Delivered CSV must require one UTF-8 BOM, CRLF and lossless strict readback")
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
    fields = template["fields"]
    canvas = (template["canvas"]["width"], template["canvas"]["height"])
    shared = program_visuals["shared"]
    if (template["template_id"] != "RYP_STORY_MAIN_V3" or canvas != (1080, 1920)
            or fields["漫画主画面"]["bounds"] != STORY_BOUNDS
            or fields["常驻主题"]["bounds"] != TITLE_BOUNDS
            or fields["口播面板"]["bounds"] != CAPTION_PANEL
            or fields["口播字幕"]["bounds"] != CAPTION_TEXT
            or caption["background"]["bounds"] != CAPTION_PANEL
            or caption["text"]["bounds"] != CAPTION_TEXT):
        raise ValueError("V3 canvas, persistent title, story and static-caption geometry disagree")
    if (fields["常驻主题"]["font_size_px"] != 62 or fields["常驻主题"]["line_height_px"] != 76
            or caption["text"]["font_size_px"] != 48 or caption["text"]["line_height_px"] != 64
            or caption["text"]["max_lines"] != 2 or caption["text"]["auto_shrink"]):
        raise ValueError("V3 requires measured two-line text at the specified font size, never auto-shrink")
    if (not template["limits"]["persistent_topic_on_every_final_page"]
            or template["limits"]["top_brand_or_slogan"]
            or not template["production"]["voice_subtitles_in_scene_plate"]
            or not template["production"]["hosts_in_scene_plate"]
            or not caption["scene_plate"]["bake_narration_text_in_final_png"]
            or caption["scene_plate"]["keep_empty_black_slot_in_final_png"]
            or caption["delivery"]["primary"] != "static_caption_baked_final_png"
            or caption["delivery"]["final_voice_required"]
            or rules["final_voice_required_for_default_delivery"]
            or rules["caption_delivery_default"] != caption["delivery"]["primary"]):
        raise ValueError("V3 final PNGs must contain persistent title, actors and static captions without waiting for audio")
    profiles = {template["caption_profile_id"], caption["profile_id"], rules["caption_profile_id"],
                editorial["caption_profile_id"], program_visuals["caption_profile_id"],
                shared["caption_profile_id"], narrative["visual_execution"]["caption_profile_id"]}
    if profiles != {CAPTION_PROFILE}:
        raise ValueError("Active specs must share the static-caption profile")
    if (tuple(shared["canvas"]) != canvas or shared["story_bounds"] != STORY_BOUNDS
            or shared["persistent_title_bounds"] != TITLE_BOUNDS
            or shared["caption_panel_bounds"] != CAPTION_PANEL
            or shared["caption_text_bounds"] != CAPTION_TEXT
            or not shared["final_png_bakes_current_caption"]
            or shared["base_has_episode_text"] or shared["base_has_hosts"]
            or shared["base_fixed_text_allowlist"] != ["锐评"]):
        raise ValueError("Program layouts must share V3 geometry and only the fixed seal text in blank bases")
    slots = template["characters"]["slots"]
    if ({key: value["bounds"] for key, value in slots.items()} != EDGE_HOSTS
            or shared["edge_hosts_bounds"] != EDGE_HOSTS
            or not template["characters"]["do_not_reoverlay_on_final_png"]):
        raise ValueError("V3 must use all three spread edge positions without duplicate overlays")
    for name in ("top", "right", "bottom"):
        area = template["safe_area"][name]
        rect = [area[key] for key in ("x", "y", "width", "height")]
        expected = {"top": [0, 0, 1080, 208], "right": [920, 540, 160, 1100],
                    "bottom": [0, 1640, 1080, 280]}[name]
        if rect != expected:
            raise ValueError("Project UI-risk reservations changed without reviewed geometry")
    asset_paths = [template["characters"]["overlay_file"]]
    if set(template["variants"]) != {"cover_opening", "body", "closeup", "evidence"}:
        raise ValueError("V3 must include four reusable main layout variants")
    for variant in template["variants"].values():
        if (variant["caption_text_bounds"] != CAPTION_TEXT
                or variant["persistent_title_bounds"] != TITLE_BOUNDS):
            raise ValueError("All main V3 variants must retain title and caption geometry")
        asset_paths.append(variant["base_plate"])
    programs = program_visuals["programs"]
    if (programs["MAIN_ACCOUNT"]["spec_source"] != "spec/template.json"
            or programs["MAIN_ACCOUNT"]["template_id"] != template["template_id"]
            or set(programs["MAIN_ACCOUNT"]["variants"]) != set(template["variants"])):
        raise ValueError("Main program must reference the active V3 layout variants")
    required_variants = {
        "COUNTER_REPLY": {"question", "reply"},
        "SAME_RULE_COMPARE": {"standard", "reveal_1", "reveal_2", "reveal_3"},
    }
    program_assets = []
    for program_id, variants in required_variants.items():
        program = programs[program_id]
        if set(program["variants"]) != variants or program["template_id"] != template["template_id"]:
            raise ValueError("V3 program visual variants incomplete: " + program_id)
        for variant in program["variants"].values():
            if (variant["caption_text_bounds"] != CAPTION_TEXT
                    or variant["persistent_title_bounds"] != TITLE_BOUNDS):
                raise ValueError("Program variant lost persistent V3 title or caption geometry")
            program_assets.append(variant["base_plate"])
    if len(program_assets) != 6 or len(set(program_assets)) != 6:
        raise ValueError("Program visuals require six separately named reusable base plates")
    if [variant["active_case"] for variant in programs["SAME_RULE_COMPARE"]["variants"].values()] != [0, 1, 2, 3]:
        raise ValueError("Compare states must reveal the standard then each of three distinct cases")
    if programs["SAME_RULE_COMPARE"]["identity_card_visible"]:
        raise ValueError("Three-case comparison must not overlay the single-actor identity card")
    asset_paths.extend(program_assets)
    inventory = template["local_assets"]["asset_inventory"]
    if len(inventory) != 11 or {asset["file"] for asset in inventory} != set(asset_paths):
        raise ValueError("V3 inventory must contain exactly ten bases and one spread-host overlay")
    for asset in inventory:
        name = asset["file"]
        if not name.startswith("assets/template/v3/"):
            raise ValueError("Current V3 assets must not point at legacy files")
        validate_rgba_png(name, canvas)
        content = (ROOT / name).read_bytes()
        if len(content) != asset["bytes"] or hashlib.sha256(content).hexdigest() != asset["sha256"]:
            raise ValueError("V3 asset inventory differs from the exported PNG: " + name)
    legacy = json.loads((ROOT / "spec/legacy/v2/template.json").read_text(encoding="utf-8"))
    legacy_caption = json.loads((ROOT / "spec/legacy/v2/caption_style.json").read_text(encoding="utf-8"))
    if (legacy["template_id"] != "RYP_STORY_MAIN_V2"
            or legacy_caption["delivery"]["primary"] != "black_background_mp4"
            or legacy["fields"]["字幕视频预留槽"]["bounds"] != [96, 1408, 776, 128]):
        raise ValueError("Explicit V2 compatibility must retain its original geometry and MP4 spec")
    for variant in legacy["variants"].values():
        if not (ROOT / variant["base_plate"]).is_file():
            raise ValueError("Legacy V2 asset missing: " + variant["base_plate"])
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (data["layout_template"] != template["template_id"]
            or data["caption_profile_id"] != CAPTION_PROFILE):
        raise ValueError("Manifest points at the wrong default template")
    prd_title = (ROOT / "PRD_V7.md").read_text(encoding="utf-8").splitlines()[0]
    prd_match = re.search(r"\bPRD V(\d+\.\d+)\b", prd_title)
    if not prd_match:
        raise ValueError("PRD title must declare its current version")
    if len({prd_match.group(1), data["prd_version"], template["prd_version"],
            caption["prd_version"], rules["prd_version"], narrative["prd_version"],
            editorial["prd_version"], program_visuals["prd_version"], identity["prd_version"]}) != 1:
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
    print("PASS: %d files, PRD version, three V3 programs, ten bases and spread-host overlay, decoded RGBA assets, persistent title/static-caption geometry, legacy V2 compatibility, asset hashes and BOM/CRLF mapping template verified. Validate actual page plans/CSV files separately; rendered text, likeness and phone-preview safety require visual QA." % len(data["files"]))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, json.JSONDecodeError, zlib.error, struct.error) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        sys.exit(1)
