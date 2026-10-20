# Z-Image-Turbo GGUF Q6_K — Hệ thống tạo ảnh AI hai GPU trên Kaggle

[![Repository audit](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml/badge.svg)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml)
[![Technical preview](https://img.shields.io/badge/Release-v1.0.0-2864b4)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0)
[![License: MIT](https://img.shields.io/badge/Project-MIT-2ea44f)](LICENSE)
[![Upstream model: Apache 2.0](https://img.shields.io/badge/Upstream%20model-Apache--2.0-1565c0)](LICENSE-NOTES.vi.md)
[![Kaggle T4 x2](https://img.shields.io/badge/Kaggle-Tesla%20T4%20%C3%97%202-20beff)](docs/runtime-compatibility.vi.md)
[![GGUF Q6_K](https://img.shields.io/badge/GGUF-Q6__K-7350a2)](manifests/model.json)

**Ngôn ngữ:** [English](README.md) · Tiếng Việt

**Bản phát hành:** [v1.0.0](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0) · **Nền tảng:** Kaggle, NVIDIA Tesla T4 ×2 · **Đầu ra:** PNG 1024 × 1024

> **Dự án trình diễn tạo ảnh AI dựa trên bằng chứng thực nghiệm, không phải dịch vụ production đang vận hành.** Dự án triển khai Z-Image-Turbo định dạng GGUF Q6_K trên hai GPU Tesla T4 của Kaggle, gồm mã hóa prompt có giới hạn trên GPU0, hai inference worker độc lập trên GPU0/GPU1, Studio tạo ảnh có xác thực và bộ gallery benchmark có thể kiểm tra lại. Repository công bố mã nguồn, notebook khởi chạy trên Kaggle, bằng chứng kiểm thử GPU/trình duyệt và gallery 170 ảnh để người đọc có thể xem xét, đối chiếu và tự triển khai.

**Khám phá:** [Kiến trúc hệ thống](#kiến-trúc-hệ-thống) · [Bằng chứng thực nghiệm](#bằng-chứng-thực-nghiệm-và-trạng-thái-nghiệm-thu) · [Gallery 170 ảnh](#hai-gallery-170-ảnh-trên-release) · [Chạy trên Kaggle](#chạy-demo-trên-kaggle) · [Cấu trúc source](#cấu-trúc-repository) · [Bảo mật và giới hạn](#bảo-mật-và-các-giới-hạn)

## Mục tiêu và bài toán kỹ thuật

Chạy model tạo ảnh đã lượng tử hóa trên hai Tesla T4 với bộ nhớ GPU giới hạn không chỉ là bài toán nạp model. Hệ thống phải kiểm soát VRAM khi mã hóa prompt, phân phối công việc thực sự cho từng GPU, quản lý vòng đời job, đảm bảo quyền sở hữu và toàn vẹn của ảnh PNG, đồng thời hiển thị trạng thái và thời gian xử lý rõ ràng trên trình duyệt. Repository này tập hợp source code, các điểm khởi chạy, phép kiểm thử CPU tự động và bằng chứng nghiệm thu để người khác có thể đánh giá từng vấn đề đó.

Đối tượng hướng tới là kỹ sư AI/ML muốn tìm hiểu **cách xây dựng và kiểm chứng một demo inference hai GPU trên Kaggle**. Hai worker thể hiện khả năng chạy inference độc lập trên hai GPU, không đồng nghĩa một ảnh sẽ được tạo nhanh gấp đôi.

## Những thành phần đã xây dựng

| Thành phần | Thiết kế và giá trị kiểm chứng |
|---|---|
| Model và phần cứng | Z-Image-Turbo định dạng GGUF **Q6_K** trên **Tesla T4 ×2**; model weights không được commit vào Git. |
| Thực thi hai GPU | Mã hóa prompt có giới hạn trên **GPU0**; hai inference worker độc lập chạy trên **GPU0** và **GPU1**. Bằng chứng lịch sử ghi nhận worker ID và hoạt động thực tế của cả hai GPU. |
| Điều phối job | Vòng đời job lưu trong SQLite, cơ chế consumer, trạng thái phiên và khôi phục; thời gian chờ queue không bị đánh đồng với thời gian tính toán trên GPU. |
| Studio có xác thực | Giao diện Vue và gateway hỗ trợ nhập prompt, theo dõi trạng thái, xem/tải PNG và hiển thị thời gian xử lý theo giây. |
| Toàn vẹn dữ liệu ảnh | PNG lưu riêng tư, kiểm tra quyền sở hữu theo job và biên nhận SHA256; truy xuất ảnh qua API có xác thực. |
| Quy trình khởi chạy | Notebook Kaggle clone source từ Git tag phát hành, kiểm tra model/GPU, chuẩn bị gói phụ thuộc có kiểm SHA256 và khởi chạy các dịch vụ demo cục bộ. |
| Minh chứng trực quan | **Gallery chất lượng 48 ảnh** và **gallery kiểm thử/benchmark 122 ảnh**, phát hành chung trong một archive đã watermark và kiểm SHA256. |
| Hồ sơ kỹ thuật | Tài liệu EN/VI, manifest môi trường, kiểm thử CPU/bảo mật và JSON nghiệm thu có phân biệt rõ hạng mục đã xác minh với hạng mục còn chờ. |

## Kiến trúc hệ thống

```text
Kaggle runtime · NVIDIA Tesla T4 ×2

Trình duyệt ── HTTPS Quick Tunnel (Studio) ── Gateway xác thực :18789
                                                      │
                                                API riêng tư :18788
                                                      │
                                         SQLite jobs / trạng thái phiên
                                                      │
                                         Mã hóa prompt có giới hạn
                                                    GPU0
                                                      │
                                             Điều phối job GPU
                                            /                 \
                                  Inference worker 0     Inference worker 1
                                    Tesla T4 / GPU0       Tesla T4 / GPU1
                                            \                 /
                                          PNG + biên nhận SHA256
                                                      │
                                            Xem / Tải có xác thực

Trình duyệt ── HTTPS Quick Tunnel riêng ── Hai webserver gallery độc lập :18881 / :18882
                                                  ├─ Gallery chất lượng 48 ảnh
                                                  └─ Gallery benchmark 122 ảnh
```

**Điểm cần hiểu đúng:** GPU0 vừa đảm nhiệm mã hóa prompt vừa chạy worker inference, không phải GPU chỉ dùng cho text encoder. Hai worker độc lập cho phép xử lý đồng thời những công việc phù hợp, nhưng tốc độ thực tế vẫn phụ thuộc vào bước mã hóa, VRAM, queue và thời gian khởi tạo. Bằng chứng hai GPU cùng hoạt động không tự động chứng minh hiệu năng tăng tuyến tính. Tunnel Studio chỉ trỏ vào **gateway xác thực**, **không** công khai API riêng tư. Xem [kiến trúc chi tiết](docs/architecture.vi.md) · [API](docs/api.vi.md).

## Bằng chứng thực nghiệm và trạng thái nghiệm thu

Bảng này phân biệt bằng chứng của runtime đã chạy, phần giao diện/ảnh được người dùng nghiệm thu, kiểm tra CI và các việc còn phải thực hiện. Một lần PASS chỉ có giá trị trong phạm vi phiên và điều kiện kiểm thử đã ghi nhận; không tự động áp dụng cho phiên Kaggle mới.

| Hạng mục | Kết quả ghi nhận | Bằng chứng và phạm vi |
|---|---|---|
| Inference hai GPU | **PASS — 2/2 job** hoàn thành trên worker GPU0/GPU1, biên nhận PNG riêng tư được xác minh SHA256; cùng một mẫu đo ghi nhận **GPU0=100%, GPU1=100%**. | [Nghiệm thu dual-GPU, 16/10](evidence/dual-gpu-inference-acceptance-2026-10-16.json); đây là bằng chứng có giới hạn, không phải benchmark khả năng mở rộng. |
| Tạo ảnh qua trình duyệt | **PASS** với PNG **1024 × 1024**, xem/tải ảnh được và không ghi nhận lỗi JavaScript. | [Nghiệm thu trình duyệt, 16/10](evidence/browser-image-generation-acceptance-2026-10-16.json). |
| Studio trên runtime tham chiếu | **PASS** xác thực, View/Download và mức độ phù hợp prompt đã được người dùng kiểm tra; **5 job completed, 1 job cancelled** trong tập kết quả ghi nhận. | [Nghiệm thu Kaggle/Studio, 18/10](evidence/kaggle-t4x2-studio-acceptance-2026-10-18.json); không phải kết quả chạy notebook sạch. |
| Đo thời gian pha GPU | Năm kết quả lịch sử của **pha diffusion 9 bước**: **234, 236, 246, 247, 262 giây** (theo tập ghi nhận). | [Báo cáo 18/10](evidence/kaggle-t4x2-studio-acceptance-2026-10-18.json). Các giá trị này **không bao gồm đầy đủ** queue/setup/encoding/saving; không được gọi là thời gian toàn bộ một job. |
| Hiển thị thời gian trên Studio | **PASS — 6/6** hàng job completed có hiển thị tổng thời gian theo giây trong lần kiểm tra HTTPS trước. | [Nghiệm thu elapsed time](evidence/studio-elapsed-time-acceptance-2026-10-16.json). |
| Gói gallery công khai | **170 PNG = 48 ảnh chất lượng + 122 ảnh benchmark**, kèm **40 thumbnail WebP**; bản *giao diện và watermark* đã được duyệt và đưa lên Release `v1.0.0`. | [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0); duyệt cách trình bày không có nghĩa 100% prompt đạt chất lượng. |
| GitHub repository audit | **PASS** với commit chỉnh lý README gần nhất; kiểm tra cú pháp Python/notebook, tài liệu song ngữ, bảo mật và CPU contracts. | [GitHub Actions](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml). CI không thay thế kiểm thử inference bằng GPU. |

**Phạm vi tái lập:** Notebook phát hành chưa được kiểm thử đầu-cuối trên một phiên Kaggle T4×2 mới hoàn toàn; bằng chứng GPU/Studio đã công bố áp dụng cho các runtime tham chiếu được ghi nhận. Đây là giới hạn xác minh khi tái lập, không có nghĩa hệ thống demo đã thực hiện là chưa hoàn thành.

Các số liệu trên chứng minh hệ thống đã từng tạo ảnh thật trên GPU, nhưng **không** đủ để khẳng định tốc độ chuẩn cho mọi ảnh, thông lượng ảnh/giờ liên tục hoặc tỷ lệ đạt yêu cầu ngữ nghĩa 100%. Xem [phương pháp benchmark](docs/benchmark.vi.md) và [chỉ mục bằng chứng](docs/evidence-index.vi.md).

## Hai gallery 170 ảnh trên Release

Giá trị của gallery không chỉ nằm ở ảnh cuối: prompt, seed, thông tin GPU/runtime khi có, liên hệ giữa original–retry, trạng thái duyệt và SHA256 cho phép người xem đánh giá quá trình thực nghiệm, thay vì chỉ nhìn một số thumbnail đẹp đã tuyển chọn.

| Bộ ảnh | Nội dung | Ý nghĩa đánh giá |
|---|---|---|
| **Gallery chất lượng 48 ảnh** | **48 PNG** thuộc bộ gallery chất lượng đã được duyệt, kèm **40 thumbnail WebP** để xem nhanh. | Thể hiện độ đa dạng hình ảnh và quy trình duyệt của con người. Các trạng thái original/retry, pending/rejected vẫn được giữ lại; không tuyên bố mọi prompt đều thành công. |
| **Gallery test & benchmark 122 ảnh** | **122 PNG** có metadata theo từng ảnh và thông tin chạy lịch sử. Có thể xem thông tin worker và lần chạy của từng ảnh trong metadata kèm theo. | Bộ kiểm thử và minh chứng kỹ thuật, không phải 122 ý tưởng mỹ thuật độc lập đều đã qua nghiệm thu chất lượng. |

Cả hai website tĩnh đều hỗ trợ **English/Tiếng Việt**, tìm kiếm/lọc, modal xem ảnh, điều hướng bàn phím, giao diện responsive và liên kết qua lại. Bản public sử dụng cách trình bày có watermark đã được duyệt. Bộ ảnh PNG gốc không watermark được lưu **riêng tư**, không nằm trong repository hoặc Release công khai.

**Artifact công khai:** [`zimage-gallery-170-watermarked-public-v1.0.0.tar.gz`](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/zimage-gallery-170-watermarked-public-v1.0.0.tar.gz)

**SHA256:** `e0240d7bc60314f9e8394b5afd922a330216ecd6b596122e381f0bab3e755997`

**Bao gồm:** bộ 170 PNG, thumbnail và giao diện gallery song ngữ đã được duyệt. Ảnh nằm trong **GitHub Release asset**, không được commit vào Git hoặc đóng gói thành dataset Kaggle chứa source code.

Có thể xem hai gallery công khai trên máy Linux/macOS mà **không cần GPU**: tải archive, kiểm SHA256, giải nén và mở webserver tại thư mục gốc:

```bash
curl -fL -o zimage-gallery-170-watermarked-public-v1.0.0.tar.gz \
  https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/zimage-gallery-170-watermarked-public-v1.0.0.tar.gz
printf '%s  %s\n' \
  e0240d7bc60314f9e8394b5afd922a330216ecd6b596122e381f0bab3e755997 \
  zimage-gallery-170-watermarked-public-v1.0.0.tar.gz | sha256sum -c -
tar -xzf zimage-gallery-170-watermarked-public-v1.0.0.tar.gz
find . -name index.html -print
# Phục vụ thư mục đã giải nén chứa các gallery HTML.
python3 -m http.server 8080 --bind 127.0.0.1
```

Mở các đường dẫn `index.html` mà lệnh `find` liệt kê tại `http://127.0.0.1:8080/`; cấu trúc thư mục thực tế lấy theo archive. Trong notebook Kaggle, hai gallery này được phục vụ độc lập với Studio xác thực và có thể nhận đường dẫn HTTPS tạm.

## Chạy demo trên Kaggle

### Điều kiện cần

- Notebook Kaggle chọn accelerator **Tesla T4 ×2**, bật **Internet** khi cài đặt dependency và tải Release lần đầu.
- Attach model GGUF **`dangkhoa2016/unsloth-z-image-turbo-gguf`**, biến thể **`q6-k`**, phiên bản **1** (`z-image-turbo-Q6_K.gguf`).
- Attach support components **`dangkhoa2016/z-image-turbo-diffusers-support-components`** (text encoder và VAE cần thiết). Đây là **đầu vào của model**, không phải dataset riêng để lưu source code ứng dụng.
- Source code được clone trực tiếp từ GitHub theo tag **`v1.0.0`**. Cần kiểm tra commit SHA thực tế sau checkout; tag có thể được cập nhật, không tương đương với commit SHA bất biến.

### Các bước khởi chạy

1. Mở [`notebooks/kaggle-dual-gpu-production-demo.ipynb`](notebooks/kaggle-dual-gpu-production-demo.ipynb) (cũng có bản notebook tải riêng tại [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/kaggle-dual-gpu-production-demo.ipynb)).
2. Bật GPU T4×2, Internet và attach hai input model/support đúng như trên.
3. Chạy notebook **theo thứ tự**: clone/kiểm source → xác minh GPU và input → bootstrap các thư viện đã khóa hash và preflight → khởi động private API và Studio xác thực → bật GPU consumer.
4. Để kiểm tra inference thật, gửi **hai prompt phân biệt** từ Studio, sau đó xem GPU assignment, PNG, receipt và các trường đo thời gian của từng job. Notebook **không tự sinh ảnh thử nghiệm** khi khởi chạy.
5. Nếu muốn xem gallery, chạy cell khôi phục bộ 170 ảnh công khai; notebook tự tải archive từ Release, kiểm SHA256 và manifest, rồi mở cả hai gallery trên một webserver tĩnh.
6. Mở hai liên kết Quick Tunnel riêng cho Studio và gallery. Notebook in **tài khoản demo dùng tạm**; không in token API/service nội bộ ra output công khai.

**Tổ chức notebook:** 18 cell, gồm các cell gallery tùy chọn và một tunnel HTTPS riêng cho Studio. Gateway Studio dùng localhost **`:18789`**, API riêng tư **`:18788`**, server gallery chất lượng **`:18881`** và server gallery benchmark **`:18882`**. URL Quick Tunnel biến mất khi tiến trình/runtime dừng; dữ liệu trong môi trường Kaggle có thể mất nếu chưa được xuất ra nơi lưu trữ khác.

**Hướng dẫn tái lập:** khi khởi chạy trên một runtime Kaggle mới, hãy kiểm tra hai GPU worker, thao tác submit/View/Download trên trình duyệt đã đăng nhập, tính toàn vẹn của ảnh và khả năng truy cập hai gallery. Các kết quả chạy trước đây phản ánh môi trường tham chiếu, không phải cam kết mọi runtime mới sẽ có kết quả giống hệt. Xem [hướng dẫn Kaggle](docs/kaggle.vi.md) · [tương thích runtime](docs/runtime-compatibility.vi.md) · [khắc phục lỗi](docs/troubleshooting.vi.md).

## Cấu trúc repository

```text
Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/
├── README.md / README.vi.md              # Điểm vào tài liệu song ngữ
├── notebooks/                             # Notebook demo Kaggle
├── product-studio/                        # Giao diện Vue và gateway xác thực
├── production-system/                    # Queue, inference, session, worker, artifact
│   ├── studio-demo/                       # API/consumer/khởi chạy demo cục bộ
│   └── private-artifact-store/            # Quyền sở hữu job, receipt, truy xuất PNG
├── deployment/                           # Các lệnh start/resume
├── scripts/                              # Checkout, bootstrap, CPU/security tests
├── manifests/                            # Model, support và lock tương thích
├── evidence/                             # JSON nghiệm thu lịch sử đã làm sạch
├── docs/                                 # Kiến trúc và hướng dẫn kỹ thuật EN/VI
├── .github/workflows/                    # Workflow kiểm toán repository
├── RELEASE_NOTES_v1.0.0.md               # Thông tin bản phát hành kỹ thuật
└── LICENSE / LICENSE-NOTES.md            # Phạm vi MIT và giấy phép upstream
```

**Git source không phải nơi phân phối model:** repository không chứa weights GGUF, các checkpoint tokenizer/encoder, PNG riêng tư của job, SQLite runtime hoặc file bí mật. Bộ **170 ảnh có watermark** được phát hành riêng dưới dạng GitHub Release asset.

### Kiểm tra source khi không có GPU

Trong môi trường Python đã cài các dependency cần thiết, repository có các lệnh:

```bash
python scripts/run_cpu_tests.py
python scripts/scan_secrets.py
```

Workflow [repository audit](.github/workflows/repository-audit.yml) tự kiểm tra cú pháp/tài liệu và CPU/security contracts. Bốn thư viện vendor đã xác minh version và SHA256 của wheel/cây file trong [`manifests/runtime-compatibility.json`](manifests/runtime-compatibility.json): Diffusers **0.41.0**, Hugging Face Hub **1.28.0**, TorchAO **0.15.0**, GGUF **0.17.1**. Đây là chuẩn tham chiếu **vendor/CPU**, **không** phải GPU version lock hoàn chỉnh; phiên bản PyTorch/CUDA/Transformers/Accelerate vẫn cần đo lại trên runtime T4×2 mục tiêu.

## Bảo mật và các giới hạn

- **Phạm vi demo:** không cung cấp SLA, endpoint công khai lâu dài, bảo đảm autoscale hoặc chứng nhận production. CI PASS không đồng nghĩa inference GPU ở runtime mới đã PASS.
- **Ranh giới truy cập:** chỉ đưa gateway Studio có xác thực ra ngoài qua Cloudflare; giữ API riêng tư, service key và receipt nội bộ phía sau. Gallery là artifact công khai **đã watermark**, được phục vụ độc lập.
- **Dữ liệu tạm thời:** process Kaggle, SQLite cục bộ, PNG chưa xuất và URL Quick Tunnel có thể biến mất sau khi tắt phiên. Cần tải/xuất kết quả riêng tư cần giữ lại trước khi dừng runtime.
- **Cách diễn giải kết quả:** hai worker hoạt động đồng thời khác với job xếp hàng; thời gian diffusion 9 bước khác với tổng thời gian một job; duyệt giao diện gallery khác với đánh giá prompt-adherence hoặc chất lượng của mọi ảnh.

## Tài liệu kỹ thuật liên quan

| Chủ đề | English | Tiếng Việt |
|---|---|---|
| Kiến trúc | [Architecture](docs/architecture.md) | [Kiến trúc](docs/architecture.vi.md) |
| Cài đặt Kaggle | [Kaggle guide](docs/kaggle.md) | [Hướng dẫn Kaggle](docs/kaggle.vi.md) |
| API và Studio | [API](docs/api.md) | [API](docs/api.vi.md) |
| Môi trường chạy | [Compatibility](docs/runtime-compatibility.md) | [Tương thích](docs/runtime-compatibility.vi.md) |
| Benchmark | [Benchmarks](docs/benchmark.md) | [Benchmark](docs/benchmark.vi.md) |
| Bằng chứng | [Evidence index](docs/evidence-index.md) | [Chỉ mục bằng chứng](docs/evidence-index.vi.md) |
| Triển khai | [Deployment profile](docs/deployment-profile.md) | [Cấu hình triển khai](docs/deployment-profile.vi.md) |
| Tổng quan kỹ thuật | [Engineering overview](docs/engineering-overview.md) | [Tổng quan kỹ thuật](docs/engineering-overview.vi.md) |
| Phát hành | [Release notes](RELEASE_NOTES_v1.0.0.md) | [Ghi chú phát hành](RELEASE_NOTES_v1.0.0.vi.md) |
| Thay đổi | [Changelog](CHANGELOG.md) | [Nhật ký thay đổi](CHANGELOG.vi.md) |

Các chính sách bổ sung: [Bảo mật](SECURITY.vi.md) · [Đóng góp](CONTRIBUTING.vi.md) · [Cam kết dự án](PROJECT-CONTRACT.vi.md) · [Khắc phục lỗi](docs/troubleshooting.vi.md).

## Giấy phép và ghi nhận tác giả

Mã nguồn và tài liệu do dự án tự phát triển: **MIT License**, © 2026 **Đăng Khoa** ([i.am@dangkhoa.dev](mailto:i.am@dangkhoa.dev)). MIT của dự án **không thay thế giấy phép** của Z-Image-Turbo, weights GGUF hoặc các thư viện bên thứ ba. Họ model Z-Image và bản lượng tử hóa tham chiếu có thông báo upstream Apache-2.0 riêng; cần giữ nguyên điều khoản và xác minh quyền sử dụng cho trường hợp cụ thể. Xem [ghi chú giấy phép](LICENSE-NOTES.vi.md), [bản giấy phép upstream](THIRD_PARTY_LICENSES/Z-IMAGE-APACHE-2.0) và [dự án Z-Image gốc](https://github.com/Tongyi-MAI/Z-Image).

---

**Định vị dự án:** hệ thống demo tạo ảnh trên hai Tesla T4 có bằng chứng kỹ thuật, mã nguồn, notebook khởi chạy và gallery song ngữ đã được công bố. Người đọc có thể triển khai và xác minh lại trên môi trường của mình, với các giới hạn thực nghiệm được ghi nhận rõ ràng.
