#!/usr/bin/env python3
"""Read-only indexer for unencrypted/OPEN GTA V RPF7 archives.

This intentionally does not modify archives. It prints the directory tree as
JSON so two builds can be compared safely before any patch is attempted.
"""

from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path


RPF7_MAGIC = 0x52504637
OPEN = 0x4E45504F
NONE = 0
DIRECTORY_MARKER = 0x7FFFFF00


def c_string(buf: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(buf):
        return f"<bad-name-offset:{offset}>"
    end = buf.find(b"\0", offset)
    if end < 0:
        end = len(buf)
    return buf[offset:end].decode("utf-8", errors="replace")


def read_index(path: Path) -> dict:
    with path.open("rb") as stream:
        header = stream.read(16)
        if len(header) != 16:
            raise ValueError("File is too short for an RPF7 header")
        magic, entry_count, names_length, encryption = struct.unpack("<4I", header)
        if magic != RPF7_MAGIC:
            raise ValueError(f"Not RPF7 (magic=0x{magic:08X})")
        if encryption not in (NONE, OPEN):
            raise ValueError(
                f"Encrypted RPF table is unsupported (flag=0x{encryption:08X})"
            )
        if entry_count > 10_000_000 or names_length > 1_000_000_000:
            raise ValueError("Implausible RPF table size")
        table = stream.read(entry_count * 16)
        names = stream.read(names_length)
        if len(table) != entry_count * 16 or len(names) != names_length:
            raise ValueError("Truncated RPF table")

    entries: list[dict] = []
    for index in range(entry_count):
        raw = table[index * 16 : (index + 1) * 16]
        first, second, third, fourth = struct.unpack("<4I", raw)
        if second == DIRECTORY_MARKER:
            entry = {
                "index": index,
                "kind": "directory",
                "name_offset": first,
                "name": c_string(names, first),
                "children_index": third,
                "children_count": fourth,
            }
        elif second & 0x80000000:
            name_offset = first & 0xFFFF
            file_size = (first >> 16) | ((second & 0xFF) << 16)
            file_offset = (second >> 8) & 0x7FFFFF
            entry = {
                "index": index,
                "kind": "resource",
                "name_offset": name_offset,
                "name": c_string(names, name_offset),
                "file_offset_sector": file_offset,
                "stored_size": file_size,
                "system_flags": third,
                "graphics_flags": fourth,
            }
        else:
            packed = struct.unpack("<Q", raw[:8])[0]
            name_offset = packed & 0xFFFF
            entry = {
                "index": index,
                "kind": "binary",
                "name_offset": name_offset,
                "name": c_string(names, name_offset),
                "stored_size": (packed >> 16) & 0xFFFFFF,
                "file_offset_sector": (packed >> 40) & 0xFFFFFF,
                "uncompressed_size": third,
                "encrypted": bool(fourth),
            }
        entries.append(entry)

    if not entries or entries[0]["kind"] != "directory":
        raise ValueError("RPF root entry is missing")

    def attach(directory_index: int, prefix: str, active: set[int]) -> None:
        if directory_index in active:
            raise ValueError("Directory cycle in RPF table")
        active.add(directory_index)
        directory = entries[directory_index]
        start = directory["children_index"]
        end = start + directory["children_count"]
        if end > len(entries):
            raise ValueError("Directory child range exceeds RPF table")
        for child in entries[start:end]:
            child_path = f"{prefix}/{child['name']}" if prefix else child["name"]
            child["path"] = child_path
            child["parent_index"] = directory_index
            if child["kind"] == "directory":
                attach(child["index"], child_path, active)
        active.remove(directory_index)

    entries[0]["path"] = ""
    attach(0, "", set())
    return {
        "archive": str(path.resolve()),
        "size": path.stat().st_size,
        "entry_count": entry_count,
        "names_length": names_length,
        "encryption": "OPEN" if encryption == OPEN else "NONE",
        "entries": entries,
    }


def extract_binary(archive: Path, result: dict, entry_path: str, output: Path) -> None:
    matches = [
        entry
        for entry in result["entries"]
        if entry.get("path", "").casefold() == entry_path.casefold()
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one entry for {entry_path!r}, found {len(matches)}")
    entry = matches[0]
    if entry["kind"] != "binary":
        raise ValueError("Only binary entries can be extracted by this safety tool")
    if entry["encrypted"]:
        raise ValueError("Entry is encrypted; refusing to guess at key material")
    length = entry["stored_size"] or entry["uncompressed_size"]
    offset = entry["file_offset_sector"] * 512
    if offset + length > archive.stat().st_size:
        raise ValueError("Entry range exceeds archive length")
    output.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("rb") as source:
        source.seek(offset)
        remaining = length
        chunks = []
        while remaining:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("Unexpected end of archive while extracting")
            chunks.append(chunk)
            remaining -= len(chunk)
    data = b"".join(chunks)
    if entry["stored_size"]:
        errors = []
        for window_bits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                data = zlib.decompress(data, window_bits)
                break
            except zlib.error as exc:
                errors.append(str(exc))
        else:
            raise ValueError("Could not decompress entry: " + " | ".join(errors))
        expected = entry["uncompressed_size"]
        if expected and len(data) != expected:
            raise ValueError(
                f"Decompressed size mismatch: got {len(data)}, expected {expected}"
            )
    with output.open("wb") as target:
        target.write(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--json", type=Path, help="Write full JSON index here")
    parser.add_argument("--filter", default="", help="Case-insensitive path filter")
    parser.add_argument(
        "--extract-path", help="Extract one raw, unencrypted binary entry by path"
    )
    parser.add_argument("--output", type=Path, help="Destination for --extract-path")
    args = parser.parse_args()

    result = read_index(args.archive)
    if args.extract_path:
        if not args.output:
            parser.error("--extract-path requires --output")
        extract_binary(args.archive, result, args.extract_path, args.output)
        print(f"Extracted {args.extract_path} -> {args.output}")
        return 0
    if args.json:
        args.json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    needle = args.filter.casefold()
    print(
        f"{result['archive']} | entries={result['entry_count']} "
        f"names={result['names_length']} encryption={result['encryption']}"
    )
    for entry in result["entries"]:
        path = entry.get("path", "")
        if needle and needle not in path.casefold():
            continue
        details = ""
        if entry["kind"] == "binary":
            details = (
                f" stored={entry['stored_size']} raw={entry['uncompressed_size']}"
                f" encrypted={entry['encrypted']}"
            )
        elif entry["kind"] == "resource":
            details = f" stored={entry['stored_size']}"
        print(f"{entry['kind']:<9} {path}{details}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
