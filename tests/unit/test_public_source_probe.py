import gzip
import json
import runpy
from pathlib import Path

import httpx
import pytest
import respx

capture = runpy.run_path(str(Path(__file__).parents[2] / "scripts/public_source_probe.py"))[
    "capture"
]


@respx.mock
@pytest.mark.parametrize(
    "status,body",
    [(403, "Forbidden"), (401, "Login"), (200, "<title>Just a moment</title>cf-chl-test")],
)
def test_saves_denial_before_stopping(tmp_path, status, body):
    route = respx.get("https://example.org/list").mock(
        return_value=httpx.Response(status, text=body)
    )
    with pytest.raises(RuntimeError, match="STOP source"):
        capture(tmp_path, "denied", "https://example.org/list", delay=0)
    meta = json.loads((tmp_path / "denied.json").read_text())
    assert meta["status"] == status and meta["blocked"]
    assert gzip.decompress((tmp_path / "denied.hop-0.body.gz").read_bytes()).decode() == body
    assert route.call_count == 1


@respx.mock
def test_no_cross_origin_redirect(tmp_path):
    respx.get("https://example.org/").mock(
        return_value=httpx.Response(302, headers={"Location": "https://other.example/"})
    )
    with pytest.raises(RuntimeError, match="Cross-origin"):
        capture(tmp_path, "redirect", "https://example.org/", delay=0)
    assert len(respx.calls) == 1
