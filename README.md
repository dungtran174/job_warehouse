# job_warehouse

Đồ án kho dữ liệu hiện chỉ dùng **lịch sử Hugging Face**. S0 có profiler
offline; S1 có PostgreSQL Bronze registry; S2 có Silver core offline;
S3 có enrichment và nhập ánh xạ địa điểm offline; trục ngành hiện dùng nhãn
nguồn, alias và ghép cha theo quyết định chủ dự án. CLI ngành xuất Silver
đầy đủ và tập phân tích theo ngưỡng ≥500, giữ lưu vết về Bronze.
S5 đã kiểm định offline bản thí điểm trích kỹ năng từ requirements cho ba
ngành; kết quả Parquet và hồ sơ nghiệm thu lưu riêng ngoài repository.
Silver database publish/Gold/dashboard/Airflow chưa triển khai.
CLI `silver skills-apply-review` hỗ trợ nhập các claim kỹ năng đã rà soát
trong bundle có lưu vết, tạo output mới và giữ nguyên các tin ngoài tập review.
Code warehouse ở `src/job_warehouse/`, test ở `tests/warehouse/`,
[hợp đồng và cách chạy](docs/warehouse/history_data_contract.md) ở `docs/warehouse/`.

Code crawler trước đây ở `src/job_crawler/` và các batch CareerViet/CareerLink
được giữ riêng; warehouse không dùng chúng làm input hay gọi crawler.
[Kiến trúc crawler và dữ liệu cũ](docs/architecture_data.md) ghi hợp đồng,
batch dự phòng, bài học và cách khôi phục báo cáo lịch sử của phần web.

## Warehouse lịch sử — S0

```bash
.venv/bin/python -m pip install -e '.[dev,warehouse]'
.venv/bin/job-warehouse profile \
  --input /path/to/history_data.parquet \
  --report-dir /path/outside/repository/s0-profile
```

Input đọc đủ file ở chế độ chỉ đọc; CLI mặc định kiểm SHA/revision contract và
606.878 dòng. Report directory phải mới, lưu ngoài repository. Profiler báo
null/trùng/phân bố raw, chưa chuẩn hóa ngành hoặc loại nhãn ít mẫu. Nhãn cùng
ngữ nghĩa cần gộp trước khi áp ngưỡng 500/1.000 ở Silver. Không commit report
thật, Parquet hoặc kế hoạch ngoài repo. Chi tiết ở hợp đồng warehouse liên kết trên.

## Warehouse lịch sử — S1 Bronze

Compose/Dockerfile riêng tại `infra/warehouse/`, code registry và migration tại
`src/job_warehouse/bronze/`. PostgreSQL chỉ lưu metadata file; processor đọc
Parquet gốc bằng bind mount chỉ đọc. Cấu hình và secret nằm trong `.runtime/warehouse/`
được Git bỏ qua, report thật nằm ngoài repository.

Xem [hướng dẫn khởi động, register, kiểm thử và backup](docs/warehouse/bronze_operations.md).
CLI: `job-warehouse bronze migrate` và `job-warehouse bronze register`.
Cùng artifact đăng ký lại là no-op; cùng revision/artifact khác SHA bị từ chối.

## Warehouse lịch sử — S2 Silver core

Normalizer và extractor học vấn/kinh nghiệm từ requirements ở
`src/job_warehouse/silver/`, độc lập với crawler và PostgreSQL. Các giá trị suy
ra lưu riêng kèm evidence; ưu tiên không thành yêu cầu bắt buộc, câu phức tạp
chờ review. Tách title thiếu/Không, giữ raw và đối soát core+quarantine.

```bash
.venv/bin/job-warehouse silver core \
  --input /path/to/history_data.parquet \
  --output-dir /path/outside/repository/s2-core-run
```

CLI giữ SHA/N pin, output phải mới và ngoài repository. Chưa parse
salary/location/industry, loại trùng, trích skill hay publish vào database.
S2 gán cách viết thống nhất cho `position_label_clean`,
`education_label_clean`, `job_type_label_clean`, giữ nguyên 14 cột nguồn.
Đếm nhãn Silver bằng các cột này; không gộp Cử nhân với Đại học, không bỏ
Remote hoặc chọn một thành phần của nhãn ghép. Mapping và số lượng thực tế
được xuất trong `source_label_mapping.csv` và `core_quality_report.json`.
Từ v6, `company_name_clean` cũng thống nhất các tên chỉ khác hoa/thường:
chọn cách viết sạch phổ biến nhất trên core, hòa thì chọn theo thứ tự chữ.
Không ghép tên viết tắt/pháp nhân/chi nhánh khác nhau; `company_match_key`
giữ nguyên. Xem `company_name_mapping.csv` để đối chiếu tên gốc và tên chung.
Xem [hợp đồng và cách kiểm định core](docs/warehouse/silver_core_contract.md).

