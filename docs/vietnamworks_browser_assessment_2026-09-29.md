# VietnamWorks — browser-first, main listing và batch raw, 29/09/2026

## Phạm vi và tiến độ đã kiểm chứng

Theo yêu cầu mới của chủ dự án, chọn **Chrome thường có giao diện ngay từ đầu**
tại `https://www.vietnamworks.com/viec-lam`. Không chạy HTTP listing trước,
không dùng browser để né một phản hồi chặn mới. Không đăng nhập, stealth, proxy,
CAPTCHA solver, đổi User-Agent hoặc gọi API độc lập.

Lượt mới đã đọc được listing chính và **3/3 detail mới đầy đủ**; pilot tiếp theo
đã ghi **20/20 detail raw hợp lệ**, audit toàn văn HTML đạt, không lỗi/trùng ID.
Mốc **100 raw đã audit đạt**, sau 102 lượt detail. Sau bàn giao và resume trong
Terminal, batch kết thúc ở trần **300 lượt thử với 295 raw / 295 ID duy nhất**.
Rà soát để commit ngày 29/09 audit **offline toàn bộ 295 record**, không gửi thêm
request live. Không gọi 300 lượt thử là 300 detail thành công.

| Giai đoạn đã kiểm chứng | Listing main thành công | ID main duy nhất | Detail thử / hợp lệ | Raw thực ghi |
| --- | ---: | ---: | ---: | ---: |
| Probe browser mới | 1 | 50 | 3 / 3 | 0 — diagnostic riêng |
| Pilot batch mới | 2 | 99 | 20 / 20 | 20 |
| Trần 100 lượt detail, lũy kế | 3 | 141 | 100 / 98 | 98 |
| Mốc 100 raw, lũy kế | 3 | 141 | 102 / 100 | 100 |
| Kết thúc trần 300 lượt, lũy kế | 8 | 351 | 300 / 295 | 295 |

Không dùng 330 ID gợi ý của `/tim-viec-lam` làm main. Không chép ba HTML
chẩn đoán cũ vào raw. Hai URL sau là **hai loại trang khác nhau**, dù tên gần nhau:

- `/tim-viec-lam`: landing các nhóm tuyển gấp/hot/lương cao; lượt HTTP trước
  đọc được nhưng không xác minh main search/pagination.
- `/viec-lam`: listing tìm kiếm chính; lượt browser mới chuyển **308** sang
  `/tim-viec-lam/tim-tat-ca-viec-lam`, rồi **200**. Sau render có 50 main card.

Giữ [báo cáo landing trước](vietnamworks_reassessment_2026-09-29.md),
[pilot 403 cũ](vietnamworks_batch_pilot_2026-09-26.md) và
[đối chiếu chính sách/OCR cũ](vietnamworks_policy_check_2026-09-26.md) nguyên trạng.
Lỗi cũ không được gán cho phép thử mới; ba detail cũ không phải record batch cũ,
batch đó vẫn 0 dòng và checkpoint/lỗi/HTML được giữ nguyên.

## Robots, điều khoản và cơ sở quyết định

Tái sử dụng đúng bằng chứng kiểm tra gần nhất, cùng ngày và khoảng 22 phút trước
probe browser: `data/diagnostics/vietnamworks_reassessment/20260929T083452Z/`.
Robots tại https://www.vietnamworks.com/robots.txt lúc **08:35:46 UTC** trả 200,
SHA-256 `1f9cda1409f861260997f9df57750333a76892ef20b3eed9e12e0173154d3aeb`.
Đối chiếu hash body trước tái sử dụng, đọc BOM UTF-8 và kiểm tra mỗi URL/hop
bằng RobotFileParser cùng guard wildcard bảo thủ. Không Disallow khớp
`/viec-lam`, `?page=2`, route sau redirect hoặc ba detail định mở.

Thỏa thuận https://www.vietnamworks.com/thoa-thuan-su-dung lúc **08:36:32 UTC**
trả 200; toàn văn đã đọc ở lượt ngay trước. Quyền từ chối dịch vụ, giới hạn
mục đích và giới hạn sao chép vẫn tồn tại; ngoại lệ bản sao dùng nội bộ không
nêu ngưỡng số lượng hợp lý. Không xác nhận quyền tái công bố/khai thác thương mại
hoặc quyền do chủ nguồn cấp. PDF/OCR lịch sử được đối chiếu offline, không tải lại.

