# Đặc tả crawler TopCV cho dự án `job_warehouse`

## 1. Mục tiêu

Xây dựng crawler TopCV có thể chạy cục bộ, kiểm thử được và dễ đưa vào Airflow sau này. Dữ liệu được lưu ở lớp Raw/Bronze để phục vụ hệ thống phân tích xu hướng thị trường tuyển dụng theo thời gian.

Luồng dài hạn dự kiến:

```text
TopCV/VietnamWorks/nguồn khác
→ Raw/Bronze
→ Silver chuẩn hóa
→ Gold/Data Warehouse
→ Dashboard
→ LLM/NL2SQL (tùy chọn về sau)
```

Phạm vi nhiệm vụ này chỉ gồm crawler TopCV và Raw/Bronze. Chưa triển khai OLTP nghiệp vụ, Airflow, dbt, Data Warehouse, dashboard hoặc LLM.

Trang bắt đầu mặc định:

```text
https://www.topcv.vn/tim-viec-lam-moi-nhat?type_keyword=1&sba=1
```

Con số việc làm hiển thị trên giao diện thay đổi theo thời điểm. Không hard-code số lượng. Nếu lấy được, lưu `source_reported_total` tách biệt với số URL thực tế phát hiện.

## 2. Việc cần làm trước khi viết code

1. Đọc `AGENTS.md`, `README.md`, `pyproject.toml`, các file dependency và cấu hình nếu tồn tại.
2. Kiểm tra cấu trúc repository và `git status`.
3. Xác định convention hiện có; nếu repo trống thì tạo scaffold Python 3.11+ tối giản.
4. Kiểm tra `robots.txt`, điều khoản công khai và khả năng truy cập các trang không cần đăng nhập.
5. Kiểm tra HTML thực tế để quyết định dùng HTTP parser hay trình duyệt tự động.
6. Nêu kế hoạch ngắn trước khi triển khai.

## 3. Nguyên tắc truy cập an toàn

- Chỉ truy cập trang tuyển dụng công khai.
- Không đăng nhập và không sử dụng cookie/tài khoản cá nhân.
- Không thu thập CV, dữ liệu ứng viên hoặc thông tin riêng tư không cần thiết.
- Không vượt CAPTCHA, không dùng stealth plugin, không xoay proxy/IP để né giới hạn.
- Không khai thác endpoint nội bộ hoặc endpoint được bảo vệ.
- Nếu gặp chặn truy cập hoặc hạn chế pháp lý, dừng và báo cáo.

Cấu hình mặc định:

- concurrency: `1`;
- độ trễ ngẫu nhiên: khoảng `1.5–3.0` giây;
- timeout có thể cấu hình;
- retry tối đa 3 lần cho lỗi tạm thời;
- exponential backoff;
- tôn trọng HTTP 429 và `Retry-After`;
- User-Agent minh bạch, có thể cấu hình.

## 4. Các chế độ chạy

### 4.1 Sample

- Tối đa 2 trang danh sách.
- Tối đa 20 trang chi tiết.
- Đây là chế độ duy nhất được phép chạy tự động trong nhiệm vụ đầu tiên.

Ví dụ CLI mong muốn:

```bash
python -m job_crawler.cli crawl topcv \
  --mode sample \
  --max-pages 2 \
  --max-details 20
```

### 4.2 Full snapshot

- Dùng để lấy toàn bộ tin công khai có thể truy cập tại thời điểm chạy.
- Chỉ triển khai code và tài liệu trong nhiệm vụ đầu tiên; không tự chạy.
- Bắt buộc có cờ xác nhận riêng, ví dụ `--confirm-full`.
- Hỗ trợ checkpoint và `--resume`.

```bash
python -m job_crawler.cli crawl topcv \
  --mode full-snapshot \
  --resume \
  --confirm-full
```

### 4.3 Incremental

Chuẩn bị interface để sau này:

- phát hiện ID mới;
- tải lại tin có khả năng thay đổi;
- so sánh `content_hash`;
- lưu snapshot theo ngày;
- ghi nhận tin hết hạn hoặc không còn xuất hiện.

