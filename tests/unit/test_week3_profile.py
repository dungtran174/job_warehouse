import runpy
from pathlib import Path

MODULE = runpy.run_path(str(Path(__file__).parents[2] / "scripts/profile_week3_inputs.py"))


def test_missing_distinguishes_null_absent_blank_empty_array_from_zero():
    profile = MODULE["field_profile"](
        [
            {},
            {"x": None},
            {"x": " "},
            {"x": []},
            {"x": 0},
            {"x": False},
            {"x": ["a"]},
        ]
    )["x"]
    assert profile["missing_count"] == 4
    assert profile["missing"] == {
        "absent": 1,
        "null": 1,
        "blank_string": 1,
        "empty_array": 1,
        "present": 3,
    }
    assert profile["types"]["integer"] == profile["types"]["boolean"] == 1
    assert profile["array_element_types"] == {"string": 1}


def test_salary_shapes_do_not_infer_a_fixed_salary_from_bare_number():
    classify = MODULE["salary_shape"]
    assert classify("20000000") == "bare_number_ambiguous_bound"
    assert classify("7.1 triệu - 11.6 triệu") == "range_million_decimal"
    assert classify("600 - 1600 USD MONTH") == "range_USD_MONTH"
    assert classify("Cạnh tranh") == "Cạnh tranh"
    assert classify(None) == "null"
