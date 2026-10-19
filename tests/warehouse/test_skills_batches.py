"""Explicit scopes, disjoint samples and independently versioned sales context."""

import json
import unicodedata
from pathlib import Path

import pytest

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")

from job_warehouse.history.identity import file_sha256  # noqa: E402
from job_warehouse.skills.batches import (  # noqa: E402
    batch_scope,
    normalized_text_hash,
    prepare_batch,
)
from job_warehouse.skills.runner import load_policy, run_skills  # noqa: E402
from job_warehouse.skills.sales import SALES_MAPPINGS, SalesSkillMatcher  # noqa: E402
from job_warehouse.skills.taxonomy import load_taxonomy  # noqa: E402


@pytest.fixture
def matcher():
    return SalesSkillMatcher(
        load_taxonomy(SALES_MAPPINGS),
        load_policy(SALES_MAPPINGS, scope=batch_scope("sales_customer_service"))[0],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Có kinh nghiệm bán hàng và chăm sóc khách hàng",
            {"review_ban_hang_sales", "review_cham_soc_khach_hang"},
        ),
        ("Ưu tiên thành thạo CRM và Salesforce", {"review_crm", "review_salesforce"}),
        ("Có kinh nghiệm sử dụng Salesforce", {"review_salesforce"}),
        ("Tìm kiếm khách hàng tiềm năng", {"sales_prospecting"}),
        ("Lập báo giá và xử lý đơn hàng", {"sales_quotation", "sales_order_management"}),
        ("Không yêu cầu Excel; biết CRM", {"review_crm"}),
        ("Sẽ được đào tạo kỹ năng sale, quy trình chốt deal", set()),
        ("Đam mê bán hàng", set()),
        ("Tốt nghiệp ngành bán hàng", set()),
        ("Có laptop và điện thoại", set()),
        ("Có kỹ năng giao tiếp, đàm phán, thuyết phục tốt", set()),
        ("Thành thạo Tiếng Anh (Không yêu cầu bằng cấp)", {"english"}),
        ("Nắm chắc SQL, Python", {"sql", "python"}),
        ("Có chứng chỉ tiếng Anh TOEIC 700", {"english"}),
        ("Sẽ được đào tạo từ đầu, chỉ cần bạn có: Khả năng giao tiếp tiếng Anh", {"english"}),
        ("Thưởng nóng Best Sales tháng", set()),
        ("Có kinh nghiệm SQL Server", {"sql_server"}),
        ("Biết C++ và C# và .NET", {"cpp", "csharp", "dotnet"}),
        ("Không có kinh nghiệm bán hàng", set()),
        ("Chưa có kinh nghiệm bán hàng", set()),
        (
            "Có kinh nghiệm bán hàng là lợi thế, chưa có kinh nghiệm sẽ được đào tạo",
            {"review_ban_hang_sales"},
        ),
        ("Thành thạo Word, Excel. Không yêu cầu kinh nghiệm", {"word", "excel"}),
        ("Thông thạo Excel", {"excel"}),
        ("Tiếng Anh cơ bản", {"english"}),
        ("Có kinh nghiệm nhân viên kinh doanh", {"review_ban_hang_sales"}),
        ("Sử dụng phần mềm quản lý bán hàng", set()),
        ("Proficiency in Excel for sales reporting", {"excel"}),
        ("Bachelor or College Certificate in Sales and Marketing", set()),
        ("Biết cơ bản nền tảng mạng xã hội", set()),
        ("Biết AI tools: ChatGPT", set()),
        ("Sử dụng tốt world và Excel", {"word", "excel"}),
        ("Understand the world", set()),
        ("Vi tính văn phòng Excel, Word, PowerPoint", {"office_it", "excel", "word", "powerpoint"}),
        (
            "Thành thạo tin học văn phòng (Word; Excel; PowerPoint)",
            {"office_it", "excel", "word", "powerpoint"},
        ),
        ("Đã từng sử dụng hoặc bán phần mềm kế toán (MISA, FAST)", {"misa", "fast_accounting"}),
        ("Có tư duy dịch vụ khách hàng tốt", set()),
        ("Có tố chất chăm sóc khách hàng", set()),
        ("Learning & Development Opportunities. Hands-on experience with Salesforce CRM", set()),
        ("Thu nhập: có hoa hồng. Được cấp chứng chỉ môi giới BĐS. Yêu cầu: biết Excel", {"excel"}),
        ("Office computer: good", {"office_it"}),
        ("Biết ngoại ngữ: Anh, Hàn, Trung là lợi thế", {"english", "korean", "chinese"}),
        ("Có kiến thức cơ bản về lĩnh vực kinh doanh", set()),
    ],
)
def test_sales_claim_semantics(matcher, text, expected):
    result = matcher.extract(text)
    assert set(result.skill_codes) == expected
    for e in result.evidence:
        assert text[e.start : e.end] == e.text
        assert e.context_start <= e.start < e.end <= e.context_end


