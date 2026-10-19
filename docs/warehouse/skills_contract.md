# S5 — Trích kỹ năng từ requirements

Trạng thái: đã kiểm định offline bản thí điểm ba ngành; chưa nạp PostgreSQL.
Code tại `src/job_warehouse/skills/`, độc lập crawler và extractor S2.

## Mở rộng theo đợt

Đợt `sales_customer_service` chọn đúng năm nhãn nguồn: Bán hàng - Kinh doanh,
Chăm sóc khách hàng, Nhân viên kinh doanh, Phát triển thị trường, Bất động sản.
Nhãn ngành chỉ chọn phạm vi; không làm bằng chứng và không được sửa lại.
Gói `mappings_sales/` kế thừa mã khái niệm cũ, bổ sung nghiệp vụ bán hàng/CSKH,
có phiên bản và kiểm định riêng. Không bật toàn bộ catalogue 602 tự động.
Lệnh `silver skills` không có `--batch` vẫn dùng ba ngành/bộ 96 như trước.

```bash
job-warehouse silver skills-batch-prepare \
  --batch sales_customer_service \
  --jobs-run /outside/repository/s4-run \
  --output-dir /outside/repository/new-batch-samples

job-warehouse silver skills \
  --batch sales_customer_service \
  --jobs-run /outside/repository/s4-run \
  --output-dir /outside/repository/new-batch-candidate

job-warehouse silver skills-batch-merge \
  --batch sales_customer_service \
  --candidate-run /outside/repository/new-batch-candidate \
  --baseline-run /outside/repository/accepted-s5-run \
  --gate /outside/repository/validated-batch-gate.json \
  --output-dir /outside/repository/new-merged-s5-run
```

Chuẩn bị mẫu mặc định 20 tune + 50 holdout/nhãn. Chia nhóm bằng NFC,
casefold và thu gọn khoảng trắng, chỉ để tách mẫu; requirements/evidence vẫn
nguyên văn. Loại toàn bộ nội dung đã có trong ba ngành thí điểm, kể cả bản
sao qua ngành. Khi sửa rule, API `prepare_batch` nhận `exclude_samples`,
`exclude_job_ids`, `sample_seed` để tạo vòng mới loại các nhóm đã dùng.
Thiết kế cân bằng năm và nhóm văn bản khác với lấy ngẫu nhiên theo từng tin;
không coi đây là loại hết các câu gần giống.

Hai cặp rõ và chưa rõ trong cùng tin được xử lý riêng. Kỹ năng mềm, ngành
học đứng riêng, sở thích, doanh số hoặc lời hứa đào tạo không tạo cặp.
Danh sách công cụ thiếu ngữ cảnh năng lực giữ chưa rõ; nhiệm vụ chuyên môn
cụ thể trong requirements có thể tạo cặp. Không suy nghiệp vụ bán hàng từ
việc chỉ dùng phần mềm quản lý bán hàng hoặc làm báo cáo doanh số.
Chủ dự án xác nhận: đầu mục kỹ năng rõ như "Vi tính văn phòng" có thể
làm ngữ cảnh chung cho danh sách công cụ dù không có từ "thành thạo"; câu "đã từng sử dụng
hoặc bán MISA/FAST" được lấy công cụ và giữ quan hệ lựa chọn, còn chỉ bán
phần mềm không tự chứng minh biết dùng. SAP là nhãn hệ sinh thái chung;
SAP BO/SuccessFactors được tính SAP, giữ sản phẩm trong bằng chứng và
không suy thêm skill ERP. Quyết định và ID/quote cụ thể nằm trong hồ sơ
ngoài Git, được gate khóa SHA; không sửa manifest các run đã tạo.

Merge yêu cầu gate theo từng nhãn (≥50 văn bản, có cặp dương, precision
≥95%, recall ≥80%), cùng SHA taxonomy/alias/policy/code và hồ sơ kiểm định.
Gate phải xuất phát từ đánh giá tham chiếu mù và đối chiếu ngữ nghĩa; JSON/SHA
chỉ kiểm tính nhất quán, không tự chứng minh chất lượng. Nhãn AI không được
gọi là nhãn con người. Điểm tính trong từ điển đã khóa, không đo mọi skill.
Gói/nhãn chưa đạt tiếp tục ở candidate, chưa nhập vào bản hiện hành.
Khi chỉ một phần đợt đạt, thêm `--industry 'Nhãn nguồn'` lặp lại cho từng
nhãn được nhận vào lệnh `silver skills`. Nhãn phải là tập con không trùng
trong đợt đã khai báo. Manifest ghi `processed_scope` và báo cáo ghi các
nhãn hoãn; merge đối chiếu gate đúng tập con đó, giữ nguyên trạng thái và
mọi cặp/evidence của các nhãn khác. Chưa đạt không thành "không có skill".
Chọn phạm vi không đổi `extract(text)`; nếu bổ sung cơ chế chọn tập con sau
khóa mẫu, phải giữ checksum extractor/alias/policy, lưu diff của phần điều
khiển và kiểm thử bảo toàn dữ liệu trước khi chạy.

Merge kiểm nguồn S4, tập ID/hash, tên chuẩn, bằng chứng/offset, số lượng,
đọc lại Parquet và bảo toàn các dòng cũ. Không ghi lại kết quả thí điểm bằng
rule mới; một đợt đã xử lý không bị ghi đè. Lệnh tạo run mới ngoài Git và
acceptance offline; việc cập nhật con trỏ vẫn cần kiểm tra báo cáo cuối.
Chưa publish PostgreSQL, không tự commit/push các thay đổi của đợt mới.

