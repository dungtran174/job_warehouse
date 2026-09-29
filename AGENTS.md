# Hướng dẫn dự án `job_warehouse`

## Mục tiêu

- Xây dựng pipeline thu thập và phân tích xu hướng thị trường tuyển dụng Việt Nam.
- Giai đoạn hiện tại chỉ triển khai crawler TopCV và lưu dữ liệu Raw/Bronze.
- Kiến trúc phải cho phép bổ sung VietnamWorks và các nguồn khác về sau.

## Quy tắc làm việc

- Ưu tiên Python 3.11 trở lên.
- Trước khi sửa code, đọc `README.md` và các tài liệu trong `docs/`.
- Không sửa hoặc xóa thay đổi không liên quan của người dùng.
- Mọi thay đổi logic phải có kiểm thử phù hợp.
- Sau khi sửa code, chạy formatter, linter và test theo cấu hình của repository.
- Không hard-code mật khẩu, cookie, token, API key hoặc thông tin đăng nhập.
- Không commit dữ liệu crawl dung lượng lớn, file bí mật hoặc môi trường ảo vào Git.

## Quy tắc crawl

- Chỉ crawl nội dung tuyển dụng công khai, không yêu cầu đăng nhập.
- Tôn trọng `robots.txt`, rate limit và HTTP `Retry-After`; đọc và ghi nhận điều khoản sử dụng. Mặc định dừng nếu điều khoản cấm, trừ ngoại lệ probe kỹ thuật hẹp được chủ dự án xác nhận rõ dưới đây.
- Không vượt CAPTCHA, không dùng stealth plugin, không xoay proxy/IP để né chặn.
- Nếu bị chặn (HTTP 401/403/429, CAPTCHA/challenge, kể cả HTTP 200) hoặc robots không cho phép, dừng và báo cáo; không tìm cách vượt qua. Hạn chế điều khoản vẫn là điều kiện dừng mặc định, ngoại trừ đúng probe được ghi nhận bên dưới.
- Mặc định chỉ chạy sample tối đa 2 trang danh sách và 20 trang chi tiết.
- Phép thử kỹ thuật công khai có yêu cầu rõ của chủ dự án không bắt buộc văn bản chấp thuận của chủ website: ghi `project_owner_public_test`, `authorization_reference=null`, không nhận là quyền do nguồn cấp. Thiếu văn bản tự nó không phải lý do dừng sample; robots, tín hiệu chặn và phạm vi thử vẫn phải được kiểm tra.
- Không chạy full snapshot nếu người dùng chưa xác nhận rõ ràng trong chat hiện tại.
- Full snapshot phải có cờ xác nhận riêng và hỗ trợ resume/checkpoint.

### Ngoại lệ probe JobOKO theo quyết định chủ dự án ngày 28/09/2026

- Chỉ cho một probe kỹ thuật được yêu cầu trong chat: tối đa 1 listing chính và 3 detail từ listing đó trên `vn.joboko.com`, dù điều khoản nguồn hạn chế bot/crawler. Không áp dụng cho nguồn khác hoặc lần chạy batch tiếp theo.
- Đây là quyết định nội bộ của chủ dự án, không phải chấp thuận của JobOKO hoặc xác nhận quyền sử dụng/tái công bố dữ liệu. Ghi `project_owner_public_test`, `authorization_reference=null` và giữ nguyên bằng chứng điều khoản/lịch sử cũ.
- Bắt buộc robots hiện tại cho từng URL, nội dung công khai, HTTP trước, tuần tự, nghỉ ít nhất 10 giây, không retry khi bị chặn. Browser thường chỉ được dùng nếu HTTP 200 bình thường cần JavaScript; không dùng để vượt chặn.
- Cho lưu status, URL cuối và body/HTML của đúng mẫu làm bằng chứng cục bộ, không công bố raw. Không bỏ qua 401/403/429, CAPTCHA/challenge hoặc robots; không đăng nhập, stealth, proxy rotation hay CAPTCHA solver. Không chạy batch lớn, commit hoặc push trong probe này.

### Lượt thử lại TopCV theo quyết định chủ dự án ngày 29/09/2026

- Cho một lượt đánh giá mới: 1 listing chính và tối đa 3 detail từ listing, không coi kết quả bị chặn cũ là trạng thái hiện tại. Giữ nguyên HTML/log/checkpoint và provenance cũ; không tự resume hoặc đổi công cụ để né phản hồi chặn của lượt mới.
- HTTP trước, tuần tự, nghỉ ít nhất 10 giây, không retry 401/403/429/CAPTCHA/challenge. Chỉ render browser thường khi HTTP 200 bình thường cần JavaScript, không dùng stealth/proxy/tài khoản hoặc giải CAPTCHA.
- Chỉ sau 3/3 detail đủ nội dung mới triển khai pilot tối đa 20 detail theo batch/HTML/dedup/checkpoint của repo. Giới hạn 20 không phải gate `pilot` 250 của CareerViet; chưa cho mở rộng 100/300 hoặc full snapshot.
- Không phải chấp thuận TopCV hoặc quyền khai thác dữ liệu quy mô lớn. Ghi quyết định chủ dự án, robots và điều khoản; chỉ lưu bằng chứng cục bộ. Không commit/push, không chạy nguồn khác.

## Kiến trúc và dữ liệu

- Không viết crawler thành một script đơn lẻ; tách crawler, parser, model, storage và CLI.
- Mỗi nguồn tuyển dụng dùng adapter/parser riêng nhưng cùng tuân theo hợp đồng dữ liệu chung.
- Raw/Bronze phải giữ giá trị gốc của nguồn; chưa chuẩn hóa nghiệp vụ sâu tại crawler.
- Các trường không tồn tại ở nguồn hoặc dữ liệu lịch sử được phép `null`.
- Mỗi record phải có `source_name`, `source_job_id`, `canonical_url`, `crawled_at`, `snapshot_date`, `schema_version`, `parser_version` và `content_hash`.
- Không coi SQLite checkpoint kỹ thuật là cơ sở dữ liệu OLTP nghiệp vụ.
- Chưa triển khai OLTP, Airflow, dbt, Data Warehouse, dashboard hoặc LLM nếu nhiệm vụ không yêu cầu rõ.

## Kiểm chứng và báo cáo

- Unit test không được phụ thuộc website đang hoạt động; sử dụng HTML fixture đã rút gọn.
- Live test phải được đánh dấu riêng và không chạy mặc định.
- Khi hoàn thành, báo cáo file đã đổi, lệnh đã chạy, kết quả test, kết quả sample và các giới hạn còn lại.
