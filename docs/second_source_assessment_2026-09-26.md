# Đánh giá nguồn live thứ hai — 26/09/2026

## Phạm vi và cơ sở truy cập

Theo yêu cầu trực tiếp của chủ dự án: thử CareerLink → Việc Làm 24h → freeC;
chỉ nội dung công khai, HTTP trước, dừng khi từ chối; không đăng nhập, API nội bộ,
proxy, stealth, giải CAPTCHA hoặc browser để vượt chặn. Đây không phải chấp thuận
của chủ website. Không chạy lại VietnamWorks; không làm bước Bronze/Silver.

Bằng chứng cục bộ: `data/diagnostics/second_source_assessment/20260926/`.
Mỗi phản hồi có body gzip, URL yêu cầu/URL cuối, status, thời điểm UTC và SHA-256.
Không ghi cookie/header xác thực vào metadata. HTML raw chỉ giữ nội bộ, không commit.

## Điều kiện đã kiểm tra

### CareerLink

- 15:48:14 UTC: https://www.careerlink.vn/robots.txt — HTTP 200.
- 15:48:55 UTC: https://www.careerlink.vn/thoa-thuan-su-dung — HTTP 200, đọc toàn văn.
- 15:49:17 UTC: https://www.careerlink.vn/quy-che-hoat-dong — HTTP 200, đọc toàn văn.
- Robots không chặn các đường dẫn `/vieclam/tim-kiem-viec-lam`, `/vieclam/list?page=2`
  và `/tim-viec-lam/<slug>/<id>` với User-Agent crawler dự án. Các vùng tài khoản
  bị chặn không được truy cập. Không suy rộng robots thành giấy phép sử dụng dữ liệu.
- Thỏa thuận §3 giới hạn sao chép giao diện, mã nguồn, nội dung biên tập và tài sản
  của CareerLink; §4 phân biệt tin tuyển dụng do người dùng đăng và quyền sở hữu của họ.
  §5 cấm xâm nhập, gây quá tải và thu thập trái phép thông tin cá nhân.
- Quy chế II.1 nói có thể xem tin không cần tài khoản; V cấm công cụ can thiệp/phá hoại;
  IX.1 bảo vệ nội dung do CareerLink tạo; X.2 cấm sao chép/phân phối trái phép cho bên thứ ba.
- Đánh giá phạm vi: không thấy lệnh cấm rõ áp dụng riêng cho thử nghiệm HTTP tốc độ thấp,
  đọc tin tuyển dụng công khai và lưu cục bộ phục vụ đồ án. Đây là nhận định có giới hạn,
  **không** xác nhận quyền tái xuất bản/chia sẻ/bán toàn văn hay quyền thu thập hồ sơ ứng viên.
  Không trích xuất trường tên/điện thoại người liên hệ vào record.

### Việc Làm 24h

15:58:11 UTC: https://vieclam24h.vn/robots.txt — **403**. Lưu body và metadata
`vieclam24h-robots.*`; dừng ngay. Chưa xác minh được robots/điều khoản hiện hành,
chưa yêu cầu listing hoặc detail; không kết luận parser thất bại.

### freeC

15:58:33 UTC: https://freec.asia/robots.txt — **429**, không phải 403.
Lưu body và metadata `freec-robots.*`; không retry, dừng nguồn.
Chưa xác minh được robots/điều khoản, listing hay detail.

## Mẫu và pilot CareerLink trước tích hợp

- Danh sách chính: https://www.careerlink.vn/vieclam/tim-kiem-viec-lam (HTTP 200).
- Vùng main: `ul.list-group > li.job-item a.job-link[href]`; không dùng tin gợi ý.
- 50 URL/ID duy nhất ở trang 1; `.pagination a[rel=next]` dẫn tới
  https://www.careerlink.vn/vieclam/list?page=2; trang 2 có 50 ID khác, overlap 0,
  next là `?page=3`. Tổng 33.397 hiển thị trên nguồn không phải số đã crawl.
- Ba mẫu: 3634108, 3634019, 3628750; đều HTTP 200, không đổi URL, đủ tiêu đề,
  công ty, mô tả và yêu cầu từ chính detail. ID đối chiếu canonical và JSON-LD.
- Pilot gồm 10 tin trang 1 + 10 tin trang 2, tái sử dụng 3 mẫu đã lưu:
  **20 detail kiểm tra, 20 truy cập thành công, 20 record hợp lệ, 0 lỗi**.
  Có 17 request detail mới; không cộng 3 mẫu thành 23 ID độc lập.
