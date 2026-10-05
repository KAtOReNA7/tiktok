"""Validate a V3 semantic page plan against its actual two-column CSV files.

This checks text conservation and mapping, not rendered pixels, character likeness,
font-fit claims, audio timing, or completion of the local image assembly.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from validate_mapping_csv import COLUMNS, validate_mapping_csv

TEMPLATE_IDS = {"RYP_STORY_MAIN_V3", "RYP_STORY_MAIN_V3_1"}
PROFILE_ID = "STATIC_CAPTION_PAGES_V1"


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + " must be nonempty text")
    if "\ufffd" in value or "\ufeff" in value:
        raise ValueError(label + " contains a replacement character or BOM")
    return value


def validate_caption_pages(plan_path, csv_directory=None):
    """Return checked episode/page counts; never modify the plan or its CSVs."""
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8", errors="strict"))
    if plan.get("template_id") not in TEMPLATE_IDS or plan.get("caption_mode") != PROFILE_ID:
        raise ValueError("Plan must declare a supported V3 template and static caption profile")
    csv_directory = Path(csv_directory) if csv_directory else plan_path.parent
    episodes = plan.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("Plan must contain at least one episode")
    seen_episodes, seen_pages, total_pages = set(), set(), 0
    for episode in episodes:
        episode_id = _text(episode["episode_id"], "episode_id")
        if episode_id in seen_episodes:
            raise ValueError("Duplicate episode_id: " + episode_id)
        seen_episodes.add(episode_id)
        sources, pages = episode["source_rows"], episode["pages"]
        if not sources or not pages:
            raise ValueError("Each episode requires source rows and final caption pages")
        source_ids, source_texts = [], []
        for source in sources:
            parent = _text(source["parent_scene_id"], "parent_scene_id")
            if parent in source_ids or not re.fullmatch(re.escape(episode_id) + r"_S\d{2,}", parent):
                raise ValueError("Invalid or duplicate source scene ID: " + parent)
            source_ids.append(parent)
            source_texts.append(_text(source["source_text"], "source_text"))
        if episode.get("source_scene_count") != len(sources) or episode.get("output_page_count") != len(pages):
            raise ValueError("Declared source/page counts do not match records: " + episode_id)
        grouped, group_order, rows, output_names = {}, [], [], set()
        for page in pages:
            parent, page_id = page["parent_scene_id"], _text(page["page_id"], "page_id")
            if parent not in source_ids:
                raise ValueError("Unknown parent scene: " + str(parent))
            if not group_order or parent != group_order[-1]:
                group_order.append(parent)
            group = grouped.setdefault(parent, [])
            expected_index = len(group) + 1
            if (type(page["page_index_in_scene"]) is not int
                    or page["page_index_in_scene"] != expected_index
                    or page_id != parent + "_%02d" % expected_index
                    or page_id in seen_pages):
                raise ValueError("Page IDs and indices must be unique and continuous from _01: " + page_id)
            seen_pages.add(page_id)
            caption = _text(page["caption_text"], "caption_text")
            lines = page["display_lines"]
            if (not isinstance(lines, list) or not 1 <= len(lines) <= 2
                    or any(not isinstance(line, str) or not line for line in lines)
                    or "".join(lines) != caption):
                raise ValueError("One/two display lines must rejoin exactly to the source fragment: " + page_id)
            filename = _text(page["output_filename"], "output_filename")
            if (Path(filename).name != filename or not filename.startswith(page_id + "_")
                    or not filename.endswith(".png") or filename in output_names):
                raise ValueError("Each PNG filename must uniquely include its page ID: " + page_id)
            output_names.add(filename)
            rows.append([page_id, caption])
            group.append(page)
        if group_order != source_ids:
            raise ValueError("Pages must retain parent scene order without interleaving: " + episode_id)
        for parent, original in zip(source_ids, source_texts):
            group = grouped[parent]
            if any(type(page["page_count_in_scene"]) is not int or page["page_count_in_scene"] != len(group)
                   for page in group):
                raise ValueError("Incorrect page_count_in_scene: " + parent)
            if "".join(page["caption_text"] for page in group) != original:
                raise ValueError("Caption pages change, omit, repeat or reorder source text: " + parent)
        if "".join(row[1] for row in rows) != "".join(source_texts):
            raise ValueError("Episode narration is not conserved: " + episode_id)
        filename = _text(episode["page_mapping_filename"], "page_mapping_filename")
        if Path(filename).name != filename:
            raise ValueError("CSV filename must name a file inside the supplied CSV directory")
        if validate_mapping_csv(csv_directory / filename) != [COLUMNS] + rows:
            raise ValueError("Actual delivered CSV differs from the page plan: " + filename)
        total_pages += len(pages)
    return len(episodes), total_pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("page_plan", type=Path)
    parser.add_argument("--csv-directory", type=Path, help="Defaults to the page plan directory")
    args = parser.parse_args()
    try:
        episodes, pages = validate_caption_pages(args.page_plan, args.csv_directory)
        print("PASS: %d episodes, %d pages; source text, page order, IDs and actual BOM/CRLF CSV cells verified. "
              "This is text/mapping verification only; PNG composition, font fit, likeness and audio remain separate checks."
              % (episodes, pages))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
