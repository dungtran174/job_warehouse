# job_warehouse

Pipeline thu thập dữ liệu tuyển dụng công khai cho phân tích thị trường Việt Nam. Giai
đoạn hiện tại có adapter TopCV và CareerViet cùng lớp Raw/Bronze. CareerViet được chọn
sau feasibility probe giới hạn; TopCV vẫn được giữ nhưng live detail có thể bị WAF chặn.
Dự án không triển khai OLTP, Airflow, dbt, Data Warehouse, dashboard hoặc LLM.

## Cổng an toàn và phạm vi

Không chạy crawler nếu chưa có chấp thuận bằng văn bản phù hợp từ chủ nguồn. Mọi lệnh
live bắt buộc có `--authorization-reference`; đây chỉ là mã tham chiếu không bí mật, không
phải token hay cookie. Crawler không đăng nhập, không vượt CAPTCHA, không dùng stealth
hoặc proxy rotation và dừng khi robots, HTTP 401/403 hoặc challenge không cho phép tiếp
tục.

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
- `crawlers/topcv.py`, `crawlers/careerviet.py` và các `parsers/<source>_*` chứa logic
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

Chỉ thực hiện sau khi có quyền bằng văn bản và sau một kiểm tra kỹ thuật giới hạn 1
listing + 1 detail để xác nhận HTML công khai chứa dữ liệu cần thiết:

```bash
export JOB_CRAWLER_USER_AGENT='job-warehouse-crawler/0.1 (+public-research; contact=data@example.org)'
python -m job_crawler.cli crawl topcv \
  --mode sample \
  --fetcher auto \
  --max-pages 2 \
  --max-details 20 \
  --authorization-reference APPROVAL-REFERENCE
```

`--save-html` là tùy chọn và mặc định tắt. Chỉ bật khi phạm vi chấp thuận cho phép lưu
HTML nguồn.

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
và chỉ chuyển một chiều sang Chromium chuẩn khi listing trả 403 hoặc không có job hợp
lệ. `--headed` chỉ áp dụng cho Playwright; không có stealth, proxy rotation hay thay đổi
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

```bash
python scripts/probe_job_sources.py --source careerviet \
  --max-listing-pages 1 --max-details 3 --fetcher auto \
  --save-html --save-screenshot-on-error
```

Các source hợp lệ là `careerviet`, `jobsgo`, `vieclam24h` và `vietnamworks`. Artifact
được ghi dưới `data/diagnostics/source_feasibility/` và bị loại khỏi Git cùng toàn bộ
dữ liệu runtime.

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
