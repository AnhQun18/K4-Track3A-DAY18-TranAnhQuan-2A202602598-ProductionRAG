# Failure Analysis — Lab 18: Production RAG

**Họ và tên học viên:** Trần Anh Quân
**Khóa:** K4 - Track 3A

---

## RAGAS Scores

**Căn cứ báo cáo:** Lần chạy thành công gần nhất do học viên cung cấp qua terminal,
đối chiếu với `reports/naive_baseline_report.json` và `reports/ragas_report.json`.
Lần chạy đánh giá 20 câu hỏi, hoàn tất 80 tác vụ metric cho mỗi pipeline; tổng thời
gian 1246.5 giây (khoảng 20 phút 47 giây). Đây là số liệu thực nghiệm cũ, không phải
kết quả chạy mới. Các lần thử sau bị giới hạn request API nên không dùng làm kết quả
đánh giá. Đợt tối ưu chất lượng sau khi đọc log đã được hoàn tác theo yêu cầu.

| Metric | Naive Baseline | Production | Δ |
|--------|---------------:|-----------:|--:|
| Faithfulness | 0.8083 | 0.5125 | -0.2958 |
| Answer Relevancy | 0.7083 | 0.5433 | -0.1650 |
| Context Precision | 0.9333 | 0.9375 | +0.0042 |
| Context Recall | 0.9083 | 0.8333 | -0.0750 |

Kết quả Production chưa đạt mục tiêu ở Faithfulness và Answer Relevancy. Context Precision đạt 0.9375, cho thấy các đoạn được lấy về nhìn chung liên quan, nhưng mô hình sinh câu trả lời chưa bám chắc vào bằng chứng. File report hiện tại không lưu nguyên văn `answer` và `contexts` của từng câu, vì vậy các nhận định dưới đây dựa trên điểm RAGAS, ground truth và đối chiếu trực tiếp với tài liệu nguồn; không suy đoán một câu trả lời cụ thể khi không có log.

## Bottom-5 Failures

Các điểm trung bình dưới đây lấy từ danh sách `failures` trong report, không phải
điểm Faithfulness riêng của từng câu. `worst_metric` chỉ xác định metric thấp nhất.
Các mục Root cause và Error Tree là giả thuyết cần kiểm chứng, không phải lỗi đã
được xác nhận bằng câu trả lời/context. Nhãn tự động `LLM hallucinating` cũng không
đủ để kết luận mô hình đã bịa một nội dung cụ thể.

### #1 — Bảo hiểm PVI trong thời gian thử việc

- **Question:** Nhân viên thử việc có được hưởng bảo hiểm sức khỏe PVI không?
- **Expected:** Không. Nhân viên thử việc chỉ tham gia bảo hiểm xã hội bắt buộc và chưa được hưởng gói bảo hiểm sức khỏe PVI.
- **Got:** Report không lưu nguyên văn câu trả lời. Điểm trung bình 0.3750 và `faithfulness` là metric thấp nhất, nên câu trả lời không được RAGAS xác nhận là bám sát context.
- **Câu trả lời có đúng không?** Không thể kết luận tuyệt đối từ report; với Faithfulness thấp, nhiều khả năng câu trả lời đã thiếu điều kiện “nhân viên thử việc” hoặc suy diễn từ chính sách dành cho nhân viên chính thức.
- **Context có chứa đáp án không?** Corpus có đáp án trực tiếp tại `data/thu_viec.md`: nhân viên thử việc chưa được hưởng PVI. Tuy nhiên report không lưu retrieved contexts nên chưa thể chứng minh đoạn này đã vào top-3.
- **Câu hỏi có cần viết lại không?** Không. Câu hỏi ngắn, rõ đối tượng và quyền lợi cần kiểm tra.
- **Worst metric:** Faithfulness.
- **Error Tree:** Output chưa được chứng minh đúng → bằng chứng nguồn có sẵn → query rõ → lỗi ở retrieval/rerank hoặc generation.
- **Root cause:** Dense retrieval có thể ưu tiên `bao_hiem_suc_khoe.md`, nơi nói “tất cả nhân viên chính thức”, nhưng bỏ qua đoạn phủ định rõ hơn trong `thu_viec.md`.
- **Suggested fix / module:** M2/M3 — tăng trọng số BM25 cho cụm “thử việc”, rerank cả hai chính sách; pipeline generation phải trích đúng câu phủ định trước khi kết luận.

### #2 — Ngày phép theo thâm niên