- Mô tả/yêu cầu: 20/20 có nội dung và khớp toàn bộ DOM section sau chuẩn hóa khoảng trắng.
  `careerlink-pilot.jsonl` là dữ liệu diagnostic, chưa phải batch raw CLI.
  `careerlink-pilot-report.json` chứa audit độ dài/hash/status/URL từng detail.
- HTTP đã chứa nội dung; không dùng Playwright. Form login ẩn có widget CAPTCHA
  thụ động nhưng không chắn nội dung; parser không đăng nhập hay thực thi widget.

## Tích hợp được chọn

CareerLink là nguồn duy nhất qua pilot. Parser riêng, adapter riêng, fetcher HTTP-only;
CLI/engine dùng batch JSONL, checkpoint, dedup sẵn có. Fetcher lưu mọi body trước
khi phân loại lỗi. Chế độ `bounded` dành riêng CareerLink do chủ dự án yêu cầu,
tối đa 6 trang/300 detail lũy kế, bắt buộc lưu HTML/đủ nội dung, delay ≥3 giây,
max-retries=0. Ngưỡng lỗi detail 5%, dừng ngay khi bị từ chối; không full snapshot.

## Batch raw thực tế và điều kiện dừng

Batch: `data/raw/careerlink/snapshot_date=2026-09-26/batch_id=20260926T160422Z-c39d6a20/`.

| Nguồn / giai đoạn | Listing thành công | ID main duy nhất | Detail thử | Detail có nội dung / hợp lệ | Kết quả |
| --- | ---: | ---: | ---: | ---: | --- |
| CareerLink pilot diagnostic | 2 | 100 | 20 | 20 / 20 | Đủ điều kiện tích hợp |
| CareerLink batch raw | 2 | 100 | 56 | 55 / 55 | Dừng challenge thật |
| Việc Làm 24h | 0 (chưa thử) | Chưa biết | 0 | Chưa thử | Robots 403 |
| freeC | 0 (chưa thử) | Chưa biết | 0 | Chưa thử | Robots 429 |

Batch raw bắt đầu 16:04:22 UTC; dừng 16:08:38 UTC (23:08:38 giờ Việt Nam).
Tin thứ 56, ID **3626178**, URL:
https://www.careerlink.vn/tim-viec-lam/chuyen-vien-sale-admin-ocean-edu-yen-lac-thu-nhap-tu-13-trieu-thang-phong-van-di-lam-ngay/3626178
trả HTTP **200** nhưng là trang yêu cầu xác nhận không phải robot, có form
`recaptcha_confirm_form` và widget `h-captcha`; không có nội dung detail cần thiết.
Đây là challenge thật, khác form đăng nhập ẩn trên các detail bình thường.
Không gửi thêm request sau đó, không retry, không browser.

Bằng chứng nguyên phản hồi:
`http/20260926T160838.708991Z-d1b387b5.html.gz` và metadata cùng tên trong batch.
`errors.jsonl` có 1 lỗi `FetchError`; manifest `stopped/access_blocked`.
Có 59 phản hồi HTTP 200 trong batch = 1 robots + 2 listing + 56 detail;
**không** được xem 56 HTTP 200 là 56 detail truy cập thành công.

`jobs.jsonl`: **55 dòng hợp lệ, 55 ID duy nhất**, tỷ lệ detail hợp lệ **55/56 = 98,2%**.
Không cộng pilot 20 vào raw 55 vì có ID trùng giữa các lượt.
Cả 55 record có title/company/full description/requirements/salary/location/posted date.
Audit đối chiếu toàn bộ DOM section, canonical, content hash và ngày đăng: **0 sai lệch**.
Độ đầy đủ từng trường trong phạm vi này: **55/55 (100%)**.
Các trường mở rộng ngoài phạm vi parser (ví dụ phúc lợi tách riêng, kinh nghiệm,
cấp bậc) chưa được trích riêng; null không đồng nghĩa website không có.
Không tuyên bố đầy đủ mọi trường như CareerViet.

### Sửa parser offline sau audit

- v1.0.1 sửa 2 tin nhiều địa điểm: 3633921, 3633922; giữ cả ba khối địa điểm.
- v1.0.2 bổ sung fallback địa chỉ văn phòng hiển thị trên detail cho 4 tin:
  3621196, 3621190, 3612715, 3633575; không suy ra địa điểm từ tiêu đề/listing.
- Trích xuất lại 55 record từ HTML đã lưu, không fetch lại. Giữ crawled_at, trạng thái
  dừng, lỗi và checkpoint. Đồng bộ hash kỹ thuật riêng CareerLink.
- Bản JSONL/manifest/state trước sửa được giữ trong
  `offline-reparse-backup-1.0.0/` và `offline-reparse-backup-1.0.1/`.
  Audit và nhật ký sửa: `careerlink-final-audit.json`,
  `careerlink-offline-reparse.json`, `careerlink-office-reparse.json` trong diagnostics.

