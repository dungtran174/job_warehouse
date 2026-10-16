# Silver S4 — chuẩn hóa lương lịch sử

`salary-v3`, `owner-salary-20261016-v3`. Chạy offline; không gọi crawler,
không sửa Bronze/S2/S3 và chưa publish PostgreSQL. Cột salary là nguồn mức tiền mặc định. Chỉ78 ID được chủ dự án duyệt cụ thể
mới dùng quyết định đã đối chiếu benefits; không tự trích hoặc bù cho tin khác.
Không bù bằng description, requirements, title hoặc mô hình AI.

## Quy tắc đã chốt

- Thiếu kỳ nhưng có đơn vị tiền: giả định tháng, lưu cờ `assumed_month`.
- Một mức → min=max; khoảng → hai cận; từ/trên và dưới/tới giữ cận thiếu null.
  Giữ thông tin cận mở/đóng trong artifact kỹ thuật.
- Khoảng có đúng một cận 0 và cận kia dương → min=max=số dương, lưu
  `positive_bound_as_point`. Toàn số 0 → hai cận null, giữ tin.
- Hai số dương đảo thứ tự: sắp xếp min≤max, lưu `positive_bounds_reordered`.
- Không tự loại giá trị cao/thấp hoặc sửa số nghi lỗi. Các tín hiệu <1 triệu,
  >200 triệu, khoảng max>10×min chỉ là cờ kiểm tra, không là ngưỡng loại.
- Chỉ lấy phần tiền rõ trước thưởng/hoa hồng chưa định lượng. Thu nhập lên
  đến 20 triệu chỉ có max, component=advertised_income. Không đổi NET/GROSS.
- Tuần ×52/12, ngày ×26, giờ ×208 về tháng. Đây là quy ước phân tích,
  không phải lịch làm thực tế, đặc biệt với part-time/thời vụ. Giữ cờ.
- USD cần bảng tỷ giá local có năm, thời kỳ, nguồn, series, reference và
  approved=true. Không fallback năm khác. Thiếu rate → `fx_missing`, hai
  cận VNĐ null, giữ số gốc trong audit. Không có truy cập mạng trong CLI.
