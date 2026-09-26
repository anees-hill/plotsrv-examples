"""Append a finite synthetic JSONL batch after starting the separate follower."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--records", type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.records <= 100:
        parser.error("--records must be between 1 and 100")
    # Append only: existing content belongs to the source's earlier history.
    with args.source.open("a", encoding="utf-8") as output:
        for sequence in range(1, args.records + 1):
            output.write(json.dumps({"sequence": sequence, "synthetic": True,
                                     "level": "INFO", "value": sequence * 3}) + "\n")
            output.flush()


if __name__ == "__main__":
    main()
