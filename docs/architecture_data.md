# Kiến trúc, dữ liệu và bài học vận hành

## Phạm vi

Hai nguồn pipeline chính: **CareerViet + CareerLink**. Hiện có crawler/raw,
chưa triển khai Bronze ingestion, Silver, Gold, lịch chạy hay dashboard.
`jobs.jsonl` là raw đầu vào; thư mục Bronze có đối soát/idempotency sẽ là bước sau.
Không thay schema/parser của batch cũ khi chưa có migration hoặc reparse có phiên bản.

```text
CLI -> engine -> fetcher HTTP -> adapter/parser nguồn
          |-> jobs.jsonl + HTML + HTTP evidence + manifest/errors
          `-> checkpoint theo batch + incremental_state theo nguồn

Sau này: batch mới theo ngày -> Bronze ingest -> Silver -> Gold -> dashboard
```

## Hợp đồng raw và khóa

- Mỗi dòng phải là detail, không phải listing/preview/gợi ý. Các trường lõi:
  ID, canonical URL, title, company, toàn văn description và requirements từ detail.
- Provenance: `source_name`, `source_job_id`, `source_url`, `canonical_url`,
  `listing_url`, `crawled_at`, `snapshot_date`, `batch_id`, `schema_version`,
  `parser_version`, `raw_html_path`, `content_hash`.
- Trường tùy chọn giữ nguyên giá trị nguồn hoặc null/array rỗng: salary, location,
  posted date, occupation tags, job type, experience, education, benefits, deadline.
  Null do parser chưa map phải phân biệt với nguồn không công bố qua HTML.
- Khóa nghiệp vụ trong nguồn là `(source_name, source_job_id)`. Checkpoint/JSONL
  tách thư mục theo nguồn nên dedup ID trong batch được namespace bởi thư mục đó.
  Không dùng ID hay content hash để tuyên bố đã khử trùng xuyên nguồn.
- SQLite là trạng thái kỹ thuật, không phải OLTP hoặc Data Warehouse.

## Snapshot, resume và incremental

Batch mới có `snapshot_date` theo Asia/Ho_Chi_Minh; `crawled_at` có timezone.
Resume giữ batch/snapshot/parser/schema/start URL/cơ sở truy cập cũ, không tải
completed ID. Processing bị ngắt được đưa lại pending; failed không tự retry.
Raw là authority khi đồng bộ completed; JSONL đuôi dang dở được giữ `.partial`.

`max-pages` và `max-details` là **lượt thử lũy kế**, không phải ngân sách mới của
resume. Slot gián đoạn có thể đã được đếm trước khi gửi HTTP; lỗi cũ không bị xóa.
CareerLink `target-records` đếm tổng ID raw duy nhất, không đếm ID discovery;
không thắng robots/challenge/error-rate/max-attempts. Nếu mục tiêu đã có đủ,
gọi lại đúng lệnh không gửi request mạng. Giới hạn bản mới: tối đa 8 listing,
330 detail attempts; muốn attempts >300 phải chỉ định target <=300.
`manifest.run_settings` ghi cấu hình thực của từng invocation mới (giới hạn,
delay, retry, fetcher); không tự dựng lại cấu hình các lượt lịch sử chưa ghi.
Các trường delay ở gốc manifest vẫn là cấu hình khởi tạo của batch cũ.

State incremental độc lập tại `data/raw/<source>/incremental_state.sqlite3`:
first/last seen, last content hash, last detail fetched, seen count, active.
**Hiện vẫn tải detail trong mỗi snapshot**, chưa có scheduler hoặc chính sách
chỉ tải ID mới + tin đến hạn kiểm tra lại. Định hướng bước sau:

1. Batch mới mỗi ngày; resume chỉ hoàn tất batch dang dở.
2. Quét listing có giới hạn, lưu coverage/phân trang; ID mới tải detail, ID cũ
   kiểm tra lại theo lịch. Không dừng chỉ vì trang đầu toàn ID cũ khi chưa chứng
   minh thứ tự nguồn luôn theo ngày đăng.
3. Chỉ biết hash đổi sau khi tải/parse. Bronze giữ lịch sử và manifest/file SHA;
   Silver upsert bản hiện tại kèm lịch sử thay đổi; Gold đếm theo grain rõ ràng.
4. Vắng mặt trong một lần quét giới hạn/crawl lỗi không đủ để đánh dấu hết hạn.
5. Dashboard tách "tin lần đầu quan sát" với "tin đăng ngày đó"; không cộng
   cùng ID qua các batch thành nhiều việc làm hoặc gọi mẫu quota là toàn thị trường.

Chưa triển khai các bước này trong lượt chuẩn bị/dọn repository.

## Batch cần giữ và trạng thái nguồn

Số liệu xác minh offline 29/09/2026, không phải kết quả crawl mới:

| Nguồn | Vai trò | Batch ID | Raw / ID duy nhất | Trạng thái |
| --- | --- | --- | ---: | --- |
| CareerViet | Chính, HTTP | `20260922T165843Z-f6b389a4` | 299 / 299 | 6 listing, 299 detail hợp lệ |
| CareerLink | Chính, HTTP | `20260926T160422Z-c39d6a20` | 75 / 75 | 2 listing, 100 ID; 76 attempts, 1 challenge cũ; 25 pending |
| VietnamWorks | Dự phòng, browser | `20260929T091457Z-1d8023a1` | 295 / 295 | 8 listing/351 ID; 300 slot = 295 thành công +4 lỗi +1 gián đoạn |
| Việc Làm 24h | Dự phòng, browser | `20260929T042736Z-b37e7b1a` | 104 / 104 | 11 listing/277 ID; 502 và capture cuối chưa biết status |
| Timviec365 | Đối chiếu kế hoạch cũ, archive ngoài repo | `20260926T174917Z-3a406cfa` | 299 / 299 | Dữ liệu thật; bản trong repo đã bỏ sau kiểm chứng archive |

Đường batch: `data/raw/<source>/snapshot_date=<ngày>/batch_id=<id>/`.
CV snapshot 22/09, CL 26/09, TV 27/09, VW/V24h 29/09. Probe CareerViet cũ
vẫn giữ; TopCV/JobOKO đã dọn khỏi repo và có bản lưu probe ngoài repo.
Không trộn probe vào tổng chính. Batch VietnamWorks 26/09 raw=0 bị
403 riêng; không gắn nhãn "crawl lỗi" cho batch 295 thành công ngày 29/09.

Adapter/parser/fetcher/fixture và audit/recovery của nguồn dự phòng còn được
CLI/factory/engine/test tham chiếu nên giữ nguyên, không xóa dây chuyền test.
Không tự chạy các nguồn dự phòng. Code browser hiện còn là dependency của repo;
chạy CareerViet/CareerLink bằng HTTP không mở Chrome, không cần executable path.
Các gate CareerViet cũ medium/pilot/page6 vẫn giữ tương thích: không tự mở khóa
batch lớn tương lai hoặc dùng reference do chủ dự án tự đặt như văn bản chủ nguồn.

## Bài học cần giữ cho chuẩn hóa

- CareerLink metadata nghề/type/degree/experience/company/benefits có trong nhiều
  HTML nhưng raw chưa map. Có thể enrich offline ở Silver, không sửa 75 dòng cũ.
- CareerViet có lower/upper salary bounds và nhiều job locations; parser có thể
  mất nhãn "Trên/Lên đến" hoặc chỉ lấy location đầu. Giữ HTML và giá trị gốc.
- VietnamWorks main listing cần render trong batch đã kiểm chứng; HTTP200 khung
  Loading/featured không tính là main. `onlineOn` khác ngày UI ở 205/293 detail
  có nhãn ngày; không coi nó luôn là ngày đăng gốc.
- Việc Làm 24h HTML có dữ liệu nhưng chưa chạy batch HTTP độc lập. Ngành chưa map,
  location `+2` không phải tỉnh; lỗi 502/capture chưa biết status không phải 403.
- Challenge HTTP200 là lỗi truy cập, không phải detail. CareerLink ID3626178
  bị hCaptcha 26/09, đọc lại hợp lệ 29/09; lỗi cũ còn errors, completed không retry.
- Dữ liệu lịch sử revision `679c3a17347ff6ce769d9bf510c122a087493cf6` khai báo
  606.878 dòng/14 trường; đã đọc 1.000 mẫu thực, chưa profile toàn bộ Parquet.
  `year` chỉ chính xác theo năm, `id` thuộc dataset, không phải ID website.
  Giữ attribution CC BY-NC4.0; license đó không cấp quyền cho raw web mới.

Chi tiết trường, mapping, CSV và đề xuất ô Excel trong
[đánh giá hai nguồn chính](primary_sources_recommendation_2026-09-29.md).
Artifacts được liên kết trong báo cáo là file cục bộ, không đi cùng clone.

## Tài liệu lịch sử và tương thích

Báo cáo từng lượt/spec cũ có thể đọc lại từ Git revision
`49b5e639353a4825b6ac4e20a10d2b851a8d87f1`, ví dụ:
`git show 49b5e639:docs/careerlink_resume_assessment_2026-09-29.md`.
Ngoại lệ probe cũ chỉ là lịch sử, không phải quyền chạy lại trong tương lai.
Fixture tự chứa dữ liệu kiểm thử; giữ coverage và adapter dự phòng đang được
import. Raw schema không đổi; `RunManifest.run_settings` mặc định rỗng nên đọc
được manifest cũ mà không migration raw.

Dữ liệu lịch sử, revision/card/license, mẫu đã đọc và profile trong
`data/diagnostics/primary_sources_assessment_20260929/` vẫn cần cho đồ án,
không phải artifact tạm. Raw và bằng chứng của các nguồn còn giữ không bị xóa.

## Nguồn không chọn

- **TopCV:** lượt 29/09/2026 robots200 nhưng listing403/Cloudflare access-denied,
  detail thử0. Bốn batch thử cũ có3 batch rỗng và1 dòng qua schema; đối chiếu
  HTML cho thấy raw yêu cầu chỉ là heading "Yêu cầu ứng viên", không phải toàn
  văn, nên0 detail đạt yêu cầu. Bản gốc không được sửa thành record hợp lệ;
  lưu ngoài repo để có thể xem lại. Fixture/parser regression trong Git vẫn giữ.
- **JobOKO:** probe28/09 đọc3/3 detail bằng HTTP từ hub, nhưng chưa xác minh main
  search listing/phân trang, không có raw batch. Điều khoản hạn chế bot/crawler
  và quyền sử dụng dữ liệu chưa xác minh; quyết định probe của chủ dự án không
  phải chấp thuận nguồn. Không chọn cho pipeline chính, không gọi là lỗi HTTP.
- **Timviec365:**299 detail toàn văn là dữ liệu thật; chuyển ra archive vì phạm
  vi pipeline đã chốt CareerViet+CareerLink, không phải vì crawl thất bại.

## Bản lưu dữ liệu cục bộ ngoài repository

Thư mục bền vững (không phải /tmp, không commit/public):
`/home/dung/project/job_warehouse_archives/local_cleanup_20260929/`.

- `timviec365.tar.gz`: raw/HTML/http/manifest/checkpoint/incremental state,
  hai thư mục diagnostics và ba báo cáo cũ;1.027 file. SHA-256 archive:
  `7a112a03f5663d43f66dc6816b8ad4fb50f8260b8e4e3aded9eceb4f4baa552d`.
- `discarded_topcv_joboko.tar.gz`: bốn batch TopCV, diagnostics/ảnh/HTML
  TopCV+JobOKO và các báo cáo cũ liên quan;96 file. Đây chỉ là bản lưu bằng
  chứng, không tính1 dòng TopCV lỗi trích xuất hoặc3 diagnostic JobOKO vào raw
  hợp lệ. SHA-256 archive:
  `4b7692a6b5d7a0e4b876c845f8028c5c2cf0895177a78add93bcf1344cd31ed0`.
- Hai file `*.inventory.json` bên cạnh ghi SHA-256/kích thước từng member,
  danh sách chính xác các đường dẫn đã bỏ trong repo và SHA archive.

Đã đọc toàn bộ archive, kiểm tra gzip CRC và checksum mọi file; giải nén thử
Timviec365 rồi audit299/299 full description/requirements, ID/hash/canonical,
manifest/checkpoint. SHA jobs.jsonl trước/sau:
`296f67ec9e5b5d6be9c717c6135b09460be85b53f1a0ddb6f5940e8f64460bc2`.
Test chỉ dùng fixture/tmp_path, không cần restore batch để chạy offline.

Kiểm tra archive và khôi phục vào repo **khi bạn cần**, không ghi đè file đang có:

```bash
gzip -t /home/dung/project/job_warehouse_archives/local_cleanup_20260929/timviec365.tar.gz
sha256sum /home/dung/project/job_warehouse_archives/local_cleanup_20260929/timviec365.tar.gz
tar --extract --gzip --keep-old-files --no-same-owner \
  --file /home/dung/project/job_warehouse_archives/local_cleanup_20260929/timviec365.tar.gz \
  --directory /home/dung/project/job_warehouse
```

Đổi tên archive thành `discarded_topcv_joboko.tar.gz` nếu cần xem bằng chứng
probe cũ. `--keep-old-files` từ chối ghi đè, không dùng để tiếp tục crawler.
Các bảng/checksum lịch sử trong diagnostics chung vẫn mô tả thời điểm cũ,
không phải đường dẫn hiện còn tồn tại hoặc cam kết permission/crawl tương lai.
