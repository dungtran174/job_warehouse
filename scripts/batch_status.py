"""Print a read-only progress snapshot; no crawl or automatic monitoring."""

import argparse
import json
from pathlib import Path

from job_crawler.storage.status import read_batch_status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(read_batch_status(args.batch_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
