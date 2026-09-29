# job_warehouse

Pipeline thu thập dữ liệu tuyển dụng công khai cho phân tích thị trường Việt Nam. Giai
đoạn hiện tại có adapter TopCV, CareerViet, VietnamWorks, CareerLink, Timviec365
và Việc Làm 24h, lưu batch raw.
Pilot VietnamWorks ngày 26/09 dừng ở listing render HTTP 403; lượt browser-first
ngày 29/09 đã ghi và audit **295 detail raw duy nhất** từ tám trang listing chính.
CareerViet được chọn
sau feasibility probe giới hạn; TopCV vẫn được giữ nhưng live detail có thể bị WAF chặn.
Dự án không triển khai OLTP, Airflow, dbt, Data Warehouse, dashboard hoặc LLM.

Các đường dẫn `data/` và `.runtime/` trong README/báo cáo là **artifact cục bộ**,
được `.gitignore` loại khỏi GitHub: HTML/JSONL raw, checkpoint, diagnostics, log,
ảnh challenge và backup diff. Clone repository không có các artifact này; lệnh
audit/profile/resume cần đúng batch trên máy. Git chỉ chứa code, tài liệu và fixture
kiểm thử rút gọn trong `tests/fixtures/`, không phải toàn bộ phản hồi crawl.
Các báo cáo theo ngày là snapshot của từng lượt thử: trạng thái Git hoặc câu
“không commit/push” trong báo cáo mô tả lượt đó, không phải cấm một lượt publish
code/test/tài liệu riêng được chủ dự án yêu cầu sau này. Không publish raw.

## Cổng an toàn và phạm vi

Quyết định nội bộ của chủ dự án: cho phép thử giới hạn trên trang tuyển dụng công khai
nếu robots và điều khoản hiện hành không cấm hoạt động dự định, trừ ngoại lệ
probe JobOKO cụ thể được chủ dự án quyết định dưới đây. Cờ
`--project-owner-public-test` chỉ ghi nhận quyết định của chủ dự án, **không phải**
sự chấp thuận của VietnamWorks hay bất kỳ chủ nguồn nào. Trong mode `sample`,
giới hạn là đúng 1 listing và tối đa 3 detail cho TopCV/CareerViet. Với VietnamWorks/CareerLink,
chủ dự án đã cho phép pilot nhỏ trong mode `sample`: tối đa 2 listing/20 detail;
mặc định vẫn là 1/3 nếu không truyền giới hạn. Probe feasibility vẫn khóa 1/3.
CareerLink, Timviec365, Việc Làm 24h và VietnamWorks có mode `bounded` với giới hạn tường minh, xem bên dưới;
đây không phải quyền tự động mở rộng hay chạy lại sau challenge.
`--authorization-reference` chỉ dùng khi có
văn bản chấp thuận thật của chủ nguồn; không tự tạo mã hoặc dùng mã chủ dự án thay thế.

**Không bắt buộc văn bản của chủ website cho phép thử kỹ thuật công khai được
chủ dự án yêu cầu rõ.** Dùng `--project-owner-public-test` hoặc ghi cùng cơ sở
trong biên bản probe, `authorization_reference=null`; thiếu văn bản tự nó không
phải điều kiện dừng sample. Điều này không thay đổi điều khoản website hoặc xác
nhận quyền sử dụng dữ liệu quy mô lớn; luôn kiểm tra robots và tín hiệu truy cập.

Crawler không đăng nhập, không vượt CAPTCHA, không dùng stealth hoặc proxy rotation.
Dừng khi điều khoản cấm (trừ đúng ngoại lệ probe JobOKO dưới đây), robots không
cho phép, HTTP 401/403/429 hoặc CAPTCHA/challenge, kể cả HTTP 200; không dùng
Playwright để vượt một phản hồi chặn. Trước khi lưu HTML, ghi rõ phạm vi quyết
định và quyền sử dụng đã/chưa được xác minh; ngoài ngoại lệ này, chỉ lưu khi được phép.

### Ngoại lệ nội bộ: một probe kỹ thuật JobOKO ngày 28/09/2026

Theo yêu cầu rõ trong chat, chủ dự án quyết định thử tối đa **1 listing chính và
3 detail từ listing đó** trên `https://vn.joboko.com/`, dù đã biết điều khoản
JobOKO hạn chế bot/crawler. Đây **không phải chấp thuận của JobOKO**, không xác
nhận quyền sử dụng/tái công bố dữ liệu và không tạo authorization-reference.
Biên bản ghi `access_basis=project_owner_public_test`, `authorization_reference=null`,
quyết định chủ dự án và hạn chế điều khoản; không sửa báo cáo/bằng chứng cũ.

