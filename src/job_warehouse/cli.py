"""Local history CLI; never calls crawler, network, or a database."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from job_warehouse.history.contract import EXPECTED_ROWS, EXPECTED_SHA256, HistoryProfileError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job-warehouse")
    commands = parser.add_subparsers(dest="command", required=True)
    profile = commands.add_parser("profile", help="fully profile a local historical Parquet")
    profile.add_argument("--input", type=Path, required=True)
    profile.add_argument(
        "--report-dir", type=Path, required=True, help="new local report directory"
    )
    profile.add_argument("--batch-size", type=int, default=4096)
    profile.add_argument("--expected-sha256", default=EXPECTED_SHA256)
    profile.add_argument("--expected-rows", type=int, default=EXPECTED_ROWS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        # Optional dependency is needed for profiling, not for crawler or CLI help.
        from job_warehouse.history.profile import profile_history, write_profile

        if args.report_dir.exists():
            raise HistoryProfileError("Report directory already exists; choose a new directory")
        result = profile_history(
            args.input,
            batch_size=args.batch_size,
            expected_sha256=args.expected_sha256,
            expected_rows=args.expected_rows,
        )
        write_profile(result, args.report_dir)
    except ImportError:
        print(
            "Install warehouse dependencies: python -m pip install -e '.[warehouse]'",
            file=sys.stderr,
        )
        return 2
    except (ValueError, OSError) as exc:
        print(f"History profile error: {exc}", file=sys.stderr)
        return 2
    print(f"Decoded {result.row_count} rows; validation={'passed' if result.passed else 'failed'}")
    print(f"Report: {args.report_dir.absolute() / 'profile.json'}")
    for error in result.validation_errors:
        print(error, file=sys.stderr)
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
