# Individual Reflection — Lab 18: Production RAG

**Họ và tên:** Trần Anh Quân
**Khóa:** K4 - Track 3A
**Ngày hoàn thành:** 04/10/2026

---

**Phạm vi thực nghiệm:** Reflection sử dụng lần chạy thành công gần nhất trên 20
câu hỏi và hai file report đã lưu. Tổng thời gian 1246.5 giây. Sau đó API bị giới
hạn request, nên không có số liệu đánh giá mới. Đợt tối ưu chất lượng sau khi đọc
log đã được hoàn tác; các phương án cải thiện chưa được kiểm chứng bằng RAGAS lại.

## Phần 1: Mapping bài giảng (Lecture Mapping)

| Lecture Concept | Module | Hàm cụ thể | Observation & Phân tích |
|----------------|--------|-------------|--------------------------|
| Semantic chunking | M1 | `chunk_semantic()` | Văn bản được tách thành câu hoàn chỉnh, mã hóa bằng `all-MiniLM-L6-v2` và gom nhóm theo cosine similarity. Cách này hạn chế cắt giữa một ý nhưng phải tải thêm embedding model và phụ thuộc threshold. |
| Hierarchical chunking | M1 | `chunk_hierarchical()` | Parent tối đa 2048 ký tự giữ context rộng, child tối đa 256 ký tự tăng độ chính xác retrieval. `parent_id` cho phép truy xuất child nhưng vẫn quay lại parent khi cần thêm ngữ cảnh. |
| Structure-aware chunking | M1 | `chunk_structure_aware()` | Regex nhận diện `#` và `##`, giữ tên section trong metadata. Kỹ thuật này phù hợp với chính sách Markdown, bảng và các mục quy định có cấu trúc. |
| Vietnamese lexical retrieval | M2 | `segment_vietnamese()`, `BM25Search.index()`, `BM25Search.search()` | `underthesea` chuẩn hóa từ tiếng Việt trước BM25. BM25 mạnh với số tiền, số ngày, tên chính sách và các cụm từ chính xác. |
| Dense retrieval | M2 | `DenseSearch.index()`, `DenseSearch.search()` | `BAAI/bge-m3` tạo vector 1024 chiều và Qdrant tìm các đoạn gần nghĩa. Dense search xử lý tốt khác biệt cách diễn đạt nhưng có thể nhầm các phiên bản chính sách gần giống nhau. |
| Hybrid search và RRF | M2 | `reciprocal_rank_fusion()` | RRF cộng điểm theo thứ hạng thay vì trộn trực tiếp score khác thang đo, kết hợp ưu điểm lexical và semantic retrieval. |
| Cross-encoder reranking | M3 | `CrossEncoderReranker.rerank()` | `BAAI/bge-reranker-v2-m3` chấm trực tiếp cặp query-document và chọn top 3. Mục tiêu là cải thiện thứ hạng, đổi lại model lớn và thời gian nạp/chấm cao; chưa có ablation để chứng minh mức tăng chất lượng riêng của reranker. |
| RAGAS 4 metrics | M4 | `evaluate_ragas()` | Faithfulness đo mức bám context; Answer Relevancy đo mức trả lời đúng trọng tâm; Context Precision/Recall đo chất lượng retrieval. Lab cho thấy precision cao không bảo đảm faithfulness cao. |
| Diagnostic failure analysis | M4 | `failure_analysis()` | Điểm trung bình xác định các câu tệ nhất, metric thấp nhất được ánh xạ sang diagnosis và suggested fix để biết cần sửa retrieval, prompt hay chunking. |
| Contextual enrichment | M5 | `contextual_prepend()`, `_enrich_single_call()` | Một lần gọi LLM sinh summary, HyQA questions, contextual line và metadata. Fallback extractive giúp pipeline vẫn chạy khi thiếu API key hoặc API lỗi. |

## Phần 2: Khó khăn & Cách giải quyết (Challenges & Debugging)

- **Lỗi kỹ thuật gặp phải:**
  - `APIStatusError: 402 ... in_flight_budget_exhausted` khi RAGAS chạy nhiều request OpenRouter đồng thời.
  - Lỗi 429 do giới hạn request/provider khi thử đánh giá lại; giảm concurrency và giãn request không bảo đảm giải quyết giới hạn của dịch vụ miễn phí.
  - Bốn metric RAGAS trả về `nan`, khiến bảng comparison và delta cũng thành `nan` dù progress bar báo hoàn tất.
  - `WinError 10013` khi `sentence_transformers` kiểm tra model `BAAI/bge-reranker-v2-m3` trên Hugging Face trong môi trường bị chặn socket.
  - `pytest` không nằm trong PATH của terminal hệ thống dù đã được cài trong `.venv`.