## Chốt phiên bản thí điểm

Chốt phiên bản là đóng băng đầu ra đã nhận cùng catalogue, policy và provenance;
không có nghĩa đã tìm hết kỹ năng hoặc đã xử lý mọi đề xuất. Hồ sơ chốt ngoài
repository gồm Parquet cặp tin–skill/evidence/status, snapshot từ điển, manifest
SHA, kết quả đối soát toàn file, số liệu theo ngành và danh sách hoãn xử lý.
Giữ nguyên manifest/bundle của các lượt cũ; bảng nguồn, crawler và PostgreSQL
không thay đổi. Con trỏ hiện hành ghi thêm đường dẫn receipt bản chốt.

Tách rõ hai lớp: bộ 96 khái niệm có kiểm định mẫu tự động và catalogue bổ sung
qua claim đã rà soát theo ID/hash. Không áp điểm precision/recall của bộ 96 cho
catalogue mở rộng, không trình bày các khái niệm bổ sung như đã được trích tự
động đồng đều trên mọi tin. Bản chạy mở rộng chưa đạt gate không được thay
bản đã nhận chỉ vì độ phủ hoặc số cặp lớn hơn.

Đề xuất AI chưa nghiệm thu, kể cả đề xuất có nhãn “lấy” từ AI trình duyệt,
giữ trong danh sách riêng với kết luận/bằng chứng gốc và lớp đối chiếu; chưa
tạo cặp nghiệp vụ. Các đối chiếu một phần không được gọi là hoàn thành toàn
tập. Quyết định mới về ngữ cảnh/nhãn được lưu cùng backlog và chỉ áp dụng
trong một phiên bản mới sau kiểm tra; không hồi tố điểm kiểm định cũ.

Giữ tin chưa nhận diện được kỹ năng và trạng thái kỹ thuật tương ứng; không
ép skill hoặc biến “chưa nhận diện” thành “không yêu cầu”. Báo cáo phạm vi có
requirements hữu ích, tin thiếu requirements và tin ngoài ngành riêng. Khi mở
rộng ngành, tạo phiên bản mới, so với bản đã đóng băng và kiểm định mẫu; không
cần đọc lại từng tin không khớp để tuyên bố hoàn tất một phiên bản thí điểm.

## Nhập kết quả rà soát kỹ năng

`silver skills-apply-review` nhập bundle có lưu vết và ba chế độ:
`held_out_review` (mặc định) áp dụng toàn tập `needs_review` của S5 gốc;
`no_match_proposals` áp dụng toàn tập `processed_no_match` sau khi đã hoàn
thành lượt held-out; `no_proposal_followup` nhập các đề xuất mới cho toàn tập
`review_no_proposal` sau lượt no-match đã hoàn tất. Các tin ngoài tập được
chọn giữ nguyên, kể cả tin đã có skill hoặc đang needs_review ở lượt trước.
Không tự mở rộng matcher toàn cục khi catalogue review có kỹ năng mới.

```bash
job-warehouse silver skills-apply-review \
  --jobs-run /outside/repository/s4-run \
  --baseline-run /outside/repository/accepted-s5-run \
  --review-bundle /outside/repository/curated-review-bundle \
  --output-dir /outside/repository/new-reviewed-s5-run
```

Bundle gồm `source.csv` (tổng hợp gốc), `details.csv` (đánh giá gốc),
`claims.csv` (lớp kết luận sau đối chiếu), `catalogue.csv`, `policy.json`
và `bundle.json` khóa SHA từng file, manifest/acceptance S5 gốc và phiên bản.
Giữ nguyên 96 khái niệm ban đầu trong catalogue; khái niệm mới chỉ có hiệu lực
với các claim được duyệt. Claim gốc định danh `csv:<số dòng gồm header>`;
claim bổ sung định danh `extra:...`. Mỗi claim giữ ID, nhãn/kết luận/trích dẫn
gốc, kết luận riêng `accept/reject/unclear`, mã/tên chuẩn, bằng chứng nguyên văn,
lý do, điều kiện và hash requirements. Phải đối soát đủ từng claim gốc,
ID/phân bố của hai CSV, mã/tên chuẩn và bằng chứng trước khi ghi output mới.

Với `kind=no_match_proposals`, `source.csv` là bản xuất đầy đủ tập chưa
khớp (`id`, `job_industry`, `year`, `requirements`); `details.csv` giữ nguyên
CSV đề xuất ba cột `id`, `tên kỹ năng đề xuất`, `trích dẫn nguyên văn làm bằng chứng`.
Không tạo nhãn âm giả cho tin không xuất hiện trong file đề xuất. Mỗi dòng
đề xuất giữ `source_decision=proposed`, phải có đúng một kết luận rà soát;
claim bổ sung lưu riêng. Tập ID đề xuất chỉ được là tập con của population
đã khóa, còn population phải khớp toàn bộ `processed_no_match` trong baseline.
Baseline cần manifest, `review_completion.json`, SHA technical audit và
bundle lượt trước; catalogue hiện hành được giữ nguyên khi thêm khái niệm.
Chế độ `no_proposal_followup` dùng cùng cấu trúc bundle đề xuất và kiểm
đủ mọi claim, nhưng khóa population là toàn tập `review_no_proposal` của
baseline hiện hành. Baseline phải có completion trạng thái
`reviewed_proposals_offline_not_db_published`, audit và bundle khớp SHA.
Mỗi đề xuất có kết luận riêng; cặp rõ được lấy dù cùng tin còn ca chưa rõ.
Tin chưa có đề xuất tiếp tục `review_no_proposal`, không thành nhãn âm.
Khi trích dẫn lặp nhiều lần, cột tùy chọn `evidence_start` chọn đúng lần xuất
hiện đã đối chiếu; importer kiểm slice nguyên văn trước khi lưu offsets. Bundle
cũ không có cột này giữ hành vi chọn lần xuất hiện đầu tiên.