Probe browser không gửi request điều kiện mới vì bằng chứng gần nhất phù hợp.
CLI batch/resume kiểm tra robots lại qua chính browser được chọn; từng phản hồi
được lưu riêng, robots không tải được thì trạng thái quyền truy cập là chưa biết.
Trong batch cuối có **5 lượt robots HTTP 200**. Bản browser bỏ BOM nên SHA-256
body là `0dcd8c48107acbcb11095f22da1c9ed4ebeecc9bccd51869904bd8dfedd468cb`;
dòng quy tắc trùng bản HTTP đã đọc, không phải thay đổi quyền truy cập.
401/403/429 hoặc challenge vẫn dừng nguồn, không đổi công cụ để thử lại.

`owner-decision.json` ghi `access_basis=project_owner_public_test`,
`authorization_reference=null`, `source_authorization=false`. Đây là quyết định
của chủ dự án, **không phải chấp thuận của VietnamWorks**. Body/HTML chỉ giữ cục bộ,
không đưa vào GitHub hoặc công bố toàn văn.

## Listing mới và pagination

Probe bắt đầu điều hướng **08:58:08 UTC (15:58:08 ICT)**. Body HTTP cuối được
lưu ngay trước đọc DOM: 319.953 byte, SHA-256
`e5219329ba4c05652ad3fc89c42fef812e3ab422c66f2a760dc337d15157902f`.
Body thô có **0 ID main**, `Loading` xuất hiện 14 lần và 5 ID nổi bật.
Sau render/cuộn đến pagination có **50 `.block-job-list .search_list` card,
50 ID main duy nhất**, `Loading=0`. Các card `.out-stading-jobs` không enqueue.
HTML sau render và ảnh chụp được lưu, không bỏ mất body HTTP ban đầu.

UI có nút 1–7 và `>`; parser yêu cầu active page trùng query `page`.
Trang 2 `https://www.vietnamworks.com/viec-lam?page=2` đã truy cập **thật trong
pilot**, HTTP 200, active page 2, 50 ID, một overlap với trang 1 → **99 ID main**.
Next của trang 2 là `?page=3`; trang 3 cũng được mở thật, 50 ID, 42 ID mới.
Ba trang đã thấy 150 card, union 141 ID, overlap 9; không gọi carousel gợi ý
là pagination main. ID trên các trang live có thể thay đổi theo thời gian.
Kết thúc: **tám trang chính thực truy cập**, mỗi trang 50 card; 400 occurrence,
49 overlap, union **351 ID main**. Số ID mới từng trang: 50, 49, 42, 33, 39,
49, 47, 42. Link next trang 8 là `?page=9`, chỉ lưu pending, **chưa truy cập**.

UI của phiên Chrome thành công tự tải
`https://ms.vietnamworks.com/job-search/v1.0/search` (HTTP 200).
Metadata ghi endpoint/status/method; crawler **parse card DOM**, không gọi endpoint
riêng, không dò API nội bộ và không sử dụng JSON sau phản hồi chặn.
Browser tải script/ảnh/font/telemetry như một phiên bình thường: phân biệt số
điều hướng listing/detail với tổng tài nguyên trang, không gọi một navigation
là toàn bộ số request mạng của browser.

## Ba detail mới từ chính listing

| ID mới / hậu tố URL | HTTP | Mô tả ký tự | Yêu cầu ký tự | Lương raw | Địa điểm raw |
| --- | ---: | ---: | ---: | --- | --- |
| 2113254 / `-jv` | 200 | 1070 | 936 | Thương lượng | Hung Yen, Hai Duong, Ha Noi |
| 2113253 / `-jv` | 200 | 1372 | 1115 | $$ 400-1,300 /tháng | Ho Chi Minh, Da Nang |
| 2113132 / `-jv` | 200 | 1142 | 1850 | Thương lượng | Binh Duong |

Từng ID khớp canonical URL, title khớp h1, company khớp link nhà tuyển dụng trên
chính detail. Hai trường toàn văn khớp section DOM sau chuẩn hóa khoảng trắng;
audit ghi độ dài, hash, 100 ký tự đầu/cuối. Bỏ banner hỏi mức độ phù hợp ứng viên,
không lấy preview listing, related job hoặc nội dung đăng nhập để điền thiếu.

