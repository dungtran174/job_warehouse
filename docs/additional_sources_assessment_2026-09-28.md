# Khảo sát nguồn tuyển dụng bổ sung — 28/09/2026

## Kết luận và phạm vi

Đã xem xét **14 nền tảng**, trong đó kiểm tra live **5 nguồn chưa bị chặn trong
bằng chứng cũ**. JobsGO cũng nằm trong nhóm ưu tiên của yêu cầu, nhưng repository
đã có bằng chứng listing 403/CAPTCHA ngày 22/09 nên **không thử lại**.

**ITviec là mẫu tốt nhất về kỹ thuật: 1 listing chính HTTP 200, 20 UUID thuộc
vùng kết quả chính, 3/3 detail HTTP 200 và đủ mô tả/yêu cầu từ chính detail.**
Tuy nhiên, chưa chọn nguồn nào để chạy batch mở rộng: điều khoản ITviec §2.2
chỉ có ngoại lệ sử dụng cá nhân hợp lý/chừng mực; chưa xác minh ngoại lệ đó bao
phủ việc sao chép 20–299 toàn văn vào kho dữ liệu. Không tự coi quyết định chủ
dự án là chấp thuận của nguồn, cũng không kết luận ITviec thất bại về kỹ thuật.

Kết quả thực ghi **vào raw `jobs.jsonl` mới = 0**. Ba record ITviec được trích
xuất, kiểm chứng và lưu trong **artifact diagnostic**, không gọi là batch/pilot.
Không tích hợp crawler chưa đủ điều kiện mở rộng, không chạy pilot 20 hoặc mốc
100/299, không tạo checkpoint/batch rỗng để biểu thị đã thu thập. Đây là trở
ngại về phạm vi sử dụng chưa được xác nhận, không phải lệnh cấm bot rõ ràng của
ITviec. Cần làm rõ ngoại lệ hoặc có quyền thực phù hợp trước khi mở rộng.

Đã đọc README, quy tắc dự án, mô hình raw, cấu hình giới hạn và báo cáo cũ.
Không sửa README/config/guard để mở khóa nguồn. Cơ sở mẫu nội bộ được ghi
`project_owner_public_test`, `authorization_reference=null`; không tạo mã giả.
Chưa làm Bronze/Silver. Không stage, commit hoặc push.

## Bảng tất cả nền tảng

`T/C` = số thử/thành công. Hàng **mới** là số của lượt này; hàng **cũ/tham chiếu**
là số đo đã lưu, không phải xác nhận website vẫn truy cập được ngày 28/09.
Tất cả hàng cũ có **0 request mới**. `N/A` nghĩa chưa có detail để đo, không phải
0% đầy đủ. ID là ID của listing chính, không phải số record detail.