### Khả năng tiếp tục

Checkpoint: 55 detail completed, 45 pending (gồm URL bị challenge), 2 listing completed,
1 listing pending (trang 3). **Chưa đạt 100, chưa thử 300, chưa kiểm chứng trang 3 trở đi.**
CareerLink được chọn vì là nguồn duy nhất qua pilot và ghi raw thật, nhưng chưa chứng minh
khả năng duy trì batch 100–300. Không đề xuất né challenge để đạt số lượng.

Lệnh đã chạy thực tế:

```bash
.venv/bin/job-crawler crawl careerlink --mode bounded --project-owner-public-test --fetcher http --max-pages 2 --max-details 100 --delay-min 3 --delay-max 5 --max-retries 0 --timeout 30 --save-html --require-complete-content --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

Lệnh resume tham khảo, **CHƯA CHẠY và không chạy trong điều kiện đang bị challenge**.
Chỉ cân nhắc sau khi điều kiện truy cập được xác nhận phù hợp và có yêu cầu tiếp tục;
giới hạn lũy kế là số lần thử, nên một lần lỗi đã tiêu tốn một lượt:

```bash
.venv/bin/job-crawler crawl careerlink --mode bounded --project-owner-public-test --fetcher http --max-pages 2 --max-details 100 --delay-min 3 --delay-max 5 --max-retries 0 --timeout 30 --save-html --require-complete-content --resume --resume-batch-id 20260926T160422Z-c39d6a20 --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

## Kiểm thử, bảo toàn và Git

- `pytest -q`: **156 passed** (offline; không chạy test live).
- `ruff check .`: đạt; `ruff format --check .`: 78 files already formatted.
- `mypy src`: đạt, 39 source files. `git diff --check`: đạt.
- Hash đối chiếu **396 file CareerViet/VietnamWorks: không file nào đổi**.
  CareerViet vẫn 299 dòng; SHA-256 jobs:
  `018aa543af009120e4d7d1a1119091faaced9fe7616e00e8c927684543a1afdc`.
- Không commit/reset Git, không tải lại VietnamWorks, không viết Bronze/Silver.
- File có sẵn được sửa trong lượt này: README, CLI, config, engine (thêm bounded gate),
  fetchers/factory. Giữ các thay đổi có sẵn của người dùng.
- File mới: parser/crawler/fetcher CareerLink; hai script capture/audit; fixture 3 detail;
  test parser, nhiều địa điểm, địa chỉ-only/challenge, audit, probe-capture và integration;
  báo cáo này.
- Git diff lưu ở diagnostics: `git-tracked.diff` (diff tracked toàn worktree,
  **có cả thay đổi người dùng từ trước**) và `git-new-careerlink-files.diff`
  (các file mới của lượt này). Không thêm raw/HTML dung lượng lớn vào Git.
- Số liệu machine-readable: `comparison.json`.

Lệnh audit có thể chạy lại hoàn toàn offline:

```bash
.venv/bin/python scripts/audit_careerlink_batch.py data/raw/careerlink/snapshot_date=2026-09-26/batch_id=20260926T160422Z-c39d6a20
```

## Lệnh đã thực hiện

- HTTP chính sách/mẫu: `.venv/bin/python - <<'PY' ...` dùng `httpx.get`, sau đó
  `scripts.public_source_probe.capture(root, label, url)`; từng URL/thời điểm/status
  lưu trong metadata. Không có lệnh live VietnamWorks.
- Pilot: script Python tuần tự dùng `parse_listing`, `parse_detail`, `capture`,
  tái dùng trang 1 + 3 mẫu; chỉ fetch trang 2 và 17 detail còn lại, delay 4 giây.
- `.venv/bin/pytest -q`
- `.venv/bin/ruff check .`
- `.venv/bin/ruff format --check .`
- `.venv/bin/mypy src`
- Batch: lệnh `job-crawler crawl careerlink --mode bounded ...` ghi trong README;
  mốc đầu `--max-pages 2 --max-details 100`, nghỉ 3–5 giây.

## Giới hạn diễn giải

Đủ nội dung nghĩa là đủ các khối tuyển dụng công khai được nguồn trả về, không chứng minh
tính chính xác nghiệp vụ, tin còn tuyển hay mọi trường tùy chọn tồn tại. Thông tin thiếu
để null. Kết quả của hai nguồn bị chặn là chưa kiểm chứng detail, không phải 0% thành công.
Không dùng kết quả CareerLink để thay đổi kết luận VietnamWorks (3 detail cũ lấy được,
luồng listing sau đó bị 403).
