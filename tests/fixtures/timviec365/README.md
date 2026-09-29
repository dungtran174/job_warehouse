# Timviec365 — fixture offline rút gọn

Ba file lấy cấu trúc DOM từ detail HTTP đã lưu ngày 27/09/2026 (ICT), ID
2070499, 2070495, 2070494. Giữ canonical, h1/data-id, nhãn trường và container
nội dung; loại JS, ảnh, nút ứng tuyển và nội dung ngoài phạm vi kiểm thử.
Mô tả/quyền lợi/yêu cầu tự do được thay bằng câu kiểm thử tổng hợp có đầu/cuối
và thẻ `br`: đây **không phải dữ liệu raw thật**, không dùng để tính tỷ lệ pilot.

Fixture tự chứa dữ liệu kiểm thử; unit/integration test không cần batch thật.
HTML đầy đủ, probe và batch 299 detail đã được lưu ngoài repository tại
`/home/dung/project/job_warehouse_archives/local_cleanup_20260929/timviec365.tar.gz`.
Archive giữ đường dẫn tương đối `data/raw/timviec365/` và
`data/diagnostics/timviec365_assessment/`; xem cách kiểm tra/khôi phục trong
[tài liệu dữ liệu](../../../docs/architecture_data.md#bản-lưu-dữ-liệu-cục-bộ-ngoài-repository).