def test_bare_list_is_unclear_but_clear_claim_retained(matcher):
    result = matcher.extract("CRM; Excel. Biết tiếng Anh")
    assert result.skill_codes == ("english",)
    assert result.status == "expanded_partial_match"
    assert len([e for e in result.evidence if e.context == "ambiguous"]) == 2


def test_batch_policy_cannot_silently_replace_pilot_policy():
    with pytest.raises(ValueError, match="scope"):
        load_policy(SALES_MAPPINGS)
    with pytest.raises(ValueError, match="Unknown skills batch"):
        batch_scope("arbitrary_industry")


def test_processing_subset_rejects_unknown_or_duplicate_labels():
    from job_warehouse.skills.scopes import processing_scope

    approved = batch_scope("sales_customer_service")
    assert processing_scope("sales_customer_service", (approved[1], approved[0])) == approved[:2]
    for labels in [(), ("Marketing",), (approved[0], approved[0])]:
        with pytest.raises(ValueError, match="subset"):
            processing_scope("sales_customer_service", labels)


def test_grouping_preserves_original_but_excludes_cosmetic_duplicates():
    first = "Biết Tiếng Anh"
    second = unicodedata.normalize("NFD", " BIẾT   TIẾNG ANH \n")
    assert normalized_text_hash(first) == normalized_text_hash(second)


@pytest.fixture
def batch_jobs(tmp_path):
    rows = [{"id": 1, "job_industry": "Marketing", "year": 2024, "requirements": "Biết Tiếng Anh"}]
    for i, industry in enumerate(batch_scope("sales_customer_service")):
        for n, text in enumerate(
            [
                " BIẾT   TIẾNG ANH ",
                "Biết CRM",
                "Biết SQL",
                "Biết Excel",
                None,
                "Không",
                f"Synthetic unique industry {i}",
            ]
        ):
            rows.append(
                {
                    "id": 2 + i * 7 + n,
                    "job_industry": industry,
                    "year": 2022 + n % 5,
                    "requirements": text,
                }
            )
    source = tmp_path / "jobs"
    source.mkdir()
    path = source / "jobs_analysis.parquet"
    schema = pa.schema(
        [
            ("id", pa.int64()),
            ("job_industry", pa.string()),
            ("year", pa.int16()),
            ("requirements", pa.string()),
        ]
    )
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "source": {"revision": "fixture", "pinned_artifact_verified": False},
                "partition": {"analysis": len(rows)},
                "artifacts": {path.name: {"sha256": file_sha256(path)}},
            }
        )
    )
    return source


def test_sampling_excludes_pilot_and_shared_normalized_texts(batch_jobs, tmp_path):
    # Three shared groups + five unique groups: not enough for 2*5 independent
    # texts. Must reject, rather than leak duplicate text between industries.
    with pytest.raises(ValueError, match="Insufficient disjoint"):
        prepare_batch(
            batch_jobs,
            tmp_path / "samples",
            batch_name="sales_customer_service",
            tune_per_industry=1,
            holdout_per_industry=1,
            allow_unpinned_fixture=True,
        )
    assert not (tmp_path / "samples").exists()


