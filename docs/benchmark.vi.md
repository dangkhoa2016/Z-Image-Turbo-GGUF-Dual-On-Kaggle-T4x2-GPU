# Phương pháp benchmark và bằng chứng

> 🌐 Language / Ngôn ngữ: [English](benchmark.md) | **Tiếng Việt**

Fresh validation cần đo inference thật trên T4×2, receipt theo GPU và browser; source review không thay thế nghiệm thu. Cần tách thời gian chạy, prompt/seed, worker, SHA256 của PNG và đánh giá chất lượng thị giác. Nội dung media của hai gallery 48/122 ảnh được phân phối qua bundle 170 ảnh trong GitHub Release, không commit trực tiếp vào source repository. Bộ Release 170 ảnh thể hiện những ảnh đã phân phối, không chứng minh tất cả ảnh đều đạt yêu cầu chất lượng hoặc bám sát prompt. Kết quả đánh giá thị giác được phân biệt với PASS về inference kỹ thuật. Việc có code hoặc GPU không tự chứng minh notebook chạy E2E. Fresh GPU Run All và tái lập độc lập phải có bằng chứng theo đúng Git SHA trên [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0); không sử dụng số đo cũ như benchmark mới.
