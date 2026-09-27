# Timviec365 — probe detail và batch mẫu, 27/09/2026

## Kết luận có giới hạn

**HTTP lấy được listing chính và 3/3 detail đầy đủ mô tả/yêu cầu.** Đã tích hợp
adapter mẫu và ghi **3 bản ghi raw thật**. Pilot chạy một detail rồi resume thêm
hai detail, không ghi trùng hoặc thay dòng đầu. Không browser, API, đăng nhập,
proxy, stealth hay truy cập host PDF bị cấm.

**Chưa chứng minh batch nhiều trang ổn định:** chỉ đọc trang listing số 1, chưa
thử trang 2. Probe và pilot đọc lại cùng ba ID, không phải sáu tin độc lập.
Không chạy 20/100/300 tin. `completed` trong manifest nghĩa là hoàn thành giới hạn
3 detail, không phải hết nguồn. Checkpoint còn 21 detail pending.

Báo cáo trước `timviec365_assessment_2026-09-27.md` được giữ nguyên như lịch sử
lần dừng preflight; phần chưa đọc được quy chế ở đó đã có bằng chứng bổ sung dưới đây.

## Điều kiện truy cập và phạm vi quyết định

Artifact cục bộ, không commit: `data/diagnostics/timviec365_assessment/20260926T173627Z/`.
`access-decision.json` ghi trước request listing: `project_owner_public_test`,
`authorization_reference=null`, tối đa 1 listing/3 detail. Đây là quyết định chủ
dự án, **không phải chấp thuận của Timviec365**. Probe là HTTP diagnostics có ghi
access basis, không phải lệnh CLI feasibility đã có sẵn hỗ trợ nguồn này.
Pilot dùng cờ `--project-owner-public-test` của CLI sau khi có mẫu detail đạt.