Chỉ gửi request khi **robots hiện tại cho phép đúng URL**, HTTP thông thường trước,
một luồng, nghỉ ít nhất 10 giây, không retry phản hồi chặn. Chỉ dùng browser thường
nếu HTTP 200 bình thường cần JavaScript; không đăng nhập hoặc vượt 401/403/429,
CAPTCHA/challenge, không stealth/proxy/CAPTCHA solver. Lưu status, URL cuối và
body/HTML của đúng mẫu làm bằng chứng **cục bộ, không công bố raw**; việc lưu này
theo quyết định nội bộ, không được ghi thành quyền do nguồn cấp. Không lấy preview
listing làm detail, không crawl sang host khác. Dừng ngay khi robots cấm hoặc bị chặn.

Ngoại lệ chỉ dành cho probe này, không mở quyền cho nguồn khác, batch lớn hoặc
probe tự động tiếp theo; không commit/push. CLI chưa tích hợp nguồn JobOKO: probe
dùng công cụ ghi bằng chứng hiện có, không mở `bounded` hay sửa guard nguồn cũ.

### Thử lại TopCV theo yêu cầu mới ngày 29/09/2026

Lượt mới do chủ dự án yêu cầu, không tự suy diễn tình trạng hiện tại từ challenge
cũ và không xóa/sửa lịch sử. Thử đúng 1 listing chính và tối đa 3 detail từ listing;
HTTP trước, nghỉ ít nhất 10 giây, một luồng, không retry khi bị chặn. Chỉ render
browser thường nếu HTTP 200 bình thường cần JavaScript; robots không cho phép
hoặc HTTP 401/403/429/CAPTCHA/challenge thì dừng ngay, không đổi công cụ để né.
Không lấy sitemap/tin gợi ý thay listing chính. Dữ liệu JSON chỉ dùng nếu trang
công khai thật tải để hiển thị nội dung, ghi URL và nguồn gốc, không dò API nội bộ.

Chỉ khi ba detail đủ title/company/toàn văn description/requirements mới xem xét
tích hợp và pilot tối đa 20 detail, lưu HTML/raw JSONL/dedup/checkpoint/resume.
Đây không phải gate `pilot` 250 của CareerViet, không cho phép tự mở rộng 100/300.
CLI hiện giữ TopCV owner sample 1/3; chỉ cập nhật tích hợp/guard pilot khi mẫu đạt,
không đặt authorization-reference giả để vượt guard. Lưu bằng chứng nội bộ theo
quyết định chủ dự án, không ghi là chấp thuận TopCV. Không commit/push.

### Giới hạn chung của các gate

Sample bị khóa cứng ở tối đa 2 URL listing và 20 URL detail duy nhất. Full snapshot không
được chạy nếu chưa có xác nhận riêng trong cuộc trao đổi hiện tại; CLI còn bắt buộc
`--confirm-full`.

Gate `medium` là chế độ riêng, bị khóa ở tối đa 5 listing và 50 detail. Nó không phải
full snapshot và vẫn yêu cầu authorization reference.

Gate `pilot` bị khóa ở tối đa 5 listing đã discovery và 250 detail cumulative. Resume
từ batch `medium` sang `pilot` giữ authorization reference gốc và thêm reference mới
vào `authorization_references`; tỷ lệ detail lỗi tối đa là 5%.

Gate `page6-check` là chặng kiểm tra riêng cho CareerViet: bắt buộc resume batch pilot
5/250 nguyên vẹn, HTTP thuần, lưu HTML, nội dung detail đầy đủ, và đúng giới hạn
cumulative 6 listing/300 detail. Gate `pilot` vẫn giữ nguyên 5/250.

## Kiến trúc

```text
CLI -> source-independent engine -> fetcher
                         |-> source adapter/parsers
                         |-> JSONL + manifest + error log
                         `-> SQLite technical checkpoint
