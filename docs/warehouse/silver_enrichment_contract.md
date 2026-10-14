# Silver enrichment — nghề và địa điểm lịch sử

> Trục ngành hiện hành dùng nhãn nguồn qua `silver industry`; xem
> [quyết định, vận hành và lưu vết](source_industry_operations.md).
> `occupation_*` và `scope_*` dưới đây là phân loại chức năng được giữ để
> đối chiếu, không thay `job_industry` và `industry_scope_*` hiện hành.

S3 đọc core S2 bất biến, tạo `enrichment.parquet` ngoài repository. Một dòng
enrichment tương ứng đúng một `record_key` core. Đây là artifact offline,
chưa phải bảng PostgreSQL hoặc dữ liệu đã công bố lên dashboard.

```bash
.venv/bin/job-warehouse silver enrich \
  --core /path/outside/repository/s2-core-run/core.parquet \
  --core-manifest /path/outside/repository/s2-core-run/manifest.json \
  --output-dir /path/outside/repository/s3-enrichment-run
```

CLI kiểm hash core với manifest, schema/asset/version S2, revision/SHA/số dòng
Bronze đã pin; đọc đủ core, kiểm khóa nguồn và đối soát readback đầu ra.
Output directory phải mới, ở ngoài checkout, kể cả khi chạy installed wheel.
Input, manifest và cấu hình được kiểm lại trước khi xuất atomic. Không gọi
crawler, geocoding, PostgreSQL, Airflow, hoặc sửa file S2/Bronze.

## Cột và grain

Schema Arrow có kiểu và nullable được xuất vào `schema.json` mỗi lượt chạy.
Các list luôn tồn tại, rỗng khi chưa có giá trị. Không lưu full description,
requirements hoặc benefits lần thứ hai; nối về core khi cần.

| Cột | Kiểu Arrow | Nullable | Ý nghĩa/quy tắc |
| --- | --- | --- | --- |
| record_key | string | Không | PK logic, duy nhất; FK logic về core.record_key, chưa có constraint DB |
| source_row_index | int64 | Không | Chỉ số vật lý nguồn, không phải số thứ tự output |
| source_dataset_id | int64 | Không | ID dataset; không phải ID website |
| source_content_hash | string | Không | Candidate hash từ S2, không chứng minh vacancy trùng |
| year_value | int16 | Không | Năm nguồn; không dựng ngày/tháng |
| job_title_clean | string | Không | Title S2 giữ nguyên để đối chiếu evidence |
| job_industry_clean | string | Có | NFC/entity/whitespace theo text normalizer S2; raw vẫn ở core |
| occupation_primary | string | Có | Một code nghề hoặc null khi chưa đủ căn cứ |
| occupation_status | string | Không | assigned / unresolved / needs_review / multiple_or_ambiguous |
| occupation_method | string | Không | title_rule / source_candidate / none |
| occupation_candidates, occupation_source_candidates | list<string> | Không | Tập candidate có thứ tự cố định; không coi mọi candidate là nghề chính |
| domains | list<string> | Không | Lĩnh vực được title/nhãn nguồn nhắc; không suy ngành pháp nhân công ty |
| occupation_flags | list<string> | Không | Override, ca tư vấn thiếu sales, nhãn ghép, title bị cắt… |
| occupation_evidence | list<struct> | Không | field, rule_id, value, start/end int32, text; slice đúng clean field |
| location_places | list<string> | Không | Code tên địa phương được nguồn nhắc, unique; review chỉ là candidate |
| location_status | string | Không | mapped_single / mapped_multiple / nationwide / remote / foreign / unknown / unmapped / needs_review |
| location_group | string | Không | Tỉnh/thành đơn, Nhiều địa điểm, hoặc nhãn trạng thái địa điểm |
| location_remote, location_nationwide | bool | Không | Qualifier nguồn; có thể tồn tại cùng danh sách tỉnh |
| location_foreign | list<string> | Không | Quốc gia nhận diện bằng danh sách hữu hạn, không tự đầy đủ mọi quốc gia |
| location_flags, location_evidence | list | Không | Cờ review/bằng chứng; field location_clean là biểu diễn ảo chuẩn hóa từ core.location, không lưu lại địa chỉ trong enrichment |
| location_address_links | list<struct> | Không | Q13: rule_id, place, partial_start/end, complete_start/end; offsets int32 trỏ về location_clean ảo, không chứa text địa chỉ |
| family_record_count | int64 | Không | Số core được gán primary family trong cả revision; null family = 0 |
| scope_500, scope_1000 | bool | Không | Count sau gộp nghĩa ≥500/≥1.000; false nếu chưa có primary |
| scope_reason | string | Không | eligible / below_family_threshold / occupation_unresolved |
| enrichment_version, taxonomy_version, location_version | string | Không | Version cùng hash asset trong manifest |

Khóa logical chưa thay FK/PK trong PostgreSQL. Manifest và `record_key` giúp
truy về revision/file Bronze và run S2. Row digest kiểm replay độc lập batch
size; hash Parquet kiểm artifact vật lý. Timestamp không nằm trong row digest.

## Nghề: chức năng trước, domain riêng

Danh mục chức năng, định nghĩa và exclusions ở
`silver/enrichment/mappings/families.csv`; alias chính xác, title rule và domain
rule là các CSV riêng. Đây là taxonomy đồ án, chưa phải ISCO chính thức.