## Warehouse lịch sử — S4 lương

Parser offline ở `src/job_warehouse/silver/salary/`; CLI `silver salary`
đọc core S2 và mapping S3 đã kiểm SHA. Hai cận lương là VNĐ/tháng; giữ
ngoại lệ do chủ dự án duyệt, tỷ giá theo năm và hệ số kỳ trong hồ sơ chạy.
Xuất `jobs.parquet`/`jobs_analysis.parquet` với tên cột nghiệp vụ thống nhất,
`salary_enrichment.parquet` và CSV mapping để đối soát. Input không đổi;
các chuỗi chưa xác định vẫn giữ tin và lý do, chưa publish PostgreSQL.
Xem [quy tắc, tỷ giá, schema và cách chạy S4](docs/warehouse/silver_salary_contract.md).

## Warehouse lịch sử — S5 kỹ năng (thí điểm ba ngành)

`silver skills-prepare` khảo sát requirements, chia mẫu tune/holdout theo hash;
`silver skills` xuất cặp job–skill, bằng chứng và trạng thái riêng. Phạm vi đầu
là Công nghệ thông tin, Kế toán / Kiểm toán và Marketing. Chỉ đọc requirements,
dùng từ điển/alias và rule offline, không gọi AI ở runtime. Bản v8 đã đạt
kiểm định cặp tin–skill trên 300 văn bản mới do hai AI đánh giá độc lập:
precision ≥95%, recall ≥80% từng ngành trong từ điển 96 khái niệm.
Đây là kiểm định mẫu bằng AI; dữ liệu review giữ riêng. Các gói mở rộng
kiểm định theo từng nhãn, chưa publish database. CLI luôn tạo candidate; hồ sơ nghiệm
thu bổ sung và dữ liệu thật nằm ngoài Git.
Xem [chính sách, đầu ra và lệnh S5](docs/warehouse/skills_contract.md).
Bản thí điểm được đóng băng theo phiên bản: giữ kết quả đã nhận và tách các
đề xuất chưa nghiệm thu để xử lý sau. Bộ 96 kỹ năng được kiểm định tự động;
catalogue bổ sung qua review chỉ có hiệu lực với các claim ID/hash đã duyệt,
không đồng nghĩa toàn catalogue được trích đồng đều trên mọi tin. Hồ sơ chốt,
Parquet, từ điển và danh sách hoãn xử lý lưu ngoài Git. Xem mục chốt phiên bản
trong hợp đồng S5.
Mở rộng theo đợt dùng `silver skills-batch-prepare`,
`silver skills --batch sales_customer_service` và `silver skills-batch-merge`. Gói bán hàng/CSKH có
phạm vi, mẫu và gate riêng; kết quả ngoài đợt được giữ nguyên. Dữ liệu thực tế
và tình trạng nghiệm thu từng run lưu ngoài repository; lệnh chạy tạo candidate.
Riêng Bất động sản dùng `silver skills --batch real_estate`, có từ điển và
rule ngữ cảnh riêng để giữ nguyên kết quả bán hàng/CSKH đã chốt. Bộ mẫu mới
70 văn bản do hai AI đánh giá độc lập đạt gate; hồ sơ, sai sót còn lại và
bản Silver offline đã ghép được lưu ngoài Git, chưa publish database.
Bộ mở rộng nằm riêng ở `skills/mappings_expanded/`; CLI `silver skills-expand`
chạy đồng đều ba ngành và `silver skills-expand-merge` đối chiếu với các review
đã duyệt. Đây là bản candidate mới, không kế thừa điểm kiểm định của bộ 96.

Gói nhân sự/tài chính/pháp lý chạy bằng `silver skills --batch hr_finance_legal`.
Từ đợt 02, chủ dự án chốt cách lấy từ khóa rõ, bỏ qua claim chưa rõ và giữ mọi
tin; không đặt mục tiêu recall hoặc gọi điểm development là kiểm định độc lập.
Các vòng AI cũ giữ nguyên kết quả. Snapshot và quyết định nghiệm thu nằm ngoài
Git; chưa publish PostgreSQL.

