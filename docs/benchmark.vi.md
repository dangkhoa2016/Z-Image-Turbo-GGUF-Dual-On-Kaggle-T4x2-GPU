# Phương pháp benchmark và bằng chứng

> 🌐 Language / Ngôn ngữ: [English](benchmark.md) | **Tiếng Việt**

Các mốc trước đã kiểm thử thật trên T4×2, receipt trong queue và Chromium browser; có inference độc lập GPU0/GPU1. Cần tách thời gian chạy, prompt/seed, worker, SHA256 của PNG và đánh giá chất lượng thị giác. Nội dung media của hai gallery 48/122 ảnh được phân phối qua bundle 170 ảnh trong GitHub Release, không commit trực tiếp vào source repository. Bộ Release 170 ảnh thể hiện những ảnh đã phân phối, không chứng minh tất cả ảnh đều đạt yêu cầu chất lượng hoặc bám sát prompt. Kết quả đánh giá thị giác được phân biệt với PASS về inference kỹ thuật. Việc có code hoặc GPU chưa chứng minh notebook đã chạy E2E từ runtime sạch.
