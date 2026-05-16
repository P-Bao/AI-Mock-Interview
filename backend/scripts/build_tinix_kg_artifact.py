from __future__ import annotations

import argparse
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_dir))

from integrations.tinix_careerpathkg import write_artifact


def _resolve_path(value: str, *, base: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build offline Tinix-CareerPathKG artifact for cv-module.")
    parser.add_argument(
        "--data-dir",
        default="",
        help="Path containing req_skill_matching.jsonl and req_sum.jsonl. Defaults to repo Tinix-CareerPathKG/data.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output artifact directory. Defaults to KG_ARTIFACT_DIR.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    default_data_dir = repo_root / "Tinix-CareerPathKG" / "data"
    data_dir = _resolve_path(args.data_dir, base=repo_root) if args.data_dir else default_data_dir
    output_dir = _resolve_path(args.output_dir or "./data/tinix_kg", base=backend_dir)

    missing = [name for name in ("req_skill_matching.jsonl", "req_sum.jsonl") if not (data_dir / name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing Tinix source files in {data_dir}: {', '.join(missing)}")

    output_path = write_artifact(data_dir, output_dir)
    print(f"Wrote Tinix KG artifact: {output_path}")


if __name__ == "__main__":
    main()
