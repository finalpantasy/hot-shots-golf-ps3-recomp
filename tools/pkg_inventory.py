import argparse
import hashlib
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

PKG_MAGIC = b"\x7fPKG"
INPUT_SUFFIXES = (".pkg", ".pup", ".rar", ".crdownload")
EXCLUDED_DIRS = {".git", "external", "build", "generated"}


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def role_for(path, content_id):
    name = path.name.upper()
    if path.suffix.lower() == ".pup":
        return "ps3-firmware"
    if "NPUA80864" not in name and "NPUA80864" not in content_id.upper():
        return "other-title"
    if "FIX" in name:
        return "third-party-fix"
    if "-A0101-" in name:
        return "official-update-1.01"
    if "-A0102-" in name:
        return "official-update-1.02"
    if "-A0103-" in name:
        return "official-update-1.03"
    if "DLC" in name:
        return "dlc"
    return "base-game-candidate"


def inspect_pkg(path):
    result = {"format": "ps3-pkg", "package_complete": False, "entries": []}
    with path.open("rb") as source:
        header = source.read(0xC0)
        if len(header) < 0x80 or header[:4] != PKG_MAGIC:
            result["error"] = "invalid PS3 PKG header"
            return result
        revision, package_type = struct.unpack_from(">HH", header, 4)
        metadata_offset, metadata_count, metadata_size, item_count = struct.unpack_from(">IIII", header, 8)
        total_size, data_offset, data_size = struct.unpack_from(">QQQ", header, 0x18)
        content_id = header[0x30:0x60].split(b"\0")[0].decode("ascii", "replace")
        actual_size = path.stat().st_size
        result.update({
            "revision": revision,
            "package_type": package_type,
            "content_id": content_id,
            "item_count": item_count,
            "declared_size": total_size,
            "metadata_offset": metadata_offset,
            "metadata_count": metadata_count,
            "metadata_size": metadata_size,
            "data_offset": data_offset,
            "data_size": data_size,
        })
        complete = (
            actual_size == total_size
            and data_offset + data_size <= actual_size
            and path.suffix.lower() != ".crdownload"
            and item_count <= 100000
        )
        result["package_complete"] = complete
        if item_count > 100000:
            result["error"] = "unreasonable item count"
            return result
        result["entries_status"] = "encrypted item table not decoded"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    records = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if not path.name.lower().endswith(INPUT_SUFFIXES):
            continue
        record = {
            "path": str(path.relative_to(root)),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        if path.name.lower().endswith((".pkg", ".pkg.crdownload")) or path.suffix.lower() == ".pkg":
            record.update(inspect_pkg(path))
        else:
            record["format"] = path.suffix.lower().lstrip(".")
        record["role_guess"] = role_for(path, record.get("content_id", ""))
        records.append(record)
    by_hash = {}
    for record in records:
        by_hash.setdefault(record["sha256"], []).append(record["path"])
    duplicates = [paths for paths in by_hash.values() if len(paths) > 1]
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "packages": records,
        "duplicate_groups": duplicates,
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    for record in records:
        entries = record.get("entries", [])
        eboots = [entry.get("path", "") for entry in entries if "EBOOT" in entry.get("path", "").upper()]
        print(json.dumps({
            "path": record["path"],
            "role_guess": record["role_guess"],
            "size": record["size"],
            "sha256": record["sha256"],
            "content_id": record.get("content_id"),
            "complete": record.get("package_complete"),
            "items": len(entries),
            "eboots": eboots,
            "error": record.get("error"),
        }, ensure_ascii=True))
    print(f"wrote {output}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
