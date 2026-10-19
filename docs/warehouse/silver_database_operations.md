# S6 — PostgreSQL Silver

S6 đã nạp 590.693 tin và 875.580 cặp kỹ năng vào PostgreSQL, đối soát toàn bộ
với Parquet, kiểm tra nạp lại và thử khôi phục backup vào database riêng.
Báo cáo/dump thật nằm ngoài Git; các câu lệnh dưới đây dùng lại cho vận hành.
Không cần chạy lại chuẩn hóa hoặc trích kỹ năng để đọc dữ liệu Silver.

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
partial unique index. Không đánh dấu Parquet là đã nạp SQL trước khi công bố
thực sự. Những lần chạy fixture chỉ ghi nhật ký trong database thử riêng.

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

Fingerprint preflight gồm version preflight, DDL và manifest/artifact nguồn.
Fingerprint nạp bổ sung version, hash code loader/projection/preflight/migration
và DDL. Không băm mật khẩu hoặc chuỗi kết nối; không đổi nhãn nghiệp vụ để tạo
fingerprint. Các tham chiếu tuyệt đối trong hồ sơ nguồn phải còn đọc được khi
chuyển máy; không tự viết lại manifest/receipt đã chốt.

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

## Nạp và công bố

Dùng kết nối riêng, idle/autocommit theo cấu hình Bronze. Loader kiểm input
trước khi ghi DB và yêu cầu migration đúng checksum. Không dùng kết nối có
transaction đang mở hoặc chứa bảng tạm `_s6_jobs`, `_s6_skills` của ứng dụng khác.

```bash
.venv/bin/job-warehouse silver db-load \
  --jobs-run /path/to/s4-run \
  --skills-run /path/to/s5-closure-run \
  --output-dir /path/outside/repository/new-s6-load \
  --batch-size 4096
```

Không có cờ bỏ kiểm tra hoặc dùng fixture trong CLI. Output phải mới và ngoài
repo. `request.json` và run_id được lưu/in trước khi làm việc với DB;
`load.json` chỉ ghi sau khi DB hoàn tất. File input và code được kiểm lại SHA
sau staging và trước công bố. Kiểm định đợt 1 không thay thế lần kiểm này.

| Giai đoạn | Cách xử lý |
|---|---|
| Khóa writer | Session advisory lock; writer thứ hai bị từ chối, chưa tạo attempt mới |
| Nhật ký | Một attempt running được commit riêng; lưu fingerprint, hồ sơ nguồn và số dòng dự kiến |
| Staging | COPY FROM STDIN theo batch vào hai bảng tạm của kết nối; không tạo CSV, không mount Parquet vào DB |
| Kiểm tra | Schema/kiểu SQL thực tế, PK, FK và tên skill ở staging, counts, SHA; Decimal không qua float |
| Công bố | Khóa ghi hai bảng, xóa con trước cha, chép jobs rồi skill, kiểm nội dung hai chiều bằng EXCEPT ALL, cập nhật nhật ký và current trong cùng transaction |
| Kết thúc | Xóa bảng tạm, nhả khóa, ghi báo cáo cục bộ; không tạo checkpoint đến từng dòng |

Staging chỉ commit dữ liệu tạm; dữ liệu nghiệp vụ chưa bị thay. Transaction
công bố không commit theo batch. SELECT vẫn đọc được bản trước trong khi đang
thay dữ liệu. Nhiều truy vấn cần cùng phiên bản phải dùng transaction đọc có
snapshot phù hợp. Chờ khóa bảng quá 10 giây sẽ thất bại và rollback.

Đã có kiểm tra kiểu cột thực tế trước COPY và công bố: ledger đúng checksum
không đủ nếu ai đó sửa kiểu numeric bằng tay. Loader báo lỗi thay vì chấp
nhận việc PostgreSQL tự làm tròn số.

## Nạp lại và xử lý lỗi

| Kết quả | Ý nghĩa |
|---|---|
| `published` | Hai bảng và current marker được công bố đồng bộ |
| `verified_noop` | Fingerprint và toàn bộ nội dung đều khớp; không DELETE/INSERT dữ liệu nghiệp vụ, current marker giữ nguyên |
| `republished_after_content_drift` | Fingerprint cũ khớp nhưng nội dung SQL lệch; đã nạp lại từ input được chốt để khôi phục |