```

- `crawlers/base.py` định nghĩa hợp đồng adapter dùng chung.
- `crawlers/topcv.py`, `crawlers/careerviet.py`, `crawlers/vietnamworks.py`,
  `crawlers/careerlink.py` và các parser tương ứng chứa logic
  riêng của từng nguồn.
- `engine.py` quản lý robots, phân trang, deduplication, giới hạn và resume.
- `storage/` ghi JSONL append-only, manifest nguyên tử và checkpoint kỹ thuật. SQLite
  không phải cơ sở dữ liệu OLTP nghiệp vụ.

## Cài đặt

Yêu cầu Python 3.11 trở lên:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m playwright install chromium
```

Các cấu hình không bí mật có thể đặt bằng biến môi trường mô tả trong `.env.example`.
Dự án không tự đọc file `.env`; export biến bằng công cụ shell/deployment phù hợp.

## Kiểm tra offline

Các test mặc định loại marker `live` và không truy cập website:

```bash
ruff format --check .
ruff check .
mypy src
pytest -m "not live" --cov=job_crawler --cov-report=term-missing
```

## Chạy sample

Chỉ chạy sau khi kiểm tra robots và điều khoản hiện hành của từng nguồn. Ví dụ sau
dùng đường có văn bản chấp thuận thật của chủ nguồn:

```bash
export JOB_CRAWLER_USER_AGENT='job-warehouse-crawler/0.1 (+public-research; contact=data@example.org)'
python -m job_crawler.cli crawl topcv \
  --mode sample \
  --fetcher auto \
  --max-pages 2 \
  --max-details 20 \
  --authorization-reference APPROVAL-REFERENCE
```

`--save-html` là tùy chọn và mặc định tắt. Chỉ bật khi điều khoản hoặc phạm vi chấp
thuận cho phép lưu HTML nguồn. Đường `--project-owner-public-test` hỗ trợ
sample công khai (VietnamWorks/CareerLink tối đa 2 listing/20 detail, nguồn khác 1/3)
và mode `bounded` riêng CareerLink/Timviec365/Việc Làm 24h/VietnamWorks;
manifest ghi `access_basis=project_owner_public_test`
và `authorization_reference=null`, không gắn nhãn chấp thuận của chủ nguồn.

CareerViet dùng cùng guard và pipeline; sample kiểm chứng nhỏ nhất là:

```bash
python -m job_crawler.cli crawl careerviet \
  --mode sample \
  --fetcher http \
  --max-pages 1 \
  --max-details 3 \
  --require-complete-content \
  --authorization-reference APPROVAL-REFERENCE
```

Pagination CareerViet dùng route được xác nhận từ navigation công khai, ví dụ trang 2:
`/viec-lam/tat-ca-viec-lam-trang-2-vi.html`. Crawler không dùng query `?page=N`.

Medium gate hai pha có thể chạy bằng cùng batch:

```bash
python -m job_crawler.cli crawl careerviet --mode medium \
  --max-pages 5 --max-details 10 --fetcher http --save-html \
  --require-complete-content --authorization-reference APPROVAL-REFERENCE

python -m job_crawler.cli crawl careerviet --mode medium \
  --max-pages 5 --max-details 50 --fetcher http --save-html \
  --require-complete-content --resume --resume-batch-id BATCH-ID \
  --authorization-reference APPROVAL-REFERENCE
```

Pilot tiếp tục đúng batch medium, không mở thêm listing khi batch đã đạt 5 trang:

```bash
python -m job_crawler.cli crawl careerviet --mode pilot \
  --max-pages 5 --max-details 250 --fetcher http --save-html \
  --require-complete-content --resume --resume-batch-id BATCH-ID \
  --authorization-reference PILOT-APPROVAL-REFERENCE
```

Chặng kiểm tra trang 6 chỉ dùng sau preflight xác nhận batch pilot 5/250 nguyên vẹn:

```bash
python -m job_crawler.cli crawl careerviet --mode page6-check \
  --max-pages 6 --max-details 300 --fetcher http --save-html \
  --require-complete-content --resume --resume-batch-id BATCH-ID \
  --authorization-reference PAGE6-APPROVAL-REFERENCE
```

Lệnh không mở trang 7; checkpoint giữ 5 listing và 250 detail đã hoàn thành.
Cross-page overlap cùng ID/canonical URL được đếm trong `cross_page_overlaps` và không
tạo detail thứ hai. Enqueue ID mới, fingerprint và trạng thái listing completed được
commit trong cùng một giao dịch SQLite; ID trùng nhưng ánh xạ URL khác sẽ dừng batch.
Với batch page 6 cũ đã dừng giữa chừng tại overlap, hàm
`recover_page6_from_saved_html(root)` đối soát HTML gzip đã lưu, thêm đúng ID thiếu
và có thể gọi lại an toàn trước khi resume; hàm không gửi request mạng.