Chưa cần hoàn thiện toàn bộ incremental trong nhiệm vụ đầu tiên.

## 5. Kiến trúc đa nguồn

Không viết toàn bộ logic thành một script. Tối thiểu phải có:

- base/interface crawler;
- adapter crawler TopCV;
- parser trang danh sách;
- parser trang chi tiết;
- data model;
- URL canonicalization;
- Raw storage;
- manifest và error log;
- checkpoint/resume;
- CLI;
- logging có context.

Nếu repository trống, có thể dùng cấu trúc:

```text
src/job_crawler/
├── cli.py
├── config.py
├── models.py
├── crawlers/
│   ├── base.py
│   └── topcv.py
├── parsers/
│   ├── topcv_listing.py
│   └── topcv_detail.py
├── storage/
│   └── jsonl.py
└── utils/
    ├── url.py
    └── hash.py

tests/
├── fixtures/topcv/
├── test_topcv_listing_parser.py
├── test_topcv_detail_parser.py
├── test_url.py
└── test_hash.py
```

Khi thêm VietnamWorks, chỉ cần adapter/parser mới, không sửa toàn bộ pipeline. Raw được phép có trường riêng theo nguồn; các trường không tồn tại được phép `null`.

## 6. Lựa chọn công nghệ tải trang

Kiểm tra trang thật trước:

1. Nếu dữ liệu nằm trong HTML trả về, ưu tiên `httpx` hoặc `requests` kết hợp `BeautifulSoup`/`selectolax`.
2. Nếu dữ liệu bắt buộc render JavaScript, dùng Playwright.
3. Không cài đồng thời Selenium và Playwright nếu không cần.
4. Không dùng selector DOM tuyệt đối dễ gãy.

Ưu tiên nguồn dữ liệu theo thứ tự:

1. JSON-LD hoặc structured data công khai.
2. Heading/label có ý nghĩa ngữ nghĩa.
3. Thuộc tính ổn định như `data-*`.
4. CSS selector tương đối.

Parser phải chịu được trường tùy chọn bị thiếu, layout tin thường/tin nổi bật khác nhau và thứ tự section thay đổi.

## 7. URL, ID và phân trang

URL chi tiết thường có dạng:

```text
https://www.topcv.vn/viec-lam/<slug>/<job_id>.html?...tracking...
```

Yêu cầu:

- lấy `source_job_id` ổn định từ URL hoặc dữ liệu trang;
- `source_name` luôn là `topcv`;
- khóa nguồn là `(source_name, source_job_id)`;
- bỏ query tracking như `ta_source`, `ref`, `sr_id` và tham số marketing;
- lưu cả `source_url` và `canonical_url`;
- không dùng slug làm ID;
- deduplicate trước khi tải detail;
- không đưa “việc làm liên quan” vào hàng đợi chính.

Điều kiện dừng phân trang:

- không còn trang tiếp theo;
- trang không có ID mới;
- fingerprint trang bị lặp;
- đạt `max_pages`;
- phát hiện vòng lặp URL;
- gặp chặn truy cập không thể xử lý hợp lệ.

## 8. Trường dữ liệu cần thu thập

Mọi trường tùy chọn được phép `null`; thiếu trường tùy chọn không làm hỏng toàn bộ record.

### Metadata nguồn

- `source_name`
- `source_job_id`
- `source_url`
- `canonical_url`
- `listing_url`
- `source_reported_total`
- `crawled_at`
- `snapshot_date`
- `batch_id`
- `schema_version`
- `parser_version`
- `raw_html_path`
- `content_hash`

Quy ước: `crawled_at` là ISO 8601 UTC; `snapshot_date` theo `Asia/Ho_Chi_Minh`.

### Thông tin công việc

