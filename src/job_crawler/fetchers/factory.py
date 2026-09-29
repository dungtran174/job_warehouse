from __future__ import annotations

from job_crawler.config import CrawlConfig
from job_crawler.fetchers.auto import AutoFetcher
from job_crawler.fetchers.base import Fetcher
from job_crawler.fetchers.careerlink import CareerLinkHttpFetcher
from job_crawler.fetchers.http import HttpFetcher
from job_crawler.fetchers.playwright import PlaywrightFetcher
from job_crawler.fetchers.timviec365 import Timviec365HttpFetcher
from job_crawler.fetchers.vieclam24h import Vieclam24hBrowserFetcher
from job_crawler.fetchers.vietnamworks import VietnamWorksFetcher
from job_crawler.fetchers.vietnamworks_browser import VietnamWorksBrowserFetcher


def create_fetcher(config: CrawlConfig) -> Fetcher:
    if config.source == "vietnamworks" and config.fetcher == "playwright":
        return VietnamWorksBrowserFetcher(config)
    if config.source == "vieclam24h":
        return Vieclam24hBrowserFetcher(config)
    if config.source == "timviec365":
        return Timviec365HttpFetcher(config)
    if config.source == "careerlink":
        return CareerLinkHttpFetcher(config)
    if config.fetcher == "http":
        return HttpFetcher(config)
    if config.fetcher == "playwright":
        return PlaywrightFetcher(config)
    if config.source == "vietnamworks":
        return VietnamWorksFetcher(config)
    return AutoFetcher(config)
