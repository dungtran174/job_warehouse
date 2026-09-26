# Độ sẵn sàng thiết kế dữ liệu tuần 3 — đánh giá offline 26/09/2026

Các đường dẫn `data/`, CSV/JSON profile, HTML, checkpoint và delta trong báo cáo
là **artifact cục bộ, không được commit lên GitHub**. Script tái lập có trong Git,
nhưng cần các batch cục bộ nêu trong báo cáo; clone repository không kèm dữ liệu raw.

## Kết luận và phạm vi

**Có thể bắt đầu thiết kế tuần 3 bằng 55 CareerLink + 299 CareerViet.**
Đủ mẫu để thiết kế hợp đồng đa nguồn, kiểu dữ liệu/nullable, khóa nguồn, quan hệ
nhiều địa điểm/ngành nghề và quy tắc chất lượng ban đầu. Không cần chờ 100/300 tin.
Đây không phải kết luận dữ liệu đại diện thị trường, đủ đo xu hướng hay mô hình cuối cùng
đã bao phủ mọi tình huống. Chưa triển khai Bronze/Silver, cơ sở dữ liệu hay pipeline mới.

Đã đọc toàn bộ **354 record + 354 HTML detail tương ứng**, không lấy card listing.
Profile tái lập ở `data/diagnostics/week3_readiness_20260926/profiles.json`,
bảng máy đọc được `field_profile.csv`. Script: `scripts/profile_week3_inputs.py`.
Không gửi request mạng trong lượt đánh giá này, không gọi engine resume.
Nguồn lịch sử: **chưa có mẫu cục bộ được xác định**, nên chưa thể báo tỷ lệ thiếu,
schema hay so khớp giá trị của dataset lịch sử; không tự gán kết quả của 354 tin cho nó.

| Chỉ số | CareerLink | CareerViet |
| --- | ---: | ---: |
| Detail / ID duy nhất | 55 / 55 | 299 / 299 |
| Tên công ty khác nhau (chưa entity resolution) | 28 | 210 |
| Dạng giá trị lương raw khác nhau | 27 | 73 |
| Giá trị địa điểm raw khác nhau | 43 | 83 |
| Ngành nghề khác nhau | 39 nhãn trong HTML; JSONL chưa trích | 58 nhãn trong category_tags |
| Mô tả / yêu cầu không rỗng | 55 / 55 | 299 / 299 |
| Snapshot được chọn | 1 batch | 1 batch |

Mẫu CareerLink là 50 tin trang 1 + 5 tin trang 2 trước khi bị chặn, không phải mẫu ngẫu nhiên.
FPT chiếm 10/55; nhãn bán hàng/kinh doanh có ở 22/55, tư vấn dịch vụ khách hàng 17/55.
Các nhãn có thể cùng thuộc một tin, không cộng thành số tin. CareerViet cũng là mẫu theo
thứ tự listing; 210 tên không được hiểu ngay là 210 thực thể công ty đã chuẩn hóa.

## 1. Toàn bộ trường, kiểu JSON thực tế và thiếu

Cả hai nguồn có **45 key trên mỗi record**, không có key vắng mặt.
“Thiếu” bên dưới = null, chuỗi rỗng/trắng hoặc array rỗng; không coi 0/false là thiếu.
Các array rỗng của CareerLink là `[]`, không phải null và chưa quan sát kiểu phần tử ở nguồn này.
Array không rỗng trong CareerViet có phần tử string. CSV tách riêng absent/null/blank/empty array.

