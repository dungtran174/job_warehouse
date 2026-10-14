import pytest

from job_warehouse.silver.industry_rollup import resolve_industry_rollup


def test_follows_owner_selected_chain_to_one_final_parent() -> None:
    decisions = {
        "Tư vấn chăm sóc khách hàng": "Chăm sóc khách hàng",
        "Chăm sóc khách hàng": "Giáo dục - Đào tạo / Chăm sóc khách hàng",
    }
    assert resolve_industry_rollup("Tư vấn chăm sóc khách hàng", decisions) == (
        "Giáo dục - Đào tạo / Chăm sóc khách hàng"
    )
    assert resolve_industry_rollup("Nhân viên kinh doanh", decisions) == "Nhân viên kinh doanh"


@pytest.mark.parametrize(
    "decisions", [{"A": "A"}, {"A": "B", "B": "A"}, {"A": "B", "B": "C", "C": "B"}]
)
def test_rejects_cycles(decisions: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="Cycle"):
        resolve_industry_rollup("A", decisions)


def test_rejects_empty_parent() -> None:
    with pytest.raises(ValueError, match="Empty parent"):
        resolve_industry_rollup("A", {"A": " "})
