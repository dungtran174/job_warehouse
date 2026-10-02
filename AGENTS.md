# Hướng dẫn dự án job_warehouse

## Phạm vi và làm việc

- Pipeline chính: CareerViet + CareerLink; nguồn khác là dự phòng/đối chiếu,
  không tự chạy hoặc xóa code/batch của chúng. Python >=3.11.
- Trước sửa đọc README và docs/architecture_data.md; bảo toàn thay đổi có sẵn.
- Logic mới phải có test offline; chạy pytest, Ruff format/check, mypy, diff --check.
- Không hard-code secret/cookie/token; không commit raw/HTML, môi trường hoặc secrets.
- Không triển khai Airflow/Bronze/Silver/Gold/dashboard nếu chưa được yêu cầu rõ.

## Crawl và truy cập

- Không tự crawl live. Chỉ nguồn tuyển dụng công khai, không đăng nhập; người vận
  hành đối chiếu điều khoản, robots và phạm vi lưu dữ liệu trước mỗi lượt chạy.
- Tôn trọng robots/rate limit/Retry-After; nếu điều khoản cấm hoạt động dự định
  hoặc robots không cho phép thì dừng. Robots chưa xác định không phải được phép.
- Dừng 401/403/429 hoặc CAPTCHA/challenge kể cả HTTP200; lưu bằng chứng/checkpoint,
  không retry/fallback để né. Không stealth, proxy/IP/UA rotation hoặc CAPTCHA solver.
- Một luồng, giới hạn request hữu hạn; CareerLink mở rộng nghỉ10–15s, retries=0.
- Quyết định chủ dự án (`project_owner_public_test`) không phải chấp thuận nguồn;
  authorization-reference chỉ cho văn bản nguồn có thật. Thành công kỹ thuật
  không chứng minh quyền khai thác/tái công bố mọi quy mô. Ngoại lệ probe cũ
  không áp dụng lại tự động. Full snapshot cần yêu cầu rõ và --confirm-full.

## Dữ liệu và vận hành

- Listing chỉ phát hiện ID; chỉ detail đủ title/company/toàn văn description và
  requirements mới ghi jobs.jsonl. Không bù bằng preview/gợi ý; thiếu tùy chọn=null.
- Giữ raw/provenance và HTML cũ; không viết lại schema/parser batch cũ khi chưa migration.
  CareerLink có thể không lưu body HTTP 200 không challenge: ghi metadata v2,
  giữ body HTTP lỗi/challenge; lỗi parse trên HTTP 200 chỉ còn metadata,
  đánh dấu chế độ theo lượt; không được gọi metadata là kiểm chứng lại toàn văn HTML.
  Tin nhà tuyển dụng và dữ liệu dashboard có phạm vi quyền riêng với HTML website.
- Khóa là source_name + source_job_id. Dedup/resume đúng nguồn/batch, không đếm
  ID listing hay cộng cùng ID qua nhiều snapshot thành tin mới.
- Batch mới theo ngày; resume chỉ hoàn tất batch dang dở, giữ snapshot cũ và
  crawled_at thực. Processing có thể phục hồi; failed không retry tự động.
- max-pages/max-details là attempts lũy kế; target-records là tổng raw duy nhất.
  Lượt gián đoạn/lỗi không được tự gọi là success hoặc failure thiếu bằng chứng.
- Content hash phát hiện thay đổi sau fetch; vắng mặt trong crawl lỗi/quét giới
  hạn không tự suy hết hạn. SQLite checkpoint là state kỹ thuật, không phải OLTP.
- Unit test dùng fixture, không phụ thuộc live; live test đánh dấu riêng.
- Bàn giao file đổi, test, số raw thật, điểm dừng và lệnh vận hành. Không tự commit/push.
