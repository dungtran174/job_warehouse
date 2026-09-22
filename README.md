# job_warehouse

Pipeline thu thập dữ liệu tuyển dụng công khai cho phân tích thị trường Việt Nam. Giai
đoạn hiện tại chỉ có adapter TopCV và lớp Raw/Bronze. Dự án không triển khai OLTP,
Airflow, dbt, Data Warehouse, dashboard hoặc LLM.

## Cổng an toàn và phạm vi

Không chạy crawler nếu chưa có chấp thuận bằng văn bản phù hợp từ chủ nguồn. Mọi lệnh
live bắt buộc có `--authorization-reference`; đây chỉ là mã tham chiếu không bí mật, không
phải token hay cookie. Crawler không đăng nhập, không vượt CAPTCHA, không dùng stealth
hoặc proxy rotation và dừng khi robots, HTTP 401/403 hoặc challenge không cho phép tiếp
tục.

Sample bị khóa cứng ở tối đa 2 URL listing và 20 URL detail duy nhất. Full snapshot không
được chạy nếu chưa có xác nhận riêng trong cuộc trao đổi hiện tại; CLI còn bắt buộc
`--confirm-full`.

## Kiến trúc

```text
CLI -> source-independent engine -> fetcher
                         |-> source adapter/parsers
                         |-> JSONL + manifest + error log
                         `-> SQLite technical checkpoint
```

- `crawlers/base.py` định nghĩa hợp đồng adapter dùng chung.
- `crawlers/topcv.py` và `parsers/topcv_*` chứa logic riêng của TopCV.
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

`--fetcher` nhận `http`, `playwright` hoặc `auto` (mặc định). `auto` bắt đầu bằng HTTP
và chỉ chuyển một chiều sang Chromium chuẩn khi listing trả 403 hoặc không có job hợp
lệ. `--headed` chỉ áp dụng cho Playwright; không có stealth, proxy rotation hay thay đổi
fingerprint. Khi phát hiện CAPTCHA/challenge/access denied, crawler lưu bằng chứng nếu
được yêu cầu bằng `--save-screenshot-on-error`, rồi dừng batch ngay.

Output:

```text
data/raw/topcv/snapshot_date=YYYY-MM-DD/batch_id=<id>/
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

`--resume` chọn batch chưa hoàn tất mới nhất của đúng nguồn và mode, đối chiếu checkpoint
với ID đã có trong `jobs.jsonl` để tránh ghi trùng.

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

## Giới hạn hiện tại

- Selector listing/detail đã được xác nhận bằng sample công khai giới hạn và được khóa
  bằng fixture HTML rút gọn. Giao diện nguồn vẫn có thể thay đổi nên manifest thống kê
  field thiếu cho từng batch.
- Chromium chuẩn được hỗ trợ khi HTTP không đủ. Việc một listing tải được không đảm bảo
  mọi detail sẽ tải được; Cloudflare/WAF có thể chặn giữa batch và crawler sẽ dừng, không
  thử vượt chặn.
- Incremental mới có nền tảng ID, content hash và snapshot; chưa theo dõi đầy đủ trạng
  thái tin hết hạn.
- Full snapshot chỉ có guard/checkpoint được kiểm thử offline, chưa được chạy thực tế.