1. NFC/whitespace/casefold chỉ dùng cho lookup alias; không bỏ dấu mọi title.
2. Rule title cụ thể có exclusions. Nếu có một family rõ, chọn primary và ghi
   flag khi khác source. Nhiều family hoặc tin liệt kê nhiều vị trí giữ review,
   không chọn phần đầu hoặc tách thành nhiều posting.
3. Q11: khi title chưa rõ, exact source alias chỉ tạo candidate và trạng thái
   review, primary vẫn null. Alias nguyên chuỗi được thử trước; nhãn ghép chỉ
   nhận thành phần đã có alias. Không chọn ngành nguồn làm nghề chính khi thiếu
   rule title cụ thể. Không fuzzy match tất cả keyword hoặc lấy nguồn đầu tiên.
4. “Bất động sản”, “dược phẩm”, “lao động phổ thông”, “chưa xác định” đơn lẻ
   không chứng minh một nghề. Domain không đủ để tạo primary.
5. Tư vấn tuyển sinh/tài chính/khóa học hoặc trình dược viên đơn lẻ giữ review;
   SALES cần rule title sales/kinh doanh/telesales rõ. Nhãn sales nguồn được giữ
   làm candidate; Q11 mới hơn không cho phép nhãn nguồn đơn lẻ tạo primary.
6. HSE/an toàn/môi trường thuộc SAFETY_ENVIRONMENT. Nông nghiệp và kỹ thuật
   thực phẩm riêng; không gộp khác nhiệm vụ chỉ để đạt 500.
7. Q12: HEALTHCARE mang tên “Y tế và thú y”, gồm bác sĩ/y tá thú y cả phòng khám
   hoặc chăm sóc sức khỏe vật nuôi. ANIMAL_HEALTH là domain riêng; bác sĩ thú y
   không tự thành AGRICULTURE chỉ vì làm trong trang trại. Kỹ sư chăn nuôi là
   nghề nông nghiệp; bán thuốc thú y có title bán hàng rõ là SALES.
8. Thiết kế/kỹ thuật chung, QA/QC chưa rõ đối tượng, chức năng phụ chưa phân giải
   giữ review. CNC vận hành/gia công khác lập trình phần mềm; PLC/servo điều
   khiển thiết bị thuộc ENGINEERING khi title có bằng chứng cụ thể.
9. Q15: nhiều chức danh cùng một family vẫn có primary chung và cờ
   `multiple_roles_same_family`; các family khác nhau hoặc phần chức danh chưa
   phân giải giữ review. Mỗi posting vẫn chỉ một dòng.
10. Q16: MARKETING_MEDIA gồm sáng tạo nội dung, biên tập và sản xuất video;
    DESIGN gồm thiết kế đồ họa/UI-UX/thời trang/bao bì. Tên lĩnh vực của sản
    phẩm/dịch vụ không tự thành nhiệm vụ marketing hoặc thiết kế.
11. Q17: phát triển thị trường thuộc SALES. Chuyên môn nông nghiệp ghi trong
    ngoặc không thay chức năng bán hàng; domain nông nghiệp vẫn được giữ.
    Nghiên cứu thị trường khác phát triển thị trường.

“Giờ/làm hành chính”, “biết lái xe”, “mảng truyền thông” là bối cảnh, không tự
tạo nghề. Hỗ trợ thanh toán chung chưa rõ nghiệp vụ giữ review; khoản vay/thu
hồi nợ rõ có rule riêng. Công nhân chưa rõ loại công việc không tự là sản xuất.

Q18: tư vấn chung đi kèm CSKH rõ vẫn CUSTOMER_SERVICE, kèm cờ phần tư vấn
chưa xác định; các tư vấn chuyên biệt Q6 chưa rõ tiếp tục review. Q19: dược sĩ
bán thuốc tại nhà thuốc là HEALTHCARE; nhân viên bán thuốc không có vai trò
dược sĩ là SALES; sales/kinh doanh thuốc rõ là SALES. Q20: tuyển dụng/nhân sự
kèm đào tạo nhân viên thuộc HR_ADMIN; giảng dạy/chuyên môn rõ thuộc EDUCATION,
đào tạo chung chưa rõ không tự thành giáo dục. Rule exclusions áp trong mệnh
đề chức danh, không làm biến mất vai trò khác sau dấu phân cách. “Không sales”
không phải vai trò sales; tên phòng ban/sản phẩm không phải chức năng của vị trí.

| Trước | Sau dự kiến theo rule; chưa thay kiểm định độc lập |
| --- | --- |
| Sales Manager (ERP), nguồn IT phần mềm | SALES; domain SOFTWARE; source candidate IT_DATA; override có evidence |
| Software Tester, nguồn QA-QC/Thẩm định/Giám định | IT_DATA; không thành QC nhà máy |
| Kế toán bán hàng / cửa hàng | ACCOUNTING; từ bán hàng không biến nghề thành SALES |
| Trình dược viên, nguồn Y tế - Dược | primary=null, needs_review; domain HEALTH_PHARMA |
| Kỹ sư HSE, nguồn Chưa xác định | SAFETY_ENVIRONMENT từ title |
| Title liệt kê developer và kế toán | primary=null; giữ candidate, không nhân dòng |

