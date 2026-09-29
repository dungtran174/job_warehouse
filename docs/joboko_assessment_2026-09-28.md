# JobOKO — đánh giá điều kiện truy cập, 28/09/2026

## Kết luận

**Dừng tại preflight điều khoản, trước listing/detail.** Điều khoản hiện hành
nêu cấm dùng bot/crawler/scrape. Không tích hợp crawler, không chạy pilot hoặc
các mốc 100/299; không tạo `jobs.jsonl` rỗng để thể hiện đã thu thập dữ liệu.

Đây là kết quả kiểm tra điều kiện truy cập, **không phải kết luận JobOKO thất
bại về kỹ thuật**. Homepage HTTP 200 không chứng minh listing hoặc detail đọc
được, đủ nội dung, có ID ổn định hay có thể chạy batch nhiều trang.

Yêu cầu thử của chủ dự án được ghi nhận là `project_owner_public_test`,
`authorization_reference=null`, không phải sự chấp thuận của JobOKO và không
được dùng để bỏ qua điều khoản nguồn. Không sửa README/config/guard để mở khóa.

## Request thực tế và bằng chứng

Artifact **cục bộ, không commit**:
`data/diagnostics/joboko_assessment/20260928T143728Z/`.
Mỗi hop lưu nguyên body gzip trước khi quyết định tiếp tục; metadata ghi URL,
status, redirect, thời điểm bắt đầu và SHA-256, không ghi cookie/token.

| Mục đích | URL yêu cầu | Bắt đầu UTC 28/09/2026 | HTTP / URL cuối |
| --- | --- | --- | --- |
| Robots | https://vn.joboko.com/robots.txt | 14:38:06.584813 | 200; URL giữ nguyên |
| Tìm liên kết chính sách/navigation | https://vn.joboko.com/ | 14:38:45.915852 | 200; URL giữ nguyên |
| Điều khoản từ footer | https://vn.joboko.com/dieu-khoan-dich-vu.html | 14:39:11.303812 | 301 → 200; https://vn.joboko.com/dieu-khoan-dich-vu |

Giờ Việt Nam = UTC + 7, tương ứng khoảng 21:38–21:39 ngày 28/09.
Cột thời điểm của điều khoản là lúc bắt đầu chuỗi; công cụ không lưu riêng
thời điểm bắt đầu hop 301 kế tiếp nên không tự điền một thời điểm chính xác.

Tổng **4 HTTP GET**, ba URL logic: 1 robots + 2 điều khoản (gồm redirect
cùng host) + 1 homepage để tìm liên kết. Có 3 phản hồi 200 và 1 phản hồi 301.
Không có request listing/detail. Không request sau quyết định dừng, không
retry, browser, Selenium, đăng nhập, proxy, stealth, API nội bộ hoặc host khác.
Chỉ dùng HTTP với User-Agent minh bạch của repository, nghỉ 10 giây trước
mỗi lượt/hop; không tải ảnh/script/tài nguyên liên kết trong HTML.

Các file bằng chứng:

- `robots.json`, `robots.hop-0.body.gz`, `robots.txt`.
- `homepage.json`, `homepage.hop-0.body.gz`, `homepage.txt`.
- `terms.json`, `terms.hop-0.body.gz` (301), `terms.hop-1.body.gz` (200),
  `terms.txt` (text đã đọc).
- `robots-analysis.json`: đối chiếu URL offline, không phải request tới URL đó.
- `access-decision.json`: lý do và phạm vi dừng, không nhận là chấp thuận nguồn.
- `report.json`: số liệu máy đọc được; `baseline-raw.json`: checksum trước thử.

SHA-256 body robots:
`b3d2660b4179fa8b71662be25c0c6b4febec860aba5c8ca2c3a259b1e197b963`.
Body điều khoản cuối:
`97bd2b7a2aedc7add705c382159778acf0388a8a180145a8e98ed25813600393`.

## Đối chiếu robots và điều khoản

### Robots không đồng nghĩa điều khoản cho phép

