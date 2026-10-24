# Chạy trên Kaggle

> 🌐 Language / Ngôn ngữ: [English](kaggle.md) | **Tiếng Việt**

## Notebook Kaggle chính thức và phạm vi nghiệm thu

Mở [notebook production duy nhất](../notebooks/kaggle-dual-gpu-production-demo.ipynb) từ nhánh `main`, chọn Tesla T4 ×2, bật Internet, attach GGUF Q6_K v1 và support dataset. Run All mặc định sinh hai ảnh thật, kiểm SHA256 và bật Studio/Gallery. Model Qwen3/GGUF staging trong `/tmp`; source/log/PNG/ZIP ở `/kaggle/working`; cả hai ổ được kiểm tra dung lượng trước khi nạp GPU.

**Chỉ test Studio**: ở runtime mới chạy **code cell 3, 5, 7, 16, 18**, gửi prompt qua Studio rồi chạy **cell 27** để monitor chỉ đọc liên tục. Không tính đây là fresh Run All. Nghiệm thu Studio yêu cầu job `ARCHIVED` và PNG được kiểm SHA256; muốn Run All đầy đủ cần chạy đủ 28 cell. Không công khai mật khẩu demo đang có hiệu lực.

## Chuẩn bị
Sử dụng Kaggle notebook có **Tesla T4 ×2**, Internet, model GGUF và support dataset theo [README tiếng Việt](../README.vi.md). Notebook chính thức mặc định lấy source từ **`main`**. Muốn tái lập đúng một revision không đổi, đặt `ZIMAGE_SOURCE_SHA` thành Git SHA đầy đủ 40 ký tự trước cell tải source. Nhánh `main` luôn có thể tiếp tục thay đổi nên không phải revision bất biến.

## Dung lượng lưu trữ và bằng chứng lịch sử

Notebook chính thức kiểm tra dung lượng cả `/tmp` và `/kaggle/working` trước khi chạy GPU. Staging local có xác minh hash cần khoảng 8,05 GB cho Qwen3, 5,91 GB cho GGUF và dự phòng 3 GiB. Chỉ đặt `ZIMAGE_GGUF_SOURCE_MODE=auto` trước Bước 02 khi chủ động chấp nhận khả năng đọc trực tiếp chậm ở cold-start.

Kết quả P2.3 sinh ảnh bằng hai GPU và P2.7 load-only đã PASS trong các phiên Kaggle tương ứng; chúng không thay thế việc chạy lại đầu-cuối trên runtime sạch từ notebook công khai hiện hành. Run All hiện tại xuất `p23-runall-acceptance.zip` với PNG, provenance và log chẩn đoán giới hạn. Kiểm tra thông tin đăng nhập còn hiệu lực trước khi công bố output.

## Chạy minh chứng GPU trực tiếp trong notebook
Thực hiện lần lượt **28 cell**. Sau khi clone source, kiểm tra GPU/model và bootstrap vendor, các bước **04–06** mã hóa hai prompt trên GPU0, chạy hai GGUF worker độc lập GPU0/GPU1, kiểm SHA256 của hai PNG 1024 × 1024 và hiển thị kết quả. Kết quả notebook đã xác minh trong cùng workspace được dùng lại; dữ liệu chưa hoàn chỉnh sẽ khiến notebook dừng an toàn. Ảnh do Studio tạo không thay thế minh chứng GPU notebook-native.

## Chọn nguồn GGUF và so sánh A/B có kiểm soát
Thư viện mặc định `auto`, nhưng notebook dual-GPU Run All chủ động mặc định `local` để giảm nguy cơ cold-start. Trước cell 12 có thể đặt ZIMAGE_GGUF_SOURCE_MODE thành auto, direct hoặc local. **auto** tái sử dụng bản local có SHA256 hợp lệ nếu đã tồn tại, nếu không đọc thẳng GGUF từ Kaggle input mà không sao chép 5,9 GB. **direct** luôn dùng model gốc và bỏ qua staging; đường đọc trực tiếp từng gặp timeout nên không đảm bảo nhanh hơn. **local** chủ động sao chép GGUF streaming và kiểm SHA256 trước khi nạp worker; cache hỏng luôn dừng an toàn, không tự ghi đè.

