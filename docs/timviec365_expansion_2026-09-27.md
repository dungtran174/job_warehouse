# Timviec365 — mở rộng có giới hạn, 27/09/2026

## Kết quả cuối

**299 ID detail duy nhất đã ghi vào raw**, đạt quy mô khoảng 300 theo yêu cầu.
Tăng **296** so với ba record ban đầu; riêng lần tiếp tục sau gián đoạn tăng
**104** (195 → 299). Dừng tự nhiên ở trần 300 lần thử, không phải bị website chặn.
Không gọi kết quả này là 300/300: có một lần thử dang dở chưa có phản hồi lưu lại.

## Phạm vi và lịch sử

Tiếp tục đúng batch `20260926T174917Z-3a406cfa`, không tạo snapshot mới,
không tính ba ID probe thành ba tin mới. Người dùng yêu cầu các mốc tổng ID
30 → 100 → khoảng 300. Đây là quyết định nội bộ của chủ dự án, không phải
chấp thuận của Timviec365: `access_basis=project_owner_public_test`,
`authorization_reference=null`. Không công bố lại HTML/raw hoặc khẳng định
quyền khai thác thương mại. Không chạy CareerViet, CareerLink hoặc VietnamWorks.

Các đường dẫn `data/` dưới đây là artifact **cục bộ, không đưa lên Git**.
Báo cáo assessment và followup cũ được giữ nguyên như lịch sử; số ba detail
trong báo cáo followup không phải kết quả cuối của đợt mở rộng này.

## Điều kiện và bằng chứng trước khi chạy

Evidence root: `data/diagnostics/timviec365_expansion/20260926T180022Z/`.

Ba GET preflight đầu tiên đều HTTP 200, URL cuối không đổi:

- `https://timviec365.vn/robots.txt` lúc 18:00:47 UTC 26/09/2026:
  không đổi so với bản đã đọc; listing `/viec-lam?page=N` và detail
  `-p<ID>.html` không khớp vùng Disallow.
- `https://timviec365.vn/thoa-thuan-su-dung.html` lúc 18:01:17 UTC:
  nội dung text không đổi so với bản đã đối chiếu.
- `https://timviec365.vn/images/manual/quy_che_cong_ty_HHP.pdf` lúc
  18:01:28 UTC: SHA-256 không đổi,
  `7f7a4c6c591cbf16065ec97cd452ec9e9bc41f5841e893cdd4db97084d9f27f8`.

Không tải PDF hoặc tài nguyên từ `storage1.timviec365.vn`, nơi robots cấm `/`.
Bản PDF trên host chính là URL chính thức đã xác định ở lượt followup, không
suy diễn quyền truy cập từ robots của host khác. Chưa xác minh hai bản PDF
đồng nhất. Đối chiếu phạm vi các khoản trong
[báo cáo followup](timviec365_followup_2026-09-27.md): chưa xác định lệnh cấm
áp dụng rõ cho phép thử nội bộ này; không coi đó là giấy phép của nguồn.

Sau khi tiến trình bị gián đoạn, kiểm tra lại robots/thỏa thuận/PDF host chính:
cả ba HTTP 200, robots và nội dung thỏa thuận không đổi, PDF cùng checksum.
Metadata thời điểm chính xác trong `resume-robots.json`, `resume-terms.json`,
`resume-policy.json`; quyết định tiếp tục trong `resume-access-decision.json`.
Mỗi lần chạy CLI còn đọc lại robots trước request công việc.

HTTP thông thường, một luồng, nghỉ ngẫu nhiên 10–15 giây sau phản hồi,
`max-retries=0`, timeout 30 giây. Không browser/API/đăng nhập/proxy/stealth;
không retry phản hồi chặn. Fetcher lưu body và status/URL cuối trước khi xét
lỗi; dừng khi HTTP khác 200 hoặc phát hiện challenge, kể cả HTTP 200.

## Trang 2 và sửa lỗi offline

Đầu tiên resume giới hạn 2 listing nhưng vẫn chỉ 3 lần thử detail để kiểm tra
trang 2 trước khi mở rộng detail. `https://timviec365.vn/viec-lam?page=2`
trả HTTP 200 lúc 18:04:14 UTC, có **24 ID main mới**, không trùng trang 1.

Crawler ban đầu báo `Non-sequential Timviec365 pagination`: cả nút lùi `<`
và tiến `>` cùng dùng `.pagi_pre`, parser chọn nhầm nút lùi. Đây là lỗi parser,
không phải chặn truy cập. Đã sửa chọn đúng nút `>`, kiểm tra chuyển sang trang 3,
thêm fixture nhỏ `tests/fixtures/timviec365/page2_arrows.html` và test offline.