| Nền tảng / loại bằng chứng | Điều kiện truy cập | Listing T/C | ID chính duy nhất | Detail T/C | Record raw `jobs.jsonl` | Đủ mô tả / yêu cầu | Phạm vi ngành | Lỗi / lý do chọn hoặc không chọn | Bằng chứng cục bộ / tài liệu |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| JobsGO — cũ 22/09 | Robots 200; listing 403/CAPTCHA đã có | 1/0 | 0 | 0/0 | 0 | N/A | Nền tảng đa ngành; chưa có mẫu detail | Không thử live lại; không dùng browser để né chặn | `source_feasibility/jobsgo/20260922T105141.302251Z/report.json` |
| Việc Làm Tốt — mới | Robots 200; homepage 403 managed challenge; điều khoản chưa đọc được | 0/0 | Chưa đo | 0/0 | 0 | N/A | Đa ngành theo nền tảng yêu cầu khảo sát; chưa đo mẫu | Dừng sau homepage; robots còn cấm URL chứa `page=`/`q=` | `D/vieclamtot/` |
| Glints Việt Nam — mới | Robots 200; `/vn` 403 firewall/CAPTCHA; điều khoản chưa đọc được | 0/0 | Chưa đo | 0/0 | 0 | N/A | Đa ngành; chưa đo mẫu | Dừng nguồn, không render/retry; robots cấm một số explore có query | `D/glints/` |
| 123job — mới | Robots 200; điều khoản §1/2/8 hạn chế sao chép hệ thống/dữ liệu khi chưa có văn bản | 0/0 | Chưa đo | 0/0 | 0 | N/A | Đa ngành, được thể hiện trong navigation | Dừng trước listing; không suy ra khả thi từ homepage 200 | `D/123job/` |
| ITviec — mới | Robots cho URL đã thử; §2.2 ngoại lệ sử dụng cá nhân hợp lý, chưa xác nhận cho batch kho dữ liệu | 1/1 | 20; 11 không gắn `super-hot` | 3/3 | **0**; 3 record diagnostic | **3/3 và 3/3 (100%)** | **IT**, không đại diện mọi ngành | Tốt nhất về mẫu kỹ thuật; chưa chọn chạy batch vì phạm vi ngoại lệ chưa rõ | `D/itviec/`, `detail-audit.json`, `details-extracted.json` |
| TopDev — mới | Robots 200; homepage lỗi TLS; điều khoản chưa xác minh | 0/0 | Chưa đo | 0/0 | 0 | N/A | **IT**, không đại diện mọi ngành | `SSL UNEXPECTED_EOF_WHILE_READING`; không có HTTP status/body ở lần lỗi; không đổi công cụ | `D/topdev/` |
| Việc Làm 24h — cũ 26/09 | Robots 403; chưa xác minh điều khoản | 0/0 | Chưa đo | 0/0 | 0 | N/A | Đa ngành; chưa đo mẫu | Không thử live lại | `second_source_assessment/20260926/vieclam24h-robots.*` |
| freeC — cũ 26/09 | Robots **429**; chưa xác minh điều khoản | 0/0 | Chưa đo | 0/0 | 0 | N/A | Đa ngành; chưa đo mẫu | Không thử live lại, không đổi thành kết luận 403 | `second_source_assessment/20260926/freec-robots.*` |
| TopCV — cũ 22/09, batch dừng cuối | Đã gặp browser challenge; điều kiện hiện hành chưa kiểm tra lại | 1/1 | 48 | 1/0 | 0 ở batch dừng; **1 ở batch trước** | Batch dừng N/A; record trước có hai trường, chưa audit toàn văn trong lượt này | Đa ngành; 1 record không đại diện | Không thử live lại; không xóa hoặc phủ nhận record cũ | `raw/topcv/.../batch_id=20260922T090917Z-488cb4e3/`; batch trước `20260922T085820Z-83c86cd5` |
| VietnamWorks — cũ 26/09, batch dừng | Listing HTTP 200 nhưng render 403; không retry | 1/0 | 0 enqueue trong batch dừng | 0/0 trong batch dừng | 0 | Batch N/A; **probe trước 3/3 đầy đủ** | Đa ngành; chưa chứng minh batch ổn định | Giữ riêng probe 3/3 và main-listing diagnostic 100 ID với batch dừng | [Báo cáo batch VietnamWorks](vietnamworks_batch_pilot_2026-09-26.md) |
| CareerLink — cũ 26/09 | Đã kiểm tra điều khoản; detail thứ 56 HTTP 200 hCaptcha | 2/2 | 100 | 56/55 | **55** | 55/55 và 55/55 (100%) | Đa ngành, nhưng batch nhỏ | Dừng challenge; không thử lại; không cộng pilot trùng ID vào 55 | [Báo cáo nguồn thứ hai](second_source_assessment_2026-09-26.md) |
| JobOKO — bằng chứng đã có 28/09 | Điều khoản §3 cấm bot/crawler/scrape | 0/0 | Chưa đo | 0/0 | 0 | N/A | Đa ngành; chưa đo mẫu | **Không thử live**, không gửi request crawler hoặc preflight mới | [Báo cáo JobOKO](joboko_assessment_2026-09-28.md) |
| CareerViet — batch tham chiếu 22/09 | Không kiểm tra lại điều kiện/live trong lượt này | 6/6 | 299 | 299/299 | **299** | 299/299 và 299/299 (100%) | Đa ngành; chưa đo tính đại diện toàn thị trường | Giữ nguyên để đối chiếu; không crawl lại | `raw/careerviet/.../batch_id=20260922T165843Z-f6b389a4/` |
| Timviec365 — batch tham chiếu 27/09 | Không kiểm tra lại điều kiện/live trong lượt này | 13/13 | 303 | 300 lượt đếm / 299 record thành công¹ | **299** | 299/299 và 299/299 (100%) | Đa ngành; chưa đo tính đại diện toàn thị trường | Giữ nguyên; ngày Cập nhật không được tính là ngày đăng | [Báo cáo mở rộng Timviec365](timviec365_expansion_2026-09-27.md) |