`--fetcher` nhận `http`, `playwright` hoặc `auto` (mặc định). `auto` bắt đầu bằng HTTP
và chỉ có thể chuyển sang Chromium chuẩn khi HTTP truy cập bình thường nhưng listing
không có job do cần render JavaScript; HTTP 401/403 không kích hoạt fallback.
`--headed` chỉ áp dụng cho Playwright; không có stealth, proxy rotation hay thay đổi
fingerprint. Khi phát hiện CAPTCHA/challenge/access denied, crawler lưu bằng chứng nếu
được yêu cầu bằng `--save-screenshot-on-error`, rồi dừng batch ngay.

Output:

```text
data/raw/<source>/snapshot_date=YYYY-MM-DD/batch_id=<id>/
├── jobs.jsonl
├── manifest.json
├── errors.jsonl
├── checkpoint.sqlite3
├── html/                    # chỉ có khi --save-html hoặc cần lưu bằng chứng lỗi
└── screenshots/             # screenshot đầu tiên/lỗi khi được cấu hình
```

Raw HTML (nếu bật) được nén gzip. `jobs.jsonl` là Bronze, giữ trường `*_raw` và chỉ
chuẩn hóa kỹ thuật. Record thiếu trường bắt buộc được ghi thành lỗi thay vì đưa vào
dataset.

## Resume và full snapshot

`--resume` chọn batch có checkpoint còn pending mới nhất của đúng nguồn và mode. Dùng
thêm `--resume-batch-id <id>` để chọn chính xác batch, ví dụ khi chạy gate nhiều pha.
Resume đối chiếu checkpoint với ID đã có trong `jobs.jsonl` để tránh tải/ghi trùng; phần
đuôi JSONL dang dở do tiến trình bị ngắt được giữ ở `jobs.jsonl.partial` trước khi phục
hồi file hợp lệ.

State incremental nằm tại `data/raw/<source>/incremental_state.sqlite3`, tách khỏi batch.
Nó giữ `first_seen_at`, `last_seen_at`, `last_content_hash`,
`last_detail_fetched_at`, `seen_count` và `active`. Một lần vắng mặt hoặc crawl lỗi không
tự động chuyển job sang inactive. Hiện crawler vẫn tải detail một lần cho mỗi snapshot;
hash được dùng để phân biệt nội dung mới, không đổi hoặc thay đổi sau khi parse.

Lệnh dưới đây chỉ để tài liệu hóa và **không được chạy khi chưa có phê duyệt riêng**:

```bash
python -m job_crawler.cli crawl topcv \
  --mode full-snapshot \
  --resume \
  --confirm-full \
  --authorization-reference APPROVAL-REFERENCE
```

## Thêm nguồn mới

Tạo adapter tuân theo `SourceCrawler`, parser listing/detail và fixture riêng. Không đưa
selector nguồn vào engine, fetcher hoặc storage. Nguồn mới vẫn phải áp dụng cổng quyền
truy cập, robots, rate limit và hợp đồng `JobRecord` chung; field không tồn tại được để
`null`.

## Feasibility probe nguồn mới

Probe chẩn đoán bị khóa ở đúng một listing và tối đa ba detail, không chạy các nguồn
song song:

Trước live phải đối chiếu robots, điều khoản và phạm vi lưu HTML. Hai đường truy cập
được ghi khác nhau: `--authorization-reference` dành cho văn bản của chủ nguồn có thật;
`--project-owner-public-test` chỉ là quyết định nội bộ của chủ dự án và không chứng
minh nguồn đã chấp thuận. Không dùng cả hai cùng lúc.

```bash
python scripts/probe_job_sources.py --source careerviet \
  --max-listing-pages 1 --max-details 3 --fetcher auto \
  --save-html --save-screenshot-on-error \
  --authorization-reference APPROVAL-REFERENCE
```

Nếu quy định của nguồn cho phép thử công khai và không cần lưu HTML, thay cờ cuối
bằng `--project-owner-public-test`. Probe không tự chứng minh quyền; người vận hành
phải dừng nếu quy định hoặc phản hồi truy cập không cho phép.

Các source hợp lệ là `careerviet`, `jobsgo`, `vieclam24h` và `vietnamworks`. Artifact
được ghi dưới `data/diagnostics/source_feasibility/` và bị loại khỏi Git cùng toàn bộ
dữ liệu runtime.