Khôi phục từ chính body đã lưu, không request lại trang 2. Hàm
`storage.timviec365_recovery.recover_page2` đối chiếu hash/status/challenge,
enqueue 24 ID và hoàn tất checkpoint trong giao dịch; gọi lại trả 0 ID mới.
Không xóa dòng lỗi lịch sử trong `errors.jsonl`. Bằng chứng:
`page2-recovery.json`, `gate-page2.json`, và metadata trong batch
`http/20260926T180414.965653Z-6a27e480.json` cùng body gzip.

Đã đọc thành công **13 listing chính, 303 ID duy nhất**: 12 trang đầu mỗi
trang 24 ID, trang 13 có 15 ID; không overlap giữa trang. Không đếm quảng cáo
ngoài vùng main hoặc card gợi ý thành detail. Đây không phải khẳng định đã
thu thập toàn bộ website.

## Các mốc đã kiểm toán

| Mốc | Listing thành công lũy kế | ID main phát hiện | Detail thử / thành công | Record tăng thêm | Tổng ID raw | Đủ mô tả / yêu cầu |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ban đầu | 1 | 24 | 3 / 3 | 0 | 3 | 100% / 100% |
| 30 | 2 | 48 | 30 / 30 | +27 | 30 | 100% / 100% |
| 100 | 5 | 120 | 100 / 100 | +70 | 100 | 100% / 100% |
| Gián đoạn | 13 | 303 | 196 / 195 | +95 | 195 | 100% / 100% |
| Kết thúc | 13 | 303 | 300 / 299 | +104 | 299 | 100% / 100% |

Mốc 30 hoàn tất 18:14:40 UTC; mốc 100 hoàn tất 18:31:46 UTC ngày 26/09.
`milestone-030.json` và `milestone-100.json` lưu audit, độ dài và đầu/cuối
nội dung từng detail, hash JSONL, bộ đếm và checkpoint.

Tiến trình chặng cuối không còn tồn tại khi người dùng yêu cầu tiếp tục.
Manifest còn `running`: 195 dòng hợp lệ, 196 lần thử, một ID ở trạng thái
processing (`2070127`) chưa có phản hồi được lưu. **Không biết kết quả lần
thử dang dở này**, không gán nó thành HTTP thành công hay lỗi truy cập.
214 phản hồi đã lưu lúc đó đều HTTP 200, không challenge. Kiểm toán offline
195/195 record khớp HTML (`interrupted-at-195.json`).

Resume giữ nguyên bộ đếm 196, không xóa hoặc giảm số lần thử để đạt số tròn.
Không tải lại 195 detail đã hoàn thành, không tải lại 13 listing; chỉ phục hồi
job dang dở/pending. Với trần 300 lần thử, nếu những lượt còn lại đều thành
công thì raw sẽ đạt **299 ID**, không phải 300. Đây là mục tiêu khoảng 300
của người dùng, không có lý do mở cap hoặc chạy thêm batch để làm tròn.

## Lệnh và kiểm toán

Lệnh chung đã dùng; lần lượt đặt cặp `--max-pages/--max-details` là
`2/3` (gate trang 2), `2/30`, `5/100`, `13/300`; sau gián đoạn resume lại
`13/300`, không chạy đồng thời:

```bash
.venv/bin/job-crawler crawl timviec365 --mode bounded --fetcher http \
  --resume --resume-batch-id 20260926T174917Z-3a406cfa \
  --max-pages 13 --max-details 300 --delay-min 10 --delay-max 15 \
  --max-retries 0 --timeout 30 --save-html --require-complete-content \
  --project-owner-public-test \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

`--max-details` tính lần thử lũy kế, không phải số tin mới. Không tự resume
sau tín hiệu chặn. Không chạy lại lệnh khi đã đạt cap chỉ để chứng minh dedup;
đã kiểm thử resume offline và bằng các mốc live cùng batch.

Audit offline bằng `scripts/audit_timviec365_batch.py`: xác nhận ID/title/
company/canonical từ HTML detail, content hash, toàn bộ text hai section mô
tả/yêu cầu sau gộp whitespace, số ID duy nhất và số phản hồi thực đã lưu.
Không bù dữ liệu từ listing. Ngày nguồn gắn nhãn **Cập nhật**, nên giữ
`posted_at_raw=null`, không biến thành ngày đăng. Đủ toàn văn HTML không có
nghĩa nguồn đã cung cấp mọi thông tin tuyển dụng hoặc thông tin đã xác thực.

## Kết quả cuối và phân biệt lần thử với phản hồi

Kết thúc lúc **08:21:10 ICT ngày 27/09/2026** (01:21:10 UTC), status
`completed`, reason `max_details`. Chặng 100 → 299 tăng 199 record; hai dòng
cuối trong bảng tách đoạn gián đoạn và resume, không phải hai batch mới.

| Chỉ số cuối, lũy kế trong batch | Kết quả |
| --- | ---: |
| Listing thử / HTTP thành công / parse hoàn tất | 13 / 13 / 13 |
| ID chính duy nhất / overlap giữa trang | 303 / 0 |
| Lần thử detail được bộ đếm ghi nhận | 300 |
| Phản hồi detail HTTP 200 lưu được / URL duy nhất | 299 / 299 |
| Lần thử dang dở chưa biết kết quả | 1 |
| Detail lỗi có bằng chứng / challenge | 0 / 0 |
| Record JSONL hợp lệ / tổng ID duy nhất | 299 / 299 |
| ID ghi trùng / URL detail lặp trong phản hồi đã lưu | 0 / 0 |
| Mô tả toàn văn khớp HTML / yêu cầu toàn văn khớp HTML | 299 / 299 |
| Tiêu đề / công ty / lương / địa điểm có giá trị | 299 / 299 / 299 / 299 |
| Ngày đăng có giá trị | 0 — giữ null, không dùng ngày Cập nhật |
| Checkpoint completed / pending | 299 / 4 |

Tỷ lệ record hợp lệ trên **phản hồi detail đã lưu** là 100%; trên bộ đếm
300 lần thử là 99,67%. Không tự phân loại lần dang dở là thất bại HTTP hoặc
thành công. Không có bằng chứng tải lại ID đã hoàn thành: 299 phản hồi detail
đã lưu tương ứng 299 URL khác nhau. Không thể xác định lần dang dở đã tới máy
chủ hay chưa. ID dang dở đã được xử lý thành công trong resume.

`errors.jsonl` giữ **một lỗi listing parser lịch sử** ở trang 2 đã khôi phục
offline. Không xóa bằng chứng để tuyên bố toàn bộ đợt không có lỗi. Không có
401/403/429/challenge trong các phản hồi được lưu; không retry bằng công nghệ khác.

### Request thực tế theo phạm vi

- Riêng lần tiếp tục 195 → 299: **108 GET có phản hồi lưu được** = 4 kiểm tra
  điều kiện (robots/thỏa thuận/PDF ngoài batch + robots CLI) + 0 listing +
  104 detail. Không tải lại listing đã hoàn thành.
- Toàn bộ đợt mở rộng từ ba record ban đầu: **319 GET có phản hồi lưu được** =
  11 kiểm tra điều kiện + 12 listing mới + 296 detail mới; thêm một lần thử
  dang dở có trạng thái mạng chưa biết. Không tự tuyên bố tổng request thực
  tới máy chủ là 320. Chi tiết: `request-ledger.json`.
- Cả batch, tính cả ba record trước mở rộng: thư mục `http/` có **319** cặp
  metadata/body, gồm 7 robots + 13 listing + 299 detail, tất cả HTTP 200.
  Số 319 này có phạm vi khác dòng trên: gồm sáu phản hồi pilot ban đầu nhưng
  không gồm sáu phản hồi preflight ngoài batch. Không cộng hai số này với nhau.

Resume cuối chạy từ 07:57:41 đến 08:21:10 ICT, khoảng 23 phút 29 giây.
Khoảng cách bắt đầu GET trung bình 13,536 giây (~4,43 GET/phút), thấp nhất
11,093 giây. Đây là khoảng cách bắt đầu request thực đo; cấu hình nghỉ vẫn
10–15 giây sau phản hồi. `idle_seconds_min` trong audit dùng thời điểm ghi
metadata sau nén body, nên có thể nhỏ hơn 10 giây vài mili giây; không dùng
trường này để suy diễn crawler giảm khoảng nghỉ cấu hình.

### Đối chiếu toàn văn

Audit **299/299 record**, không chỉ ba mẫu. Khoảng độ dài mô tả 120–3.176 ký
tự, yêu cầu 90–1.588 ký tự; các phần ngắn vẫn được so sánh với toàn bộ section
HTML, không tự coi độ ngắn là parser cắt nội dung.

| ID mẫu | Ký tự mô tả | Ký tự yêu cầu | Toàn bộ section khớp HTML |
| --- | ---: | ---: | --- |
| 2070499 — tin đầu cũ | 672 | 593 | Có |
| 2070386 — mốc 30 | 668 | 413 | Có |
| 2070308 — mốc 100 | 788 | 453 | Có |
| 2070127 — phục hồi sau gián đoạn | 813 | 1099 | Có |
| 2069081 — tin cuối | 767 | 436 | Có |

Độ dài, 80 ký tự đầu/cuối của từng section và kết quả khớp nằm trong
`milestone-final-299.json`; tóm tắt trong `final-summary.json`. Đối chiếu thêm
ID, canonical URL, tiêu đề, công ty và tính lại content hash đều đạt.
`working_time` thiếu 15/299; các trường chưa ánh xạ như category/profession/
specialization/company metadata vẫn cần đánh giá, không suy ra website không
có chúng. Lương là literal từ DOM, chưa xác minh nghiệp vụ hoặc độc lập với nguồn.

## Vị trí dữ liệu và bảo toàn

```text
data/raw/timviec365/snapshot_date=2026-09-27/batch_id=20260926T174917Z-3a406cfa/
  jobs.jsonl                 # 299 dòng, 299 ID
  manifest.json
  checkpoint.sqlite3        # 299 completed, 4 pending
  errors.jsonl              # 1 lỗi listing đã khôi phục; không xóa
  html/                     # 13 listing + 299 detail gzip
  http/                     # 319 metadata/body gzip
