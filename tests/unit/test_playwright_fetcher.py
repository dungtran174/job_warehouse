import gzip
from pathlib import Path

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from job_crawler.config import CrawlConfig
from job_crawler.fetchers.base import FetchError
from job_crawler.fetchers.playwright import PlaywrightFetcher, classify_browser_page


class FakePage:
    def screenshot(self, *, path: str, full_page: bool) -> None:
        assert full_page
        Path(path).write_bytes(b"fake-png")


class Closeable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class Stoppable:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def config() -> CrawlConfig:
    return CrawlConfig(
        fetcher="playwright",
        authorization_reference="APPROVAL",
        save_screenshot_on_error=True,
    )


class FakeLocator:
    def __init__(self, text: str = "Public jobs", visible: bool = False) -> None:
        self.text = text
        self.visible = visible
        self.clicked = False

    @property
    def first(self):
        return self

    def is_visible(self, *, timeout: int) -> bool:
        assert timeout == 500
        return self.visible

    def click(self, *, timeout: int) -> None:
        assert timeout == 1000
        self.clicked = True

    def wait_for(self, *, timeout: int) -> None:
        assert timeout <= 8000

    def inner_text(self, *, timeout: int) -> str:
        assert timeout == 3000
        return self.text


class FakeResponse:
    def __init__(self, url: str, status: int = 200, text: str = "") -> None:
        self.url = url
        self.status = status
        self.headers = {"content-type": "text/html"}
        self._text = text

    def text(self) -> str:
        return self._text


class BrowserPage(FakePage):
    def __init__(
        self,
        url: str,
        *,
        title: str = "Jobs",
        text: str = "Public jobs",
        html: str = "<html><body>Public jobs</body></html>",
        error: Exception | None = None,
        status: int = 200,
    ) -> None:
        self.url = url
        self._title = title
        self._text = text
        self._html = html
        self._error = error
        self._status = status
        self.closed = False
        self.evaluations = 0

    def goto(self, url: str, **_kwargs):
        self.url = url
        if self._error:
            raise self._error
        return FakeResponse(url, self._status)

    def locator(self, selector: str) -> FakeLocator:
        if selector == "body":
            return FakeLocator(self._text)
        return FakeLocator()

    def wait_for_timeout(self, _milliseconds: int) -> None:
        pass

    def evaluate(self, _script: str) -> None:
        self.evaluations += 1

    def content(self) -> str:
        return self._html

    def title(self) -> str:
        return self._title

    def close(self) -> None:
        self.closed = True


class FakeRequest:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def get(self, _url: str, *, timeout: float) -> FakeResponse:
        assert timeout > 0
        return self.response


class FakeContext(Closeable):
    def __init__(self, pages: list[BrowserPage], request: FakeRequest) -> None:
        super().__init__()
        self.pages = pages
        self.request = request

    def new_page(self) -> BrowserPage:
        return self.pages.pop(0)


class FakeBrowser(Closeable):
    def __init__(self, context: FakeContext) -> None:
        super().__init__()
        self.context = context

    def new_context(self) -> FakeContext:
        return self.context


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser
        self.headless = None

    def launch(self, *, headless: bool) -> FakeBrowser:
        self.headless = headless
        return self.browser


class FakeDriver(Stoppable):
    def __init__(self, browser: FakeBrowser) -> None:
        super().__init__()
        self.chromium = FakeChromium(browser)


class FakeManager:
    def __init__(self, driver: FakeDriver) -> None:
        self.driver = driver

    def start(self) -> FakeDriver:
        return self.driver


def browser_fetcher(tmp_path, pages: list[BrowserPage], **overrides) -> PlaywrightFetcher:
    cfg = CrawlConfig(
        fetcher="playwright",
        authorization_reference="APPROVAL",
        delay_min_seconds=0,
        delay_max_seconds=0,
        browser_wait_ms=0,
        **overrides,
    )
    request = FakeRequest(FakeResponse("https://www.topcv.vn/robots.txt", text="User-agent: *"))
    context = FakeContext(pages, request)
    manager = FakeManager(FakeDriver(FakeBrowser(context)))
    fetcher = PlaywrightFetcher(cfg, playwright_factory=lambda: manager)
    fetcher.configure_run(tmp_path, "batch-test")
    return fetcher


