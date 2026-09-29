# JobOKO — rà soát yêu cầu mẫu live 1 listing / 3 detail

Thời điểm rà soát: **2026-09-28T16:18:11 UTC** (23:18:11 giờ Việt Nam).
Đây là biên bản **mới**, không sửa báo cáo, metadata hoặc lịch sử kiểm tra cũ.

## Kết quả

**BLOCKED_REPOSITORY_POLICY — dừng trước mọi request mới.**
Chủ dự án yêu cầu đánh giá kỹ thuật mẫu nhỏ và đã biết hạn chế bot; không ghi
nhận yêu cầu này là chấp thuận của JobOKO. Không tự sửa quy tắc repository,
không tạo authorization-reference giả. Cơ sở yêu cầu vẫn được ghi
`project_owner_public_test`, `authorization_reference=null`.

| Chỉ số trong lượt này | Thực tế |
| --- | --- |
| Request mới kiểm tra điều kiện, gồm làm mới robots | **0** |
| Listing thử / thành công | **0 / 0 — chưa thử** |
| URL/ID thuộc main listing duy nhất | **Chưa đo**, không dùng card homepage |
| Detail thử / thành công / hợp lệ | **0 / 0 / 0 — chưa thử** |
| HTTP status / URL cuối listing và detail | **N/A**, chưa có request |
| Record mới ghi vào `jobs.jsonl` | **0**, không tạo batch/file rỗng |
| Trường thiếu / tỷ lệ đủ mô tả, yêu cầu | **Chưa đánh giá / N/A**, không ghi 0% |
| Lỗi HTTP mới / challenge mới | **0 / 0**, không phải lý do dừng |
| Browser, retry hoặc tích hợp crawler | **Không thực hiện** |
| Điểm dừng | Rà soát điều kiện trước bước làm mới robots/listing |

**Khả năng truy cập kỹ thuật của listing/detail JobOKO vẫn chưa biết.** Không
gọi 0 lần thử là 0% thành công, không kết luận kỹ thuật thất bại hoặc khả thi.
Chưa kiểm chứng ID ổn định, nội dung đầy đủ, trường tùy chọn, hết hạn hay host
cuối của detail. Homepage/robots 200 cũ không trả lời được những câu hỏi đó.

## Ràng buộc chính xác trong repository