def test_sampling_success_is_disjoint_and_reproducible(batch_jobs, tmp_path):
    path = batch_jobs / "jobs_analysis.parquet"
    table = pq.read_table(path)
    rows = table.to_pylist()
    for row in rows:
        if row["id"] > 2 and row["requirements"] not in {None, "Không"}:
            row["requirements"] += f" synthetic distinct {row['id']}"
    pq.write_table(pa.Table.from_pylist(rows, schema=table.schema), path)
    manifest_path = batch_jobs / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][path.name]["sha256"] = file_sha256(path)
    manifest_path.write_text(json.dumps(manifest))
    original_sha = file_sha256(path)
    outputs = [tmp_path / "samples_one", tmp_path / "samples_two"]
    for out in outputs:
        prepare_batch(
            batch_jobs,
            out,
            batch_name="sales_customer_service",
            tune_per_industry=1,
            holdout_per_industry=1,
            allow_unpinned_fixture=True,
        )
    chosen = set()
    for split in ["tune", "holdout"]:
        name = f"{split}_unlabelled.json"
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
        samples = json.loads((outputs[0] / name).read_text())
        assert len(samples) == 5
        for sample in samples:
            hashed = sample["normalized_text_hash"]
            assert hashed not in chosen
            assert hashed != normalized_text_hash("Biết Tiếng Anh")
            chosen.add(hashed)
    assert file_sha256(path) == original_sha


def test_runner_batch_scope_and_replay_do_not_run_on_pilot(batch_jobs, tmp_path):
    kwargs = {
        "taxonomy_dir": SALES_MAPPINGS,
        "batch_name": "sales_customer_service",
        "allow_unpinned_fixture": True,
    }
    first = run_skills(batch_jobs, tmp_path / "first", batch_size=1, **kwargs)
    second = run_skills(batch_jobs, tmp_path / "second", batch_size=23, **kwargs)
    assert first["artifacts"] == second["artifacts"]
    assert first["counts"]["scope_rows"] == 35
    pairs = pq.read_table(tmp_path / "first/job_skill_match.parquet").to_pylist()
    statuses = pq.read_table(tmp_path / "first/job_skill_status.parquet").to_pylist()
    assert statuses[0]["status"] == "out_of_scope"
    assert all(row["job_id"] != 1 for row in pairs)
    assert first["scope"] == list(batch_scope("sales_customer_service"))
    # No cross-run cache pollution: a legacy run does not retain CRM results.
    run_skills(batch_jobs, tmp_path / "pilot", allow_unpinned_fixture=True)
    assert pq.read_table(tmp_path / "pilot/job_skill_match.parquet").to_pylist() == [
        {"job_id": 1, "skill_code": "english", "skill_name": "Tiếng Anh"},
    ]


def test_no_global_expanded_context_in_batch(batch_jobs, tmp_path):
    with pytest.raises(ValueError, match="experimental"):
        run_skills(
            batch_jobs,
            tmp_path / "bad",
            taxonomy_dir=SALES_MAPPINGS,
            batch_name="sales_customer_service",
            expanded_context=True,
            allow_unpinned_fixture=True,
        )


def test_cli_batch_and_defaults():
    from job_warehouse.cli import build_parser

    args = build_parser().parse_args(
        [
            "silver",
            "skills",
            "--jobs-run",
            "/tmp/jobs",
            "--output-dir",
            "/tmp/out",
            "--batch",
            "sales_customer_service",
        ]
    )
    assert args.batch == "sales_customer_service"
    assert isinstance(args.jobs_run, Path)


