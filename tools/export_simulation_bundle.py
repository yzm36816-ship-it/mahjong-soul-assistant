"""Publish only verified synthetic event logs, with a path-free manifest."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_log", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    source = json.loads(args.manifest.read_text(encoding="utf-8"))
    if source.get("data_kind") != "synthetic_demo" or source.get("human_game_records") is not False:
        raise ValueError("public bundle requires confirmed synthetic-only data")
    raw = args.event_log.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source.get("event_log_sha256"):
        raise ValueError("event log SHA256 does not match the source manifest")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive = args.output_dir / f"{args.event_log.name}.gz"
    archive.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    public_manifest = {key: value for key, value in source.items()
                       if key not in ("event_log_file", "training_file")}
    public_manifest["event_log_file"] = archive.name
    public_manifest["training_file"] = "rebuild locally from the synthetic event archive"
    (args.output_dir / args.manifest.name).write_text(
        json.dumps(public_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"archive": str(archive), "compressed_bytes": archive.stat().st_size,
                      "event_log_sha256": source["event_log_sha256"],
                      "dataset_sha256": source["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