- Owner đã duyệt 2025: 24.962 VNĐ/USD; 2026: 25.179 tạm tính cho tháng 1–8.
  Nguồn: [MUFG, bảng Việt Nam trang 13](https://www.bk.mufg.jp/report/econew/economic_monthly_ASEANIndiaau20261014e.pdf).
  2026=(25.083×3+25.134×3+25.247+25.534)/8, bình quân có trọng số số tháng
  từ các kỳ đã làm tròn; không phải bình quân chính xác của các tỷ giá ngày.
  Bảng tỷ giá/PDF có SHA và công thức được giữ ngoài Git; CLI không tự tải.
- Decimal; nhân tiền tệ và kỳ một lần, làm tròn HALF_UP đến 0,01 VNĐ ở cuối.
- Số không đủ đơn vị, biểu thức thay thế hoặc chưa hỗ trợ: giữ tin và lý do,
  không đoán đơn vị. Trong nhóm85 dòng ban đầu, 7 dòng đã xác nhận VNĐ/tháng; 78 dòng còn lại đã
  được chủ dự án duyệt sau đối chiếu benefits:47 có cận và31 để null. Không
  biến chính sách theo ID này thành bộ suy luận tự động cho các tin khác.

## Ngoại lệ theo ID

`src/job_warehouse/silver/salary/owner_overrides.csv` lưu raw kỳ vọng, hành
động, hai cận theo tháng, tiền tệ, cờ và tham chiếu quyết định owner. Chỉ áp dụng cho revision đã
pin và đúng raw; raw lệch phải dừng thay vì sửa nhầm. Không alias cả cột.

- Tháng, min=max: 6653 (10 triệu), 4653 (5 triệu), 11027 (10 triệu),
  11199 (8,5 triệu), 12746/12783 (2 triệu), 13313 (10 triệu), 13753 (4 triệu).
- Hai cận null vì chưa xác định: 3199, 9073, 9646, 10769, 10771, 17155.
- ID43531 `$ 13tr-17tr /tháng`: min=13 triệu, max=17 triệu VNĐ/tháng.

Owner duyệt thêm 19 ID từ hàng đợi review, tổng 34 quyết định trong CSV:

| ID | Min / max theo triệu VNĐ mỗi tháng, trừ khi ghi USD |
|---|---|
| 50951 | 9 / 12 |
| 51099 | 6 / 10 |
| 51104 | 9 / 15 |
| 51109 | 10 / 18 |
| 51193 | 10 / 14 |
| 51271 | 12 / 15 |
| 51338 | 8 / 8 |
| 43561 | 10 / 15 |
| 45017 | 2 / 3 |
| 51387 | 2 / 2 |
| 43519 | 20 / 30 |
| 50962 | 6 / 10 |
| 50643 | null / 20 |
| 51350 | 20 / 50 |
| 43499 | null / 30 |
| 50734 | 10 / 15 |
| 45010 | 10 / 15 |
| 50862 | 8 / 15 |
| 108256 | null / 1.800 USD; qua bảng FX năm2026 → max45.322.200 VNĐ |

ID50962 có nguồn6–15triệu nhưng owner chọn6–10; ID45010 có nguồn15–20
nhưng owner chọn10–15. Lưu cờ `owner_numeric_correction`, không gọi là chỉ
sửa cách viết. ID108256 chỉ lấy cận trên tháng1.800USD, không nhân14;
lưu cờ xử lý gói thu nhập theo quyết định owner. Cận thiếu giữ null, không
biến tin “lên đến” thành một mức exact. Các quyết định không dùng benefits
để tự điền cho ID khác, kể cả có cùng salary raw.

### Quyết định theo benefits — v3

Bảng CSV hiện có112 quyết định:34 cũ và78 quyết định mới. Mỗi dòng mới lưu
raw kỳ vọng, source_min/source_max, currency, period, rounding_quantum,
evidence_column=benefits và SHA256 của benefits. Khi benefits nguồn khác
hash đã duyệt thì dừng, không áp dụng nhãn cũ. Benefits null được phân biệt
với chuỗi rỗng; không commit toàn văn benefits hoặc báo cáo thật vào Git.

- Toàn bộ mục2/3/4 của báo cáo78 ID để hai cận null; thêm2354/12471/16620
  trong mục1 cũng để null. Tổng31 dòng null mới; giữ tin và lý do.
-47 dòng còn lại gán đúng điểm/khoảng/cận theo owner, không tự thêm cận.
  Ví dụ9524 min7triệu/maxnull;13314 minnull/max1triệu;11246 min=max18triệu.
-1310:200–500triệu/năm →17–42triệu/tháng;1469:200–700 →17–59triệu;
  6446 chỉ max300triệu/năm →max25triệu/tháng;7263:120–200 →10–17triệu.
  Chia12 trước, sau đó làm tròn từng cận lên đến **một triệu VNĐ**. Giữ số
  năm, period=year, quantum=1000000 và cờ làm tròn trong audit. Phép chia
  dùng Decimal trực tiếp, không nhân trước với hệ số1/12 đã làm tròn.
- Quy tắc làm tròn này chỉ áp dụng bốn ID theo năm đã được duyệt; không
  tự làm tròn mọi mức tháng hoặc các khoản tuần/ngày/giờ lên triệu.
-13314 benefits ghi hỗ trợ thực tập700.000VNĐ/tháng nhưng owner chọn
  cận trên1triệu; lưu cờ owner_numeric_correction, không gọi là số trích
  nguyên từ benefits. Các quyết định chọn riêng lương cứng, thu nhập,
  lương thử việc hoặc cận theo owner cũng giữ cờ, không ghi đè văn bản nguồn.

Áp dụng ngoại lệ trước nhân kỳ/FX; 10 triệu đã sửa sang tháng không nhân208.
Chỉnh sửa owner không được gọi là thông tin đã kiểm chứng từ website gốc.

## Đầu vào, đầu ra và vận hành

```bash
.venv/bin/job-warehouse silver salary \
  --core-run /path/outside/repo/s2-current \
  --industry-run /path/outside/repo/s3-industry-current \
  --fx-rates /path/outside/repo/fx_rates.json \
  --output-dir /path/outside/repo/s4-new-run
```

Output phải mới và ngoài repo; không ghi đè. Bỏ --fx-rates chỉ phù hợp để
khảo sát phần VNĐ, không phải nghiệm thu quy đổi USD hoàn chỉnh.
S2/S3 Parquet được kiểm SHA theo manifest, cùng tập record_key/ID/index,
source_content_hash và year. Giữ ngưỡng ngành 500 đã chốt, không đếm lại
ngành theo số mẫu lương. Không join bằng thứ tự dòng hoặc title/company.

| File | Grain và vai trò |
|---|---|
| salary_enrichment.parquet | Một dòng/core; raw, hai cận VNĐ/tháng, trạng thái, số/kỳ/tiền tệ nguồn, cờ, FX reference; đủ khóa đối soát |
| jobs.parquet | Một dòng/core, 14 cột nghiệp vụ theo thiết kế gọn |
| jobs_analysis.parquet | Cùng schema jobs, chỉ giữ scope ngành ≥500 của S3 |
| salary_mapping.csv | Raw×năm×kết quả×tập chọn; số dòng, ID ví dụ và lý do |
| salary_review.csv | Tổng hợp needs_review, thiếu FX, owner đã chọn null và các tín hiệu bất thường; có mặt trong file không đồng nghĩa chưa được duyệt |
| salary_quality_report.json | Coverage toàn core/tập chọn, trạng thái theo năm/ngành, kiểm tra đọc lại |
| fx_rates.json / owner_overrides.csv | Bản chụp cấu hình và quyết định đã áp dụng |
| manifest.json | SHA đầu vào, mã nguồn/policy, đầu ra, revision/license, partition, giới hạn |

`jobs` gồm id, job_title, company_name, salary_min, salary_max, location,
job_type, job_industry, experience_min_years, experience_max_years,
education_level, job_position, requirements, year. Location là mảng tên
địa điểm theo kết quả S3; giữ cả nhãn Chưa xác định/remote/toàn quốc khi có.
Job_type là chuỗi nguồn đã thống nhất cách viết, giữ Remote và nhãn ghép.
Tên công ty dùng bản chuẩn hóa S2 v6; học vấn giữ nhãn nguồn. Hai cận kinh
nghiệm theo năm được giữ chính xác đến 6 chữ số thập phân như S2; chưa ép
về decimal(6,2) của bản sơ đồ cũ. Tiền là decimal(18,2). Chưa tạo bảng SQL.

Không nhân dòng khi nhiều nơi, không lọc tin vì thiếu lương. Salary raw nằm
trong audit và Bronze, không cần thêm vào jobs gọn. Cận chỉ được ghi khi đã
là VNĐ/tháng; các ca chưa xác định phải null, không được còn USD/giờ.

## Kiểm định nghiệm thu S4 — 16/10/2026

Chủ dự án đồng ý dùng hai trợ lý AI riêng gán nhãn mù: không xem code hoặc
prediction. Khóa code/sample trước đối chiếu; 240 chuỗi phân tầng và60 chuỗi
phổ biến bổ sung không trùng nhau. 300/300 nhãn khớp giữa hai reviewer và
parser về hai cận nguồn, tiền tệ, kỳ, loại khoảng và inclusivity khi có số.
Các chuỗi không có mức số được chấm theo abstention; thông tin currency/
period phụ của placeholder không tính như số đo lương công bố.

| Nhóm chuỗi | N | Khớp |
|---|---:|---:|
| Số tiền VND | 138 | 138 |
| Đơn vị triệu/nghìn/tr | 60 | 60 |
| Có qualifier | 20 | 20 |
| USD | 30 | 30 |
| Kỳ khác tháng | 30 | 30 |
| Dạng khác | 8 | 8 |
| Không có lương số | 12 | 12 |
| Toàn số0 | 2 | 2 |

Trọng số tần suất trên mẫu:100% khớp; các chuỗi đại diện448.604 dòng, bằng
73,94% của606.745 dòng không có owner override. Đây là độ phủ và đồng thuận
trên mẫu AI, không phải accuracy toàn thị trường hoặc nhãn con người.
112 ID owner quyết định bị loại khỏi benchmark tự động, đã đối soát riêng.
Gate ≥200 chuỗi và ≥95% đồng thuận theo phương pháp đã duyệt được đáp ứng.
Mẫu/nhãn/prediction/SHA/biên bản lưu ngoài Git; không đưa dữ liệu thật vào test.

Output audit có salary_numeric_eligible (ít nhất một cận VNĐ/tháng) và
salary_midpoint_eligible (đủ hai cận); không lấy tin chỉ một cận tính midpoint.
Quality report có comparison_coverage_by_industry_year cho cả core và tập
ngành đã chọn, giữ đúng mẫu số. Chúng là cột kỹ thuật, không thêm vào jobs gọn.
Run manifest ghi pending tại lúc xuất; acceptance.json sau kiểm định liên kết
SHA của manifest, report AI và code đóng băng để xác nhận gate tương ứng.

## Kiểm thử và giới hạn

Test offline về số/đơn vị, qualifier, cận 0/đảo, kỳ, FX, ngoại lệ và dữ liệu
không đủ căn cứ. Integration kiểm SHA, identity, raw, projection, partition,
đọc lại Decimal/array, replay theo batch size và hủy output nếu lỗi. Cuối run
kiểm lại hash input/code, rồi mới công bố thư mục hoàn chỉnh.

Kiểm tra kỹ thuật và đồng thuận AI là hai bằng chứng riêng. Báo coverage và
review; không gọi parser chính xác toàn bộ. Các giá trị có tín hiệu bất thường vẫn
được giữ theo owner; dùng BI cần đọc cờ audit. Midpoint là đại diện khoảng
đăng tuyển, không phải lương thực nhận; tin một cận không tính midpoint.
Cận có nguồn benefits chỉ áp dụng qua quyết định owner và kiểm hash, không
có extractor NLP benefits tự động. Không có extractor kỹ năng, job_skill_match, Gold, dashboard hoặc Airflow
mới trong S4. Không commit dữ liệu thật, PDF nguồn hay output chạy.