`proposal_review.py` hỗ trợ đối chiếu lexical/ngữ cảnh từng đề xuất bằng
pattern hữu hạn: ngành học, đào tạo tương lai, phủ định và waiver kinh nghiệm
được xét tại skill cụ thể. Pattern và những kết luận AI/chủ dự án sau đối chiếu
nằm trong bundle ngoài Git. Chỉ có exact quote hoặc rule pass chưa chứng minh
ngữ nghĩa đúng; phải rà soát nhãn, ca rủi ro và những claim chưa đủ hỗ trợ.
Đây là hỗ trợ tuyển chọn đề xuất, không dùng để tự sinh skill toàn kho.

Một cặp tin–skill chỉ ghi một lần, nhiều bằng chứng được giữ riêng. Các skill
rõ của tin vẫn được nhập khi còn claim khác chưa rõ:

| Trạng thái sau rà soát | Ý nghĩa |
|---|---|
| `reviewed_match` | Có skill được lấy, không còn claim chưa rõ |
| `reviewed_partial_match` | Có skill được lấy, còn claim chưa rõ |
| `reviewed_no_match` | Không có skill được lấy trong phạm vi rà soát, không còn claim chưa rõ |
| `needs_review` | Chưa có skill được lấy và còn claim chưa rõ |
| `review_no_proposal` | Tin thuộc tập rà soát nhưng CSV bên ngoài không có đề xuất; không kết luận không có skill |

Evidence mới có context `reviewed_positive`, không suy thành bắt buộc; điều
kiện nằm trong bundle và được liên kết bằng `group_id=condition:<claim_id>`.
Evidence cũ được giữ nguyên. Output sao lưu cả bundle và manifest có provenance,
hash, số cặp, số claim, trạng thái, giới hạn; không ghi đè S4/S5 gốc, không nạp DB.

Bundle là dữ liệu đánh giá đã tuyển chọn, không phải nhãn đúng được bảo đảm bởi
CSV/SHA. Kiểm tra kỹ thuật xác nhận tính nhất quán và lưu vết; độ đúng ngữ nghĩa
phải được đánh giá riêng. Với file AI bên ngoài, ghi rõ phương pháp AI và các
quyết định của chủ dự án; không dùng precision/recall của bộ 96 kỹ năng cũ để
chứng nhận catalogue mở rộng, hoặc coi rà soát một tập là đầy đủ mọi skill.

## Đầu vào và phạm vi

Đọc `jobs_analysis.parquet` của S4 đã nghiệm thu offline. Trước khi chạy,
kiểm SHA Parquet, manifest, liên kết acceptance và báo cáo kiểm định S4;
kiểm revision Hugging Face, schema, số dòng và ID không lặp. Chỉ đọc
`id`, `job_industry`, `year`, `requirements`. Không sửa/ghi đè jobs S4.

Phạm vi đầu: Công nghệ thông tin, Kế toán / Kiểm toán, Marketing; dùng
đúng nhãn S3 hiện hành. Ngành chỉ chọn phạm vi xử lý, không là bằng chứng skill.
Ngoài phạm vi vẫn giữ jobs và một trạng thái kỹ năng cho từng ID.
Không tạo ngày/tháng từ year. Giữ revision, nguồn, giấy phép và ghi công S4.

Loại kỹ năng: chuyên môn, công cụ/công nghệ và ngoại ngữ; chưa trích kỹ năng
mềm, phẩm chất, tuổi/giới tính, bằng cấp hoặc số năm kinh nghiệm thành skill.
Không lấy title, description hay benefits để bù requirements thiếu.

## Chính sách được chủ dự án chọn ngày 17/10/2026

- Cặp dương gồm kỹ năng bắt buộc **hoặc ưu tiên**. Không gọi tất cả là bắt buộc.
- Cho phép suy ngoại ngữ từ chứng chỉ có bảng ánh xạ; lưu bằng chứng riêng,
  không tự suy điểm, mức thông thạo hay kỹ năng nghe/nói cụ thể.
- Đồng ý hai trợ lý AI gán nhãn mù độc lập, ghi rõ nhãn AI.
- Q6/Q10: Content Marketing gồm viết/biên tập và sản xuất nội dung hình ảnh,
  thiết kế banner/đồ họa, quay dựng video khi requirements có ngữ cảnh
  marketing rõ; không dùng title/nhãn ngành để tạo ngữ cảnh.
- Q7: digital được ghép vào Digital Marketing khi requirements có ngữ cảnh
  marketing rõ; không tự ghép digital products/devices/transformation.
- Q8: câu tin học văn phòng đã được duyệt ở ID 532645 là yêu cầu đào tạo
  trước; policy khóa hash toàn văn + skill + bằng chứng cho riêng trường hợp
  này. Các câu “sẽ được đào tạo sau khi nhận việc” vẫn là training/mentioned.
- Q9: “tiếng Trung (Anh)” có cả tiếng Anh; giữ quan hệ danh sách chưa rõ,
  không kết luận bắt buộc có cả hai.
- Q11: nhận Facebook Ads/TikTok Ads khi tin nêu kinh nghiệm 0–3 tháng và
  chấp nhận đào tạo nếu chưa có. Bảng nghiệp vụ chỉ lưu kỹ năng, không tách
  bắt buộc/ưu tiên. Bổ sung alias `FBads` và `FB Ads`; không vì quyết định này
  mà lấy mọi kỹ năng chỉ được nhắc trong chương trình đào tạo tương lai.

