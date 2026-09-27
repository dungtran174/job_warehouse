# Timviec365 — dừng ở bước kiểm tra quy chế, 27/09/2026

## Kết luận

**BLOCKED: chưa hoàn tất kiểm tra Quy chế hoạt động trước probe.** Trang chủ và
Thỏa thuận sử dụng truy cập được qua HTTP; PDF Quy chế do chính footer liên kết
nằm trên host có robots cấm mọi đường dẫn. Không tải PDF, không dùng browser,
cache/search mirror hoặc host khác để né quy định đó. Chưa gửi request listing/detail.

Đây **không phải** kết luận Timviec365 thất bại về kỹ thuật hoặc robots của trang
việc làm cấm crawl. Chưa đủ bằng chứng để xếp nguồn là ổn định, lấy được mẫu,
hay detail thiếu dữ liệu. Nếu phải đặt vào nhóm dừng triển khai thì thuộc nhóm 3
**tạm thời do bước xác minh quy chế bị chặn**, không phải do listing/detail 403.
Không tạo crawler hoàn chỉnh khi cổng trước probe chưa hoàn tất.

## Phạm vi và bằng chứng truy cập

Thử theo yêu cầu chủ dự án, không phải chấp thuận của Timviec365; không dùng
authorization-reference giả. Chỉ HTTP, một luồng; không đăng nhập, proxy, đổi IP/UA,
stealth, CAPTCHA solver hoặc API nội bộ. Không gọi CareerLink/VietnamWorks.

Artifact cục bộ, không commit:
`data/diagnostics/timviec365_assessment/20260926T172842Z/`.
Mỗi phản hồi có `*.hop-0.body.gz`, `*.json` chứa URL/status/thời điểm/hash,
và `*.txt` trích text. Không lưu cookie/header xác thực vào metadata.

Thời gian dưới đây là lúc bắt đầu request UTC ngày 26/09/2026; tương ứng
00:28–00:30 ngày 27/09/2026 tại Việt Nam. Mỗi URL cuối giữ nguyên, không redirect.

| Nhãn artifact | URL | Thời điểm UTC | HTTP | Kết quả |
| --- | --- | --- | ---: | --- |
| robots | https://timviec365.vn/robots.txt | 17:28:52.546266 | 200 | Allow / kèm các Disallow cụ thể |
| homepage | https://timviec365.vn/ | 17:29:19.165956 | 200 | Navigation có /viec-lam và link quy chế |
| terms | https://timviec365.vn/thoa-thuan-su-dung.html | 17:29:44.049649 | 200 | Đã đọc toàn văn thỏa thuận HTML |
| policy-host-robots | https://storage1.timviec365.vn/robots.txt | 17:30:25.927805 | 200 | Disallow / cho mọi crawler |

Tổng 4 request thực tế, không retry; khoảng cách giữa thời điểm bắt đầu request:
26,620 / 24,884 / 41,878 giây. Trước mỗi lượt dùng delay 10 giây; đây là preflight,
**chưa phải** pilot với delay ngẫu nhiên 10–15 giây.
Ghi nhận quyết định dừng lúc 17:31:13 UTC (00:31:13 ICT); không có request sau
lượt kiểm tra robots của host PDF. Không có HTTP 401/403/429 hoặc challenge được
quan sát trong bốn phản hồi này; lý do dừng là robots/policy preflight.

## Quy định đã kiểm tra và phần chưa biết

### Robots trên host chính