| Trường | Kiểu thực tế CareerLink | Thiếu CareerLink | Kiểu thực tế CareerViet | Thiếu CareerViet |
| --- | --- | ---: | --- | ---: |
| `application_deadline` | null | 55/55 (100%) | string | 0/299 (0%) |
| `application_deadline_raw` | null | 55/55 (100%) | string | 0/299 (0%) |
| `application_method` | null | 55/55 (100%) | null | 299/299 (100%) |
| `batch_id` | string | 0/55 (0%) | string | 0/299 (0%) |
| `benefits` | array (rỗng) | 55/55 (100%) | array[string] | 4/299 (1.34%) |
| `candidate_requirements` | string | 0/55 (0%) | string | 0/299 (0%) |
| `canonical_url` | string | 0/55 (0%) | string | 0/299 (0%) |
| `category_tags` | array (rỗng) | 55/55 (100%) | array[string] | 0/299 (0%) |
| `company_address` | null | 55/55 (100%) | null | 299/299 (100%) |
| `company_id` | null | 55/55 (100%) | string / null | 3/299 (1%) |
| `company_industry` | null | 55/55 (100%) | null | 299/299 (100%) |
| `company_name` | string | 0/55 (0%) | string | 0/299 (0%) |
| `company_size` | null | 55/55 (100%) | null | 299/299 (100%) |
| `company_url` | null | 55/55 (100%) | string / null | 3/299 (1%) |
| `content_hash` | string | 0/55 (0%) | string | 0/299 (0%) |
| `crawled_at` | string | 0/55 (0%) | string | 0/299 (0%) |
| `detailed_work_address` | string / null | 32/55 (58.18%) | string | 0/299 (0%) |
| `education_level` | null | 55/55 (100%) | string | 0/299 (0%) |
| `experience_raw` | null | 55/55 (100%) | string / null | 33/299 (11.04%) |
| `income_text` | null | 55/55 (100%) | string | 0/299 (0%) |
| `job_description` | string | 0/55 (0%) | string | 0/299 (0%) |
| `job_level` | null | 55/55 (100%) | string / null | 17/299 (5.69%) |
| `job_title` | string | 0/55 (0%) | string | 0/299 (0%) |
| `job_type` | null | 55/55 (100%) | string | 0/299 (0%) |
| `listing_url` | string | 0/55 (0%) | string | 0/299 (0%) |
| `location_raw` | string | 0/55 (0%) | string | 0/299 (0%) |
| `parser_version` | string | 0/55 (0%) | string | 0/299 (0%) |
| `posted_at_estimated` | null | 55/55 (100%) | string | 0/299 (0%) |
| `posted_at_raw` | string | 0/55 (0%) | string | 0/299 (0%) |
| `posted_date_precision` | string | 0/55 (0%) | string | 0/299 (0%) |
| `profession_tags` | array (rỗng) | 55/55 (100%) | array (rỗng) | 299/299 (100%) |
| `raw_html_path` | string | 0/55 (0%) | string | 0/299 (0%) |
| `requirement_tags` | array (rỗng) | 55/55 (100%) | array[string] | 33/299 (11.04%) |
| `salary_raw` | string | 0/55 (0%) | string | 0/299 (0%) |
| `schema_version` | string | 0/55 (0%) | string | 0/299 (0%) |
| `snapshot_date` | string | 0/55 (0%) | string | 0/299 (0%) |
| `source_job_id` | string | 0/55 (0%) | string | 0/299 (0%) |
| `source_name` | string | 0/55 (0%) | string | 0/299 (0%) |
| `source_reported_total` | integer | 0/55 (0%) | integer | 0/299 (0%) |
| `source_url` | string | 0/55 (0%) | string | 0/299 (0%) |
| `specialization_tags` | array (rỗng) | 55/55 (100%) | array (rỗng) | 299/299 (100%) |
| `vacancies` | null | 55/55 (100%) | null | 299/299 (100%) |
| `vacancies_raw` | null | 55/55 (100%) | null | 299/299 (100%) |
| `work_model` | null | 55/55 (100%) | null | 299/299 (100%) |
| `working_time` | null | 55/55 (100%) | string | 0/299 (0%) |

Lưu ý kiểu/ý nghĩa:

- ID CareerLink là string chữ số (ví dụ 3634108); CareerViet là string hex (35C87EF3).
  Không ép ID đa nguồn thành integer; khóa phải kèm source_name.
