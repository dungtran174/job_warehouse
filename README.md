# job_warehouse

Crawler raw tuyển dụng công khai; pipeline chính: **CareerViet + CareerLink**.
Bronze ingestion/Silver/Gold/dashboard và scheduler hằng ngày là bước tiếp theo,
chưa triển khai. [Kiến trúc và dữ liệu](docs/architecture_data.md) ghi hợp đồng,
batch dự phòng, bài học và cách khôi phục báo cáo lịch sử.

## Cài đặt và kiểm tra offline

Python >=3.11. Dùng môi trường đang có hoặc tạo môi trường mới:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Hai nguồn chính dùng HTTP, không cần Chrome/đường dẫn browser để chạy chúng.
Dependency Playwright còn giữ để tương thích adapter/test nguồn dự phòng.
Repo không tự đọc `.env`; tham khảo `.env.example` nếu export cấu hình.

```bash
.venv/bin/pytest -q -m 'not live'
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
git diff --check
```

## Quy tắc vận hành

- Chỉ tin công khai; người vận hành kiểm tra điều khoản/phạm vi lưu HTML trước
  live. Engine đọc robots đầu mỗi invocation và kiểm tra từng URL; không truy
  cập URL bị cấm. Robots không tải được thì dừng, quyền chưa xác định.
- Một luồng, UA minh bạch, CareerLink đợt mở rộng nghỉ10–15s, retries=0.
  Dừng 401/403/429 hoặc CAPTCHA/challenge kể cả HTTP200, giữ bằng chứng/checkpoint.
  Không tự resume sau chặn, đổi browser/IP/UA, đăng nhập, stealth/proxy/CAPTCHA solver.
- `--project-owner-public-test` ghi quyết định chủ dự án, không phải chấp thuận
  nguồn. `--authorization-reference` chỉ dùng văn bản nguồn thật, không tự đặt mã.
  HTTP200/thành công kỹ thuật không chứng minh quyền khai thác/tái công bố mọi quy mô.
- Listing chỉ discovery; JSONL chỉ ghi detail đủ title/company/toàn văn mô tả/yêu
  cầu từ detail. Không bù bằng preview/gợi ý; trường tùy chọn thiếu giữ null.
- Không tự chạy live/full snapshot khi chưa có yêu cầu rõ; full cần `--confirm-full`.
  Cờ/giới hạn CLI không thay thế điều kiện nguồn hiện hành.

## CareerLink: resume cùng batch tới mục tiêu 300

Xác minh offline 29/09/2026: **75 raw / 75 ID**, 76 detail attempts, 75 success,
1 hCaptcha lịch sử; 2 listing/100 ID, 25 pending detail và trang3 pending.
ID từng challenge3626178 đã completed ở lượt khỏe29/09, không tải lại.
Điều khoản đã lưu26/09, robots khỏe gần nhất29/09; lượt chuẩn bị này không
kiểm tra live lại điều kiện. Start URL phải giữ đúng manifest cũ.

**Bạn tự chạy sau khi đối chiếu điều kiện truy cập; lệnh này chưa được chạy.**
Không cần Chrome. Chạy từ thư mục gốc, chỉ một tiến trình:

```bash
cd /home/dung/project/job_warehouse
.venv/bin/job-crawler crawl careerlink --mode bounded \
  --start-url 'https://www.careerlink.vn/vieclam/tim-kiem-viec-lam' \
  --output-dir data/raw --project-owner-public-test --fetcher http \
  --resume --resume-batch-id 20260926T160422Z-c39d6a20 \
  --max-pages 8 --max-details 330 --target-records 300 \
  --delay-min 10 --delay-max 15 --max-retries 0 --timeout 30 \
  --save-html --require-complete-content \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

- `max-pages=8`: tối đa8 listing attempts **toàn batch** (đã2, còn tối đa6).
- `max-details=330`: tối đa330 detail attempts **toàn batch** (đã76, còn tối
  đa254), không phải số tin mới. Slot lỗi/gián đoạn cũng có thể đã tính.
- `target-records=300`: dừng khi có tổng300 ID raw duy nhất, thêm tối đa225
  dòng vào cùng batch. Lượt hCaptcha cũ tốn1 attempt, nên cap300 attempts thì
  dù các lượt còn lại đều khỏe cũng chỉ có tối đa299 record.

8/330 là trần cấu hình hữu hạn bù overlap/lỗi, không bảo đảm có đủ ID hoặc
đọc được trang3+. Chỉ2 trang cũ có100 ID. Listing mới/overlap/next được xác
minh khi bạn chạy. Nếu hết next/pending, lặp listing, mapping conflict,
robots/challenge hoặc vượt tỷ lệ lỗi thì dừng, không cố đủ300 bằng retry.
Failed không tự retry; challenge giữ pending để đánh giá, không chạy lại ngay.
Engine discovery listing trước detail nên ID có thể tăng trước số dòng JSONL.

Nếu muốn chặng100 trước, dùng **cùng lệnh** nhưng thay bằng `--max-pages 2
--max-details 101 --target-records 100` (tối đa25 lượt thêm từ25 pending).
Chỉ sang lệnh8/330/300 nếu chặng100 đủ raw, không lỗi mới/chặn. Không lặp
command tự động; nếu thiếu dữ liệu/trần phải audit trước khi đổi cấu hình.

## Xem tiến độ và resume sau ngắt

Terminal thứ hai, chạy từng lệnh khi muốn xem; không cần watch/tail liên tục:

```bash
wc -l data/raw/careerlink/snapshot_date=2026-09-26/batch_id=20260926T160422Z-c39d6a20/jobs.jsonl
.venv/bin/python scripts/batch_status.py \
  data/raw/careerlink/snapshot_date=2026-09-26/batch_id=20260926T160422Z-c39d6a20
```

Status đọc JSONL/manifest/checkpoint **read-only**: raw/unique/duplicate,
attempts/success/failure, queue pending/processing, lỗi cuối và cấu hình lượt
mới. Khi đang ghi các file có thể lệch tạm thời; wc không chứng minh toàn văn.
Sau khi tiến trình kết thúc, audit offline:

```bash
.venv/bin/python scripts/audit_careerlink_batch.py \
  data/raw/careerlink/snapshot_date=2026-09-26/batch_id=20260926T160422Z-c39d6a20
```

Đạt mục tiêu: unique raw=300, duplicate=0, `termination_reason=target_records`.
Batch có1 lỗi cũ nên `completed_with_errors`/exit2 vẫn có thể là kết thúc tại
mục tiêu; xem reason/raw/lỗi mới, không suy exit2 là chặn mới. `max_details`
là hết attempts, không chứng minh đủ300. `target_unmet_no_pending_details`
là không còn detail trong discovery. `stopped`, `access_blocked`,
`browser_challenge`, `robots_*` thì dừng, không tự chạy lại ngay.

Máy/terminal ngắt: chắc chắn tiến trình cũ đã chết rồi chạy lại **nguyên lệnh
8/330/300**, giữ batch ID. Processing được phục hồi, completed không tải/ghi
lại; slot ngắt vẫn tính lũy kế. Nếu đã đủ300, gọi lại không gửi request mạng.
Resume giữ snapshot26/09, record mới có crawled_at thực; không đổi75 tin cũ
thành dữ liệu mới ngày chạy. Cập nhật hằng ngày sau này tạo batch mới.

## Dữ liệu và nguồn dự phòng

```text
data/raw/<source>/snapshot_date=YYYY-MM-DD/batch_id=<id>/
  jobs.jsonl / errors.jsonl / manifest.json / checkpoint.sqlite3
  html/*.html.gz / http/*  # body, URL/status/metadata cục bộ
```

CareerViet299, CareerLink75, VietnamWorks295 và Việc Làm24h104 giữ nguyên
trong repo. Timviec365299 đã chuyển sang archive ngoài repo, được kiểm tra
checksum/toàn văn; xem cách khôi phục trong tài liệu kiến trúc. Hai nguồn
browser là dự phòng có dữ liệu thật, không xóa như
"crawl lỗi"; code/audit/test còn phụ thuộc nên giữ. Raw/HTML/checkpoint/
diagnostics/.runtime/.venv không vào Git, clone không có artifact cục bộ.
Báo cáo từng lượt đã lưu cục bộ/Git revision; xem
[kiến trúc và bài học](docs/architecture_data.md).
