# Silver core lịch sử — S2

`silver-core-v4`, `core-mappings-v1`, `requirements-attributes-v4`.
S2 chạy offline bằng Python/PyArrow, độc lập với crawler, PostgreSQL và Docker.
Đây là đầu ra trung gian local; bảng `silver.job_clean` được publish ở S6.

## Quyết định và grain

- Nguồn duy nhất là artifact Hugging Face đã pin trong contract S0/S1.
- Tách title null/blank hoặc literal `Không` sang quarantine. File hiện tại dự
  kiến 20 null +1 literal, core 606.857; đối soát core+quarantine=606.878.
- Dòng chỉ thiếu công ty/trường tùy chọn vẫn giữ. Không dùng description làm title.
- Một source row có đúng một record ở core hoặc quarantine; key hai tập không
  giao nhau. Trùng nội dung giữ riêng, chưa lọc ngành/ngưỡng hoặc trích skill.
- Giữ 14 cột raw trong cả hai output và identity từ S0. Dataset ID không là ID
  website. Year chỉ là năm, không tạo posted_at. Quarantine chưa chạy enrichment.
- Đến S6, chuyển các quyết định quarantine vào row_decision theo cùng key,
  không loại/đếm cùng dòng thêm lần nữa.

## Từng cột

| Nguồn | Đầu ra/ý nghĩa |
| --- | --- |
| id | source_dataset_id, source_row_index, record_key, source_content_hash; không thay ID |
| job_title | job_title_clean; NFC/whitespace/control; null/Không tách riêng |
| company_name | company_name_clean/match_key/status; giữ dấu/pháp lý/chi nhánh; null và `.` riêng; key tương đương không chứng minh cùng pháp nhân |
| job_type | employment_types[], work_arrangement, shift_work; remote không suy full_time/onsite; không chọn nhãn đầu |
| education_level | education_category/status; Không/Kỹ sư mơ hồ, Trung học chưa biết THCS/THPT |
| job_position | label sạch +role/seniority/management arrays; không biến Nhân viên thành junior; nhãn lệch trường giữ raw/flag, không chuyển sang cột khác |
| experience_level | cận/kind/group/status, canonical months, source unit/values; point không tự là tối thiểu; khoảng không expand |
| job_description | text sạch có kiểm soát/status; không tóm tắt/cắt nội dung hoặc bù requirements |
| benefits | text sạch/status; thiếu không có nghĩa không có phúc lợi; không lấy tiền thưởng làm salary |
| requirements | clean/status/hash và học vấn/kinh nghiệm inferred riêng; không tạo skill S2 |
| year | integer 2022–2026 theo revision, không sinh ngày/tháng |
| salary | giữ raw, parser thuộc S4 |
| location | giữ raw, mapping thuộc S3 |
| job_industry | giữ raw, gộp ngữ nghĩa/scope thuộc S3 |

Text ngắn và dài dùng NFC; giữ dấu tiếng Việt và C++/C#/.NET/Node.js, dấu câu,
phủ định/newline. Plain mode không strip tag: `<T>` hay `a < b` được giữ. Chỉ
unescape token HTML chuẩn/numeric kết thúc bằng `;`; unknown `&CN;` giữ nguyên.
Giới hạn decode 4 lớp; quá giới hạn giữ biểu diễn nguồn đã NFC và flag, không
làm sạch dần mỗi replay. Control C0/DEL (trừ tab/newline) đổi thành khoảng trắng
với flag. Không xóa Unicode Cf đại trà. `.` ở content là placeholder;
requirements `Không/khác` là unusable khác physical null, không no_match.

Kinh nghiệm giữ exact decimal ở **months**. Years hiển thị decimal(18,6), có
`years_rounded`; 1 tháng=1 canonical month, năm hiển thị 0,083333. Không coi giá
trị làm tròn là exact. Buckets `<1`, `1–<3`, `3–<5`, `≥5`, range_crossing và
unknown/no_requirement/required_unspecified xét cả cận mở/đóng; không suy
kinh nghiệm thật của ứng viên. Dictionary và grammar có thể abstain nhãn mới.

