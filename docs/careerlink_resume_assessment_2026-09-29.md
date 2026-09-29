# CareerLink: kiểm tra lại và resume có giới hạn — 29/09/2026

## Kết quả của lượt mới

**Thêm 20 detail thật; batch cũ tăng từ 55 lên 75 dòng / 75 ID duy nhất.**
Không coi 55 tin cũ là kết quả mới. Dừng ở giới hạn 20 lượt detail mới,
không mở rộng đến 100 hoặc 299 trong lượt này.

| Chỉ số | Lượt 29/09/2026 |
| --- | ---: |
| Request HTTP thật mới | 23 |
| Request robots | 2, đều HTTP 200 |
| Listing thử / thành công | 1 / 1 |
| ID chính duy nhất trên listing mới | 50 |
| Listing tải lại trong resume | 0 |
| Detail mới thử / truy cập đầy đủ / record hợp lệ | 20 / 20 / 20 |
| Dòng JSONL ghi thêm | 20 |
| Tổng dòng / ID duy nhất trong batch sau resume | 75 / 75 |
| ID trùng, ID trong 55 tin cũ bị tải lại | 0 / 0 |
| Mô tả và yêu cầu đầy đủ, khớp toàn văn DOM | 20/20 (100%) |
| Lỗi mới | 0 |
| Detail còn pending trong hai listing cũ | 25 |

Tất cả 23 phản hồi mới là HTTP 200, nhưng chỉ 20 phản hồi detail được tính
thành công sau kiểm tra nội dung. Không cộng listing/robots vào số tin.
Đây là kết quả truy cập kỹ thuật của mẫu giới hạn, không phải chấp thuận của
CareerLink, quyền tái công bố raw hoặc bảo đảm nguồn sẽ tiếp tục không chặn.

## Batch và bằng chứng

Raw được **append vào đúng batch cũ**, không tạo batch thay thế:

`data/raw/careerlink/snapshot_date=2026-09-26/batch_id=20260926T160422Z-c39d6a20/jobs.jsonl`

Các đường dẫn `data/` dưới đây là **artifact cục bộ, không commit/public lên GitHub**.
Thư mục bằng chứng lượt mới:

`data/diagnostics/careerlink_reassessment/20260929T033930Z/`

- `offline-before.json`: 55 ID ban đầu, toàn bộ queue chỉ đọc, lỗi cũ, manifest,
  checksum 1.522 file raw có sẵn và trạng thái/diff Git trước khi chạy.
- `robots.json`, `robots.body.gz`: robots hiện tại.
- `listing-hop-0.json`, `listing-hop-0.body.gz`, `listing-dom-audit.json`:
  status, URL cuối, body và cấu trúc listing mới.
- `pending-detail-3626178.json`, `pending-detail-3626178.body.gz`,
  `probe-dom-audit.json`: detail từng bị hCaptcha, lần này truy cập được.
- `live-probe.json`: từng request thăm dò, thời điểm và quyết định chủ dự án.
- `resume-plan.json`, `probe-reused.json`, `resume-result.json`: tham số đợt resume,
  bằng chứng tái sử dụng phản hồi probe và manifest sau đợt.
- `old-55-dom-audit.json`, `final-dom-audit.json`, `new-records-audit.json`:
  đối chiếu JSONL với toàn bộ section HTML, canonical, ngày đăng và content hash.
- `after-audit.json`: số request thật, ID mới/pending, checksum và Git sau chạy.
- `quality-checks.json`, `reuse-offline-test.json`: kết quả kiểm tra offline.

Mỗi HTTP response mới có body gzip, URL yêu cầu/URL cuối, status, thời điểm và
SHA-256. Trong batch, `http/` nhận thêm 20 phản hồi = 1 robots + 19 detail mới;
20 HTML detail được lưu theo `raw_html_path`. Probe ban đầu ở diagnostics được
tái sử dụng một lần, không GET lại và không đếm hai lần.