Cell 12 ghi gguf-source-selection-*.json bao gồm chế độ yêu cầu/thực tế và thời gian chọn nguồn. File model-startup-*.jsonl ghi chế độ GGUF cùng các mốc thời gian, CPU, RAM và I/O từng worker. Báo cáo cuối phân biệt thời gian chọn nguồn, khởi tạo model và sinh ảnh song song. Chỉ so sánh direct và local trên cùng phần cứng/model/runtime; giữ mọi log và ảnh đã xác minh. Không chạy lại công việc tạo ảnh đã hoàn thành chỉ để benchmark; dùng phiên biệt lập hoặc bài thử khởi tạo model riêng. Thay đổi này chưa giải quyết nút thắt chuyển Qwen3 từ CPU sang CUDA.


## Theo dõi CPU, RAM và I/O khi Qwen3 đang tải
Bước 04 thống kê dung lượng các shard trọng số Qwen3 và đọc thử tối đa 4 MiB từ một shard. Kết quả có thể dùng page cache, không phải benchmark cold-start. Trong lúc tải model, notebook đo đúng tiến trình con encode_batch_gpu.py mỗi 15 giây (CPU, RSS, page faults, read_bytes và rchar); bộ nhớ và mức sử dụng GPU được đo khoảng 30 giây/lần. Hãy giữ lại encoder-resources-*.jsonl cùng encoder.log để phân tích. read_bytes bằng 0 không chứng minh model đã ngừng hoạt động do có thể đọc qua cache hoặc memory mapping. Công cụ không thay đổi phép tính Qwen3 hoặc trọng số.

## Telemetry từng giai đoạn của Qwen3 encoder
Cell 10 báo stage gần nhất của encoder mỗi 15 giây; các bản ghi JSON bao gồm thời gian, RSS và I/O được ghi tức thời vào encoder.log. Các giai đoạn gồm import thư viện, tải tokenizer, nạp trọng số Qwen3, chuyển model lên CUDA, mã hóa từng prompt và ghi/xác minh embedding. Phase controller không còn giữ output của encoder cho tới khi subprocess kết thúc. Đây là thời gian đã qua, không phải phần trăm tiến độ. Không thay đổi phép tính model, prompt hoặc dtype. CPU PASS không phải nghiệm thu hiệu năng GPU.

## Chẩn đoán nạp GGUF (công cụ chỉ dùng CPU)
Bước 05 đọc thử 16 MiB GGUF (có thể từ OS cache), ghi CPU, RSS, I/O và page faults của từng worker mỗi 30 giây, đồng thời yêu cầu ghi Python stack vào worker log khoảng 120 giây/lần trong lúc nạp GGUF. Công cụ không thay đổi trọng số model, không khởi động lại inference và không kéo dài timeout 1.200 giây cho mỗi GPU. Khi gặp lỗi, cần lưu worker logs và JSONL telemetry trước khi tắt Kaggle. CPU test PASS không có nghĩa GPU inference đã PASS.

## Trải nghiệm trình duyệt tùy chọn
Cell **15–25** mở Studio có xác thực và GPU consumer, khôi phục gallery 170 ảnh được kiểm SHA256, tạo các HTTPS tunnel tạm riêng cho Studio, gallery 48 ảnh và gallery 122 ảnh. Các cổng nội bộ tương ứng: `18789`, `18881` và `18882`; API riêng tư chỉ nghe tại localhost `18788`. Mật khẩu Studio chỉ dùng cho demo; không công bố notebook đã thực thi khi tunnel và mật khẩu còn hoạt động.

Cell **27–28** cho phép theo dõi Studio chỉ đọc. Monitor hiện tại chạy liên tục cho tới khi người dùng chọn **Interrupt Cell**, không gửi yêu cầu sinh ảnh. Hãy lưu PNG, báo cáo và log trước khi kết thúc phiên Kaggle.

## Trạng thái tái lập
Các bằng chứng GPU và Studio đã PASS chỉ phản ánh những phiên Kaggle đã ghi nhận. Việc chạy toàn bộ notebook **hiện hành** từ một môi trường Kaggle T4×2 sạch vẫn đang chờ nghiệm thu; CPU/CI PASS không đồng nghĩa GPU đã được chạy lại.
