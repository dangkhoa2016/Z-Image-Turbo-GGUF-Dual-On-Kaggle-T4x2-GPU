# Tổng quan kỹ thuật và nguồn gốc dự án

> 🌐 Language / Ngôn ngữ: [English](engineering-overview.md) | **Tiếng Việt**

Z-Image-Turbo GGUF Dual trải qua nhiều phiên thử nghiệm Kaggle GPU, gồm suy luận dual-worker, hàng đợi, đánh giá chất lượng ảnh và kiểm thử Vue Studio có xác thực trên trình duyệt. PASS kỹ thuật không đồng nghĩa PASS chất lượng ảnh: Pilot32 trước đây **NOT_PASS** và kiểm thử Kaggle T4×2 từ môi trường sạch vẫn **PENDING**.

## Lịch sử công bố mã nguồn

39 commit được tổ chức từ source snapshot đã tồn tại để thuận tiện cho việc review. Ngày tác giả phân nhóm 14–16/10/2026 là **mốc giai đoạn biên tập, không phải timestamp gốc đã khôi phục của từng module**. Snapshot được công bố lần đầu ngày 16/10/2026. Các Git object trước khi chỉnh được giữ ở archive branches. Phân biệt này không làm thay đổi bằng chứng GPU hay trạng thái các quality gate.