- crawled_at là string ISO-8601 có múi giờ; snapshot_date là string ngày YYYY-MM-DD.
  application_deadline CareerViet cũng là string ngày sau serialization, không phải JSON date.
- posted_at_raw có hai dạng khác nhau (xem dưới); không chọn một parser ngày chung mù quáng.
- source_reported_total là integer tổng nguồn hiển thị, không phải số dòng thu được.
- content_hash là string SHA-256; không dùng làm business key thay cho ID nguồn.
- Không suy từ “0% thiếu trong mẫu hợp lệ” thành ràng buộc NOT NULL cho mọi nguồn/lịch sử:
  crawler đã lọc bỏ record thiếu nội dung, nên đây là mẫu đã qua điều kiện chấp nhận.

## 2. Null do chưa trích khác với nguồn không có

Trong 55 HTML CareerLink đã có những dữ liệu sau nhưng parser hiện chưa điền vào JSONL:

| Dữ liệu trong detail HTML/JSON-LD | Độ phủ đã thấy | Trạng thái JSONL |
| --- | ---: | --- |
| Kinh nghiệm, cấp bậc, học vấn, loại công việc | 55/55 | null |
| Nhãn ngành nghề | 55/55, tổng 39 nhãn | category_tags=[] |
| URL công ty / ID có trong URL | 55/55 | company_url/id=null |
| Quy mô công ty | 55/55, 5 khoảng quy mô | company_size=null |
| validThrough / khối hạn ứng tuyển | 55/55 | application_deadline*=null |
| Khối phúc lợi riêng | 44/55 | benefits=[] |
| Khối địa chỉ văn phòng riêng | 23/55 | detailed_work_address có đúng 23; 32 null |

Kinh nghiệm trong HTML gồm 0–1 năm (29), 1–2 (15), 2–5 (9), 5–10 (2).
Cấp bậc gồm nhân viên (47), quản lý/trưởng phòng (3), trưởng nhóm/giám sát (2),
kỹ thuật viên/kỹ sư (2), mới đi làm (1). Học vấn có 6 nhãn; 55/55 loại công việc
“Nhân viên toàn thời gian”. Quy mô công ty gồm 25–99, 100–499, 500–999,
1.000–4.999, 5.000–9.999 nhân viên.

11 tin không có khối phúc lợi riêng không có nghĩa không có quyền lợi trong mô tả.
Ví dụ 3628750 lồng thu nhập/quyền lợi trong mô tả. Chưa phân loại toàn bộ nội dung tự do.
Số lượng tuyển không có ở key totalJobOpenings trong 354 JSON-LD; vẫn có ví dụ
“số lượng 02” trong mô tả CareerLink 3633899. Không kết luận dữ liệu số lượng tuyển
hoàn toàn không tồn tại.

**Không cần crawl thêm để thiết kế các trường này.** Có thể bổ sung trích xuất offline sau,
nhưng lượt này chỉ đánh giá, không đổi parser hoặc 55/299 record.

## 3. Lương: những quy tắc đã có mẫu thật

| Trường hợp | CareerLink | CareerViet | Ví dụ / nhận xét |
| --- | ---: | ---: | --- |
| Khoảng số nguyên, đơn vị triệu | 37 | 0 trong salary_raw | 8 triệu - 10 triệu |
| Khoảng số thập phân, đơn vị triệu | 3 | 0 trong salary_raw | 7.1 triệu - 11.6 triệu |
| Khoảng VND/tháng dạng số tuyệt đối | 0 | 140 | 15000000 - 20000000 VND MONTH |
| Khoảng USD/tháng | 0 | 3 | 600 - 1600 USD MONTH |
| Thương lượng | 11 | 0 trong salary_raw | Không đổi thành 0 đồng |
| Cạnh tranh | 4 | 151 | Không suy ra số |
| Một con số đứng riêng, ngữ nghĩa chưa đủ trong raw | 0 | 5 | 15000000 / 20000000 / 25000000 |