Ánh xạ chứng chỉ dự thảo: IELTS/TOEIC/TOEFL → Tiếng Anh;
HSK → Tiếng Trung; JLPT → Tiếng Nhật; TOPIK → Tiếng Hàn;
DELF/DALF → Tiếng Pháp. Chỉ áp dụng khi ngữ cảnh là điều kiện tuyển dụng
khẳng định/ưu tiên; nhắc “không yêu cầu IELTS” không tạo cặp Tiếng Anh.
Không tự suy ngoại ngữ từ tên bằng/chuyên ngành. Bảng hữu hạn này cần qua
kiểm định cùng matcher; chưa công bố mọi chứng chỉ/ngôn ngữ đã được hỗ trợ.

## Từ điển và thuật toán

`mappings/taxonomy.csv`: mã, tên chuẩn, nhóm và định nghĩa.
`mappings/aliases.csv`: cách viết → mã; mode literal, contextual, certificate
hoặc shared_language (tên ngôn ngữ có chung tiền tố tiếng).
`mappings/policy.json`: phiên bản, phạm vi và quyết định chủ dự án.
Đây là từ điển hữu hạn của dự án cho bản thí điểm, không phải ESCO/O*NET.

Dò alias literal bằng trie, chọn cụm dài trước ở cùng vị trí; kiểm ranh giới
trên chuỗi gốc. Casefold dùng để so khớp, có bảng ánh xạ về offsets Unicode
gốc kể cả ký tự biến thành nhiều ký tự sau casefold. Giữ C++/C#/.NET.
Không lấy Java trong JavaScript, SQL trong PostgreSQL/SQL Server,
React từ React Native hay GitHub từ GitHub Actions.
Hai khái niệm được nêu rõ có thể có evidence chồng nhau: “viết SEO” có
cả Content Marketing và SEO. Không dùng quy tắc loại span chồng nhau để
làm mất một kỹ năng rõ; các sản phẩm vẫn chặn khái niệm cha suy ngầm.

`requirements-skills-v4` / `pilot-skills-v5` và policy
`owner-skills-20261017-v4` đã được khóa trước vòng holdout bốn: 96 khái niệm,
294 alias. Vòng hai và ba chưa đạt recall Marketing, được giữ nguyên điểm.
Vòng bốn loại toàn bộ 990 văn bản đã dùng; không áp lại điểm cũ sau sửa
alias/rule. Snapshot và SHA trong hợp đồng kiểm định lưu ngoài Git.

Alias AI/PS/Pr chỉ nhận dạng công cụ trong ngữ cảnh phần mềm thiết kế/chỉnh
sửa hình ảnh; Pr còn cần ngữ cảnh video. AI hỗ trợ bán hàng và PR chung
không tự thành Illustrator/Premiere. Các cách viết Adobe Premier, After
effect, Ilustrator và GG ads được khai báo hữu hạn; không dùng fuzzy matching
để tự sửa mọi từ chưa biết.

Danh sách nền tảng có chung cụm quảng cáo được nhận theo cùng mệnh đề;
không truyền ý quảng cáo sang yêu cầu khác về mạng xã hội. Google Analytics
không tự tạo Google Ads. Cụm nội dung/fanpage được khai báo hữu hạn, chỉ
dùng ngữ cảnh trong requirements. Nghề nghiệp mong muốn, sở thích, KPI và
kiến thức về thị trường/sản phẩm ngoại ngữ không tự thành năng lực ứng viên.

Phân đoạn câu/mệnh đề, heading và dấu chuyển ý; phân loại required,
preferred, mentioned, negated, ambiguous. Có bằng chứng khẳng định và phủ
định mâu thuẫn cho cùng skill → review. Ca không xử lý rõ giữ lý do,
không tự chọn bằng chứng đầu tiên. Quy tắc ngữ cảnh có giới hạn; không coi
việc pass test tổng hợp là chứng minh chất lượng toàn dữ liệu.
Logic any_of chỉ cho “hoặc/or”; slash giữ listed_together_unspecified;
“ít nhất hai” giữ minimum_subset:2. Không gọi mọi phần của danh sách là
bắt buộc. Phủ định chứng chỉ không tự phủ định năng lực ngoại ngữ được nêu
riêng; evidence phân biệt chứng chỉ và ngôn ngữ trực tiếp.

Một tin nhắc skill nhiều lần vẫn một cặp, mọi đoạn khớp giữ ở evidence.
Text lặp có thể cache kết quả; không loại job lặp nội dung. Cache có giới hạn.

## Đầu ra và ý nghĩa trạng thái

| Artifact ngoài Git | Grain / vai trò |
|---|---|
| job_skill_match.parquet | Một cặp duy nhất `(job_id, skill_code)`; thêm `skill_name` chuẩn |
| job_skill_evidence.parquet | Các đoạn khớp, context, logic, rule, offsets, hash và versions |
| job_skill_status.parquet | Một dòng mỗi ID của toàn input |
| skill_review.csv | ID, lý do và requirements cần xem |
| skill_quality_report.json | Counts, coverage ngành×năm, skill counts, readback |
| taxonomy_snapshot/ | Đúng từ điển/policy đã dùng |
| manifest.json | SHA input/code/config/output, revision, phiên bản, thời gian |

Schema nghiệp vụ dự kiến: `job_id bigint`, `skill_code varchar`,
`skill_name varchar`; PK `(job_id, skill_code)`, FK sang `silver.jobs.id`.
S5 chưa tạo bảng SQL. Ngữ cảnh/evidence không thêm lại vào bảng nghiệp vụ.

