# Tổng quan kỹ thuật và nguồn gốc dự án

> 🌐 Language / Ngôn ngữ: [English](engineering-overview.md) | **Tiếng Việt**

Repository công bố source snapshot của dự án Z-Image-Turbo GGUF trên Kaggle Tesla T4 ×2, đã có quá trình thử nghiệm GPU, đánh giá chất lượng ảnh, điều phối job, tạo ảnh qua trình duyệt và Vue Studio xác thực trước ngày đưa lên GitHub 16/10/2026.

**Minh bạch về timestamp Git:** 39 commit là lịch sử được tái cấu trúc từ snapshot. AuthorDate và CommitterDate hiển thị được **phân nhóm biên tập** vào ba ngày **14, 15 và 16/10/2026** để dễ review. Đây **không phải ngày giờ tạo commit hay viết từng module gốc đã được xác minh**. SHA và thời điểm rewrite/publication thực tế còn lưu ở lịch sử Git backup cùng báo cáo đối chiếu, không phải các timestamp được tái dựng này.

Ba giai đoạn lần lượt gồm: hạ tầng/inference và kiểm thử; Studio integration và tài liệu; evidence, hướng dẫn và chuẩn bị phát hành. Không được diễn giải ngày phân nhóm thành bằng chứng năng suất coding theo từng ngày. Pilot32 visual QC trước đây vẫn **NOT_PASS**; kiểm thử trên runtime Kaggle sạch vẫn **PENDING**.
