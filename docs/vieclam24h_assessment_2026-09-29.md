# Việc Làm 24h: probe, batch detail và resume — 29/09/2026

## Phạm vi và cơ sở truy cập

Đây là quyết định thử kỹ thuật của chủ dự án trong chat ngày 29/09/2026,
không phải chấp thuận của Việc Làm 24h hoặc giấy phép khai thác/tái công bố.
Manifest ghi `access_basis=project_owner_public_test`, `authorization_reference=null`.
Chỉ tin công khai, không đăng nhập; một luồng Chrome thường có giao diện,
nghỉ 10–15 giây giữa các điều hướng, không retry, stealth, proxy, CAPTCHA solver
hoặc chuyển công cụ sau khi bị chặn. Browser được chọn **trước request đầu tiên**
theo yêu cầu, không phải fallback từ một phản hồi HTTP bị từ chối.

Artifact đầy đủ bên dưới chỉ lưu cục bộ, nằm trong `data/` được Git ignore;
không phải file sẽ đi cùng bản clone repository. Fixture được rút gọn thành
cấu trúc/số ID mẫu và nội dung tổng hợp, không đưa toàn bộ HTML live lên Git.

## Quy định và robots: không đánh đồng với listing/detail

- Bằng chứng cũ: `data/diagnostics/second_source_assessment/20260926/vieclam24h-robots.json`:
  GET robots ngày 26/09/2026 15:58:11 UTC trả 403; listing thử = 0, detail thử = 0.
  Không dùng 403 này làm bằng chứng rằng listing/detail hiện tại bị chặn.