| Trạng thái | Ý nghĩa |
|---|---|
| missing_requirements | Null thực |
| unusable_requirements | Chuỗi trống/placeholder hữu hạn, kể cả “Không” |
| out_of_scope | Có nội dung nhưng ngành chưa được hỗ trợ |
| processed_match | Xử lý xong, có cặp dương |
| processed_no_match | Xử lý xong, chưa khớp skill dương trong từ điển |
| needs_review | Mơ hồ/mâu thuẫn; giữ evidence, chưa đưa cặp dương của tin vào output |

Thứ tự: null/placeholder → ngoài scope → matcher. Báo scope-null riêng để
không nhầm thiếu requirements ngoài scope với coverage ba ngành. Lỗi kỹ
thuật làm run thất bại và dọn staging; không đổi lỗi thành no-match.
Output thư mục mới ngoài repo; staging đổi tên sau readback và kiểm input
không thay đổi. CLI không tự tạo acceptance/con trỏ nghiệm thu. Hồ sơ này
được bổ sung riêng sau khi kết quả kỹ thuật và kiểm định ngữ nghĩa đạt;
manifest/output gốc giữ nguyên trạng thái candidate tại thời điểm tạo.

## Lệnh chạy

```bash
job-warehouse silver skills-prepare \
  --jobs-run /path/outside/repo/accepted-s4-run \
  --output-dir /path/outside/repo/s5-preparation

job-warehouse silver skills \
  --jobs-run /path/outside/repo/accepted-s4-run \
  --output-dir /path/outside/repo/s5-candidate
```

Có thể chọn `--taxonomy-dir` để chạy đúng snapshot cũ; vẫn kiểm scope ba
ngành và cấu trúc taxonomy/policy. Cả hai lệnh mặc định batch 2.048 dòng.
Chạy offline, không gọi AI/network ở runtime, không cần Docker/PostgreSQL.

## Kiểm định và mẫu số

Preparation mặc định 30 tune + 100 holdout **văn bản khác nhau** mỗi ngành.
Chia theo SHA requirements trên cả ba ngành; không cho text trùng ở hai tập.
Chọn xác định, phân tầng đều theo năm; đây không phải mẫu ngẫu nhiên đơn
theo số job. Báo rõ trọng số/coverage, chưa suy điểm mẫu thành accuracy toàn kho.
Không cắt ngắn requirements khi gán nhãn. Nhãn tham chiếu phải đánh dấu đủ
mọi skill trong taxonomy, gồm văn bản không có skill, không chỉ duyệt prediction.

Hai AI đã đánh giá tập tune và đánh giá lại sau Q6–Q9; Q10 giải quyết ranh
giới sản xuất hình ảnh/video. Nhãn gốc giữ nguyên, quyết định mới lưu riêng.
Chưa dùng tune để kết luận đạt gate. Khóa taxonomy/guide/matcher rồi mới
đọc nhãn/prediction holdout; thay rule theo holdout phải kiểm định bằng mẫu mới.
Reference validator kiểm đủ mẫu, SHA, mã skill/context và bằng chứng nguyên văn.

Đo precision/recall/F1 cặp job–skill, theo từng ngành. Khi matcher abstain,
skill dương trong reference vẫn là FN; không bỏ các tin khó để nâng điểm.
Mục tiêu kế hoạch: precision ≥95%, recall ≥80% trong taxonomy đã khóa;
nhóm/ngành thiếu mẫu hoặc không đạt phải ghi rõ. Nhãn AI không phải nhãn người.

Ngày 17/10/2026, v8 đạt kiểm định vòng bốn trên 300 văn bản mới (100/ngành),
loại 990 văn bản tune/vòng trước theo SHA. Hai AI gán nhãn độc lập, trợ lý
đối chiếu bốn bất đồng trước khi chấm; giữ nguyên nhãn gốc và các vòng chưa
đạt. Các điểm dưới đây chỉ áp dụng cho cặp tin–skill trong từ điển đã khóa:

| Ngành | Precision | Recall |
|---|---:|---:|
| Công nghệ thông tin | 98,84% | 94,44% |
| Kế toán / Kiểm toán | 100% | 94,89% |
| Marketing | 96,77% | 84,27% |

Đầu ra: 139.708 cặp duy nhất của 54.062 tin; 581 tin review giữ riêng.
Chưa khẳng định chất lượng trên 31 nhãn ngành ngoài phạm vi, từng skill hiếm,
hoặc mọi mẫu câu chưa thấy. Tách mẫu theo SHA không loại hết các mẫu gần
trùng về diễn đạt. Các báo cáo SHA/nhãn/điểm thật lưu ngoài repository.
1.600 test offline đạt, 14 test PostgreSQL bỏ qua; full audit/replay đạt.

Prevalence = số job có cặp skill / (`processed_match` + `processed_no_match`)
dưới cùng bộ lọc. Báo thêm coverage trên 3 ngành và toàn input. No-match
không chứng minh job không cần kỹ năng. Không tính số pair thành số tin,
không nhân lương khi join skill. Với bảng 3 cột, dashboard chưa có sẵn bộ lọc
required/preferred hay trực tiếp/suy chứng chỉ; cần evidence nếu muốn tách.

## Kiểm tra trước commit

Test synthetic trong `tests/warehouse/test_skills_*.py`; pytest offline toàn
repo, Ruff format/check, mypy và `git diff --check`. Chạy candidate readback,
replay, đối soát population/PK/evidence và kiểm định ngữ nghĩa trước nghiệm thu.
Không commit Parquet, mẫu thật, nhãn AI hay báo cáo chứa requirements nguồn.
Chỉ commit/push khi chủ dự án yêu cầu.