Năm số đơn **không phải năm mẫu lương cố định**: HTML xác nhận **4 “Trên …” và
1 “Lên đến …”**. Ví dụ 35C87EF3 = trên 25 triệu; 35C86AA4 = lên đến 20 triệu;
35C868A4 = trên 20 triệu. Nếu chỉ đọc salary_raw sẽ mất hướng giới hạn, tiền tệ/kỳ lương.
income_text/HTML cần được dùng làm bằng chứng khi thiết kế chuẩn hóa sau này.

JSON-LD CareerViet có currency VND (280), USD (7), LTT (10), LCT (2);
chỉ 3 tin có khoảng lương USD số, không đồng nhất 7 metadata USD thành 7 khoảng lương.
LTT/LCT xuất hiện cùng giá trị định tính; cần giữ mã nguồn và đưa vào nhóm chưa ánh xạ,
không tự coi là ISO currency hay chuyển thành VND.
CareerLink JSON-LD currency VND ở 55 tin. Các giá trị kỳ lương đã thấy là MONTH.

Thiết kế ban đầu nên hỗ trợ raw + loại lương (range/lower_bound/upper_bound/negotiable/
competitive/unknown), số thập phân min/max nullable, currency_raw, period_raw và provenance.
Đây là đề xuất thiết kế, chưa chuyển đổi hoặc ghi lại raw.

## 4. Địa điểm: đủ mẫu để thiết kế quan hệ nhiều-nhiều

CareerLink có 49 tin một khối địa điểm, 2 tin ba khối (3633921 và 3633922:
Nghệ An / Quảng Trị / Đà Nẵng), 4 tin dùng địa chỉ văn phòng thay cho khối địa điểm riêng.
location_raw đang ghép các khối thành text, nên không tách mù theo dấu phẩy.
Dấu phẩy còn phân cách phường/quận/tỉnh trong cùng một địa điểm, ví dụ
“Hải Châu, Sơn Trà, Đà Nẵng”; địa chỉ đầy đủ còn chứa nhiều dấu phẩy.

CareerViet: jobLocation trong JSON-LD là object ở 279 tin, array ở 20 tin;
**20 array đều có nhiều địa điểm**. Parser hiện chỉ chọn phần tử đầu để ghi location_raw.
Ví dụ 35C87FF3 có 2 địa điểm; 35C87ED9 có 3. Đây là giới hạn parser đã có mẫu để sửa
offline, không phải cần nhiều record hơn mới biết mô hình phải hỗ trợ nhiều địa điểm.
Có cả “Toàn quốc, VN” (1), “Khác, VN” (1), tỉnh đơn và tỉnh/quận.
Hai nguồn có thứ tự địa danh, độ chi tiết và tên gọi khác nhau; giữ raw,
định danh địa lý/mapping theo phiên bản, không chỉ split chuỗi hoặc thay tên cũ vô điều kiện.

## 5. Ngày đăng và thời điểm quan sát

- CareerLink: 55 chuỗi DD-MM-YYYY, 14 ngày khác nhau, từ 27/08 tới 26/09/2026.
  posted_at_estimated hiện null và precision=unknown ở 55 tin: đây là phần chưa chuẩn hóa,
  không phải không có ngày đăng trong nguồn.
- CareerViet: 299 ISO timestamps có Z, 124 giá trị khác nhau; 176 tin có cùng
  2026-09-23T02:00:11.013Z. Chỉ khẳng định đó là datePosted nguồn cung cấp;
  chưa biết đó là ngày đăng đầu tiên hay việc nguồn cập nhật đồng loạt.
