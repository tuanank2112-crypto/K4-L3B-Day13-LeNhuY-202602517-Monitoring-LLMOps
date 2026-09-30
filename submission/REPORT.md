# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.
>
> Các ô ghi **⏳ CẦN ĐIỀN** là phần chỉ có được sau khi tự chạy với project Langfuse cá nhân hoặc sau khi nhận `config/challenge.json` tại CP3; không điền số liệu chưa chạy.

## 1. Thông tin học viên

- **Họ và tên:** ⏳ CẦN ĐIỀN
- **MSSV:** 202602517
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/tuanank2112-crypto/K4-L3B-Day13-LeNhuY-202602517-Monitoring-LLMOps
- **Commit SHA cuối:** ⏳ CẦN ĐIỀN (`git log -1 --oneline` sau commit cuối)
- **Challenge ID:** ⏳ CẦN ĐIỀN (CP3)
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-202602517`

## 2. Evidence index

| Evidence | Đường dẫn | Trạng thái |
|---|---|---|
| Pytest cuối | [evidence/01-pytest.txt](evidence/01-pytest.txt) | 37 passed |
| Log validator | [evidence/02-log-validator.txt](evidence/02-log-validator.txt) | 100/100 |
| Dashboard validator | [evidence/03-dashboard-validator.txt](evidence/03-dashboard-validator.txt) | 6/6 panel |
| Structured log | [evidence/04-structured-log.txt](evidence/04-structured-log.txt) | trích nguyên văn `data/logs.jsonl` |
| PII redaction | [evidence/05-pii-redaction.txt](evidence/05-pii-redaction.txt) | input PII giả → log đã che |
| Trace list | `evidence/06-trace-list.png` | ⏳ CẦN ĐIỀN |
| Trace waterfall | `evidence/07-trace-waterfall.png` | ⏳ CẦN ĐIỀN |
| Trace metadata | `evidence/08-trace-metadata.png` | ⏳ CẦN ĐIỀN |
| Prompt versions | `evidence/09-prompt-versions.png` | ⏳ CẦN ĐIỀN |
| Prompt rollback | `evidence/10-prompt-rollback.png` | ⏳ CẦN ĐIỀN |
| Dashboard runtime | [evidence/11-dashboard-overview.png](evidence/11-dashboard-overview.png) | 6 panel từ log thật |
| Incident metric | `evidence/12-incident-metric.png` | ⏳ CẦN ĐIỀN (CP3) |
| Incident log | `evidence/13-incident-log.png` | ⏳ CẦN ĐIỀN (CP3) |
| Incident trace | `evidence/14-incident-trace.png` | ⏳ CẦN ĐIỀN (CP3) |

Evidence phụ:

- Baseline trước khi sửa code: [evidence/baseline/](evidence/baseline/) (`01-pytest-baseline.txt`, `02-log-validator-baseline.txt`, `03-dashboard-validator-baseline.txt`, `load-test.txt`, `logs-baseline.jsonl`).
- Practice scenarios (`rag_slow`, `tool_fail`, `cost_spike`) và bảng tổng hợp: [evidence/practice/](evidence/practice/), đặc biệt [practice-summary.txt](evidence/practice/practice-summary.txt).

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (20 record thiếu correlation ID, 20 record thiếu enrichment, 0 correlation ID) | 100/100 (131 record, 68 correlation ID, 0 PII leak) | Baseline đã pass PII vì `main.py` dùng `summarize_text` cho preview; processor mới che thêm mọi field khác |
| `validate_dashboard.py` | HỢP LỆ 6/6 | HỢP LỆ 6/6 | Contract không đổi; thêm dashboard runtime từ log |
| `pytest` | 22 passed | 37 passed | Thêm test PII (CCCD, thẻ, hộ chiếu, nested field), middleware, child observations, alert/SLO, dashboard builder |
| Số traces hợp lệ | 0 (`tracing_enabled: false`, chưa có key) | ⏳ CẦN ĐIỀN | Cần key của project cá nhân trong `.env` |
| Số PII leak | 0 | 0 | `grep` 5 giá trị PII giả trong `data/logs.jsonl` trả về 0 dòng |
| Latency P95 / TTFT P95 | 158 ms / 55 ms (31 request bình thường) | 158 ms / 55 ms bình thường; `rag_slow`: 2657 ms / 54 ms | Số từ [practice-summary.txt](evidence/practice/practice-summary.txt) |
| Retrieval success rate | 100% bình thường | 100% bình thường; `tool_fail`: 0%; cả cửa sổ 60 phút: 83.9% | Dashboard báo BREACH error rate 16.1% do đợt `tool_fail` |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** [`app/middleware.py`](../app/middleware.py) gọi `clear_contextvars()` đầu mỗi request, nhận header `x-request-id` nếu đúng format `req-<8-hex>` (không phân biệt hoa thường), ngược lại sinh `req-` + 8 ký tự hex từ `uuid4`. Header sai format (ví dụ chứa xuống dòng) bị thay bằng ID mới để tránh log injection. ID được bind vào structlog contextvars, gắn vào `request.state`, truyền vào `LabAgent.run` (trace metadata `correlation_id`) và trả lại qua header `x-request-id` cùng `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** ngoài `ts`, `level`, `service`, `event`, `correlation_id`, handler `/chat` ([`app/main.py`](../app/main.py)) bind `user_id_hash` (SHA-256 cắt 12 ký tự, không log user_id gốc), `session_id`, `feature`, `model`, `env` **trước** dòng `request_received`, nên `request_received`, `response_sent` và `request_failed` đều mang chung context. `response_sent` có thêm `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** [`app/logging_config.py`](../app/logging_config.py) đăng ký `scrub_event` sau `format_exc_info` (để cả exception text đã render cũng được che) và **trước** `JsonlFileProcessor`/`JSONRenderer`. `scrub_event` đi đệ quy qua mọi field string, dict, list, không chỉ `event`/`payload`. Pattern trong [`app/pii.py`](../app/pii.py): email, thẻ 16 số (có/không dấu cách hoặc gạch), CCCD 12 số, điện thoại VN (`0`/`+84` + 9 số với các dấu phân cách phổ biến), hộ chiếu VN (1 chữ in hoa + 7 số). Thẻ và CCCD được che trước điện thoại để dãy số dài không bị che dở dang.
- **Cách kiểm chứng kết quả:** `tests/test_pii.py` (từng loại PII, text không PII giữ nguyên, nested field/exception), `tests/test_middleware.py` (ID hợp lệ được giữ, ID xấu được sinh lại, hai request liên tiếp không rò `session_id`, log không có PII thô). Runtime: request chứa PII giả với `x-request-id: req-1a2b3c4d` và `req-5e6f7a8b` cho log `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`, `[REDACTED_CREDIT_CARD]`, `[REDACTED_PASSPORT_VN]` ([05-pii-redaction.txt](evidence/05-pii-redaction.txt)); `validate_logs.py` 100/100.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** ⏳ CẦN ĐIỀN (ảnh trace list có tên project `day13-k4-l3b-202602517`, thời gian trùng lần chạy `load_test.py`, và `correlation_id` trong metadata trùng với `data/logs.jsonl`).
- **Cấu trúc root/retrieval/generation observations:** [`app/agent.py`](../app/agent.py) dùng Langfuse SDK v4:

  ```text
  day13-agent-request (trace name, qua propagate_attributes)
  └── lab-agent-run            (as_type=agent, @observe; metadata prompt_name/label/version/source, query_preview đã scrub)
      ├── retrieval            (as_type=retriever; input query_preview, output doc_count + doc_previews, metadata tool_success, retrieval_ms; lỗi → level=ERROR)
      └── llm-generation       (as_type=generation; model, prompt managed, usage_details input/output/total, cost_details input/output/total, completion_start_time = start + TTFT)
  ```

  Input/output của observation chỉ là preview đã qua `summarize_text` (scrub PII + cắt ngắn); root dùng `capture_input=False, capture_output=False` nên không lưu message thô.
- **Cách nối trace với log:** `correlation_id` nằm trong trace metadata (qua `propagate_attributes`) và trong mọi dòng log của request; `user_id` của trace là cùng `user_id_hash` với log, `session_id` trùng nhau.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** ⏳ CẦN ĐIỀN (ví dụ v1 — labels `baseline`, `production`)
- **Version/label candidate:** ⏳ CẦN ĐIỀN (ví dụ v2 — label `candidate`)
- **Trace ID của mỗi version:** ⏳ CẦN ĐIỀN
- **Cách promote và rollback `production`:** code không đổi khi đổi version; app lấy prompt theo `LANGFUSE_PROMPT_NAME` + `LANGFUSE_PROMPT_LABEL` ([`app/prompt_management.py`](../app/prompt_management.py)). Promote = chuyển label `production` sang v2 trên Langfuse; rollback = chuyển `production` về v1. Cache prompt là 60 giây (`cache_ttl_seconds=60`) nên sau khi đổi label cần chờ tối đa 60 giây hoặc khởi động lại API. ⏳ CẦN ĐIỀN: trace ID trước/sau rollback.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** [`scripts/build_dashboard.py`](../scripts/build_dashboard.py) đọc `data/logs.jsonl` và [`config/dashboard.yaml`](../config/dashboard.yaml) (dùng lại `load_dashboard_config` của validator), sinh `data/dashboard.html` gồm đúng 6 panel theo contract: latency P50/P95/P99 + TTFT P95, traffic request/phút, error rate + breakdown `error_type` + retrieval success, cost theo phút + tổng, tokens in/out, quality mean. Time range 60 phút, auto-refresh 30 giây, mỗi panel ghi đơn vị, đường threshold nét đứt và badge OK/BREACH so với threshold của contract (threshold không hard-code trong script). Chạy `python scripts/build_dashboard.py` (hoặc `--watch` để tự sinh lại, `--anchor latest` để cửa sổ kết thúc ở log mới nhất). Ảnh: [11-dashboard-overview.png](evidence/11-dashboard-overview.png) — cửa sổ 15:29→16:29 UTC ngày 2026-09-30, 131 log record, gồm baseline + ba practice scenario: P95 2655 ms (do `rag_slow`), error rate 16.1% BREACH (do `tool_fail`), tokens out 11,310 (có đợt `cost_spike`), quality 0.88.
- **SLO và lý do chọn:** [`config/slo.yaml`](../config/slo.yaml) — 99.5% request thành công và `latency_ms <= 3000` trong 28 ngày. Giữ 3000 ms để trùng SLO line của panel latency. Baseline đo được P95 158 ms, 0% lỗi nên mục tiêu này đạt được khi hệ thống bình thường nhưng một sự cố kéo dài sẽ vi phạm rõ ràng.
- **Cách tính error budget:** error budget = 100% − 99.5% = 0.5% số request. Với 10,000 request/28 ngày thì tối đa 50 request được phép lỗi hoặc chậm hơn 3000 ms. Trong đợt practice `tool_fail`, 10/10 request lỗi (100% xấu) tức burn rate 200 lần: chỉ 50 request lỗi như vậy là hết budget của cả 28 ngày.
- **Ba alert và runbook tương ứng:** [`config/alert_rules.yaml`](../config/alert_rules.yaml), runbook [`docs/alerts.md`](../docs/alerts.md); tất cả gửi Slack `#k4-l3b-alerts`, owner `student-202602517`.

  | Alert | Điều kiện | Duration | Severity | Căn cứ từ số đo thật |
  |---|---|---|---|---|
  | `HighLatencyP95` | `p95(latency_ms) > 2000` | 5m | warning | baseline P95 158 ms; `rag_slow` P95 2657 ms vẫn < 3000 ms nên alert phải đặt sớm hơn SLO |
  | `HighErrorRate` | error rate > 2% | 5m | critical | baseline 0%; `tool_fail` 100%, retrieval success 0% |
  | `CostPerRequestSpike` | `avg(cost_usd) > 0.004` USD/request | 10m | warning | baseline 0.002013; `cost_spike` 0.008891 và tokens_out 586 so với 127 |