## Chạy lại danh mục mở rộng

`mappings_expanded/` là phiên bản riêng của catalogue mở rộng từ 601 khái niệm đã tích lũy
qua hai lớp review, kèm alias hữu hạn và provenance. Không thay từ điển 96
của bản đã kiểm định. `silver skills-expand` chạy cùng bộ rule trên toàn bộ
requirements hợp lệ của ba ngành; ngành chỉ chọn phạm vi, không làm bằng chứng.
Các cụm cùng nghĩa được ghép theo bảng alias, không tự tách mọi nhãn có dấu `/`.
Giữ C++/C#/.NET, tên sản phẩm cụ thể không tự tạo skill cha. Quyết định chủ dự án:
quyết toán thuế/kê khai thuế/quản trị Fanpage dùng khái niệm chuyên môn riêng;
nhóm rộng cần được nêu riêng. Riêng sản xuất nội dung hình ảnh/video có marketing
rõ trong requirements vẫn tạo chuyên môn và Content Marketing theo policy cũ.

```bash
job-warehouse silver skills-expand \
  --jobs-run /outside/repo/s4-run \
  --output-dir /outside/repo/new-expanded-automatic-run

job-warehouse silver skills-expand-merge \
  --automatic-run /outside/repo/new-expanded-automatic-run \
  --baseline-run /outside/repo/current-reviewed-run \
  --review-run /outside/repo/581-reviewed-run \
  --review-run /outside/repo/23825-reviewed-run \
  --output-dir /outside/repo/new-expanded-with-reviews
```

Lớp merge giữ cặp và evidence đã duyệt theo ID/hash, chặn các cặp từng bị loại
trong review, không biến ngoại lệ ngữ nghĩa cho một tin thành alias toàn cục.
Tự động được tính lại đồng đều: xuất cả `added_pairs.csv`,
`removed_automatic_pairs.csv` và `blocked_by_review.csv` để đối chiếu.
Tin còn claim mơ hồ có thể giữ những cặp rõ khác; lưu trạng thái/rule của từng
evidence để kiểm tra. `expanded_no_match` chỉ nghĩa chưa khớp bằng rule hiện tại,
không phải nhãn xác nhận không có kỹ năng. Giữ toàn bộ tin ngoài phạm vi.

Kết quả luôn là **candidate** cho đến khi kiểm tra ngữ nghĩa bộ mở rộng;
điểm precision/recall của bộ 96 không áp dụng cho bộ mở rộng. Không tự thay pointer
hiện hành hoặc nạp PostgreSQL, commit/push. Báo cáo thật và mẫu review ngoài Git.

Bản mở rộng hiện có 602 khái niệm, thêm Chỉnh sửa hình ảnh để không đồng nhất
chỉnh sửa ảnh với thiết kế. Alias hữu hạn gồm cách viết quan sát được và tương
đương nghề rõ; không áp dụng fuzzy match toàn văn. Chặn cam kết→CAM, Solid
knowledge→SOLID, phần tên sản phẩm→skill cha, sector công ty→nghiệp vụ. Chuỗi
ngành học nối bằng dấu gạch vẫn là học vấn đến khi có mệnh đề năng lực mới.

Theo chốt bổ sung: “phần mềm kế toán MISA” giữ cả kỹ năng chung và công cụ;
MISA đứng riêng không sinh kỹ năng chung. Marketing chỉ nằm ở ngành học không
đủ làm ngữ cảnh Content Marketing; hiểu biết từ khóa chung không tự thành
Nghiên cứu từ khóa. Lớp merge cũng cập nhật ngoại lệ đã duyệt bị policy mới
thay thế, giữ bảng thay đổi và source run gốc. Mọi evidence mới kiểm FK, hash
requirements và offsets trên chính S4 trước khi xuất. Các điểm số từ mẫu đã
dùng sửa rule được lưu nguyên và tách khỏi vòng mẫu mới.


## Bổ sung riêng Bất động sản

`silver skills --batch real_estate` dùng `mappings_real_estate/` và matcher
riêng; chỉ xử lý nhãn Bất động sản. Các rule và dictionary bán hàng/CSKH đã chốt
được giữ nguyên. Mọi run vẫn là candidate cho đến khi có gate kiểm định riêng.
Không suy Kiến thức bất động sản chỉ từ kinh nghiệm làm trong ngành, bằng cấp
hoặc từ nghiệp vụ pháp lý. Phần mềm CSKH không tự thành nghiệp vụ CSKH.
Sở thích chốt đơn, cam kết học kỹ năng sale và đào tạo tương lai không là năng lực.

Các quyết định chủ dự án được thể hiện bằng rule và evidence ngữ cảnh:

- Danh sách CSKH/Sale/Telesale ngay sau câu yêu cầu kinh nghiệm có thể nhận
  ngữ cảnh từ câu đó; danh sách công cụ đứng riêng vẫn chưa rõ.
- Kinh nghiệm quản lý bán hàng rõ được tính Bán hàng; chỉ đếm số nhân viên
  sales được quản lý chưa đủ bằng chứng.
- Pháp luật kinh doanh có thể liên kết với Bất động sản nêu rõ trong cùng
  đoạn trước đó; lĩnh vực pháp luật mâu thuẫn tiếp tục chưa rõ.
- Lỗi gõ Preier được hiểu là Adobe Premiere trong danh sách phần mềm thiết kế
  rõ, không áp dụng alias này cho mọi ngữ cảnh.