- `job_title`
- `salary_raw`
- `location_raw`
- `detailed_work_address`
- `experience_raw`
- `application_deadline_raw`
- `application_deadline`
- `job_level`
- `education_level`
- `vacancies_raw`
- `vacancies`
- `work_model`
- `job_type`
- `profession_tags`
- `category_tags`
- `specialization_tags`
- `requirement_tags`

### Nội dung chi tiết

- `job_description`
- `candidate_requirements`
- `income_text`
- `benefits`
- `working_time`
- `application_method`

Giữ text sạch và, nếu hữu ích, danh sách bullet. Không gộp sai các section riêng thành một chuỗi duy nhất.

### Công ty

- `company_name`
- `company_id` nếu công khai và ổn định
- `company_url`
- `company_size`
- `company_address`
- `company_industry`

### Thời gian đăng/cập nhật

- `posted_at_raw`
- `posted_at_estimated`
- `posted_date_precision`

Với giá trị tương đối như “4 ngày trước”, luôn giữ raw; timestamp chuyển đổi phải được đánh dấu là ước tính và ghi precision.

## 9. Nguyên tắc Raw/Bronze

Crawler chỉ chuẩn hóa kỹ thuật:

- canonical URL;
- Unicode/khoảng trắng;
- timestamp;
- kiểu dữ liệu cơ bản;
- khóa nguồn;
- `content_hash`.

Không chuẩn hóa nghiệp vụ sâu ở bước này. Phải giữ các giá trị như:

```json
{
  "salary_raw": "8 - 20 triệu",
  "location_raw": "Hồ Chí Minh",
  "experience_raw": "Không yêu cầu"
}
```

Việc tách lương min/max, chuẩn hóa tỉnh thành, taxonomy ngành nghề và kỹ năng sẽ thực hiện ở Silver.

## 10. Content hash

Tạo hash ổn định từ những trường nội dung quan trọng như tiêu đề, công ty, lương, địa điểm, mô tả, yêu cầu, quyền lợi và hạn ứng tuyển.

Không đưa vào hash:

- `crawled_at`;
- `batch_id`;
- đường dẫn file tạm;
- tracking query;
- thứ tự dictionary.

Cùng nội dung phải sinh cùng hash; nội dung thay đổi phải sinh hash khác.

## 11. Lưu dữ liệu

Ưu tiên JSON Lines và tùy chọn lưu HTML nén:

```text
data/raw/topcv/
└── snapshot_date=YYYY-MM-DD/
    └── batch_id=<batch-id>/
        ├── jobs.jsonl
        ├── manifest.json
        ├── errors.jsonl
        ├── checkpoint.json
        └── html/
            └── <source_job_id>.html.gz
```

Không commit dữ liệu crawl lớn vào Git; cập nhật `.gitignore` phù hợp.

`manifest.json` tối thiểu có:

- source, batch, mode, start URL;
- start/finish/status;
- số lượng nguồn công bố;
- số trang listing request/thành công;
- URL phát hiện và ID duy nhất;
- detail thành công/thất bại;
- duplicate bỏ qua;
- record đã ghi và record thiếu trường bắt buộc;
- cấu hình rate limit;
- schema/parser version;
- lý do kết thúc.

`errors.jsonl` lưu URL, job ID, stage, loại lỗi, HTTP status, message, attempt, timestamp và khả năng retry. Không ghi secret.

## 12. Checkpoint và idempotency

Full snapshot phải:

- biết ID đã hoàn tất và URL chưa xử lý;
- tiếp tục được sau khi dừng;
- không ghi trùng record đã hoàn tất;
- cập nhật checkpoint an toàn theo lô nhỏ;
- hạn chế hỏng file nếu tiến trình bị ngắt.

Có thể dùng SQLite làm state/checkpoint kỹ thuật. Nếu dùng, ghi rõ đây không phải OLTP nghiệp vụ.

## 13. Data model và validation

Dùng dataclass hoặc Pydantic phù hợp convention. Trường tùy chọn nullable, list có kiểu rõ ràng, serialization ổn định và có version.

Trường bắt buộc tối thiểu:

- `source_name`
- `source_job_id`
- `canonical_url`
- `job_title`
- `crawled_at`
- `snapshot_date`
- `content_hash`

