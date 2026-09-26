# VietnamWorks — đối chiếu điều khoản và thử công khai giới hạn (2026-09-26)

Đây là báo cáo tại thời điểm probe, không phải trạng thái triển khai mới nhất.
Các đường dẫn `data/` là artifact lưu cục bộ, không được commit lên GitHub.
Xem [báo cáo batch ở lượt sau](vietnamworks_batch_pilot_2026-09-26.md).

Đây là đánh giá kỹ thuật theo quyết định của chủ dự án, **không phải** chấp thuận
của VietnamWorks và không phải kết luận pháp lý cho thu thập quy mô lớn. Đã đọc
toàn văn Thỏa thuận sử dụng và OCR đủ 58 trang Quy chế PDF trước request
listing/detail mới. Thời điểm kiểm tra: 2026-09-25 17:38–17:40 UTC
(2026-09-26 00:38–00:40 ICT).

## Điều kiện nguồn

- Thỏa thuận: https://www.vietnamworks.com/thoa-thuan-su-dung, HTTP 200.
  Mục 2 giữ quyền từ chối dịch vụ với trường hợp khai thác thông tin không
  phục vụ tuyển dụng cho chính người dùng. Đây là quyền từ chối, không viết
  thành lệnh cấm mọi lượt xem công khai. Mục 5 nói dùng sai mục đích tuyển
  dụng/tìm việc *có thể* bị xem là vi phạm theo đánh giá của Công ty.
  Mục 7 mặc định hạn chế sao chép, phân phối nội dung, nhưng cho phép
  số lượng hợp lý bản sao điện tử để dùng nội bộ, phải giữ thông tri quyền
  và URL nguồn. Ngoại lệ không xác định ngưỡng cho kho dữ liệu lớn.
- Quy chế: https://images.vietnamworks.com/terms/QuyCheHoatDong_2025.pdf,
  HTTP 200, OCR toàn bộ 58 trang. Trang 1, mục I cấm rõ việc dùng bất kỳ
  phần nào của website cho mục đích thương mại hoặc nhân danh bên thứ ba
  khi chưa có văn bản cho phép. Với thử đồ án phi thương mại do chính
  chủ dự án yêu cầu, điều kiện này chưa khớp rõ. Trang 56 nhắc lại
  việc dùng sai mục đích *có thể* bị coi vi phạm. Trang 53 khoản X.1.2(vii)
  hạn chế nhà tuyển dụng/thành viên sao chép công cụ dịch vụ, không phải
  lệnh cấm trực tiếp mọi lượt xem tin công khai. PDF tự ghi đầu trang
  là “TÀI LIỆU MẪU”; trang 1 đề ngày 19/04/2023 dù tên file có 2025,
  nên trạng thái hiệu lực chính xác của PDF còn chưa rõ.
- Robots: https://www.vietnamworks.com/robots.txt, HTTP 200. Với
  User-Agent job-warehouse-feasibility/0.1 (public-research), parser
  trả Allow=True cho một listing và đúng ba URL detail bên dưới.
  Robots không cấp quyền sao chép hoặc công bố nội dung.

Kết luận trước live: không thấy lệnh cấm **áp dụng rõ ràng** cho mẫu
phi thương mại 1 listing/3 detail, không đăng nhập và chỉ giữ bản sao
nội bộ. Quyền từ chối dịch vụ, điều khoản mục đích và giới hạn
sao chép vẫn tạo rủi ro/điểm chưa rõ. Không suy rộng thành quyền
crawl hàng trăm tin hoặc công bố lại nguyên văn.

## Kết quả thử giới hạn

Chạy probe với --project-owner-public-test, --fetcher http,
--max-listing-pages 1, --max-details 3 và --save-html. Robots 200,
listing HTTP 200, URL cuối giữ nguyên. Báo cáo probe ban đầu ghi
no_detail_urls vì parser chỉ nhận hậu tố -jv. Phân tích lại **cùng
HTML đã lưu**, không tải lại listing: có 5 URL/ID -jd duy nhất trong
mục tin nổi bật; kết quả tìm kiếm chính chỉ có số lượng trong SSR và
cần render JS. Không coi listing là detail. Đã thêm fixture/test
offline cho -jd. Ba URL đầu của chính listing đó được kiểm tra
robots riêng, HTTP thường trước rồi mới render Chrome thường vì
DOM HTML thô chưa hiện mô tả/yêu cầu.

| ID | HTTP/detail URL cuối | Mô tả | Yêu cầu | Tiêu đề, công ty, lương, địa điểm, ngày đăng |
| --- | --- | ---: | ---: | --- |
| 2109839 | 200, /strategic-planning-1790044179001307861-2109839-jd | 3269 ký tự | 1585 ký tự | Có đủ; lương “Negotiable” |
| 2107184 | 200, /customer-support-specialist-english-or-englishandchinese-2107184-jd | 2045 ký tự | 246 ký tự | Có đủ; lương 10m-30m ₫/month |
| 2107466 | 200, /consultant-data-governance-2107466-jd | 4434 ký tự | 4676 ký tự | Có đủ; lương “Negotiable” |

Cả 3 có ID trùng URL, tiêu đề và công ty từ detail; mô tả/yêu cầu
được lấy trọn section hiển thị, không bù từ listing. Các trường
ngày đăng lần lượt 22/09/2026, 15/09/2026, 15/09/2026.
Detail thử 3, HTTP truy cập 3, bản ghi đạt năm trường bắt buộc 3,
401/403/challenge 0. HTML thô của 1 listing/3 detail và
detail_audit.jsonl lưu nội bộ trong
data/diagnostics/source_feasibility/vietnamworks/20260925T174014.552556Z/
(bị loại khỏi Git). Không công bố lại toàn văn nguồn.

Giới hạn: 5 URL thuộc tin nổi bật, **không phải** kết quả tìm kiếm đầy đủ.
Parser probe hiện chưa trích đúng detail Next.js App Router; báo cáo
gốc report.json phản ánh lần chạy tự động lỗi nhận diện, còn
detail_audit.jsonl là đối chiếu tiếp trên các URL của cùng listing.
Tại thời điểm probe chưa có adapter, checkpoint/resume hay pilot VietnamWorks; chưa chứng
minh quyền hoặc độ ổn định để mở rộng lên khoảng 300 detail.