- **Nguyên nhân gốc rễ & Cách debug:**
  - Kiểm tra chữ ký `ragas.evaluate()` và `RunConfig` cho thấy mặc định `max_workers=16`, vượt in-flight budget. Tôi giảm concurrency, tăng thời gian chờ/retry và chuẩn hóa `NaN/inf` thành `0.0` để report luôn là JSON hợp lệ.
  - Chạy score diagnostic bằng `math.isfinite()` xác nhận BM25 và reranker không tạo NaN; lỗi step 3 thực chất là network retry. Dùng `HF_HUB_OFFLINE=1` và `TRANSFORMERS_OFFLINE=1` để chạy model từ cache.
  - Chạy test bằng `.venv\Scripts\python.exe -m pytest` thay vì gọi `pytest` trực tiếp.
  - Đối chiếu report cho thấy Production đạt Context Precision 0.9375 nhưng Faithfulness chỉ 0.5125. Điều này giúp tách lỗi retrieval khỏi lỗi generation/version conflict thay vì tối ưu mù toàn pipeline.
  - Điểm thấp chỉ gợi ý hướng điều tra, không chứng minh câu trả lời cụ thể đã sai. Report cũ không lưu answer/context nên các nguyên nhân Bottom-5 được ghi là giả thuyết. Chuẩn hóa NaN thành 0 chỉ bảo đảm JSON hợp lệ, không thay thế một phép đánh giá thành công.
- **Kiến thức còn thiếu & Cách khắc phục:**
  - Cần hiểu sâu hơn về metadata filtering và temporal/version-aware retrieval. Tôi sẽ bổ sung metadata `version`, `effective_date`, `status` và viết test cho trường hợp chính sách cũ bị thay thế.
  - Cần benchmark latency/quality của cross-encoder trên CPU và nghiên cứu cache model dùng chung giữa các instance.
  - Cần thiết kế evaluation có khả năng resume, lưu answer/context từng câu và retry riêng các sample thất bại để tránh phải chạy lại toàn bộ RAGAS.

## Phần 3: Action Plan cho Project cá nhân (Application Plan)

### Project: Trợ lý tra cứu quy định và tài liệu nội bộ

Đây là kế hoạch ứng dụng đề xuất, chưa phải hệ thống cá nhân đã triển khai hoặc
đã có benchmark. Hiện trạng bên dưới mô tả thiết kế khởi đầu dự kiến.

#### 1. Hiện trạng

- **Pipeline hiện tại:** Tài liệu được chia theo độ dài, embedding vào vector database và dùng top-k dense retrieval để đưa context cho LLM.
- **Vấn đề / Bottlenecks đang gặp:** Các phiên bản tài liệu cũ và mới dễ bị trộn; truy vấn chứa số/mã quy định không luôn được dense search xếp cao; câu trả lời đôi khi đúng chủ đề nhưng không bám sát bằng chứng; chưa có bộ evaluation định kỳ.

#### 2. Kế hoạch cải tiến

1. **Chunking strategy:** Dùng hierarchical chunking cho văn bản dài và structure-aware chunking cho Markdown/bảng. Parent cung cấp context, child phục vụ retrieval chính xác.
2. **Search retrieval:** Kết hợp BM25 và BGE-M3 dense retrieval bằng RRF. Thêm metadata filter theo phòng ban, phiên bản, ngày hiệu lực và trạng thái tài liệu.
3. **Reranking:** Dùng `BAAI/bge-reranker-v2-m3` rerank top 20 xuống top 3; cache một instance model và benchmark CPU/GPU trước khi production.
4. **Evaluation:** Xây test set gồm câu hỏi đơn giản, multi-hop, xung đột phiên bản và phép tính. Theo dõi bốn metric RAGAS, latency, tỷ lệ “không tìm thấy” và chi phí; lưu đầy đủ answer/context để phân tích lỗi.
5. **Enrichment:** Dùng contextual prepend và metadata extraction. Chỉ dùng HyQA cho các chính sách có nhiều cách diễn đạt; luôn có fallback không phụ thuộc API.

#### 3. Timeline triển khai

- **Tuần 1:** Chuẩn hóa tài liệu, schema metadata, versioning và bộ test 30–50 câu hỏi; triển khai chunking có bảo toàn bảng.
- **Tuần 2:** Xây hybrid retrieval + RRF, thêm metadata filtering và cross-encoder reranking; benchmark recall/precision và latency.
- **Tuần 3:** Tích hợp generation có citation, cơ chế từ chối khi thiếu bằng chứng và enrichment có cache/fallback.
- **Tuần 4:** Chạy RAGAS, phân tích Bottom-10, tối ưu theo error tree và đóng gói monitoring dashboard cho production.