Lần no-op vẫn có một dòng nhật ký status=published, is_current=false để ghi
nhận việc kiểm tra thành công; `input_manifest.operation=verified_noop` và
`input_manifest.current_run_id` chỉ tới lượt công bố được dùng lại. Không coi
no-op là một bộ tin mới hoặc một lần tăng số dòng nghiệp vụ.

Lỗi trước commit: rollback toàn bộ công bố, giữ cả dữ liệu và current marker
cũ; attempt thành failed. Mất kết nối có thể để attempt running: sau khi khóa
session cũ đã nhả, writer tiếp theo mới đánh dấu abandoned_session/failed.
Không tự kết luận một running attempt đang hoạt động là bị treo.

Lỗi sau commit hoặc ghi `load.json` lỗi không được đổi attempt đã published
thành failed. Tra UUID trong `request.json` hoặc stdout bằng SQL:

```sql
SELECT run_id, status, is_current,
       input_manifest->>'operation' AS operation,
       input_manifest->>'current_run_id' AS publication_run_id,
       expected_counts, actual_counts, started_at, finished_at
FROM ops.silver_load_run
WHERE run_id = '<run_id>'::uuid;
```

Nếu published thì DB đã hoàn tất lượt đó, kể cả báo cáo trên máy chưa ghi được;
xem operation/current_run_id để phân biệt công bố với no-op. Có thể dùng thư
mục output mới để chạy lại; loader so cả nội dung và không nhân bản tin/skill.
Nếu chưa có row nhật ký thì attempt chưa được đăng ký; không suy thành công.
Báo lỗi CLI chỉ ghi loại lỗi/run_id, không in lỗi kết nối chứa secret hoặc dòng
requirements. Báo cáo thật, request, dữ liệu tạm và backup không đưa vào Git.

## Đọc lại toàn bộ để nghiệm thu

```bash
.venv/bin/job-warehouse silver db-verify \
  --jobs-run /path/to/s4-run \
  --skills-run /path/to/s5-closure-run \
  --output-dir /path/outside/repository/new-s6-verification
```

Lệnh dùng một transaction REPEATABLE READ, READ ONLY; đọc mọi trường của cả
hai bảng qua server-side cursor. Mỗi giá trị được băm SHA-256 với kiểu dữ liệu
rõ: NULL khác 0/chuỗi rỗng, mảng giữ thứ tự, Decimal chuẩn hóa về 2 chữ số chỉ
khi không mất giá trị. Chỉ số tạm chứa khóa và hash, không lưu toàn văn tin;
tự xóa khi xong. Nguồn và DB được so theo khóa rồi đối chiếu hash toàn bảng.

`verification.json` báo dòng thiếu/thừa/trùng/khác, cột khác, counts, NULL,
phân bố năm/ngành, FK, tên skill, ledger/current fingerprint và dung lượng DB.
Exit 0 khi tất cả khớp, exit 2 khi không đạt. Không sửa dữ liệu khi kiểm tra.

Truy vấn xem nhanh, không thay thế kiểm nội dung:

```sql
SELECT count(*) FROM silver.jobs;
SELECT count(*) FROM silver.job_skill_match;
SELECT count(DISTINCT job_id) FROM silver.job_skill_match;
SELECT year, count(*) FROM silver.jobs GROUP BY year ORDER BY year;
SELECT job_industry, count(*) FROM silver.jobs
GROUP BY job_industry ORDER BY count(*) DESC;
```

Kết quả nghiệm thu nguồn hiện hành: 590.693 jobs, 875.580 pairs, 380.984 tin
có skill, 209.709 tin không có cặp skill; 34 nhãn ngành. Không tính lương
trung bình sau JOIN skill trực tiếp vì có thể nhân nhiều dòng của một tin.

## Backup và thử restore

