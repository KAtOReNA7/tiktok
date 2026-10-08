"""Fill the two versioned publishing-cover masters, without inventing a layout.

Usage: python tools/render_cover.py cover_job.json --output-dir /local/delivery
The job and its generated render record belong to local episode files, not Git.
Only Pillow is needed. Fonts, base plates and actor overlays come from the repo.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features
import PIL

from validate_cover import validate_cover_spec, validate_render_record

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig", errors="strict"))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_job_path(job_path, name):
    path = Path(name).expanduser()
    return path.resolve() if path.is_absolute() else (job_path.parent / path).resolve()


def ensure_supported_text(font, text):
    """Reject missing glyphs instead of silently replacing the bundled font."""
    missing = font.getmask("\U0010ffff")
    missing_key = (missing.size, bytes(missing))
    for character in set(text):
        if character.isspace():
            continue
        if ord(character) < 32 or ord(character) == 127:
            raise ValueError("Cover titles cannot contain control characters")
        glyph = font.getmask(character)
        if (glyph.size, bytes(glyph)) == missing_key:
            raise ValueError("Bundled cover font lacks glyph %r; no font fallback is allowed" % character)


def draw_title(canvas, title, lines, layout, font_path):
    if (not isinstance(lines, list) or not lines
            or any(not isinstance(line, str) or not line or "\n" in line or "\r" in line for line in lines)
            or "".join(lines) != title):
        raise ValueError("Explicit title_lines must reconstruct the approved title exactly")
    title_style = layout["title"]
    if len(lines) > title_style["max_lines"]:
        raise ValueError("Too many cover-title lines; do not resize the title or move its frame")
    font = ImageFont.truetype(str(font_path), title_style["font_size_px"],
                              layout_engine=ImageFont.Layout.BASIC)
    ensure_supported_text(font, title)
    x, y, width, height = title_style["bounds"]
    line_height = title_style["line_height_px"]
    draw = ImageDraw.Draw(canvas)
    measurements = []
    highlight = title_style.get("highlight", {})
    highlight_lines = ([len(lines) - 1] if highlight.get("mode") == "last_nonempty_line"
                       else highlight.get("line_indices", []))
    right_padding = highlight.get("right_padding_px", 0)
    ascent, descent = font.getmetrics()
    for index, line in enumerate(lines):
        left, top, right, bottom = draw.textbbox((0, 0), line, font=font, anchor="ls")
        measured_width, measured_height = right - left, bottom - top
        line_top = y + index * line_height
        baseline = line_top + ascent + (line_height - ascent - descent) // 2
        ink_bounds = [x + left, baseline + top, measured_width, measured_height]
        if (left < 0 or right > width or measured_height > line_height
                or baseline + top < line_top or baseline + bottom > line_top + line_height
                or line_top + line_height > y + height):
            raise ValueError("Cover title overflows its fixed frame on line %d; use another lossless line break" % (index + 1))
        if index in highlight_lines:
            background_width = min(width, int(draw.textlength(line, font=font) + 0.5) + right_padding)
            draw.rectangle((x, line_top, x + background_width - 1,
                            line_top + line_height - 1), fill=highlight["fill"])
        draw.text((x, baseline), line, font=font, fill=title_style["fill"], anchor="ls")
        measurements.append({"text": line, "bounds": ink_bounds, "baseline_y": baseline,
                             "line_bounds": [x, line_top, width, line_height]})
    return measurements


def paste_art(canvas, art_path, bounds, options, background):
    x, y, width, height = bounds
    with Image.open(art_path) as image:
        image.load()
        art = image.convert("RGBA")
    fit = options.get("art_fit", "contain")
    if fit not in ("contain", "cover"):
        raise ValueError("art_fit must be contain or explicitly reviewed cover; stretching is forbidden")
    if fit == "cover" and options.get("crop_reviewed") is not True:
        raise ValueError("Cover-crop mode requires an internal recorded check that actions, faces, hands and props remain complete")
    scale = (min if fit == "contain" else max)(width / art.width, height / art.height)
    # Explicit rounding and one resampling filter prevent platform defaults changing the layout.
    scaled_size = (max(1, int(art.width * scale + 0.5)), max(1, int(art.height * scale + 0.5)))
    resized = art.resize(scaled_size, Image.Resampling.LANCZOS)
    tile = Image.new("RGBA", (width, height), background)
    offset = ((width - resized.width) // 2, (height - resized.height) // 2)
    if fit == "cover":
        anchor = options.get("crop_anchor", [0.5, 0.5])
        if (not isinstance(anchor, list) or len(anchor) != 2
                or any(not isinstance(value, (int, float)) or not 0 <= value <= 1 for value in anchor)):
            raise ValueError("crop_anchor must be two explicit fractions in [0,1]")
        offset = (-int((resized.width - width) * anchor[0] + 0.5),
                  -int((resized.height - height) * anchor[1] + 0.5))
    tile.paste(resized, offset, resized)
    canvas.alpha_composite(tile, (x, y))
    return {"source_canvas": list(art.size), "fit": fit, "resized_canvas": list(resized.size),
            "offset_in_story_window": list(offset), "crop_reviewed": options.get("crop_reviewed", False)}


def render_covers(job_path, output_dir):
    job_path = Path(job_path).resolve()
    spec_path = ROOT / "spec/cover_delivery.json"
    spec = read_json(spec_path)
    validate_cover_spec(spec, ROOT)
    job = read_json(job_path)
    title = job.get("title")
    if not isinstance(title, str) or not title or "\n" in title or "\r" in title:
        raise ValueError("Supply the complete approved title as one unchanged string")
    topic_id = job.get("topic_id")
    if (not isinstance(topic_id, str) or not topic_id
            or any(character in topic_id for character in '/\\\r\n') or topic_id in (".", "..")):
        raise ValueError("topic_id must be a safe local file identifier")
    part = job.get("part_number", 1)
    revision = job.get("revision", 1)
    if type(part) is not int or part < 1 or type(revision) is not int or revision < 1:
        raise ValueError("part_number and revision must be positive integers")
    variants = job.get("variants", {})
    if set(variants) != set(spec["variants"]):
        raise ValueError("Supply explicit title_lines for both fixed cover ratios")
    art_path = resolve_job_path(job_path, job["art_path"])
    if not art_path.is_file():
        raise ValueError("Missing local episode art: " + str(art_path))
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    record = {"schema_version": "1.0", "profile_id": spec["profile_id"],
              "cover_template_revision": spec["cover_template_revision"], "title": title,
              "job_path": str(job_path), "job_sha256": sha256(job_path),
              "spec_sha256": sha256(spec_path), "art_path": str(art_path),
              "art_sha256": sha256(art_path), "renderer": {
                  "Pillow": PIL.__version__, "FreeType": features.version("freetype2"),
                  "font_fallback": False, "auto_shrink": False}, "covers": {}}
    # Measure before creating either final file: an overflow never produces a half-approved pair.
    rendered = []
    font_path = ROOT / spec["typography"]["font_file"]
    for name, variant in spec["variants"].items():
        options = variants[name]
        if not isinstance(options, dict):
            raise ValueError("Each cover variant must supply an object with explicit title_lines")
        if set(options) - {"title_lines", "art_fit", "crop_reviewed", "crop_anchor"}:
            raise ValueError("Cover jobs may replace only title lines and artwork placement; fixed chrome/hosts/font cannot be overridden")
        layout = variant["layout"]
        with Image.open(ROOT / variant["base_plate"]) as base:
            canvas = base.convert("RGBA")
        art_info = paste_art(canvas, art_path, layout["story_bounds"], options,
                             spec["composition"]["art_letterbox_fill"])
        text_info = draw_title(canvas, title, options.get("title_lines"), layout, font_path)
        with Image.open(ROOT / variant["hosts_overlay"]) as image:
            hosts = image.convert("RGBA")
        canvas.alpha_composite(hosts)
        filename = variant["filename_pattern"].format(topic_id=topic_id, part_number=part,
                                                       revision=revision)
        output = output_dir / filename
        rendered.append((name, canvas, output, art_info, text_info))
    for name, canvas, output, art_info, text_info in rendered:
        canvas.save(output, format="PNG", optimize=False, compress_level=9)
        record["covers"][name] = {"path": str(output), "sha256": sha256(output),
                                  "canvas": list(canvas.size), "title_lines": text_info,
                                  "art": art_info}
    record_path = output_dir / ("%s_P%02d_封面渲染记录_v%02d.json" % (topic_id, part, revision))
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validate_render_record(record_path, spec, ROOT)
    return record_path, record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path, nargs="?")
    parser.add_argument("--job", dest="job_option", type=Path)
    parser.add_argument("--output-dir", "--output", dest="output_dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.job is None and args.job_option is None:
            raise ValueError("Supply a local cover_job.json path")
        if args.job is not None and args.job_option is not None and args.job.resolve() != args.job_option.resolve():
            raise ValueError("The positional job and --job disagree")
        path, record = render_covers(args.job or args.job_option, args.output_dir)
        print("PASS: two fixed cover PNGs rendered; local record " + str(path))
        for value in record["covers"].values():
            print(value["path"])
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
