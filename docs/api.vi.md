# API và Studio

> 🌐 Language / Ngôn ngữ: [English](api.md) | **Tiếng Việt**

Vue Studio v3 có session của gateway và xác thực dịch vụ nội bộ. Gửi prompt qua POST /v1/jobs, đọc danh sách và trạng thái qua GET /v1/jobs và GET /v1/jobs/{job_id}; lấy ảnh PNG đã hoàn thành qua GET /v1/studio/jobs/{job_id}/image. Total Ns tính từ created_at đến updated_at, không phải inference time thuần. Khi nhấn View, SVG loading xuất hiện cho tới khi lấy ảnh và prompt xong. Tunnel công khai chỉ trỏ đến 18789, không mở API 18788; không công khai service token.