[Robots chính thức](https://vn.joboko.com/robots.txt) có nhóm áp dụng chung
cho User-Agent dự án. Các vùng cấm gồm tài khoản/CV/ứng viên, ajax và một số
route query/chuyển hướng. Ba quy tắc nguyên văn liên quan:

```text
Disallow: /jobs?*
Disallow: /rd?*
Disallow: /rdn?*
```

Không gọi các route đó. Nhóm cấm toàn bộ `/` dành cho các bot được đặt tên
riêng không bị suy diễn thành cấm toàn bộ cho User-Agent dự án. Phân tích
offline xử lý wildcard trong nhóm phù hợp, không chỉ dựa vào robotparser
vốn không xử lý đầy đủ wildcard.

Homepage có navigation `/tim-viec-lam` và `/viec-lam-moi`; chúng không khớp
Disallow đã lưu. **Chưa request hai URL này**, chưa xác nhận vùng main hay
pagination. Không đổi URL/query để né một đường dẫn bị cấm. Chưa biết URL
detail nên chưa thể xác nhận robots cho các detail cụ thể.

### Lý do dừng là lệnh cấm crawler, không phải quyền từ chối chung

[Điều khoản dịch vụ chính thức](https://vn.joboko.com/dieu-khoan-dich-vu),
cập nhật 31/12/2025, hiệu lực 01/01/2026:

- **Mục 3**, danh sách hành vi không được thực hiện, có cụm nguyên văn
  **“dùng bot/crawler/scrape”**. Đây là hành vi dự định của nhiệm vụ này,
  không chỉ là điều khoản nêu quyền khóa hoặc từ chối dịch vụ.
- **Mục 1** đưa việc truy cập/sử dụng tính năng vào phạm vi người dùng.
  Vì vậy không có căn cứ xem không đăng nhập là ngoại lệ cho bot; tiêu đề
  hướng tới ứng viên không đủ để bỏ qua phạm vi này.
- **Mục 2** định nghĩa cơ sở dữ liệu có bao gồm tin tuyển dụng. Không xem
  nội dung công khai là nằm ngoài các quy định dịch vụ.
- **Mục 9** còn hạn chế sao chép tài sản/nội dung dịch vụ khi chưa có văn
  bản chấp thuận. Phạm vi quyền với từng tin bên thứ ba chưa xác minh;
  không cần suy rộng khoản này để quyết định dừng vì mục 3 đã đủ rõ.

Đây là quyết định tuân thủ quy tắc repository, không phải tư vấn pháp lý.
Không dùng robots hoặc mục đích đồ án làm ngoại lệ tự tạo. Chưa xác nhận
quyền lưu/công bố lại hàng loạt nội dung tuyển dụng. HTML chính sách chỉ
giữ làm bằng chứng cục bộ, không đưa lên Git.

## Số liệu tách listing/detail/pilot

| Chỉ số | Kết quả thực tế |
| --- | --- |
| Request kiểm tra điều kiện | 3 GET: robots + điều khoản/redirect |
| Request tìm navigation/chính sách | 1 GET homepage, không phải listing probe |
| Listing chính thử / thành công | **0 / 0 — chưa thử** |
| URL/ID duy nhất trong main listing | Chưa đo, không dùng card homepage thay thế |
| Phân trang | Chưa xác định |
| Detail thử / thành công / lỗi HTTP | **0 / 0 / 0 — chưa thử** |
| Record detail hợp lệ thực ghi | **0** |
| `jobs.jsonl` / batch raw JobOKO | **Không tạo** |
| Tỷ lệ đủ mô tả/yêu cầu | **N/A**, chưa có detail; không ghi 0% hoặc 100% |
| Thiếu công ty/nội dung, hết hạn, ngày đăng không rõ | Chưa đánh giá |
| Detail ở JobOKO hay redirect sang host khác | Chưa biết; chưa thử detail |
| Pilot khoảng 20 ID mới / kiểm tra resume | Không chạy, không tạo checkpoint giả |
| Mốc 100 / khoảng 299 detail | Không chạy |
| HTTP 401/403/429 hoặc challenge quan sát trong preflight | Không có; không phải lý do dừng |
| Trở ngại | Điều khoản cấm crawler; dừng trước bước 1 |

Không gọi một nguồn khả thi chỉ vì robots/homepage truy cập được. Không có
bằng chứng detail đầy đủ hoặc batch ổn định để tích hợp parser/fetcher/CLI.
Muốn đánh giá tiếp cần quyền/ngoại lệ thực từ JobOKO phù hợp với crawler,
lưu HTML và quy mô dự định, hoặc nguồn dữ liệu chính thức được phép sử dụng;
không chỉ đặt một authorization-reference hoặc sửa quy tắc nội bộ.

## Bảo toàn, kiểm tra và Git

Đối chiếu **1.522 file raw/checkpoint có trước lượt này: không đổi**. Batch
CareerViet 299, CareerLink 55 và Timviec365 299 vẫn giữ nguyên; mọi batch cũ,
HTML/JSONL, incremental state và checkpoint đều được kiểm tra bằng SHA-256.
Không request các nguồn đã có, không sửa code/config/test/fixture cũ.

Git ban đầu sạch trên `main`, HEAD
`7ba563532bf1251dcdc5b380cb377a70968c97d4`. Chỉ thêm báo cáo này; diagnostics
ở `data/` bị gitignore loại khỏi Git. **Không stage, commit hoặc push**.

Kiểm tra offline dù không thay code:

```bash
.venv/bin/pytest -q -m 'not live'    # 205 passed
.venv/bin/ruff format --check .    # 94 files already formatted
.venv/bin/ruff check .             # passed
.venv/bin/mypy src                 # 43 source files, passed
git diff --check                   # passed; báo cáo mới kiểm tra whitespace riêng
```

HTTP chạy qua `scripts.public_source_probe.capture(root, label, url, delay=10)`
cho robots, homepage rồi điều khoản tìm được từ footer, tuần tự. Phân tích
robots, quyết định dừng, đếm request và checksum chạy bằng Python **offline**
trên những phản hồi đã lưu. Không có lệnh crawl hoặc resume JobOKO hợp lệ
được tạo trong lượt này vì nguồn chưa qua điều kiện trước probe.