Gói kho vận/vận tải chạy bằng `silver skills --batch logistics_transport`,
dùng từ khóa chuyên môn và mapping bằng/chứng chỉ lái xe đã chốt. Không suy
vận hành logistics từ sales logistics hoặc từ việc chỉ sở hữu phương tiện.
Tin không có từ khóa rõ vẫn giữ nguyên; kết quả mới phải đối soát trước khi nhận.

Gói kỹ thuật/sản xuất dùng `silver skills --batch engineering_production` cho
năm nhãn nguồn, với alias CAD/PLC/CNC, đọc bản vẽ, quản lý sản xuất và chất
lượng. Chỉ nhận bằng chứng rõ trong requirements; không suy từ ngành học,
chứng nhận của doanh nghiệp hoặc tên công cụ sang nghiệp vụ vận hành.

Gói xây dựng/thiết kế/dự án dùng `silver skills --batch construction_design_projects`
cho bốn nhãn nguồn. Từ điển gồm công cụ thiết kế, BIM, bóc tách, dự toán và
nghiệp vụ thi công/dự án có bằng chứng rõ; không suy từ ngành học hay nhãn ngành.

## Warehouse lịch sử — S3 enrichment

**Trục ngành hiện hành:** dùng `job_industry`, không dùng `occupation_primary`
hoặc cờ `scope_500` của classifier chức năng dưới đây. Sau chặng địa điểm,
chạy `silver industry` để áp dụng policy cuối và lọc tập phân tích:

```bash
job-warehouse silver industry \
  --bronze /path/to/history_data.parquet \
  --base-run /path/outside/repo/verified-location-run \
  --output-dir /path/outside/repo/industry-run --threshold 500
```

Giữ Giáo dục - Đào tạo và Chăm sóc khách hàng riêng; tư vấn CSKH vẫn ghép
vào CSKH. Giữ cả hai nhóm Chưa xác định/Nghề nghiệp khác nếu đạt ngưỡng.
Xem [quyết định, cột, lưu vết và cách chạy lại](docs/warehouse/source_industry_operations.md).
Classifier chức năng và các báo cáo lịch sử dưới đây giữ để đối chiếu,
không là trục phân tích chính hiện tại.

Code, taxonomy và mapping ở `src/job_warehouse/silver/enrichment/`, có version
riêng với core S2. CLI `job-warehouse silver enrich` đọc core cùng manifest,
giữ một dòng mỗi record_key, lưu nghề theo chức năng, domain riêng, đủ labels
địa điểm và scope ≥500/≥1.000. Không xóa nhóm ít mẫu khỏi Silver.
Taxonomy có 23 nhóm mang tên bao quát theo chức năng; công việc vệ sinh ở
mọi cơ sở thuộc Dịch vụ vệ sinh, gồm cả vệ sinh buồng phòng khách sạn.
Xem [contract, cách chạy và kiểm định S3](docs/warehouse/silver_enrichment_contract.md).
Đầu ra thật ở ngoài Git; coverage và các nhóm ít mẫu còn giới hạn, được ghi
trong báo cáo kiểm định. Chưa publish Silver vào database/dashboard.
Chính sách Q32–Q37:
giữ các tỉnh được đề cập, ưu tiên một địa chỉ đầy đủ khi nhãn bao ngoài mâu
thuẫn, dùng tỉnh đã rõ và ghi cờ khi danh sách chưa đầy đủ. Mỗi version địa
điểm mới cần đối soát toàn file và mẫu kiểm định mới trước khi nhận gate cũ.
Tin nhắc cả Việt Nam và nước ngoài giữ các tỉnh Việt Nam, quốc gia lưu riêng
kèm cờ; không loại tỉnh đã rõ vì có thêm nơi nước ngoài.
Kiểm định địa điểm vòng 6 khớp 251/268 (93,66%), chưa đạt 95%. Location v9
qua vòng 7 tổng thể 309/322 (95,96%), nhưng nhóm tên cơ sở chỉ 20/30;
điểm cũ giữ nguyên. Location v11/pipeline v14 đã đối soát đủ core; vòng 9
khớp 292/300 (97,33%), nhưng nhiều tỉnh chỉ 40/45 (88,89%) và còn lỗi cần sửa.
Q41 không lấy tỉnh từ tên cơ sở lặp; Q42 đọc quan hệ tên mới/cũ nguồn ghi rõ;
Q43 tránh tên đường Hậu Giang trong danh sách đường. Giữ tên cũ trong bằng
chứng; không tự quy đổi tin khác. Q44 đã chốt ưu tiên tỉnh chung rõ của các
địa chỉ bên trong khi nhãn bao ngoài lặp mâu thuẫn; bản tiếp theo cần kiểm định mới.

