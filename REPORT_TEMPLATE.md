# Báo cáo cá nhân — Day 6

## Dữ liệu và pipeline
- Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:
Dự án xây dựng pipeline Data Ingestion và Retrieval phục vụ truy xuất thông tin từ tài liệu kinh tế học. Bộ dữ liệu sử dụng nội dung từ Principles of Economics 3e của OpenStax, tập trung vào ba chương đầu: giới thiệu kinh tế học, lựa chọn trong điều kiện khan hiếm, và cung – cầu.

Nguồn dữ liệu: OpenStax – Principles of Economics 3e.

File đầu vào: data/raw/openstax_economics_ch1_ch3.pdf.

Phạm vi: 70 trang PDF.

Quy tắc tính trang: sử dụng số trang PDF bắt đầu từ 1, độc lập với số trang in trong sách.

Metadata của tài liệu khai báo giấy phép CC BY-NC-SA 4.0. Cần đối chiếu lại với giấy phép chính thức của tài liệu gốc trước khi nộp.
- Chuẩn hóa, lỗi và giới hạn:
Pipeline thực hiện đọc nội dung PDF, trích xuất văn bản, chia thành các chunk, tạo embedding và lưu trữ trong cơ sở dữ liệu vector. Các chunk được gắn thông tin nguồn, trang và metadata để phục vụ truy xuất và kiểm chứng bằng chứng.

Những giới hạn quan sát được:

Nội dung trích xuất có thể chứa tiêu đề, số trang, chú thích hình ảnh và ký tự bị dính.

Một số chunk bị cắt giữa câu, làm mất ngữ cảnh.

Paragraph chunking tạo ra chunk ngắn nhất chỉ 6 ký tự.

Các đoạn chứa bảng biểu hoặc hình minh họa có thể không được biểu diễn đầy đủ bằng văn bản.

Một số bằng chứng đúng về mặt ngữ nghĩa không được hệ thống exact matching công nhận.

- Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:
Hệ thống sử dụng Hugging Face / Sentence Transformers làm embedding provider, với mô hình sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, phiên bản revision e8f8c211226b894fcb81acc59f3b34ba3efd5f42, tạo vector embedding 384 chiều. Dữ liệu vector được lưu trữ trong PostgreSQL 16.16 kết hợp pgvector 0.8.7, sử dụng phương pháp Exact Cosine Similarity để truy xuất. Pipeline được triển khai bằng Python 3.11.4, chạy trên CPU và có chi phí API là 0 USD.
Lệnh thực hiện tại thư mục starter:

python -m src.run --benchmark ..\benchmark\questions.json

Model embedding được tải từ Hugging Face và chạy cục bộ. Vì không sử dụng API embedding trả phí nên chi phí API được ghi nhận là 0 USD. Chi phí điện, phần cứng và Internet chưa được tính.
- Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:
Các trường quan sát được trong retrieval trace gồm:

Hệ thống sử dụng các trường metadata gồm document_id để xác định tài liệu nguồn, source để lưu đường dẫn tài liệu, page để xác định trang chứa bằng chứng, edition để ghi nhận phiên bản tài liệu (3e), license để lưu thông tin giấy phép, section để phân loại nội dung theo chương và hỗ trợ lọc dữ liệu, cùng với language để xác định ngôn ngữ tài liệu (en).

Trường section được sử dụng trong các câu hỏi có metadata filter, giúp giới hạn phạm vi truy xuất theo chương. Các giá trị metadata cần được kiểm tra với manifest và nội dung PDF để xác nhận tính chính xác.

## Cấu hình và benchmark
- A / B / C (tham số cụ thể, khác biệt duy nhất B–C):

 Hệ thống triển khai ba chiến lược chunking: A (Fixed-size chunking) chia văn bản thành các đoạn có kích thước cố định, tạo ra 479 chunks; B (Paragraph-based chunking) chia văn bản theo đoạn văn, tạo ra 623 chunks; và C (Paragraph-based chunking kết hợp metadata filtering) sử dụng cách chia đoạn tương tự B nhưng bổ sung cơ chế lọc theo metadata, tạo ra 623 chunks.
 Chiến lược A chia văn bản thành các đoạn có giới hạn kích thước cố định. Chiến lược B chia theo cấu trúc đoạn văn nhằm bảo toàn ranh giới nội dung tự nhiên. Chiến lược C sử dụng cách chia đoạn tương tự B, nhưng bổ sung cơ chế lọc dựa trên metadata.