- Đối chiếu từng record: **0/354 có ngày đăng sau thời điểm crawl**.
- CareerViet giữ snapshot_date=2026-09-22 nhưng 298/299 crawled_at thuộc ngày
  23/09 theo Asia/Ho_Chi_Minh, do batch được tiếp tục qua ngày; 1 tin thuộc 22/09.
  Ngày batch khác ngày quan sát không tự động là lỗi. CareerLink: 55/55 cùng ngày 26/09.
- Không dùng snapshot_date làm ngày đăng hoặc thay thế observed_at. Cần phân biệt
  source_posted_at, source_updated_at (chưa rõ), crawled_at và ngày/lần batch;
  chỉ gán độ chính xác mà bằng chứng hỗ trợ. Chưa có mẫu raw ngày đăng tương đối.

## 6. Cấu trúc mô tả và yêu cầu

| Nội dung | CareerLink: min / median / max ký tự | CareerViet: min / median / max |
| --- | ---: | ---: |
| Mô tả | 118 / 680 / 1.761 | 158 / 982 / 6.542 |
| Yêu cầu | 88 / 253 / 990 | 26 / 698 / 4.501 |

CareerLink: mô tả có p ở 50 tin, ul/li ở 11, br ở 10; yêu cầu tương ứng 47, 9, 7.
Bullet bằng dấu gạch đầu dòng xuất hiện ở 49 mô tả và 48 yêu cầu.
CareerViet bổ sung ordered list ol (9 mô tả, 5 yêu cầu), unordered lists,
định dạng strong/em và nội dung dài hơn. Một mô tả 35C86419 lấy từ JSON-LD
khi không có DOM section tương ứng; 298 mô tả còn lại và 299 yêu cầu có DOM section.
Đối chiếu toàn văn sau chuẩn hóa khoảng trắng: **55/55 và 299/299 khớp nguồn đã lưu**.

Cả 354 JSONL đã dồn nội dung thành một dòng, không còn newline; không bảo toàn biên đoạn/
bullet như HTML. Vì vậy giữ text dài và tham chiếu HTML, không đặt VARCHAR(255),
không dùng số dòng text để đo độ đầy đủ. Chưa có table trong các section đã đo;
không suy từ text ngắn (ví dụ yêu cầu 26 ký tự) thành mất dữ liệu.
Mô tả có thể gộp quyền lợi/thu nhập/lịch làm việc, không giả định mọi nguồn tách section giống nhau.

## 7. Đối chiếu mẫu lịch sử: giới hạn hiện tại

Đã tìm trong repo/data và cache Hugging Face tiêu chuẩn; chưa định vị file của
`tinixai/vietnamese-job-descriptions` hoặc mẫu lịch sử do người dùng nhắc.
Các file sample_records.jsonl tìm được là probe live, **không phải dữ liệu lịch sử**.
Không tải Hugging Face vì nhiệm vụ yêu cầu offline; đã hỏi đường dẫn/file mẫu.

Do chưa đọc mẫu, **chưa kiểm chứng**: tổng 608.000 dòng trên máy, schema/kiểu thực,
ID/source URL, thời gian quan sát, tách description/requirements, currency,
tỷ lệ null, trùng lặp hoặc khác biệt ngôn ngữ của lịch sử.
Không ghi một bảng tỷ lệ thiếu lịch sử giả, không mặc định metadata lịch sử đều null.

Khi nhận mẫu, đối chiếu theo ngữ nghĩa, không chỉ tên cột:
ID+nguồn; title/company; description/requirements gộp hay tách; salary/location dạng
string/list/object; posted date và observed/import date; provenance file/dòng.
Nếu thiếu source_job_id thì dùng định danh ingest theo provenance riêng, không tạo ID website giả.
Nếu thiếu crawled_at lịch sử thì để unknown, lưu imported_at riêng, không dùng hôm nay làm ngày crawl.
Phần lịch sử chưa kiểm chứng không chặn thiết kế lõi cho hai nguồn live đã đo,
nhưng adapter/mapping lịch sử chưa được xem là hoàn tất.

## 8. Ma trận trường hợp đã có / chưa có