@pytest.fixture
def merge_inputs(batch_jobs, tmp_path):
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    run_skills(batch_jobs, baseline, allow_unpinned_fixture=True)
    (baseline / "acceptance.json").write_text(
        json.dumps(
            {
                "status": "accepted_offline_not_db_published",
                "manifest_sha256": file_sha256(baseline / "manifest.json"),
            }
        )
    )
    run_skills(
        batch_jobs,
        candidate,
        allow_unpinned_fixture=True,
        batch_name="sales_customer_service",
        taxonomy_dir=SALES_MAPPINGS,
    )
    candidate_manifest = json.loads((candidate / "manifest.json").read_text())
    gate = {
        "status": "accepted_ai_holdout_not_human_gold",
        "scope": list(batch_scope("sales_customer_service")),
        "taxonomy_sha256": file_sha256(SALES_MAPPINGS / "taxonomy.csv"),
        "aliases_sha256": file_sha256(SALES_MAPPINGS / "aliases.csv"),
        "policy_sha256": file_sha256(SALES_MAPPINGS / "policy.json"),
        "asset_hashes": candidate_manifest["asset_hashes"],
        "validation_artifacts": {
            str(SALES_MAPPINGS / "taxonomy.csv"): file_sha256(SALES_MAPPINGS / "taxonomy.csv")
        },
        # Synthetic gate metadata only; production reference lives outside Git.
        "by_industry": {
            label: {
                "tp": 70,
                "fp": 1,
                "fn": 4,
                "texts": 50,
                "precision": 70 / 71,
                "recall": 70 / 74,
            }
            for label in batch_scope("sales_customer_service")
        },
    }
    gate_path = tmp_path / "gate.json"
    gate_path.write_text(json.dumps(gate))
    return baseline, candidate, gate_path


def test_merge_preserves_pilot_and_replays(merge_inputs, tmp_path):
    from job_warehouse.skills.batch_merge import merge_batch

    baseline, candidate, gate = merge_inputs
    hashes = {
        p: file_sha256(p) for root in [baseline, candidate] for p in root.rglob("*") if p.is_file()
    }
    one, two = tmp_path / "merged_one", tmp_path / "merged_two"
    for out in [one, two]:
        report = merge_batch(candidate, baseline, gate, out, batch_name="sales_customer_service")
        assert report["batch_jobs"] == 35
        assert report["baseline_outside_batch_preserved"] is True
        for name in ["job_skill_match.parquet", "job_skill_evidence.parquet"]:
            old = pq.read_table(baseline / name)
            new = pq.read_table(out / name)
            assert new.slice(0, old.num_rows).equals(old)
        assert (
            pq.read_table(out / "job_skill_status.parquet")
            .slice(0, 1)
            .equals(pq.read_table(baseline / "job_skill_status.parquet").slice(0, 1))
        )
    for name in [
        "job_skill_match.parquet",
        "job_skill_status.parquet",
        "job_skill_evidence.parquet",
    ]:
        assert file_sha256(one / name) == file_sha256(two / name)
    assert all(file_sha256(p) == sha for p, sha in hashes.items())


@pytest.mark.parametrize("fault", ["weak", "scope", "taxonomy", "code", "review"])
def test_merge_rejects_invalid_or_changed_gate(merge_inputs, tmp_path, fault):
    from job_warehouse.skills.batch_merge import merge_batch

    baseline, candidate, path = merge_inputs
    gate = json.loads(path.read_text())
    if fault == "weak":
        next(iter(gate["by_industry"].values()))["precision"] = 0.94
    elif fault == "scope":
        gate["scope"] = ["Marketing"]
    elif fault == "taxonomy":
        gate["taxonomy_sha256"] = "0" * 64
    elif fault == "code":
        first = next(iter(gate["asset_hashes"]))
        gate["asset_hashes"][first] = "0" * 64
    elif fault == "review":
        first = next(iter(gate["validation_artifacts"]))
        gate["validation_artifacts"][first] = "0" * 64
    path.write_text(json.dumps(gate))
    with pytest.raises(ValueError):
        merge_batch(
            candidate, baseline, path, tmp_path / "bad", batch_name="sales_customer_service"
        )
    assert not (tmp_path / "bad").exists()


