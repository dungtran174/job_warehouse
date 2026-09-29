# TopCV — thử lại live theo quyết định chủ dự án, 29/09/2026

## Kết luận

**Đã gửi request live mới sau khi cập nhật quy tắc nội bộ.** Không suy diễn trạng
thái hiện tại từ lần thử cũ, không dừng vì thiếu văn bản chấp thuận. Robots hiện
tại HTTP 200 và không cấm URL listing định thử. Nhưng **chính request listing
mới trả HTTP 403**, trang Cloudflare “Attention Required!” với thông báo bị chặn.
Lưu body/status/URL cuối trước khi dừng, không đổi công cụ hoặc tiếp tục nguồn.

| Chỉ số của lượt mới | Thực tế |
| --- | --- |
| Tổng request live | **2 GET**, 1 robots + 1 listing |
| Robots / URL listing được robots cho phép | 200 / có |
| Listing thử / thành công | **1 / 0**; HTTP **403**, không có nội dung main |
| URL/ID main duy nhất phát hiện | **0** trong phản hồi bị chặn, không phải TopCV có 0 tin |
| Detail thử / truy cập được / hợp lệ | **0 / 0 / 0 — chưa tới bước detail** |
| Dòng raw `jobs.jsonl` thực ghi mới | **0**, không tạo batch/file rỗng |
| Tỷ lệ đủ mô tả / yêu cầu | **N/A**, mẫu detail rỗng; không ghi 0% |
| Lỗi | **1**, listing HTTP 403 / Cloudflare access-denied |
| Browser / JSON API / sitemap / retry | **0 / 0 / 0 / 0** |
| Pilot tối đa 20 detail | **Không chạy**, chưa có mẫu 3/3 hợp lệ |
| Điểm dừng | Listing chính HTTP 403, trước parser/detail/render |

Đây là kết quả **kỹ thuật mới của một URL và cách truy cập HTTP này**, không
phải kết luận TopCV vĩnh viễn không crawl được. Chưa biết detail hiện tại có
đủ nội dung, phân trang hoạt động, hoặc pilot ổn định không vì listing đã bị chặn.
Không lấy sitemap, URL detail cũ, tin gợi ý hay quảng cáo để lách bước discovery.

## Quy tắc đã làm rõ và cơ sở quyết định

Đọc README, AGENTS.md, đặc tả crawler TopCV, code config/CLI/fetcher/parser,
test cơ sở owner và log/HTML cũ trước khi thử. README và AGENTS được bổ sung:

- Phép thử kỹ thuật công khai có yêu cầu rõ của chủ dự án **không bắt buộc văn
  bản của chủ website**; thiếu văn bản tự nó không phải lý do dừng sample.
- Ghi `access_basis=project_owner_public_test`, `authorization_reference=null`.
  **Không phải sự chấp thuận của TopCV**, không xác nhận quyền dùng dữ liệu
  quy mô lớn; không tạo mã chấp thuận giả hoặc tái sử dụng reference cũ.
- Cho lượt TopCV mới 1 listing/3 detail, HTTP trước, một luồng, nghỉ ít nhất
  10 giây, không retry khi bị chặn. Browser chỉ sau HTTP 200 bình thường cần JS.
- Giữ điều kiện dừng robots/401/403/429/CAPTCHA/challenge, kể cả HTTP 200.
  Chỉ khi 3/3 detail đủ nội dung mới xem xét pilot tối đa 20; không phải gate
  `pilot` 250 của CareerViet, chưa cho mở rộng 100/300/full snapshot.

CLI/config **đã có đường owner sample 1/3 không cần authorization-reference**.
Không cần xóa guard hoặc sửa config để gửi probe; test mới kiểm chứng trực tiếp
đường TopCV này. Không nới guard pilot vì mẫu chưa đạt. Quyết định thật từ chat
được lưu trong `owner-decision.json` trước request. Giữ nguyên ngoại lệ JobOKO
và các thay đổi/tài liệu có sẵn, không sửa kết quả thử trước.

