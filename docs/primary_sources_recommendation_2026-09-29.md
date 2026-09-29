# Đề xuất hai nguồn web chính — đánh giá dữ liệu ngày 29/09/2026

## 1. Kết luận và phạm vi

**Hai nguồn chính đề xuất: CareerViet + CareerLink. Cặp dự phòng: CareerViet + VietnamWorks.**
Đây là lựa chọn ưu tiên tiến độ đồ án, chi phí vận hành và khả năng chạy lại; không phải
xếp hạng chất lượng toàn website. VietnamWorks đã có batch detail thật, không bị loại vì
403 cũ. Việc Làm 24h cũng có 104 detail thật, không chỉ listing.

CareerViet là nguồn nền: HTTP, toàn văn, metadata nghề/type/education/benefits khá đầy đủ.
CareerLink bổ sung định dạng lương/ngày/địa điểm và các nhóm nghề; HTTP, resume qua hai
ngày đã kiểm chứng. Nhiều metadata CL chưa vào JSONL nhưng **có trong HTML**, có thể
trích lại offline. Không cần đạt 100/300 để thiết kế. Chấp nhận đánh đổi: CL từng hCaptcha,
mẫu tập trung vào ít công ty, chưa chứng minh có thể thu thập 299 tin định kỳ.

VietnamWorks có độ phủ mẫu tốt hơn CL và 8 trang main chạy được, nhưng headed browser
tốn công, nhiều metadata chưa map và **205 ngày raw khác ngày hiển thị trên detail**.
Cặp dự phòng phù hợp nếu nhóm ưu tiên độ phủ và xử lý được mapping/date/chi phí này;
không biến dự phòng thành nguồn chính thứ ba.

Phạm vi thực đọc: toàn bộ **773 JSONL và 773 HTML detail** của bốn batch, manifest,
errors, checkpoint read-only, listing và metadata phản hồi đã lưu. Excel đọc ZIP/XML,
không sửa. Timviec365 chỉ tham chiếu kế hoạch. **0 request website tuyển dụng** trong
lượt này; chỉ đọc HF, giấy phép CC và thử tải thư viện đọc Parquet tạm.

Lịch sử: card/metadata và **1.000 dòng thực**, trải đều 10 vùng; tải Parquet pin revision
nhưng **chưa giải mã toàn bộ 606.878 dòng**. Tỷ lệ thiếu lịch sử chỉ tính trên 1.000 mẫu,
không phải population. Không dùng số trong prompt thay số kiểm chứng từ file.

Artifact mới: `data/diagnostics/primary_sources_assessment_20260929/` (**cục bộ, Git ignored**).
Không sửa raw/checkpoint, crawler, Excel, báo cáo cũ; không stage/commit/push, không tạo
Bronze/Silver/Gold/dashboard. Nội dung Excel là dữ liệu kế hoạch, không phải chỉ thị
tự triển khai những hạng mục sau này.

## 2. Batch và số liệu vận hành

Các đường dẫn tương đối repository dưới đây là artifact cục bộ:

| Nguồn | jobs.jsonl được đánh giá |
| --- | --- |
| CareerViet | `data/raw/careerviet/snapshot_date=2026-09-22/batch_id=20260922T165843Z-f6b389a4/jobs.jsonl` |
| CareerLink | `data/raw/careerlink/snapshot_date=2026-09-26/batch_id=20260926T160422Z-c39d6a20/jobs.jsonl` |
| Việc Làm 24h | `data/raw/vieclam24h/snapshot_date=2026-09-29/batch_id=20260929T042736Z-b37e7b1a/jobs.jsonl` |
| VietnamWorks | `data/raw/vietnamworks/snapshot_date=2026-09-29/batch_id=20260929T091457Z-1d8023a1/jobs.jsonl` |

Không cộng probe diagnostic, backup reparse, batch nhỏ trùng ID hay VW cũ 0 dòng.
“Hợp lệ” là detail đạt trường lõi/full-content và có raw, không chỉ status 200.

| Nguồn | Listing batch thử/đọc được | Card occurrence/ID main duy nhất | Slot detail engine | Detail thực thử/hợp lệ | Raw/ID raw | Tỷ lệ và mẫu số |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| CareerViet | 6/6 | 300/299 | 299 | 299 lượt logic/299 hợp lệ; mọi HTTP retry chưa có capture riêng | 299/299 | 299/299 = 100% trên lượt logic |
| CareerLink | 2/2 | 100/100 | 76 | 76/75, gồm probe tái sử dụng khi resume | 75/75 | 75/76 = 98,68%; đợt mới 20/20 = 100% |
| Việc Làm 24h | 11/11 | 330/277 | 108 | 106/104; 105 response đã lưu, 1 lượt status chưa biết | 104/104 | 104/106 = 98,11% trên navigation; 104/105 = 99,05% trên response đã lưu |
| VietnamWorks | 8/8 | 400/351 | 300 | 300/295; 299 URL khác nhau | 295/295 | 295/300 = 98,33% trên lượt; 295/299 = 98,66% trên URL khác nhau |

