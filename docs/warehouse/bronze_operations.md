# Bronze lịch sử — PostgreSQL và file bất biến

S1 dùng duy nhất artifact Hugging Face đã kiểm chứng ở S0. PostgreSQL lưu
**registry metadata**, không chứa bản sao các dòng Parquet. Không gọi crawler.
Silver, Gold, Airflow, dbt và Metabase chưa triển khai trong sprint này.

## Các thư mục

```text
infra/warehouse/                    Compose, Dockerfile, env example riêng
src/job_warehouse/bronze/            validator, kết nối, registry, CLI orchestration
src/job_warehouse/bronze/migrations/ SQL có phiên bản, đi cùng package/wheel
tests/warehouse/                    test synthetic và PostgreSQL offline
docs/warehouse/                     contract và hướng dẫn vận hành
.runtime/warehouse/                 cấu hình, secret, backup local — Git bỏ qua
```

File gốc vẫn ở vị trí local đang có. Container processor đọc nó tại
`/bronze/input/history_data.parquet` qua bind mount `read_only: true`.
Processor chỉ chứa `job_warehouse`, không chứa package/dependency crawler.
Thư mục report host được mount riêng tại `/reports`. PostgreSQL có named volume
`job-warehouse-history_postgres_data`; không dùng thư mục raw làm volume database.

## Chuẩn bị local

```bash
python -m pip install -e '.[dev,warehouse]'
mkdir -p .runtime/warehouse
cp infra/warehouse/.env.example .runtime/warehouse/compose.env
chmod 600 .runtime/warehouse/compose.env
```

Sửa `compose.env`: đường dẫn tuyệt đối của Parquet **đã có**, thư mục report ngoài
repo, file password và UID/GID thực (`id -u`, `id -g`). Tạo sẵn thư mục report;
Compose không tự tạo input file/thư mục report nếu gõ sai đường dẫn.
Tạo password mới một lần, không in ra terminal và không ghi đè secret đang có:

```bash
python - <<'PY'
import os
import secrets
from pathlib import Path
path = Path('.runtime/warehouse/db_password')
with path.open('x') as stream:
    os.chmod(path, 0o600)
    stream.write(secrets.token_urlsafe(32) + '\n')
PY
```

`WAREHOUSE_DB_PASSWORD_FILE` trong `compose.env` phải trỏ tới file vừa tạo.
Không dùng `POSTGRES_HOST_AUTH_METHOD=trust`; password được cấp bằng Compose
secret. DB publish duy nhất `127.0.0.1:55432` theo mặc định. Role bootstrap của
image có quyền quản trị cho môi trường local; không coi đây là cấu hình production.
Đổi password file sau khi volume đã được init không tự đổi password trong DB.

Để rút gọn lệnh trong terminal Bash tại gốc repo:

```bash
warehouse_compose() {
  docker compose --env-file .runtime/warehouse/compose.env \
    -f infra/warehouse/compose.yaml "$@"
}
```

## Khởi động, migrate và register

```bash
warehouse_compose up -d --wait db
warehouse_compose build processor
warehouse_compose run --rm processor bronze migrate \
  --report-dir /reports/migrate_01
warehouse_compose run --rm processor bronze register \
  --input-root /bronze/input --relative-path history_data.parquet \
  --report-dir /reports/register_01
warehouse_compose run --rm processor bronze register \
  --input-root /bronze/input --relative-path history_data.parquet \
  --report-dir /reports/register_02
```

Mỗi `--report-dir` phải là thư mục mới. Chạy lại lệnh với tên report mới.
Không sửa hash/count để ép file khác qua gate; CLI register cố định revision S0.
Library validator có override phục vụ fixture tổng hợp trong test.

CLI host cũng có thể dùng với các biến môi trường `WAREHOUSE_DB_HOST`,
`WAREHOUSE_DB_PORT`, `WAREHOUSE_DB_NAME`, `WAREHOUSE_DB_USER` và
`WAREHOUSE_DB_PASSWORD_FILE` (hoặc `WAREHOUSE_DB_PASSWORD`, không đặt cả hai).
Host dùng `127.0.0.1:55432`; processor dùng `db:5432`. CLI không tự đọc `.env`
hay `.runtime/warehouse/compose.env`; file đó do Docker Compose đọc.

## Registry và gate

Migration: `001_bronze.sql`, ledger `warehouse_meta.schema_migration` gồm version,
SHA migration, timestamp. Migrate dùng transaction + advisory lock; lặp lại là
no-op, sửa migration đã apply sẽ bị từ chối. Thay đổi schema sau này dùng migration mới.

`bronze.dataset_file`:

| Cột | Kiểu | Điều kiện |
| --- | --- | --- |
| `file_id` | bigint identity | PK, không null |
| `dataset_name` | text | Không null/rỗng, tên dataset |
| `revision` | text | Không null, 40 hex lowercase |
| `artifact_path` | text | Không null/rỗng, `data.parquet` ở nguồn |
| `relative_path` | text | Không null/rỗng, không tuyệt đối/`..` |
| `sha256` | char(64) | Không null, 64 hex lowercase |
| `byte_size` | bigint | Không null, >0 |
| `row_count` | bigint | Không null, ≥0, số dòng đã decode |
| `schema_json` | jsonb | Không null, JSON object tên/kiểu/contract |
| `source_url`, `artifact_url` | text | Không null/rỗng, provenance nguồn |
| `license_id`, `attribution` | text | Không null/rỗng, giấy phép/ghi công |
| `ingested_at` | timestamptz | Không null, thời điểm nhận registry đầu tiên |
| `validation_version` | text | Không null/rỗng, `history-input-v1` |