- [Robots hiện hành](https://vieclam24h.vn/robots.txt): browser ngày 29/09/2026
  04:04:25 UTC nhận 200. Nhóm `User-agent: *` cấm `/admin/`, `/*?q`, `/asset/`,
  `/taikhoan/`, `/thong-bao-viec-lam.html`, `/quan-ly-ho-so-tim-viec.html`;
  không cấm listing chính không query, `?page=N` hoặc các detail canonical đã thử.
  Bot Semrush/Ahrefs có crawl-delay 5; đợt này nghỉ tối thiểu 10 giây.
  Crawler đọc lại robots ở mỗi lần resume, kiểm tra từng URL và redirect;
  guard wildcard thiên về dừng nếu có Disallow khớp. Không dùng sitemap.
- [Điều khoản sử dụng](https://vieclam24h.vn/dieu-khoan-su-dung.html): ngày
  29/09/2026 04:08:28 UTC nhận 200, đọc toàn bộ mục 1–10 (230 dòng).
  Mục 1.1/1.2, 2.1 và 10.1(d) áp dụng cả khách xem không có tài khoản.
  Mục 4.1 nói về tài khoản sử dụng dịch vụ, nhưng ba trang tin công khai thực tế
  xem được không đăng nhập. Mục 6.1 liên quan quyền với nội dung người dùng đưa
  lên; 6.2 bảo vệ tên/dấu hiệu của Công ty. Mục 8.2 và 10.4 là quyền hạn chế
  dịch vụ/tài khoản, không phải lệnh cấm crawler được nêu rõ cho phép thử này.
  Không tìm thấy khoản cấm bot/crawler áp dụng rõ trong văn bản đã đọc;
  đây là kết quả đối chiếu kỹ thuật, **không phải kết luận pháp lý hay giấy phép**.
- Biên bản, thời điểm và văn bản đầy đủ: `robots.json`, `robots.txt`, `terms.json`,
  `terms.txt`, `access-decision.json` trong thư mục diagnostics bên dưới.

## Probe đầu tiên: listing chính và 3 detail

Thư mục bằng chứng: `data/diagnostics/vieclam24h_reassessment/20260929T040236Z/`.
Có status, URL cuối, body HTTP gốc, HTML render và screenshot từng trang.
Ba request kiểm tra điều kiện/tiếp cận ban đầu là robots, listing, điều khoản;
thêm ba detail: **6 điều hướng chính**, tất cả 200. Browser còn tải tài nguyên
và XHR của chính trang; 6 không phải số toàn bộ request mạng.

Listing ngày 04:04:37 UTC:
`https://vieclam24h.vn/tim-kiem-viec-lam-nhanh`, không đổi host/URL.
30 ID/URL thuộc `main`, card có `data-job-id`, tracking `0201_<page>_…`;
đối chiếu tập ID bằng public `__NEXT_DATA__ → jobsResponse.items`.
Không lấy banner, widget gợi ý hoặc quảng cáo ngoài tập kết quả chính.
Tập chính có 27 tin được nguồn gắn `job_paid=true`, 3 tin không gắn cờ này:
đó vẫn là tin tuyển dụng nằm trong response kết quả tìm kiếm, không phải banner.
Ba detail mẫu được chọn từ **3 tin không gắn cờ paid**; batch sau lấy tin thật
trong vùng kết quả chính, không dùng các slot quảng cáo thay cho detail.

Có link công khai `?page=2`; metadata current=1, total_pages=34.
Số tổng nguồn tự báo không phải số record thu thập. HTML response ban đầu cũng
có 30 ID và phần detail đầy đủ: không khẳng định rằng nội dung bắt buộc phải JS.
Đợt này chưa đo fetcher HTTP độc lập; kết quả thực đo là browser thường.

| Detail ID | HTTP / cùng host | Mô tả (ký tự) | Yêu cầu (ký tự) | Trường tùy chọn có |
|---|---|---:|---:|---|
| 200941421 | 200 / có | 455 | 344 | lương, địa điểm, ngày đăng |
| 200944169 | 200 / có | 353 | 134 | lương, địa điểm, ngày đăng |
| 200945045 | 200 / có | 466 | 228 | lương, địa điểm, ngày đăng |

3/3 hợp lệ: ID canonical và detail JSON trùng nhau; h1, công ty, mô tả/yêu cầu
được lấy từ chính detail. Toàn văn DOM bằng `description_html` và
`other_requirement_html`, không dùng `resume_requirement_html` (hồ sơ ứng tuyển).
JSON-LD `identifier` là ID nhà tuyển dụng, **không** dùng làm ID việc làm.
`sample-records-validated.json` và `sample-audit-validated.json` là kiểm chứng
cuối cùng đã sửa cách đọc nhãn lương/địa điểm/ngày đăng; file audit trung gian
không phải số liệu cuối. Probe chưa ghi `jobs.jsonl`, không tính 3 ID này thành
3 record mới của pilot.

## Batch và các mốc thực chạy

Batch: `data/raw/vieclam24h/snapshot_date=2026-09-29/batch_id=20260929T042736Z-b37e7b1a/`.

| Mốc | Listing 200 / đã thử | ID chính duy nhất | Detail thử / hợp lệ | Dòng raw | Đủ mô tả + yêu cầu |
|---|---:|---:|---:|---:|---:|
| Pilot 20, sau phục hồi offline | 2/2 | 60 | 20/20 | 20 | 20/20 (100%) |
| Mốc 100 | 4/4 | 116 | 101/100 | 100 | 100/100 (100%) |
| Mở rộng hướng 300, thực dừng | 11/11 | 277 | 106/104 | 104 | 104/104 (100%) |

Mốc 100 hoàn tất 05:16:48 UTC. 20 ID mới sau lỗi gateway đều đạt, 80 dòng cũ
giữ nguyên byte-for-byte; cumulative detail HTTP success = 100/101 (99,01%).
Tiêu đề/công ty/mô tả/yêu cầu/lương/địa điểm/ngày đăng có ở 100/100;
bằng cấp thiếu ở 33 tin, để null. Không expired theo deadline ở thời điểm crawl.
`phase-100.json` chứa đối chiếu toàn văn/hash từng detail và snapshot counters.
Đợt mở rộng dùng trần 11/300, nhưng **dừng thật ở 104**, không đạt 299/300.
106 lượt điều hướng detail gồm 104 response 200 hợp lệ, 1 response 502,
1 lượt cuối chưa lưu được response. Tỷ lệ hợp lệ trên lượt điều hướng =
104/106 (98,11%); trên response đã lưu = 104/105 (99,05%). Độ đầy đủ nội dung
100% tính trên **104 record hợp lệ**, không phải trên toàn bộ lượt thử.
`phase-final-104.json` và `final-counts.json` là số liệu chốt.

| Phạm vi | Robots / điều khoản | Listing thử / đọc được | ID main duy nhất | Detail thử / hợp lệ | Raw |
|---|---:|---:|---:|---:|---:|
| Probe | 1 / 1 | 1/1 | 30 | 3/3 | 0 |
| Batch lũy kế | 5 / 0 | 11/11 | 277 | 106/104 | 104 |
| Cả lượt, không cộng nhầm listing vào raw | 6 / 1 | 12/12 | 299 (union snapshot listing) | 109/107 | 104 |

128 điều hướng chính đã được bắt đầu, 127 response có bằng chứng
(126×200, 1×502), 1 lượt cuối chưa biết status. Browser còn tải asset/XHR;
không đo được tổng request tài nguyên, **không gọi 128 là toàn bộ request mạng**.
299 ID từ union các listing **không phải 299 detail**. Ba probe ID không có
trong 104 dòng raw hiện tại; không cộng 3 probe thành record batch mới.

Manifest `detail_requested=108` là slot engine, có 2 slot không gửi HTTP:
1 SIGINT trong khoảng nghỉ và 1 latch gọi lại sau 502. Detail navigation thật
là 106, không dùng 108 để báo số GET. 105 capture detail không URL nào tải hai lần;
104 dòng cũ của các mốc được giữ nguyên, không ghi duplicate.

Pilot chạy 04:27:36–04:33:29 UTC: 1 robots + 2 listing + 20 detail = 23
điều hướng chính, tất cả 200. Ngày đăng lấy nhãn **Ngày đăng** trên detail,
không lấy ngày cập nhật. 20/20 mô tả và yêu cầu khớp cả DOM đầy đủ và JSON
của detail; không có ID trùng hoặc deadline đã qua ở thời điểm crawl.
Độ dài mô tả min/median/max = 281/596/6.141 ký tự; yêu cầu = 82/367/1.459.
Không áp ngưỡng độ dài tùy tiện để coi một yêu cầu ngắn là thiếu toàn văn.

### Lỗi parser trang 2 và phục hồi không request

Trang 2 trả **200 với 30 ID mới**, nhưng selector ban đầu chỉ nhận tracking
`0201_1_…`, trong khi trang 2 dùng `0201_2_…`. Đây là lỗi parser, không phải
lỗi truy cập hay pagination giả. Body/DOM/metadata đã lưu trước khi parse.
Sửa selector thành `0201_`, thêm test page=2; ID DOM phải trùng tập ID trong
jobsResponse và current phải bằng page trong URL.

Sau khi pilot đã dừng ở 20, phục hồi chính checkpoint từ HTML trang 2 bằng
`scripts/recover_vieclam24h_listing.py`: **0 request mới, +30 ID pending**, không
đổi byte nào trong `jobs.jsonl` hoặc `errors.jsonl`. Lần gọi thứ hai là no-op.
Giữ dòng lỗi listing_parse cũ để không sửa lịch sử; metadata và
`listing-offline-recovery.json` giải thích vì sao lỗi này đã được xử lý.
Audit trước/sau: `phase-20-before-recovery.json`, `phase-20.json` tại diagnostics.

### Lỗi khoảng trắng tiêu đề và gián đoạn có ghi bằng chứng

ID `200946594` trả 200 với đầy đủ nội dung, nhưng JSON title có khoảng trắng đầu;
DOM text đã được trim nên phép so sánh cũ báo mismatch. Sửa so sánh whitespace
trên cả hai phía, thêm test regression; không thay nội dung công việc.
Tạm dừng đúng process bằng SIGINT để sửa offline, không phải do bị nguồn chặn.
`parser-fix-interruption.json` giữ manifest trước, PID đã dừng và ID `200940031`
ở trạng thái processing **chưa có HTTP capture**: 74 slot attempt nhưng 73
detail HTTP thực (72 record trước phục hồi + 1 detail lỗi parser).

Phục hồi ID `200946594` từ HTML đã lưu bằng `--detail`: +1 dòng raw, **0 request**,
không đổi byte dòng cũ hoặc HTML/error cũ; lần gọi thứ hai no-op. `crawled_at`
vẫn là thời điểm response gốc, không phải thời điểm reparse. Manifest chuyển
lỗi parser đang chưa giải quyết thành success sau kiểm chứng; báo cáo
`detail-offline-recovery-200946594.json` giữ counters trước/sau và lỗi lịch sử
không bị xóa. `phase-parser-fix-73.json` kiểm chứng 73/73 toàn văn và 0 trùng.

Resume tiếp cùng batch đặt trần 101 slot để đạt tối đa 100 detail HTTP thực:
slot bị ngắt vẫn giữ trong counter, không giảm counter hoặc giấu lịch sử.

### HTTP 502: lỗi gateway, không phải 403/challenge

Ngày 05:04:54 UTC, ID `200937439` trả **502 Bad Gateway / nginx**,
URL cuối không đổi; `blocked=false`, `challenge_type=null`, `source_denials=[]`.
Body, DOM, JSON metadata và ảnh lỗi đã lưu trong batch. Đợt đó dừng ở **80 raw**;
88 điều hướng chính thực gồm 87 response 200 và 1 response 502.
Không có response 401/403/429 hay CAPTCHA. `phase-80-technical-stop.json`
kiểm toán 80/80 toàn văn, 0 trùng, 0 deadline đã qua.

Fetcher phiên bản đầu latch cả lỗi kỹ thuật, nhưng engine còn gọi slot tiếp theo
(`200944157`) rồi nhận lỗi "already stopped" **không gửi mạng**; vì vậy manifest
lịch sử ghi `access_blocked` sai nghĩa. Không sửa/xóa manifest snapshot hoặc
error cũ để che lỗi. `technical-stop-review.json` đối chiếu dữ liệu thực.
Đã bổ sung `FetchError.terminal` opt-in (mặc định false, không đổi luồng nguồn cũ),
để engine dừng ngay với `detail_fetch_failed` cho 502, không đếm slot giả tiếp
và không gán lỗi gateway thành access denial. Test chứng minh điều này offline.

Sau rà soát không có tín hiệu hạn chế truy cập thực, tiếp tục **một đợt nhỏ**
trong phạm vi yêu cầu gốc, cùng browser/IP/user-agent mặc định và tốc độ,
không retry ID 502 (checkpoint vẫn failed). Trần 103 slot để hướng đến 100
record thực, do một slot SIGINT + một slot latch không gửi HTTP đã có trong lịch sử.
Nếu lỗi kỹ thuật lặp hoặc có tín hiệu chặn thật, dừng; không đổi công nghệ để né.
Trần cuối vẫn 300 slot: nếu phần còn lại đều đạt, tối đa 297 record sau các
slot gián đoạn và HTTP 502 đã ghi nhận, không mặc định là 300/300.

### Điểm dừng cuối: DOM đang điều hướng, không biết status cuối

Đợt mở rộng kết thúc 05:21:42 UTC với `status=failed`,
`termination_reason=unexpected_error`, sau khi ghi 104 record. ID đang xử lý:
`200946972`, URL `https://vieclam24h.vn/it-phan-cung-mang/nhan-vien-ky-thuat-trien-khai-van-hanh-ha-tang-vien-thong-toa-nha-c7p98id200946972.html`.
`Page.content` báo không lấy được nội dung khi trang đang điều hướng.
Nhánh exception cũng gọi `Page.content` rồi lỗi lần nữa, che mất lỗi ban đầu;
body/status/final URL/screenshot của **lượt này chưa lưu được**. Không suy ra
HTTP 200, 403 hoặc CAPTCHA từ exception. `last-navigation-unverified.json`
chỉ là biên bản đối chiếu engine/checkpoint, **không phải HTTP capture**.

Đã sửa offline: lưu status và body HTTP gốc trước wait/đọc DOM; nếu goto lỗi,
giữ response document đã quan sát; metadata ghi original_error và lỗi capture
phụ, không để DOM/screenshot/close lỗi che exception gốc. Body vẫn giữ được
khi DOM thay đổi; 403 và hCaptcha trong HTTP 200 vẫn terminal, không fallback
hoặc retry. Test mô phỏng DOM lỗi hai lần, screenshot lỗi, goto lỗi sau khi
quan sát response và page.close lỗi. **Bản sửa cuối chưa được kiểm chứng live**;
không request mới sau lượt cuối chưa xác minh.

Checkpoint giữ 104 completed, 1 failed (502), 171 pending, 1 processing
(lượt chưa biết status). Resume kỹ thuật sẽ đưa processing về pending;
không tự resume khi chưa đánh giá lại điều kiện truy cập/response chưa biết.
Page 12 đã có link public pending, chưa tải. 11 trang có 330 card occurrence,
dedup 53 → 277 ID thật; không suy rằng mỗi trang luôn thêm 30 ID.

## Lệnh và giới hạn

Chạy từ thư mục gốc repository; Chrome có sẵn, không dùng launch flag stealth
hoặc override user agent của browser. `--user-agent` bên dưới là định danh cấu
hình/robots; browser giữ user agent Chrome mặc định. Không cài cookie/tài khoản.

```bash
JOB_CRAWLER_BROWSER_EXECUTABLE_PATH=/usr/bin/google-chrome \
.venv/bin/job-crawler crawl vieclam24h --mode bounded \
  --project-owner-public-test --fetcher playwright --headed \
  --max-pages 2 --max-details 20 --delay-min 10 --delay-max 15 \
  --max-retries 0 --timeout 30 --save-html --save-screenshot-on-error \
  --require-complete-content \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

Các trần `max-pages`/`max-details` đếm **lũy kế cùng batch**, không phải số
record mới. Lệnh resume mốc 100 thêm `--resume --resume-batch-id
20260929T042736Z-b37e7b1a`, ban đầu dùng `--max-pages 4 --max-details 100`;
sau gián đoạn nêu trên, dùng `--max-pages 4 --max-details 101`.
Sau lỗi gateway/latch, đợt bổ sung nhỏ dùng `--max-pages 4 --max-details 103`.
Chỉ sau audit mốc 100 ổn định mới tăng trần, không chạy hai batch đồng thời.
Code giới hạn tối đa 12 listing/300 lần thử detail, không phải full snapshot.

Lệnh mở rộng **đã chạy** là lệnh trên cộng resume đúng batch và đổi thành
`--max-pages 11 --max-details 300`. Lệnh resume nhỏ cho lần sau (chưa chạy,
chỉ sau đánh giá lại truy cập, không dùng để né challenge) giữ các flag ở trên:

```bash
JOB_CRAWLER_BROWSER_EXECUTABLE_PATH=/usr/bin/google-chrome \
.venv/bin/job-crawler crawl vieclam24h --mode bounded \
  --project-owner-public-test --fetcher playwright --headed \
  --resume --resume-batch-id 20260929T042736Z-b37e7b1a \
  --max-pages 11 --max-details 128 --delay-min 10 --delay-max 15 \
  --max-retries 0 --timeout 30 --save-html --save-screenshot-on-error \
  --require-complete-content \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

128 = 108 slot cũ + tối đa 20 slot mới; không phải thêm 128 record.
Không tự bỏ qua nguyên nhân của lượt cuối, không retry ID 502 đã failed.

```bash
.venv/bin/python scripts/recover_vieclam24h_listing.py \
  data/raw/vieclam24h/snapshot_date=2026-09-29/batch_id=20260929T042736Z-b37e7b1a \
  'https://vieclam24h.vn/tim-kiem-viec-lam-nhanh?page=2'
.venv/bin/python scripts/audit_vieclam24h_batch.py \
  data/raw/vieclam24h/snapshot_date=2026-09-29/batch_id=20260929T042736Z-b37e7b1a \
  data/diagnostics/vieclam24h_reassessment/20260929T040236Z/phase-20.json
```

Không dùng lệnh phục hồi parser để mở lại batch bị challenge/robots cấm;
công cụ có guard và test cho trường hợp đó.

## Code, kiểm thử và dữ liệu giữ nguyên

Adapter, parser và fetcher tách riêng tại `src/job_crawler/{crawlers,parsers,fetchers}/vieclam24h.py`;
CLI/config/factory bổ sung nguồn này. Dùng storage JSONL/HTML, incremental hash,
checkpoint/resume chung; một dòng JSONL chỉ sau detail đạt trường lõi.
Fetcher lưu body HTTP **và** DOM trước khi phân loại, dừng ngay 401/403/429 hoặc
challenge kể cả 200, chặn điều hướng ra host khác; không HTTP/browser fallback.

Test offline kiểm chứng ID main so với embedded response, pagination/tracking,
toàn văn gồm đoạn cuối, yêu cầu không lẫn hồ sơ ứng tuyển, job ID không lẫn
employer ID, ngày cập nhật không thành ngày đăng, nullable, stop latch, robots
wildcard, resume dedup và phục hồi parser idempotent không đổi JSONL/errors.
Kiểm tra trước mốc 100: **240 test pass**, Ruff format/check, mypy 46 source file
và `git diff --check` đều đạt. Bản sửa cuối bổ sung các test 502/terminal và
bảo toàn HTTP khi DOM/goto/screenshot lỗi; kết quả kiểm tra cuối ở dưới.

Baseline cũ: CareerViet 299, Timviec365 299, CareerLink 75. Không stage, commit,
push hoặc sửa dữ liệu/checkpoint các nguồn đó. `before.json` lưu hash toàn bộ
1.582 file raw cũ và trạng thái Git trước lượt này.

Checksum sau: `preservation-after.json` xác nhận **1.582/1.582 file raw cũ không
đổi, không mất**, 7 file untracked cũ không đổi; HEAD/index và diff AGENTS.md
đúng baseline. CareerViet 299, Timviec365 299, CareerLink 75 vẫn nguyên vẹn.
Các mốc raw 20/80/100 của nguồn mới cũng là byte-prefix nguyên vẹn của 104 dòng cuối.

## Dữ liệu và đối chiếu nội dung cuối

Raw: `data/raw/vieclam24h/snapshot_date=2026-09-29/batch_id=20260929T042736Z-b37e7b1a/jobs.jsonl`.
SHA256 = `064ef9e04b7a5e34aceded2ed0aaf5e7d229a58a4821bafa668da5e8b0f4b1cd`.
HTML mỗi record: `html/<source_job_id>.html.gz`; HTTP gốc/DOM/metadata: `http/`.
Ảnh 502: `screenshots/http_error-001-nhan-vien-van-hanh-may-san-xuat-c10p90id200937439.html.png`.
Lỗi lịch sử gồm 2 parser đã phục hồi, 1 HTTP 502, 1 latch không gửi mạng,
1 lỗi engine/DOM cuối. Không xóa lịch sử hoặc đổi lỗi thành thành công giả.

| Trường | Việc Làm 24h | CareerViet | Timviec365 | CareerLink |
|---|---:|---:|---:|---:|
| Record detail raw duy nhất | 104 | 299 | 299 | 75 |
| Tiêu đề, công ty, mô tả, yêu cầu có dữ liệu | 104/104 | 299/299 | 299/299 | 75/75 |
| Lương / địa điểm có dữ liệu | 104/104 | 299/299 | 299/299 | 75/75 |
| Ngày đăng raw có dữ liệu | 104/104 | 299/299 | 0/299 | 75/75 |
| Địa chỉ làm việc chi tiết có dữ liệu | 104/104 | 299/299 | 299/299 | 27/75 |
| Bằng cấp có dữ liệu | 70/104 | 299/299 | 299/299 | 0/75 |

34/104 bằng cấp thiếu (32,69%), để null. Tags/work_model/income_text/working_time/
application_method/quy mô/ngành/địa chỉ công ty chưa map, không coi là bằng chứng
nguồn không có thông tin. Metadata bắt buộc, source ID/URL, parser/schema version,
content hash và raw HTML path có ở 104/104. Ngày đăng đối chiếu nhãn Ngày đăng;
không suy ra từ Cập nhật. Deadline chưa qua tại thời điểm crawl 104/104,
nhưng chưa xác minh công ty thực tế có còn tuyển hay không.

Toàn văn đối chiếu DOM + JSON của **từng detail** có hash/ký tự trong
`phase-final-104.json` (không chỉ kiểm tra vài bản ghi). Mô tả min/median/max
146/562/6.141; yêu cầu 82/410,5/1.865 ký tự. Chọn đối chiếu cụ thể:
ID `200934545` (dòng đầu), `200946594` (đã phục hồi whitespace title),
`200937962` (dòng cuối): canonical ID, h1, công ty trong main, cả đoạn cuối
mô tả/yêu cầu bằng toàn bộ nội dung JSON tương ứng, không lấy preview.
Việc mô tả ngắn 146 ký tự là độ dài công bố của nguồn, không phải parser cắt.

## Giới hạn đánh giá

Toàn văn khớp HTML là bằng chứng parser không lấy preview, **không** chứng minh
tin là chính xác, doanh nghiệp đáng tin hoặc việc làm còn tuyển ngoài thực tế.
Các trường mở rộng chưa map (tags, quy mô/ngành công ty, working_time…)
không được diễn giải là nguồn không có thông tin. Ngày/lương giữ raw của nguồn;
chưa Bronze/Silver hay chuẩn hóa nghiệp vụ. Quyền sử dụng ở quy mô lớn/tái công bố
vẫn là vấn đề riêng với chủ nguồn, không suy ra từ HTTP 200 hay 3/3 detail.

**Kết luận:** nguồn đã chứng minh có listing chính qua 11 trang và **104 detail
thật đủ nội dung lõi**, tích hợp raw/checkpoint/resume được. Chưa chứng minh
batch 299/300 ổn định như CareerViet; lỗi gateway và lỗi capture cuối là các
giới hạn thực. Không coi số 299 ID listing union là hoàn thành 299 detail,
không kết luận Việc Làm 24h thất bại về kỹ thuật hoặc hiện bị 403 chỉ vì lỗi cũ.

## Kiểm tra cuối và Git

Đã chạy sau bản sửa cuối (offline, không website live trong test):

```bash
.venv/bin/pytest -q
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
git diff --check
```

Kết quả: **250 passed**, 108 file đã đúng format, Ruff check pass,
mypy không lỗi trên 46 source file, diff whitespace pass.
36 case test riêng Việc Làm 24h gồm stop/unknown/capture trước DOM và resume.
Không nói bản sửa capture đã pass live: chưa request thêm sau lỗi cuối.

Thay đổi của lượt này: README; CLI/config/factory; 3 module adapter/parser/fetcher
Việc Làm 24h; opt-in terminal error trong fetchers/base.py và engine.py;
2 script kiểm toán/phục hồi offline; test unit và 4 fixture nhỏ; báo cáo này.
Engine/base chỉ thêm cờ opt-in mặc định false, không đổi nghiệp vụ nguồn cũ.
Diff AGENTS.md cùng 7 file untracked cũ là thay đổi **có trước**, không thuộc
lượt này và được giữ nguyên. HTML/JSONL/screenshot/checkpoint không đưa vào Git.
Nhánh `main`, HEAD vẫn `7ba563532bf1251dcdc5b380cb377a70968c97d4`;
index giữ nguyên, **không stage/commit/push**. `preservation-after.json`
ghi git status/diff stat và xác nhận những điều này.