| Trường hợp | Đã có bằng chứng | Chưa có / cần kiểm tra tiếp |
| --- | --- | --- |
| Nguồn/ID/công ty | ID numeric-string và hex-string, nhiều tin/công ty | Cùng một công ty hoặc một tin giữa hai nguồn chưa entity-match |
| Lương | range, decimal, định tính, USD, lower/upper bound | Lương cố định số có ngữ nghĩa rõ; hour/week/year; EUR; min>max/định dạng lỗi |
| Địa điểm | một/nhiều, địa chỉ, toàn quốc/khác, object/array | Địa điểm nước ngoài; remote/hybrid có trường cấu trúc xác nhận |
| Thời gian | DMY và ISO-Z, batch qua ngày, timestamp trùng nhiều tin | Ngày tương đối/không phân tích được; cùng ID thay đổi qua các snapshot |
| Mô tả/yêu cầu | ngắn/dài, p/br/ul/ol, DOM và JSON-LD fallback | Tin hợp lệ thiếu một section, nội dung chỉ bằng ảnh/PDF hoặc table trong section |
| Loại hợp đồng | CareerLink full-time; CareerViet có PART_TIME, CONTRACTOR, INTERN | Các loại này trên CareerLink chưa có trong 55 mẫu |
| Số lượng tuyển | Có văn bản số lượng trong mô tả | vacancies kiểu integer chưa xuất hiện trong hai JSONL |
| Thiếu dữ liệu | null/array rỗng, một số optional thiếu, parser chưa trích | Không đo được tỷ lệ thiếu của toàn thị trường do mẫu đã lọc hợp lệ |
| Vòng đời | Hai tập snapshot, provenance/HTML/hash | Thay đổi nội dung cùng ID, hết hạn/xóa rồi đăng lại; không suy inactive từ crawl lỗi |
| Lịch sử | Chưa có mẫu local xác định | Tất cả kết luận schema/tỷ lệ lịch sử phải chờ file |

“Chưa có” chỉ áp dụng tập/khối đã đo, không khẳng định website không có trường hợp đó.
Có thể viết fixture giả lập edge case ngay cho thiết kế, nhưng phải gắn nhãn synthetic,
không tính vào số detail thật.

## 9. Việc có thể thiết kế ngay (chưa triển khai)

1. Grain tin nguồn: (source_name, source_job_id); grain lần quan sát tách khỏi tin.
   Không dùng title/company hoặc content_hash làm ID duy nhất.
2. Contract raw giữ 45 field + provenance/version/HTML; schema nullable cho optional,
   phân biệt absent/null/empty/unknown/not_extracted trong thống kê chất lượng.
3. Dự kiến quan hệ job–location và job–category nhiều-nhiều; employment type cũng có thể đa trị
   (CareerViet có FULL_TIME, PART_TIME, CONTRACTOR, INTERN trong cùng một tin).
4. Lương có raw/loại giới hạn/currency/period; không biến cạnh tranh thành 0,
   không biến upper/lower bound thành fixed.
5. Thời gian có giá trị nguồn, độ chính xác, thời điểm crawl và ngày batch riêng;
   không coi toàn bộ datePosted là lần đăng đầu tiên.
6. Các test chất lượng: khóa/duplicate, nguyên nội dung vs HTML, missing reason,
   salary bound/unknown currency, nhiều địa điểm, locale/ngày, snapshot qua ngày.
7. Giữ việc xác minh mapping lịch sử, địa lý, chuẩn hóa công ty, remote/hybrid và vòng đời
   trong backlog có bằng chứng cụ thể. Không trì hoãn thiết kế để chạy thêm cho đủ số.

## 10. Resume có điều kiện — chưa chạy live

