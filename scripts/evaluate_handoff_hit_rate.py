#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from memory_hub.acceptance import load_labeled_samples, summarize_hit_rate
from memory_hub.errors import BusinessError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate cross-session context hit rate.")
    parser.add_argument("--input", type=Path, required=True, help="Path to labeled JSONL file.")
    parser.add_argument("--min-projects", type=int, default=2)
    parser.add_argument("--min-samples-per-project", type=int, default=10)
    parser.add_argument("--overall-threshold", type=float, default=0.9)
    parser.add_argument("--project-threshold", type=float, default=0.85)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        samples = load_labeled_samples(args.input)
        result = summarize_hit_rate(
            samples,
            min_projects=args.min_projects,
            min_samples_per_project=args.min_samples_per_project,
            overall_threshold=args.overall_threshold,
            project_threshold=args.project_threshold,
        )
    except BusinessError as exc:
        print(json.dumps({"pass": False, "error": exc.to_payload()}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
