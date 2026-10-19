# job_warehouse

Đồ án kho dữ liệu tuyển dụng dùng bộ lịch sử Hugging Face
`tinixai/vietnamese-job-descriptions`, độc lập với crawler cũ.
**Đã hoàn thành Bronze–Silver (S0–S6)**; Gold, dashboard và Airflow chưa triển khai.

| Phần | Kết quả đã chốt |
|---|---|
| Bronze | Parquet nguồn bất biến: 606.878 dòng, 14 cột; PostgreSQL lưu registry file |
| Silver core | 606.857 tin; tách 21 dòng không có title hữu ích vào quarantine |
| Ngành, địa điểm | Ánh xạ có lưu vết về nguồn; 34 nhãn ngành đạt ≥500, giữ tên tỉnh/thành theo nguồn |
| Lương | Hai cận VNĐ/tháng, tỷ giá và ngoại lệ đã duyệt lưu trong hồ sơ xử lý |
| Kỹ năng | Từ điển và quy tắc trên requirements; 875.580 cặp cho 380.984 tin |
| PostgreSQL Silver | 590.693 tin phân tích và 875.580 cặp; đã đối soát, kiểm nạp lại và backup/restore |

Tin không trích được skill vẫn giữ trong Silver. Những dòng không thuộc tập
phân tích vẫn có trong đầu ra đầy đủ để đối soát Bronze. Kết quả kiểm định
bằng AI được ghi rõ phạm vi; không gọi là nhãn xác nhận của con người hoặc
độ chính xác toàn bộ dữ liệu.

## Tìm đúng tài liệu

| Cần làm | Tài liệu |
|---|---|
| Kiểm nguồn và hồ sơ S0 | [Hợp đồng dữ liệu lịch sử](docs/warehouse/history_data_contract.md) |
| Khởi động, đăng ký Bronze, cấu hình DB | [Vận hành Bronze](docs/warehouse/bronze_operations.md) |
| Hiểu làm sạch trường chung S2 | [Silver core](docs/warehouse/silver_core_contract.md) |
| Địa điểm và classifier chức năng lịch sử | [Enrichment](docs/warehouse/silver_enrichment_contract.md) |
| Ghép nhãn ngành và lọc ≥500 hiện hành | [Ánh xạ ngành nguồn](docs/warehouse/source_industry_operations.md) |
| Quy tắc lương, tỷ giá và ngoại lệ | [Lương S4](docs/warehouse/silver_salary_contract.md) |
| Từ điển, các đợt trích skill và lưu vết review | [Kỹ năng S5](docs/warehouse/skills_contract.md) |
| Schema, nạp, đọc lại, backup và restore Silver | [PostgreSQL S6](docs/warehouse/silver_database_operations.md) |
| Crawler cũ, batch và hướng dẫn resume | [Kiến trúc crawler](docs/architecture_data.md) |

Kế hoạch, báo cáo Word, bàn giao ngữ cảnh và dữ liệu thật nằm ngoài Git,
ở thư mục lân cận `../job_warehouse_design/`. Mở `README.md` tại đó để tìm
bản hiện hành; kế hoạch tập trung trong `tai_lieu/ke_hoach/`.
Các file `*_latest_output.json` chỉ tới phiên bản đã chốt.
Không tự sửa manifest/receipt hoặc thay đường dẫn đầu ra đã được khóa SHA.

## Cấu trúc code

```text
src/
  job_warehouse/             # Pipeline lịch sử Hugging Face
    cli.py                   # Lệnh job-warehouse
    history/                 # Hợp đồng nguồn, hash và khảo sát S0
    bronze/                  # Registry PostgreSQL và migration S1
    silver/                  # Làm sạch trường chung S2
      enrichment/            # Ngành và địa điểm S3
      salary/                # Chuẩn hóa lương S4
      database/              # Migration, nạp và đối soát S6
    skills/                  # Trích kỹ năng, review và ghép các đợt S5
  job_crawler/               # Crawler cũ, không được warehouse gọi
infra/warehouse/             # Docker Compose riêng cho warehouse
scripts/                     # Công cụ kiểm tra crawler cũ
tests/                      # Test offline và integration riêng
docs/warehouse/             # Hợp đồng và hướng dẫn theo từng phần
```

Trong `skills/`, các thư mục `mappings*` là từ điển/alias/chính sách được
đóng gói cùng ứng dụng, mỗi bộ có phạm vi và phiên bản riêng. Đây là tài
nguyên chạy pipeline, không phải dữ liệu tạm. Snapshot kiểm chứng và đầu ra
Parquet thật được giữ ngoài repo.

## Cài đặt và kiểm tra

Python ≥3.11. Dùng môi trường hiện có hoặc tạo mới:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,warehouse]'
.venv/bin/job-warehouse --help
```

Các lệnh tạo đầu ra phải dùng thư mục mới ngoài repo; xem cú pháp và điều
kiện từng lệnh trong tài liệu tương ứng. Chạy kiểm tra offline:

```bash
.venv/bin/pytest -q -m 'not live'
.venv/bin/ruff format --check .
.venv/bin/ruff check .
MYPYPATH=src .venv/bin/mypy src
git diff --check
```

Test PostgreSQL chỉ chạy khi có cấu hình DB thử; thiếu cấu hình sẽ skip.
Không tự bật Docker hoặc crawl live chỉ để chạy bộ test offline.

## Dữ liệu và vận hành

- Không commit raw/HTML, Parquet, Excel, dump, secrets, môi trường hay báo cáo sinh tự động.
  `data/`, `.runtime/`, `.venv/` và các cache được Git bỏ qua.
- Giữ nguồn bất biến, lưu mapping và quyết định xử lý để đối chiếu Bronze.
  Không ghi đè output đã chốt; tạo run mới và kiểm SHA trước khi nhận.
- `silver.jobs` và `silver.job_skill_match` là hai bảng nghiệp vụ;
  `ops.silver_load_run` là nhật ký kỹ thuật. Chi tiết DDL và vận hành ở tài liệu S6.
- Code và dữ liệu crawler cũ giữ riêng. Không tự chạy live, xóa batch hoặc
  đổi parser/schema cũ; xem `AGENTS.md` và tài liệu kiến trúc trước khi thao tác.
- Hai nguồn crawler chính dùng HTTP. Bộ Chromium tải trong `.runtime/`
  đã được dọn; nếu cần adapter trình duyệt dự phòng, cài lại bằng:

```bash
PLAYWRIGHT_BROWSERS_PATH=.runtime/ms-playwright .venv/bin/python -m playwright install chromium
```
