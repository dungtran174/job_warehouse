# Hợp đồng dữ liệu lịch sử Hugging Face — S0

Version: `history-input-v1`. Pipeline warehouse chỉ dùng Parquet lịch sử;
không import adapter/parser/fetcher/checkpoint của crawler.

## Tổ chức code và trạng thái

```text
src/job_warehouse/
  cli.py                    # profile, bronze, silver core
  silver/                   # core/inference offline S2, riêng với crawler
  history/
    contract.py             # nguồn, revision, schema, điều kiện kiểm tra
    identity.py             # SHA256, row key, fingerprint nội dung
    profile.py              # đọc đủ file và xuất báo cáo local
tests/warehouse/             # fixture tổng hợp, không phụ thuộc dữ liệu thật
docs/warehouse/              # hợp đồng và hướng dẫn warehouse

src/job_crawler/             # code web trước đây, giữ riêng và nguyên trạng
```

S0 đã có profiler và data contract; S1 bổ sung PostgreSQL registry theo
[hướng dẫn Bronze](bronze_operations.md). S2 có [Silver core offline](silver_core_contract.md)
và extractor học vấn/kinh nghiệm từ requirements, lưu inferred riêng. Chưa có
mapping nghề/địa điểm, salary parser, skill extractor, Silver database publish,
Gold, Airflow hoặc Metabase. Kế hoạch triển khai chi
tiết, báo cáo thật và các thiết kế giữ ngoài repository.

## Nguồn và bất biến