VietnamWorks: sau khi đọc toàn văn thỏa thuận và OCR quy chế, chưa thấy lệnh cấm
áp dụng rõ cho mẫu phi thương mại 1 listing/3 detail. Mẫu ngày 2026-09-26:
listing HTTP 200, 5 URL/ID `-jd` duy nhất ở mục tin nổi bật, 3/3 detail HTTP 200
và có mô tả/yêu cầu sau render. Đây **không** phải chấp thuận của VietnamWorks
hay bằng chứng cho crawl quy mô lớn. Kết quả kiểm tra danh sách chính và pilot bị chặn
ở lượt sau được báo cáo riêng trong mục VietnamWorks bên dưới.
Xem [đối chiếu chính sách/probe](docs/vietnamworks_policy_check_2026-09-26.md).

## Giới hạn hiện tại

- Selector listing/detail được khóa bằng fixture HTML rút gọn. Giao diện nguồn vẫn có
  thể thay đổi nên manifest thống kê field thiếu cho từng batch.
- CareerViet công khai JSON-LD cho metadata và dùng các section ngữ nghĩa cho mô tả/yêu
  cầu. `application_method`, `company_size`, `company_address`, `company_industry` và
  `work_model` có thể `null` khi nguồn không công bố trên detail.
- Chromium chuẩn được hỗ trợ khi HTTP không đủ. Việc một listing tải được không đảm bảo
  mọi detail sẽ tải được; Cloudflare/WAF có thể chặn giữa batch và crawler sẽ dừng, không
  thử vượt chặn.
- Incremental mới có nền tảng ID, content hash và snapshot; chưa theo dõi đầy đủ trạng
  thái tin hết hạn.
- Full snapshot chỉ có guard/checkpoint được kiểm thử offline, chưa được chạy thực tế.

## VietnamWorks: batch sample và resume

Chỉ card trong vùng kết quả tìm kiếm chính được enqueue; tin nổi bật/gợi ý bị loại.
Pagination đã đối chiếu bằng UI: trang 2 chuyển tới /viec-lam?page=2.
Fetcher auto của VietnamWorks kiểm tra HTTP trước; chỉ render listing JS truy cập
bình thường. Detail được parse từ payload inline trong HTML HTTP, không gọi API nội bộ.
ID trong detail phải khớp URL -jv/-jd; thiếu title/company/description/requirements
thì không ghi jobs.jsonl. Các metadata không có giữ null, không lấy bù từ listing.

Pilot ngày 2026-09-26 đã dừng khi render listing trả 403, chưa fetch detail.
Không chạy lại các lệnh dưới đây khi tín hiệu từ chối chưa được giải quyết.

Lệnh đã dùng (pilot nhỏ dùng mode sample, không phải gate pilot 250 của CareerViet):

~~~bash
JOB_CRAWLER_BROWSER_EXECUTABLE_PATH=/usr/bin/google-chrome \
.venv/bin/python -m job_crawler.cli crawl vietnamworks \
  --mode sample --fetcher auto --max-pages 1 --max-details 20 \
  --delay-min 3 --delay-max 5 --max-retries 0 --timeout 30 \
  --save-html --save-screenshot-on-error --require-complete-content \
  --project-owner-public-test \
  --user-agent 'job-warehouse-crawler/0.1 (public-research)'
~~~

Biến JOB_CRAWLER_BROWSER_EXECUTABLE_PATH là tùy chọn đường dẫn browser chuẩn đã có;
không đặt nếu sử dụng Chromium được Playwright cài. Không dùng browser để vượt chặn.

Resume có điều kiện, chỉ khi đã kiểm tra lại nguồn cho phép truy cập. Giới hạn
listing hiện tính cumulative attempts: batch đã dùng 1 attempt bị chặn nên
max-pages=2 dành đúng một attempt nữa, không phải yêu cầu lấy thêm hai trang.

~~~bash
JOB_CRAWLER_BROWSER_EXECUTABLE_PATH=/usr/bin/google-chrome \
.venv/bin/python -m job_crawler.cli crawl vietnamworks \
  --mode sample --fetcher auto --max-pages 2 --max-details 20 \
  --delay-min 3 --delay-max 5 --max-retries 0 --timeout 30 \
  --save-html --save-screenshot-on-error --require-complete-content \
  --project-owner-public-test \
  --user-agent 'job-warehouse-crawler/0.1 (public-research)' \
  --resume --resume-batch-id 20260926T151442Z-1439f601