[Robots host chính](https://timviec365.vn/robots.txt) có `User-agent: *`, `Allow: /`
và các vùng cấm, gồm `/admin/*`, `/ajax/*`, `/tim-kiem`, vùng ứng viên,
`/nha-tuyen-dung/` và query `type_search`. Không xem Allow / là cho phép bỏ qua
Disallow cụ thể. Đường dẫn `/viec-lam` được tìm từ hai anchor nhãn “Việc làm”
trên homepage; nó không khớp các vùng cấm đã lưu. Chưa request đường dẫn này,
chưa xác định vùng kết quả, ID, canonical hoặc phân trang.

### Thỏa thuận HTML

[Thỏa thuận sử dụng](https://timviec365.vn/thoa-thuan-su-dung.html), mục 1.1:

> Nghiêm cấm mọi hành vi sao chép, sử dụng và phổ biến bất hợp pháp các nội dung trên.

Khoản này hạn chế hành vi bất hợp pháp, không tự nó xác định mọi lượt thu thập
tin công khai cho đồ án là bị cấm. Các khoản chấm dứt dịch vụ ở mục 1.1 nói về
thành viên/vi phạm; không diễn giải chúng thành lệnh cấm crawler chung.
Mục 2.1.b hạn chế nhà tuyển dụng/người đăng tin sao chép/phân phối công cụ dịch vụ
cho bên thứ ba khi chưa được đồng ý; không đánh đồng với mọi lượt đọc tin.
Chưa thấy trong HTML một lệnh cấm tự động áp dụng rõ ràng cho phạm vi thử nội bộ
này. Đây không phải kết luận pháp lý hay giấy phép tái xuất bản nội dung.

### Quy chế PDF — chưa đọc, không suy đoán nội dung

Footer homepage liên kết chính thức tới
[Quy chế hoạt động](https://storage1.timviec365.vn/timviec365/manual/quy_che_cong_ty_HHP.pdf).
Trước khi tải PDF, đã kiểm tra
[robots của host lưu PDF](https://storage1.timviec365.vn/robots.txt), nguyên văn:

```text
User-agent: *
Disallow: /
```

Đánh giá offline URL PDF với robots đã lưu: `can_fetch=False`.
HTTP 200 của robots chỉ nói file robots đọc được, không có nghĩa PDF được phép tải.
Không biết HTTP status/nội dung/số trang/ngày hiệu lực của PDF vì chưa yêu cầu nó;
không OCR hay trích khoản PDF chưa đọc. Cấm trên host storage không đồng nghĩa
cấm `/viec-lam` ở host chính. Trở ngại là chưa kiểm chứng đầy đủ quy chế mà yêu
cầu đặt trước probe; không tự bỏ bước này để chạy 100–300 detail.

## Số liệu probe/batch

| Chỉ số | Kết quả |
| --- | --- |
| Listing chính thử / tải được | 0 / 0 — chưa thử |
| ID/URL main duy nhất, phân trang | Chưa biết |
| Detail thử / thành công / thất bại | 0 / 0 / 0 — chưa thử |
| Record mới / dòng jobs.jsonl được tạo | 0 / 0 |
| Tỷ lệ detail hợp lệ | N/A, không có mẫu |
| Độ đầy đủ từng trường, nhiều địa điểm/lương | Chưa đo, không gán 0% thiếu |
| ID/URL trùng | Chưa đo |
| Pilot 20 / chặng 100 / chặng 300 | Không chạy |
| Batch raw / checkpoint / HTML detail Timviec365 | Chưa tạo |

Không lấy card homepage làm detail, không tạo jobs.jsonl hoặc checkpoint rỗng
để thể hiện đã chạy batch. Vì chưa tích hợp nguồn vào CLI, **chưa có lệnh resume
Timviec365 hợp lệ**; không cung cấp một lệnh giả có source/batch không tồn tại.
Muốn tiếp tục: cần bản Quy chế chính thức được cung cấp hợp lệ để đọc offline
hoặc một đường dẫn chính thức cho phép truy cập; sau đó kiểm tra lại điều kiện
nguồn trước probe 1 listing/3 detail. Không retry tự động hoặc né robots host PDF.

## Bảo toàn, kiểm thử và Git

- Đối chiếu SHA-256 toàn bộ **567 file raw/checkpoint cũ: không đổi**.
- CareerViet 299 dòng; jobs SHA-256:
  `018aa543af009120e4d7d1a1119091faaced9fe7616e00e8c927684543a1afdc`.
- CareerLink 55 dòng; jobs SHA-256:
  `a2133e710dc0db966ad0ba9bc202dc63da9eb3b62b07ecd157234e691fb87be1`.
- Không thay code/test/config/CLI, không sửa dữ liệu VietnamWorks hoặc batch cũ.
  Chỉ thêm báo cáo này và artifact diagnostics cục bộ. Không làm Bronze/Silver.
- `pytest`: 159 passed; Ruff format: 82 file không đổi; Ruff check đạt;
  mypy: đạt, 39 source file. Không có parser/test Timviec365 mới vì chưa qua probe.
- `git diff --check` dùng cho tracked; báo cáo mới kiểm tra whitespace riêng.
  Không stage, commit hoặc push. HEAD giữ `2eef4fe` trên `main`.

Lệnh kiểm tra đã chạy:

```bash
.venv/bin/pytest -q -m 'not live'
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/mypy src
git diff --check
```

HTTP preflight chạy qua `.venv/bin/python` gọi `scripts.public_source_probe.capture`
với bốn URL trong bảng, `delay=10`, cùng User-Agent minh bạch của repository.
Mỗi lượt được đọc kết quả trước khi quyết định request kế tiếp; không chạy crawler CLI.
Tóm tắt máy đọc được: `report.json` trong thư mục diagnostics ở trên.
