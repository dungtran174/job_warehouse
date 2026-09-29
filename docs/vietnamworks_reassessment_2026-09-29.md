# VietnamWorks — phép thử live mới tại `/tim-viec-lam`, 29/09/2026

## Kết luận và phạm vi

**Đã gửi request live mới**, không suy diễn trạng thái từ lỗi 403 cũ.
`https://www.vietnamworks.com/tim-viec-lam` trả **HTTP 200**, URL cuối giữ nguyên,
không redirect sang `/viec-lam`, không phát hiện challenge. Tuy nhiên đây là
**landing khám phá việc làm theo các khối tuyển gấp/hot/lương cao**, không phải
danh sách kết quả tìm kiếm chính có phân trang. Không lấy 330 ID trong các khối
này làm discovery của batch, không fetch detail từ chúng.

Lượt này dừng ở **xác minh listing chính**, không phải tại 403, thiếu chấp thuận
bằng văn bản, hay parser detail. Chưa chứng minh có thể chạy batch như CareerViet;
cũng không kết luận VietnamWorks hiện thất bại về truy cập detail. Ba detail
chẩn đoán cũ giữ riêng; batch raw cũ vẫn 0 dòng. Không tạo batch/raw giả cho lượt mới.

| Chỉ số riêng lượt mới | Kết quả |
| --- | ---: |
| Request kiểm tra điều kiện | 2 GET: robots + thỏa thuận, đều 200 |
| Request URL ứng viên listing | 1 GET, HTTP 200 |
| Tổng request live / redirect / retry | **3 / 0 / 0** |
| Listing ứng viên thử / listing chính thành công | **1 / 0** |
| ID thuộc kết quả tìm kiếm chính đã xác minh | **0** trong phản hồi này |
| Liên kết detail ở các khối không phải main | 389 liên kết, **330 ID duy nhất** |
| URL trang kế tiếp của kết quả chính | `null` — chưa xác định |
| Detail mới thử / truy cập được / hợp lệ | **0 / 0 / 0** |
| Dòng `jobs.jsonl` mới thực ghi | **0**, không tạo batch mới |
| Đủ mô tả / yêu cầu | **N/A**, chưa thử detail mới |
| HTTP 401/403/429 / challenge | **0 / 0** |
| Browser / API / đăng nhập / đổi danh tính | **0 / 0 / 0 / 0** |
| Pilot 20 / mốc 100 / mốc 300 | **Chưa chạy** — điều kiện listing và 3 detail chưa đạt |

“0 ID main” không có nghĩa VietnamWorks không có tin tuyển dụng. Nguồn hiển thị
`totalJobsOnline=10576`; đây là tổng do nguồn báo, **không phải số đã discovery,
fetch detail hoặc lưu raw**. HTTP 200 cũng không được tính là listing chính thành công.

## Điều kiện truy cập và thời điểm

Đã đọc README, AGENTS.md, adapter, fetcher HTTP/render, parser listing/detail,
test unit/integration, checkpoint/manifest/errors và HTML VietnamWorks cũ trước live.
CLI hiện hỗ trợ sample owner 1 listing/3 detail; cấu hình này validate thành công.
Không sửa quy tắc hoặc giả `authorization-reference` để chạy phép thử.

| Mục đích | URL yêu cầu = URL cuối | Bắt đầu UTC 29/09/2026 | HTTP |
| --- | --- | --- | ---: |
| Robots | https://www.vietnamworks.com/robots.txt | 08:35:46.681311 | 200 |
| Thỏa thuận | https://www.vietnamworks.com/thoa-thuan-su-dung | 08:36:32.627515 | 200 |
| Landing được yêu cầu | https://www.vietnamworks.com/tim-viec-lam | 08:37:50.566666 | 200 |

Giờ Việt Nam: **15:35–15:37 ngày 29/09/2026**. HTTP một luồng, User-Agent minh
bạch cố định `job-warehouse-crawler/0.1 (public academic research; single-threaded)`;
nghỉ ít nhất 10 giây trước từng GET, không retry. Lưu body/status/URL cuối ngay
sau nhận phản hồi, **trước phân loại lỗi, parser hoặc đổi fetcher**.