Record thiếu trường bắt buộc phải vào error/quarantine và được thống kê; không âm thầm bỏ qua.

## 14. Cấu hình và logging

Tách khỏi code các giá trị:

- start URL;
- output directory;
- timeout;
- delay min/max;
- retry;
- max pages/details;
- User-Agent;
- lưu HTML;
- timezone;
- log level.

Tạo `.env.example` nếu sử dụng biến môi trường; không cần secret.

Logging cần có `batch_id`, mode, stage, page, job ID, URL, status, attempt và thời gian request. Không in toàn bộ HTML ra console.

## 15. Kiểm thử

Bổ sung test cho:

1. Tách job ID từ URL.
2. Canonical URL và bỏ tracking query.
3. Parser listing.
4. Parser detail.
5. Detail thiếu trường tùy chọn.
6. Các layout khác nhau nếu có fixture.
7. Content hash ổn định.
8. Deduplication theo khóa nguồn.
9. Serialization model.
10. Điều kiện dừng khi không có ID mới.

Unit test dùng fixture HTML đã rút gọn, không phụ thuộc live website. Live test phải đánh dấu riêng và không chạy mặc định.

## 16. README

README phải hướng dẫn:

- mục tiêu và kiến trúc;
- cài môi trường;
- chạy formatter/linter/test;
- chạy sample;
- vị trí output;
- resume;
- câu lệnh full snapshot kèm cảnh báo;
- cách thêm adapter nguồn mới;
- giới hạn hiện tại và nguyên tắc rate limit.

## 17. Thứ tự triển khai

1. Khảo sát repo và website hợp lệ.
2. Tạo scaffold và cấu hình dependency.
3. Viết model và URL utilities.
4. Viết listing parser.
5. Viết detail parser.
6. Viết storage, manifest, error và checkpoint.
7. Viết crawler orchestration và CLI.
8. Viết fixture và unit test.
9. Chạy formatter/linter/test.
10. Chạy sample tối đa 2 listing pages và 20 details.
11. Kiểm tra output và báo cáo.

## 18. Tiêu chí hoàn thành sample

- Chạy được bằng một câu lệnh rõ ràng.
- Phát hiện detail URL và canonical hóa đúng.
- Không có ID trùng trong output.
- Tạo `jobs.jsonl`, `manifest.json`, `errors.jsonl` và checkpoint.
- Record có đủ trường bắt buộc.
- Parser không chết khi thiếu trường tùy chọn.
- Unit test vượt qua.
- Không gửi request quá nhanh hoặc vượt cơ chế chống bot.

## 19. Báo cáo cuối nhiệm vụ

Báo cáo:

1. File đã tạo/thay đổi.
2. Kiến trúc và dependency đã chọn.
3. Lệnh cài đặt/chạy.
4. Kết quả formatter/linter/test.
5. Kết quả sample: listing pages, URL, ID duy nhất, detail thành công/thất bại.
6. Tỷ lệ thiếu các trường chính và vị trí output.
7. Selector dễ thay đổi và giới hạn hiện tại.
8. Vấn đề robots/điều khoản/chống bot nếu có.
9. Ước lượng thời gian/dung lượng full snapshot dựa trên sample.
10. Việc cần làm trước khi chạy toàn bộ.

Kết thúc bằng việc hỏi người dùng có đồng ý chạy full snapshot hay không.

## 20. Những việc không làm ở nhiệm vụ đầu tiên

- Không chạy toàn bộ hàng chục nghìn tin.
- Không triển khai OLTP nghiệp vụ.
- Không triển khai PostgreSQL chỉ để lưu trạng thái crawl nếu chưa cần.
- Không triển khai Airflow, dbt, ClickHouse, Data Warehouse hoặc dashboard.
- Không ghép dataset lịch sử Hugging Face.
- Không triển khai NLP/LLM.
- Không crawl VietnamWorks.
- Không vượt CAPTCHA hoặc cơ chế chặn.