Ngày raw lấy từ **`onlineOn` trong payload inline của detail**, lần lượt
`2026-09-29T15:57:18+07:00`, `2026-09-29T15:56:31+07:00`,
`2026-09-29T15:55:30+07:00`. Không suy từ dòng “Cập nhật” trên listing;
không tuyên bố đã đối chiếu với nhãn ngày đăng độc lập trên UI (mẫu không có nhãn đó),
không tự ước lượng ngày. Metadata này cần phân biệt với xác minh ngày đăng gốc
khi chuẩn hóa về sau; precision của model chưa tự đổi thành ngày chính xác.

Ba record mới lưu ở `new-main-probe-records.jsonl` **diagnostic**, raw=0 tại
giai đoạn probe. Pilot tải lại main hiện hành, thứ tự đã thay đổi; 20 ID raw của
pilot không trùng ba ID mẫu mới. Không cộng “3 + 20” thành 23 dòng raw.

## Batch, giới hạn và resume

Batch mới:
`data/raw/vietnamworks/snapshot_date=2026-09-29/batch_id=20260929T091457Z-1d8023a1/`.
File đích: `jobs.jsonl`; cùng thư mục có manifest, errors, checkpoint, HTML gzip,
`http/` lưu body/status/DOM trước mọi phân loại lỗi.

Pilot: **20 dòng = 20 ID duy nhất**, 20/20 title/company/description/requirements;
lương, địa điểm và `onlineOn` cũng 20/20. Toàn văn DOM khớp **20/20**, không có
lỗi truy cập hoặc parser. Mô tả ngắn nhất 127 ký tự vẫn là toàn bộ section được
nguồn trả, không tự coi ngắn là parser cắt. Yêu cầu dài 464–1858 ký tự.
Checkpoint sau pilot: 20 completed, 79 pending; 2 listing completed, trang 3 pending.

Lệnh pilot đã chạy:

```bash
JOB_CRAWLER_BROWSER_EXECUTABLE_PATH=/usr/bin/google-chrome \
.venv/bin/job-crawler crawl vietnamworks --mode bounded \
  --start-url https://www.vietnamworks.com/viec-lam \
  --project-owner-public-test --fetcher playwright --headed \
  --max-pages 2 --max-details 20 --delay-min 10 --delay-max 15 \
  --max-retries 0 --timeout 45 --save-html --save-screenshot-on-error \
  --require-complete-content \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

Resume **batch mới**, giữ cùng start URL/mode/parser; trần `max-details` là lần
thử **lũy kế**, không phải số record mới được bảo đảm. Đợt 3/100 đạt 98 raw;
sau sửa chờ hydration, đợt 3/102 thêm hai ID pending mới đạt đúng 100 raw.
Trần tiếp theo tối đa 8/300 chỉ sau audit 100 ổn định. Cùng các cờ bên trên,
thêm `--resume --resume-batch-id 20260929T091457Z-1d8023a1`.
Không resume batch cũ 0 dòng, không tự resume sau tín hiệu từ chối.

Hai ID `2113190` và `2098899` trả HTTP 200, có toàn văn payload inline nhưng
DOM chỉ có h2 và div section rỗng lúc capture. Parser từ chối, hai ID ở trạng
thái failed được giữ nguyên, không retry và không lấy payload làm record rồi
khai là đã khớp DOM. `render-readiness-errors.json` đối chiếu nguyên nhân.
Fetcher được sửa chờ **cùng trang** tối đa 15 giây cho hai section có nội dung
trước capture; không thêm navigation, không thay công cụ/danh tính. Nếu vẫn
không render thì dừng terminal và giữ bằng chứng 200, không ghi là bị chặn.
Hai test offline mới kiểm tra delayed hydration và timeout không retry.

Audit mốc 100 raw: 100/100 toàn văn khớp DOM; title/company đủ 100/100,
không ID trùng; 20 dòng pilot giữ nguyên byte. 102 URL detail khác nhau đều
HTTP 200, source denial = 0. Checkpoint: 100 completed, 2 failed, 39 pending;
3 listing completed, trang 4 pending. Exit code 2 của các lần resume phản ánh
hai lỗi cũ trong manifest lũy kế, không phải hai lượt mới thất bại.

### Kết quả cuối và điểm dừng

Manifest kết thúc **10:47:37 UTC (17:47:37 ICT)**, `completed_with_errors`,
`termination_reason=max_details`, `detail_requested=300`, `detail_succeeded=295`,
`detail_failed=4`. Một slot gián đoạn không được ghi thành lỗi HTTP hoặc thành công.
Tỷ lệ record hợp lệ trên lượt thử **295/300 = 98,33%**; độ đầy đủ mô tả/yêu cầu
trên record đã ghi **295/295 = 100%**, không tính listing hoặc diagnostic cũ.

Hai lỗi hydration kể trên giữ nguyên. Hai lỗi parser sau resume, đều HTTP 200:

- `2104996`: tên công ty DOM không khớp hoặc không có trong link nhà tuyển dụng
  để đối chiếu payload; chưa xác định nguyên nhân nguồn, không tự điền từ listing.
- `2113147`: không tìm thấy payload detail khớp ID, không dùng related job thay thế;
  chưa xác định đây là tin hết hạn, bị gỡ hay thay đổi cấu trúc.

Không retry bốn ID failed. ID `2101226` có một lần đã lưu body HTTP 200 nhưng
chưa capture DOM khi dừng để bàn giao; resume xử lý lại đúng ID unfinished này.
Vì vậy **300 điều hướng detail / 299 URL detail khác nhau**, không phải 300 ID;
không tải lại ID đã completed và không ghi duplicate raw. Bằng chứng lần gián
đoạn không bị xóa. Trong toàn batch có 313 navigation chính gồm 5 robots,
8 listing và 300 detail; các final status quan sát đều 200, source denial = 0. Redirect 308
đầu listing được lưu riêng; đây không phải tổng số request asset/XHR của browser.

Checkpoint cuối: **295 completed, 4 failed, 52 pending detail**; tám listing
completed, trang 9 pending. Trần 300 đã dùng hết: chạy lại cùng `--max-details 300`
không thêm raw; chưa có phê duyệt/code để vượt trần này và không tự mở rộng.
Delay cấu hình 10–15 giây, một luồng; khoảng nghỉ nhỏ nhất thực đo từ metadata
capture hoàn tất đến navigation kế tiếp **10,117 giây**; không automatic retry.

Audit từng JSONL với h1, công ty, toàn văn hai section DOM và reparse Flight đạt
**295/295**, 0 ID trùng. Byte-prefix 20 dòng pilot và 100 dòng mốc trước nguyên vẹn.
SHA-256 `jobs.jsonl`:
`b3c36a2149f76bb4bced8379c5c2f31010900f5ef7e7cbcdaeb282778df48b2e`.
Mô tả min/median/max = **102 / 1281 / 6291** ký tự;
yêu cầu = **123 / 1000 / 4326**. Ngắn không đồng nghĩa bị cắt.

| Trường có dữ liệu | VietnamWorks raw cuối | CareerViet tham chiếu | Timviec365 tham chiếu | Việc Làm 24h tham chiếu |
| --- | ---: | ---: | ---: | ---: |
| Record detail / ID duy nhất | 295 / 295 | 299 / 299 | 299 / 299 | 104 / 104 |
| Tiêu đề, công ty, mô tả, yêu cầu | 295/295 mỗi trường | 299/299 | 299/299 | 104/104 |
| Lương / địa điểm | 295/295 | 299/299 | 299/299 | 104/104 |
| Ngày raw có dữ liệu | 295/295 (`onlineOn`, chưa xác minh ngày đăng gốc) | 299/299 | 0/299 | 104/104 |
| Quy mô công ty | 152/295 | 0/299 | 0/299 | 0/104 |
| Bằng cấp / benefits tách riêng | 0/295 / 0/295 | 299/299 / 295/299 | 299/299 / 299/299 | 70/104 / 104/104 |

Địa chỉ làm việc chi tiết có 266/295 (thiếu 29); company size thiếu 143.
Các trường mở rộng chưa map để null/array rỗng, không diễn giải là nguồn không
công bố. Đã đạt batch nhiều detail thật, lớn hơn mẫu Việc Làm 24h 104 trong
repository, nhưng không suy ra dữ liệu giàu mọi trường như CareerViet hoặc
khả năng crawl toàn website ổn định trong tương lai.

## Tích hợp và kiểm thử

- Fetcher mới `src/job_crawler/fetchers/vietnamworks_browser.py`: browser-first,
  guard URL/robots/redirect, evidence trước DOM, theo dõi denial document/XHR/fetch,
  không fallback/retry, latch stop và giữ nguyên lỗi gốc nếu capture DOM thất bại.
- Factory chọn fetcher này **chỉ** cho VietnamWorks + `playwright`; HTTP/auto cũ
  và fetcher nguồn khác giữ nguyên. Config/CLI cho owner `bounded` riêng 8/300,
  bắt buộc headed, HTML/full content, delay >=10, retries=0.
- Parser `vietnamworks-1.1.0` đối chiếu h1/company và toàn văn DOM với Flight;
  HTTP payload vẫn parse offline được. Field thiếu giữ `null`, không bù từ listing.
- Engine dừng cả lỗi listing `terminal=True`, không tiêu tốn thêm detail pending
  sau fetcher đã stop; kiểm thử riêng cho nhánh này.
- Fixture mới nhỏ `rendered_detail_20260929.html`; test browser/config/capture/
  200 challenge/JSON403/DOM error/truncation/terminal listing, không gọi website.
- `scripts/audit_vietnamworks_batch.py` kiểm toán từng raw với HTML, ID main,
  metadata, độ dài/hash và checkpoint, phát hiện raw bị cắt bằng test fixture.

Audit offline đã chạy tại mốc 20:

```bash
.venv/bin/python scripts/audit_vietnamworks_batch.py \
  data/raw/vietnamworks/snapshot_date=2026-09-29/batch_id=20260929T091457Z-1d8023a1 \
  data/diagnostics/vietnamworks_browser_reassessment/20260929T085609Z/pilot20-audit.json
