# API và Studio

> 🌐 Language / Ngôn ngữ: [English](api.md) | **Tiếng Việt**

Vue Studio kiểm soát truy cập bằng phiên đăng nhập gateway và thông tin xác thực backend riêng tư. Gửi prompt qua POST /v1/jobs, đọc danh sách và trạng thái qua GET /v1/jobs và GET /v1/jobs/{job_id}; lấy ảnh PNG đã hoàn thành qua GET /v1/studio/jobs/{job_id}/image. Thời gian end-to-end được ghi rõ là bao gồm queue/setup. Thời gian generation đo từ worker được hiển thị khi có dữ liệu; các job lịch sử hiển thị thời gian GPU diffusion (9 bước) khôi phục từ log và không đồng nhất với tổng thời gian xử lý. Khi nhấn View, SVG loading xuất hiện cho tới khi lấy ảnh và prompt xong. Tunnel công khai chỉ trỏ đến 18789, không mở API 18788; không công khai service token.
