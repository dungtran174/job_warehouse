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

- Chỉ tin công khai; người vận hành kiểm tra điều khoản/phạm vi lưu dữ liệu trước
  live. Engine đọc robots đầu mỗi invocation và kiểm tra từng URL; không truy
  cập URL bị cấm. Robots không tải được thì dừng, quyền chưa xác định.
- Một luồng, UA minh bạch, CareerLink đợt mở rộng nghỉ10–15s, retries=0.
  Dừng 401/403/429 hoặc CAPTCHA/challenge kể cả HTTP200, giữ bằng chứng/checkpoint.
  Không tự resume sau chặn, đổi browser/IP/UA, đăng nhập, stealth/proxy/CAPTCHA solver.
- `--project-owner-public-test` ghi quyết định chủ dự án, không phải chấp thuận
  nguồn. `--authorization-reference` chỉ dùng văn bản nguồn thật, không tự đặt mã.
  HTTP200/thành công kỹ thuật không chứng minh quyền khai thác/tái công bố mọi quy mô.
- HTML nguyên trang chứa giao diện/mã/nội dung biên tập của website; tin do nhà
  tuyển dụng đăng và dữ liệu công bố trên dashboard cần đánh giá quyền riêng.
  Không coi điều khoản sao chép HTML là lệnh cấm tuyệt đối đọc tin công khai.
- Listing chỉ discovery; JSONL chỉ ghi detail đủ title/company/toàn văn mô tả/yêu
  cầu từ detail. Không bù bằng preview/gợi ý; trường tùy chọn thiếu giữ null.
- Không tự chạy live/full snapshot khi chưa có yêu cầu rõ; full cần `--confirm-full`.
  Cờ/giới hạn CLI không thay thế điều kiện nguồn hiện hành.

## CareerLink: resume cùng batch tới mục tiêu 300

Xác minh offline 30/09/2026: **156 raw / 156 ID**, 159 detail attempts, 156 success,
3 lỗi gồm 1 hCaptcha cũ và 2 lượt hCaptcha mới cùng ID `3635311`;
8 listing/400 ID, còn 244 detail pending. Batch dừng `access_blocked`.
ID từng challenge3626178 đã completed ở lượt khỏe29/09, không tải lại.
Start URL phải giữ đúng manifest cũ.

**Không chạy lại lệnh dưới đây khi nguồn còn trả challenge.** Chỉ cân nhắc một
lượt resume thông thường sau khi kiểm tra điều khoản/robots/phạm vi lưu dữ liệu
hiện hành và có cơ sở truy cập bình thường đã khôi phục. ID `3635311` vẫn
pending và sẽ được thử đầu tiên; nếu lại là hCaptcha/403/429 thì dừng, không
bỏ qua hoặc lặp thử. Không cần Chrome; chạy một tiến trình từ thư mục gốc:

```bash
cd /home/dung/project/job_warehouse
.venv/bin/job-crawler crawl careerlink --mode bounded \
  --start-url 'https://www.careerlink.vn/vieclam/tim-kiem-viec-lam' \
  --output-dir data/raw --project-owner-public-test --fetcher http \
  --resume --resume-batch-id 20260926T160422Z-c39d6a20 \
  --max-pages 8 --max-details 330 --target-records 300 \
  --delay-min 10 --delay-max 15 --max-retries 0 --timeout 30 \
  --require-complete-content \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

- `max-pages=8`: tối đa8 listing attempts **toàn batch**; đã dùng hết8.
- `max-details=330`: tối đa330 detail attempts **toàn batch** (đã159, còn tối
  đa171), không phải số tin mới. Lượt lỗi cũng được tính.
- `target-records=300`: dừng khi có tổng300 ID raw duy nhất, cần thêm144
  dòng hợp lệ; số lượt còn lại không bảo đảm lấy đủ.

Tám listing đã phát hiện400 ID nhưng chỉ156 dòng detail hợp lệ; ID listing không
phải raw. Challenge giữ ID pending để đánh giá, không chạy lại ngay hoặc dùng
công cụ khác để né chặn. Nếu hết pending, lặp listing, mapping conflict,
robots/challenge hoặc vượt tỷ lệ lỗi thì dừng, không cố đủ300 bằng retry.

Audit offline đối chiếu HTML khớp156/156 raw cũ; hai response challenge không có
detail. Không lặp command tự động; nếu thiếu dữ liệu/trần phải audit trước khi đổi cấu hình.

Không có `--save-html`, CareerLink vẫn parse HTML trong RAM nhưng không lưu body
nguyên trang của response HTTP 200 không bị challenge. `http/*.json` phiên bản 2
ghi URL/ID yêu cầu, URL/ID cuối, canonical URL/ID, status, content type, cờ
challenge, kích thước và SHA-256 body; `raw_html_path=null` ở record mới.
Response lỗi/challenge vẫn giữ body để kiểm tra điểm dừng. `manifest.run_settings`
ghi `success_body_storage=metadata_only` cho lượt mới; lượt cũ thiếu trường
này được hiểu là `full`, raw/HTML cũ không đổi. Audit mới kiểm tra ID/status,
metadata và content hash của record, **không thể** đối chiếu lại DOM, toàn văn,
đầu/cuối mô tả/yêu cầu hay tính lại SHA-256 body nếu không lưu body. Tắt lưu
HTML không tự cấp quyền lưu/tái công bố nội dung tin hoặc dữ liệu dashboard.
Response HTTP 200 mà parser không nhận ra detail cũng chỉ còn metadata và
`errors.jsonl`; muốn điều tra DOM sau đó phải có bản lưu hợp lệ từ nguồn khác.

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
Batch có3 lỗi lũy kế nên `completed_with_errors`/exit2 vẫn có thể là kết thúc tại
mục tiêu trong tương lai; xem reason/raw/lỗi mới, không suy exit2 là chặn mới. `max_details`
là hết attempts, không chứng minh đủ300. `target_unmet_no_pending_details`
là không còn detail trong discovery. `stopped`, `access_blocked`,
`browser_challenge`, `robots_*` thì dừng, không tự chạy lại ngay.

Máy/terminal ngắt vì lý do khác chặn truy cập: chắc chắn tiến trình cũ đã chết
rồi mới resume đúng batch ID. Processing được phục hồi, completed không tải/ghi
lại; slot ngắt vẫn tính lũy kế. Nếu gặp challenge/401/403/429 thì dừng, không
coi đó là ngắt máy thông thường để chạy lại ngay.
Resume giữ snapshot26/09, record mới có crawled_at thực; không đổi156 tin cũ
thành dữ liệu mới ngày chạy. Cập nhật hằng ngày sau này tạo batch mới.

## Dữ liệu và nguồn dự phòng

```text
data/raw/<source>/snapshot_date=YYYY-MM-DD/batch_id=<id>/
  jobs.jsonl / errors.jsonl / manifest.json / checkpoint.sqlite3
  html/*.html.gz / http/*  # HTML tùy chế độ; URL/status/metadata cục bộ
```

CareerViet299, CareerLink156, VietnamWorks295 và Việc Làm24h104 giữ nguyên
trong repo. Timviec365299 đã chuyển sang archive ngoài repo, được kiểm tra
checksum/toàn văn; xem cách khôi phục trong tài liệu kiến trúc. Hai nguồn
browser là dự phòng có dữ liệu thật, không xóa như
"crawl lỗi"; code/audit/test còn phụ thuộc nên giữ. Raw/HTML/checkpoint/
diagnostics/.runtime/.venv không vào Git, clone không có artifact cục bộ.
Báo cáo từng lượt đã lưu cục bộ/Git revision; xem
[kiến trúc và bài học](docs/architecture_data.md).