~~~

Xem docs/vietnamworks_batch_pilot_2026-09-26.md để phân biệt kết quả kiểm tra
listing 50+50 ID, ba detail offline và batch pilot bị chặn (0 record).

### VietnamWorks: browser-first theo yêu cầu mới ngày 29/09/2026

Lượt mới chọn Chrome thường có giao diện **ngay từ đầu** tại `/viec-lam`,
không chuyển công cụ để né phản hồi chặn. `/tim-viec-lam` là landing gợi ý,
không được dùng 330 ID ở đó làm main results. Giữ nguyên batch 403 cũ;
ba detail chẩn đoán cũ không được chép vào raw của batch mới.

Chỉ sau main listing và 3 detail mới được kiểm chứng đủ toàn văn mới chạy
pilot tối đa 20 record. Mode `bounded` của VietnamWorks dành cho yêu cầu này:
trần 8 listing/300 **lần thử detail lũy kế**, `--project-owner-public-test`,
`--fetcher playwright --headed`, lưu HTML, đầy đủ nội dung, nghỉ >=10 giây,
không retry. Không phải full snapshot hoặc chấp thuận của VietnamWorks.
Mode HTTP/auto cũ và gate của nguồn khác không được mở rộng.

```bash
JOB_CRAWLER_BROWSER_EXECUTABLE_PATH=/usr/bin/google-chrome \
.venv/bin/job-crawler crawl vietnamworks --mode bounded \
  --start-url https://www.vietnamworks.com/viec-lam \
  --project-owner-public-test --fetcher playwright --headed \
  --max-pages 2 --max-details 20 --delay-min 10 --delay-max 15 \
  --max-retries 0 --timeout 45 --save-html --save-screenshot-on-error \
  --require-complete-content \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

Fetcher mới lưu status, URL cuối và body gốc trong `http/` **trước khi đọc DOM**;
main card được render/cuộn trong phạm vi hữu hạn. Parser đối chiếu h1/công ty
và toàn văn hai section DOM với payload detail inline, bỏ banner gợi ý.
Chỉ ghi URL/status endpoint JSON mà UI tự tải, không gửi API độc lập.
Robots cấm hoặc 401/403/429/challenge (kể cả 200) dừng ngay, không fallback.
Lỗi điều hướng/DOM cũng dừng và giữ bằng chứng, không che mất HTTP gốc.

Chỉ sau audit pilot ổn định và pagination thật hoạt động mới resume **batch mới**
với `--resume --resume-batch-id ID`, cùng mode/start URL/parser và limits lũy kế:
mốc 100 rồi tối đa 300. Không dùng batch cũ `20260926T151442Z-1439f601`;
không tự resume sau tín hiệu từ chối. Kết quả thực tế ghi trong
[báo cáo browser-first](docs/vietnamworks_browser_assessment_2026-09-29.md).

Kết quả cuối batch mới `20260929T091457Z-1d8023a1`: **295 raw / 295 ID duy nhất**,
toàn văn mô tả và yêu cầu khớp HTML 295/295. Tám listing có 351 ID main;
300 lượt detail gồm 295 hợp lệ, bốn lỗi parser và một lượt gián đoạn được resume.
Dừng ở trần `max-details`, không phải 403/challenge mới; không báo 300 tin thành công.
Raw/HTML/checkpoint chỉ có cục bộ; không tự mở rộng vượt giới hạn hiện tại.

## CareerLink: batch giới hạn sau pilot (26/09/2026)

Ngày 26/09, pilot đạt 20/20 nhưng batch tăng quy mô dừng ở 55/56 detail vì
HTTP 200 chứa hCaptcha thật. Theo yêu cầu kiểm tra mới ngày 29/09, detail pending
đã truy cập bình thường và một đợt resume giới hạn thêm 20 record: **75 raw / 75 ID**.
Lỗi challenge cũ được giữ nguyên; chưa đạt 100/300 và không tự mở rộng.
Xem [báo cáo resume CareerLink](docs/careerlink_resume_assessment_2026-09-29.md).
Mỗi lần tiếp tục vẫn phải đánh giá điều kiện truy cập và dừng khi bị từ chối.

Đã kiểm tra robots, thỏa thuận sử dụng và quy chế hoạt động; mẫu 3/3 và pilot
20/20 detail từ hai trang chính đều đủ nội dung qua HTTP. Xem
[đánh giá ba nguồn](docs/second_source_assessment_2026-09-26.md).
Đây là thử nghiệm theo quyết định của **chủ dự án**, không phải chấp thuận của
CareerLink. Không đặt authorization-reference giả; không công bố lại HTML/raw.
Điều kiện phải được kiểm tra lại trước đợt mới; dừng khi bị từ chối.

CareerLink chỉ hỗ trợ HTTP, lưu HTML, kiểm tra đủ nội dung, một luồng,
nghỉ ít nhất 3 giây và không tự retry. Chế độ `bounded` bắt buộc chỉ định
`--max-pages` (1–6) và `--max-details` (1–300); không phải full snapshot.
Chỉ tăng giới hạn sau khi kiểm tra batch nhỏ, không coi card listing là detail.

```bash
.venv/bin/job-crawler crawl careerlink --mode bounded \
  --project-owner-public-test --fetcher http \
  --max-pages 2 --max-details 100 --delay-min 3 --delay-max 5 \
  --max-retries 0 --timeout 30 --save-html --require-complete-content \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

