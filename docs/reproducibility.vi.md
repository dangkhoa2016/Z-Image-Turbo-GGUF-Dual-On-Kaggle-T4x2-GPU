# Trạng thái tái lập

> 🌐 Language / Ngôn ngữ: [English](reproducibility.md) | **Tiếng Việt**

Repository chủ động không chứa thư viện vendor lớn, weights GGUF, safetensors, PNG hay database riêng tư. Archive branch lưu lại snapshot Git ban đầu để truy nguyên. Cài dependencies cho runtime Kaggle sạch CHƯA PASS: còn cần ghim đúng phiên bản vendor và kiểm thử. Workspace Kaggle ban đầu có sẵn môi trường đã chạy thành công GPU thật. Clone Git không thể khôi phục các session cũ. Nếu cần backup phải lưu SQLite, artifact, checksum riêng và có bảo vệ. Chỉ đánh dấu PASS runtime mới sau khi chạy E2E thật với hai GPU.
