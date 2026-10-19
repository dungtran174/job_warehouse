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
    skills_prepare = silver_commands.add_parser(
        "skills-prepare", help="profile requirements and freeze unlabelled skill samples"
    )
    skills_prepare.add_argument("--jobs-run", type=Path, required=True)
    skills_prepare.add_argument("--output-dir", type=Path, required=True)
    skills_prepare.add_argument("--tune-per-industry", type=int, default=30)
    skills_prepare.add_argument("--holdout-per-industry", type=int, default=100)
    skills_prepare.add_argument("--batch-size", type=int, default=2048)
    skills = silver_commands.add_parser(
        "skills", help="extract candidate requirement skills offline"
    )
    skills.add_argument("--jobs-run", type=Path, required=True)
    skills.add_argument("--output-dir", type=Path, required=True)
    skills.add_argument("--taxonomy-dir", type=Path)
    skills.add_argument("--batch-size", type=int, default=2048)
    skills.add_argument(
        "--batch",
        choices=[
            "sales_customer_service",
            "real_estate",
            "hr_finance_legal",
            "logistics_transport",
            "engineering_production",
            "construction_design_projects",
            "education_language",
            "hospitality_retail",
            "healthcare_food_garment",
        ],
    )
    skills.add_argument("--industry", action="append", help="only validated labels within --batch")
    batch_prepare = silver_commands.add_parser(
        "skills-batch-prepare",
        help="freeze disjoint samples for an explicit skills expansion batch",
    )
    batch_prepare.add_argument("--jobs-run", type=Path, required=True)
    batch_prepare.add_argument("--output-dir", type=Path, required=True)
    batch_prepare.add_argument(
        "--batch",
        choices=[
            "sales_customer_service",
            "real_estate",
            "hr_finance_legal",
            "logistics_transport",
            "engineering_production",
            "construction_design_projects",
            "education_language",
            "hospitality_retail",
            "healthcare_food_garment",
        ],
        required=True,
    )
    batch_prepare.add_argument("--tune-per-industry", type=int, default=20)
    batch_prepare.add_argument("--holdout-per-industry", type=int, default=50)
    batch_merge = silver_commands.add_parser(
        "skills-batch-merge", help="merge a validated expansion batch while preserving the baseline"
    )
    batch_merge.add_argument(
        "--batch",
        choices=[
            "sales_customer_service",
            "real_estate",
            "hr_finance_legal",
            "logistics_transport",
            "engineering_production",
            "construction_design_projects",
            "education_language",
            "hospitality_retail",
            "healthcare_food_garment",
        ],
        required=True,
    )
    batch_merge.add_argument("--candidate-run", type=Path, required=True)
    batch_merge.add_argument("--baseline-run", type=Path, required=True)
    batch_merge.add_argument("--gate", type=Path, required=True)
    batch_merge.add_argument("--output-dir", type=Path, required=True)
    review = silver_commands.add_parser(
        "skills-apply-review", help="apply evidence-bound skill review to held-out jobs"
    )
    review.add_argument("--jobs-run", type=Path, required=True)
    review.add_argument("--baseline-run", type=Path, required=True)
    review.add_argument("--review-bundle", type=Path, required=True)
    review.add_argument("--output-dir", type=Path, required=True)
    expanded = silver_commands.add_parser(
        "skills-expand", help="rerun the expanded skills dictionary on the three pilot industries"
    )
    expanded.add_argument("--jobs-run", type=Path, required=True)
    expanded.add_argument("--output-dir", type=Path, required=True)
    expanded.add_argument("--taxonomy-dir", type=Path)
    expanded.add_argument("--batch-size", type=int, default=2048)
    expanded_merge = silver_commands.add_parser(
        "skills-expand-merge", help="combine expanded candidates and document-bound reviews"
    )
    expanded_merge.add_argument("--automatic-run", type=Path, required=True)
    expanded_merge.add_argument("--baseline-run", type=Path, required=True)
    expanded_merge.add_argument("--review-run", type=Path, action="append", required=True)
    expanded_merge.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "silver":
            if args.silver_command == "skills-batch-merge":
                from job_warehouse.skills.batch_merge import merge_batch

                report = merge_batch(
                    args.candidate_run,
                    args.baseline_run,
                    args.gate,
                    args.output_dir,
                    batch_name=args.batch,
                )
                print(f"Batch merged: {report}; output={args.output_dir}")
                return 0
            if args.silver_command == "skills-batch-prepare":
                from job_warehouse.skills.batches import prepare_batch

                report = prepare_batch(
                    args.jobs_run,
                    args.output_dir,
                    batch_name=args.batch,
                    tune_per_industry=args.tune_per_industry,
                    holdout_per_industry=args.holdout_per_industry,
                )
                print(f"Batch samples: {report}; output={args.output_dir}")
                return 0
            if args.silver_command == "skills-expand-merge":
                from job_warehouse.skills.expansion_merge import merge_expansion

                report = merge_expansion(
                    args.automatic_run, args.baseline_run, args.review_run, args.output_dir
                )
                print(f"Expanded candidates: {report}; output={args.output_dir}")
                return 0
            if args.silver_command == "skills-expand":
                from job_warehouse.skills.expanded import EXPANDED_MAPPINGS
                from job_warehouse.skills.runner import run_skills

                report = run_skills(
                    args.jobs_run,
                    args.output_dir,
                    taxonomy_dir=args.taxonomy_dir or EXPANDED_MAPPINGS,
                    batch_size=args.batch_size,
                    expanded_context=True,
                )
                print(f"Expanded candidate skills: {report['counts']}; output={args.output_dir}")
                return 0
            if args.silver_command == "skills-apply-review":
                from job_warehouse.skills.review_import import apply_review

                report = apply_review(
                    args.jobs_run, args.baseline_run, args.review_bundle, args.output_dir
                )
                print(f"Reviewed pairs added: {report['added_pairs']}; output={args.output_dir}")
                return 0
            if args.silver_command == "skills":
                from job_warehouse.skills.runner import run_skills
                from job_warehouse.skills.taxonomy import MAPPINGS

                taxonomy_dir = args.taxonomy_dir or MAPPINGS
                if args.batch:
                    from job_warehouse.skills.sales import SALES_MAPPINGS

                    taxonomy_dir = args.taxonomy_dir or SALES_MAPPINGS
                    if args.batch == "real_estate":
                        from job_warehouse.skills.real_estate import REAL_ESTATE_MAPPINGS

                        taxonomy_dir = args.taxonomy_dir or REAL_ESTATE_MAPPINGS
                    elif args.batch == "healthcare_food_garment":
                        from job_warehouse.skills.life_sciences import LIFE_SCIENCES_MAPPINGS

                        taxonomy_dir = args.taxonomy_dir or LIFE_SCIENCES_MAPPINGS
                    elif args.batch == "hospitality_retail":
                        from job_warehouse.skills.hospitality import HOSPITALITY_MAPPINGS

                        taxonomy_dir = args.taxonomy_dir or HOSPITALITY_MAPPINGS
                    elif args.batch == "education_language":
                        from job_warehouse.skills.education import EDUCATION_MAPPINGS

                        taxonomy_dir = args.taxonomy_dir or EDUCATION_MAPPINGS
                    elif args.batch == "construction_design_projects":
                        from job_warehouse.skills.construction import CONSTRUCTION_MAPPINGS

                        taxonomy_dir = args.taxonomy_dir or CONSTRUCTION_MAPPINGS
                    elif args.batch == "engineering_production":
                        from job_warehouse.skills.engineering import ENGINEERING_MAPPINGS

                        taxonomy_dir = args.taxonomy_dir or ENGINEERING_MAPPINGS
                    elif args.batch == "logistics_transport":
                        from job_warehouse.skills.logistics import LOGISTICS_MAPPINGS

                        taxonomy_dir = args.taxonomy_dir or LOGISTICS_MAPPINGS
                    elif args.batch == "hr_finance_legal":
                        from job_warehouse.skills.hr_finance import HR_FINANCE_MAPPINGS

                        taxonomy_dir = args.taxonomy_dir or HR_FINANCE_MAPPINGS
                report = run_skills(
                    args.jobs_run,
                    args.output_dir,
                    taxonomy_dir=taxonomy_dir,
                    batch_size=args.batch_size,
                    batch_name=args.batch,
                    enabled_industries=tuple(args.industry) if args.industry else None,
                )
                print(f"Candidate skills: {report['counts']}; output={args.output_dir}")
                return 0
            if args.silver_command == "skills-prepare":
                from job_warehouse.skills.profile import prepare_skills

                report = prepare_skills(
                    args.jobs_run,
                    args.output_dir,
                    tune_per_industry=args.tune_per_industry,
                    holdout_per_industry=args.holdout_per_industry,
                    batch_size=args.batch_size,
                )
                print(f"Skills preparation: {report['counts']}; output={args.output_dir}")
                return 0
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