Resume thêm `--resume --resume-batch-id <batch-id>`, giữ nguyên mode/start URL;
giới hạn trang/detail là **lũy kế**, không phải số request thêm. Không tự resume
sau 401/403/429/challenge. Raw ở `data/raw/careerlink/snapshot_date=.../batch_id=.../`:
`jobs.jsonl`, `errors.jsonl`, `manifest.json`, checkpoint, HTML và thư mục
`http/` lưu body + metadata ngay trước khi xét trạng thái lỗi.
Không đổi dữ liệu CareerViet hoặc chạy lại VietnamWorks.

## Độ sẵn sàng dữ liệu tuần 3

[Đánh giá offline 55 CareerLink + 299 CareerViet](docs/week3_data_readiness_2026-09-26.md)
ghi kiểu giá trị, tỷ lệ thiếu, đối chiếu HTML và các trường hợp chưa có mẫu.
Có thể bắt đầu thiết kế từ 354 tin đã đánh giá ở thời điểm 26/09;
mẫu lịch sử chưa được xác định cục bộ trong báo cáo đó.
Chưa triển khai Bronze/Silver. Báo cáo cũng có lệnh resume có điều kiện, tối đa
20 lần thử detail thêm, **chưa chạy tại thời điểm báo cáo 26/09**.
Đợt 29/09 sau đó đã thêm 20 tin, xem báo cáo resume riêng;
không dùng mốc 100/300 để bỏ qua challenge.

## Timviec365: mẫu HTTP và batch mở rộng có giới hạn

Mode `sample` giữ giới hạn 1 listing/3 detail. Theo yêu cầu tăng dần của chủ dự án
ngày 27/09/2026, mode `bounded` cho phép tối đa 13 listing/300 lần thử detail lũy kế,
với các mốc kiểm toán 30 → 100 → 300 ID hợp lệ (không bảo đảm đạt trước khi đo).
HTTP một luồng, delay tối thiểu 10 giây, không retry, bắt buộc lưu HTML và đủ nội dung.
Đây không phải full snapshot hay chấp thuận của chủ nguồn: manifest vẫn ghi
`access_basis=project_owner_public_test`, `authorization_reference=null`.
Resume `sample` → `bounded` chỉ cho Timviec365, đúng batch ID, mẫu đã completed,
có ít nhất 3 record, không lỗi detail/challenge và cùng parser/schema/access basis.