Theo kết quả thực nghiệm, cả ba chiến lược có độ dài chunk tối đa 500 ký tự. Tuy nhiên, kích thước mục tiêu, overlap và quy tắc xử lý đoạn dài cần được xác nhận trực tiếp trong src/chunking.py.

Khác biệt thiết kế giữa B và C là cơ chế metadata filtering; số lượng chunk và tổng ký tự của hai chiến lược giống nhau.
- ≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence:

Bộ benchmark gồm 20 câu hỏi:

Dev: 15 câu, từ q01 đến q15.

Test: 5 câu, từ q16 đến q20.

Các câu có filter được ghi trong trường filter của benchmark, ví dụ q04 giới hạn chapter_1 và q10 giới hạn chapter_2.

Mỗi câu có thông tin gold source, gold page và evidence quote.

Retrieval được đánh giá trên Top 1 và Top 3 kết quả.

Hit@1 cho biết kết quả đầu tiên có khớp bằng chứng chuẩn theo bộ đánh giá hay không. Evidence Hit@3 cho biết có ít nhất một kết quả trong ba kết quả đầu khớp bằng chứng chuẩn hay không.

Ngoài đánh giá tự động, cần kiểm tra thủ công các đoạn diễn đạt tương đương, vì exact evidence matching có thể tạo false negative.
- Tiêu chí chọn chiến lược đã chốt trước khi xem test:

Tiêu chí đề xuất là ưu tiên Evidence Hit@3 trên Dev, sau đó xem xét Hit@1, tính mạch lạc của chunk, tính chính xác của metadata, khả năng tuân thủ filter và chi phí xử lý.

Chưa có bằng chứng trong log xác nhận các tiêu chí này đã được chốt trước khi xem tập Test. Vì vậy, không khẳng định đây là quy tắc lựa chọn đã đăng ký trước thí nghiệm.

## Kết quả
| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|A|Dev|8/15 (53.33%)|10/15 (66.67%)|479|19.857s|$0|
|A|Test|2/5 (40%)|2/5 (40%)|479|19.857s|$0|
|B|Dev|5/15 (33.33%)|7/15 (46.67%)|623|19.399s|$0|
|B|Test|0/5 (0%)|2/5 (40%)|623|19.399s|$0|
|C|Dev|5/15 (33.33%)|7/15 (46.67%)|623|19.403s|$0|
|C|Test|0/5 (0%)|2/5 (40%)|623|19.403s|$0|

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|

Đường dẫn trace, nhãn thủ công và cách chọn mẫu:

Retrieval trace: starter/results/retrieval_trace.json

Metrics: starter/results/metrics.csv và starter/results/metrics.json

Cấu hình chạy: starter/results/run_info.json

Log: starter/results/errors.log

Nhãn thủ công: chưa có file nhãn được xác nhận.

Đề xuất chọn mẫu audit gồm các trường hợp retrieval thành công, thất bại, có metadata filter và các trường hợp exact matching không công nhận bằng chứng tương đương. Việc chấm cần lưu ID câu, chiến lược, chunk được đánh giá, nhãn và giải thích.

## Phân tích và kết luận
- So sánh A–B và B–C; 2 ví dụ sai có ID câu và nguồn:

 trên tập Dev với Hit@1 = 53.33% và Evidence Hit@3 = 66.67%, cao hơn B lần lượt 20 điểm phần trăm ở cả hai chỉ số. A tạo 479 chunks, trong khi B tạo 623 chunks.

B sử dụng paragraph chunking nhưng một số đoạn quá ngắn hoặc thiếu nội dung trả lời. Điều này có thể khiến embedding không biểu diễn đầy đủ ý nghĩa của tài liệu.