## Học vấn/kinh nghiệm suy ra từ requirements

- Chỉ input requirements_clean. Cột nguồn chuẩn hóa và inferred giữ riêng.
- Summary chỉ nhận claim rõ, accepted/high, **required** hoặc no_requirement
  rõ nghĩa. Preferred/mentioned/negated giữ claims riêng, không điền yêu cầu
  bắt buộc; no_requirement không thành 0.
- Evidence/offsets Unicode code point, end exclusive, trỏ đúng clean text và
  requirements_text_hash. Có context, rule/version, confidence/reasons.
- Theo quyết định chủ dự án, claim student mặc định `mentioned`, kể cả
  “Đang là sinh viên Đại học năm 3, 4”; ưu tiên rõ giữ `preferred`. Giữ
  qualification student/student_final_year, không suy điều kiện bắt buộc
  và không đưa vào summary yêu cầu bằng đã tốt nghiệp.
- `qualification_state` mô tả điều kiện nhà tuyển dụng, không phải trình độ
  thực tế của ứng viên. Theo quyết định chủ dự án, `bằng/có bằng + bậc học`
  nhận biết được là graduated; vẫn giữ required/preferred riêng. `Từ + bậc
  học` là minimum_level kể cả không có `trở lên`; claim ghi reason
  owner_from_degree_minimum để truy vết chính sách này.
- Phủ định/ưu tiên chỉ áp dụng đúng tiêu chí; không truyền từ tình trạng gia
  đình, giới tính hoặc kỹ năng sang bằng cấp/kinh nghiệm độc lập. Scope kinh
  nghiệm chỉ lấy trong mệnh đề của chính claim, không lấy từ claim kế tiếp.
- Generic claim bị phủ định giữ evidence/context, parsed_value.experience
  là null; không lưu thành một yêu cầu kinh nghiệm khẳng định.
- OR rõ của một thuộc tính giữ options; danh sách bằng cấp ngăn bằng slash,
  dấu phẩy/gạch hoặc `và/hay` chưa rõ logic giữ needs_review. Cận `trở lên`
  nằm sau tên chuyên ngành cũng giữ review nếu chưa phân giải được.
- Câu điều kiện nhiều nhánh/có ngoại lệ/multiple scopes giữ complex hoặc
  needs_review. Không bắt buộc S2 v4 dựng cây OR–AND đầy đủ, không cộng năm/lấy
  giá trị đầu/cao nhất/midpoint. Summary liên quan để trống; job vẫn ở core.
- Comparison ghi source_unavailable/consistent/different_expression/
  potential_conflict/complex_unresolved...; chưa chọn một nguồn thắng cho BI.
- V4 giữ review cho cận tối thiểu trộn khoảng, nhánh đã/sắp tốt nghiệp,
  ngoại lệ chấp nhận sinh viên/mới ra trường và nhiều yêu cầu bắt buộc khác
  nhau chưa phân giải. Abstain có thể giảm coverage để tránh kết luận sai.
- V4 parse đủ hai đầu khoảng có đơn vị rõ như `6 tháng–1 năm`:
  cận canonical 6–12 tháng, giữ đơn vị/giá trị nguồn riêng từng đầu. Khoảng
  đảo cận hoặc trộn ngưỡng tối thiểu chưa rõ giữ review. Không lấy một phần
  khoảng tháng–năm thành điểm. Cận viết sai dấu chưa
  kiểm định giữ review, không sửa văn bản gốc. Ưu tiên theo domain/kỹ năng khác
  không áp lên thời lượng chung; phạm vi ưu tiên chưa rõ giữ review. Quản lý
  dự án/website/kênh không tự thành kinh nghiệm quản lý nhân sự.