Các đường dẫn viết `source_feasibility/`, `second_source_assessment/` nằm dưới
`data/diagnostics/`; `raw/` nằm dưới `data/`.
`D` = `data/diagnostics/additional_sources_assessment/20260928T150105Z`.
Tất cả đường dẫn dữ liệu/HTML/JSON trong báo cáo là **artifact lưu cục bộ,
không commit**, không có sẵn khi clone Git. Tài liệu Markdown liên kết ở trên
được lưu trong repository, trừ báo cáo JobOKO vẫn là thay đổi untracked có từ
trước lượt này và được giữ nguyên.

¹ Timviec365 có một lượt đếm bị gián đoạn, không có response để xác định kết
quả; không gọi đó là một lỗi HTTP hay detail thành công. Xem báo cáo mở rộng
để phân biệt counter/checkpoint và 299 response detail/record thực có.

## Request mới thực tế và thời điểm

Một luồng HTTP thông thường, User-Agent minh bạch cố định của repository,
nghỉ **10 giây trước mỗi GET**, không retry. Không dùng browser/Selenium,
đăng nhập, cookie xác thực, API nội bộ, proxy/stealth, CAPTCHA solver hoặc host
ngoài các nền tảng. Không tải ảnh/script/asset trong HTML.

| Nguồn / mục đích | URL yêu cầu | Bắt đầu UTC 28/09/2026 | Kết quả |
| --- | --- | --- | --- |
| Việc Làm Tốt / robots | https://www.vieclamtot.com/robots.txt | 15:01:56.313143 | 200 |
| Việc Làm Tốt / tìm điều khoản | https://www.vieclamtot.com/ | 15:02:23.180982 | **403, managed challenge**, dừng |
| Glints / robots | https://glints.com/robots.txt | 15:03:00.659980 | 200 |
| Glints / tìm điều khoản | https://glints.com/vn | 15:03:42.317357 | **403, firewall/CAPTCHA**, dừng |
| 123job / robots | https://123job.vn/robots.txt | 15:04:12.185993 | 200 |
| 123job / tìm navigation/điều khoản | https://123job.vn/ | 15:04:50.124599 | 200, không tính là listing chính |
| 123job / điều khoản từ footer | https://123job.vn/help/policy | 15:05:39.479100 | 200, đọc toàn văn; dừng trước listing |
| ITviec / robots | https://itviec.com/robots.txt | 15:06:18.068758 | 200 |
| ITviec / tìm navigation/điều khoản | https://itviec.com/ | 15:06:43.289043 | 200, không tính là listing chính |
| ITviec / điều khoản Anh | https://itviec.com/blog/terms-and-conditions/ | 15:07:19.206883 | 200, đọc toàn văn |
| ITviec / điều khoản Việt | https://itviec.com/blog/terms-conditions-vn/ | 15:08:15.334371 | 200, đọc toàn văn |
| ITviec / listing chính | https://itviec.com/it-jobs | 15:08:57.755118 | 200, 20 UUID trong main |
| ITviec / detail 1 | URL đầy đủ tại bảng detail bên dưới | 15:11:38.899419 | 200, URL giữ nguyên |
| ITviec / detail 2 | URL đầy đủ tại bảng detail bên dưới | 15:15:29.085836 | 200, URL giữ nguyên |
| ITviec / detail 3 | URL đầy đủ tại bảng detail bên dưới | 15:15:40.373332 | 200, URL giữ nguyên |
| TopDev / robots | https://topdev.vn/robots.txt | 15:16:02.661990 | 200 |
| TopDev / tìm điều khoản | https://topdev.vn/ | 15:16:29.914869 | **Lỗi TLS, không nhận response HTTP** |