Quyết định nội bộ không thay đổi điều khoản TopCV hoặc cấp quyền sao chép/tái
công bố dữ liệu. **Chưa xác minh quyền khai thác quy mô lớn.** Không đọc được
footer listing để xác định chính sách hiện tại; sau 403 không gửi thêm request
điều khoản/homepage. Vì vậy không tuyên bố đã kiểm tra điều khoản online mới
nhất hoặc suy ra được phép từ robots. Mọi body chỉ là bằng chứng cục bộ.

## Lần thất bại cũ đã được đối chiếu

Batch cũ:
`data/raw/topcv/snapshot_date=2026-09-22/batch_id=20260922T090917Z-488cb4e3/`.
Manifest: listing 1/1, 48 ID, detail 1/0, raw 0; fetcher thực tế Playwright,
trạng thái `stopped/browser_challenge`. `errors.jsonl` ghi **stage=detail**,
HTTP **403**, ID **2303107**, timestamp **2026-09-22T09:09:47.585876Z**.

URL detail bị chặn cũ:
`https://www.topcv.vn/viec-lam/nhan-vien-kinh-doanh-sales-thi-truong-tu-van-ban-hang-nganh-me-be-1-nam-kinh-nghiem-thu-nhap-tu-10-trieu-di-lam-ngay/2303107.html`.

HTML gốc:
`html/captcha-002-2303107.html.html.gz`, tiêu đề **Attention Required! | Cloudflare**.
Thông điệp trong error cũ ghi browser dừng tại captcha; không suy từ nhãn đó
thành đã nhìn thấy CAPTCHA tương tác trong lượt mới. Screenshot và HTML cũ
giữ nguyên. `old-failure-analysis.json` lưu URL/bước/status, title/hash body.
Giá trị authorization-reference trong manifest cũ chỉ được giữ như lịch sử,
không được xác nhận là văn bản của chủ TopCV và **không dùng lại** cho lượt này.

Diagnostic HTTP listing cũ lúc 08:39 ngày 22/09 trả 200, và một batch trước
`20260922T085820Z-83c86cd5` từng ghi một record TopCV. Không phủ nhận record đó,
không cộng vào số liệu mới. **Khác biệt lần này: chặn ngay listing HTTP**, chưa
thử detail. Không gửi request tới URL detail 2303107 hoặc resume batch cũ.

## Robots và request mới

| Mục đích | URL yêu cầu = URL cuối | Bắt đầu UTC 29/09/2026 | HTTP |
| --- | --- | --- | ---: |
| Robots hiện tại | https://www.topcv.vn/robots.txt | 03:22:36.372803 | **200** |
| Listing chính theo config | https://www.topcv.vn/tim-viec-lam-moi-nhat?type_keyword=1&sba=1 | 03:23:47.680859 | **403** |

Giờ Việt Nam = UTC + 7: khoảng 10:22–10:23 ngày 29/09. Không redirect trong
hai request, User-Agent minh bạch cố định của repo. Nghỉ 10 giây trước mỗi GET,
thực tế thời điểm bắt đầu hai request cách nhau hơn một phút. Không retry,
đổi User-Agent/IP/proxy, dùng cookie/tài khoản, browser, giải CAPTCHA hoặc API.

Robots nhóm `User-agent: *` cấm các vùng CV riêng tư và route `/p/`, không có
Disallow khớp path/query của listing định thử. Guard đối chiếu wildcard trên
path + query và kiểm tra host/robots trước từng request/hop. Không gọi sitemap
dù robots có URL sitemap, không gọi các đường dẫn CV/tài khoản bị cấm.
Không có URL detail mới vì listing chưa đọc được để chọn; không giả kết quả
robots cho những URL detail chưa được discovery.

SHA-256 robots:
`a50ac03683ec4a09b502bd752cfa1dcfe28978613d698296a740e68921edd421`.
SHA-256 body listing 403:
`d2008f92ca4a73857d5e4ef9ebaeef0d0960be16e01b8d6ac1d333279220639a`.
Body 5.017 byte, title Cloudflare, thông báo bị chặn; **0 link `/viec-lam/`**.
Đây không phải HTTP 200 app shell thiếu JavaScript, nên **không render**.