- **Question:** Thâm niên bao nhiêu năm thì được cộng thêm ngày phép?
- **Expected:** Theo chính sách v2024, từ 3 năm trở lên được cộng 1 ngày cho mỗi 3 năm; quy định 5 năm thuộc bản v2023 đã bị thay thế.
- **Got:** Report không lưu nguyên văn câu trả lời. Điểm trung bình 0.3958 và `faithfulness` thấp nhất.
- **Câu trả lời có đúng không?** Chưa thể xác nhận do thiếu nguyên văn câu trả lời. Một giả thuyết cần kiểm tra là nhầm phiên bản giữa mốc 3 năm và 5 năm.
- **Context có chứa đáp án không?** Corpus chứa cả đáp án đúng trong `nghi_phep_nam_v2024.md` và thông tin cũ trong `nghi_phep_nam_v2023.md`. Retrieved contexts không được lưu, nhưng nguy cơ lấy đồng thời hai phiên bản là rất cao.
- **Câu hỏi có cần viết lại không?** Có thể thêm “theo chính sách hiện hành” để giảm mơ hồ, dù hệ thống vẫn phải tự ưu tiên văn bản mới nhất.
- **Worst metric:** Faithfulness.
- **Error Tree:** Output có khả năng dùng chính sách cũ → context xung đột phiên bản → query có thể rõ hơn → cần metadata/version filtering.
- **Root cause:** Pipeline chưa biểu diễn và lọc metadata `version`, `effective_date`, `status`; enrichment metadata chung chưa đủ để loại chính sách đã thay thế.
- **Suggested fix / module:** M5 trích xuất metadata phiên bản/trạng thái; M2 lọc hoặc boost tài liệu hiện hành; M3 ưu tiên v2024; prompt generation phải nêu nguồn hiện hành và cảnh báo bản cũ.

### #3 — Phê duyệt nghỉ không lương 20 ngày

- **Question:** Nghỉ phép không lương 20 ngày cần ai phê duyệt?
- **Expected:** Giám đốc điều hành (CEO); nghỉ trên 14 ngày còn phải tự đóng phần bảo hiểm của mình.
- **Got:** Report không lưu nguyên văn câu trả lời. Điểm trung bình 0.4459 và `faithfulness` thấp nhất.
- **Câu trả lời có đúng không?** Chưa thể xác nhận; điểm thấp cho thấy câu trả lời có thể nhầm sang cấp phê duyệt của khoảng 6–15 ngày hoặc chỉ trả lời một phần.
- **Context có chứa đáp án không?** Corpus có bảng quy tắc đầy đủ trong `nghi_phep_khong_luong.md`: 16–30 ngày cần CEO. Không có retrieved context trong report để kiểm chứng top-3.
- **Câu hỏi có cần viết lại không?** Không. Số ngày và ý định phê duyệt đều rõ ràng.
- **Worst metric:** Faithfulness.
- **Error Tree:** Output chưa chắc đúng → nguồn có quy tắc theo khoảng → query rõ → cần giữ nguyên cấu trúc quy định và rerank đúng đoạn.
- **Root cause:** Chunking theo kích thước có thể tách điều kiện “16–30 ngày” khỏi nhãn “Quy trình phê duyệt”, hoặc reranker ưu tiên đoạn nói chung về nghỉ không lương.
- **Suggested fix / module:** M1 dùng structure-aware chunking cho mục “Quy trình phê duyệt”; M3 boost đoạn chứa cả “20 ngày”, “16–30 ngày” và “CEO”.

### #4 — Chu kỳ đổi mật khẩu

- **Question:** Bao lâu phải đổi mật khẩu một lần?
- **Expected:** Mỗi 120 ngày theo chính sách v2.0 hiện hành; mốc 90 ngày thuộc v1.0 đã bị thay thế.
- **Got:** Report không lưu nguyên văn câu trả lời. Điểm trung bình 0.4583 và `faithfulness` thấp nhất.
- **Câu trả lời có đúng không?** Chưa thể xác nhận do thiếu nguyên văn câu trả lời. Cần kiểm tra giả thuyết chọn nhầm mốc 90 ngày hoặc không phân biệt hai phiên bản 90/120 ngày.
- **Context có chứa đáp án không?** Corpus chứa cả hai phiên bản. `mat_khau_v2.md` ghi rõ 120 ngày và thay thế v1.0; `mat_khau_v1.md` ghi 90 ngày nhưng có trạng thái đã thay thế.
- **Câu hỏi có cần viết lại không?** Có thể thêm “theo chính sách hiện hành”, nhưng một production RAG vẫn phải xử lý đúng version mà không phụ thuộc cách hỏi.
- **Worst metric:** Faithfulness.
- **Error Tree:** Output có khả năng chọn dữ liệu cũ → context có conflict → query thiếu mốc “hiện hành” → lỗi chính ở version-aware retrieval.
- **Root cause:** BM25/Dense cùng xem hai tài liệu gần như tương đương; metadata chưa có cơ chế loại `status=deprecated`.
- **Suggested fix / module:** M5 trích `version/status/effective_date`; M2 thêm metadata filter; M3 rerank theo trạng thái hiện hành; prompt yêu cầu ưu tiên văn bản thay thế mới nhất.