Bản cuối kiểm định bằng hai AI độc lập trên 70 văn bản mới, tách các mẫu cũ đã
xem thành dữ liệu phát triển. Gate, điểm số, trạng thái nhận thực tế và giới hạn
nằm trong hồ sơ chạy ngoài Git; không gọi nhãn AI là nhãn con người xác nhận.

## Gói nhân sự, tài chính và pháp lý

`silver skills --batch hr_finance_legal` chọn ba nhãn nguồn: Nhân sự / Hành
chính - Thư ký; Ngân hàng / Tài chính - Đầu tư - Chứng Khoán; Luật - Pháp Lý -
Tuân thủ. Gói `mappings_hr_finance/` và matcher riêng không ghi lại các đợt đã
nhận. CLI chỉ tạo candidate; gate ngữ nghĩa và kết quả nhận thực tế nằm trong
hồ sơ ngoài repository, không được suy từ việc có tên batch trong CLI.

Tái sử dụng mã khái niệm cũ khi cùng nghĩa. Quyết toán thuế và kê khai thuế
nhận mã chuyên môn riêng, không tự thêm Báo cáo thuế. Phân tích báo cáo tài
chính không tự thêm kỹ năng lập báo cáo. MISA quản lý nhân sự có mã `hr_misa`,
MISA kế toán giữ `misa`; nguồn phải ghi rõ ngữ cảnh phần mềm nhân sự mới đổi
sang mã HR. Không đổi tên/mã/cặp đã nhận ở bản cũ.

Luật được liệt kê có thể dùng chung đầu cụm luật/pháp luật theo danh sách
hữu hạn, không suy mọi nhánh luật từ bằng luật. BHXH, C&B, tính lương, đào tạo
và hợp đồng chỉ được lấy trong ngữ cảnh năng lực hoặc nhiệm vụ chuyên môn;
quyền lợi, đào tạo sau khi nhận việc và ký hợp đồng của ứng viên không là skill.
Từng làm tại ngân hàng/tổ chức tài chính/văn phòng luật không đủ chứng minh
mọi nghiệp vụ. Câu thiếu chuyên môn và bare list chưa rõ vẫn giữ trạng thái.

API lấy mẫu nhận thêm `exclude_industries` để loại nhóm văn bản của các nhãn
đã nhận trước đó; cấm loại chính ngành mục tiêu. Mặc định vẫn loại ba ngành
thí điểm như cũ. Khi sửa rule, phải loại cả mẫu phát triển/kiểm định đã xem
bằng `exclude_samples` hoặc `exclude_job_ids`; không dùng lại điểm holdout cũ.

### Chốt theo từ khóa rõ, không đặt mục tiêu recall

Theo quyết định chủ dự án, gói nhân sự/tài chính/pháp lý dùng
`owner_explicit_keywords_skip_unclear`: giữ kỹ năng có bằng chứng rõ, bỏ qua
claim chưa rõ hoặc không khớp; vẫn giữ mọi tin. Ambiguous evidence chỉ lưu
vết, không tạo hàng đợi review bắt buộc và không chặn đóng đợt. Không trích
được không đồng nghĩa tin không có kỹ năng. ASP.NET và PL/SQL giữ riêng;
trả lương không tự thành tính lương.

Merge có loại gate riêng `accepted_owner_keyword_policy_no_recall_guarantee`,
phải ràng buộc SHA quyết định chủ dự án, policy và đúng phiên bản extractor.
Loại gate này không tuyên bố đạt kiểm định độc lập precision/recall; các điểm
vòng thử nghiệm cũ được giữ nguyên. Gate AI cũ vẫn giữ ngưỡng cũ. Cả hai cách
đều kiểm hash, toàn bộ cặp–bằng chứng, giữ baseline và đối soát đầu vào.
Các đợt tiếp theo áp dụng cách làm hữu hạn: khảo sát/từ điển, xử lý một lượt,
kiểm các lỗi gán sai rõ và đối soát; không lặp chỉ để tăng số tin có skill.

## Gói kho vận và vận tải

`silver skills --batch logistics_transport` dùng `mappings_logistics/` cho
hai nhãn nguồn xuất nhập khẩu/thu mua/kho vận và vận tải/lái xe/giao nhận.
Tái dùng chính sách từ khóa rõ: bỏ qua claim chưa rõ, giữ tin; không mở vòng
kiểm định lặp để đạt recall. Có các cụm thu mua, quản lý kho/tồn kho, kiểm kê,
chứng từ XNK, hải quan, điều độ, giao nhận; WMS/TMS/GPS chỉ lấy khi có ngữ cảnh
năng lực rõ. Dùng phần mềm quản lý kho không tự thành nghiệp vụ quản lý kho;
sales logistics và bằng cấp ngành học không tự thành vận hành logistics.

Chủ dự án cho phép bằng/chứng chỉ lái xe được nêu rõ tạo skill tương ứng
ô tô, xe máy hoặc xe nâng. Không suy số năm kinh nghiệm hoặc quy đổi hạng
bằng cũ–mới; có xe máy/điện thoại không tự thành kỹ năng lái xe. Chứng chỉ
được công ty hứa đào tạo/cấp trong tương lai không tính là năng lực có sẵn.
CLI giữ `--taxonomy-dir` nếu người vận hành cung cấp. Các đợt trước giữ
kết quả đã nhận; không dùng điểm kiểm định thí điểm để chứng nhận gói này.

## Gói kỹ thuật và sản xuất

