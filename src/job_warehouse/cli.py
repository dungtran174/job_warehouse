"""Historical warehouse CLI; profiling is local, Bronze connects to PostgreSQL."""

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
    bronze = commands.add_parser("bronze", help="validate and register immutable historical files")
    bronze_commands = bronze.add_subparsers(dest="bronze_command", required=True)
    migrate = bronze_commands.add_parser("migrate", help="apply the versioned registry migration")
    migrate.add_argument("--report-dir", type=Path, required=True)
    register = bronze_commands.add_parser(
        "register", help="validate the pinned file and register it"
    )
    register.add_argument("--input-root", type=Path, required=True)
    register.add_argument("--relative-path", default="history_data.parquet")
    register.add_argument("--batch-size", type=int, default=4096)
    register.add_argument("--report-dir", type=Path, required=True)
    silver = commands.add_parser("silver", help="offline core historical normalization")
    silver_commands = silver.add_subparsers(dest="silver_command", required=True)
    core = silver_commands.add_parser("core", help="normalize the pinned file outside Git")
    core.add_argument("--input", type=Path, required=True)
    core.add_argument("--output-dir", type=Path, required=True)
    core.add_argument("--batch-size", type=int, default=2048)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "silver":
            from job_warehouse.silver.core_runner import run_core

            manifest = run_core(args.input, args.output_dir, batch_size=args.batch_size)
            print(f"Silver core: {manifest['partition']}; output={args.output_dir}")
            return 0
        if args.command == "bronze":
            from job_warehouse.bronze.commands import run_bronze

            return run_bronze(args)
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
        print(f"Historical warehouse error: {exc}", file=sys.stderr)
        return 2
    print(f"Decoded {result.row_count} rows; validation={'passed' if result.passed else 'failed'}")
    print(f"Report: {args.report_dir.absolute() / 'profile.json'}")
    for error in result.validation_errors:
        print(error, file=sys.stderr)
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
