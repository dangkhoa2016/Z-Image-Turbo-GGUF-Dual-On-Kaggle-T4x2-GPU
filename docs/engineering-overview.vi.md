# Tổng quan kỹ thuật

> 🌐 Language / Ngôn ngữ: [English](engineering-overview.md) | **Tiếng Việt**

Z-Image-Turbo GGUF Dual là hệ thống trình diễn tạo ảnh trên Kaggle Tesla T4 ×2, mã hóa prompt có giới hạn và worker inference độc lập. Hệ thống bao gồm hàng đợi có nhận thức phiên, biên nhận artifact độc lập, Vue Studio xác thực và notebook khởi chạy.

## Bằng chứng kỹ thuật và giới hạn

Source hiện tại gồm GPU orchestration, Studio có xác thực và hai gallery tĩnh. Kết quả nghiệm thu Run All và browser được công bố theo từng Git SHA trên [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0). Việc duyệt giao diện gallery không chứng minh tất cả ảnh đã tạo đều đáp ứng đầy đủ tiêu chí chất lượng và độ bám sát prompt. Không khẳng định GPU PASS hoặc tái lập độc lập nếu chưa có evidence khớp Git SHA.

## Tài liệu tham khảo kỹ thuật

Xem [kiến trúc](architecture.vi.md), [môi trường tương thích](runtime-compatibility.vi.md) và [chỉ mục bằng chứng](evidence-index.vi.md) để tìm hiểu chi tiết triển khai và phạm vi kiểm thử đã xác minh.