```bash
job-crawler crawl timviec365 --mode sample --fetcher http \
  --max-pages 1 --max-details 3 --delay-min 10 --delay-max 15 \
  --max-retries 0 --timeout 30 --save-html --require-complete-content \
  --project-owner-public-test \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

Chỉ chạy sau khi đối chiếu điều kiện hiện hành. Thêm `--resume --resume-batch-id ID`
để tiếp tục đúng batch; `max-details` là giới hạn **lũy kế**, không phải số tin thêm.
Không tự resume sau challenge/401/403/429. Fetcher không theo redirect, không gọi
API hoặc tải ảnh/script/PDF; lưu body + metadata trong `http/` trước khi xét lỗi.
Guard robots riêng chặn mọi Disallow khớp (kể cả wildcard), thiên về dừng nếu
quy tắc tương lai có Allow ngoại lệ cần đánh giá lại.

Parser chỉ lấy card thuộc vùng kết quả chính, đối chiếu ID canonical với h1 của
detail; không lấy preview làm mô tả. Ngày “Cập nhật” không được gán thành ngày đăng.
[Đánh giá và pilot 27/09/2026](docs/timviec365_followup_2026-09-27.md) phân biệt
đọc được ba detail với độ ổn định nhiều trang; artifact raw chỉ có trên máy cục bộ.

Lệnh mở rộng theo từng mốc (chỉ sau khi điều kiện hiện hành phù hợp và mốc trước ổn):

```bash
job-crawler crawl timviec365 --mode bounded --fetcher http \
  --resume --resume-batch-id 20260926T174917Z-3a406cfa \
  --max-pages 2 --max-details 30 --delay-min 10 --delay-max 15 \
  --max-retries 0 --timeout 30 --save-html --require-complete-content \
  --project-owner-public-test \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

Mốc tiếp theo dùng 5/100 rồi tối đa 13/300, không chạy đồng thời. `max-details`
đếm lần thử lũy kế; báo cáo phải đếm riêng record hợp lệ và tổng ID duy nhất,
không cộng lại ba detail probe. Không tự chạy lại sau tín hiệu chặn.

Kết quả mở rộng ngày 27/09/2026: **299 ID detail raw duy nhất** từ 13 listing
chính (303 ID discovery), 299/299 mô tả và yêu cầu khớp toàn văn HTML. Bộ đếm
300 lần thử gồm một lần gián đoạn chưa có phản hồi; không báo 300/300 thành công.
Xem [báo cáo mở rộng, resume và kiểm toán](docs/timviec365_expansion_2026-09-27.md).
Không tự mở rộng tiếp; CareerViet 299 và CareerLink 55 được giữ nguyên.

## Việc Làm 24h: batch giới hạn theo yêu cầu chủ dự án

Nguồn `vieclam24h` sử dụng listing chính
`https://vieclam24h.vn/tim-kiem-viec-lam-nhanh` và phân trang `?page=N`.
Lượt ngày 29/09/2026 chọn browser Chrome thường **ngay từ đầu** theo yêu cầu,
không chuyển sang browser để né lỗi HTTP của lượt khác. Chỉ dùng `bounded`,
`--project-owner-public-test`, `--fetcher playwright --headed`, lưu HTML và
kiểm tra nội dung đầy đủ; một luồng, nghỉ tối thiểu 10 giây, `--max-retries 0`.
Không thay đổi guard/fetcher các nguồn cũ. Quyết định chủ dự án không phải
chấp thuận của website (`authorization_reference=null`). Robots cấm hoặc
401/403/429/challenge, kể cả 200, vẫn phải dừng ngay; không full snapshot.

```bash
JOB_CRAWLER_BROWSER_EXECUTABLE_PATH=/usr/bin/google-chrome \
.venv/bin/job-crawler crawl vieclam24h --mode bounded \
  --project-owner-public-test --fetcher playwright --headed \
  --max-pages 2 --max-details 20 --delay-min 10 --delay-max 15 \
  --max-retries 0 --timeout 30 --save-html --save-screenshot-on-error \
  --require-complete-content \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

Sau audit mốc trước ổn định, resume đúng batch ID với trần lũy kế 4/100 rồi
tối đa 12/300 (số **lần thử**, không phải số tin mới bảo đảm thành công).
Parser chỉ nhận ID card vùng main khớp `jobsResponse` công khai; mỗi dòng raw
là detail đã kiểm chứng toàn văn DOM, không lấy preview/listing hoặc tin gợi ý.
Xem [báo cáo và bằng chứng cục bộ](docs/vieclam24h_assessment_2026-09-29.md).
Artifact `data/` được Git ignore và không đi cùng bản clone repository.

Kết quả 29/09/2026: **104 ID detail raw hợp lệ**, đủ toàn văn mô tả/yêu cầu
104/104, từ 11 listing chính (277 ID discovery). Mốc 100 đã kiểm toán đạt;
mở rộng dừng ở 104 do lỗi capture DOM khi trang đang điều hướng, status/body
của lượt cuối chưa xác minh. Có một HTTP 502 trước đó, không gán thành 403.
Bản sửa capture chỉ kiểm thử offline, chưa xác nhận live; không tự resume
sau lỗi cuối hoặc coi 299 ID listing union là 299 record detail.
