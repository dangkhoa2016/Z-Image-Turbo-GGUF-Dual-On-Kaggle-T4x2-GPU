# v1.0.0 — Bản xem trước kỹ thuật

> 🌐 Language / Ngôn ngữ: [English](RELEASE_NOTES_v1.0.0.md) | **Tiếng Việt**

Bản xem trước kỹ thuật công bố mã nguồn hệ thống Z-Image-Turbo GGUF Q6_K trên Kaggle hai Tesla T4: mã hóa prompt trên GPU0, hai worker inference, Vue Studio xác thực, biên nhận PNG riêng tư, notebook Kaggle và tài liệu song ngữ.

## Nghiệm thu
- Có bằng chứng JSON về dual-GPU, tạo ảnh qua trình duyệt, HTTPS và tổng thời gian xử lý. [Bản tổng hợp nghiệm thu runtime ngày 18/10](evidence/kaggle-t4x2-studio-acceptance-2026-10-18.json) xác nhận ảnh dual-T4 và View/Download trên Studio, không đồng nghĩa notebook đã tái lập từ đầu.
- CI GitHub kiểm tra cấu trúc mã nguồn/tài liệu, không thay thế kiểm thử GPU trong runtime mới.
- Việc duyệt giao diện gallery không có nghĩa mọi prompt đều đạt đầy đủ tiêu chí chất lượng thị giác và độ bám sát nội dung.
- Cài đặt sạch trên Kaggle T4×2 và chạy lại đầu-cuối: **PENDING**.

## Phân phối và hỗ trợ
- Không đóng gói model weights bên thứ ba; attach model và dataset hỗ trợ trên Kaggle.
- GitHub Release cung cấp archive 170 ảnh có watermark đã duyệt (48 ảnh chất lượng và 122 ảnh benchmark), kèm HTML gallery song ngữ. Bộ media gốc không watermark được giữ riêng tư.
- HTTPS tunnel hoạt động tạm thời, bản demo không cam kết SLA vận hành production.

Xem [tổng quan kỹ thuật](docs/engineering-overview.vi.md), [môi trường tương thích](docs/runtime-compatibility.vi.md), [chỉ mục bằng chứng](docs/evidence-index.vi.md) và [giấy phép](LICENSE-NOTES.vi.md).