- [README dòng 18–19](../README.md#cổng-an-toàn-và-phạm-vi): đường thử theo
  quyết định chủ dự án chỉ áp dụng nếu robots **và điều khoản không cấm** hoạt
  động dự định. Dòng 20–21 phân biệt quyết định chủ dự án với chấp thuận nguồn.
- README dòng 31 yêu cầu dừng khi điều khoản cấm, không chỉ khi HTTP bị chặn.
- [AGENTS.md](../AGENTS.md), dòng 22 yêu cầu tôn trọng điều khoản; dòng 24
  yêu cầu dừng/báo cáo nếu điều khoản không cho phép.

[Điều khoản JobOKO](https://vn.joboko.com/dieu-khoan-dich-vu) **bản đã lưu**
ngày 28/09 lúc 14:39:11.303812 UTC, §3 có cụm “dùng bot/crawler/scrape” trong
danh sách hành vi không được thực hiện. Cụm này được ngăn bằng dấu chấm phẩy
với hành vi thu thập dữ liệu người dùng trái phép; §1 đưa việc truy cập/sử dụng
vào phạm vi người dùng. Vì vậy không coi không đăng nhập, mẫu 1/3 hoặc chỉ đọc
tin công khai là một ngoại lệ đã được nguồn công bố. Quyền khóa tài khoản nói
sau danh sách không phải căn cứ độc lập cho quyết định dừng.

Đã xác minh trực tiếp cụm trên trong body HTML gzip cũ và đối chiếu SHA-256
với metadata, không chỉ dựa vào phần kết luận của báo cáo. Không tải lại điều
khoản trong lượt này và không tuyên bố đã kiểm tra phiên bản online mới nhất.

Không có adapter JobOKO trong `DEFAULT_START_URLS`; CLI hiện không nhận source
`joboko` và config sẽ báo `Unsupported source`. **Đây không phải lý do quyết
định dừng phép probe**: công cụ `scripts/public_source_probe.capture` có thể
lưu HTTP độc lập, nhưng không phải authorization gate; người gọi vẫn phải
tuân thủ quy tắc điều khoản trước request. Không gọi công cụ đó trong lượt này.

## Robots: phân biệt bản lưu với kiểm tra hiện tại

URL dự kiến từ navigation homepage đã lưu:
`https://vn.joboko.com/tim-viec-lam`.
Chưa xác nhận đây là listing chính đầy đủ vì chưa request. Không chuyển sang
URL khác để tránh quy định; chưa chọn URL detail từ homepage.

Robots gần nhất trong bằng chứng:
`https://vn.joboko.com/robots.txt`, **HTTP 200**, URL cuối giữ nguyên,
**2026-09-28T14:38:06.584813 UTC** (21:38:06 giờ Việt Nam).
Phân tích offline cũ không thấy Disallow khớp `/tim-viec-lam` hoặc
`/viec-lam-moi` với User-Agent dự án. Có Disallow cho `/jobs?*`, `/rd?*`,
`/rdn?*`; không gọi các route đó. Chưa có detail URL để đối chiếu robots.

**Không làm mới robots trong lượt này**, vì ràng buộc điều khoản đã đủ để
dừng trước request. Vì vậy kết quả robots online ở thời điểm 16:18 UTC là
**chưa xác minh**; không dùng robots 14:38 để khẳng định hiện tại cho phép.
Ngay cả robots cho phép URL cũng không thay thế điều kiện về điều khoản.

## Bằng chứng, dữ liệu và Git

Các artifact dưới `data/` là **cục bộ, không commit**, không có khi clone Git.

Biên bản máy đọc được mới:
`data/diagnostics/joboko_limited_probe/20260928T161811Z/report.json`.
Thư mục này còn có `baseline-raw.json`, `baseline-files.json` và
`preservation-check.json` cho việc đối chiếu trước/sau.

Bằng chứng gốc giữ nguyên:
`data/diagnostics/joboko_assessment/20260928T143728Z/`:

- `terms.json`, `terms.hop-1.body.gz`, `terms.txt`: điều khoản §1/3, status
  cuối 200, redirect 301 trước đó; SHA-256 body cuối đã xác minh:
  `97bd2b7a2aedc7add705c382159778acf0388a8a180145a8e98ed25813600393`.
- `robots.json`, `robots.hop-0.body.gz`, `robots-analysis.json`: thời điểm và
  phân tích URL offline; SHA-256 đã xác minh:
  `b3d2660b4179fa8b71662be25c0c6b4febec860aba5c8ca2c3a259b1e197b963`.
- `homepage.*`, `access-decision.json`, `report.json`: lần trước có tổng
  **4 GET preflight/navigation, 0 listing, 0 detail**, không cộng vào lượt mới.
- [Báo cáo đánh giá cũ](joboko_assessment_2026-09-28.md): giữ nguyên byte.

Đã đọc README, AGENTS, config, CLI, công cụ probe và bằng chứng cũ; không sửa
source/test/fixture nên không chạy lại suite kiểm thử trong lượt này.
Kiểm tra SHA-256 trước/sau và `git diff --check`; file tài liệu mới kiểm tra
whitespace riêng. **1.522 file raw/checkpoint và 127 file repo có trước lượt
này không đổi**. CareerViet 299, Timviec365 299, CareerLink 55 ID duy nhất giữ
nguyên. Không có request tới các nguồn đó.

Chỉ thêm biên bản này và artifact rà soát offline; giữ hai tài liệu untracked
có từ trước, không stage, commit hoặc push. Không sửa README/AGENTS/config,
không thay đổi báo cáo khảo sát hoặc lịch sử quyết định JobOKO.

Để tiếp tục trong quy tắc hiện hành cần căn cứ thực rằng nguồn cho phép/ngoại
lệ phù hợp với probe crawler, lưu HTML và mẫu 1/3; việc chủ dự án biết điều
khoản hoặc chấp nhận rủi ro không tự tạo ra ngoại lệ đó. Đây là kết luận vận
hành theo quy tắc repository, không phải tư vấn pháp lý.
