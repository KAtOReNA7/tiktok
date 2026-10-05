"""Check actual RGBA actor-overlay pixels against a protected story rectangle.

Any alpha greater than zero counts as visible, including antialiased edges and
shadows. This does not assess actor likeness, visual cropping, or phone UI safety.
"""
import argparse
import json
import struct
import sys
import zlib
from pathlib import Path


def _paeth(left, above, upper_left):
    prediction = left + above - upper_left
    distances = [abs(prediction - value) for value in (left, above, upper_left)]
    return (left, above, upper_left)[distances.index(min(distances))]


def read_rgba_alpha(path, expected_canvas=None):
    """Validate an 8-bit noninterlaced RGBA PNG and return unfiltered alpha bytes."""
    path = Path(path)
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Actor overlay must be a real PNG: " + str(path))
    offset, chunks, compressed = 8, [], bytearray()
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind, end = raw[offset + 4:offset + 8], offset + 12 + length
        if end > len(raw):
            raise ValueError("Truncated PNG data")
        data = raw[offset + 8:offset + 8 + length]
        crc = struct.unpack(">I", raw[offset + 8 + length:end])[0]
        if zlib.crc32(kind + data) & 0xffffffff != crc:
            raise ValueError("PNG checksum mismatch")
        if not chunks:
            if kind != b"IHDR" or length != 13:
                raise ValueError("Invalid PNG header")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            if (not width or not height or (depth, color, compression, filtering, interlace) != (8, 6, 0, 0, 0)
                    or expected_canvas is not None and (width, height) != tuple(expected_canvas)):
                raise ValueError("Expected exact-size 8-bit noninterlaced RGBA overlay")
        elif kind == b"IHDR":
            raise ValueError("Duplicate PNG header")
        if kind == b"IDAT":
            compressed.extend(data)
        chunks.append(kind)
        offset = end
        if kind == b"IEND":
            if length or offset != len(raw):
                raise ValueError("Invalid PNG ending")
            break
    if not chunks or chunks[-1] != b"IEND" or not compressed:
        raise ValueError("Incomplete PNG")
    stride = width * 4 + 1
    inflater = zlib.decompressobj()
    pixels = inflater.decompress(bytes(compressed), stride * height + 1)
    if (len(pixels) != stride * height or not inflater.eof
            or inflater.unused_data or inflater.unconsumed_tail):
        raise ValueError("Invalid PNG scanline data")
    alpha, previous = bytearray(), bytearray(width)
    for y in range(height):
        start = y * stride
        filtering = pixels[start]
        if filtering > 4:
            raise ValueError("Invalid PNG row filter")
        current = bytearray(width)
        for x in range(width):
            left, above = current[x - 1] if x else 0, previous[x]
            upper_left = previous[x - 1] if x else 0
            predictor = (0, left, above, (left + above) // 2,
                         _paeth(left, above, upper_left))[filtering]
            current[x] = (pixels[start + 4 + x * 4] + predictor) & 255
        alpha.extend(current)
        previous = current
    return width, height, bytes(alpha)


def validate_host_overlay(path, story_bounds, expected_canvas=(1080, 1920)):
    width, height, alpha = read_rgba_alpha(path, expected_canvas)
    if (len(story_bounds) != 4 or any(type(value) is not int for value in story_bounds)):
        raise ValueError("Story bounds must be four integers x/y/width/height")
    x, y, w, h = story_bounds
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError("Story bounds must be inside the PNG canvas")
    visible = sum(value > 0 for value in alpha)
    if not visible:
        raise ValueError("Actor overlay is fully transparent; zero overlap alone is not sufficient")
    overlap = sum(value > 0 for row in range(y, y + h)
                  for value in alpha[row * width + x:row * width + x + w])
    if overlap:
        raise ValueError("Actor overlay enters the story window: %d pixels have alpha > 0" % overlap)
    return {"file": str(path), "canvas": [width, height], "story_bounds": list(story_bounds),
            "visible_actor_pixels": visible, "story_intersection_pixels": overlap,
            "alpha_threshold": "> 0"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("overlay", type=Path)
    parser.add_argument("--story-bounds", nargs=4, type=int, required=True, metavar=("X", "Y", "W", "H"))
    parser.add_argument("--canvas", nargs=2, type=int, default=[1080, 1920], metavar=("W", "H"))
    args = parser.parse_args()
    try:
        result = validate_host_overlay(args.overlay, args.story_bounds, args.canvas)
        print("PASS: " + json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, struct.error, zlib.error) as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