Robots mới nhóm `User-agent: *` không có Disallow khớp `/tim-viec-lam`, `/viec-lam`,
`/viec-lam?page=2` hoặc trang thỏa thuận. Đối chiếu cả RobotFileParser và guard
wildcard bảo thủ của repository; đọc BOM UTF-8 đúng cách. Chỉ các URL robots và
thỏa thuận/landing trong bảng đã được GET; kiểm tra robots cho `/viec-lam` và
`?page=2` **không phải đã request các trang ấy**. Chưa discovery detail main nên
không giả kết quả robots cho những URL detail chưa có.

Đã đọc toàn văn trang thỏa thuận mới (844 dòng text gồm navigation/form/footer).
Các giới hạn tại mục dịch vụ, mục đích sử dụng và sở hữu trí tuệ vẫn hiện diện:
quyền từ chối dịch vụ cho người khai thác ngoài mục đích tuyển dụng; việc dùng
sai mục đích có thể bị đánh giá vi phạm; giới hạn sao chép và ngoại lệ bản sao
với số lượng hợp lý dùng nội bộ. Không thấy lệnh cấm áp dụng rõ ràng riêng cho
mẫu kỹ thuật nhỏ phi thương mại này; **không xác nhận quyền thu thập quy mô lớn,
chia sẻ hoặc tái công bố toàn văn**. [Thỏa thuận hiện hành](https://www.vietnamworks.com/thoa-thuan-su-dung).

Đối chiếu thêm [báo cáo toàn văn/OCR cũ](vietnamworks_policy_check_2026-09-26.md),
không tải PDF lại trong lượt này và không tuyên bố đã xác minh lại hiệu lực PDF.
`owner-decision.json` ghi `access_basis=project_owner_public_test`,
`authorization_reference=null`, `source_authorization=false`. Quyết định của
chủ dự án và robots **không phải chấp thuận của VietnamWorks**.

## Đối chiếu HTML mới: không nhầm landing với main hoặc khung Loading

Phản hồi HTTP gồm **1.982.117 byte**, SHA-256:
`f19691bc6c0553b09148b9bb883b069752cd42b19aae06bbbe0d9cda59eec210`.

- `__NEXT_DATA__.page` là `/tim-viec-lam`; canonical cũng là URL này.
- `pageProps.jobsData` có `urgentJobs`, `featuredJobs`, `partTimeJobs`,
  `highSalaryJobs`, `headhunterJobs`, `bestJobs`, các nhóm thành phố/ngành/cấp bậc,
  `totalJobsOnline` và `companies`. Không có payload kết quả tìm kiếm chính/phân trang.
- Tất cả 389 anchor detail đều nằm trong các block `#vnwLayout__col` có heading
  tuyển gấp/hot/bán thời gian/lương cao/việc làm tốt nhất/công ty đầu ngành.
  Không chỉ dựa vào selector cũ để kết luận: đã đối chiếu ancestry DOM, heading
  và cấu trúc JSON nhúng của chính phản hồi mới.
- Không có `.block-job-list .search_list`, không có pagination main, **0 lần
  xuất hiện `Loading`**. Đây không phải lỗi cũ “HTTP 200 chỉ có khung tải dữ liệu”.
- Có 65 control `recommend-jobs-pagination-*`; chúng thuộc carousel gợi ý,
  **không phải nút sang trang 2 của main search**.

| Heading block không phải kết quả chính | Anchor detail |
| --- | ---: |
| Tuyển dụng Gấp | 72 |
| Việc làm đang Hot | 72 |
| Việc làm bán thời gian | 29 |
| Việc làm lương cao | 72 |
| Việc làm tốt nhất | 72 |
| Việc làm công ty đầu ngành | 72 |
| Tổng anchor / tổng ID dedup | **389 / 330** |

Không render lại URL này: HTTP đã chứa nội dung của landing và JSON phân nhóm,
không thiếu nội dung vì khung Loading. Không tự bấm/tải thêm route để thay thế
URL được giới hạn một lượt trong phép thử. Kết luận giới hạn ở HTML HTTP đã lưu;
**chưa thử giao diện sau render hoặc listing `/viec-lam` mới**. Không gọi JSON API,
đọc asset JS, sitemap, hoặc tải detail từ tin gợi ý để lách điều kiện main.

Bước tiếp theo phù hợp là một phép thử riêng tại **listing tìm kiếm chính
`/viec-lam`**, kiểm tra main và pagination hiện tại trước lấy detail. Đường sang
`/viec-lam?page=2` từng được xác minh ngày 26/09 là **bằng chứng lịch sử**, chưa
được coi là pagination hoạt động ngày 29/09. Chưa cần nới giới hạn batch lên 300
khi chưa có listing chính và mẫu detail mới đủ nội dung.

## Dữ liệu cũ giữ riêng

[Pilot cũ](vietnamworks_batch_pilot_2026-09-26.md):
`data/raw/vietnamworks/snapshot_date=2026-09-26/batch_id=20260926T151442Z-1439f601/`
vẫn có **0 dòng**, listing cũ pending, detail queue rỗng, lỗi browser 403/nginx
giữ nguyên. Không mở/resume batch này hoặc chỉnh lại lịch sử.

Ba HTML chẩn đoán cũ ID 2109839, 2107184, 2107466 đã đọc/parse lại **offline**,
không fetch lại và không ghi vào raw. Đây vẫn là ba tin nổi bật của probe cũ,
không phải mẫu từ main listing mới. HTML diagnostic main ngày 26/09 có 50+50 ID;
không cộng các ID này vào lượt ngày 29/09.

## Bằng chứng cục bộ, file thay đổi và kiểm tra

Artifact ở `data/diagnostics/vietnamworks_reassessment/20260929T083452Z/`:

- `before.json`, `preservation-after.json`: checksum, số dòng/ID, Git trước/sau.
- `owner-decision.json`, `policy-review.json`: cơ sở quyết định và giới hạn diễn giải.
- `robots.json`, `robots.hop-0.body.gz`, `robots-analysis.json`: status/body/rules.
- `terms.json`, `terms.hop-0.body.gz`, `terms.txt`: trang thỏa thuận mới.
- `listing.json`, `listing.hop-0.body.gz`: status/URL/body HTTP duy nhất tại landing.
- `listing-offline-audit.json`, `listing-next-data-shape.json`: ID, DOM/JSON, phân loại.
- `old-evidence-analysis.json`, `stop.json`, `summary.json`, `quality-checks.json`.

Các artifact `data/` bị Git ignore và **chỉ lưu cục bộ**, không có trong bản clone.
Không lưu cookie/token/auth headers; không công bố HTML hoặc toàn văn tin.

Thay đổi của lượt này chỉ gồm báo cáo này, fixture nhỏ
`tests/fixtures/vietnamworks/discovery_landing_20260929.html`, và regression test
trong `tests/unit/test_vietnamworks_listing_parser.py`,
`tests/integration/test_vietnamworks_engine.py`. Fixture rút gọn cấu trúc, thay
title/slug/nội dung mẫu, không chứa IP người dùng, công ty hoặc toàn văn detail.
Parser/fetcher/CLI **không sửa**: chúng đang đúng khi loại các khối không phải main.

Kiểm thử offline đã chạy:

```bash
.venv/bin/pytest -q tests/unit/test_vietnamworks_listing_parser.py tests/unit/test_vietnamworks_detail_parser.py tests/unit/test_vietnamworks_offline.py tests/integration/test_vietnamworks_engine.py
.venv/bin/ruff format tests/unit/test_vietnamworks_listing_parser.py tests/integration/test_vietnamworks_engine.py
.venv/bin/pytest -q
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
git diff --check
```

**33 test VietnamWorks đạt; toàn suite 252 test đạt (11,23 giây)**.
Ruff format: 108 file đúng định dạng; Ruff check đạt; mypy 46 source file đạt;
`git diff --check` đạt. Test mới xác nhận landing có ID/card/carousel/JSON vẫn
không enqueue main, không render, không fetch detail hoặc ghi raw trong engine
mô phỏng. Test không gọi website và batch mô phỏng chỉ ở thư mục tạm của pytest.

Checksum trước/sau toàn bộ **2.072 file raw** và **24 file diagnostic VietnamWorks
cũ** không đổi. Các batch được yêu cầu vẫn có số dòng/ID duy nhất:
CareerViet **299**, Timviec365 **299**, CareerLink **75**, Việc Làm 24h **104**.
Giữ mọi checkpoint/state/HTML/error cũ và các thay đổi Git có sẵn.
Nhánh `main`, HEAD `7ba563532bf1251dcdc5b380cb377a70968c97d4` không đổi,
index không đổi; **không stage, commit hoặc push**.
