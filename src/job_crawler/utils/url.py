from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

TOPCV_HOSTS = {"topcv.vn", "www.topcv.vn"}
TRACKING_PARAMETERS = {"ta_source", "ref", "sr_id", "u_sr_id", "fbclid", "gclid"}
JOB_ID_PATTERN = re.compile(r"/viec-lam/(?:[^/?#]+/)+(\d+)\.html/?$", re.IGNORECASE)


def canonicalize_url(url: str, base_url: str | None = None) -> str:
    absolute = urljoin(base_url, url) if base_url else url
    parts = urlsplit(absolute)
    scheme = parts.scheme.lower() or "https"
    hostname = (parts.hostname or "").lower()
    port = parts.port
    netloc = hostname
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{hostname}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path) or "/"
    if path != "/":
        path = path.rstrip("/")
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMETERS and not key.lower().startswith("utm_")
    ]
    return urlunsplit((scheme, netloc, path, urlencode(sorted(query)), ""))


def extract_topcv_job_id(url: str) -> str | None:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in TOPCV_HOSTS:
        return None
    match = JOB_ID_PATTERN.search(parts.path)
    return match.group(1) if match else None


def is_topcv_detail_url(url: str) -> bool:
    return extract_topcv_job_id(url) is not None


def topcv_robots_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme or "https", parts.netloc, "/robots.txt", "", ""))
