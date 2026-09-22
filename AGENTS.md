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
- Tôn trọng `robots.txt`, điều khoản sử dụng, rate limit và HTTP `Retry-After`.
- Không vượt CAPTCHA, không dùng stealth plugin, không xoay proxy/IP để né chặn.
- Nếu bị chặn hoặc điều khoản không cho phép, dừng và báo cáo; không tìm cách vượt qua.
- Mặc định chỉ chạy sample tối đa 2 trang danh sách và 20 trang chi tiết.
- Không chạy full snapshot nếu người dùng chưa xác nhận rõ ràng trong chat hiện tại.
- Full snapshot phải có cờ xác nhận riêng và hỗ trợ resume/checkpoint.

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