Giờ Việt Nam = UTC + 7, khoảng 22:01–22:16 ngày 28/09. Tổng **17 lần gọi GET**:
8 kiểm tra điều kiện (5 robots + 3 trang điều khoản), 5 navigation/homepage,
1 listing chính, 3 detail. Có **16 response HTTP: 14 HTTP 200, 2 HTTP 403**;
1 lỗi TLS chưa có response. Không có redirect trong những response mới.
Không gộp 403 homepage thành listing thử hoặc 14 response 200 thành detail.

Mỗi response có `*.json` ghi URL/status/thời điểm/SHA-256 và nguyên
`*.hop-0.body.gz` lưu **trước** quyết định dừng/phân tích. Các trang bình thường
có text đã bỏ script/style để đọc offline. TLS không có body; metadata lưu lỗi,
không tự gán status. Metadata không ghi header cookie/token; body raw chỉ lưu
nội bộ và không công bố lại vì có thể chứa mã phiên/challenge của website.

## Đối chiếu robots, điều khoản và quyết định

### Việc Làm Tốt và Glints: bị từ chối trước listing

[Robots Việc Làm Tốt](https://www.vieclamtot.com/robots.txt) có nhóm chung cho
User-Agent dự án, cho `/` nhưng cấm tài khoản, các query phân trang/tìm kiếm
`/*page=` và `/*q=` cùng nhiều query lọc. Các nhóm bot được đặt tên riêng không
được suy diễn thành áp dụng cho mọi bot. Host `www.vieclamtot.com` là host chuẩn
thể hiện trong sitemap; không dùng tên miền/URL thay thế để né challenge.
Trang chủ trả 403 với managed challenge, nên không đọc được footer điều khoản,
không thử listing/detail. Chưa xác minh quyền sao chép dữ liệu hoặc phân trang.

[Robots Glints](https://glints.com/robots.txt) không cấm `/vn`, nhưng cấm một số
route explore có query, vùng tài khoản/preview/recommended và tracking API.
`/vn` trả 403 với trang firewall yêu cầu CAPTCHA; dừng ngay. Không đổi query,
browser hoặc host để né giới hạn. Không kết luận parser thất bại vì chưa được
thử main listing hay detail, cũng chưa đọc được điều khoản hiện hành.

### 123job: điều khoản hạn chế sao chép, không chỉ quyền khóa tài khoản

[Robots 123job](https://123job.vn/robots.txt) cấm `/ajax` và `/apply`, không
phải lý do dừng. [Điều khoản](https://123job.vn/help/policy) cập nhật/hiệu lực
23/03/2026 đã đọc toàn văn. §1 áp dụng cho truy cập/sử dụng; §2 bao gồm người
truy cập không đăng ký và dữ liệu tuyển dụng. §8 hạn chế sao chép, sửa đổi,
phân phối hoặc khai thác hệ thống/dữ liệu khi chưa có sự cho phép bằng văn bản.
Cụm liên quan: “khai thác bất kỳ phần nào của hệ thống”.

Sao chép toàn văn vào kho dữ liệu là hoạt động cần đối chiếu khoản này; chưa
có sự cho phép thật hoặc ngoại lệ đồ án được xác nhận. **Không gọi đây là
điều khoản cấm bot riêng**. §6 chỉ nói thu thập trái phép, tự nó không đủ để
kết luận mọi request là bị cấm; §12 quyền hạn chế dịch vụ cũng không phải lý
do độc lập để dừng. Quyết định dừng dựa trên hạn chế sao chép §8 kết hợp phạm
vi §1/2, không dựa vào homepage 200 hay việc không đăng nhập.

Homepage có navigation `/tuyen-dung`, `/jobs`, nhưng chưa thử; không lấy các
card tuyển gấp/nổi bật trên homepage làm ID main hoặc detail thành công.

### ITviec: mẫu đọc được, ngoại lệ không tự mở rộng thành quyền crawl batch

[Robots ITviec](https://itviec.com/robots.txt) không cấm `/it-jobs` hay ba URL
detail đã thử với User-Agent dự án; vùng `/subscriptions/new` không được gọi.
Không coi robots cho phép là giấy phép sao chép hoặc tái xuất bản.

[Điều khoản Anh §2.2](https://itviec.com/blog/terms-and-conditions/) có ngoại lệ
“reasonable personal use of the website” và yêu cầu “prior written consent”
cho việc lấy/sao chép/tải nội dung ngoài ngoại lệ. [Bản Việt §2.2](https://itviec.com/blog/terms-conditions-vn/)
diễn đạt ngoại lệ cần thiết và sử dụng trong chừng mực. Hai bản có hiệu lực
01/07/2023, trang blog ghi cập nhật 08/12/2025. §2.1 bao gồm dữ liệu/văn bản.
§4.3 quyền tạm ngừng dịch vụ và §4.5 không bảo đảm chính xác **không phải**
lệnh cấm crawl độc lập; không phát hiện câu cấm bot/crawler riêng trong hai bản.

Đánh giá có giới hạn trước thử: mẫu **1 listing/3 detail**, nội bộ, không
thương mại/công bố lại, được xử lý trong ngoại lệ sử dụng cá nhân hợp lý.
Đây là nhận định phạm vi, không phải giấy phép của ITviec hoặc tư vấn pháp lý;
`access-decision.json` đã lưu trước listing. **Chưa xác minh ngoại lệ cho kho
dữ liệu 20–299 toàn văn**, nên không mở rộng chỉ vì HTTP hoạt động tốt. Không
sửa gate `bounded` và không tạo authorization-reference thay thế sự chấp thuận.

### TopDev: lỗi kỹ thuật ở preflight, không kết luận điều khoản cấm

[Robots TopDev](https://topdev.vn/robots.txt) cho nhóm chung `/`, cấm login,
search nhà tuyển dụng, apply/challenge/affiliate/partners/topdemy/socket.
Nhóm Yeti bị cấm riêng không phải User-Agent dự án. Homepage gặp TLS EOF,
chưa có HTML để tìm URL điều khoản/main listing. Chưa biết điều khoản hoặc URL
detail cụ thể; không tự coi robots là đủ điều kiện để thử. Không tắt xác minh
TLS, đổi host, browser, User-Agent hoặc retry trong lượt này.

## ITviec: listing chính, phân trang và ba detail thật

Vùng kết quả: **`.card-jobs-list .job-card`**, 20 card, 20 UUID duy nhất lấy
từ `data-job-key`; không có card cùng selector ngoài vùng main. Không lấy
homepage, phần “More jobs for you” hoặc navigation công ty làm kết quả main.
9 card có lớp `super-hot` được loại khỏi tập chọn mẫu; còn 11 card main.
Tất cả 20 có nhãn `HOT`: nhãn này không đủ chứng minh từng card là quảng cáo
hoặc organic. Vì thế **20 là tổng ID main, không phải 20 tin organic đã xác
minh**; 11 là số không có lớp super-hot, không phải cam kết không được tài trợ.
Ba URL mẫu nằm trong main, không thuộc nhóm super-hot hay vùng gợi ý riêng.

Link UI `rel=next`:
`https://itviec.com/it-jobs?page=2&query=&source=search_job`.
HTML có liên kết tới trang cuối 36; heading hiển thị 705 việc làm IT. **Chưa
request trang 2**, chưa đo overlap/ID mới, không coi 705 là số thu thập được.
Không gọi route fragment `/content?...` của UI hoặc dò API. Các link detail
được lấy nguyên từ heading card, kể cả query `lab_feature=preview_jd_page`;
kiểm chứng nội dung bên dưới thay vì mặc định query này trả toàn văn.

| Detail / UUID khớp listing và HTML detail | Tiêu đề / công ty | Ký tự mô tả / yêu cầu | `datePosted` / `validThrough` | URL đã request, cũng là URL cuối |
| --- | --- | ---: | --- | --- |
| 1 — `c6196e56-3e58-4c18-9053-f0f10cc45e23` | Senior Software Engineer (PHP/ Java/ Golang/ Python) / Global Fashion Group | 1.799 / 667 | 2026-09-28 / 2026-11-02 | https://itviec.com/it-jobs/senior-software-engineer-php-java-golang-python-global-fashion-group-1031?lab_feature=preview_jd_page |
| 2 — `2c97f05b-2e04-484a-b15a-40f88e8e869f` | Junior Security Engineer / ZALORA Group | 2.377 / 1.442 | 2026-09-28 / 2026-11-02 | https://itviec.com/it-jobs/junior-security-engineer-zalora-group-5536?lab_feature=preview_jd_page |
| 3 — `8957157b-cbff-4b1a-aefd-faabc6a19a31` | Presales/Consultant (Salesforce, CRM) / GiMASYS | 326 / 924 | 2026-09-07 / 2026-10-12 | https://itviec.com/it-jobs/presales-consultant-salesforce-crm-gimasys-0236?lab_feature=preview_jd_page |

Kiểm chứng offline cả ba:

- UUID từ widget lưu việc làm **trong detail** khớp UUID main listing. Không
  dùng hậu tố bốn chữ số của slug làm ID; tính ổn định qua thời gian chưa đo.
- H1 detail khớp tiêu đề card; công ty JSON-LD khớp header detail. Canonical
  nằm trên `itviec.com`; response không chuyển host. Không gọi link ứng tuyển.
- Lấy toàn bộ container của hai heading “Job description” và “Your skills and
  experience”, bỏ đúng heading. Toàn bộ văn bản từng section sau chuẩn hóa
  khoảng trắng xuất hiện nguyên trong `JobPosting.description` JSON-LD cùng
  HTML, **6/6 đối chiếu đạt**. Không lấy snippet/listing/related jobs để bù.
- `detail-audit.json` lưu độ dài, đoạn đầu/cuối, kích thước HTML section và
  kết quả đối chiếu. Mô tả ngắn nhất 326 ký tự vẫn là toàn section, không kết
  luận bị cắt chỉ vì ngắn. Không chứng minh nội dung ẩn phía tài khoản tồn tại.
- Địa chỉ/địa điểm lấy từ JSON-LD detail: hai tin ở Hồ Chí Minh; GiMASYS có
  cả Hồ Chí Minh và Hà Nội, giữ cả hai. Không suy ra từ tiêu đề/listing.
- Lương trên cả ba yêu cầu đăng nhập. JSON-LD chứa giá trị quảng bá “You'll
  love it”, **không phải mức lương**; `salary_raw=null` cả ba, không đăng nhập.
- `datePosted` có ở cả ba JSON-LD; không dùng ngày cập nhật làm ngày đăng.
  `validThrough` đều sau 28/09/2026, không có dấu hiệu hết hạn theo ngày nguồn
  khai báo; chưa xác minh nhà tuyển dụng vẫn đang tuyển hoặc tin là xác thực.
- Ba payload được `JobRecord.model_validate` và tính `job_content_hash` theo
  model/helper repo. Lưu `details-extracted.json` dạng diagnostic, ghi rõ
  batch ID diagnostic, không giả định đã chạy adapter/CLI/pilot.

Tỷ lệ truy cập detail **3/3**, đủ title/company/description/requirements
**3/3**, lỗi detail **0**. Chưa có phép đo tốc độ/độ ổn định nhiều trang,
dedup/resume live, lỗi ở quy mô 20–299 hoặc quyền công bố toàn văn. Không coi
kết quả này là “có thể chạy batch ổn định”.

## Đối chiếu với hai batch dữ liệu hiện có

Phân tích offline `jobs.jsonl` thật; nguồn ITviec là **diagnostic n=3**, không
phải batch raw và không đại diện mọi ngành. Profile máy đọc được:
`D/reference-data-profile.json`.

| Chỉ tiêu | CareerViet raw | Timviec365 raw | ITviec diagnostic |
| --- | ---: | ---: | ---: |
| Record / ID duy nhất | 299/299 | 299/299 | 3/3 |
| Tên công ty khác nhau, chưa entity-resolution | 210 | 252 | 3 |
| Có tiêu đề / công ty / mô tả / yêu cầu | 299/299 mỗi trường | 299/299 mỗi trường | 3/3 mỗi trường |
| Có lương / địa điểm | 299/299 mỗi trường | 299/299 mỗi trường | **0/3 lương**, 3/3 địa điểm |
| Có ngày đăng raw | 299/299 | **0/299**, null; không lấy ngày Cập nhật | 3/3, từ JSON-LD `datePosted` |
| Độ dài mô tả, ký tự | 158–6.542 | 120–3.176 | 326–2.377 |
| Độ dài yêu cầu, ký tự | 26–4.501 | 90–1.588 | 667–1.442 |
| Phạm vi | Đa ngành trong batch | Đa ngành trong batch | Chỉ IT trong mẫu |
| Bằng chứng batch/resume | Đã lưu batch 299 | Đã lưu batch 299 và audit mở rộng | Chưa thử pilot/resume |

Độ đầy đủ ở bảng là trường có nội dung, không chứng minh đúng nghiệp vụ.
Đối chiếu DOM/JSON-LD ITviec xác nhận nội dung trang được trích nguyên section,
không xác minh tính thật của công ty/tin, lương/địa điểm đúng, chống tuyển dụng
lừa đảo, hết hạn thực tế hoặc tính đại diện thị trường. ITviec §4.5 cũng không
bảo đảm tính chính xác nội dung. Không tuyên bố chất lượng “đầy đủ như
CareerViet” ở tất cả trường, nhất là lương bị khóa và chỉ có ba mẫu IT.

## Bằng chứng, lệnh, kiểm tra và bảo toàn

Artifact mới tại `D/`:

- `baseline-raw.json`, `baseline-files.json`: SHA-256 trước khảo sát.
- `report.json`: request ledger, các counter và lý do chưa chọn nguồn chạy batch.
- Mỗi nguồn: robots/homepage/terms/listing/detail metadata và body tương ứng;
  `assessment-decision.json` ghi cơ sở chủ dự án, không nhận chấp thuận nguồn.
- ITviec: `access-decision.json` trước listing, `listing-analysis.json`,
  `detail-audit.json`, `details-extracted.json`.
- `listing-analysis.initial.json` lưu lần phân loại offline ban đầu loại mọi
  nhãn HOT; sau đọc cấu trúc DOM đã sửa phân biệt main/super-hot. Lỗi chọn mẫu
  offline này xảy ra **trước request detail**, không tạo thêm listing request.

Các lệnh thực hiện: `git status --short`, `git branch --show-current`,
`git rev-parse HEAD`, `rg`/`sed` đọc repo; các đoạn Python HTTP tuần tự gọi
`scripts.public_source_probe.capture(root, label, url, delay=10)` cho đúng
17 lượt trong ledger, không retry. Phân tích DOM/JSON-LD, đếm record/ID,
`JobRecord.model_validate`, hash và đối chiếu checksum chạy **offline** trên
body đã lưu. Không có lệnh `job-crawler crawl` hoặc resume nguồn cũ trong lượt này.

Kiểm tra cuối:

```bash
.venv/bin/pytest -q -m 'not live'  # 205 passed, 10.16s
.venv/bin/ruff format --check .  # 95 files already formatted
.venv/bin/ruff check .           # All checks passed
.venv/bin/mypy src               # 43 source files, passed
git diff --check                # passed; file mới kiểm tra whitespace riêng
```

Test suite trên là test của code hiện có, **không có test crawler ITviec** vì
chưa tích hợp parser/CLI. Audit ba HTML diagnostic nêu trên là kiểm chứng
offline riêng bằng assertion, không gọi nó là pilot/resume test thành công.

Đối chiếu SHA-256 **1.522 file raw/checkpoint cũ và 125 file code/test/script/
docs/README có trước lượt này: không đổi**. CareerViet vẫn 299, Timviec365
299, CareerLink 55; giữ mọi batch, HTML, incremental state và checkpoint.
Không sửa code của các nguồn cũ hoặc báo cáo JobOKO untracked có sẵn.

Git: `main`, HEAD `7ba563532bf1251dcdc5b380cb377a70968c97d4` trước/sau.
Chỉ thêm tài liệu này; không có diff tracked/staged và không stage/commit/push.
Diagnostics bị gitignore, không đưa HTML/JSON/raw lên Git. Không tạo `jobs.jsonl`
nguồn mới, không làm thay đổi tổng ID hai batch tham chiếu.

Để đi tiếp, ưu tiên **làm rõ phạm vi sử dụng dữ liệu với ITviec** vì đây là
nguồn duy nhất có bằng chứng 3 detail đầy đủ trong lượt này, nhưng chỉ bổ sung
góc nhìn IT. Cần quyền/ngoại lệ thực cho thu thập/lưu HTML toàn văn và quy mô
pilot; sau đó mới tích hợp và đo pilot, phân trang, resume trước khi quyết
định 100/299. Không đưa lệnh resume giả cho nguồn chưa có batch/checkpoint.