Location v12/pipeline v15 đã chạy và audit đủ 606.857 dòng, còn 17.792
unmapped. Q44 và quan hệ địa chỉ cũ/mới đã có code/test; reference KCN Quế Võ
được bổ sung. Vòng AI mù 10 đã hoàn tất: khớp 312/320 (97,5%) tổng thể;
nhiều tỉnh 65/70 và quan hệ địa chỉ cũ 3/4, còn bất đồng cần xử lý.
Nhãn/score v12 giữ nguyên. Location v13/pipeline v16 sửa tám ca bất đồng,
gồm Q45 đã chốt về địa chỉ cũ lặp khớp rõ cùng nơi. Run-v20 đã audit đủ
606.857 dòng, còn 17.768 unmapped. Vòng AI thật 11 khớp 310/318 tuple
(97,48%), tập tỉnh 312/318; nhiều địa điểm 62/70 còn yếu. Q45 có 32 câu
thử tổng hợp khớp 32/32, báo riêng; không thay mẫu thật.

Code hiện tại là location v14/pipeline v19, sửa bảy ca rõ của vòng11 và
Q46 về tên nhà máy có địa chỉ cùng lô/KCN ghi tỉnh rõ. Theo điều chỉnh Q47,
chỉ trích/chuẩn hóa tên tỉnh/thành theo nguồn, giữ tên cũ, chưa thêm cột hoặc
quy đổi toàn bộ sang địa giới sau sáp nhập. Run-v22 đã audit đủ606.857 dòng,
còn17.759 unmapped. Vòng AI mù12 khớp310/318tuple(97,48%) và313/318status;
nhóm nhiều địa điểm67/70(95,71%). Đạt gate tổng thể của mẫu, còn8bất đồng,
nhóm tên cơ sở chỉ0/1 và rule cùng lô/KCN chỉ1/1, chưa đủ bảo đảm riêng.
Không gọi đồng thuận AI là accuracy toànfile; domains/coverage vẫn có giới hạn.
Chưa publish Silver DB.

## Nhập ánh xạ địa điểm do chủ dự án cung cấp

`silver apply-location-map` đọc hai sheet trong XLSX, ghép theo địa chỉ raw
với các dòng unmapped của run S3 đã kiểm SHA; số lần xuất hiện và ID ví dụ
phải khớp. Sheet chưa xác định được gán “Chưa xác định”. Output mới có cột
`location` là tên tỉnh/thành (nhiều tỉnh nối bằng `; `), mã tỉnh vẫn lưu trong
`location_places`; giữ tên cũ, không quy đổi địa giới sau sáp nhập.

```bash
job-warehouse silver apply-location-map \
  --base-run /path/outside/repo/s3-run \
  --mapping-xlsx /path/owner-mapping.xlsx \
  --output-dir /path/outside/repo/new-mapped-run
```

Excel và CSV mapping thật được lưu ngoài Git, giữ SHA/row/provenance trong
manifest. Đây là nhập nhãn chủ dự án, chưa phải kiểm định địa lý độc lập;
không sửa Bronze/S2, nghề/năm hay tin đã xác định tỉnh. Chưa publish DB.

## Cài đặt crawler cũ và kiểm tra offline

Python >=3.11. Dùng môi trường đang có hoặc tạo môi trường mới:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Hai nguồn chính dùng HTTP, không cần Chrome/đường dẫn browser để chạy chúng.
Dependency Playwright còn giữ để tương thích adapter/test nguồn dự phòng.
Repo không tự đọc `.env`; tham khảo `.env.example` nếu export cấu hình.

```bash
.venv/bin/pytest -q -m 'not live'
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
git diff --check
```

## Quy tắc vận hành

