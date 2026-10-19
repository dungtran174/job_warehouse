# S6 — PostgreSQL Silver

Đợt 1 triển khai kiểm tra đầu vào và migration. Chưa có loader, chưa nạp dữ liệu
nghiệp vụ hoặc tạo bản công bố Silver trong PostgreSQL. Các bước nạp/giao dịch,
đối soát SQL với Parquet và backup/restore thuộc đợt 2–3.

## Đầu vào và thiết kế

Dùng `jobs_analysis.parquet` sau S4 và bản S5 đã đóng trạng thái còn lại.
Không chạy lại chuẩn hóa, trích skill hoặc loại thêm tin. Mặc định kiểm bộ
đầu vào đã chốt: 590.693 jobs, 875.580 cặp, 380.984 tin có skill, 34 nhãn ngành.
Tin không có skill vẫn giữ trong jobs. Bản khác phải được đánh giá và cập nhật
hợp đồng trước khi nạp, không sửa count để vượt kiểm tra.

`silver.jobs` có 14 cột theo Parquet; `job_type` là `varchar`, `location` là
`varchar[]`; lương `numeric(18,2)` VNĐ/tháng, kinh nghiệm `numeric(6,2)` theo năm.
Giữ NULL, chuỗi, thứ tự mảng và tên địa phương nguồn. Preflight từ chối số
kinh nghiệm bị làm tròn khi chuyển từ Decimal 18,6 sang 6,2.

`silver.job_skill_match` có `(job_id, skill_code)` làm PK và FK về jobs;
`skill_name` giữ tên đã chốt. Bằng chứng vẫn ở artifact, không thêm vào SQL.

`ops.silver_load_run` lưu từng attempt, trạng thái running/published/failed,
fingerprint, manifest, số dòng, thời gian và lượt hiện hành. Cho phép nhiều
attempt cùng fingerprint, chỉ một lượt published có is_current=true bằng
partial unique index. Đợt 1 tạo cấu trúc; chưa tạo attempt giả hoặc đánh dấu
Parquet là đã nạp SQL.

## Kiểm tra đầu vào (không kết nối DB)

```bash
.venv/bin/job-warehouse silver db-preflight \
  --jobs-run /path/to/s4-run \
  --skills-run /path/to/s5-closure-run \
  --output-dir /path/outside/repository/new-s6-preflight
```

Output phải mới và ngoài repo. `preflight.json` chứa SHA, fingerprint, số dòng,
phân bố ngành/NULL/trạng thái và kết luận chưa công bố DB. Không chứa toàn văn
requirements hoặc secret. Không tự chọn hai latest pointer hoặc cập nhật chúng.

Kiểm manifest/acceptance S4, receipt/checksums/gate S5, schema cả 14 cột và ba
artifact S5, cùng SHA đầu vào S4. Đọc toàn bộ jobs, cặp và trạng thái để kiểm
ID trùng, FK, tên chuẩn skill, hash requirements, số cặp từng tin, phạm vi năm,
NULL, mảng, cận và khả năng chuyển kiểu SQL chính xác. Evidence giữ nguyên;
kiểm SHA cùng hồ sơ audit đã khóa, không chấm lại ngữ nghĩa trong S6.

Chỉ số SQLite nằm trong RAM, dùng kiểm trùng/đối soát, đóng khi kết thúc;
không tạo file dữ liệu trung gian. Sau đọc kiểm SHA lần nữa. Bộ đầu vào có
thể đổi sau preflight nên loader đợt 2 phải kiểm lại trước công bố; report
đợt 1 không phải giấy phép bỏ qua kiểm tra đầu vào về sau.

Fingerprint đợt 1 gồm version preflight, DDL và manifest/artifact nguồn,
không phụ thuộc đường dẫn máy. Đợt 2 bổ sung version/hash loader trước khi
triển khai quyết định no-op. Chưa có cơ chế no-op nạp dữ liệu trong đợt 1.

## Migration

Dùng cùng cấu hình `WAREHOUSE_DB_HOST/PORT/NAME/USER` và
`WAREHOUSE_DB_PASSWORD_FILE` như Bronze; không ghi password vào lệnh hoặc Git.
Xem [vận hành Bronze](bronze_operations.md) để khởi động Compose riêng.

```bash
.venv/bin/job-warehouse silver db-migrate
```

Lệnh tạo hai bảng Silver và bảng ops, không đọc/nạp dữ liệu thật. Migration
`002_silver` dùng chung ledger `warehouse_meta.schema_migration` và advisory
lock với Bronze; tất cả DDL và ledger ghi trong một transaction. Chạy lại
cùng checksum là no-op; checksum khác bị từ chối. Không sửa migration đã áp
dụng; thay đổi tiếp theo cần migration mới. Schema Silver có sẵn nhưng thiếu
ledger bị từ chối thay vì tự nhận là tương thích. Không đổi bảng Bronze.

DB chỉ là kiểu lưu trữ: PostgreSQL tự có thể làm tròn số khi INSERT trực tiếp;
preflight/loader chịu trách nhiệm từ chối chuyển kiểu mất chính xác. Không
bỏ qua preflight để tự nạp bằng INSERT.

## Kiểm thử

```bash
.venv/bin/pytest -q
.venv/bin/ruff format --check .
.venv/bin/ruff check .
MYPYPATH=src .venv/bin/mypy src
git diff --check
```

Để bật integration, cấu hình `WAREHOUSE_TEST_DB_HOST/PORT/NAME/USER` và
`WAREHOUSE_TEST_DB_PASSWORD_FILE`; tài khoản test cần quyền tạo database.
Tests chỉ tạo/drop database ngẫu nhiên của riêng mình, không xóa bảng DB
nghiệp vụ. Không đặt cấu hình test bằng tài khoản triển khai không cần thiết.

```bash
.venv/bin/pytest -q tests/warehouse/test_silver_database_postgres.py \
  tests/warehouse/test_bronze_postgres.py
```

Kiểm migration lặp/đồng thời, checksum, rollback DDL, PK/FK/cận/NULL/mảng,
partial unique index lượt hiện hành và giữ ledger Bronze. Nếu thiếu cấu hình,
integration bị skip; phải báo riêng, không xem là đã kiểm trên PostgreSQL.
Dữ liệu thật, report, dump, volume và cấu hình runtime tiếp tục nằm ngoài Git.
