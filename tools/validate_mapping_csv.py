"""Export and validate Excel-friendly, lossless two-column scene-map CSV files."""
import argparse
import codecs
import csv
import io
import os
import sys
import tempfile
from pathlib import Path

COLUMNS = ["插图编号", "对应口播"]


def _validate_record_boundaries(text):
    """Require CRLF between records; quoted cells may retain their original newlines."""
    in_quotes = False
    field_start = True
    after_quote = False
    last_record_ended = False
    i = 0
    while i < len(text):
        char = text[i]
        if in_quotes:
            last_record_ended = False
            if char == '"':
                if i + 1 < len(text) and text[i + 1] == '"':
                    i += 2
                    continue
                in_quotes = False
                after_quote = True
            i += 1
            continue
        if char == "\r":
            if i + 1 >= len(text) or text[i + 1] != "\n":
                raise ValueError("CSV record separators must be CRLF, not a lone CR")
            field_start, after_quote, last_record_ended = True, False, True
            i += 2
            continue
        if char == "\n":
            raise ValueError("CSV record separators must be CRLF, not a lone LF")
        last_record_ended = False
        if char == ",":
            field_start, after_quote = True, False
        elif char == '"':
            if not field_start or after_quote:
                raise ValueError("A quoted CSV field must start with its opening quote")
            in_quotes, field_start = True, False
        else:
            if after_quote:
                raise ValueError("Unexpected text after a closing CSV quote")
            field_start = False
        i += 1
    if in_quotes:
        raise ValueError("Unclosed quoted CSV field")
    if not last_record_ended:
        raise ValueError("The final CSV record must end with CRLF")


def _validate_cells(rows, allow_header_only=False):
    if not rows or rows[0] != COLUMNS:
        raise ValueError("CSV header must be exactly 插图编号,对应口播")
    if not allow_header_only and len(rows) == 1:
        raise ValueError("A delivered scene map must contain at least one data record")
    seen = set()
    for number, row in enumerate(rows, 1):
        if len(row) != 2 or any(not isinstance(cell, str) for cell in row):
            raise ValueError("Record %d must contain exactly two text cells" % number)
        if any("\ufffd" in cell or "\ufeff" in cell for cell in row):
            raise ValueError("Record %d contains a replacement character or an embedded BOM" % number)
        if number == 1:
            continue
        if not row[0].strip() or not row[1].strip():
            raise ValueError("Record %d has an empty image ID or narration" % number)
        if row[0] in seen:
            raise ValueError("Duplicate image ID: " + row[0])
        seen.add(row[0])


def validate_mapping_bytes(content, allow_header_only=False):
    """Validate the actual bytes and return unchanged parsed cells."""
    if not content.startswith(codecs.BOM_UTF8):
        raise ValueError("UTF-8 BOM EF BB BF is required at the beginning of the delivered file")
    text = content[len(codecs.BOM_UTF8):].decode("utf-8", errors="strict")
    if text.startswith("\ufeff"):
        raise ValueError("Duplicate leading UTF-8 BOM")
    _validate_record_boundaries(text)
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), dialect="excel", strict=True))
    except csv.Error as exc:
        raise ValueError("Invalid CSV syntax: " + str(exc)) from exc
    _validate_cells(rows, allow_header_only=allow_header_only)
    return rows


def validate_mapping_csv(path, allow_header_only=False):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Delivered CSV file does not exist: " + str(path))
    return validate_mapping_bytes(path.read_bytes(), allow_header_only=allow_header_only)


def export_mapping_csv(path, rows, *, overwrite=False, allow_header_only=False):
    """Write data rows (without a header), preserving every cell exactly.

    Identical reruns do not rewrite a file or add another BOM. Different existing
    output is refused unless the caller explicitly authorizes overwrite.
    """
    expected = [COLUMNS.copy()] + [list(row) for row in rows]
    _validate_cells(expected, allow_header_only=allow_header_only)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, dialect="excel", quoting=csv.QUOTE_MINIMAL,
                        lineterminator="\r\n")
    writer.writerows(expected)
    content = buffer.getvalue().encode("utf-8-sig", errors="strict")
    if validate_mapping_bytes(content, allow_header_only=allow_header_only) != expected:
        raise ValueError("CSV round-trip changed one or more cells")
    path = Path(path)
    if path.exists():
        if path.read_bytes() == content:
            validate_mapping_csv(path, allow_header_only=allow_header_only)
            return False
        if not overwrite:
            raise FileExistsError("Refusing to replace different existing CSV: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".",
                                         suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    if validate_mapping_csv(path, allow_header_only=allow_header_only) != expected:
        raise ValueError("Written CSV differs from its source cells")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path,
                        help="Explicit delivered CSV paths; this command does not modify them")
    parser.add_argument("--allow-header-only", action="store_true",
                        help="For the repository's blank template only, not a delivered episode")
    args = parser.parse_args()
    failed = False
    for path in args.files:
        try:
            rows = validate_mapping_csv(path, allow_header_only=args.allow_header_only)
            print("PASS: %s (%d data records, one UTF-8 BOM, CRLF records, two columns)"
                  % (path, len(rows) - 1))
        except (OSError, ValueError, UnicodeError, csv.Error) as exc:
            failed = True
            print("FAIL: %s: %s" % (path, exc), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