- Chỉ tin công khai; người vận hành kiểm tra điều khoản/phạm vi lưu dữ liệu trước
  live. Engine đọc robots đầu mỗi invocation và kiểm tra từng URL; không truy
  cập URL bị cấm. Robots không tải được thì dừng, quyền chưa xác định.
- Một luồng, UA minh bạch, CareerLink đợt mở rộng nghỉ10–15s, retries=0.
  Dừng 401/403/429 hoặc CAPTCHA/challenge kể cả HTTP200, giữ bằng chứng/checkpoint.
  Không tự resume sau chặn, đổi browser/IP/UA, đăng nhập, stealth/proxy/CAPTCHA solver.
- `--project-owner-public-test` ghi quyết định chủ dự án, không phải chấp thuận
  nguồn. `--authorization-reference` chỉ dùng văn bản nguồn thật, không tự đặt mã.
  HTTP200/thành công kỹ thuật không chứng minh quyền khai thác/tái công bố mọi quy mô.
- HTML nguyên trang chứa giao diện/mã/nội dung biên tập của website; tin do nhà
  tuyển dụng đăng và dữ liệu công bố trên dashboard cần đánh giá quyền riêng.
  Không coi điều khoản sao chép HTML là lệnh cấm tuyệt đối đọc tin công khai.
- Listing chỉ discovery; JSONL chỉ ghi detail đủ title/company/toàn văn mô tả/yêu
  cầu từ detail. Không bù bằng preview/gợi ý; trường tùy chọn thiếu giữ null.
- Không tự chạy live/full snapshot khi chưa có yêu cầu rõ; full cần `--confirm-full`.
  Cờ/giới hạn CLI không thay thế điều kiện nguồn hiện hành.

## CareerLink: resume cùng batch tới mục tiêu 300

Xác minh offline 30/09/2026: **156 raw / 156 ID**, 159 detail attempts, 156 success,
3 lỗi gồm 1 hCaptcha cũ và 2 lượt hCaptcha mới cùng ID `3635311`;
8 listing/400 ID, còn 244 detail pending. Batch dừng `access_blocked`.
ID từng challenge3626178 đã completed ở lượt khỏe29/09, không tải lại.
Start URL phải giữ đúng manifest cũ.

**Không chạy lại lệnh dưới đây khi nguồn còn trả challenge.** Chỉ cân nhắc một
lượt resume thông thường sau khi kiểm tra điều khoản/robots/phạm vi lưu dữ liệu
hiện hành và có cơ sở truy cập bình thường đã khôi phục. ID `3635311` vẫn
pending và sẽ được thử đầu tiên; nếu lại là hCaptcha/403/429 thì dừng, không
bỏ qua hoặc lặp thử. Không cần Chrome; chạy một tiến trình từ thư mục gốc:

```bash
cd /home/dung/project/job_warehouse
.venv/bin/job-crawler crawl careerlink --mode bounded \
  --start-url 'https://www.careerlink.vn/vieclam/tim-kiem-viec-lam' \
  --output-dir data/raw --project-owner-public-test --fetcher http \
  --resume --resume-batch-id 20260926T160422Z-c39d6a20 \
  --max-pages 8 --max-details 330 --target-records 300 \
  --delay-min 10 --delay-max 15 --max-retries 0 --timeout 30 \
  --require-complete-content \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

- `max-pages=8`: tối đa8 listing attempts **toàn batch**; đã dùng hết8.
- `max-details=330`: tối đa330 detail attempts **toàn batch** (đã159, còn tối
  đa171), không phải số tin mới. Lượt lỗi cũng được tính.
- `target-records=300`: dừng khi có tổng300 ID raw duy nhất, cần thêm144
  dòng hợp lệ; số lượt còn lại không bảo đảm lấy đủ.

Tám listing đã phát hiện400 ID nhưng chỉ156 dòng detail hợp lệ; ID listing không
phải raw. Challenge giữ ID pending để đánh giá, không chạy lại ngay hoặc dùng
công cụ khác để né chặn. Nếu hết pending, lặp listing, mapping conflict,
robots/challenge hoặc vượt tỷ lệ lỗi thì dừng, không cố đủ300 bằng retry.

Audit offline đối chiếu HTML khớp156/156 raw cũ; hai response challenge không có
detail. Không lặp command tự động; nếu thiếu dữ liệu/trần phải audit trước khi đổi cấu hình.

Không có `--save-html`, CareerLink vẫn parse HTML trong RAM nhưng không lưu body
nguyên trang của response HTTP 200 không bị challenge. `http/*.json` phiên bản 2
ghi URL/ID yêu cầu, URL/ID cuối, canonical URL/ID, status, content type, cờ
challenge, kích thước và SHA-256 body; `raw_html_path=null` ở record mới.
Response lỗi/challenge vẫn giữ body để kiểm tra điểm dừng. `manifest.run_settings`
ghi `success_body_storage=metadata_only` cho lượt mới; lượt cũ thiếu trường
này được hiểu là `full`, raw/HTML cũ không đổi. Audit mới kiểm tra ID/status,
metadata và content hash của record, **không thể** đối chiếu lại DOM, toàn văn,
đầu/cuối mô tả/yêu cầu hay tính lại SHA-256 body nếu không lưu body. Tắt lưu
HTML không tự cấp quyền lưu/tái công bố nội dung tin hoặc dữ liệu dashboard.
Response HTTP 200 mà parser không nhận ra detail cũng chỉ còn metadata và
`errors.jsonl`; muốn điều tra DOM sau đó phải có bản lưu hợp lệ từ nguồn khác.

## Xem tiến độ và resume sau ngắt

Terminal thứ hai, chạy từng lệnh khi muốn xem; không cần watch/tail liên tục:

```bash
wc -l data/raw/careerlink/snapshot_date=2026-09-26/batch_id=20260926T160422Z-c39d6a20/jobs.jsonl
.venv/bin/python scripts/batch_status.py \
  data/raw/careerlink/snapshot_date=2026-09-26/batch_id=20260926T160422Z-c39d6a20
```

Status đọc JSONL/manifest/checkpoint **read-only**: raw/unique/duplicate,
attempts/success/failure, queue pending/processing, lỗi cuối và cấu hình lượt
mới. Khi đang ghi các file có thể lệch tạm thời; wc không chứng minh toàn văn.
Sau khi tiến trình kết thúc, audit offline:

```bash
.venv/bin/python scripts/audit_careerlink_batch.py \
  data/raw/careerlink/snapshot_date=2026-09-26/batch_id=20260926T160422Z-c39d6a20
```

Đạt mục tiêu: unique raw=300, duplicate=0, `termination_reason=target_records`.
Batch có3 lỗi lũy kế nên `completed_with_errors`/exit2 vẫn có thể là kết thúc tại
mục tiêu trong tương lai; xem reason/raw/lỗi mới, không suy exit2 là chặn mới. `max_details`
là hết attempts, không chứng minh đủ300. `target_unmet_no_pending_details`
là không còn detail trong discovery. `stopped`, `access_blocked`,
`browser_challenge`, `robots_*` thì dừng, không tự chạy lại ngay.

Máy/terminal ngắt vì lý do khác chặn truy cập: chắc chắn tiến trình cũ đã chết
rồi mới resume đúng batch ID. Processing được phục hồi, completed không tải/ghi
lại; slot ngắt vẫn tính lũy kế. Nếu gặp challenge/401/403/429 thì dừng, không
coi đó là ngắt máy thông thường để chạy lại ngay.
Resume giữ snapshot26/09, record mới có crawled_at thực; không đổi156 tin cũ
thành dữ liệu mới ngày chạy. Cập nhật hằng ngày sau này tạo batch mới.

## Dữ liệu và nguồn dự phòng

```text
data/raw/<source>/snapshot_date=YYYY-MM-DD/batch_id=<id>/
  jobs.jsonl / errors.jsonl / manifest.json / checkpoint.sqlite3
  html/*.html.gz / http/*  # HTML tùy chế độ; URL/status/metadata cục bộ
```

CareerViet299, CareerLink156, VietnamWorks295 và Việc Làm24h104 giữ nguyên
trong repo. Timviec365299 đã chuyển sang archive ngoài repo, được kiểm tra
checksum/toàn văn; xem cách khôi phục trong tài liệu kiến trúc. Hai nguồn
browser là dự phòng có dữ liệu thật, không xóa như
"crawl lỗi"; code/audit/test còn phụ thuộc nên giữ. Raw/HTML/checkpoint/
diagnostics/.runtime/.venv không vào Git, clone không có artifact cục bộ.
Báo cáo từng lượt đã lưu cục bộ/Git revision; xem
[kiến trúc và bài học](docs/architecture_data.md).