### #5 — Phê duyệt thiết bị 55 triệu

- **Question:** Muốn mua thiết bị trị giá 55 triệu cần ai phê duyệt?
- **Expected:** Tổng Giám đốc (CEO), vì giá trị trên 50.000.000 VNĐ.
- **Got:** Report không lưu nguyên văn câu trả lời. Điểm trung bình 0.4583 và `faithfulness` thấp nhất.
- **Câu trả lời có đúng không?** Chưa thể xác nhận; hệ thống có thể nhầm với khoảng 5–50 triệu do các ngưỡng nằm cạnh nhau trong bảng.
- **Context có chứa đáp án không?** Corpus có đáp án chính xác trong bảng tại `mua_sam.md`. Retrieved context không được lưu nên chưa biết hàng “trên 50 triệu” có được giữ trọn hay không.
- **Câu hỏi có cần viết lại không?** Không. Giá trị và hành động cần phê duyệt đều rõ.
- **Worst metric:** Faithfulness.
- **Error Tree:** Output có khả năng chọn sai ngưỡng → đáp án nằm trong bảng → query rõ → lỗi ở table-aware chunking/retrieval.
- **Root cause:** Hierarchical chunking theo ký tự không bảo đảm giữ nguyên ngữ nghĩa từng hàng bảng; dense retrieval có thể gần với hàng 5–50 triệu hơn.
- **Suggested fix / module:** M1 bảo toàn toàn bộ bảng hoặc tạo mỗi hàng thành một chunk có header; M2 tăng lexical matching cho số `55`/`50.000.000`; M3 rerank theo điều kiện số học “trên 50 triệu”.

## Case Study (cho presentation)

**Question chọn phân tích:** Bao lâu phải đổi mật khẩu một lần?

**Error Tree walkthrough:**
1. **Output đúng?** Chưa thể xác nhận từ report, nhưng Faithfulness thấp và corpus có hai giá trị xung đột.
2. **Context đúng?** Corpus có cả 90 ngày (v1.0, đã thay thế) và 120 ngày (v2.0, hiện hành); retrieval cần ưu tiên v2.0.
3. **Query rewrite OK?** Query rõ về chu kỳ nhưng chưa nói “hiện hành”; có thể rewrite thành “Theo chính sách mật khẩu hiện hành, chu kỳ đổi mật khẩu là bao lâu?”.
4. **Fix ở bước:** M5 metadata phiên bản → M2 metadata filtering → M3 reranking → generation nêu rõ phiên bản nguồn.

**Nếu có thêm 1 giờ, sẽ optimize:**
- Bổ sung `version`, `effective_date`, `status` vào metadata, loại tài liệu đã thay thế trước dense/BM25 retrieval và lưu `answer`/`contexts` vào report để failure analysis có bằng chứng đầy đủ.

## Kết luận và giới hạn

- Production đạt Context Precision 0.9375 và Context Recall 0.8333; Faithfulness
  0.5125 và Answer Relevancy 0.5433 chưa đạt mục tiêu 0.70–0.75. Chỉ Context Precision
  tăng nhẹ so với baseline; không kết luận Production tốt hơn trên toàn bộ metric.
- Pipeline trước đợt tối ưu dùng hierarchical children, enrichment, hybrid search
  và cross-encoder top-3. `build_pipeline()` chưa khôi phục parent làm context;
  `run_query()` dùng đoạn enriched được rerank và prompt ngắn chỉ yêu cầu bám context.
- Hai PDF scan không có text layer bị bỏ qua; phạm vi đánh giá không bao gồm nội dung
  chưa OCR của hai tài liệu này.
- Giữ nguyên JSON thực nghiệm. Không bổ sung giả lập answer/context hay metric riêng
  từng câu. Phân tích Bottom-5 hoàn thành với các giới hạn bằng chứng được nêu rõ.
- Các sửa lỗi API/ghi report trước đợt tối ưu vẫn được giữ; chưa có lần chạy API đầy
  đủ xác nhận lại trạng thái code hiện tại. Không cam kết tái tạo chính xác điểm cũ.