- Dataset: [tinixai/vietnamese-job-descriptions](https://huggingface.co/datasets/tinixai/vietnamese-job-descriptions).
- Revision: `679c3a17347ff6ce769d9bf510c122a087493cf6`.
- Artifact: `data.parquet`, 293.171.544 bytes.
- SHA256: `4d5e11b58490edc40900386986de71e844cd9f0f3a5fc714418747f66462f834`.
- Dòng dự kiến của revision: 606.878; kiểm thực đọc tới EOF, không chỉ dùng footer/card.
- License ghi nhận từ nguồn: CC BY-NC 4.0; attribution: TiniX AI/Tinixai,
  Vietnamese Job Descriptions. Giữ revision/link/ghi công, không commit raw.
- Không tải nguồn, đăng nhập hay gọi website; đường dẫn input do người vận hành
  cung cấp. File được mở chỉ đọc và kiểm SHA trước/sau.

## Schema 14 cột

Tên cột phải đủ, không dư/lặp. Chấp nhận thứ tự cột vật lý khác nhau, nhưng hash
luôn dùng thứ tự contract. Hai trường số phải int64; text string/large_string.
Không ép kiểu hoặc sửa giá trị nguồn trong profiler.

| Cột | Kiểu input | Ý nghĩa và điều kiện |
| --- | --- | --- |
| `id` | int64 | ID dataset, không null, >0, duy nhất trong file; không phải ID website |
| `job_title` | string | Chức danh; null/blank báo riêng, không fallback mô tả |
| `company_name` | string | Tên nguồn; khác tên chưa chứng minh khác pháp nhân |
| `salary` | string | Giá trị raw, chưa suy VND/tháng hoặc đổi thành số |
| `location` | string | Nhãn/địa chỉ/đa địa điểm raw, chưa lấy tỉnh đầu |
| `job_type` | string | Loại việc và có thể có remote/theo ca; chưa gộp nghĩa |
| `job_industry` | string | Nhãn nguồn, có thể ghép hoặc khác cách viết; chưa là taxonomy |
| `experience_level` | string | Số/khoảng/cận raw; chưa biến thành năm chính xác |
| `education_level` | string | `Không` mơ hồ, không tự gán no_requirement |
| `job_position` | string | Chức vụ/level raw; chưa suy từ title |
| `job_description` | string | Toàn văn nguồn, không dùng thay requirements để trích skill |
| `benefits` | string | Toàn văn nguồn; thiếu không có nghĩa không có phúc lợi |
| `requirements` | string | Nguồn duy nhất cho extractor ở Silver sau này |
| `year` | int64 | Không null; 2022–2026 cho revision này; không có ngày/tháng |

Trường text nullable được giữ nguyên. Profile đếm null vật lý, chuỗi blank,
literals placeholder và cardinality riêng. Không thay `Không`, `Đang cập nhật`,
`Chưa xác định` bằng null/0. `0 VND` vẫn là text; chưa coi đó là lương thật.

## Identity, trùng và scope

- `source_row_index`: từ 0 theo thứ tự vật lý trước sort/filter; chia batch không
  reset index.
- `record_key`: SHA256 của UTF-8 `file_sha256 + ':' + str(source_row_index)`.
  SHA file là 64 hex lowercase; không gắn website hoặc URL tin giả.
- Fingerprint: SHA256 của JSON array **13 cột ngoài `id`, có `year`**, theo
  thứ tự contract, `ensure_ascii=False`, separators `(',', ':')`. Không trim,
  bỏ dấu, Unicode normalize hoặc thay null trong phép so này.
- S0 giữ **tất cả dòng**, xuất nhóm candidate và mọi row reference. Hai ID khác
  có cùng fingerprint không tự được gọi là một vacancy đã xác minh.
- Chính sách đầu vào: `retain_and_flag`; số nội dung khác biệt được báo riêng,
  không thay cho số dòng nguồn. Muốn collapse trong Silver phải giữ một đại
  diện deterministic, đối chiếu đủ 13 giá trị, lưu quyết định từng dòng và ghi
  rõ KPI là bản ghi nội dung sau xử lý trùng. Không xóa Bronze.
- Title/company giống riêng lẻ không đủ loại; khác năm vẫn giữ riêng.
- Ngưỡng nhóm nghề mặc định ≥500, đối chiếu ≥1.000, **chỉ áp sau ánh xạ ngữ
  nghĩa và policy trùng đã chọn**. Nhãn hiếm cùng nghề phải được gộp trước đếm.
  Profiler chưa áp threshold hoặc quyết định loại ngành.
- Skill chỉ từ requirements; symbol/negation/evidence/taxonomy cần kiểm định
  ở sprint sau. S0 không tạo skill từ title hoặc description.

## Chạy offline và báo cáo

```bash
python -m pip install -e '.[dev,warehouse]'
job-warehouse profile \
  --input /path/to/history_data.parquet \
  --report-dir /path/outside/repository/s0-profile
```

Report directory phải mới; không ghi đè report tốt. CLI mặc định kiểm SHA và N
của revision cố định. `--expected-sha256` và `--expected-rows` cho phép kiểm
fixture local; không dùng chúng để coi file khác là revision mới được nguồn
xác nhận. `profile_history()` cấp thư viện cho phép không đặt expected values
để đo fixture; báo cáo luôn ghi rõ expected values có/không.
`source.pinned_artifact_verified` chỉ true khi SHA và N thực sự khớp artifact
đã ghi nhận; fixture đạt validation theo tham số riêng vẫn không mang cờ này.

Các file báo cáo được publish cùng một thư mục sau khi ghi xong:

| File local | Nội dung |
| --- | --- |
| `profile.json` | N/SHA/schema/null/sentinel/cardinality/ID/year, validation, scope chưa áp, mẫu review tối đa 100 nhóm |
| `scalar_value_counts.csv` | Các giá trị raw salary/type/industry/experience/education/position/year và tần suất; value encode JSON để phân biệt null/chuỗi |
| `industry_year_counts.csv` | Nhãn ngành raw × year; chưa gộp nghề hoặc loại ít mẫu |
| `duplicate_candidates.jsonl` | Fingerprint/năm/row_index/ID của mọi nhóm trùng; không chứa toàn văn |

Exit 0: đủ file, expected values phù hợp, ID/year đạt contract, SHA trước/sau
khớp. Exit 2: lỗi file/hash/schema/output hoặc validation không đạt. Lỗi row
count/ID/year vẫn xuất report `passed=false`, không sửa/loại dòng. Input đổi
trong lúc đọc, lỗi đọc hoặc mismatch SHA/schema không publish report mới.
Report cũ không tự trở thành kết quả của lượt lỗi; dùng thư mục mới mỗi lần.

Đọc batch bằng [PyArrow ParquetFile](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html),
một luồng. Không giữ toàn bộ dataframe; các tập distinct và fingerprint vẫn
tăng RAM theo cardinality. Long text distinct dùng SHA256 raw UTF-8 để tránh
giữ toàn văn; báo `distinct_method`, không giả đó là phép so full text.
Đo thời gian/RAM khi nghiệm thu full file. Mẫu review chọn tối đa 50 nhóm lớn
nhất rồi nhóm còn lại theo fingerprint đến 100; không phải mẫu ngẫu nhiên.

## Kiểm thử và Git

```bash
.venv/bin/pytest -q -m 'not live'
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
git diff --check
```

Warehouse tests sinh Parquet tổng hợp ở `tmp_path`, không commit file thật.
Nếu chỉ cài extras crawler/dev, warehouse tests được skip có lý do; nghiệm
thu S0 phải cài extra warehouse và chạy chúng thực sự. Mypy kiểm cả package
warehouse và crawler; thiếu typing upstream của PyArrow được giới hạn override.

File code/test/contract có thể stage riêng sau review. Report, annotation,
Parquet, raw/checkpoint, môi trường và kế hoạch ngoài repo không stage. S0 không
tự commit/push, không tạo database hoặc gọi các crawler.