Các mẫu số không đồng nhất, không xếp hạng chỉ bằng tỷ lệ. Trên record đã chấp nhận,
mô tả/yêu cầu toàn văn đủ **299/299, 75/75, 104/104, 295/295**, đều 100%; đây là mẫu
đã lọc chất lượng, không phải độ đầy đủ của mọi tin trên nguồn.

### Lượt còn lại của VietnamWorks: không phải lỗi thứ năm

Manifest: requested 300, succeeded 295, failed 4. Checkpoint: 295 completed,
4 failed, 52 pending, không processing. ID **2101226** có response 200 lúc
`2026-09-29T09:55:23.469707+00:00`, lưu body nhưng chưa capture DOM khi bàn giao;
resume cùng ID lúc `09:58:42.943350+00:00` hoàn tất, chỉ ghi **một raw**.
`300 − 295 − 4 = 1` là slot gián đoạn, không phải detail thất bại thứ năm.

Bốn failed ID: 2113190/2098899 (DOM chưa hydration đủ), 2104996 (công ty DOM chưa
đối chiếu được), 2113147 (không payload detail khớp ID). Capture đều 200; null status
trong errors là thiếu truyền status ở nhánh parser, không phải 403. Không retry bốn
failed; batch dừng max_details, completed_with_errors. Chi tiết trong
`audit_vietnamworks.json`, metadata `http/*.json` tại batch và
[báo cáo browser trong Git revision cũ](https://github.com/dungtran174/job_warehouse/blob/49b5e639353a4825b6ac4e20a10d2b851a8d87f1/docs/vietnamworks_browser_assessment_2026-09-29.md).

### Fetch, pagination, điểm dừng, thời gian và độ ổn định

| Nguồn | Công nghệ/pagination thực chứng | Lỗi, điểm dừng, checkpoint | Thời gian/công sức có bằng chứng | Giới hạn ổn định |
| --- | --- | --- | --- | --- |
| CareerViet | HTTP; route `tat-ca-viec-lam-trang-N-vi.html`, 6 trang; next trang 7 chưa mở | 0 detail lỗi; overlap 1; 299 completed; max_pages | Delay manifest khởi tạo 1,5–3s, retry cap 3; start→finish **17h03**, gồm qua đêm/resume, không phải active time; thiếu log tổng thời gian request | Pilot nhỏ và nhiều chặng cùng batch; chưa chứng minh fresh snapshot qua nhiều tuần |
| CareerLink | HTTP; 2×50 ID, next `?page=3`; ngày 29/09 `/vieclam/list` xác nhận lại 50 ID | hCaptcha 200 ID 3626178 ngày 26/09; ngày 29/09 đọc lại đúng ID, thêm 20; lỗi cũ giữ; 75 completed/25 pending; max_details | Đợt đầu ≈4m16 đến challenge; resume 03:45:09–03:49:31 UTC ≈4m22, gap GET 10,858–16,562s; manifest giữ delay khởi tạo 3–5s, đợt mới dùng 10–15s | Có hai ngày truy cập cùng batch; chưa chứng minh fresh snapshot định kỳ, trang 3 hoặc 299 detail |
| Việc Làm 24h | Chrome/Playwright headed 10–15s; `?page=N`, 11 main pages khớp NEXT_DATA | Selector/title sửa offline; 1 HTTP502; slot SIGINT+latch không HTTP; cuối lỗi capture DOM, **status chưa biết**; 104 completed/1 failed/171 pending/1 processing | 04:27:36–05:21:42 UTC ≈54m06, gồm sửa/resume; pilot20 ≈5m53 | Một batch nhiều chặng; sửa capture cuối chưa xác minh live; không tự resume/khẳng định lỗi cuối là 403 |
| VietnamWorks | Chrome/Playwright headed 10–15s; `/viec-lam` 308→`/tim-viec-lam/tim-tat-ca-viec-lam` 200; 8 main pages; next page9 chưa mở | 4 parser errors 200 + 1 interrupted slot; không denial mới; 295 completed/4 failed/52 pending | 09:14:57–10:47:37 UTC ≈92m40, gồm pause/sửa/bàn giao; gap nghỉ tối thiểu 10,117s; 313 navigation chính=5 robots+8 listing+300 detail, không gồm mọi asset/XHR | Batch mới có 295 thật; batch 26/09 403 vẫn raw 0; chưa chứng minh nhiều fresh snapshots |

CareerLink batch có 79 capture đều HTTP200, trong đó một challenge cũ; probe phục vụ
resume lưu riêng ở diagnostics. Đợt mới 23 request thực =2 robots+1 listing+20 detail.
Không cộng listing mới vào hai trang discovery cũ hoặc tính lại 55 raw cũ.

Việc Làm 24h: 108 slot không phải 108 GET; hai slot không mạng là SIGINT và latch
“already stopped”. Lỗi lịch sử selector/title đã phục hồi offline còn trong errors;
HTTP502 không phải 403. Lượt cuối thiếu body/status không được gọi là thành công/challenge.

Tất cả nguồn dùng engine chung, JSONL append-only, dedup ID theo nguồn, checkpoint/
incremental hash. Reparse listing xác nhận union ID khớp manifest, audit raw không
trùng ID nội batch. Resume đã chạy thật, nhưng chưa chứng minh theo dõi tin thay đổi
ở nhiều snapshot độc lập. max-pages/max-details **lũy kế lượt thử**, không phải số
record mới mỗi resume. Audit không reset processing về pending.

## 3. Profile raw, null và giới hạn parser

Mỗi nguồn có **45 key**, không key absent. ID string; metadata/text/lương/địa điểm/ngày
raw string; tags/benefits array; crawled_at ISO có timezone, snapshot YYYY-MM-DD.
CSV `field_profile.csv` gồm **194 dòng trường** (4×45+14 lịch sử), tách null, blank,
empty array và missing tổng. Không coi [] là JSON null, không coi 0/false là thiếu.

`A` bên dưới = array rỗng; scalar missing trong bảng là null, không mặc định nguồn thiếu.

| Trường/nhóm | CareerViet n299 | CareerLink n75 | V24h n104 | VW n295 |
| --- | ---: | ---: | ---: | ---: |
| ID/title/company | 0% mỗi trường | 0% | 0% | 0% |
| Full description/requirements | 0%/0% | 0%/0% | 0%/0% | 0%/0% |
| Salary/location/posted raw | 0% mỗi trường | 0% | 0% | 0%, ngày có mismatch |
| Ngành category_tags | 0% A | 100% A | 100% A | 100% A |
| Job type | 0% | 100% | 0% | 100% |
| Experience | 33/299=11,04% | 100% | 0% | 100% |
| Education | 0% | 100% | 34/104=32,69% | 100% |
| Benefits | 4/299=1,34% A | 100% A | 0% A | 100% A |
| Job level | 17/299=5,69% | 100% | 0% | 0% |
| Detailed work address | 0% | 48/75=64% | 0% | 29/295=9,83% |
| Company size | 100% | 100% | 100% | 143/295=48,47% |
| Company URL | 3/299=1% | 100% | 0% | 100% |
| Deadline raw | 0% | 100% | 0% | 0% |

profession_tags/specialization_tags đều [] ở cả bốn; đừng nhầm với category_tags.
requirement_tags CV chưa là bộ kỹ năng chuẩn. company_industry khác ngành tin tuyển dụng.

### Null nào là chưa trích, null nào chưa thấy giá trị nguồn?

| Trường/nguồn | Bằng chứng detail HTML thực | Kết luận |
| --- | --- | --- |
| CL industry/type/experience/education/level | `#section-job-summary .job-summary-item`: 75/75 đủ năm nhóm, 47 chuỗi kết hợp ngành | Parser chưa map, không phải website thiếu |
| CL company URL/size/deadline; benefits | URL/size/expiry 75/75; benefit section 62/75. ID 3634108: full-time, THCS, 0–1 năm, size500–999, URL `/viec-lam-cua/.../189293` | Có thể trích offline; 13 tin không section benefits riêng chưa chứng minh không nhắc trong description |
| CV benefits [] | IDs 35C88065/35C87F49/35C87F39/35C87EE9 có heading nhưng `<ul class="welfare-list"></ul>` trống | Không có giá trị cấu trúc trong HTML này, không điền mặc định |
| CV experience null | 33/33 JSON-LD không experienceRequirements; 29/33 có từ liên quan kinh nghiệm trong yêu cầu tự do | Thiếu metadata cấu trúc không có nghĩa không yêu cầu kinh nghiệm |
| V24h industry [] | “Ngành nghề” ở “Thông tin chung” có 104/104 giá trị, 83 chuỗi kết hợp | Parser chưa map |
| V24h education null | 34 HTML không giá trị nhãn/JSON-LD education; 13/34 nhắc bằng cấp trong requirements | Không suy không yêu cầu bằng cấp; text extraction cần rule/test riêng |
| VW industry/skills/experience | “Thông tin việc làm” có ba nhóm 293/295; 88 chuỗi ngành; experience gồm 1/2/3/5…, 42 “Không yêu cầu”, 10 “Không hiển thị” | Parser chưa map; không hiển thị khác 0 năm; 2 HTML thiếu khối cần nullable |
| VW benefits/company URL | Heading benefits 295/295; audit đối chiếu tên công ty qua link detail 295/295 dù URL raw null | Có trường trên trang; phải đo value từng benefit, không dùng heading làm coverage nội dung |
| Company size/industry/address ở nguồn khác | Không thấy metadata cấu trúc tương ứng ở mẫu/selector đã xem; không fetch thêm profile công ty | Chưa đủ kết luận toàn website không có thông tin ở trang khác |

Bằng chứng: html_profile_*.json, detail_optional_metadata.json, null_structured_vs_text.json,
careerviet_null_review.json. Không reparse ghi đè raw. Bổ sung field sau này phải có
output/version/provenance mới hoặc Silver enrichment, giữ bản raw gốc.

### Dạng giá trị và edge case đã có, không cần chờ thêm tin

- **CV salary:** 140 range VND/MONTH, 3 range USD/MONTH, 151 Cạnh tranh, 5 bare number.
  HTML xác nhận 4 bare là “Trên”, 1 là “Lên đến”, **không phải fixed salary**.
  ID 35C87EF3 raw 25000000 mất hướng cận; JSON-LD có mã LTT/LCT không phải ISO currency.
- **CL salary:** 56 range triệu nguyên, 3 range thập phân (`7.1 triệu - 11.6 triệu`),
  12 thương lượng, 4 cạnh tranh. Có currency/period ở JSON-LD, không đổi định tính thành 0.
- **V24h:** `7 - 15 triệu`, `Thoả thuận`; job_type 99 full-time cố định, 2 part-time,
  1 full-time tạm thời, 1 hợp đồng tư vấn, 1 Khác. Gross/net/period không tự được suy.
- **VW:** `12tr-15tr ₫/tháng`, `Tới 35tr ₫/tháng`, `$$ 500-1,000 /tháng`; ID 2104432
  có **`$$ 10tr-15tr /tháng`**. Giữ ambiguous currency, không biến thành triệu USD.
- **Location:** CV 20/299 JSON-LD array nhiều nơi nhưng parser chọn đầu cho location_raw
  (IDs 35C87FF3/35C87ED9). CL 3 tin nhiều khối location; dấu phẩy trong `Nghĩa Lộ,
  Quảng Ngãi` chia cấp địa lý, không hai tỉnh. V24h ID 200940463 có `TP.HCM , Hà Nội ,
  Đà Nẵng , + 2`: summary trong detail **chưa đủ mọi địa điểm**, cần section/JSON-LD;
  không tạo tỉnh “+2”. VW ID 2113250: `Ho Chi Minh, Tay Ninh, Binh Duong`, cần mapping
  không dấu/địa giới theo phiên bản, không sửa tên lịch sử mù quáng.
- **Date:** CL DD-MM-YYYY (27/08–26/09/2026), V24h DD/MM/YYYY (28/08–29/09), CV ISO-Z
  (22–23/09), VW onlineOn ISO+07. Precision raw CV exact_day, ba nguồn kia unknown:
  default unknown không phải nguồn không có ngày. 298 CV crawl23/09 ICT trong batch 22/09;
  20 CL crawl29/09 trong batch 26/09. Ngày batch, ngày crawl và ngày nguồn khác nhau.

### Phát hiện mới: ngày UI VietnamWorks khác onlineOn

Đọc label trong **“Thông tin việc làm” của chính detail**, không dùng listing/gợi ý:
293/295 HTML có “NGÀY ĐĂNG”; chỉ 88 cùng ngày onlineOn, **205/293=69,97% khác ngày**,
chênh 1–35 ngày. UI range25/08–29/09/2026. ID 2107295 UI15/09, raw 29/09T16:00+07;
ID 2103736 UI07/09, raw 29/09. Hai IDs 2113156/2097479 không khối ngày đó.

Chưa biết onlineOn là refresh/re-online hay cơ chế nào. Nhãn ngày đăng cũng chưa chứng
minh ngày đăng lần đầu của vòng đời. Giữ onlineOn riêng, posted_date_ui nullable,
precision/provenance/mismatch flag; chốt rule trước Gold, không sửa raw che khác biệt.
Toàn bộ 205 ID/HTML trong `vietnamworks_posted_date_review.json`. Báo cáo browser cũ
ghi chưa đối chiếu UI; đây là phần **mới kiểm chứng offline**, không xóa lịch sử.

### Toàn văn mô tả và yêu cầu

| Nguồn | Description min/median/max ký tự | Requirements min/median/max | HTML đối chiếu |
| --- | --- | --- | --- |
| CV | 158/982/6.542 | 26/698/4.501 | 299/299; 1 description JSON-LD fallback, 298 DOM |
| CL | 118/718/1.761 | 88/286/990 | 75/75 toàn section DOM |
| V24h | 146/562/6.141 | 82/410,5/1.865 | 104/104 DOM+embedded đúng detail |
| VW | 102/1.281/6.291 | 123/1.000/4.326 | 295/295 DOM+payload đúng ID |

HTML có p/br/ul/li, CV có ol/strong/em; CL requirements có 1 ol. VW có p/br/strong/em,
không nhất thiết dùng ul/li. Chưa thấy table trong section đo. JSONL cả bốn dồn thành
một dòng: giữ long text + HTML, không VARCHAR(255), không đo completeness bằng newline.
Ngắn không đồng nghĩa bị cắt; benefits/income/time có thể lẫn trong description.

## 4. Lịch sử: schema, revision, mẫu thực và quyền sử dụng

[Dataset card](https://huggingface.co/datasets/tinixai/vietnamese-job-descriptions) khai báo
606.878 record, 14 cột, năm 2022–2026. Viewer num_rows_total cũng 606878. Không dùng số
608000 trong trao đổi làm tổng đo được; size_categories metadata 1M<n<10M không khớp
tổng nên không dùng tag đó thay phép đếm. File repository là **data.parquet**, dù card nói CSV.

Revision **679c3a17347ff6ce769d9bf510c122a087493cf6**, lastModified2026-04-28T08:13:21Z.
[Card pin revision](https://huggingface.co/datasets/tinixai/vietnamese-job-descriptions/blob/679c3a17347ff6ce769d9bf510c122a087493cf6/README.md).
Parquet tải 29/09: 293.171.544 byte, SHA256
`4d5e11b58490edc40900386986de71e844cd9f0f3a5fc714418747f66462f834`.
**Tải đủ file không có nghĩa đã profile đủ dòng.** Môi trường không có Parquet reader;
index pip mặc định không có gói, wheel/binary chính thức tải trì trệ, đã dừng.
Không đổi dependencies production; file giữ để đọc toàn bộ sau, không bịa tỷ lệ population.

Mẫu thực: 10 cửa sổ×100, offsets `0,67420,134840,202259,269679,337099,404519,471938,
539358,606778`, **1.000 dòng=0,1648%**. Không ngẫu nhiên/đại diện theo năm. Parquet pin
revision; Viewer đọc head hiện hành, không API pin revision riêng; sample chưa được
chứng minh byte-for-byte từ Parquet pin. Tất cả tỷ lệ bảng sau trên **mẫu1.000**:

| Field | Kiểu thực | Null | Lưu ý giá trị |
| --- | --- | ---: | --- |
| id | integer | 0% | 1.000 ID mẫu khác nhau, không có source_name/URL gốc |
| job_title | string/null | 0,1% | 1 thiếu |
| company_name | string/null | 0,5% | 5 thiếu |
| salary | string | 0% | 36 Đang cập nhật; `26 - 36 triệu`, `4000 usd` không tự có period |
| location | string | 0% | free text, quận/tỉnh/multiple values |
| job_type | string | 0% | 100 Chưa xác định, 6 Không |
| job_industry | string | 0% | 33 Chưa xác định; dấu / có thể trong nhãn |
| experience_level | string | 0% | 43 Không, không tự gán 0 năm |
| education_level | string | 0% | 322 Không, không tự coi không yêu cầu |
| job_position | string/null | 0,1% | cấp bậc, không ID vị trí |
| job_description | string | 0% | đọc text mẫu, không có HTML gốc để xác minh đầy đủ |
| benefits | string/null | 1,3% | khác array web |
| requirements | string/null | 2,3% | Silver phải nullable |
| year | integer | 0% | mẫu2022:193,2023:193,2024:189,2025:323,2026:102 |

Không blank string trong mẫu. Unknown literal không phải JSON null; chi tiết ở
history_profile_sample.json. Card mô tả id là định danh tin, year là năm đăng; **không
cung cấp mapping ID tới website, URL gốc hoặc cách gán ID**. Namespace lịch sử phải
riêng (`tinixai_history`, revision, id). year chỉ precision năm, không tạo ngày 01/01
hoặc dùng imported_at làm crawled_at. Truy vết được file/revision/row_index/id ingest,
chưa truy được trang nguồn. Chưa xác nhận full-history uniqueness/dedup/full-content.

License card CC BY-NC4.0: ghi công dataset/tác giả được cung cấp, link nguồn/license,
ghi rõ thay đổi; mục đích phi thương mại, không ngụ ý bảo trợ. License không giải quyết
tất cả quyền khác: [CC BY-NC4.0](https://creativecommons.org/licenses/by-nc/4.0/).
Card đề nghị trích Le et al.(2026), CareerPathKG,
[DOI10.18653/v1/2026.eacl-industry.60](https://aclanthology.org/2026.eacl-industry.60/).
Ghi công đề xuất: “tinixai, Vietnamese Job Descriptions, HF revision 679c3a1…,
CC BY-NC4.0; Le et al., CareerPathKG(2026); nhóm đã chuẩn hóa trường dữ liệu.”
Không suy license lịch sử cho phép công bố raw web mới.

## 5. Silver chung, sáu cặp nguồn, Gold/dashboard

### Mapping chung đề xuất, chưa triển khai

| Silver meaning | Web ↔ lịch sử | Nullable/provenance |
| --- | --- | --- |
| Identity | source_name+source_job_id; historical namespace riêng | History URL/listing URL/crawl time null, không ID website giả |
| Title/company/full text | job_title/company_name/job_description; candidate_requirements↔requirements | Historical title/company/requirements có null; không dùng gate detail web để xóa mọi record lịch sử |
| Salary/location | salary_raw↔salary, location_raw↔location | Raw + normalized nullable/confidence; location nhiều-nhiều, không split comma mù |
| Industry | category_tags↔job_industry; detail HTML enrichment | Nhãn nguồn + taxonomy version; company_industry riêng |
| Type/experience/education/level | job_type/experience_raw/education_level/job_level ↔ job_type/experience_level/education_level/job_position | Nullable, raw và normalized riêng; no_requirement khác unknown; multi-type |
| Benefits | array web↔benefits string | benefits_text + items/tag riêng, không coi toàn văn V24h là tag chuẩn |
| Time | source datetime/day; history year | posted_year, nullable posted_date, precision, observed_at/imported_at riêng; onlineOn riêng |
| Trace/version | batch/schema/parser/hash/HTML; history revision/file SHA/row_index | Hash không cross-source entity key; enrich phải truy nguồn |
| Source extras | companysize/deadline/address/vacancies/income/time/tags | Nullable hoặc extension; không ép lịch sử có các cột này |

Grain lần quan sát khác grain tin nguồn; cùng ID qua snapshot không tự thành tin mới.
README gọi JSONL là Bronze theo hiện trạng crawler, nhưng **chưa có layer ingest
Bronze/Silver/Gold theo Excel**. Bronze mới giữ nguyên raw/HTML và manifest/checksum.

Tất cả sáu cặp map được lõi text+salary/location tới lịch sử; time/provenance cần nullable.

| Cặp web + lịch sử | Raw web | Điểm thuận lợi | Nullable/việc bổ sung | Lựa chọn/chi phí |
| --- | ---: | --- | --- | --- |
| **CV+CL** | **374** | Lõi/date; CV metadata giàu; CL HTML summary đầy đủ, nhãn VN gần lịch sử | CL ngành/type/degree/experience/benefits chưa map; CV bounds/multi-location | **Chính**, 2HTTP, resume hai ngày; chấp nhận hCaptcha/mẫu CL tập trung |
| CV+V24h | 403 | Type/experience/benefits/date; education nullable, company URL | V24h industry chưa map, location `+2`, DMY | 1HTTP+browser; raw thuận lợi, nhưng capture cuối chưa xác minh, không chọn hiện tại |
| **CV+VW** | **594** | Lõi/joblevel, nhiều công ty, toàn văn dài, 8page main | VW optional chưa map, 205 date mismatch/2 date UI thiếu, ký hiệu tiền/nhãn EN | **Dự phòng**, 1HTTP+headed; cần offline date/metadata trước Gold |
| CL+V24h | 179 | Lõi và ngày UI DMY; V24h có metadata type/experience/benefits | Hai industry raw rỗng; CL meta enrichment; thiếu CV raw USD/multi-type | 1HTTP+browser; hCaptcha+capture, không có nguồn nền giàu trường như CV |
| CL+VW | 370 | Lõi, lương/location | Hai raw cùng thiếu ngành/type/degree/benefits, VW date mismatch | 1HTTP+browser và hai mapping HTML; không chọn |
| V24h+VW | 399 | Lõi; V24h type/experience/benefits, VW size/level | Ngành raw cả hai rỗng, date/location cần sửa mapping | **2headed browsers**, hai embedded schemas và lỗi khác nhau; không chọn cho tiến độ này |

Tên công ty sau NFKC/casefold/space (**không entity resolution**): CV 210, CL 32,
V24h 91, VW 227. Union tên của sáu cặp theo thứ tự bảng:241,299,434,123,258,317.
CL Ocean Edu18/75=24%, FPT10/75=13,33%; top CV 9/299, V24h 4/104, VW 7/295. Không nói
CL phủ đa ngành ngang VW: đổi độ phủ mẫu lấy chi phí/tiến độ. CV 58 nhãn ngành,
CL 47/V24h 83/VW 88 **chuỗi kết hợp** ngành không cùng taxonomy/đơn vị, không xếp hạng trực tiếp.

Nếu ưu tiên độ phủ để chuyển cặp dự phòng, phép kiểm tra nhỏ nhất không cần live:
5 HTML VW gồm date lệch, không khối ngày, multi-location, ambiguous salary làm fixture;
test mapping ngày/ngành/benefits, rồi replay 295 HTML đo coverage. Không cần thêm300 tin.
Bằng chứng hiện tại đủ đề xuất cặp chính, không trì hoãn STT 7 chờ quyết định này.

### Duplicate candidates, chưa khử trùng xuyên nguồn

Kiểm tra exact-match sau NFKC/casefold/space: (title,company) và (full description,
full requirements). Cả sáu cặp có **0 full-content match**; chỉ CV–V24h có 1 title/company
match: IDs 35C87BB1↔200943023, Đội trưởng Kỹ thuật Tòa nhà/Vinhomes, salary/location
khác độ chi tiết. Đây là **ứng viên cross-post**, không tự xóa/gộp. Năm cặp exact0 không
chứng minh không cùng tin đổi title/company/text. Sample lịch sử1.000 không title/company
match với bốn batch; **chưa kiểm tra toàn bộ lịch sử**. 773 raw không phải773vacancies thật.

content_hash là thay đổi trong nguồn; adapter/default/field representation khác nhau,
không entity key xuyên nguồn. Cần candidate review, giữ source/provenance, quy tắc grain.

Gold/dashboard: year lịch sử chỉ phân tích theo năm, không phân bổ giả vào ngày/tháng.
Web theo ngày chỉ có date/precision đúng; observed_date được dùng nếu đặt tên “tin quan
sát/lần đầu thấy”, không tráo ngày đăng. Chưa có chuỗi nhiều batch để đo xu hướng daily.
Mẫu quota vài trăm không đại diện toàn thị trường; không so số lịch sử lớn với web nhỏ
thành tốc độ tăng trưởng. Numeric salary có currency/period hợp lệ mới tính, unknown
không=0; VND/USD riêng, tỷ giá/date phải có provenance. Bridge nghề/location/skills
tránh join nở count; tags/title không tự là kỹ năng đã chuẩn hóa. Recruitment authenticity,
nhà tuyển dụng xác thực, tin còn hiệu lực **chưa được đánh giá** chỉ bằng HTML crawl được.

## 6. Thuận lợi pipeline và chạy lại batch sau này

Bronze ingest cặp chính có 374 detail đủ provenance/HTML/hash; idempotent theo file SHA,
batch/source/row, đối soát299/75. Historical origin/revision/row_index/imported_at/license,
không giả crawl date/URL. 55 CL cũ chưa fetch lại, không đổi batch 26/09 thành snapshot 29/09.

Silver có thể bắt đầu với common nullable và enrich CL/CV từ HTML giữ version riêng.
Gold/dashboard trước tiên coverage/phân bố theo phạm vi nguồn, historical yearly tách
web daily/observed; chưa cam kết xu hướng thị trường hay population constraints.

HTTP giảm browser/GUI dependency nhưng không bảo đảm không challenge. Ingest từ file
offline chạy lại được ngay; **live batch lần sau chưa được phép tự chạy** trong lượt
phân tích này, cần điều kiện nguồn hiện hành và stop policy. Chưa nguồn nào chứng minh
fresh snapshots định kỳ qua nhiều tuần. Browser asset/XHR/capture/hydration làm tăng
vận hành; chưa đo CPU/RAM/storage peak nên không bịa tỷ số chi phí.

CLI guard tại thời điểm đánh giá: CL owner bounded 6 pages/300 attempts;
giới hạn CareerLink hiện hành và lệnh target-records xem README. VW 8/300,
V24h 12/300 headed. CV chưa có
owner bounded tương tự: owner sample 1/3, medium/pilot/page6-check yêu cầu auth reference.
Manifest CV cũ có reference `user-requested-public-...`, **không đủ bằng chứng văn bản
chủ website**, không dùng lại thành cấp phép nguồn. Trước batch CV lớn sau này cần
cơ sở/phạm vi/gate phù hợp; không tự sửa guard trong nhiệm vụ đánh giá. Owner decision/
robots/crawl thành công không phải giấy phép khai thác/tái công bố quy mô lớn; điều kiện
tương lai chưa biết. Raw/HTML giữ cục bộ, dashboard ưu tiên tổng hợp có kiểm soát.

## 7. Excel: đúng ô, chỉ đề xuất sửa sau khi chốt cặp chính

File `/home/dung/Downloads/Kế hoạch tiến độ thực hiện đồ án .xlsx` đã đọc trực tiếp.
**STT 7 ở hàng 10, STT 12 ở hàng 17, STT 3 ở hàng 5** của Công việc. Trang Nghiên cứu giải
pháp có C5=7, C12=16 là tham chiếu công việc, không cùng số hàng với trang kia.

| Trang/ô | Nội dung hiện tại thực đọc | Câu thay thế đề xuất |
| --- | --- | --- |
| Công việc!C10 (STT 7) | Đối chiếu trường dữ liệu, tỷ lệ thiếu và dữ liệu trùng của CareerViet, Timviec365 và bộ dữ liệu lịch sử | Đối chiếu trường dữ liệu, tỷ lệ thiếu và dữ liệu trùng của CareerViet, CareerLink và bộ dữ liệu lịch sử. |
| Công việc!C17 (STT 12) | Nạp dữ liệu CareerViet và Timviec365 từ các batch raw đã lưu vào Bronze theo cấu trúc đã chốt | Nạp batch raw CareerViet và CareerLink vào Bronze; đối soát ID và số dòng. |
| Công việc!J5 (STT 3) | batch dừng tại bước listing do HTTP 403 và không ghi được tin chi tiết -> Không chọn VietnamWorks làm nguồn dữ liệu | Lượt cũ 403/raw 0; ngày 29/09 có 295 detail. VietnamWorks dự phòng: xử lý ngày đăng và chi phí browser. |
| Công việc!J8 (STT 5) | (trống; C8 là Tích hợp và kiểm chứng crawler Timviec365) | Timviec365 299 detail giữ làm đối chiếu; nguồn chính là CareerViet và CareerLink. |
| Công việc!J10 (STT 7) | (trống) | Dùng 299 CareerViet, 75 CareerLink và 1.000 mẫu lịch sử; đọc full lịch sử trước chốt tỷ lệ thiếu toàn bộ. |
| Công việc!J17 (STT 12) | (trống) | Giữ raw/HTML gốc; bổ sung trường thiếu khi chuẩn hóa, không ghi đè batch cũ. |
| Nghiên cứu giải pháp!D3 (C3=3) | Tìm hiểu cách VietnamWorks cung cấp danh sách và thông tin chi tiết của tin tuyển dụng, cùng các giới hạn truy cập. | Đối chiếu hai lượt VietnamWorks; đánh giá nguồn dự phòng, ngày đăng và chi phí browser. |
| Nghiên cứu giải pháp!E3 | Trang tuyển dụng công khai và quy định truy cập của VietnamWorks | HTML/báo cáo VietnamWorks26/09,29/09; báo cáo chọn nguồn và đối chiếu ngày. |
| Nghiên cứu giải pháp!D5 (C5=7) | Nghiên cứu cách đánh giá dữ liệu thiếu, dữ liệu trùng và đối chiếu các trường giữa ba nguồn dữ liệu. | Đối chiếu CareerViet, CareerLink, lịch sử: trường chung, NULL, trùng tin và độ chính xác thời gian. |
| Nghiên cứu giải pháp!E5 | Batch raw và HTML CareerViet, Timviec365; dataset card và mẫu của bộ dữ liệu lịch sử. | Raw/HTML CareerViet, CareerLink; card và mẫu lịch sử revision 679c3a1; bảng profile. |
| Nghiên cứu giải pháp!E12 (C12=16) | Mẫu CareerViet, Timviec365 và bộ dữ liệu lịch sử. | Mẫu CareerViet, CareerLink, lịch sử; bảng ánh xạ nghề/địa điểm có phiên bản. |

Khi nhóm bắt đầu STT 7 có thể đổi Công việc!G10 từ Chưa bắt đầu thành **Đang thực hiện**,
không đánh dấu Hoàn thành vì còn full-history và mapping. Giữ C8/STT 5 đã hoàn thành:
Timviec365 là việc thật đã làm, không viết lại lịch sử thành tích hợp CareerLink.
Không đổi ngày/giờ/người thực hiện/STT/công thức. STT 27/35 nói chung hai nguồn web
vẫn đúng, không cần đổi thành ba/bốn nguồn. Nếu chọn dự phòng, thay CL bằng VW trong
các ô kế hoạch nạp/đối chiếu và giữ yêu cầu date; **không sửa Excel trong lượt này**.

Timviec365 tham chiếu:299 raw/299 ID,299mô tả+yêu cầu, **posted_at_raw0/299**. Ngày
Cập nhật không tự thành ngày đăng. Batch này hiện được bảo toàn trong archive
ngoài repo (xem docs/architecture_data.md), không thêm vào bốn ứng viên.

## 8. Công việc 7 có thể bắt đầu ngay và đầu ra

**Bắt đầu ngay với 299 CareerViet +75 CareerLink +1.000 mẫu lịch sử thực đọc**. Dùng
V24h 104/VW 295 làm đối chiếu edge cases, Timviec365 299 làm tham chiếu kế hoạch cũ.
Không chờ thêm CL 100/300, không gọi historical sample là full dataset.

Đầu ra STT 7:

1. Data dictionary 45 field web/14 field lịch sử, ý nghĩa/type/nullable/missing reason/
   provenance và mapping vào Silver dự kiến.
2. CSV profile (đã có), quyết định đúng hai nguồn, salary/date/location edge cases,
   parser gaps; phân biệt sample statistics với population.
3. Candidate duplicates và khóa/grain/count policy; chưa tuyên bố entity-dedup hoàn tất.
4. Acceptance cases/fixture đề xuất: multi-location, bound/ambiguous currency, DMY/ISO,
   year-only, unknown sentinel, UI date≠onlineOn, resume không append trùng.
5. Danh sách ô Excel và các điều kiện còn phải kiểm tra.

Trước chốt Bronze/Silver, cần tiếp tục **offline**: giải mã toàn Parquet, đối soát606878
dòng/full-null/uniqueness/years/duplicates; xác nhận sample/file pin/schema và license.
Thử enrichment CL summary/company/benefits trên fixture rồi replay 75 HTML; sửa mapping
CV bounds/20 multi-locations trong output mới. Chốt date/timezone/precision và metric
tin mới; từ điển nghề/địa lý versioned, không gộp dấu/địa giới/+2 mù. Review duplicate
candidate và nullable rule trước constraints. Những việc này không cần crawl mới và
không chặn thiết kế sơ bộ từ dữ liệu hiện có.

## 9. Bằng chứng, kiểm tra và bảo toàn

Trong diagnostics mới có field_profile.csv, web_profiles.json, html_profile_*.json,
audit_careerlink/vieclam24h/vietnamworks.json, http_source_listing_reparse.json,
detail_optional_metadata.json, vietnamworks_posted_date_review.json,
careerlink_optional_coverage.json, careerviet_null_review.json,
null_structured_vs_text.json, pair_duplicate_candidates.json,
history_metadata/card/download/data.parquet (tên đầy đủ trong thư mục),
history_sample1000.json, history_profile_sample.json, history_sample_duplicate_candidates.json,
history_read_scope.json, excel_cells.json và preservation_before/after.json.
Artifact data/.runtime bị ignore, không đi cùng clone Git.

Helper cục bộ assess_offline.py chỉ đọc saved files, không mạng:

```bash
.venv/bin/python data/diagnostics/primary_sources_assessment_20260929/assess_offline.py
```

Helper tái lập web audit/CSV 180 field; CSV cuối có thêm14 field lịch sử được tính riêng
từ history_sample1000.json. Không dùng nhánh whole_train_split của helper cho mẫu.

Kiểm tra repository (không live):

```bash
.venv/bin/pytest -q -m 'not live'     # 278 passed
.venv/bin/ruff format --check .       # 113 files already formatted
.venv/bin/ruff check .               # All checks passed
.venv/bin/mypy src                   # 47 source files passed
git diff --check
```

Git trước main/worktree sạch. Chỉ báo cáo này là file Git nhìn thấy; diagnostics ignored.
Không stage/commit/push hoặc sửa source/test/CLI. Hash trước/sau toàn **3.321 file raw**
(checkpoint/incremental/HTML/errors) và Excel được kiểm tại preservation_before/after.json.