Unique `(dataset_name, revision, artifact_path)`. SHA giống và metadata bất biến
giống: no-op, không đổi `ingested_at`; đổi input root hoặc alias file không thêm
row. SHA hoặc metadata khác: conflict, rollback, không ghi đè registry tốt.
`relative_path` là vị trí ghi nhận đầu tiên; input root là cấu hình từng môi trường.
Nếu chuyển vị trí vật lý sau này cần kế hoạch locator/migration riêng; S1 không di chuyển file.

Trước register: kiểm SHA, đủ 14 tên/kiểu theo contract; đọc tất cả batch/cột đến
EOF, Arrow full validation; kiểm count/footer, ID không null/dương/duy nhất và
year 2022–2026. Kiểm SHA sau scan và ngay trước commit. Không clean text, không
loại trùng nội dung và không tạo ngày đăng giả. Null text vẫn được giữ nguyên.

Insert dùng `ON CONFLICT DO NOTHING` rồi đối chiếu metadata trong transaction.
Hai lượt đồng thời vẫn chỉ một row. Exception trước COMMIT rollback insert;
sequence có thể có khoảng trống do retry/rollback, không dùng `file_id` để đếm tin.
API yêu cầu connection autocommit đang idle để kết quả trả về là đã commit thực sự.

`run.json` có UUID, thời điểm UTC, trạng thái, metadata/kết quả hoặc lỗi an toàn;
không log password/DSN/toàn văn. Exit 0 khi operation đã thành công, exit 2 khi
validation/DB/file/report lỗi. Nếu process bị kill, report có thể còn `running`:
đó là chưa có kết luận. Nếu DB commit nhưng report cuối ghi lỗi, registry có thể
đã có row; CLI báo rõ, chạy lại với report mới sẽ đối soát thay vì append thêm.
Bind mount chỉ đọc bảo vệ khỏi container; host vẫn có thể sửa file. Hash kiểm tra
tại các mốc, không thay thế quản lý bất biến file ở cấp máy chủ.

Kiểm tra sau hai lượt:

```bash
warehouse_compose exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT file_id, dataset_name, revision, row_count, byte_size, ingested_at FROM bronze.dataset_file;"'
```

Kỳ vọng 1 row, `row_count=606878`, `byte_size=293171544`. Đây là số dòng trong
file registry tham chiếu, **không phải 606.878 row PostgreSQL Bronze**.

## Dừng, khởi động lại và backup

```bash
warehouse_compose stop db
warehouse_compose up -d --wait db
```

`down` giữ named volume; không chạy `down -v` hoặc xóa volume đang có dữ liệu.
Backup database không bao gồm Parquet và file secret; giữ chúng riêng cùng checksum.

```bash
warehouse_compose exec -T db sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > .runtime/warehouse/bronze_backup.dump
```

Chỉ coi backup thành công khi exit 0; dùng tên mới cho mỗi bản backup.
Restore thử vào database **mới**, không ghi đè database warehouse:

```bash
warehouse_compose exec -T db sh -c \
  'createdb -U "$POSTGRES_USER" warehouse_restore_fixture'
warehouse_compose exec -T db sh -c \
  'pg_restore -U "$POSTGRES_USER" -d warehouse_restore_fixture --exit-on-error' \
  < .runtime/warehouse/bronze_backup.dump
warehouse_compose exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d warehouse_restore_fixture -c "SELECT count(*), max(row_count) FROM bronze.dataset_file;"'
```

Nếu database restore đã tồn tại, dừng và chọn tên mới. Không restore tiếp một
bản lỗi hoặc chạy lệnh drop đối với database chính.

## Test offline

```bash
.venv/bin/pytest -q -m 'not live'
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
git diff --check
```

Test DB được skip nếu chưa khai báo môi trường test. Nghiệm thu S1 phải chạy
thật PostgreSQL integration với các biến `WAREHOUSE_TEST_DB_HOST/PORT/NAME/USER`
và `WAREHOUSE_TEST_DB_PASSWORD_FILE`; host trỏ PostgreSQL local chuyên dùng cho test.
Test tự tạo database `warehouse_test_<UUID>` rồi chỉ drop database đó. Không
truncate database warehouse. Ví dụ với server local của Compose:

```bash
WAREHOUSE_TEST_DB_HOST=127.0.0.1 \
WAREHOUSE_TEST_DB_PORT=55432 \
WAREHOUSE_TEST_DB_NAME=job_warehouse \
WAREHOUSE_TEST_DB_USER=warehouse \
WAREHOUSE_TEST_DB_PASSWORD_FILE=.runtime/warehouse/db_password \
.venv/bin/pytest -q -m 'not live'
```

Test dùng Parquet tổng hợp, không yêu cầu file thật hoặc truy cập website.
Tham khảo [Psycopg transaction](https://www.psycopg.org/psycopg3/docs/basic/transactions.html),
[PostgreSQL INSERT/ON CONFLICT](https://www.postgresql.org/docs/17/sql-insert.html),
[Compose services](https://docs.docker.com/reference/compose-file/services/)
và [PostgreSQL official image](https://hub.docker.com/_/postgres).
