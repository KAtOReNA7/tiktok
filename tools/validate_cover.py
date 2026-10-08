"""Validate fixed cover assets or an actual local pair of publishing-cover PNGs.

The asset check uses only the standard library. Actual render checks use Pillow.
Geometry and actor-alpha checks cannot prove likeness, readability or fair crops;
those remain internal visual checks of both actual output PNGs.
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

from validate_host_overlay import read_rgba_alpha, validate_host_overlay

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "COVER_DUAL_RATIO_FIXED_V2"
EXPECTED = {"cover_3x4": ("3:4", 1080, 1440, "cover_3x4_path"),
            "cover_4x3": ("4:3", 1440, 1080, "cover_4x3_path")}
FIXED_GEOMETRY = {
    "cover_3x4": {"story": [160, 16, 744, 1008], "title": [64, 1060, 840, 312],
                  "font": 92, "line": 104, "lines": 3, "seal": [24, 36, 64, 80],
                  "hosts": {"doro": [920, 8, 144, 144], "gugu": [8, 572, 144, 144],
                            "mambo": [920, 1292, 144, 144]}},
    "cover_4x3": {"story": [160, 16, 1112, 712], "title": [72, 764, 1200, 208],
                  "font": 92, "line": 104, "lines": 2, "seal": [24, 36, 64, 80],
                  "hosts": {"doro": [1288, 8, 144, 144], "gugu": [8, 424, 144, 144],
                            "mambo": [1288, 928, 144, 144]}},
}
FIXED_FONT_FILE = "assets/fonts/NotoSansSC-Black.otf"
FIXED_FONT_SHA256 = "ccb496022356b7dd14d117538a472ae40feff8f6e8f3fe8bffc5616785d2f3f9"
_ASSET_VALIDATION_CACHE = {}


def validate_highlight_line_indices(value, line_count, label="highlight_line_indices"):
    """Require deliberate emphasis on one or two existing, distinct title lines."""
    if (not isinstance(value, list) or not 1 <= len(value) <= 2
            or any(type(index) is not int or not 0 <= index < line_count for index in value)
            or len(set(value)) != len(value)):
        raise ValueError(label + " must explicitly select one or two distinct 0-based title-line indices")


def _resolve_job_art(job_path, value):
    if not isinstance(value, str) or not value:
        raise ValueError("Local cover art sources must be explicit nonempty paths")
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (job_path.parent / path).resolve()


def _safe_asset(root, name):
    if not isinstance(name, str):
        raise ValueError("Cover asset paths must be explicit repository-relative strings")
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Missing or invalid fixed cover asset: " + name)
    return path


def _rectangle(value, canvas, label):
    if not isinstance(value, list) or len(value) != 4 or any(type(number) is not int for number in value):
        raise ValueError(label + " must declare integer x/y/width/height")
    x, y, width, height = value
    if min(x, y) < 0 or min(width, height) <= 0 or x + width > canvas[0] or y + height > canvas[1]:
        raise ValueError(label + " must remain inside its publishing-cover canvas")


def _intersects(first, second):
    return (first[0] < second[0] + second[2] and second[0] < first[0] + first[2]
            and first[1] < second[1] + second[3] and second[1] < first[1] + first[3])


def validate_cover_spec(spec, root=ROOT):
    root = Path(root).resolve()
    if (spec["profile_id"] != PROFILE or spec["cover_template_revision"] != "2.0.0"
            or spec["required_per_part"] != 2 or spec["format"] != "PNG"
            or set(spec["variants"]) != set(EXPECTED)):
        raise ValueError("Two fixed V2 publishing-cover masters are required")
    composition, delivery, assets = spec["composition"], spec["delivery"], spec["assets"]
    if (composition["independent_layout_per_ratio"]
            or not composition["fixed_master_per_ratio"]
            or composition["stretch_9x16_screenshot"] or composition["blind_center_crop"]
            or composition["reuse_video_fixed_host_coordinates"]
            or composition["video_host_overlay_validator_applies"]
            or composition["narration_paragraph_required"]
            or composition["empty_video_caption_slot_required"]
            or not delivery["blank_baseplate_required"]
            or delivery["include_in_caption_mapping"] or delivery["insert_at_video_opening"]
            or delivery["per_image_user_confirmation_required"]
            or assets["can_produce_without_prebuilt_baseplate"]):
        raise ValueError("Fill the fixed masters; free redesign, missing-base improvisation and extra confirmation are prohibited")
    typography = spec["typography"]
    if (typography["font_file"] != FIXED_FONT_FILE
            or typography["fallback_allowed"] or typography["auto_shrink"]
            or typography["approved_title_rewrite_allowed"]
            or typography["line_break_mode"] != "explicit_lossless_lines_per_ratio"):
        raise ValueError("Use the bundled font and lossless explicit title lines; no fallback, shrinking or rewriting")
    inventory = assets["asset_inventory"]
    if not isinstance(inventory, list) or not inventory:
        raise ValueError("Fixed cover resources require a real hash inventory")
    names, paths = set(), {}
    for entry in inventory:
        name = entry["file"]
        if name in names:
            raise ValueError("Duplicate fixed cover asset: " + name)
        names.add(name)
        path = _safe_asset(root, name)
        raw = path.read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Fixed cover asset differs from approved export: " + name)
        if name == FIXED_FONT_FILE and entry["sha256"] != FIXED_FONT_SHA256:
            raise ValueError("Fixed V2 covers cannot change their bundled font bytes")
        paths[name] = path
    for key in ("font_file", "license_file"):
        if typography[key] not in names:
            raise ValueError("Cover font and its license must be included in the asset inventory")
    # Bytes/hashes are checked on every invocation. Reuse decoded geometry checks
    # only when the complete spec and every approved resource still match.
    cache_key = (str(root), hashlib.sha256(json.dumps(spec, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest())
    if cache_key in _ASSET_VALIDATION_CACHE:
        return copy.deepcopy(_ASSET_VALIDATION_CACHE[cache_key])
    for entry in inventory:
        if entry["file"].lower().endswith(".png"):
            read_rgba_alpha(paths[entry["file"]], entry["canvas"])
    results = {}
    for name, expected in EXPECTED.items():
        variant = spec["variants"][name]
        if tuple(variant[key] for key in ("aspect_ratio", "width", "height", "parts_csv_column")) != expected:
            raise ValueError("Wrong fixed cover canvas: " + name)
        canvas = expected[1:3]
        for key in ("base_plate", "hosts_overlay"):
            if variant[key] not in names:
                raise ValueError("Fixed cover master asset omitted: " + variant[key])
            read_rgba_alpha(paths[variant[key]], canvas)
        layout = variant["layout"]
        title = layout["title"]
        frozen = FIXED_GEOMETRY[name]
        if (layout["story_bounds"] != frozen["story"] or title["bounds"] != frozen["title"]
                or layout["seal_bounds"] != frozen["seal"]
                or title["font_size_px"] != frozen["font"]
                or title["line_height_px"] != frozen["line"]
                or title["max_lines"] != frozen["lines"]
                or title.get("vertical_alignment") != "center"
                or {host: slot["bounds"] for host, slot in layout["host_slots"].items()} != frozen["hosts"]
                or title["fill"] != "#FFFFFF"
                or title["highlight"] != {"mode": "explicit_line_indices", "fill": "#F2FA00",
                                          "text_fill": "#161616", "right_padding_px": 16,
                                          "full_line_height": True, "full_width": True}):
            raise ValueError("Fixed cover 2.0.0 geometry, typography or host anchors changed without a new design revision: " + name)
        for label, bounds in (("story_bounds", layout["story_bounds"]),
                              ("title.bounds", title["bounds"]),
                              ("seal_bounds", layout["seal_bounds"])):
            _rectangle(bounds, canvas, name + "." + label)
        if _intersects(layout["story_bounds"], title["bounds"]) or _intersects(layout["story_bounds"], layout["seal_bounds"]):
            raise ValueError("Story window cannot overlap the fixed title or seal")
        if (type(title["font_size_px"]) is not int or title["font_size_px"] <= 0
                or type(title["line_height_px"]) is not int or title["line_height_px"] < title["font_size_px"]
                or type(title["max_lines"]) is not int or title["max_lines"] < 1
                or title["line_height_px"] * title["max_lines"] > title["bounds"][3]):
            raise ValueError("Fixed cover-title size and line stack do not fit their frame")
        if set(layout["host_slots"]) != {"doro", "gugu", "mambo"}:
            raise ValueError("Every cover requires the three original actors in explicit fixed slots")
        for host, slot in layout["host_slots"].items():
            _rectangle(slot["bounds"], canvas, name + "." + host)
        results[name] = validate_host_overlay(
            paths[variant["hosts_overlay"]], layout["story_bounds"], canvas,
            layout["host_slots"], {"title": title["bounds"], "seal": layout["seal_bounds"]})
    result = {"profile_id": PROFILE, "cover_template_revision": spec["cover_template_revision"],
              "asset_count": len(inventory), "variants": results,
              "visual_identity_and_readability_checked": False}
    _ASSET_VALIDATION_CACHE[cache_key] = copy.deepcopy(result)
    return result


def validate_render_record(record_path, spec=None, root=ROOT):
    root = Path(root).resolve()
    spec_path = root / "spec/cover_delivery.json"
    spec = spec or json.loads(spec_path.read_text(encoding="utf-8"))
    validate_cover_spec(spec, root)
    record = json.loads(Path(record_path).read_text(encoding="utf-8", errors="strict"))
    if (record.get("schema_version") != "2.0"
            or record["profile_id"] != PROFILE or record["cover_template_revision"] != spec["cover_template_revision"]
            or set(record["covers"]) != set(EXPECTED)
            or record["renderer"]["font_fallback"] or record["renderer"]["auto_shrink"]):
        raise ValueError("Render record does not describe the current fixed cover pair")
    if record["spec_sha256"] != hashlib.sha256(spec_path.read_bytes()).hexdigest():
        raise ValueError("Render record was generated against another cover specification")
    job_path, art_path = Path(record["job_path"]), Path(record["art_path"])
    for label, path, expected_hash in (("job", job_path, record["job_sha256"]),
                                       ("art", art_path, record["art_sha256"])):
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError("Actual local cover %s changed or is missing; re-render before delivery" % label)
    job = json.loads(job_path.read_text(encoding="utf-8-sig", errors="strict"))
    job_art_path = _resolve_job_art(job_path, job["art_path"])
    if (job.get("title") != record["title"] or job_art_path.resolve() != art_path.resolve()
            or set(job.get("variants", {})) != set(EXPECTED)):
        raise ValueError("Render record loses its approved local title, art or ratio source")
    for name, entry in record["covers"].items():
        options = job["variants"][name]
        lines = [line["text"] for line in entry["title_lines"]]
        if options.get("title_lines") != lines:
            raise ValueError("Render record title lines differ from the approved local cover job: " + name)
        validate_highlight_line_indices(options.get("highlight_line_indices"), len(lines), name + ".highlight_line_indices")
        if options["highlight_line_indices"] != entry.get("highlight_line_indices"):
            raise ValueError("Render record highlight lines differ from the approved local cover job: " + name)
        source = entry["art"]
        variant_art_path = _resolve_job_art(job_path, options.get("art_path", job["art_path"]))
        recorded_art_path = Path(source["source_path"]).resolve()
        if variant_art_path != recorded_art_path:
            raise ValueError("Render record per-ratio art source differs from the approved local cover job: " + name)
        if (not recorded_art_path.is_file()
                or hashlib.sha256(recorded_art_path.read_bytes()).hexdigest() != source["source_sha256"]):
            raise ValueError("Actual local cover per-ratio art changed or is missing; re-render before delivery: " + name)
        if (source["fit"] != options.get("art_fit", "contain")
                or source["crop_reviewed"] != options.get("crop_reviewed", False)):
            raise ValueError("Render record art-fit review differs from the approved local cover job: " + name)
    from PIL import Image, ImageChops, ImageDraw, ImageFont
    for name, entry in record["covers"].items():
        variant = spec["variants"][name]
        layout = variant["layout"]
        expected = EXPECTED[name][1:3]
        path = Path(entry["path"])
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Actual publishing-cover PNG changed since its render record: " + str(path))
        read_rgba_alpha(path, expected)
        if (tuple(entry["canvas"]) != expected
                or "".join(line["text"] for line in entry["title_lines"]) != record["title"]):
            raise ValueError("Actual cover record loses approved title text or canvas")
        title_style = layout["title"]
        lines = entry["title_lines"]
        if not 1 <= len(lines) <= title_style["max_lines"]:
            raise ValueError("Actual cover title exceeds its fixed line count: " + name)
        font = ImageFont.truetype(str(root / spec["typography"]["font_file"]),
                                  title_style["font_size_px"], layout_engine=ImageFont.Layout.BASIC)
        x, y, width, height = title_style["bounds"]
        line_height = title_style["line_height_px"]
        stack_top = y + (height - len(lines) * line_height) // 2
        measure = ImageDraw.Draw(Image.new("L", (1, 1)))
        _, title_top, _, title_bottom = measure.textbbox((0, 0), record["title"], font=font, anchor="ls")
        baseline_offset = -title_top + (line_height - (title_bottom - title_top)) // 2
        for index, line in enumerate(lines):
            line_top = stack_top + index * line_height
            baseline = line_top + baseline_offset
            left, top, right, bottom = measure.textbbox((0, 0), line["text"], font=font, anchor="ls")
            bounds = [x + left, baseline + top, right - left, bottom - top]
            if (line["baseline_y"] != baseline or line["line_bounds"] != [x, line_top, width, line_height]
                    or line["bounds"] != bounds):
                raise ValueError("Actual cover title record drifts from its vertically centered fixed line stack: " + name)
        if entry["art"]["fit"] not in ("contain", "cover") or (entry["art"]["fit"] == "cover" and not entry["art"]["crop_reviewed"]):
            raise ValueError("Actual cover art uses stretching or an unchecked crop")
        with Image.open(root / variant["base_plate"]) as image:
            reference = image.convert("RGBA")
        with Image.open(root / variant["hosts_overlay"]) as image:
            reference.alpha_composite(image.convert("RGBA"))
        with Image.open(path) as image:
            actual = image.convert("RGBA")
        fixed_region = Image.new("L", expected, 255)
        mask_draw = ImageDraw.Draw(fixed_region)
        for bounds in (layout["story_bounds"], layout["title"]["bounds"]):
            x, y, width, height = bounds
            padding = layout["title"].get("highlight", {}).get("padding_px", 0) if bounds == layout["title"]["bounds"] else 0
            mask_draw.rectangle((x - padding, y - padding, x + width + padding - 1,
                                 y + height + padding - 1), fill=0)
        differences = ImageChops.difference(actual, reference)
        # Compare all RGBA channels; getbbox() on RGBA alone can ignore RGB-only changes.
        for channel in differences.split():
            if ImageChops.multiply(channel, fixed_region).getbbox():
                raise ValueError("Cover chrome, seal or fixed actors drifted outside editable art/title areas: " + name)
    return {"profile_id": PROFILE, "actual_cover_pair_checked": True,
            "fixed_pixels_outside_editable_regions_checked": True,
            "visual_identity_readability_and_crop_checked": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-record", type=Path)
    args = parser.parse_args()
    try:
        spec = json.loads((ROOT / "spec/cover_delivery.json").read_text(encoding="utf-8", errors="strict"))
        result = validate_render_record(args.render_record, spec) if args.render_record else validate_cover_spec(spec)
        print("PASS: " + json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