Dùng công cụ PostgreSQL 17 trong container hiện có, không cần cài pg_dump lên
host. Backup toàn database gồm Silver, ops, schema ledger và Bronze registry;
không chứa file Parquet hoặc secret. Giữ nguồn/receipt và cấu hình bí mật riêng.

Từ thư mục repo, định nghĩa hàm dùng đúng Compose warehouse:

```bash
warehouse_compose() {
  docker compose --env-file .runtime/warehouse/compose.env \
    -f infra/warehouse/compose.yaml "$@"
}
```

Dùng tên backup mới, chỉ đổi tên partial sau khi dump/list thành công:

```bash
(
  set -eC
  mkdir -p .runtime/warehouse/backups
  silver_backup_path=".runtime/warehouse/backups/silver_$(date +%Y%m%d_%H%M%S).dump"
  test ! -e "$silver_backup_path"
  warehouse_compose exec -T db sh -c \
    'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges' \
    > "$silver_backup_path.partial"
  warehouse_compose exec -T db pg_restore --list < "$silver_backup_path.partial"
  mv -n "$silver_backup_path.partial" "$silver_backup_path"
  sha256sum "$silver_backup_path"
)
```

Dump thật được giữ ngoài repository hoặc trong `.runtime/` được Git bỏ qua;
`*.dump` cũng được ignore. Không đưa dump vào commit. Lỗi dump/list thì không
gọi file partial là backup đã đạt.

Restore chỉ vào database mới, không ghi đè DB đang dùng. Ví dụ sau yêu cầu
biến `silver_backup_path` trỏ đúng dump và một tên thử chưa tồn tại:

```bash
(
  set -e
  silver_restore_db="warehouse_restore_s6_$(date +%Y%m%d_%H%M%S)"
  warehouse_compose exec -T db sh -c \
    'exec createdb -U "$POSTGRES_USER" "$1"' sh "$silver_restore_db"
  warehouse_compose exec -T db sh -c \
    'exec pg_restore -U "$POSTGRES_USER" --dbname "$1" --exit-on-error --single-transaction --no-owner --no-privileges' \
    sh "$silver_restore_db" < "$silver_backup_path"
  printf 'Restore database: %s\n' "$silver_restore_db"
)
```

Sau restore, trỏ `WAREHOUSE_DB_NAME` của kết nối kiểm tra sang DB thử và chạy
`silver db-verify` với cùng bộ S4–S5. Chỉ coi backup đạt khi full readback khớp,
đồng thời đối chiếu Bronze registry, migration ledger và lượt công bố hiện hành.
Snapshot backup chỉ chứa lịch sử ops tới thời điểm dump; một lần no-op phát
sinh sau đó ở DB chính không làm backup cũ sai dữ liệu.

Ghi lại SHA/kích thước dump, thời gian dump/restore và kết quả kiểm. Khi đã đạt,
dọn riêng database thử do lượt này tạo và trả cấu hình về DB nghiệp vụ. Giữ
backup cùng hồ sơ nghiệm thu để khôi phục/chuyển máy; dữ liệu PostgreSQL chính
vẫn nằm trên named volume của Compose.

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
  tests/warehouse/test_silver_database_loader.py \
  tests/warehouse/test_bronze_postgres.py
```

Kiểm migration lặp/đồng thời, checksum, rollback DDL, PK/FK/cận/NULL/mảng,
partial unique index lượt hiện hành và giữ ledger Bronze. Nếu thiếu cấu hình,
integration bị skip; phải báo riêng, không xem là đã kiểm trên PostgreSQL.
Dữ liệu thật, report, dump, volume và cấu hình runtime tiếp tục nằm ngoài Git.

Các test còn kiểm round-trip Decimal/NULL/mảng/Unicode, lỗi giữa COPY và giữa
lúc thay hai bảng, kết nối mất, phản hồi mất sau commit, đĩa ghi báo cáo lỗi,
counts bằng nhau nhưng nội dung lệch, hai writer và snapshot reader. Full
readback có test phát hiện khác từng trường, thiếu/thừa ID, sai tên skill,
thiếu current ledger và việc đọc một snapshot khi có writer đồng thời.
Các test fixture này tách khỏi hồ sơ nạp/restore dữ liệu thật ngoài Git.