```

Audit offline cuối trong lượt rà soát commit:

```bash
.venv/bin/python scripts/audit_vietnamworks_batch.py \
  data/raw/vietnamworks/snapshot_date=2026-09-29/batch_id=20260929T091457Z-1d8023a1 \
  .runtime/git_publish_20260929/vietnamworks-final-audit.json
```

Artifact `.runtime/` cũng bị Git ignore; file kiểm toán này không đi cùng clone.

Kiểm tra cuối trong lượt publish (không chạy crawler/live test):

```bash
.venv/bin/pytest -q -m 'not live'   # 278 passed
.venv/bin/ruff format --check .   # 113 files already formatted
.venv/bin/ruff check .            # All checks passed
.venv/bin/mypy src                # 47 source files, passed
git diff --check                  # passed
```

Audit offline Việc Làm 24h cũng đạt 104/104 toàn văn, không trùng ID. Raw và
checkpoint không được sửa trong lượt rà soát/publish; checksum kiểm tra riêng
tại `.runtime/git_publish_20260929/` (artifact cục bộ).

## Bằng chứng và giới hạn diễn giải

Artifact **cục bộ, Git ignored**:
`data/diagnostics/vietnamworks_browser_reassessment/20260929T085609Z/`:
`before.json`, `owner-decision.json`, `listing.json`, `listing.http.body.gz`,
`listing.rendered.html.gz`, `listing.png`, `details/<ID>/response.json` và HTML/ảnh,
`new-main-detail-audit.json`, `new-main-probe-records.jsonl`, `pilot20-command.json`,
`pilot20.log`, `pilot20-audit.json`, các command/log/audit mốc tiếp theo.
Clone Git không có các artifact này; không đưa raw/body/ảnh/log hoặc bí mật lên GitHub.

Kết quả kỹ thuật không chứng minh tin chính xác, nhà tuyển dụng được xác thực,
công việc còn tuyển thật hoặc metadata `onlineOn` là ngày đăng đầu tiên. Không
gọi record giàu mọi trường như CareerViet: company size/address, education,
benefits tách riêng và ngành nghề có thể thiếu/chưa map, dù hai section lõi đầy đủ.
Trong các lượt crawl không stage/commit/push. Lượt rà soát sau đó chỉ đưa code,
test, fixture nhỏ và tài liệu lên Git theo yêu cầu mới; raw/HTML/checkpoint/log
vẫn cục bộ. CareerViet 299, Timviec365 299, CareerLink 75, Việc Làm 24h 104 và
batch VietnamWorks cũ 0 dòng được giữ nguyên. Không chạy live trong audit/publish.