Ngưỡng ≥500 toàn revision 2022–2026 là mặc định; báo ≥1.000 để so sánh.
Nhóm ít mẫu hoặc unresolved vẫn có một dòng enrichment và core nguyên vẹn.
Duplicate policy giữ `retain_and_flag`. Report representative exact-content
candidates chỉ là sensitivity, không tự xóa hoặc gọi là vacancy duy nhất.
Điều kiện đủ mẫu từng năm và coverage năm là gate riêng chưa áp ở S3.

Q27: chức danh chung có thể nhận chuyên môn được nêu rõ trong cùng title,
khi không có chuyên môn mâu thuẫn; không bù bằng nhãn ngành nguồn. Ví dụ
“Kỹ thuật viên – Kỹ sư xây dựng” thuộc CONSTRUCTION; nhiều chức danh rõ
cùng family vẫn một primary, kèm cờ nhiều vai trò/chuyên môn chung.
Q28: kỹ thuật máy tính, mạng và camera cùng ngữ cảnh hạ tầng máy tính thuộc
IT_DATA; camera hoặc bảo trì cáp mạng đứng riêng chưa đủ căn cứ thì review.
Q29: tạp vụ, vệ sinh công nghiệp, housekeeping và vệ sinh buồng phòng khách
sạn thuộc CLEANING. Bếp/phục vụ/vận hành khách sạn giữ HOSPITALITY.

Q30: bảo trì chưa nêu thiết bị hoặc chuyên môn rõ giữ `primary=null`,
`needs_review`, cờ `maintenance_object_not_resolved` và evidence của phần
title chưa rõ. Lương, tên nhà máy và nhãn nguồn không đủ để gán ENGINEERING.
“Bảo trì máy sản xuất” có thiết bị rõ nên ENGINEERING; chức danh chuyên môn
rõ cùng title có thể cung cấp ngữ cảnh theo Q27. Bảo trì CNTT/xây dựng không
trở thành kỹ thuật thiết bị chỉ vì có từ bảo trì.
Q31: kỹ sư cơ điện kèm nhiệm vụ hồ sơ thanh toán/quyết toán giữ review khi
chưa rõ chức năng thực tế; không suy ACCOUNTING chỉ từ từ thanh toán.

Taxonomy v7 có 23 nhóm. Tên mới dùng cụm từ bao quát, không nối các nhãn
nguồn bằng dấu `/`; raw và nhãn nguồn không bị viết lại. Định nghĩa/exclusions
và code ổn định nằm trong [families.csv](../../src/job_warehouse/silver/enrichment/mappings/families.csv).

| Code | Tên nhóm | Code | Tên nhóm |
| --- | --- | --- | --- |
| IT_DATA | Công nghệ thông tin | SALES | Kinh doanh |
| CUSTOMER_SERVICE | Chăm sóc khách hàng | MARKETING_MEDIA | Marketing truyền thông |
| ACCOUNTING | Kế toán kiểm toán | FINANCE | Tài chính ngân hàng |
| HR_ADMIN | Hành chính nhân sự | LOGISTICS | Hậu cần vận tải |
| ENGINEERING | Kỹ thuật thiết bị | MANUFACTURING | Sản xuất công nghiệp |
| CONSTRUCTION | Xây dựng kiến trúc | HEALTHCARE | Y tế thú y |
| EDUCATION | Giáo dục đào tạo | DESIGN | Thiết kế sáng tạo |
| HOSPITALITY | Dịch vụ hiếu khách | RETAIL | Vận hành bán lẻ |
| LEGAL | Pháp lý tuân thủ | LANGUAGE | Biên phiên dịch |
| AGRICULTURE | Nông lâm ngư nghiệp | FOOD_TECH | Công nghệ thực phẩm |
| SAFETY_ENVIRONMENT | An toàn môi trường | SECURITY | An ninh bảo vệ |
| CLEANING | Dịch vụ vệ sinh | | |

