# Triển khai Kaggle

> 🌐 Language / Ngôn ngữ: [English](kaggle.md) | **Tiếng Việt**

Chọn Tesla T4 ×2, bật Internet và attach model GGUF Q6_K cùng dataset hỗ trợ theo README. Chạy notebook tuần tự để clone mã, kiểm tra GPU/model, chuẩn bị thư viện, khởi động API/consumer, mở hai tunnel gallery/Studio. Tài khoản Studio chỉ in để người xem demo sử dụng; không công khai khóa backend. Khi chạy lại notebook phải giữ trạng thái job hiện hữu. URL Cloudflare là tạm thời. Notebook tải và kiểm tra SHA256 của archive gallery 170 ảnh có watermark từ GitHub Release v1.0.0 (48 ảnh chất lượng và 122 ảnh benchmark), kèm HTML gallery song ngữ. Nếu không tải được gallery tùy chọn, Studio vẫn có thể chạy độc lập. Chỉ sử dụng archive gallery đã ghim SHA256 trong Release. Việc tái lập đúng toàn bộ phiên bản vendor từ runtime sạch chưa được kiểm chứng.


Bản cập nhật notebook: GitHub Release v1.0.0 cung cấp gói 170 ảnh có watermark (48 ảnh chất lượng + 122 ảnh benchmark), kèm hai gallery EN/VI trên cùng tunnel. Chưa xác nhận chạy lại toàn bộ notebook trên một môi trường Kaggle sạch.
