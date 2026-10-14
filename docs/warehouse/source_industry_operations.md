# Silver: nhãn ngành nguồn và phạm vi phân tích

Trục phân tích chính là `job_industry` của dataset Hugging Face, chuẩn hóa
cách viết và tổng hợp theo các quyết định chủ dự án. Không dùng AI suy nghề
từ title/description/requirements trong chặng này. `occupation_*`, `domains`
và `scope_500/scope_1000` của chặng enrichment trước được giữ để đối chiếu;
chúng không phải nhãn hoặc phạm vi ngành nguồn hiện hành.

## Chạy lại

Sau `silver enrich` và nhập ánh xạ địa điểm bằng `silver apply-location-map`,
chạy chặng ngành trên base-run đã xác nhận. Base có thể đã có nhãn ngành:
lệnh chỉ tính lại sáu cột ngành, giữ các cột khác và thứ tự bản ghi.

```bash
job-warehouse silver industry \
  --bronze /path/to/history_data.parquet \
  --base-run /path/outside/repository/verified-location-run \
  --output-dir /path/outside/repository/industry-run \
  --threshold 500
```

Bronze phải khớp SHA, revision contract và 606.878 dòng đã pin. Base cần
`enrichment.parquet` và `manifest.json` có SHA và số dòng. Khóa vật lý,
ID dataset và record_key của mọi dòng base phải khớp Bronze. Output phải
là thư mục mới ngoài checkout. Không gọi Docker, PostgreSQL hoặc crawler.

## Quy tắc và quyết định được lưu trong Git

- `silver/industry_labels.py`: NFC, khoảng trắng, chữ hoa/thường, alias hữu
  hạn cùng nghĩa; giữ nhãn rộng/hẹp khác nhau nếu chưa được chọn tổng hợp.
- `silver/industry_rollup.py`: giải quyết chuỗi con → cha cuối, từ chối vòng lặp.
- `silver/mappings/industry_rollup_policy.csv`: cấu hình phiên bản
  `owner-source-industry-20261015-v1`, gồm 253 nhãn ghép và 16 nhãn giữ riêng.
  Đây là cấu hình taxonomy, không phải raw tin tuyển dụng; không chứa ID,
  công ty, địa chỉ, toàn văn tuyển dụng hoặc số liệu từng bản ghi.
- Alias Banking → Ngân hàng, E-commerce → Thương mại điện tử và các alias
  khác được ghi trong code. Marketing - PR → Marketing do chủ dự án chọn.
- Ghép nhãn đảo thứ tự chỉ khi thành phần giống nhau; không mặc định dấu
  phẩy trong đường dẫn chuyên môn là ngành ngang cấp; không tách QA / QC
  trong ngoặc hoặc UI/UX thành các nghề.
- A01 **giữ Chăm sóc khách hàng riêng**. B07 vẫn ghép Tư vấn chăm sóc khách
  hàng → Chăm sóc khách hàng. Nhãn ghép giáo dục/CSKH vốn có trong nguồn giữ riêng.
- A09 **giữ Giáo dục - Đào tạo riêng**, hoàn tác quyết định ghép vào nhóm biên dịch.
- Các A còn lại được ghép. Giữ B03, B05, B06, B10, B11, B12, B21, B31,
  B32, B33, B34, B35, B37, B38; các B khác ghép. C01–C04 ghép đủ 204 nhãn
  được chọn, kể cả nhãn nhắc nhiều lĩnh vực, theo quyết định chủ dự án.

Các nhãn cha ghép là tập phân tích do chủ dự án chọn, không phải cây ngành
chính thức đã xác minh của nguồn. Không diễn giải mọi tin trong tập kết hợp
như thuộc một ngành đơn nhất. Nhãn raw luôn được bảo toàn.

Tên đại diện trước tổng hợp chọn từ toàn Bronze: nhãn có tần suất lớn nhất
trong nhóm tương đương; nếu hòa, chọn thứ tự chữ để tái chạy ổn định.
Ghép cha đối chiếu nguyên nhãn chuẩn hóa, không thay từ con trong mọi chuỗi.

## Cột và đầu ra

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| job_industry_raw | string, not null | Giá trị Bronze nguyên bản |
| job_industry | string, not null | Nhãn cuối theo alias và policy |
| industry_label_record_count | int64, not null | Tổng core cùng nhãn cuối trên cả revision |
| industry_scope_500 | bool, not null | Count ≥500 |
| industry_scope_1000 | bool, not null | Count ≥1.000 |
| industry_label_version | string, not null | Version normalizer và policy |

- `enrichment.parquet`: Silver đầy đủ, không mất nhóm ít mẫu.
- `jobs_analysis.parquet`: chỉ nhóm có count ≥ `--threshold` (mặc định 500).
  Giữ cả Chưa xác định và Nghề nghiệp khác theo quyết định 15/10/2026.
- `bronze_to_silver_industry.csv`: đầy đủ nhãn Bronze → nhãn cuối,
  số dòng Bronze và số core của nhóm cuối. Đây là lưu vết thực tế ngoài Git.
- `owner_rollup_applied.csv`: mã, con, cha trực tiếp, hành động và cha cuối;
  `industry_policy.csv`: snapshot policy chạy lượt đó.
- `quality_report.json`, `manifest.json`: phạm vi, số dòng, SHA input,
  code/assets, policy và output; kết quả đọc lại toàn bộ dòng/cột.

Ngưỡng tính SAU ghép, trên tất cả core trong revision. Chưa khử trùng thành
vacancy duy nhất; chưa đảm bảo đủ mẫu theo năm hoặc theo điều kiện tính lương.
Silver không bị xóa khi loại nhóm dưới ngưỡng khỏi tập phân tích.

Kết quả snapshot đã chốt trước tích hợp CLI: 606.857 core, 34 nhãn ≥500,
590.693 dòng được lấy và 16.164 dòng ngoài tập phân tích. Trong đó có hai
nhãn dư/chưa rõ ngành; không coi chúng là các ngành đồng nhất.

## Địa điểm và phạm vi bàn giao

Workbook địa điểm, các chỉnh sửa ID 176514/530258/600405 và quyết định
chủ dự án được giữ ngoài Git cùng bản địa điểm đã xác nhận. Chặng ngành
kiểm SHA base và bảo toàn mọi cột địa điểm; không tự chạy lại geocoding.
Các script chỉnh địa điểm theo ID của các lượt trước vẫn được lưu cùng
manifest base, không phải tác vụ tự động của lệnh ngành.

Không commit Parquet, workbook, môi trường, secrets hoặc báo cáo có dữ liệu
thực tế. `.gitignore` bảo vệ data/, .runtime/, *.parquet, *.xlsx, *.xls và
output phát sinh. CLI fixture không có cờ bỏ pin; fixture bypass chỉ ở API test.