## 7. Điều tra challenge

- **Challenge ID:** ⏳ CẦN ĐIỀN
- **Khoảng thời gian điều tra:** ⏳ CẦN ĐIỀN
- **Triệu chứng từ metrics:** ⏳ CẦN ĐIỀN
- **Log line và correlation ID liên quan:** ⏳ CẦN ĐIỀN
- **Trace ID và span gây ảnh hưởng:** ⏳ CẦN ĐIỀN
- **Root cause:** ⏳ CẦN ĐIỀN
- **Fix action:** ⏳ CẦN ĐIỀN
- **Preventive measure:** ⏳ CẦN ĐIỀN

> Quy trình đã tập với practice scenario (không phải challenge chính thức): với `rag_slow` (16:25:49→16:26:18 UTC), metric P95 tăng từ 158 ms lên 2657 ms trong khi TTFT P95 giữ ~54 ms → thời gian mất ở ngoài bước LLM. Log `response_sent` của `correlation_id=req-e518b3bd` có `latency_ms=2652`, `ttft_ms=50` ([04-structured-log.txt](evidence/04-structured-log.txt)). Khi bật Langfuse, trace cùng `correlation_id` sẽ cho thấy span `retrieval` chiếm phần lớn thời gian. Với `tool_fail`, log `request_failed` của `req-c7526e93` có `error_type=RuntimeError`, `tool_name=retrieval`, `tool_success=false`, `payload.detail="Vector store timeout"`.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** tạo child observation bằng `langfuse_client.start_as_current_observation(...)` (context manager) thay vì chỉ gắn thêm `@observe` lên hàm `retrieve`/`generate`. Context manager cho phép (1) cập nhật `usage_details`/`cost_details`/`completion_start_time` sau khi có response, (2) tự quyết định input/output chỉ là preview đã scrub thay vì để decorator capture argument thô chứa PII, (3) đánh dấu `level=ERROR` + `tool_success=false` khi retrieval lỗi rồi re-raise, (4) giữ quan hệ cha-con vì observation mới luôn là con của span hiện tại (`lab-agent-run`). Metadata prompt vẫn cập nhật trên root sau khi retrieval đóng, nên test contract cũ vẫn đúng.
- **Một lỗi/blocker đã gặp:** (1) `validate_logs.py` đọc toàn bộ `data/logs.jsonl`, nên sau khi sửa code các dòng baseline cũ (`correlation_id: "MISSING"`) vẫn làm điểm thấp. (2) Sau khi thêm child observation, fake client trong `tests/test_agent_prompt_trace.py` không có `start_as_current_observation` nên test cũ sẽ lỗi.
- **Cách tìm nguyên nhân và xử lý:** (1) Chuyển log baseline sang [`evidence/baseline/logs-baseline.jsonl`](evidence/baseline/logs-baseline.jsonl), khởi động lại API rồi đo lại (30/100 → 100/100). (2) Mở rộng fake client để ghi lại từng observation và thêm test kiểm tra retrieval/generation, model, usage, cost, không có PII thô và trường hợp retrieval lỗi; test cũ về prompt metadata giữ nguyên assertion. Ngoài ra tôi cũng nhận thấy latency phía client khi chạy `--concurrency 5` là 324–804 ms trong khi `latency_ms` phía server của cùng các request chỉ 151–155 ms ([practice/concurrency-5.txt](evidence/practice/concurrency-5.txt)): endpoint `async def` gọi `agent.run` đồng bộ nên các request xếp hàng trên event loop. Header `x-response-time-ms` phản ánh được thời gian chờ này, còn `latency_ms` thì không.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics trả lời "có vấn đề gì và từ lúc nào" trên toàn bộ traffic (ví dụ P95 tăng trong khi TTFT không đổi); logs cho phép lọc trong đúng khoảng đó để chọn một request cụ thể bằng `correlation_id` và thấy các field của nó; trace của chính request đó chia thời gian/lỗi ra từng span (`retrieval` hay `llm-generation`) để khoanh vùng root cause. Chỉ kết luận khi cả ba lớp cùng chỉ về một nguyên nhân.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt thay đổi hành vi như một lần deploy nhưng không đi qua code, nên mỗi trace phải ghi `prompt_name/label/version` để biết request dùng version nào; token/cost trên generation cho biết một thay đổi (prompt dài hơn, output dài hơn) tốn thêm bao nhiêu — practice `cost_spike` làm cost/request tăng ~4.4 lần mà traffic không đổi; SLO và error budget quyết định khi nào phải dừng thay đổi để ưu tiên ổn định; rollback bằng cách chuyển label `production` là cách khôi phục nhanh nhất vì không cần deploy.
- **Điều quan trọng nhất đã học:** redaction phải nằm trong pipeline logging trước bước render/ghi file và phủ mọi field, không dựa vào việc từng chỗ gọi log nhớ tự scrub; và alert nên được đặt theo số đo baseline thực tế — ngưỡng SLO 3000 ms không bắt được `rag_slow` (2657 ms).
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** chưa có trace/prompt evidence trên Langfuse và phần challenge CP3 (xem các mục ⏳). Quality score là heuristic trên câu trả lời cố định của FakeLLM nên gần như không đổi (0.8–0.9). Request lỗi 500 trả `correlation_id` trong header `x-request-id` nhưng không trong body. Alert mới được định nghĩa trong YAML, chưa nối với hệ thống gửi Slack thật.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