- Khi cùng thuộc tính còn claim chưa phân giải hoặc nhánh theo nhiều vị trí,
  giữ review các claim liên quan trong tài liệu; thuộc tính độc lập vẫn có thể
  xử lý. Ghi reasons để kiểm tra ảnh hưởng coverage; không loại job vì review.
- v4 nhận diện các mẫu tiếng Việt rõ trong dictionary/grammar, không cam kết
  bao phủ mọi cách diễn đạt/tiếng Anh. Không có LLM/API hoặc skill extractor.
  `not_mentioned` chỉ có nghĩa không nhận diện được claim bằng rule v4;
  không chứng minh requirements không đề cập thuộc tính đó.

Claims là list[struct] trong Parquet với parsed_value có schema rõ; mục không
áp dụng nullable. `requirements_attribute_groups=[]` ở v4; không giả đã phân
giải đầy đủ logic phức tạp. S6 có thể lưu claims JSONB có validator riêng.
Confidence rule không là xác suất đã hiệu chuẩn.

## Chạy và replay

```bash
.venv/bin/job-warehouse silver core \
  --input /path/to/history_data.parquet \
  --output-dir /path/outside/repository/s2-core-run \
  --batch-size 2048
```

CLI chỉ nhận file pin, không có cờ bỏ kiểm SHA/N. Thư viện cho phép expected
values riêng để test fixture; provenance cờ pinned=false cho fixture khác.
Đường dẫn output phải ngoài repository và chưa tồn tại. Input không sửa;
validate mọi buffer/ID/year/schema/count, rồi batch-normalize một luồng. Gate
đối soát/key, footer output và SHA/asset hashes trước/sau chạy. Lỗi không
publish thư mục completed; staging được dọn, run tốt cũ không bị ghi đè.
Nếu tiến trình bị cưỡng bức dừng, staging ẩn có thể còn lại; đó không phải
run hoàn tất. Chỉ dọn staging của lượt đã xác nhận dừng, rồi replay vào
thư mục mới; không xóa staging của tiến trình đang chạy.
Replay chọn thư mục mới, không append. Content digest không phụ thuộc batch
size; checksum bytes Parquet có thể khác vì row-group layout.

| Artifact local | Nội dung |
| --- | --- |
| core.parquet | Source raw, identity, các trường core/inferred/flags |
| core_quarantine.parquet | Source raw +identity+reason, đủ schema cả khi rỗng |
| manifest.json | Revision/provenance/license, N/SHA, schemas, version/asset hashes, content digest, checksums, thời gian/RAM |
| core_quality_report.json | Counts/status/flags/inference/comparison, changed fields, metrics theo năm |
| quality_review_samples.json | Mẫu vấn đề; giữ toàn bộ nhóm wrong-field position/Kỹ sư tối đa 48/32 trong tập core |
| tune_* / holdout_*.jsonl | Samples accepted/review theo thuộc tính; để gán nhãn, chưa phải ground truth |

Denominator profile raw=N_input; normalization=N_core; inference=N_eligible
requirements trong core. Claim counts khác job counts; flags có thể overlap.
Samples deterministic theo hash, nhóm trùng requirements ở cùng split; tối đa
200 accepted claims/thuộc tính ở holdout, 20 cho các nhóm khác. Không tự coi
mẫu phân tầng/dedup đại diện mọi job hoặc report recall khi chưa có nhãn độc lập.

Manifest ghi `semantic_validation=pending_independent_review`: unit tests/full
run không thay đánh giá nghĩa dữ liệu. Annotation và báo cáo kiểm định sau
run nằm ngoài Git; khóa rule trước đánh giá, không retune rồi gọi cùng mẫu là
holdout độc lập. Chưa dùng inferred cho BI/publish S6 trước kiểm định phù hợp.
Tên artifact `holdout_*` chỉ là split ban đầu. Nếu mẫu đã được đọc để sửa rule,
phải ghi nhận trong báo cáo review và chọn phần chưa dùng/tập độc lập mới cho
gate chính thức; không suy precision/recall từ việc test regression đạt.