def test_browser_page_classification() -> None:
    assert classify_browser_page("Verify you are human", "https://topcv.vn", "") == "captcha"
    assert classify_browser_page("Denied", "https://topcv.vn", "Access denied") == ("access_denied")
    assert (
        classify_browser_page(
            "Attention Required! | Cloudflare",
            "https://topcv.vn/jobs",
            "Sorry, you have been blocked. CAPTCHA may be required.",
        )
        == "access_denied"
    )
    assert classify_browser_page("Login", "https://topcv.vn/login", "") == "login_required"
    assert classify_browser_page("Jobs", "https://topcv.vn/jobs", "Public jobs") is None


def test_error_artifacts_include_html_and_screenshot(tmp_path) -> None:
    fetcher = PlaywrightFetcher(config())
    fetcher.configure_run(tmp_path, "batch-test")
    artifacts = fetcher._save_artifacts(  # noqa: SLF001 - focused artifact contract test
        FakePage(),
        "https://www.topcv.vn/jobs",
        "<html>blocked</html>",
        kind="captcha",
        screenshot=True,
    )
    assert len(artifacts) == 2
    html_path = tmp_path / next(path for path in artifacts if path.endswith(".html.gz"))
    screenshot_path = tmp_path / next(path for path in artifacts if path.endswith(".png"))
    with gzip.open(html_path, "rt", encoding="utf-8") as handle:
        assert handle.read() == "<html>blocked</html>"
    assert screenshot_path.read_bytes() == b"fake-png"


def test_close_releases_context_browser_and_driver() -> None:
    fetcher = PlaywrightFetcher(config())
    context = Closeable()
    browser = Closeable()
    driver = Stoppable()
    fetcher._context = context  # noqa: SLF001
    fetcher._browser = browser  # noqa: SLF001
    fetcher._playwright = driver  # noqa: SLF001
    fetcher.close()
    assert context.closed
    assert browser.closed
    assert driver.stopped


def test_get_rendered_page_and_robots(tmp_path) -> None:
    page = BrowserPage("https://www.topcv.vn/jobs")
    fetcher = browser_fetcher(tmp_path, [page], save_html=True)
    robots = fetcher.get("https://www.topcv.vn/robots.txt")
    response = fetcher.get("https://www.topcv.vn/jobs")
    assert robots.text == "User-agent: *"
    assert response.status_code == 200
    assert response.fetcher == "playwright"
    assert response.screenshot_path is not None
    assert page.evaluations == 2
    assert page.closed
    fetcher.close()


def test_get_stops_on_browser_challenge_and_saves_artifacts(tmp_path) -> None:
    page = BrowserPage(
        "https://www.topcv.vn/jobs",
        title="Verify you are human",
        text="CAPTCHA",
    )
    fetcher = browser_fetcher(tmp_path, [page], save_screenshot_on_error=True)
    with pytest.raises(FetchError) as caught:
        fetcher.get("https://www.topcv.vn/jobs")
    assert caught.value.blocked
    assert caught.value.challenge_type == "captcha"
    assert len(caught.value.artifact_paths) == 2
    assert fetcher.state.challenge_detected
    assert page.closed


def test_get_retries_one_network_timeout(tmp_path) -> None:
    first = BrowserPage(
        "https://www.topcv.vn/jobs", error=PlaywrightTimeoutError("net::ERR_TIMED_OUT")
    )
    second = BrowserPage("https://www.topcv.vn/jobs")
    fetcher = browser_fetcher(tmp_path, [first, second], max_retries=1)
    response = fetcher.get("https://www.topcv.vn/jobs")
    assert response.attempt == 2
    assert first.closed and second.closed


def test_robots_http_error_is_reported(tmp_path) -> None:
    fetcher = browser_fetcher(tmp_path, [])
    fetcher._ensure_started()  # noqa: SLF001
    fetcher._context.request.response = FakeResponse(  # noqa: SLF001
        "https://www.topcv.vn/robots.txt", status=503
    )
    with pytest.raises(FetchError) as caught:
        fetcher.get("https://www.topcv.vn/robots.txt")
    assert caught.value.status_code == 503
