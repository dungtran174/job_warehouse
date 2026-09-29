# JobOKO — probe live theo ngoại lệ chủ dự án, 28/09/2026

## Kết quả thực tế

**Đã thực hiện probe live**, không dừng ở quy tắc cũ: **5 HTTP GET**, gồm
1 robots, 1 URL dự định làm listing và 3 detail, tất cả HTTP 200, không redirect,
không challenge hoặc lỗi HTTP. Ba detail có ID khác nhau và đủ tiêu đề, công
ty, toàn bộ mô tả/yêu cầu mà JobOKO trả về trong HTML. Không cần Playwright.

**Giới hạn listing cần giữ rõ:** `/tim-viec-lam` thực tế là hub gồm các khối
HOT/nổi bật/ngành, không phải trang kết quả tìm kiếm chính có phân trang đã
được xác minh. Mẫu detail lấy từ tab **Gần đây, `#newest-job`**, 30 URL/ID thật
trong hub, không lấy tab HOT hoặc liên kết tin tương tự trên detail. Tab này
vẫn nằm trong section “Việc làm nổi bật”; **không gọi nó là main search listing
đầy đủ hoặc 30 tin organic đã xác minh**. Không gửi thêm listing để tìm trang
khác vì giới hạn đã dùng một URL. Kết quả đọc được ba detail không giải quyết
câu hỏi discovery nhiều trang, phân trang hoặc khả năng batch ổn định.

| Chỉ số | Thực tế trong lượt này |
| --- | --- |
| Request kiểm tra robots | 1, HTTP 200 |
| Listing URL thử / đọc HTML thành công | 1 / 1, HTTP 200; thực tế là hub |
| Main search listing được xác minh / ID main | **Chưa xác minh / chưa đo** |
| ID job duy nhất toàn hub / tab Gần đây | 118 / 30; không phải số detail đã crawl |
| Detail thử / truy cập được / đủ trường bắt buộc | **3 / 3 / 3** |
| ID detail duy nhất | **3**: 6736098, 6736096, 6736095 |
| Record diagnostic JSONL thực ghi | **3** |
| Record raw `jobs.jsonl` / batch hoặc checkpoint mới | **0 / không tạo**, đây chỉ là probe |
| Có mô tả / yêu cầu từ detail | **3/3 và 3/3 (100%)** trong HTML trả về |
| Có lương / địa điểm / `datePosted` | 3/3 mỗi trường, không bù từ listing |
| Lỗi HTTP / CAPTCHA/challenge | **0 / 0** |
| Browser / retry / request host khác | **0 / 0 / 0** |
| Điểm dừng | Đã dùng hết mẫu tối đa 1 URL listing / 3 detail |

Record: `data/diagnostics/joboko_owner_probe/20260928T162502Z/detail-records.jsonl`.
Đây **không** phải `data/raw/.../jobs.jsonl`, không phải pilot, không tích hợp
crawler và không dùng 3 mẫu để tuyên bố nguồn đạt batch hàng trăm tin.

## Quyết định nội bộ và phạm vi quyền

Đọc README, AGENTS.md, báo cáo JobOKO cũ, CLI/config và công cụ probe trước sửa.
Theo yêu cầu mới trong chat, sửa **đúng README và AGENTS.md** để thêm ngoại lệ
riêng cho một probe JobOKO tối đa 1 listing/3 detail, dù đã biết hạn chế crawler
trong điều khoản. Giữ quy tắc dừng khi robots cấm hoặc HTTP 401/403/429,
CAPTCHA/challenge, kể cả HTTP 200. Không mở `bounded`, không sửa CLI/config hay
code các nguồn cũ, không cho phép lần chạy batch tiếp theo bằng ngoại lệ này.