Tham khảo cấu trúc ba cấp nghề của [TopCV](https://tuyendung.topcv.vn/help/huong-dan-su-dung/dang-tin-tuyen-dung-mien-phi/)
và [danh mục CareerViet](https://careerviet.vn/tim-viec-lam.html), đối chiếu
nhóm rộng trong [công bố VietnamWorks](https://www.linkedin.com/posts/vietnamworks_activity-7459458365467828224-FbYv)
và [báo cáo Vieclam24h](https://vccivungtau.vn/wp-content/uploads/2025/08/Bao-cao-thi-truong-lao-dong-Q2.2025_Vieclam24h.pdf).
Đây là taxonomy chức năng của đồ án; không gọi là danh mục chính thức chung
của bốn website. Trang chính VietnamWorks/Vieclam24h trả 403 khi đối chiếu;
không kiểm chứng được toàn bộ bộ lọc hiện tại của hai trang này. Giáo dục
bao gồm hỗ trợ học vụ/lớp học rõ; đào tạo nhân viên đi cùng nhân sự thuộc HR.

## Địa điểm: tên nguồn nhắc, không suy địa giới

Danh mục tên nguồn và alias hữu hạn nằm trong places/place_rules CSV.
Không quy đổi Bà Rịa - Vũng Tàu thành Hồ Chí Minh, không dùng year để suy ngày
chuyển địa giới. “Huế, Thừa Thiên Huế” là cấu trúc city + tỉnh nguồn được owner
Q9 chốt thành một tỉnh Thừa Thiên Huế; “Huế” đơn lẻ giữ tên Huế. Hai tên xuất
hiện tách biệt ngoài cấu trúc này vẫn review, chưa có crosswalk địa giới.

- Longest match với ranh giới từ; bỏ phần tên nhỏ nằm trong match lớn. Không
  split mọi dấu phẩy/gạch ngang thành tỉnh. Lặp alias cùng tỉnh dedup trong row.
- “Hà Nội; Hồ Chí Minh” có hai labels, group Nhiều địa điểm. Một tin vẫn một
  dòng; lọc province bằng membership/EXISTS và đếm record_key. Nhóm theo tỉnh
  chồng lấn, không cộng cột tỉnh để lấy tổng tin.
- Remote/nationwide giữ qualifier và labels nhắc kèm. Group trạng thái này
  khác group nhiều tỉnh thông thường; remote không tự có tỉnh.
- Q32: với một địa chỉ đầy đủ rõ và nhãn tỉnh lặp bao ngoài mâu thuẫn, chọn
  tỉnh được ghi trong địa chỉ đầy đủ. Giữ evidence nhãn ngoài và cờ bất đồng;
  không chọn một tỉnh từ danh sách nhiều địa chỉ/văn phòng.
- Q33: giữ đủ tỉnh/thành được đề cập, kể cả văn phòng/chi nhánh; loại lặp,
  không review chỉ vì chưa rõ văn phòng tuyển dụng. Labels là tỉnh được đề cập
  trong location, không chứng minh tất cả địa chỉ là nơi đang tuyển dụng.
- Q34: có tỉnh rõ thì vẫn dùng tỉnh đó dù phần còn lại chưa map hoặc chỉ ghi
  các tỉnh lân cận. Giữ `province_list_incomplete`, không tự gán tỉnh cho phần
  chưa rõ và không coi tập labels là danh sách địa điểm đầy đủ.
- `mapped_single`/`mapped_multiple` mô tả số labels đã nhận diện, không bảo
  đảm đã nhận diện mọi phần địa chỉ. Nhắc nơi nước ngoài không loại các tỉnh
  Việt Nam đã rõ; quốc gia không được đưa vào tập labels tỉnh/thành.
- Q35: một tỉnh Việt Nam rõ trong cùng phần địa chỉ được ưu tiên hơn nhãn
  tiếng Anh Foreign bao ngoài. Bỏ UNSPECIFIED khỏi kết quả quốc gia, giữ
  evidence/cờ bất đồng. Không bỏ quốc gia cụ thể hoặc phần địa chỉ nước ngoài
  riêng biệt. Bằng chứng Foreign cũ không bị sửa thành bằng chứng tỉnh.
- Q36: cùng location có cả Huế và Thừa Thiên Huế thì giữ một THUA_THIEN_HUE,
  kèm cờ gộp tên; Huế đứng riêng giữ HUE. Giữ các tỉnh khác, không quy đổi toàn
  bộ tỉnh lịch sử theo địa giới hiện tại.
- Q37: giữ đủ tỉnh Việt Nam để lọc/thống kê, quốc gia cụ thể hoặc UNSPECIFIED
  lưu ở `location_foreign`, thêm `domestic_and_foreign_locations_mentioned`.
  Không needs_review chỉ vì cùng nhắc trong nước/nước ngoài. Mixed location
  có status mapped_multiple, còn remote/nationwide vẫn theo mode đã ghi nhận.
  Cờ nhãn Foreign mâu thuẫn cũ là thông tin chất lượng, không loại dòng.
- Q10: đầu ra chỉ tỉnh/thành, không địa chỉ hoặc dimension huyện/xã. Địa danh
  cấp dưới có thể làm input lookup bảng locality_rules, kèm reference_url/basis
  và evidence parent.*. Chỉ suy tỉnh cho đoạn chưa nhắc tỉnh trực tiếp; tên trùng
  hoặc chưa có rule rõ tiếp tục unmapped/review. Tên tỉnh trực tiếp ưu tiên hơn
  parent reference cũ, không tự đổi Ninh Bình thành Hà Nam cho “Phủ Lý, Ninh Bình”.
- Địa chỉ chi tiết chỉ ở core/Bronze bất biến; S3 kiểm evidence trên text transient
  chuẩn hóa từ core.location rồi bỏ text đó trước khi ghi file. Audit dựng lại
  cùng normalizer S2 và offsets; không lưu thêm một bản địa chỉ trong enrichment.
- Q13: một phần thiếu tỉnh chỉ nhận tỉnh từ bản đầy đủ khi phần này chứa số
  nhà/tên đường và khớp nguyên phần đầu địa chỉ đầy đủ, ranh giới dấu phẩy,
  không có tỉnh/country mâu thuẫn. Chỉ so exact-prefix sau normalize/casefold;
  không fuzzy hoặc truyền tỉnh giữa hai địa chỉ khác nhau. Lưu cờ suy từ địa
  chỉ lặp và offsets của hai phần trong `location_address_links`; tỉnh có
  evidence trên bản đầy đủ. Không sao chép chuỗi địa chỉ vào link.
- Q14: Việt Nam/Vietnam đơn lẻ là unmapped (có thông tin nhưng chưa rõ tỉnh),
  không unknown hoặc nationwide. Online trong tên tòa nhà không remote;
  tên đường/phường có từ trùng tỉnh, tên KCN có quốc gia không là nơi tuyển dụng.
- Q21 mở rộng proof bằng normalizer viết tắt hữu hạn P./Q./QL/số nhà, số nhà
  và tên đường phải cùng khóa rõ, các đơn vị cấp dưới cùng được ghi phải khớp.
  Tầng/khu phố bổ sung không tự đổi địa chỉ; tên địa danh chưa gán loại trong
  bản ngắn phải có trong bản đầy đủ. Không fuzzy/khử dấu/geocoding. Link mang
  rule_id exact_prefix hoặc structured, không chứa chuỗi địa chỉ.
- Q22 đã được Q33 thay thế: danh sách văn phòng giữ các tỉnh được đề cập,
  kèm `location_mentions_offices_not_confirmed_hiring_sites`; không khẳng định
  mọi văn phòng đang tuyển. Tên bến xe/địa danh làm mốc cần mapping có nguồn;
  chưa xác định được tỉnh và không còn thông tin khác thì unmapped.
- Q23: chủ dự án cho phép lấy tỉnh được ghi như địa bàn trong tên cơ sở ở
  `location`, như VSIP Bắc Ninh, Big C Đồng Nai hoặc Becamex Bình Dương.
  Giữ evidence và cờ `province_mentioned_in_facility_name`. Không dùng
  `company_name`, không coi tên đường hoặc quốc gia trong tên thương hiệu là
  nơi tuyển dụng. Tên tỉnh nằm giữa một tên thương hiệu mơ hồ vẫn cần ngữ cảnh.
- Q25: nếu các phần địa chỉ có bằng chứng tỉnh độc lập và cùng ra Hà Nội thì
  chỉ giữ Hà Nội. Khác phường/quận không khiến tin phải review, không cần giải
  thích nguyên nhân hoặc quy đổi địa giới. Proof Q13/Q21 chỉ phục vụ phần thiếu
  tỉnh; không truyền tỉnh giữa hai địa chỉ khác nhau.
- Q26: bổ sung bảng `address_reference_rules.csv` cho địa chỉ đã tra cứu được
  từ nguồn công khai. Bản đầu kiểm chứng 135 Cầu Giấy và 148 La Thành → Hà Nội
  bằng website của chính cơ sở, có reference_url/basis, version và evidence.
  Chỉ rule hữu hạn đã có nguồn mới chạy offline; không gọi Google/geocoder cho
  mỗi dòng. Không áp cho số nhà khác chỉ vì cùng tên đường, không bù từ tin
  khác; tỉnh nguồn ghi rõ ưu tiên hơn bảng tham chiếu. Địa chỉ chưa có ánh xạ
  vẫn unmapped/review và nằm trong backlog bổ sung, không khẳng định đã map hết.
- Location v8 có 72 rule cấp dưới và 8 địa chỉ/cơ sở tham chiếu hữu hạn.
  Nguồn đối chiếu gồm Sở QHKT TP.HCM, cổng thông tin địa phương và tài liệu
  công khai của Cục Quản lý Dược/CC1. Giữ tên tỉnh lịch sử theo reference khi
  nguồn thiếu tỉnh; tỉnh ghi trực tiếp ưu tiên hơn lookup. Google Maps không
  đọc được bằng công cụ tra cứu hiện tại; không ghi provenance là Google Maps.
  Các rule chỉ chạy offline, không gọi mạng theo từng bản ghi.
  Alias hữu hạn hỗ trợ Q.Tân Bình không có khoảng trắng và cách viết dấu gạch
  Bà Rịa – Vũng Tàu. Không tự map District Tan Phu/Binh Tan: District tiếng Anh
  có thể là quận hoặc huyện ở tỉnh khác, cần địa chỉ/ngữ cảnh đã xác minh.
- Không lấy tên tỉnh trong title/company để bù location. Không coi danh sách tuyển dụng là
  danh mục địa giới pháp lý hiện hành hoặc đồng nhất polygon qua các năm.
- Q38: tỉnh rõ hoặc parent cấp dưới đã kiểm chứng trong cùng địa chỉ ưu tiên
  hơn tên tỉnh nằm trong tên tòa nhà/thương hiệu. Tòa tháp Hòa Bình ở Cầu Giấy
  ra Hà Nội; Coopmart Hòa Bình kèm TpHCM ra Hồ Chí Minh. Giữ evidence tên cơ
  sở và cờ override. Cơ sở chỉ ghi locality, không có địa chỉ mâu thuẫn, vẫn Q23.
- Q39: nhận alias không dấu hữu hạn của các địa danh đã có reference, Biên Hoà
  là biến thể Biên Hòa. `QUÂN BÌNH TÂN` và `Qq11` chỉ suy Hồ Chí Minh khi
  có ngữ cảnh số nhà/tên đường; giữ offsets trên text nguồn, không fuzzy chung.
- Q40: Hà Đông/Thanh Xuân thiếu marker có thể suy Hà Nội trong địa chỉ số
  nhà/tên đường rõ; tên mơ hồ đứng riêng vẫn chưa map. Location v11 có 77 rule
  parent và 10 reference địa chỉ/cơ sở, thêm Hồ Gươm Plaza + 102 Trần Phú và
  Vinhomes Green Bay + 7 Đại lộ Thăng Long theo nguồn công khai đã kiểm tra.
- Q41: tên cơ sở khớp rõ lặp ở phần thiếu tỉnh không sinh thêm tỉnh từ tên
  cơ sở khi phần đầy đủ có địa lý rõ và không có bằng chứng tỉnh độc lập
  mâu thuẫn. KCN Hòa Bình/tòa nhà Hòa Bình giữ như tên cơ sở, không thêm
  tỉnh Hòa Bình; không tạo proof hai phần là cùng địa chỉ hoặc truyền tỉnh.
  Tỉnh Hòa Bình được ghi độc lập ở phần khác vẫn giữ. Phần thiếu tỉnh có cờ.
- Q42: nguồn ghi rõ `Tỉnh Tây Ninh (Long An cũ)` thì đầu ra chỉ Tây Ninh,
  Long An lưu trong evidence `historical_name.*`. Long An được ghi như địa
  điểm độc lập ở phần khác vẫn giữ; không dùng rule này quy đổi các tin khác.
- Q43: danh sách đường của ID590302 lấy Hồ Chí Minh từ địa chỉ Thới An,
  Quận 12; Hậu Giang/phường 6 trong danh sách đường không tạo tỉnh Hậu Giang.
  Tên tỉnh Hậu Giang đứng riêng hoặc có marker tỉnh vẫn giữ.
- Q44 đã chốt: nhãn bao ngoài lặp mâu thuẫn với các địa chỉ bên trong đều có
  cùng tỉnh rõ thì chỉ lấy tỉnh bên trong. Các địa chỉ thuộc tỉnh khác nhau
  vẫn giữ đủ; phần không xác định tỉnh không tự nhận tỉnh từ phần khác.

## Kiểm định và giới hạn

Địa điểm location v8 (run-v13) đã đối soát kỹ thuật đủ 606.857 dòng.
Vòng AI mù 6 khớp tuple/tập tỉnh 251/268 (93,66%), status 253/268 (94,40%);
chưa đạt gate 95%. Các nhóm wrapper đã xử lý, office và partial-list khớp
25/25, 25/25 và 35/35; nhiều địa điểm chỉ 35/45, unmapped 39/45.
Mẫu không có foreign/remote/nationwide mới và một mẫu mỗi tỉnh, nên không
kết luận chất lượng các nhóm hiếm. Giữ nhãn/score cũ; bản v9 đã sửa tên đường,
wrapper và triển khai Q38–Q40. Các vòng mới được báo riêng dưới đây.
Nghề v8 không đổi; occupation08 chỉ tái dùng với proof asset/toàn digest.

Location v9 vòng 7 đạt tổng thể 309/322 (95,96%), status 310/322 (96,27%),
nhưng tên cơ sở chỉ 20/30 (66,67%), nhiều địa điểm 42/45 (93,33%). Không gọi
nhóm yếu đã ổn. V10 sửa Q41–Q42, wrapper bị nhận nhầm là tên cơ sở, địa chỉ
liền nhau và tên khu phố/công trình. Vòng 8 khớp 357/374 (95,45%) tổng thể,
nhưng quan hệ tên cũ chỉ 6/17, nên tiếp tục sửa v11. Giữ score/nhãn cũ.

Location v11/run-v18 audit đủ 606.857 dòng. Vòng 9 khớp 292/300 tuple
(97,33%) và status, đạt gate tổng thể; nhiều tỉnh chỉ 40/45 (88,89%) nên còn
cần sửa. Ba nhóm tên cơ sở override/lặp và quan hệ tên cũ không còn mẫu thật
mới sau loại các nội dung đã xem. Chẩn đoán câu cấu trúc tổng hợp tách riêng
không cộng vào 300 mẫu thật và không chứng minh accuracy trên dữ liệu nguồn.

Location v12/pipeline v15/run-v19 đã audit đủ 606.857 dòng; Q44, địa chỉ
cũ/mới ghi rõ, số nhà chữ-số/lô LK và reference KCN Quế Võ đã triển khai.
Có 77 rule locality và 11 reference địa chỉ/cơ sở. Toàn bộ 1.202 test offline
đạt, 14 test PostgreSQL bỏ qua; wheel riêng qua 452 test enrichment.
Vòng AI mù 10 đã tiếp tục và hoàn tất 320 mẫu mới: khớp tuple/status 312/320
(97,5%), đạt gate tổng thể; nhiều tỉnh 65/70 (92,86%) và địa chỉ cũ 3/4
(75%) còn yếu. Reviewer gốc giữ nguyên 80 nhãn đầu và hoàn tất phần còn lại;
ghi chú xác nhận đánh giá mù thủ công. Lỗi capacity làm mất thông báo hoàn tất;
phiên AI khác chỉ kiểm schema/ID 320/320, không tạo nhãn. SHA output khóa trước
chấm. Nhãn/score v12 giữ nguyên, các ca lỗi rõ là tuning cho v13.
Chẩn đoán tổng hợp Q42 của v11 khớp 40/40, báo riêng; không thay mẫu thật
của v12 và không cộng vào N=320. Scorer tổng hợp có sửa tương thích metadata
stratum/record_key, giữ scorer/freeze cũ và bản giải thích sửa schema.

Location v13/pipeline v16 sửa các ca rõ: parent của địa chỉ số nhà khác
trong danh sách thiếu dấu phân cách; tên xã lặp trong cùng địa chỉ có bằng
chứng số nhà/đường; phường Bình Thuận trong địa chỉ Quận 7 có reference;
không ghép Ninh Thuận qua ranh giới Bắc Ninh/Thuận Thành; KDC có địa lý rõ;
hậu tố số nhà Bis/Ter; marker huyện sau mã bưu chính. Q45 đã chốt: phần địa
chỉ cũ lặp chỉ gộp khi số nhà/đường và danh tính KCN khớp địa chỉ mới có
quan hệ cũ nguồn ghi, các đơn vị cũ được cả hai bên cung cấp phải khớp.
Khác số nhà/đường/KCN/phường hoặc tỉnh cũ độc lập vẫn giữ. KCN/khu công
nghiệp và tên Việt Nam-Singapore/VSIP cùng suffix là alias hữu hạn.
Đầu ra chỉ tỉnh/thành, phần cũ giữ evidence; không đổi địa giới các tin khác.
Run-v20 audit đủ 606.857 dòng, còn 17.768 unmapped. Vòng AI thật 11 có
318 mẫu mới đã khớp 310/318 tuple (97,48%), status 311/318 (97,80%),
tập tỉnh 312/318; nhóm nhiều địa điểm 62/70 (88,57%) còn yếu. Bộ 32
câu thử tổng hợp Q45 khớp 32/32, báo riêng và không cộng vào N=318.
Reference locality có 78 rule, địa chỉ có 11 rule.

Location v14/pipeline v19 sửa bảy ca rõ của vòng11 và Q46 đã chốt:
cùng lô đất/KCN khớp rõ, nhãn nhà máy Hải Dương không sinh tỉnh thứ hai
khi phần đầy đủ ghi TP Hải Phòng; giữ nhãn nhà máy trong evidence.
Khác lô/KCN hoặc tỉnh độc lập ghi rõ vẫn giữ đủ. Run-v22 đã audit đủ606.857
dòng, còn17.759 unmapped. Vòng AI mù12 có318mẫu mới: tuple310/318
(97,48%), status313/318(98,43%); nhiều địa điểm67/70(95,71%).
Gate tổng thể đạt, còn8bất đồng, tên cơ sở0/1 và cùng lô/KCN1/1 là N nhỏ.
Không sửa nhãn/score cũ hoặc diễn giải đây là accuracy toànfile. Những ca
nhận nhầm tên phường/tỉnh, danh sách địa chỉ không phân cách và alias còn
thiếu được lưu backlog; chưa bảo đảm mọi rule hoặc geocode mọi địa chỉ.

Q47 được chủ dự án điều chỉnh: **chưa thêm cột địa giới sau sáp nhập**.
Chỉ trích và chuẩn hóa tỉnh/thành theo tên trong nguồn, gồm các tên cũ như
Hải Dương, Bình Dương, Bà Rịa - Vũng Tàu. Nhiều tỉnh giữ đủ, unique, không
đổi year/ngày đăng; không tự quy đổi sang Hải Phòng/Hồ Chí Minh.
Văn bản địa giới có thể giúp đối chiếu một địa chỉ cũ/mới rõ, theo quyết định
cụ thể Q42/Q45/Q46; không biến thành phép đổi toàn bộ dữ liệu. Một dòng
vẫn một record_key, không lưu địa chỉ/quận/huyện như chiều phân tích S3.

Test offline kiểm boundary, conflict, grain, threshold, SHA/schema, evidence,
replay và publication lỗi. Chạy toàn core kiểm kỹ thuật; chưa chứng minh độ
chính xác ngữ nghĩa. Manifest mới luôn ghi `pending_independent_review`.

Kiểm định S3 có hai trợ lý AI được chủ dự án cho phép. Reviewer xem source và
định nghĩa/chính sách, không xem code/dự đoán. Mẫu mới loại nội dung đã dùng
phân tích/tuning, cấu hình và dự đoán khóa trước nhãn; báo AI annotation thay
human ground truth. Nếu sửa sau holdout, cần holdout mới cho version mới.
Vòng nghề đầu chưa đạt (336/420, 80%); source fallback 33/82 (40,24%) dẫn đến
Q11 giữ source làm candidate. Vòng này là tuning cho version 2, không được gọi
là kết quả kiểm định độc lập của code đã sửa. Artefact báo cáo thật ở ngoài Git.
Mapping/dự đoán vòng đầu có trước reviewer; receipt/scorer tạo sau khi reviewer
bắt đầu nhãn, trước khi parent đọc nhãn. Protocol ghi đúng thời điểm này.

Vòng nghề 2 cũng chưa đạt (362/420, 86,19%); địa điểm vòng 1 chưa đạt
(227/274 tuple, 82,85%). Hai vòng này đã khóa scorer trước reviewer và là tuning
cho version 3 cùng Q13–Q17. Nhãn cũ và điểm cũ giữ nguyên. Version mới cần mẫu
mới loại mọi đơn vị title/location và nhóm nội dung đã dùng để tuning.

Vòng nghề 3 đạt 397/420 (94,52%), vòng 4 đạt 391/420 (93,10%); địa điểm
vòng 2 đạt 263/293 tuple (89,76%), vòng 3 đạt 260/285 (91,23%). Tất cả đều
chưa đạt gate đã đặt. Nhãn/điểm cũ giữ nguyên, kể cả các ca chủ dự án đã chốt
chính sách khác sau đó. Version 5 dùng Q23–Q26 và sửa lỗi remote, quốc gia
trong tên cơ sở, nhận diện nhiều chức năng và matching tên đơn vị địa chỉ.
Kết quả cũ chỉ dùng tuning cho các version tiếp theo.

Vòng nghề 5 và 6 cùng đạt 396/420 (94,29%), chưa đạt gate. Vòng 6 đã lưu
raw nhãn trước sửa lỗi schema status cho 17 ca cùng family; primary không
đổi. Vòng 7 dùng taxonomy v7, Q27–Q29, mẫu mới 440 eligible (20 mỗi nhóm
đủ 500) và 60 diagnostic. Cấu hình, input, scorer và prediction khóa trước
reviewer; kết quả thật nằm trong báo cáo ngoài Git.

Vòng 7 đạt gate tổng thể 418/440 (95%), nhưng ENGINEERING 13/20 (65%),
CLEANING 17/20 (85%), AGRICULTURE 18/20 (90%). Diagnostic chỉ khớp primary
32/60, không tính vào benchmark; nhiều ca chưa gán còn thiếu coverage.
Kết quả này dẫn tới chốt Q30–Q31 và sửa ca nhiều chức năng trong v8; score
v7 không áp cho v8. Vòng 7 đạt gate tổng thể, nhưng các subgroup yếu dẫn tới
việc sửa tiếp; không ghi vòng này là thất bại gate tổng thể.

V8 đã chạy và đối soát đủ 606.857 dòng core. Nghề vòng 8 có 500 nhãn AI mù,
gồm 440 benchmark và 60 diagnostic; khớp primary **430/440 (97,73%)**, đạt
gate kế hoạch. ENGINEERING/CLEANING đều 20/20, AGRICULTURE 19/20.
MANUFACTURING chỉ 18/20 (90%); còn ca nhiều chức năng cần review. Diagnostic
khớp 29/60, chưa phải benchmark recall hoặc bảo đảm chất lượng toàn bộ tin
chưa gán. Các ca bất đồng được lưu làm backlog riêng, không sửa nhãn sau
khi thấy score. FOOD_TECH không có mẫu mới sau loại title đã xem, chỉ có23
bản ghi và nằm ngoài scope500. Domains chưa có kiểm định độc lập.

Đây là phần nghề S3 offline đã đạt gate tổng thể, có giới hạn coverage/subgroup; chưa
publish database/BI. Mỗi nhóm benchmark chỉ20 mẫu, không phải bảo đảm độ
chính xác từng nghề. Thay mapping sau vòng8 phải dùng kiểm định mới.

Địa điểm vòng 4, location v5, đạt 252/262 tuple (96,18%) và 261/262 tập
labels (99,62%). Nhãn AI không phải human ground truth. Các nhóm nhiều
địa điểm/review/nationwide và tỉnh ít mẫu chưa có bảo đảm riêng. Location v5
không đổi khi nghề lên v7: dùng lại kiểm định chỉ sau khi đối soát hash các
thành phần địa điểm và digest dự đoán của toàn bộ population. Không gọi đây
là một vòng địa điểm mới. Manifest lúc tạo giữ pending_independent_review;
sidecar semantic_validation.json liên kết score/receipt/audit/SHA output.

Q24: dược sĩ kho/kho dược sĩ thuộc HEALTHCARE theo lựa chọn chủ dự án;
đây là chính sách nhóm nghề của đồ án, không khẳng định mọi tin dược sĩ kho
làm cùng nghiệp vụ với dược sĩ nhà thuốc. Các chức năng kho được nêu riêng
cùng chức năng khác vẫn tuân theo quy tắc nhiều family Q15.

Gate kế hoạch: nghề ≥95% trong mẫu phân tầng N≥max(300,20×số family công bố);
địa điểm ≥95%, N≥200, so cả tập labels và status. Báo từng subgroup với N,
coverage/unresolved và giới hạn; overall pass không chứng minh mọi family.
Không publish PostgreSQL/BI hay chuyển S4 chỉ vì test kỹ thuật pass.

## Ánh xạ Excel do chủ dự án cung cấp

CLI `silver apply-location-map --base-run ... --mapping-xlsx ... --output-dir ...`
áp dụng vào run mới, không thay file cũ. Đọc workbook dưới dạng dữ liệu, không
thực thi công thức/macro/liên kết; khớp exact `location_raw`, kiểm count và
example_source_dataset_id. Sheet chưa xác định là danh sách quyết định của
chủ dự án, chuyển nhãn hiển thị sang “Chưa xác định”, status unknown và
location_places=[]; không đưa số điện thoại/địa chỉ nước ngoài vào mã tỉnh.

Đầu ra giữ schema S3 và thêm:

| Cột | Kiểu | Nullable | Quy tắc |
|---|---|---|---|
| location | string | Không | Tên tỉnh/thành, nhiều tỉnh nối `; `; trường chưa xác định là “Chưa xác định”; qualifiers theo group cũ |
| location_mapping_method | string | Không | owner_excel hoặc source_extractor |
| location_mapping_row | int32 | Có | Số dòng Excel cho địa chỉ đã nhập, null cho bản ghi không thuộc workbook |

Pipeline xuất mới là silver-enrichment-v20, location version có suffix
owner-location-map-v1; classifier nguồn gốc vẫn v14. Workbook snapshot,
CSV import, manifest/SHA và báo cáo được lưu ngoài repository. Các trường
nghề/năm/identity và địa điểm đã xác định trước đó giữ nguyên. Thông tin
bằng chứng nguồn cũ giữ lại để trace; nhãn workbook có method/row/hash riêng,
không giả làm evidence trích text hay tự kế thừa gate AI vòng12 cho nhãn mới.

File chủ dự án hiện có13.614 chuỗi/17.759records:13.417chuỗi gán tỉnh thành,
197chuỗi còn lại đại diện277records; ngoài workbook có9records unknown cũ.
Không xóa bản ghi; không thêm cột tỉnh/thành sau sáp nhập.