`silver skills --batch engineering_production` dùng `mappings_engineering/`
cho năm nhãn nguồn điện/bảo trì, cơ khí/sản xuất, khoa học kỹ thuật, kỹ thuật
và quản lý chất lượng. Chỉ trích từ requirements với từ khóa/alias hữu hạn;
không suy chuyên môn từ nhãn ngành hoặc bằng cấp. Kế thừa chính sách chốt
khớp rõ, bỏ qua phần chưa rõ và giữ tin; không đặt mục tiêu recall.

CNC/PLC chung không tự thêm lập trình hoặc vận hành. CAD không tự đổi thành
AutoCAD; ISO chung không tự chọn số tiêu chuẩn. Hàn kim loại tách tiếng Hàn.
Dụng cụ đo chung không tự gán thành dụng cụ đo cơ khí. Chứng nhận ISO của
công ty, chỉ phối hợp với phòng QC, phần mềm quản lý sản xuất hoặc hành vi
an toàn chung không tự thành năng lực chuyên môn tương ứng của ứng viên.
Từ điển và kết quả cũ không bị ghi lại; hồ sơ khảo sát, quyết định nghiệm thu,
Parquet và đối soát giữ ngoài Git. Không có kiểm định mù mới hoặc bảo đảm
precision/recall; mẫu khảo sát/test được ghi rõ là development.

## Gói xây dựng, thiết kế và dự án

`silver skills --batch construction_design_projects` dùng `mappings_construction/`
cho bốn nhãn Xây dựng, Kiến trúc - Thiết kế nội ngoại thất, Thiết kế - Sáng tạo
nghệ thuật và Quản lý dự án. Tái dùng từ điển và chính sách từ khóa rõ; thêm
BIM, phần mềm thiết kế, bóc tách khối lượng, dự toán, giám sát thi công, hồ sơ
thầu và quản lý dự án khi requirements có bằng chứng cụ thể.

Không suy kỹ năng từ ngành học, nhãn ngành hoặc việc tham gia một dự án.
Phần mềm quản lý dự án không tự thành năng lực quản lý dự án; SAP2000 không
tự thành SAP. Thiết kế kiến trúc dữ liệu không phải thiết kế kiến trúc công
trình; QC/TCVN trong danh sách quy chuẩn không tự thành nghề kiểm soát chất
lượng. Giữ mọi tin, bỏ qua phần chưa rõ; không kiểm định lặp để tăng recall.
Khảo sát và test là kiểm tra phát triển, không phải chứng nhận độ chính xác
thống kê độc lập. Kết quả các đợt trước được giữ nguyên khi ghép.

## Gói giáo dục và ngôn ngữ

`silver skills --batch education_language` dùng `mappings_education/` cho ba
nhãn giáo dục/biên phiên dịch, giáo dục/CSKH và giáo dục. Tái sử dụng các kỹ
năng cũ khi requirements nêu rõ; thêm giảng dạy, soạn giáo án, quản lý lớp,
biên dịch, phiên dịch, tư vấn tuyển sinh và công cụ hỗ trợ học tập/dịch thuật.

Bằng cấp/ngành học, tên trung tâm ngoại ngữ hoặc sở thích giảng dạy không
tự thành kỹ năng. Dùng công cụ dịch thuật không tự thành năng lực biên dịch;
biên phiên dịch kết hợp không tự thêm các nhãn con nếu chỉ có cùng một cụm.
Chứng chỉ nghề TESOL/TEFL/CELTA được tính cho giảng dạy theo quyết định cho
phép chứng chỉ nghề cụ thể; không tự suy thêm tiếng Anh. Chứng chỉ ngoại ngữ
theo bảng ánh xạ hữu hạn hiện có. Không suy trình độ thành thạo hoặc số năm.
Thông báo bảo mật hồ sơ không phải năng lực nghiệp vụ của ứng viên.

Chốt một lượt theo từ khóa rõ: giữ mọi tin, bỏ qua phần chưa rõ/không khớp;
không mục tiêu recall hay kiểm định AI lặp. Mẫu khảo sát/test là development,
không chứng nhận thống kê độc lập. Kết quả cũ giữ nguyên khi ghép.

## Gói dịch vụ và bán lẻ

`silver skills --batch hospitality_retail` dùng `mappings_hospitality/` cho
nhãn ghép khách sạn/nhà hàng/du lịch và bán sỉ/bán lẻ/quản lý cửa hàng. Chỉ
đọc requirements: bổ sung các nghiệp vụ lễ tân, phục vụ bàn, buồng phòng,
chế biến món ăn, pha chế, đặt phòng/vé, điều hành tour, hướng dẫn du lịch,
thu ngân, quản lý nhà hàng/cửa hàng và công cụ được nêu rõ. Tái dùng kỹ năng
bán hàng, CSKH, ngôn ngữ và công cụ cũ khi có bằng chứng riêng.

Không suy bộ kỹ năng từ nhãn ngành ghép, ngành học hoặc nơi làm việc. Không
lấy sở thích ẩm thực/pha chế, đào tạo tương lai hay tuân thủ vệ sinh chung
làm năng lực chuyên môn. Dùng phần mềm quản lý cửa hàng/đặt phòng không tự
chứng minh nghiệp vụ tương ứng. Opera/PMS cần ngữ cảnh phần mềm khách sạn;
Abacus/Galileo cần ngữ cảnh công cụ hoặc đặt vé. Thẻ hướng dẫn viên du lịch
được nêu rõ theo chính sách chứng chỉ nghề cụ thể, không suy kinh nghiệm.

Khớp rõ thì lấy, chưa rõ thì bỏ qua và giữ mọi tin. Khảo sát/test phục vụ
phát triển, không phải kiểm định thống kê độc lập; không lặp để tăng recall.
Kết quả các đợt trước giữ nguyên khi ghép.