## Bằng chứng, kiểm thử và bảo toàn

Thư mục mới:
`data/diagnostics/topcv_reassessment/20260929T032042Z/`.
Các artifact `data/` bên dưới **chỉ lưu cục bộ, không commit**, không có khi clone.

- `owner-decision.json`: cơ sở chủ dự án, không chấp thuận nguồn, giới hạn thật.
- `old-failure-analysis.json`: đối chiếu log/HTML cũ, không sửa lịch sử.
- `robots.json`, `robots.hop-0.body.gz`, `robots.txt`, `robots-analysis.json`:
  URL/status/thời điểm và guard cho URL listing định truy cập.
- `listing.json`, `listing.hop-0.body.gz`: nguyên response lưu **trước** dừng.
- `listing-request-log.json`: đúng một lần gọi listing, không retry/redirect.
- `listing-offline-audit.json`: title/0 link việc làm/cờ dừng; không gọi nó là
  parser main listing thành công. Body có thể chứa IP/mã trace/phiên nên không
  in/công bố toàn văn, không đưa raw hoặc thông tin đó vào tài liệu Git.
- `report.json`: counter máy đọc được, coverage N/A và điểm dừng thật.
- `baseline-raw.json`, `baseline-protected.json`, `baseline-policies.json`,
  `preservation-check.json`: checksum trước/sau và các policy được phép sửa.

File mới `tests/unit/test_topcv_owner_probe.py`, **9 test cases offline**:
CLI TopCV owner 1/3 không yêu cầu source reference; không trộn provenance hoặc
vượt cap/đi tắt sang pilot; 401/403/429 và challenge HTTP 200 lưu nguyên body
trước dừng, đúng một lần gọi, không retry. Không dùng website thật trong test.
Không thay parser/fetcher/engine của nguồn cũ hoặc tạo fixture từ trang chặn
rồi tính nó là một detail hợp lệ.

Lệnh đã chạy: `git status --short`, `rg`/`sed` đọc repo, các đoạn Python offline
đọc gzip/hash/log; áp dụng thay đổi README/AGENTS bằng patch. `apply_patch` cập
nhật gặp lỗi sandbox mountinfo nên dùng patch tương đương qua `git apply
--unidiff-zero -`, không stage/reset. Hai GET thực dùng
`scripts.public_source_probe.capture(..., delay=10)`; request hook kiểm tra
scope/robots cho listing. Không chạy `job-crawler crawl` hoặc resume live.

```bash
.venv/bin/pytest -q -m 'not live'                 # 214 passed, 15.65s
.venv/bin/ruff format tests/unit/test_topcv_owner_probe.py
.venv/bin/ruff format --check .                  # 99 files already formatted
.venv/bin/ruff check .                           # All checks passed
.venv/bin/mypy src                               # 43 source files, passed
git diff --check                                # passed; file mới kiểm tra riêng
```

**1.522 file raw/checkpoint và 127 file code/test/script/docs có trước không
đổi**, đối chiếu SHA-256. CareerViet 299, Timviec365 299, CareerLink 55 và mọi
batch TopCV/VietnamWorks/JobOKO cũ giữ nguyên; không request các nguồn khác.
Chỉ bổ sung quy tắc TopCV vào README/AGENTS, thêm test và báo cáo này; các
thay đổi Git JobOKO/tài liệu untracked từ trước vẫn giữ nguyên. Diff tracked
toàn worktree có cả thay đổi JobOKO trước lượt này, không nhận toàn bộ là
thay đổi TopCV. Không stage, commit hoặc push; HEAD không đổi.

Chưa tới điều kiện tích hợp/pilot. Muốn thử thêm cần một yêu cầu mới và điều
kiện truy cập phù hợp; không tự retry listing hoặc chuyển công nghệ để đạt số
record. Không đề xuất mở rộng 100/300 dựa trên kết quả hiện tại.