## Đối soát lịch sử trước phép thử

Đã đọc báo cáo `second_source_assessment_2026-09-26.md`,
`week3_data_readiness_2026-09-26.md`, README, AGENTS, parser/fetcher/engine/CLI,
checkpoint mở **read-only**, `jobs.jsonl`, `errors.jsonl` và HTML lỗi.

Trước đợt mới: 55 dòng hợp lệ / 55 ID; 55 completed + 45 pending detail;
2 listing completed + 1 pending (`/vieclam/list?page=3`). Hai listing cũ có
50 + 50 ID, không overlap: tổng 100 ID, không phải 33.397 tin đã crawl.
Toàn bộ 55 record cũ khớp HTML, canonical và content hash, không có lỗi audit.

Lần trước detail thứ 56, ID **3626178**, trả HTTP 200 chứa form
`recaptcha_confirm_form` và widget `h-captcha`; không có detail đầy đủ.
URL chính xác:

https://www.careerlink.vn/tim-viec-lam/chuyen-vien-sale-admin-ocean-edu-yen-lac-thu-nhap-tu-13-trieu-thang-phong-van-di-lam-ngay/3626178

Bằng chứng cũ giữ nguyên trong batch:
`http/20260926T160838.708991Z-d1b387b5.html.gz`, metadata cùng tên và
`errors.jsonl` (1 lỗi). Không xóa lỗi hoặc sửa lịch sử để coi batch chưa từng bị chặn.

55 ID đã lưu ban đầu, theo đúng thứ tự JSONL:

```text
3634108, 3634019, 3628750, 3633735, 3628753, 3634059, 3634050, 3634056,
3621196, 3634021, 3621190, 3626563, 3612715, 3634022, 3611466, 3633856,
3611465, 3633413, 3632868, 3633403, 3611937, 3633404, 3633575, 3633412,
3617480, 3633171, 3618941, 3633915, 3618940, 3633932, 3620657, 3609753,
3625779, 3633921, 3627321, 3633798, 3617474, 3626752, 3618934, 3633922,
3623368, 3609754, 3633926, 3633928, 3633927, 3633854, 3633896, 3609823,
3633904, 3633916, 3633909, 3626180, 3633911, 3626183, 3633899
```

## Điều kiện truy cập và listing hiện tại

Cơ sở: yêu cầu trực tiếp của chủ dự án cho probe rồi resume tối đa 20 detail mới;
`project_owner_public_test`, `authorization_reference=null`. Không tạo mã cấp phép.
Không thay quy tắc repo hoặc UA để mở khóa. Dùng đúng UA minh bạch của batch cũ:
`job-warehouse-crawler/0.1 (public academic research; single-threaded)`.

29/09, **03:41:04 UTC (10:41:04 ICT)**:
https://www.careerlink.vn/robots.txt — HTTP 200, text/plain.
Đối chiếu 47 URL khác nhau: `/vieclam/list`, start URL cũ và 45 detail pending,
đều được phép với UA trên. Đã đọc cả rule wildcard và nhóm UA riêng; không gọi
vùng tài khoản, nhà tuyển dụng có đăng nhập hoặc Next.js RSC `_rsc=`.
Engine kiểm tra robots lại khi resume lúc **03:45:09 UTC**, HTTP 200,
và kiểm tra từng URL trước khi fetch/parse detail.

Điều khoản/quy chế dựa trên toàn văn đã lưu ngày 26/09 từ
https://www.careerlink.vn/thoa-thuan-su-dung và
https://www.careerlink.vn/quy-che-hoat-dong; không tải lại trong lượt này.
Nhận định phạm vi thử đồ án lưu cục bộ và giới hạn tái phân phối giữ nguyên
theo báo cáo cũ. **Chưa kiểm chứng liệu điều khoản đã thay đổi sau 26/09**;
robots cho phép không phải giấy phép khai thác/tái xuất bản quy mô lớn.