```

SHA-256 jobs cuối:
`296f67ec9e5b5d6be9c717c6135b09460be85b53f1a0ddb6f5940e8f64460bc2`.

Đối chiếu với `baseline-raw.json`: **567 file của các nguồn khác không đổi**,
gồm CareerViet 299 record, CareerLink 55 record, VietnamWorks và checkpoint.
16 file HTML/HTTP Timviec365 có trước đợt mở rộng không đổi. Tiền tố JSONL
3/30/100/195 dòng đều giữ nguyên byte so với checksum ở từng mốc. Chỉ nối thêm
dòng và cập nhật state/manifest/error log của chính batch Timviec365.

## Code, test, Git và giới hạn

Phần mở rộng sửa README, `config.py`, `cli.py`, `engine.py` để có bounded
13/300 và chuyển sample đủ ba detail sang bounded với batch chỉ định rõ.
Giữ HTTP/saved HTML/complete-content/delay >=10/no retry; không mở full snapshot.
Sửa pagination trong `parsers/timviec365.py`, bổ sung fixture `page2_arrows.html`,
logic khôi phục offline `storage/timviec365_recovery.py` và công cụ audit.
Test ở `tests/integration/test_timviec365_bounded.py` kiểm tra cap/guard,
resume/dedup, chuyển mode, recovery idempotent, phát hiện text cắt/ID trùng,
và lần thử dang dở vẫn được tính cap mà không tải lại detail đã hoàn thành.
Adapter/fetcher/ba fixture detail và báo cáo followup đã có từ lượt trước được giữ.

Lệnh kiểm tra cuối:

```bash
.venv/bin/pytest -q -m 'not live'        # 205 passed
.venv/bin/ruff format --check .        # 94 files already formatted
.venv/bin/ruff check .                 # passed
.venv/bin/mypy src                     # 43 source files, passed
git diff --check                       # passed

.venv/bin/python scripts/audit_timviec365_batch.py \
  data/raw/timviec365/snapshot_date=2026-09-27/batch_id=20260926T174917Z-3a406cfa \
  --output data/diagnostics/timviec365_expansion/20260926T180022Z/milestone-final-299.json
```

Git vẫn nhánh `main`, HEAD `2eef4fee4aba3fe2284325b967c34a58944f76cf`.
Không stage/commit/push, không reset hoặc xóa thay đổi cũ. Tracked thay đổi:
README, CLI, config, engine, fetcher factory. Các file Timviec365 mới, fixture,
audit, test, báo cáo còn untracked. Artifact raw/diagnostics vẫn ignored;
không đưa HTML/JSONL hoặc PDF lên Git. Diff tracked không bao gồm các file
untracked; cần đọc cả hai nhóm khi review.

**Đã kiểm chứng batch nhiều trang ở quy mô 299 detail**, vượt bằng chứng 3/3
của probe. Chưa chứng minh ổn định dài hạn, toàn bộ website, tin luôn còn hạn,
đủ mọi trường nghiệp vụ hoặc quyền tái xuất bản. Không tự mở rộng thêm hoặc
làm Bronze/Silver. Bốn ID pending được giữ; lệnh cùng cap 300 không lấy thêm
record, và không được tăng cap/chạy lại khi có tín hiệu chặn.