Chiến lược C có cùng số chunk và kết quả benchmark với B. Trong lần thử nghiệm này, metadata filtering chưa tạo ra cải thiện đo được. Cần thêm các truy vấn lọc có khả năng loại bỏ những chunk không liên quan để đánh giá chính xác hiệu quả.

Hai ví dụ sai có ID câu và nguồn:

Ví dụ 1 – q11: What is quantity demanded?

Chiến lược: A.

Kết quả tự động: Hit@1 = 0, Hit@3 = 0.

Gold page: 41.

Retrieved page: 42.

Nguồn: data/raw/openstax_economics_ch1_ch3.pdf.

Kết quả Top 3 giải thích quantity demanded là một điểm cụ thể trên đường cầu. Nội dung này có liên quan và hỗ trợ trả lời câu hỏi, nhưng không khớp với evidence quote chuẩn. Trường hợp này cho thấy hạn chế của phương pháp đánh giá dựa trên bằng chứng chính xác.

Ví dụ 2 – q15: What happens to demand for an inferior good when income increases?

Chiến lược: A.

Kết quả tự động: Hit@1 = 0, Hit@3 = 0.

Gold page: 49.

Retrieved page: 70 ở Top 2.

Nguồn: data/raw/openstax_economics_ch1_ch3.pdf.

Top 2 chứa định nghĩa inferior good, trong đó lượng cầu giảm khi thu nhập tăng. Mặc dù bằng chứng có thể trả lời câu hỏi, hệ thống vẫn đánh dấu không khớp với gold evidence. Điều này cho thấy cần kết hợp đánh giá tự động và đánh giá ngữ nghĩa thủ công.

- Chiến lược chọn, đánh đổi, điều kiện áp dụng:

Dựa trên kết quả Dev, A là lựa chọn baseline phù hợp nhất trong ba chiến lược đã thử nghiệm. A đạt chất lượng retrieval tốt hơn và có ít chunk hơn B/C.

Đánh đổi là fixed-size chunking có thể cắt giữa câu hoặc đoạn văn, ảnh hưởng đến tính mạch lạc. Chiến lược này phù hợp với bộ dữ liệu hiện tại, nhưng cần thử nghiệm thêm trên tài liệu có cấu trúc khác.

- Hạn chế của dữ liệu, nhãn, test nhỏ, đo thời gian/chi phí:

Dữ liệu chỉ gồm một tài liệu kinh tế học với phạm vi ba chương.

Benchmark có 20 câu, trong đó tập Test chỉ gồm 5 câu.

Exact evidence matching có thể không công nhận các bằng chứng diễn đạt tương đương.

Manual audit chưa hoàn thành.

Thời gian ingestion được đo trong một lần chạy, chưa có nhiều lần lặp để đánh giá độ ổn định.

Chi phí API bằng 0 USD nhưng chưa tính chi phí vận hành máy và tài nguyên cục bộ.

- Nếu làm lại hoặc mở rộng, cải tiến gì?

Nếu tiếp tục phát triển, tôi sẽ cải thiện quy trình chunking bằng cách kết hợp các đoạn quá ngắn với nội dung liền kề, bảo toàn tiêu đề và cấu trúc văn bản, đồng thời thử nghiệm nhiều mức chunk size và overlap.

Tôi cũng sẽ bổ sung các câu hỏi yêu cầu metadata filtering, mở rộng tập Test, thực hiện manual audit với rubric thống nhất và so sánh kết quả qua nhiều lần chạy.

Cuối cùng, tôi sẽ xem xét hybrid retrieval kết hợp vector similarity với keyword search để cải thiện khả năng tìm các định nghĩa và thuật ngữ chuyên ngành.

Kết luận: Pipeline đã thực hiện thành công quá trình ingestion, embedding, lưu trữ vector và đánh giá retrieval. Chiến lược A có hiệu năng tốt nhất trên tập Dev của thí nghiệm hiện tại. Tuy nhiên, chất lượng retrieval vẫn cần được kiểm chứng bằng đánh giá thủ công, đặc biệt ở những trường hợp bằng chứng đúng về ngữ nghĩa nhưng không khớp chính xác với gold quote.