Trạng thái gần nhất đã biết: hCaptcha tại detail thứ 56, HTTP 200.
**Không kiểm tra lại live trong lượt này; chưa xác nhận website hiện đã bình thường,
cũng không khẳng định vừa thử lại và vẫn bị chặn.**
Hiện 55 dòng/55 ID, 45 pending; record mới tăng thêm trong lượt này: **0**.
Giữ nguyên dữ liệu, HTML, checkpoint và user agent.

Đã kiểm tra config + checkpoint offline: mode bounded, parser careerlink-1.0.2,
start URL/batch/access basis khớp. Cùng ID đã hoàn tất không bị tải/ghi lại.
Hai listing đã dùng đủ giới hạn 2; không mở trang 3. Detail_requested=56,
vì vậy max-details=**76** cho **tối đa 20 lần thử thêm**, không phải 76 tin mới.
Nếu cả 20 thành công, tổng raw là 75, không phải 76 (một attempt cũ đã thất bại).

Chỉ dùng sau khi điều kiện truy cập đã được xác nhận trở lại phù hợp; kiểm tra lại
robots/điều khoản trước đợt thử, không xem “homepage mở được” là detail được phép.
Không dùng login, cookie người dùng, đổi IP/proxy/browser/UA; không loop retry.
Crawler kiểm tra robots đầu run và dừng nếu hCaptcha quay lại kể cả HTTP 200.

```bash
# Chạy từ thư mục gốc repository job_warehouse chứa đúng batch cục bộ.
.venv/bin/job-crawler crawl careerlink \
  --mode bounded --project-owner-public-test --fetcher http \
  --max-pages 2 --max-details 76 \
  --delay-min 10 --delay-max 15 --max-retries 0 --timeout 30 \
  --save-html --require-complete-content \
  --resume --resume-batch-id 20260926T160422Z-c39d6a20 \
  --user-agent 'job-warehouse-crawler/0.1 (public academic research; single-threaded)'
```

Đây là lệnh chuẩn bị, không phải lệnh đã thực thi.
Preflight: `data/diagnostics/week3_readiness_20260926/resume-preflight.json`.
Sau đúng một đợt, đo số tăng thêm bằng ID sau trừ ID trước; kiểm tra 55 dòng cũ
còn nguyên prefix, không chỉ lấy detail_succeeded làm số mới. Nếu dừng ngay bởi challenge,
số mới là 0 và vẫn bắt đầu thiết kế với 354 tin hiện có.
Kết quả mock offline xác nhận resume giữ prefix, không refetch ID đã xong và giới hạn tính theo attempts.

## 11. Tái lập

```bash
.venv/bin/python scripts/profile_week3_inputs.py --output-dir data/diagnostics/week3_readiness_20260926
.venv/bin/pytest -q tests/unit/test_week3_profile.py tests/integration/test_careerlink_resume_budget.py
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
```

Chỉ bổ sung script profile, kiểm thử offline và báo cáo này; không sửa crawler/parser đang chạy,
không viết lại jobs.jsonl, không đổi trạng thái checkpoint, không commit/reset Git.

## 12. Kết quả kiểm tra cuối lượt

- Toàn bộ test offline: **159 passed**; Ruff check/format đạt (82 file); mypy đạt (39 source file).
- Hai jobs.jsonl giữ nguyên SHA-256 như profile; prefix 55 dòng CareerLink không đổi,
  duplicate=0, removed_ids=0, **new_unique_ids=0**. Kết quả tại `resume-delta.json`.
- CareerLink vẫn 55 completed / 45 pending, chưa thực thi resume. Không có request tới
  CareerLink, CareerViet, VietnamWorks hoặc Hugging Face trong lượt này.
- Một đợt resume sau này cần báo delta counters/ID và các lỗi mới theo timestamp;
  manifest/error log hiện giữ lỗi challenge cũ, không được coi cờ/lỗi cũ là challenge mới.
- Chỉ bốn file mới thuộc lượt này: báo cáo, script profile, unit test profile và integration
  test resume-budget. Không sửa các thay đổi Git có sẵn hoặc parser/storage nguồn.
