# job_warehouse

Pipeline thu thập dữ liệu tuyển dụng công khai cho phân tích thị trường Việt Nam. Giai
đoạn hiện tại có adapter TopCV, CareerViet, VietnamWorks, CareerLink và Timviec365, lưu batch raw.
VietnamWorks đã tích hợp offline nhưng pilot live đầu tiên dừng ở listing render HTTP 403.
CareerViet được chọn
sau feasibility probe giới hạn; TopCV vẫn được giữ nhưng live detail có thể bị WAF chặn.
Dự án không triển khai OLTP, Airflow, dbt, Data Warehouse, dashboard hoặc LLM.

Các đường dẫn `data/` và `.runtime/` trong README/báo cáo là **artifact cục bộ**,
được `.gitignore` loại khỏi GitHub: HTML/JSONL raw, checkpoint, diagnostics, log,
ảnh challenge và backup diff. Clone repository không có các artifact này; lệnh
audit/profile/resume cần đúng batch trên máy. Git chỉ chứa code, tài liệu và fixture
kiểm thử rút gọn trong `tests/fixtures/`, không phải toàn bộ phản hồi crawl.

## Cổng an toàn và phạm vi

Quyết định nội bộ của chủ dự án: cho phép thử giới hạn trên trang tuyển dụng công khai
nếu robots và điều khoản hiện hành không cấm hoạt động dự định. Cờ
`--project-owner-public-test` chỉ ghi nhận quyết định của chủ dự án, **không phải**
sự chấp thuận của VietnamWorks hay bất kỳ chủ nguồn nào. Trong mode `sample`,
giới hạn là đúng 1 listing và tối đa 3 detail cho TopCV/CareerViet. Với VietnamWorks/CareerLink,
chủ dự án đã cho phép pilot nhỏ trong mode `sample`: tối đa 2 listing/20 detail;
mặc định vẫn là 1/3 nếu không truyền giới hạn. Probe feasibility vẫn khóa 1/3.
CareerLink và Timviec365 có mode `bounded` với giới hạn tường minh, xem bên dưới;
đây không phải quyền tự động mở rộng hay chạy lại sau challenge.
`--authorization-reference` chỉ dùng khi có
văn bản chấp thuận thật của chủ nguồn; không tự tạo mã hoặc dùng mã chủ dự án thay thế.

Crawler không đăng nhập, không vượt CAPTCHA, không dùng stealth hoặc proxy rotation.
Dừng khi điều khoản cấm, robots không cho phép, HTTP 401/403 hoặc challenge; không dùng
Playwright để vượt một phản hồi chặn. Trước khi lưu HTML, kiểm tra việc lưu được phép.

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
và mode `bounded` riêng CareerLink/Timviec365;
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

## CareerLink: batch giới hạn sau pilot (26/09/2026)

**Trạng thái hiện tại: STOPPED.** Pilot đạt 20/20 nhưng batch tăng quy mô dừng ở
55/56 detail vì HTTP 200 chứa hCaptcha thật. Đã lưu 55 record raw; chưa đạt 100/300.
Không chạy lại/resume cho tới khi điều kiện truy cập được xác nhận phù hợp.

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
Có thể bắt đầu thiết kế từ 354 tin hiện có; mẫu lịch sử chưa được xác định cục bộ.
Chưa triển khai Bronze/Silver. Báo cáo cũng có lệnh resume có điều kiện, tối đa
20 lần thử detail thêm, **chưa chạy**; không dùng mốc 100/300 để bỏ qua challenge.

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
