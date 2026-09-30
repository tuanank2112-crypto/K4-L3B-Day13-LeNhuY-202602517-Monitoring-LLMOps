# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`; SLO `fast_successful_requests` (99.5% request thành công và `latency_ms <= 3000`) trong [`config/slo.yaml`](../config/slo.yaml).
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 2000ms` liên tục 5 phút. Ngưỡng 2000ms thấp hơn SLO 3000ms để báo sớm: baseline P95 đo được là 158ms, còn practice `rag_slow` đẩy P95 lên 2657ms — vẫn dưới 3000ms nên nếu chỉ alert ở mức SLO sẽ bỏ lỡ sự cố.
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời; nếu kéo dài sẽ vượt SLO và đốt error budget.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Latency percentiles and TTFT**, xác nhận P95/P99 và khoảng thời gian tăng; so sánh với TTFT P95. TTFT bình thường (~50ms) mà latency tổng tăng nghĩa là thời gian bị mất ở ngoài bước sinh token đầu tiên của LLM.
  2. Lọc `data/logs.jsonl` trong khoảng đó: `event == "response_sent"` và `latency_ms > 2000`, lấy một `correlation_id` (có thể dùng `python scripts/log_summary.py --window ...`).
  3. Mở trace trên Langfuse có metadata `correlation_id` trùng, so sánh duration của span `retrieval` và `llm-generation` dưới `lab-agent-run` (xem thêm `retrieval_ms` trong metadata của span retrieval).
- Mitigation tạm thời: nếu span `retrieval` chậm thì khôi phục/tắt cấu hình làm chậm retrieval (practice: `python scripts/inject_incident.py --scenario rag_slow --disable`) hoặc giảm tải; nếu `llm-generation` chậm và trùng thời điểm đổi prompt thì rollback label `production` về version trước.
- Owner: `student-202602517`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: error rate = `count(request_failed) / count(request_received) * 100` và retrieval success = `count(tool_success == true) / count(tool_success != null) * 100` trên panel errors; guardrail `error_rate_pct_max: 2`, `retrieval_success_rate_pct_min: 90`.
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` liên tục 5 phút. Baseline có 0% lỗi; practice `tool_fail` cho 10/10 request lỗi (100%).
- Ảnh hưởng tới người dùng: người dùng nhận HTTP 500 thay vì câu trả lời; mỗi request lỗi tính thẳng vào error budget (0.5%), nên mức critical.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Error rate and retrieval success**: xem error rate, breakdown `error_type` và retrieval success cùng giảm hay không.
  2. Lọc log `event == "request_failed"` trong khoảng đó, đọc `error_type`, `tool_name`, `tool_success`, `payload.detail` và lấy một `correlation_id` (cũng có trong response header `x-request-id`).
  3. Mở trace cùng `correlation_id`: span nào có level `ERROR` (ví dụ `retrieval` với `tool_success=false`, status message chứa lỗi) và `llm-generation` có được gọi hay không.
- Mitigation tạm thời: nếu lỗi nằm ở retrieval thì khôi phục vector store/tắt cấu hình gây lỗi (practice: `python scripts/inject_incident.py --scenario tool_fail --disable`), cân nhắc trả fallback answer không có context thay vì 500; nếu lỗi bắt đầu ngay sau deploy/đổi prompt thì rollback.
- Owner: `student-202602517`

## Alert 3

- Tên: `CostPerRequestSpike`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: `avg(response_sent.cost_usd)` và `tokens_out` trên panel cost/tokens; guardrail `daily_cost_usd_max: 2.5`.
- Điều kiện và thời gian duy trì: chi phí trung bình mỗi request `> 0.004 USD` liên tục 10 phút (gần 2x baseline 0.002013 USD/request). Alert theo cost/request thay vì tổng cost để không báo nhầm khi traffic tăng hợp lệ. Practice `cost_spike` cho 0.008891 USD/request và tokens_out trung bình 586 (baseline 127).
- Ảnh hưởng tới người dùng: câu trả lời dài bất thường (khó đọc, chậm hơn) và ngân sách ngày bị đốt nhanh; nếu kéo dài sẽ vượt `daily_cost_usd_max`.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Cost over time** và **Input and output tokens**: xác định cost tăng do `tokens_in` (prompt/context dài) hay `tokens_out` (câu trả lời dài), và traffic có tăng cùng lúc không.
  2. Lọc log `response_sent` có `cost_usd > 0.004`, lấy `correlation_id`, ghi lại `tokens_in`/`tokens_out`/`model`.
  3. Mở trace cùng `correlation_id`, xem `usage_details`/`cost_details` của `llm-generation` và `prompt_name`/`prompt_version` để biết request dùng prompt version nào.
- Mitigation tạm thời: nếu trùng thời điểm promote prompt mới thì rollback label `production` về version cũ; giới hạn `max_tokens`/độ dài output; tắt cấu hình gây tăng token (practice: `python scripts/inject_incident.py --scenario cost_spike --disable`).
- Owner: `student-202602517`