Vòng 1 dùng hai reviewer AI độc lập, được chủ dự án đồng ý, không xem code
hoặc dự đoán: học vấn 176/200 (88%), kinh nghiệm 162/200 (81%), chưa đạt gate
95% mỗi thuộc tính. V2 sửa regression và áp dụng hai quyết định bằng cấp
trên. Vòng 2: học vấn 186/200 (93%), kinh nghiệm 180/200 (90%), vẫn chưa đạt.
Vòng 3 báo 186/200 (93%) cho cả hai thuộc tính, chưa đạt; nhãn/evaluation
chưa lưu bền đã mất sau restart, nên kết quả vòng này không thể tái chấm.
Blind samples/predictions/protocol đã sao lưu được giữ, không dựng lại nhãn.
V4 sửa thêm phạm vi ưu tiên, mixed bounds, student policy và điều kiện theo
toàn tài liệu.
Gate tiếp theo dùng 200 accepted claims/thuộc tính từ requirements chưa
từng dùng trong chẩn đoán hoặc bất kỳ nhóm mẫu vòng 1–3; giữ cả ca khó trong
mẫu số. Thêm 30 review và 30 no_claim chỉ phục vụ chẩn đoán, không đo recall.
Đây là kiểm định bằng AI trên distinct requirements, không phải nhãn do con
người xác nhận hay độ chính xác có trọng số theo số tin. Báo cáo từng vòng,
annotations, protocol và hashes được lưu ngoài Git; không ghi đè vòng thất bại.

Vòng 4: học vấn **193/200 (96,5%)**, kinh nghiệm **193/200 (96,5%)**,
đạt gate chung mỗi thuộc tính; loại 1.654 requirements từng dùng trước.
Vẫn có 7 bất đồng mỗi thuộc tính. Nhóm học vấn preferred chỉ đúng 1/5 mẫu,
chưa đủ căn cứ sử dụng riêng nhóm này cho BI; giữ evidence để review và
không đưa preferred vào summary bắt buộc. Required học vấn đúng 187/190;
required kinh nghiệm 112/117, preferred kinh nghiệm 52/54. Scope kinh nghiệm
và điều kiện nhiều nhánh/danh sách xa nhau còn có ca chưa phân giải đúng.
Diagnostic no_claim tìm thấy mention ở 7/30 học vấn và 5/30 kinh nghiệm;
không dùng các mẫu này để tính recall. S2 chưa publish inferred vào DB/BI.
Khi publish, cần đánh giá các giới hạn trên theo mục đích sử dụng; gate mẫu
không chứng minh mọi suy luận hoặc mọi context đều đúng.

## Tổ chức và kiểm thử

`src/job_warehouse/silver/`: models/text/categorical/experience/
requirements_attributes/core/schema/core_runner; CSV ở mappings được đóng
trong wheel/container. `.gitattributes` giữ nguyên bytes/CRLF của CSV mapping
để checksum assets tái lập qua checkout, vẫn kiểm tra whitespace khác.
Test S2 ở tests/warehouse/test_silver_core.py và
 test_silver_runner.py; core_labels.json chỉ là nhãn categorical ngắn phục vụ
regression, không chứa jobs/full texts/report thật. Các nhãn nguồn tham chiếu
artifact có attribution và license trong hợp đồng lịch sử.

Chạy pytest offline, Ruff format/check, mypy src và git diff --check. Test gồm
finite labels, cận/units/symbols/context, raw preservation, core/quarantine,
evidence serialization, empty schema, batch replay và crash/hash/schema gate.
Code/docs/tests có thể review trong Git; Parquet/report/annotation/thư mục kế
hoạch ở ngoài repository. Commit/push theo ủy quyền chủ dự án khi đạt gate;
S2 offline không cần Docker hoặc crawl.