`owner-decision.json` ghi yêu cầu thật của chủ dự án trước request:
`access_basis=project_owner_public_test`, `authorization_reference=null`,
`source_permission_claimed=false`, `data_usage_rights_verified=false`.
**Không có chấp thuận của JobOKO**. Quyết định nội bộ không thay đổi điều khoản
website hoặc xác nhận quyền khai thác, chia sẻ/tái công bố toàn văn.

Điều khoản §3 hạn chế bot/crawler đã được kiểm chứng trong [báo cáo gốc](joboko_assessment_2026-09-28.md)
và HTML lưu lúc 14:39 UTC. Không tải lại điều khoản trong probe, không tuyên bố
đã xác minh bản online mới nhất. Lưu HTML và record theo phạm vi quyết định
nội bộ, chỉ làm bằng chứng cục bộ, không công bố raw hoặc dữ liệu liên hệ.
Giữ nguyên báo cáo [lượt dừng theo quy tắc cũ](joboko_limited_probe_2026-09-28.md)
và [khảo sát các nguồn bổ sung](additional_sources_assessment_2026-09-28.md):
đó là kết quả lịch sử, không sửa counter/decision cũ thành đã thử live.

## Robots hiện tại và các request thật

[Robots JobOKO](https://vn.joboko.com/robots.txt) HTTP 200 lúc
**2026-09-28T16:26:13.258532 UTC**, URL cuối giữ nguyên. SHA-256:
`b3d2660b4179fa8b71662be25c0c6b4febec860aba5c8ca2c3a259b1e197b963`.
Body trùng bản robots đã lưu trước đó, nhưng lần này là request mới thực sự.

Nhóm áp dụng cho User-Agent minh bạch của dự án là `*`; các nhóm bot riêng bị
cấm `/` không được áp dụng nhầm. Đối chiếu wildcard trên path + query: **không
có Disallow khớp `/tim-viec-lam` hoặc ba URL detail bên dưới**. Không gọi vùng
tài khoản/CV/ajax hoặc các route `/jobs?*`, `/rd?*`, `/rdn?*` bị cấm.
`robots-analysis.json` và `detail-robots-analysis.json` lưu kết quả cho đúng URL.
Request hook kiểm tra lại host/robots trước từng request, kể cả nếu redirect;
thực tế không có redirect. Không coi robots cho phép là giấy phép sử dụng dữ liệu.

| Mục đích | URL yêu cầu = URL cuối | Bắt đầu UTC 28/09 | HTTP |
| --- | --- | --- | ---: |
| Robots | https://vn.joboko.com/robots.txt | 16:26:13.258532 | 200 |
| Listing dự định, thực tế hub | https://vn.joboko.com/tim-viec-lam | 16:27:33.580817 | 200 |
| Detail 6736098 | https://vn.joboko.com/viec-lam-nhan-vien-bao-ve-xvi6736098 | 16:29:32.589021 | 200 |
| Detail 6736096 | https://vn.joboko.com/viec-lam-giao-vien-tieng-anh-lam-viec-tai-tan-phu-thu-duc-quan-7-go-vap-dong-hoa-xvi6736096 | 16:30:26.085192 | 200 |
| Detail 6736095 | https://vn.joboko.com/viec-lam-thuc-tap-sinh-tuyen-dung-xvi6736095 | 16:30:36.583457 | 200 |

Giờ Việt Nam = UTC + 7, khoảng 23:26–23:30 ngày 28/09. HTTP một luồng, nghỉ
**ít nhất 10 giây trước mỗi GET**, không chạy đồng thời nhiều detail. Không
retry, đăng nhập, cookie xác thực, stealth, proxy rotation, CAPTCHA solver,
API nội bộ, tắt TLS hoặc tải tài nguyên ảnh/script trong HTML. Không cần browser
vì nội dung cần thiết có sẵn trong HTTP. Không thêm request sau detail thứ ba.

## Đối chiếu ba detail với HTML

| ID / tiêu đề / công ty từ detail | Ký tự mô tả / yêu cầu | Lương raw | Địa điểm từ header detail | Ngày đăng JSON-LD / hạn nộp DOM |
| --- | ---: | --- | --- | --- |
| 6736098 — Nhân Viên Bảo Vệ — Công Ty Cổ Phần Đầu Tư Và Xây Dựng Phúc Khang | 204 / 284 | 7 - 9 triệu VNĐ | Hồ Chí Minh, Long An | 2026-09-28 / 28/10/2026 |
| 6736096 — Giáo Viên Tiếng Anh Làm Việc Tại Tân Phú, Thủ Đức, Quận 7, Gò Vấp, Đông Hòa — AGENA TRAINING AND EDUCATION COMPANY LIMITED | 412 / 320 | 5 - 15 triệu | Hồ Chí Minh, Bình Dương | 2026-09-28 / 24/10/2026 |
| 6736095 — Thực Tập Sinh Tuyển Dụng — MindX Technology School - CÔNG TY CỔ PHẦN TRƯỜNG HỌC CÔNG NGHỆ MINDX | 275 / 499 | 2 triệu - 3 triệu | Hà Nội | 2026-09-28 / 28/11/2026 |

Audit offline độc lập trên body gốc:

- ID số sau `-xvi` khớp URL trong hub, URL cuối và canonical detail; ba ID
  khác nhau. **Không lấy `JobPosting.identifier` làm job ID**: payload này
  chứa ID công ty 500, 630148, 391131. Chưa kiểm chứng ID qua nhiều thời điểm.
- H1 và tên công ty trên H2 detail khớp `JobPosting` JSON-LD. Không lấy công
  ty/tiêu đề/content của tin tương tự hoặc dữ liệu listing để bù trường thiếu.
- Lấy toàn bộ `.job-desc` và `.job-requirement` từ DOM detail, đúng một section
  mỗi loại. Văn bản từng section sau chuẩn hóa khoảng trắng **khớp toàn bộ**
  section tương ứng trong `JobPosting.description`: **6/6 đối chiếu đạt**.
  `detail-audit.json` lưu độ dài, hash, đoạn đầu/cuối và cờ đối chiếu.
- Nội dung ngắn không đồng nghĩa parser cắt preview; DOM và JSON-LD đều chứa
  nguyên phần được trích. Dấu ba chấm do nguồn viết vẫn được giữ, không tự
  bổ sung. Không chứng minh nội dung gốc của nhà tuyển dụng còn dài hơn hay
  dữ liệu ẩn sau tài khoản; không tìm cách mở phần nguồn đã che.
- Lương lấy nguyên tooltip header detail, khớp giá trị text JSON-LD; địa điểm
  lấy header detail. Giữ nhiều địa điểm, không suy từ tiêu đề/listing.
- Địa chỉ chi tiết lấy `.job-work-places` khi có. Tin AGENA không có section
  này nên lấy địa chỉ có trong JSON-LD của **chính detail**; địa chỉ đường phố
  cho Bình Dương không được nguồn cung cấp, không tự dùng địa chỉ Hồ Chí Minh
  thay thế. Hà Nội ở tin MindX chỉ là địa chỉ mức thành phố, không giả địa chỉ phố.
- `posted_at_raw` giữ `datePosted` JSON-LD, không phải ngày cập nhật hay hạn
  nộp. Cả ba cùng khai báo 28/09; chưa xác minh đây là ngày xuất bản đầu tiên
  hay repost/refresh. Hạn nộp DOM khớp `validThrough`; đều chưa hết hạn theo
  ngày nguồn khai báo, chưa xác minh thực tế nhà tuyển dụng còn tuyển.
- Không thiếu bảy trường lõi của mẫu: title/company/description/requirements/
  salary/location/datePosted. Trường mở rộng chưa được trích/không xuất hiện
  vẫn `null`; không gọi đó là đo độ đầy đủ toàn bộ schema CareerViet.
- Ba payload có metadata, HTML path và `job_content_hash`, được
  `JobRecord.model_validate`. JSONL diagnostic có đúng ba dòng, không trùng ID.

Trang detail đều nằm trên `vn.joboko.com`. Có UI chuyển sang link gốc để ứng
tuyển, nhưng **không bấm, không crawl host khác**. Không xác nhận tin hoặc
doanh nghiệp là đáng tin chỉ vì đủ trường và HTTP 200.

## Bằng chứng, kiểm tra và Git

Thư mục: `data/diagnostics/joboko_owner_probe/20260928T162502Z/`.
Tất cả đường dẫn `data/` là **artifact cục bộ, không commit**, không có khi clone.

- `owner-decision.json`: quyết định mới thật, giới hạn, không chấp thuận nguồn.
- `robots.json`, `listing.json`, `detail-1.json` đến `detail-3.json`:
  status/URL/thời điểm/SHA-256; body gzip tương ứng lưu trước phân tích.
- `*.hop-0.body.gz`: năm response nguyên bản; `*.txt`: text đọc offline.
  Không ghi cookie/token header vào metadata; HTML có thể chứa thông tin phiên,
  biểu mẫu và thông tin liên hệ nên không đưa body lên Git/công bố raw.
- `listing-analysis.json`: hub 118 ID, tab Gần đây 30 ID, ba URL chọn mẫu;
  cờ `main_search_listing_verified=false`, không giả số main listing.
- `listing-request-log.json`, `detail-*-request-log.json`: request thật,
  kiểm tra scope/robots trước từng hop; không có retry/redirect.
- `detail-records.jsonl`, `detail-audit.json`, `report.json`: record thật và số
  liệu tách HTTP, listing chưa xác minh main, detail, quyền sử dụng.
- `baseline-raw.json`, `baseline-protected.json`, `baseline-policies.json`,
  `preservation-check.json`: checksum trước/sau, các policy là file được phép sửa.

Lệnh đã chạy: `git status --short`, đọc `rg`/`sed`, cập nhật README/AGENTS bằng
patch. Do `apply_patch` không đọc được file cập nhật vì lỗi sandbox mountinfo,
áp dụng patch tương đương qua `git apply --unidiff-zero -`, không stage/reset.
HTTP dùng các đoạn Python gọi `scripts.public_source_probe.capture(..., delay=10)`
và hook kiểm tra robots/host; trích xuất/validate/hash chạy offline trên HTML.
Không có lệnh crawl batch hay resume nguồn khác.

```bash
.venv/bin/pytest -q -m 'not live'  # 205 passed, 10.13s
.venv/bin/ruff format --check .  # 97 files already formatted
.venv/bin/ruff check .           # All checks passed
.venv/bin/mypy src               # 43 source files, passed
git diff --check                # passed; báo cáo mới kiểm tra whitespace riêng
```

Không sửa logic source/test, không tuyên bố test suite đã kiểm thử crawler
JobOKO: crawler chưa được tích hợp. Assertion audit ba response và guard robots
cho probe được thực hiện riêng offline; chưa thử resume/dedup batch live.

Đối chiếu SHA-256 **1.522 file raw/checkpoint và 144 file code/test/script/docs/
bằng chứng JobOKO có trước: không đổi**. CareerViet 299, Timviec365 299,
CareerLink 55 giữ nguyên; không sửa hoặc xóa các thay đổi Git có sẵn.
Diff tracked chỉ README và AGENTS: **36 dòng thêm, 5 dòng bỏ**; thêm tài liệu
này, giữ ba tài liệu untracked cũ. Không stage, commit hoặc push.

Kết luận riêng: **đọc được ba detail thật bằng HTTP trong mẫu này**. Chưa
chứng minh discovery main listing/phân trang, batch ổn định hoặc quyền sử dụng
dữ liệu vượt probe; không tự mở rộng quy mô hoặc tái sử dụng ngoại lệ này.
