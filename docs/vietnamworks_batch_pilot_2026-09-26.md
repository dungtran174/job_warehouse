# VietnamWorks: adapter batch và pilot bị chặn — 2026-09-26

Các đường dẫn `data/`, HTML gốc, manifest, checkpoint và log bên dưới là
**artifact cục bộ, không được commit**. Chỉ code, báo cáo và fixture rút gọn
được lưu trong Git; clone repository không bao gồm batch để resume.

## Phạm vi và điều kiện

Quyết định chủ dự án trong chat cho phép triển khai adapter và pilot tối đa 20
detail; không phải chấp thuận của VietnamWorks. Không chạy mode full-snapshot.
Owner scope riêng VietnamWorks được nới trong sample tới 2 listing/20 detail,
không đổi gate CareerViet, không đổi giới hạn feasibility probe 1/3.

Kiểm tra trực tiếp lúc 15:04 UTC (22:04 ICT):
- https://www.vietnamworks.com/robots.txt: HTTP 200.
- https://www.vietnamworks.com/thoa-thuan-su-dung: HTTP 200. Các khoản mục đích/
  quyền từ chối và ngoại lệ bản sao hợp lý dùng nội bộ vẫn hiện diện.
- Quy chế PDF liên quan đã OCR ở lượt trước, xem vietnamworks_policy_check_2026-09-26.md.
- Chỉ thử mẫu nội bộ; không suy rộng quyền thu thập/công bố nội dung quy mô lớn.
- Không đăng nhập, proxy, stealth, CAPTCHA solver hoặc gọi API nội bộ.

## Parser detail: kiểm chứng offline trước live

Ba HTML gốc lấy từ:
data/diagnostics/source_feasibility/vietnamworks/20260925T174014.552556Z/html/

Parser đọc payload React Flight inline từ chính HTML, không thực thi script.
ID phải khớp canonical URL; title, company, description và requirement phải tồn tại.
Không dùng listing hay related jobs để bù trường. Chỉ chọn metadata công việc;
không đưa email liên hệ và dữ liệu tài khoản trong payload vào record.

Fixtures detail_2109839.html, detail_2107184.html, detail_2107466.html được rút gọn
cơ học từ HTML gốc. Hash toàn văn description/requirement sau chuẩn hóa khoảng
trắng khớp độc lập với detail_audit.jsonl (DOM) của lượt trước, cả 3/3.
Fixture test cả URL -jd và -jv; việc HTML detail main -jv live có cùng cấu trúc
hay không vẫn chưa được kiểm chứng do pilot bị chặn trước detail.
Field tùy chọn thiếu giữ null; danh sách metadata tuân theo model chung.

## Kiểm tra main listing/phân trang, tách khỏi pilot

- HTTP trang đầu 200, sau đó Chrome thường render được.
- Vùng chính là .block-job-list .search_list; bỏ .out-stading-jobs.
- Card tải lười: DOM đầu chỉ có một phần. Cuộn tới pagination làm xuất hiện đủ card.
- Trang 1 có 50 ID duy nhất.
- Bấm nút 2 trên UI chuyển URL sang https://www.vietnamworks.com/viec-lam?page=2.
- Trang 2 có 50 ID duy nhất, overlap với trang 1 bằng 0: tổng 100 ID.
- Không lấy năm tin nổi bật làm bằng chứng cho các con số này.
- Chưa khẳng định đủ toàn website; mới xác nhận hai trang và đường sang trang kế tiếp.

HTML diagnostic và log ở data/diagnostics/vietnamworks_batch_check_20260926/.
Fixtures main_listing_1.html và main_listing_2.html giữ card/pagination cần thiết.

## Tích hợp

- crawlers/vietnamworks.py tuân theo SourceCrawler.
- parsers/vietnamworks_listing.py chỉ enqueue main results và fail closed khi
  active page không khớp URL hoặc không xác định được pagination.
- parsers/vietnamworks_detail.py xuất JobRecord, metadata/schema/parser/hash/raw_html_path.
- fetchers/vietnamworks.py dùng HTTP trên mỗi URL; render chỉ cho listing HTTP
  bình thường thiếu main results. HTTP 401/403/challenge không kích hoạt render.
- CLI/factory/config nhận vietnamworks, owner basis không có authorization giả.
- Engine/BatchStorage giữ nguyên cơ chế raw JSONL, HTML gzip, dedup ID,
  checkpoint và incremental state. URL bị từ chối giữ pending cho resume có chủ đích.
- Không tạo bộ lưu dữ liệu riêng, không sửa dữ liệu CareerViet.

## Pilot thực tế

Batch: 20260926T151442Z-1439f601, mode sample, 3–5 giây, một luồng, retry=0.
Start: 2026-09-26T15:14:42Z; stop: 15:14:47Z.

Đường dẫn:
data/raw/vietnamworks/snapshot_date=2026-09-26/batch_id=20260926T151442Z-1439f601/

| Chỉ số pilot | Kết quả |
| --- | ---: |
| Listing URL đã thử | 1 |
| Listing main thành công trong batch | 0 |
| Listing HTTP trước render | 200 |
| Cùng URL bằng browser render | 403 |
| URL/ID enqueue trong batch | 0 |
| Detail thử / thành công | 0 / 0 |
| Dòng jobs.jsonl hợp lệ | 0 |
| Tỷ lệ đủ mô tả/yêu cầu | N/A — mẫu detail rỗng |
| Lỗi | 1, listing HTTP 403 |

HTML lỗi chứa tiêu đề và heading 403 Forbidden, footer nginx.
errors.jsonl lưu stage=listing, http_status=403. Không gọi thêm nguồn sau đó,
không đổi UA/proxy/browser để thử vượt chặn. Không chép ba tin cũ vào batch pilot.
Không thể đối chiếu dòng jobs.jsonl pilot với HTML detail vì chưa có dòng nào.

Đối soát offline sau khi dừng:
- Giữ manifest.initial.json làm bằng chứng trước sửa bookkeeping.
- Manifest hiện tại ghi đúng attempted fetcher=playwright, fallback=true, headless=true,
  vì phiên bản đầu chỉ set các cờ sau khi browser thành công.
- Checkpoint listing chuyển failed -> pending để không mất URL; metadata ghi rõ
  stop HTTP403 và chỉ resume sau khi điều kiện truy cập cho phép.
- Không thay đổi counters, errors, HTML403 hay trạng thái stopped.
- Test offline mô phỏng 403 rồi explicit resume xác nhận không tự retry live.

## Kiểm tra và bước tiếp theo

127 test offline đạt; Ruff format/check và mypy src đạt. Integration test xác nhận
ghi raw từ fixture detail, resume cùng batch không refetch/duplicate,
loại tin nổi bật, giữ checkpoint khi HTTP/browser từ chối.

Lệnh pilot và resume có điều kiện nằm trong README, mục VietnamWorks.
Resume dùng cùng batch, max-pages=2 vì counters listing là cumulative attempts
(đã dùng 1 attempt), max-details=20. Không chạy lệnh resume ngay khi 403 còn tồn tại.
Không mở rộng 300, không tuyên bố crawler live ổn định.

CareerViet giữ 299 dòng, SHA-256:
018aa543af009120e4d7d1a1119091faaced9fe7616e00e8c927684543a1afdc
Git không commit/reset/checkout; các thay đổi có sẵn được giữ.