| Kiểm tra trực tiếp | Bắt đầu UTC 26/09/2026 | HTTP | Kết quả |
| --- | --- | ---: | --- |
| [Robots host chính](https://timviec365.vn/robots.txt) | 17:36:37 | 200 | `/viec-lam` và ba URL detail không khớp Disallow |
| [Quy chế trên host chính](https://timviec365.vn/images/manual/quy_che_cong_ty_HHP.pdf) | 17:37:08 | 200 | PDF 48 trang, không redirect; có lớp text để đọc trực tiếp |
| [Thỏa thuận sử dụng](https://timviec365.vn/thoa-thuan-su-dung.html) | 17:40:32 | 200 | Đọc lại nội dung HTML hiện hành |
| Robots trước pilot | 17:49:17 | 200 | Kiểm tra lại trước listing/detail |
| Robots trước resume | 17:50:17 | 200 | Kiểm tra lại trước hai detail còn lại |

Giờ Việt Nam = UTC + 7, tức 00:36–00:50 ngày 27/09. Mọi URL cuối giữ nguyên.
URL PDF host chính được tìm trong kết quả tìm kiếm chính thức, không tự thay host
trong URL bị cấm. **Không có request tới `storage1.timviec365.vn` trong lượt này**;
không tải PDF/ảnh từ host đó. Disallow `/` trên storage1 không được áp dụng suy
diễn sang listing/detail ở host chính, và Allow ở host chính không cấp quyền tải
file trên storage1. Không tải ảnh/script liên kết trong HTML.

Đối chiếu nội dung và phạm vi:

- Quy chế PDF trang 3, II.2.5: có phân biệt quyền xem thông tin của người chưa là
  thành viên chính thức với chức năng của thành viên.
- Trang 34, VII.2.2 Điều 1: hạn chế sao chép bằng biện pháp kỹ thuật khi chưa có
  đồng ý được đặt trong mục và câu quy định cho nhà tuyển dụng/người đăng tin.
  Phép thử này không đăng tin hay dùng tài khoản nhà tuyển dụng.
- Thỏa thuận HTML 1.1 hạn chế sao chép/sử dụng/phổ biến bất hợp pháp. Các khoản
  từ chối dịch vụ nói về thành viên/vi phạm; 2.1.b nói về trách nhiệm nhà tuyển dụng
  và công cụ dịch vụ. Không tự diễn giải thành lệnh cấm mọi lần đọc công khai.

Đánh giá vận hành: chưa xác định được lệnh cấm áp dụng rõ ràng cho mẫu nội bộ
nhỏ đã yêu cầu, nên thực hiện đúng giới hạn. Không coi robots hay thiếu lệnh cấm
là giấy phép bản quyền, quyền công bố lại raw hoặc quyền thu thập hàng loạt.
PDF host chính ghi năm 2024, chưa xác minh nó đồng nhất với bản storage1 không
được phép tải; không tuyên bố đã kiểm chứng mọi phiên bản quy chế. Không kết luận
pháp lý về quyền khai thác dữ liệu quy mô lớn. PDF/text đầy đủ chỉ lưu cục bộ.

SHA-256 PDF: `7f7a4c6c591cbf16065ec97cd452ec9e9bc41f5841e893cdd4db97084d9f27f8`.
Metadata và body gốc: `official-main-host-policy.json`, `.pdf`, `.body.gz`, `.txt`.

## Listing chính và phân trang

URL thử: `https://timviec365.vn/viec-lam`; HTTP 200, URL cuối giữ nguyên.
Probe 17:41:16 UTC; pilot 17:49:31 UTC. Cả hai lần đều có 24 URL/ID duy nhất.

Vùng xác nhận:

```css
.boxContentListNew .boxShowListNew > .item_vl h2.box_title_new a.title_new[href]
```

ID dạng `-p<id>.html` khớp `data-newid` trên card; 24 card quan sát có
`data-newghim=0`. Một tin quảng bá ID 2045300 ở `.box_post` ngoài vùng kết quả
không được tính. Không lấy logo/trang công ty/blog làm URL việc làm.
HTML có `.pagination .pagi_pre a` tới `/viec-lam?page=2`, các anchor 2/3/13;
chưa gọi các URL đó nên **không xác nhận có 13 trang lấy được**.
`listing-analysis.json` lưu toàn bộ danh sách và HTML pagination đã đối chiếu.

## Kết quả probe và pilot tách biệt

| Chỉ số | Probe | Batch pilot, gồm resume |
| --- | ---: | ---: |
| Request kiểm tra điều kiện | 3 | 2 robots |
| Listing thử / HTTP thành công | 1 / 1 | 1 / 1 |
| ID duy nhất thuộc listing chính | 24 | 24 |
| Detail thử / HTTP thành công | 3 / 3 | 3 / 3 |
| Bản ghi detail đủ trường bắt buộc | 3 | 3 |
| Dòng thực ghi `jobs.jsonl` raw | 0 | 3 |
| Đủ mô tả / yêu cầu | 100% / 100% | 100% / 100% |
| Lỗi / challenge | 0 / 0 | 0 / 0 |

Tổng lượt này: **13 HTTP GET trực tiếp = 5 điều kiện + 2 listing + 6 detail**;
mọi phản hồi HTTP 200, không redirect/retry. Listing là cùng một URL; detail chỉ
**3 ID khác nhau**. Một lượt tìm kiếm web với hai truy vấn để tìm nguồn quy chế
được thống kê riêng, không nhập vào HTTP crawler. Bốn GET ở báo cáo cũ không
tính lại. Probe giữ `sample_records.jsonl`, không giả làm batch raw.

| ID | HTTP probe/pilot | Ký tự mô tả | Ký tự yêu cầu | Lương raw | Địa điểm |
| --- | --- | ---: | ---: | --- | --- |
| 2070499 | 200 / 200 | 672 | 593 | 20.000.000 VNĐ | Hồ Chí Minh |
| 2070495 | 200 / 200 | 398 | 204 | 18.000.000 VNĐ | Hà Nội |
| 2070494 | 200 / 200 | 361 | 466 | 20 - 30 triệu | Hưng Yên |

URL detail cuối (không chuyển hướng):

- `https://timviec365.vn/tuyen-chuyen-vien-van-hanh-thi-cong-noi-that-p2070499.html`
- `https://timviec365.vn/ke-toan-tong-hop-p2070495.html`
- `https://timviec365.vn/kien-truc-su-p2070494.html`

Parser đối chiếu canonical ID với `h1.titleNew[data-id]`; tiêu đề/công ty lấy từ
detail. Mỗi `.itemInfoSpecific` được chọn bằng heading rồi lấy **toàn bộ**
`.boxMainInfoSpecific`, không cắt theo độ dài hay preview. Yêu cầu gồm cả đoạn
văn và các nhãn bằng cấp/kinh nghiệm/giới tính/tuổi trong vùng đó.
Kiểm toán độc lập so sánh toàn bộ text sau gộp whitespace, đồng thời lưu 80 ký
tự đầu/cuối và độ dài vào `detail-audit.json`/`followup-report.json` cục bộ.
Cả 3 dòng raw khớp HTML tương ứng; `content_hash` tính lại đúng.

Lương, địa điểm, địa chỉ chi tiết, kinh nghiệm, hạn nộp, chức vụ, bằng cấp,
số lượng raw, hình thức làm việc, quyền lợi và thời gian làm việc đều có 3/3 mẫu.
Không chuẩn hóa nghiệp vụ: giữ cả mâu thuẫn giữa đoạn yêu cầu và nhãn kinh nghiệm
ở tin kế toán. Lương giữ literal DOM, kể cả tên class `dataNewFake` của hai mức
tiền cố định; không suy đoán class này thành mức lương đã được xác minh độc lập.
Ngày nguồn hiện là **Cập nhật**, không phải ngày đăng: `posted_at_raw=null` 3/3.
Không có JobPosting JSON-LD để dùng thay thế cho phần DOM này; JSON-LD quan sát
là thông tin website/tổ chức. Một số nhãn ngành/lĩnh vực chưa được ánh xạ vào
schema; null/list rỗng không tự chứng minh nguồn không có trường ấy.

## Raw, checkpoint và resume đã chạy

Batch cục bộ:

```text
data/raw/timviec365/snapshot_date=2026-09-27/batch_id=20260926T174917Z-3a406cfa/
  jobs.jsonl
  errors.jsonl
  manifest.json
  checkpoint.sqlite3
  html/
  http/
```

`jobs.jsonl`: 3 dòng, 3 ID duy nhất; SHA-256
`944c1606ff3b831a40ef3080b003b6cbc4883d48824a4e8805f78c434050747a`.
`errors.jsonl` rỗng. `http/` có sáu cặp metadata/body nén, lưu trước khi kiểm tra lỗi;
`html/` có listing/detail đã fetch. Metadata có thời điểm, HTTP status, URL cuối,
hash body, Retry-After và kết quả challenge. Không ghi cookie/token.

Lệnh thực tế đã chạy lần lượt, **không phải hướng dẫn mở rộng thêm**:

```bash
.venv/bin/job-crawler crawl timviec365 --mode sample --fetcher http \
  --max-pages 1 --max-details 1 --delay-min 10 --delay-max 15 \
  --max-retries 0 --timeout 30 --save-html --require-complete-content \
  --project-owner-public-test \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'

.venv/bin/job-crawler crawl timviec365 --mode sample --fetcher http \
  --max-pages 1 --max-details 3 --resume \
  --resume-batch-id 20260926T174917Z-3a406cfa \
  --delay-min 10 --delay-max 15 --max-retries 0 --timeout 30 \
  --save-html --require-complete-content --project-owner-public-test \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

Resume thực tế: **1 → 3 dòng, tăng đúng 2**, không fetch lại listing/detail đầu;
hash phần byte của dòng đầu không đổi (`before-resume.json`). Checkpoint 3 completed,
21 pending; kết thúc do `max_details`, listing do `max_pages`. Chạy lại cùng cap 3
không lấy thêm detail; không tự tăng cap hay mở mode bounded/full.

## Code, test và bảo toàn

Thêm adapter/parser/fetcher `timviec365.py`; đăng ký source trong config/CLI/factory.
Không sửa logic hoặc dữ liệu các nguồn khác. Gate chung giữ nguyên; source mới
còn khóa chặt hơn: sample HTTP 1/3, delay >=10, retries=0, HTML và complete-content.
Fetcher chặn redirect, mọi lỗi HTTP, challenge kể cả HTTP 200 và marker cuối body;
giữ pending checkpoint khi dừng. Guard robots bổ sung kiểm tra Disallow wildcard
theo hướng bảo thủ, không dùng Allow `/` để bỏ qua Disallow cụ thể.

Hai file test mới kiểm tra parser, main/ad/pinned scope, ID mismatch, missing-null,
đầu/cuối nội dung, optional fields, ngày cập nhật, cap, stop/no-retry/evidence,
robots/host PDF và resume/dedup. Ba fixture nhỏ giữ cấu trúc DOM thật nhưng thay
văn mô tả bằng câu tổng hợp; không dùng fixture để tính số liệu live.

```bash
.venv/bin/pytest -q -m 'not live'        # 185 passed
.venv/bin/ruff format --check .        # 90 files already formatted
.venv/bin/ruff check .                 # passed
.venv/bin/mypy src                     # 42 source files, passed
git diff --check                       # passed
sha256sum --check --quiet /tmp/job-warehouse-timviec365-followup-baseline.sha256
```

Đã format các file Python sửa/thêm. **567 file raw/checkpoint có trước lượt này
không đổi**: CareerViet 299 dòng, CareerLink 55 dòng và mọi batch VietnamWorks được
giữ nguyên. CareerViet jobs SHA-256 `018aa543af009120e4d7d1a1119091faaced9fe7616e00e8c927684543a1afdc`;
CareerLink jobs SHA-256 `a2133e710dc0db966ad0ba9bc202dc63da9eb3b62b07ecd157234e691fb87be1`.
Không request CareerViet/CareerLink/VietnamWorks. Không stage/commit/push;
HEAD vẫn `2eef4fee4aba3fe2284325b967c34a58944f76cf`, nhánh `main`.
Báo cáo cũ untracked có từ đầu được giữ nguyên. README thêm hướng dẫn; báo cáo
này và code/test/fixture mới còn untracked. Artifact `data/` không đưa vào Git.

## Bước tiếp theo đề xuất, chưa chạy

Một thử nghiệm được cho phép riêng cho trang 2 sẽ kiểm tra ID mới, tỷ lệ trùng
và khả năng phân trang thật; sau đó mới cân nhắc cap detail lớn hơn trong code.
Cần thêm nhiều nghề/dạng nội dung, xác minh nhãn lương/ngày đăng và ánh xạ các
trường chưa hỗ trợ. Không lấy 3/3 hoặc link trang 13 làm bằng chứng nguồn đã ổn
định như CareerViet 299 detail. Không có trở ngại kỹ thuật quan sát trong mẫu này,
nhưng tính ổn định quy mô lớn và quyền khai thác/công bố lại vẫn chưa được xác nhận.
