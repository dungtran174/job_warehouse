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
    enrich = silver_commands.add_parser("enrich", help="map occupations and source places offline")
    enrich.add_argument("--core", type=Path, required=True)
    enrich.add_argument("--core-manifest", type=Path, required=True)
    enrich.add_argument("--output-dir", type=Path, required=True)
    enrich.add_argument("--batch-size", type=int, default=2048)
    owner_map = silver_commands.add_parser(
        "apply-location-map", help="apply owner Excel locations to a verified S3 run"
    )
    owner_map.add_argument("--base-run", type=Path, required=True)
    owner_map.add_argument("--mapping-xlsx", type=Path, required=True)
    owner_map.add_argument("--output-dir", type=Path, required=True)
    industry = silver_commands.add_parser(
        "industry", help="apply owner source-industry policy and select analysis records"
    )
    industry.add_argument("--bronze", type=Path, required=True)
    industry.add_argument("--base-run", type=Path, required=True)
    industry.add_argument("--output-dir", type=Path, required=True)
    industry.add_argument("--threshold", type=int, default=500)
    industry.add_argument("--batch-size", type=int, default=4096)
    salary = silver_commands.add_parser("salary", help="normalize salary to VND/month offline")
    salary.add_argument("--core-run", type=Path, required=True)
    salary.add_argument("--industry-run", type=Path, required=True)
    salary.add_argument("--output-dir", type=Path, required=True)
    salary.add_argument("--fx-rates", type=Path)
    salary.add_argument("--batch-size", type=int, default=2048)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "silver":
            if args.silver_command == "salary":
                from job_warehouse.silver.salary.runner import run_salary

                report = run_salary(
                    args.core_run,
                    args.industry_run,
                    args.output_dir,
                    fx_rates=args.fx_rates,
                    batch_size=args.batch_size,
                )
                print(f"Silver salary: {report['partition']}; output={args.output_dir}")
                return 0
            if args.silver_command == "industry":
                from job_warehouse.silver.industry_runner import run_industry

                report = run_industry(
                    args.bronze,
                    args.base_run,
                    args.output_dir,
                    threshold=args.threshold,
                    batch_size=args.batch_size,
                )
                print(f"Silver source industry: {report['partition']}; output={args.output_dir}")
                return 0
            if args.silver_command == "apply-location-map":
                from job_warehouse.silver.enrichment.owner_locations import apply_owner_mapping

                report = apply_owner_mapping(args.base_run, args.mapping_xlsx, args.output_dir)
                print(f"Owner location mapping: {report}; output={args.output_dir}")
                return 0
            if args.silver_command == "enrich":
                from job_warehouse.silver.enrichment.runner import run_enrichment

                manifest = run_enrichment(
                    args.core, args.core_manifest, args.output_dir, batch_size=args.batch_size
                )
                print(f"Silver enrichment: {manifest['partition']}; output={args.output_dir}")
                return 0
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
