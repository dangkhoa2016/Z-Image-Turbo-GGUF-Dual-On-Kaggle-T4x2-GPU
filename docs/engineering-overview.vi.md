# Tổng quan kỹ thuật và nguồn gốc dự án

> 🌐 Language / Ngôn ngữ: [English](engineering-overview.md) | **Tiếng Việt**

Z-Image-Turbo GGUF Dual là hệ thống trình diễn tạo ảnh trên Kaggle Tesla T4 ×2, mã hóa prompt có giới hạn và worker inference độc lập. Hệ thống bao gồm hàng đợi có nhận thức phiên, biên nhận artifact độc lập, Vue Studio xác thực và notebook khởi chạy.

## Bằng chứng kỹ thuật và giới hạn

Bốn JSON nghiệm thu lưu lại kết quả chạy dual-GPU, tạo PNG qua trình duyệt, hiển thị thời gian xử lý và truy cập HTTPS trong môi trường Kaggle trước đây; không thay thế kiểm thử cài đặt sạch. Việc duyệt giao diện gallery không chứng minh tất cả ảnh đã tạo đều đáp ứng đầy đủ tiêu chí chất lượng và độ bám sát prompt. Việc chạy đầu-cuối notebook trên Kaggle T4×2 sạch vẫn **PENDING**.

## Phạm vi repository

Repository lần đầu được công bố ngày 16/10/2026 từ source snapshot đã có trước. Git history thể hiện cách tổ chức mã nguồn để công bố, không phải toàn bộ nhật ký các phiên phát triển trước đó. Xem [kiến trúc](architecture.vi.md), [môi trường tương thích](runtime-compatibility.vi.md), và [chỉ mục bằng chứng](evidence-index.vi.md) để review.