**03:41:14 UTC**: https://www.careerlink.vn/vieclam/list — HTTP 200,
URL cuối vẫn chính URL đó, không redirect; canonical cũng là `/vieclam/list`.
Vùng chính `ul.list-group > li.job-item a.job-link[href]` có **50 card / 50 ID**.
Liên kết `rel=next` tới https://www.careerlink.vn/vieclam/list?page=2.
Không dùng quảng cáo/gợi ý làm dữ liệu chính; chưa GET trang 2 mới hoặc trang 3.

Crawler đang dùng start URL cũ `/vieclam/tim-kiem-viec-lam`, trong HTML cũ cũng
có 50 card cùng cấu trúc và next tới `/vieclam/list?page=2`. Không GET lại start URL
đó nên **chưa kiểm chứng redirect hiện tại của riêng start URL cũ**.
Giữ nguyên start URL khi resume vì engine yêu cầu khớp manifest; không đổi batch.
50 ID trên listing mới chỉ phục vụ khảo sát, **không enqueue** vào checkpoint cũ.

## Detail thăm dò và resume

**03:41:25 UTC**: đúng URL ID 3626178 kể trên — HTTP 200, không redirect,
không hCaptcha/challenge. Đọc được từ detail:

- Công ty: Hệ Thống Anh Ngữ Quốc Tế Ocean Edu.
- Tiêu đề: Chuyên Viên Sale Admin (Ocean Edu Yên Lạc) - Thu nhập từ 13 triệu/tháng
  - Phỏng vấn đi làm ngay.
- Mô tả 818 ký tự, yêu cầu 280 ký tự; khớp **toàn bộ** DOM section, đã đối chiếu
  đoạn đầu/cuối, không lấy preview listing.
- Lương `13 triệu - 15 triệu`; địa điểm `Yên Lạc, Phú Thọ`;
  ngày đăng lấy từ `Ngày đăng tuyển`: `17-09-2026`.

Sau kiểm tra parser và offline mock, resume **03:45:09–03:49:31 UTC**
(10:45:09–10:49:31 ICT), một luồng HTTP, delay cấu hình 10–15 giây,
max-retries=0. Khoảng cách giữa thời điểm bắt đầu GET trong resume thực đo
**10,858–16,562 giây** (bao gồm thời gian đáp ứng); không dùng browser/proxy/login.

`--max-details` là **số lượt thử lũy kế**, kể cả lượt lỗi, không phải số record hay
số lượt thêm. Ban đầu 56 lượt thử; giới hạn đợt này **76 = 56 + 20**.
Helper cục bộ dùng config/adapter/engine/fetcher/storage hiện có, cấp lại phản hồi
probe một lần qua giao diện fetcher để engine ghi HTML/JSONL/checkpoint bình thường;
sau đó tối đa 19 GET detail mới. Mock offline xác nhận không GET lại probe,
không tải ID completed và không vượt budget. Không sửa production code/parser.
`--max-pages 2` giữ budget listing bằng 2 lượt cũ, nên resume không GET page 3.

Lệnh đã thực sự chạy:

```bash
.venv/bin/python data/diagnostics/careerlink_reassessment/20260929T033930Z/resume_from_probe.py
.venv/bin/python data/diagnostics/careerlink_reassessment/20260929T033930Z/resume_from_probe.py --execute
```

Tham số CLI tương đương nằm đầy đủ trong `resume-plan.json`: đúng batch ID,
mode bounded, max-pages=2, max-details=76, delay=10–15, save-html,
require-complete-content, HTTP, owner public test và max-retries=0.
Không tuyên bố đã gọi thêm lệnh CLI độc lập rồi cộng hai lần cùng một đợt.

20 ID mới ghi vào raw, không trùng 55 ID cũ:

```text
3626178, 3632790, 3626177, 3633484, 3626176, 3633892, 3626175, 3633888,
3626173, 3626170, 3626169, 3625841, 3625840, 3617124, 3616653, 3616654,
3625839, 3625838, 3625837, 3625835
```

Cả 20 có ID/canonical, title/company, mô tả/yêu cầu, salary/location/posted date.
Audit toàn bộ 75 JSONL với HTML tương ứng: **0 sai lệch**, không cắt mô tả/yêu cầu.
Địa chỉ làm việc chi tiết thiếu **16/20 tin mới** (toàn batch 48/75);
các trường mở rộng như experience/company_id/company_url/benefits chưa được parser
trích riêng, giữ null/array rỗng. Không coi đây là dữ liệu đầy đủ mọi trường CareerViet.

Manifest lũy kế: detail_requested=76, detail_succeeded=75, detail_failed=1,
records_written=75, duplicates_skipped=0, challenge_detected=false;
`completed_with_errors`, termination=`max_details`.
Lỗi 1 là hCaptcha **cũ**, không phải lỗi mới. Hai trường delay trong manifest vẫn là
cấu hình khởi tạo 3–5 giây vì engine không cập nhật chúng khi resume;
đợt mới thực dùng 10–15 theo `resume-plan.json` và timestamp phản hồi.
Giữ nguyên bằng chứng cấu hình lịch sử, không sửa nó thành cấu hình mới giả.

## Checkpoint và mốc tiếp theo — chưa chạy

75 completed + **25 pending detail** trong 100 ID của hai listing cũ;
page 3 vẫn pending. Nếu tiếp tục truy cập bình thường, đề xuất:

1. Thêm tối đa 20 lượt: mục tiêu tối đa **95 record**, cap lũy kế **96**.
2. Sau audit đợt đó, thêm tối đa 5 lượt còn lại: mục tiêu **100 record**, cap **101**.

Lệnh đợt kế tiếp **chỉ được chuẩn bị, chưa chạy**, cần kiểm tra lại điều kiện và
dừng ngay mọi 401/403/429/challenge, kể cả HTTP 200:

```bash
.venv/bin/job-crawler crawl careerlink --mode bounded \
  --start-url 'https://www.careerlink.vn/vieclam/tim-kiem-viec-lam' \
  --output-dir data/raw --project-owner-public-test --fetcher http \
  --resume --resume-batch-id 20260926T160422Z-c39d6a20 \
  --max-pages 2 --max-details 96 --delay-min 10 --delay-max 15 \
  --max-retries 0 --timeout 30 --save-html --require-complete-content \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

Mốc 100 còn phụ thuộc 25 detail chưa thử trong lượt mới; chưa chứng minh khả năng
đọc page 3 hoặc đạt 299. Không tự chạy các mốc tiếp theo sau báo cáo này.

## Kiểm tra và bảo toàn

Đã chạy offline:

```bash
.venv/bin/pytest -q
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src/job_crawler
git diff --check
```

**214 test passed**, Ruff format/check đạt; mypy đạt trên 43 source file;
25 test CareerLink mục tiêu đạt trước resume. Helper local cũng qua Ruff và
mock tái sử dụng probe/dedup/budget; audit DOM trước/sau đạt, không cần sửa parser.

Checksum xác nhận 55 dòng đầu nguyên byte, lỗi cũ và tất cả HTML cũ nguyên trạng.
Chỉ bốn file raw đã có thay đổi: CareerLink jobs/manifest/checkpoint và
incremental_state; thêm 60 artifact raw (20 HTML + 20 cặp body/metadata HTTP).
Không xóa file. CareerViet batch 299 và Timviec365 batch 299, các batch TopCV,
VietnamWorks cùng toàn bộ source/raw/checkpoint khác giữ nguyên.
HEAD, tracked diff, staged diff và các file untracked đã có không thay đổi;
chỉ thêm báo cáo này và artifact cục bộ của CareerLink. Không stage/commit/push.