def test_partial_batch_preserves_deferred_industry(merge_inputs, batch_jobs, tmp_path):
    from job_warehouse.skills.batch_merge import merge_batch

    baseline, _, gate_path = merge_inputs
    selected = batch_scope("sales_customer_service")[:-1]
    candidate = tmp_path / "partial_candidate"
    report = run_skills(
        batch_jobs,
        candidate,
        allow_unpinned_fixture=True,
        batch_name="sales_customer_service",
        taxonomy_dir=SALES_MAPPINGS,
        enabled_industries=selected,
    )
    assert report["counts"]["scope_rows"] == 28
    assert report["deferred_industries"] == ["Bất động sản"]
    gate = json.loads(gate_path.read_text())
    gate["scope"] = list(selected)
    gate["by_industry"] = {k: v for k, v in gate["by_industry"].items() if k in selected}
    gate_path.write_text(json.dumps(gate))
    out = tmp_path / "partial_accepted"
    merged = merge_batch(candidate, baseline, gate_path, out, batch_name="sales_customer_service")
    assert merged["batch_jobs"] == 28
    old = [
        r
        for r in pq.read_table(baseline / "job_skill_status.parquet").to_pylist()
        if r["job_industry"] == "Bất động sản"
    ]
    new = [
        r
        for r in pq.read_table(out / "job_skill_status.parquet").to_pylist()
        if r["job_industry"] == "Bất động sản"
    ]
    assert new == old
    assert all(r["job_id"] < 30 for r in pq.read_table(out / "job_skill_match.parquet").to_pylist())


def test_industry_subset_cannot_change_legacy_default(batch_jobs, tmp_path):
    with pytest.raises(ValueError, match="explicit batch"):
        run_skills(
            batch_jobs,
            tmp_path / "bad_subset",
            allow_unpinned_fixture=True,
            enabled_industries=("Marketing",),
        )


def test_keyword_gate_needs_explicit_owner_policy(merge_inputs, tmp_path):
    from job_warehouse.skills.batch_merge import merge_batch

    baseline, candidate, path = merge_inputs
    gate = json.loads(path.read_text())
    gate["status"] = "accepted_owner_keyword_policy_no_recall_guarantee"
    path.write_text(json.dumps(gate))
    with pytest.raises(ValueError, match="bound owner decision"):
        merge_batch(
            candidate, baseline, path, tmp_path / "out", batch_name="sales_customer_service"
        )


def test_owner_keyword_completion_does_not_require_recall_target(merge_inputs, tmp_path):
    from job_warehouse.skills.batch_merge import merge_batch

    baseline, candidate, gate_path = merge_inputs
    # Explicit synthetic completion metadata, separate from historical AI gates.
    manifest_path = candidate / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["policy"]["decisions"]["completion_policy"] = "owner_explicit_keywords_skip_unclear"
    manifest["extractor_version"] = "requirements-skills-explicit-keywords-v1"
    manifest_path.write_text(json.dumps(manifest))
    owner_path = tmp_path / "owner.json"
    owner_path.write_text(
        json.dumps(
            {
                "decision_type": "explicit_keywords_skip_unclear_no_recall_target",
                "owner_quote": "Synthetic owner fixture: retain jobs and skip unknown skills.",
                "preserve_source_jobs": True,
            }
        )
    )
    gate = json.loads(gate_path.read_text())
    gate.update(
        status="accepted_owner_keyword_policy_no_recall_guarantee",
        owner_decision_path=str(owner_path),
        independent_quality_claim=False,
    )
    gate["validation_artifacts"][str(owner_path)] = file_sha256(owner_path)
    for m in gate["by_industry"].values():
        m["recall"] = 0.1  # Completion deliberately does not promise high recall.
    gate_path.write_text(json.dumps(gate))
    report = merge_batch(
        candidate, baseline, gate_path, tmp_path / "out", batch_name="sales_customer_service"
    )
    assert report["completion_policy"] == "accepted_owner_keyword_policy_no_recall_guarantee"
    assert "no independent precision/recall guarantee" in report["semantic_reference"]
