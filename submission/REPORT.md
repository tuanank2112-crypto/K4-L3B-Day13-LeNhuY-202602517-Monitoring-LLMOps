# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.
>
> Evidence Langfuse (06–10, 14) được xuất dạng text qua Langfuse Public API bằng [`scripts/langfuse_traces.py`](../scripts/langfuse_traces.py) và [`scripts/langfuse_prompt_setup.py`](../scripts/langfuse_prompt_setup.py); output đã lọc bỏ `resourceAttributes/scope` (có public key). Ô **⏳ CẦN ĐIỀN** là phần chưa có.

## 1. Thông tin học viên

- **Họ và tên:** Le Nhu Y
- **MSSV:** 202602517
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/tuanank2112-crypto/K4-L3B-Day13-LeNhuY-202602517-Monitoring-LLMOps
- **Commit SHA cuối:** `0f3c6fd` — commit chứa toàn bộ source và evidence; commit sau đó chỉ ghi SHA này vào report (xem `git log`)
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort K4, seed 1312)
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-202602517` (project id `cmuoc4b000091ad0cu72s4cij`; lúc xuất evidence project còn tên `hhhh` nên dòng `project:` trong các file evidence ghi `hhhh`)

## 2. Evidence index

| Evidence | Đường dẫn | Trạng thái |
|---|---|---|
| Pytest cuối | [evidence/01-pytest.txt](evidence/01-pytest.txt) | 37 passed |
| Log validator | [evidence/02-log-validator.txt](evidence/02-log-validator.txt) | 100/100 |
| Dashboard validator | [evidence/03-dashboard-validator.txt](evidence/03-dashboard-validator.txt) | 6/6 panel |
| Structured log | [evidence/04-structured-log.txt](evidence/04-structured-log.txt) | trích nguyên văn `data/logs.jsonl` |
| PII redaction | [evidence/05-pii-redaction.txt](evidence/05-pii-redaction.txt) | input PII giả → log đã che |
| Trace list | [evidence/06-trace-list.txt](evidence/06-trace-list.txt) (+ [workload](evidence/06-trace-list-workload.txt)) | 44 traces, đều có `correlation_id` |
| Trace waterfall | [evidence/07-trace-waterfall.txt](evidence/07-trace-waterfall.txt) | agent → retriever, span, generation |
| Trace metadata | [evidence/08-trace-metadata.txt](evidence/08-trace-metadata.txt) | correlation_id, prompt, token, cost; PII đã che |
| Prompt versions | [evidence/09-prompt-versions.txt](evidence/09-prompt-versions.txt) | v1 `baseline`+`production`, v2 `candidate` |
| Prompt rollback | [evidence/10-prompt-rollback.txt](evidence/10-prompt-rollback.txt) | promote v2 rồi rollback v1, kèm 4 trace |
| Dashboard runtime | [evidence/11-dashboard-overview.png](evidence/11-dashboard-overview.png) | 6 panel từ log thật |
| Incident metric | [evidence/12-incident-metric.png](evidence/12-incident-metric.png), [12-incident-metric.txt](evidence/12-incident-metric.txt) | P95 164 → 2659 ms |
| Incident log | [evidence/13-incident-log.txt](evidence/13-incident-log.txt) | `req-86adea6f`, latency 2659 ms |
| Incident trace | [evidence/14-incident-trace.txt](evidence/14-incident-trace.txt) | span `retrieval` 2505/2660 ms |

Evidence phụ:

- Baseline trước khi sửa code: [evidence/baseline/](evidence/baseline/) (`01-pytest-baseline.txt`, `02-log-validator-baseline.txt`, `03-dashboard-validator-baseline.txt`, `load-test.txt`, `logs-baseline.jsonl`).
- Practice scenarios (`rag_slow`, `tool_fail`, `cost_spike`) và bảng tổng hợp: [evidence/practice/](evidence/practice/), đặc biệt [practice-summary.txt](evidence/practice/practice-summary.txt); log practice lưu nguyên tại [logs-practice.jsonl](evidence/practice/logs-practice.jsonl).
- Challenge CP3 (lần chạy có tracing) theo từng pha: [incident/phase1-pre-incident.txt](evidence/incident/phase1-pre-incident.txt), [phase2-challenge-run.txt](evidence/incident/phase2-challenge-run.txt), [phase3-fix-verify.txt](evidence/incident/phase3-fix-verify.txt), [phase3-summary.txt](evidence/incident/phase3-summary.txt). Lần chạy đầu tiên (trước khi có Langfuse key, chỉ có metric + log) giữ nguyên tại [incident/run1-no-trace/](evidence/incident/run1-no-trace/). `config/challenge.json` không được commit.

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (20 record thiếu correlation ID, 20 record thiếu enrichment, 0 correlation ID) | 100/100 trên log cuối (138 record, 68 correlation ID, 0 PII leak) và 100/100 trên log practice (131 record, 68 correlation ID) | Baseline đã pass PII vì `main.py` dùng `summarize_text` cho preview; processor mới che thêm mọi field khác |
| `validate_dashboard.py` | HỢP LỆ 6/6 | HỢP LỆ 6/6 | Contract không đổi; thêm dashboard runtime từ log |
| `pytest` | 22 passed | 37 passed | Thêm test PII (CCCD, thẻ, hộ chiếu, nested field), middleware, child observations, alert/SLO, dashboard builder |
| Số traces hợp lệ | 0 (`tracing_enabled: false`, chưa có key) | 44 traces (16:44–16:50 UTC) | Mọi trace có `correlation_id` trùng log, đủ root + retrieval + generation |
| Số PII leak | 0 | 0 | `grep` 5 giá trị PII giả trong `data/logs.jsonl` trả về 0 dòng |
| Latency P95 / TTFT P95 | 158 ms / 55 ms (31 request bình thường) | 158 ms / 55 ms bình thường; `rag_slow`: 2657 ms / 54 ms | Số từ [practice-summary.txt](evidence/practice/practice-summary.txt) |
| Retrieval success rate | 100% bình thường | 100% bình thường; `tool_fail`: 0%; cả cửa sổ 60 phút: 83.9% | Dashboard báo BREACH error rate 16.1% do đợt `tool_fail` |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** [`app/middleware.py`](../app/middleware.py) gọi `clear_contextvars()` đầu mỗi request, nhận header `x-request-id` nếu đúng format `req-<8-hex>` (không phân biệt hoa thường), ngược lại sinh `req-` + 8 ký tự hex từ `uuid4`. Header sai format (ví dụ chứa xuống dòng) bị thay bằng ID mới để tránh log injection. ID được bind vào structlog contextvars, gắn vào `request.state`, truyền vào `LabAgent.run` (trace metadata `correlation_id`) và trả lại qua header `x-request-id` cùng `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** ngoài `ts`, `level`, `service`, `event`, `correlation_id`, handler `/chat` ([`app/main.py`](../app/main.py)) bind `user_id_hash` (SHA-256 cắt 12 ký tự, không log user_id gốc), `session_id`, `feature`, `model`, `env` **trước** dòng `request_received`, nên `request_received`, `response_sent` và `request_failed` đều mang chung context. `response_sent` có thêm `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** [`app/logging_config.py`](../app/logging_config.py) đăng ký `scrub_event` sau `format_exc_info` (để cả exception text đã render cũng được che) và **trước** `JsonlFileProcessor`/`JSONRenderer`. `scrub_event` đi đệ quy qua mọi field string, dict, list, không chỉ `event`/`payload`. Pattern trong [`app/pii.py`](../app/pii.py): email, thẻ 16 số (có/không dấu cách hoặc gạch), CCCD 12 số, điện thoại VN (`0`/`+84` + 9 số với các dấu phân cách phổ biến), hộ chiếu VN (1 chữ in hoa + 7 số). Thẻ và CCCD được che trước điện thoại để dãy số dài không bị che dở dang.
- **Cách kiểm chứng kết quả:** `tests/test_pii.py` (từng loại PII, text không PII giữ nguyên, nested field/exception), `tests/test_middleware.py` (ID hợp lệ được giữ, ID xấu được sinh lại, hai request liên tiếp không rò `session_id`, log không có PII thô). Runtime: request chứa PII giả với `x-request-id: req-1a2b3c4d` và `req-5e6f7a8b` cho log `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`, `[REDACTED_CREDIT_CARD]`, `[REDACTED_PASSPORT_VN]` ([05-pii-redaction.txt](evidence/05-pii-redaction.txt)); `validate_logs.py` 100/100.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** key trong `.env` thuộc project id `cmuoc4b000091ad0cu72s4cij` (Public API `/api/public/projects` trả đúng một project). Toàn bộ 44 trace trong [06-trace-list.txt](evidence/06-trace-list.txt) có timestamp trùng các lần tôi chạy `load_test.py` (16:44:58–16:45:05 UTC, [06-trace-list-workload.txt](evidence/06-trace-list-workload.txt)), bước prompt (16:47) và challenge (16:48–16:50). `correlation_id` trong metadata của từng trace trùng với dòng log trong `data/logs.jsonl`, ví dụ `req-fbda67c9` ([08-trace-metadata.txt](evidence/08-trace-metadata.txt) in cả trace lẫn log line).
- **Cấu trúc root/retrieval/generation observations:** [`app/agent.py`](../app/agent.py) dùng Langfuse SDK v4 ([07-trace-waterfall.txt](evidence/07-trace-waterfall.txt), trace `183e8e2d6fd4722c66d358364ee487ae`):

  ```text
  day13-agent-request (trace, qua propagate_attributes: user_id_hash, session_id, tags, correlation_id)
  └── [AGENT] lab-agent-run          160ms  (@observe; metadata prompt_name/label/version/source, query_preview đã scrub)
      ├── [RETRIEVER] retrieval        1ms  (input query_preview, output doc_count + doc_previews, metadata tool_success, retrieval_ms; lỗi → level=ERROR)
      ├── [SPAN] prompt-resolve        0ms  (prompt_name/label/version/source, prompt_resolve_ms)
      └── [GENERATION] llm-generation 158ms (model claude-sonnet-4-5, prompt day13-chat v1, usage input/output/total, cost input/output/total, completion_start_time = start + TTFT)
  ```

  Input/output của observation chỉ là preview đã qua `summarize_text` (scrub PII + cắt ngắn); root dùng `capture_input=False, capture_output=False`. Trace `52ebefaa11631f3932f57fafc717170d` của câu hỏi chứa email chỉ có `[REDACTED_EMAIL]`.
- **Cách nối trace với log:** `correlation_id` nằm trong trace metadata (qua `propagate_attributes`) và trong mọi dòng log của request; `user_id` của trace chính là `user_id_hash` trong log (ví dụ `2055254ee30a`), `session_id` trùng nhau. [`scripts/langfuse_traces.py`](../scripts/langfuse_traces.py) `show --correlation-id <id>` tìm trace từ ID lấy trong log.
- **Prompt name:** `day13-chat` (text prompt, giữ ba biến `{{feature}}`, `{{docs}}`, `{{message}}`)
- **Version/label baseline:** v1 — labels `baseline`, `production`; template `Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}`.
- **Version/label candidate:** v2 — label `candidate`; thêm một dòng yêu cầu trả lời tối đa 3 bullet ngắn. Với cùng input, `tokens_in` tăng từ 32 (v1) lên 57 (v2).
- **Trace ID của mỗi version** (cùng input *"Explain why metrics traces and logs work together"*, [10-prompt-rollback.txt](evidence/10-prompt-rollback.txt)):

  | Bước | correlation_id | Trace ID | label / version |
  |---|---|---|---|
  | `LANGFUSE_PROMPT_LABEL=baseline` | `req-0000b001` | `73c317538fe491ea09491fbb6bb60f4a` | baseline / 1 |
  | `LANGFUSE_PROMPT_LABEL=candidate` | `req-0000c002` | `4aafeab3bc04a48ddfe6a3bf03908e06` | candidate / 2 |
  | Sau promote `production` → v2 | `req-0000d003` | `863f2252343694cb62ebbaf01ce1a25c` | production / 2 |
  | Sau rollback `production` → v1 | `req-0000e004` | `6cd2c1aabb6d6fa57b4094f26b22e739` | production / 1 |
- **Cách promote và rollback `production`:** code không đổi khi đổi version; app lấy prompt theo `LANGFUSE_PROMPT_NAME` + `LANGFUSE_PROMPT_LABEL` ([`app/prompt_management.py`](../app/prompt_management.py)). `python scripts/langfuse_prompt_setup.py promote` gọi `update_prompt(version=2, new_labels=["candidate","production"])` (16:47:35 UTC); `rollback` gọi `update_prompt(version=1, new_labels=["baseline","production"])` (16:47:54 UTC). Langfuse tự gỡ label `production` khỏi version cũ vì label là duy nhất. Script in trạng thái trước/sau mỗi lần đổi. API cache prompt 60 giây (`cache_ttl_seconds=60`) nên tôi khởi động lại API sau mỗi lần đổi label để request tiếp theo dùng ngay version mới.

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

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort K4, seed 1312, `latency_threshold_ms` 2000, feature bị ảnh hưởng `monitoring`, 5 query; incident do `inject_incident.py` đọc từ `config/challenge.json`).
- **Khoảng thời gian điều tra:** 2026-09-30 **16:48:56 → 16:49:12 UTC** (từ `inject_incident.py` tới khi load test challenge kết thúc). Pha trước sự cố: 16:48:48 → 16:48:56 UTC (cùng 5 query, 2 lượt). Pha sau fix: từ 16:49:53 UTC. Đây là lần chạy thứ hai, sau khi có Langfuse key; lần đầu (16:39:43–16:39:59 UTC, không có trace) cho kết quả metric/log giống hệt và được giữ tại [incident/run1-no-trace/](evidence/incident/run1-no-trace/).
- **Triệu chứng từ metrics:** [12-incident-metric.txt](evidence/12-incident-metric.txt), [12-incident-metric.png](evidence/12-incident-metric.png), [phase3-summary.txt](evidence/incident/phase3-summary.txt)

  | Pha | Request | Error % | Retrieval OK % | P50/P95/P99 latency | TTFT P95 | Avg cost | Avg tokens_out |
  |---|---:|---:|---:|---|---:|---:|---:|
  | Trước sự cố | 10 | 0.0 | 100.0 | 152/164/164 ms | 51 ms | 0.002113 | 133.9 |
  | Sự cố | 5 | 0.0 | 100.0 | 2655/2659/2659 ms | 50 ms | 0.002214 | 140.6 |
  | Sau fix | 5 | 0.0 | 100.0 | 158/163/163 ms | 55 ms | 0.002226 | 141.4 |

  Latency tăng ~2.5 giây và vượt `latency_threshold_ms` 2000 của challenge (alert `HighLatencyP95` > 2000 ms sẽ kích hoạt; panel latency của contract vẫn OK vì ngưỡng 3000 ms). Error, retrieval success, cost, token và quality không đổi → không phải lỗi, không phải cost/prompt regression. TTFT không đổi → LLM vẫn sinh token đầu nhanh như bình thường. Phía client, latency tăng từ 477–819 ms lên 8.0–13.3 s ([phase2-challenge-run.txt](evidence/incident/phase2-challenge-run.txt)) vì các request xếp hàng sau nhau trên event loop (xem mục 8).
- **Log line và correlation ID liên quan:** [13-incident-log.txt](evidence/13-incident-log.txt). Lọc `event == "response_sent"` và `latency_ms > 2000` trong khoảng sự cố cho ra đúng 5 request challenge (2653–2659 ms). Request chậm nhất `correlation_id=req-86adea6f` (session `k4-l3b-challenge-s03`, feature `monitoring`) có `latency_ms=2659`, `ttft_ms=50`, `tokens_out=83`, `tool_name=retrieval`, `tool_success=true`. Cùng query trước sự cố chỉ mất 151–152 ms. Log control plane `incident_enabled` (`payload.name=rag_slow`) lúc 16:48:57.239 UTC trùng thời điểm latency bắt đầu tăng.
- **Trace ID và span gây ảnh hưởng:** [14-incident-trace.txt](evidence/14-incident-trace.txt). Trace `4f43433887ff09f88e9f9d345f6bc02f` có metadata `correlation_id=req-86adea6f`:

  | Span | Sự cố (`req-86adea6f`) | Trước sự cố (`req-05b28ace`, trace `df6b1a35cfa5591b01927b44ff2469a8`) | Sau fix (`req-d734c010`, trace `183e8e2d6fd4722c66d358364ee487ae`) |
  |---|---:|---:|---:|
  | `lab-agent-run` (root) | 2660 ms | 153 ms | 160 ms |
  | `retrieval` | **2505 ms** (`retrieval_ms=2500`, `tool_success=true`) | 0 ms | 1 ms |
  | `prompt-resolve` | 1 ms | 1 ms | 0 ms |
  | `llm-generation` | 152 ms | 151 ms | 158 ms |

  Span gây ảnh hưởng là **`retrieval`**, chiếm 2505/2660 ms (~94%) của request; generation và prompt không đổi.
- **Root cause:** bước retrieval (RAG / vector store) chậm thêm ~2.5 giây mỗi lần gọi do incident `rag_slow` được bật lúc 16:48:57 UTC. Ba lớp evidence cùng chỉ về một chỗ: metric có latency tăng một lượng cố định trong khi TTFT/token/cost/error không đổi, log có `req-86adea6f` 2659 ms với `ttft_ms` bình thường kèm dòng `incident_enabled rag_slow` cùng thời điểm, và trace cùng `correlation_id` cho thấy span `retrieval` 2505 ms.
- **Fix action:** tắt cấu hình gây chậm retrieval (`python scripts/inject_incident.py --disable`, 16:49:53 UTC), rồi chạy lại đúng 5 query challenge để kiểm chứng. Kết quả: P95 về 163 ms, TTFT 55 ms, 0% lỗi, span `retrieval` còn 1 ms ([phase3-fix-verify.txt](evidence/incident/phase3-fix-verify.txt), [phase3-summary.txt](evidence/incident/phase3-summary.txt)).
- **Preventive measure:** (1) alert `HighLatencyP95` (> 2000 ms trong 5 phút) kèm runbook alert 1 trong [`docs/alerts.md`](../docs/alerts.md): bước 1 so sánh latency với TTFT, bước 3 mở span `retrieval`. (2) Đặt timeout và latency budget cho retrieval (ví dụ 500 ms), khi quá hạn thì trả fallback thay vì chờ. (3) Ghi `retrieval_ms` vào `response_sent` để lọc được bằng log mà không cần mở trace. (4) Chạy `agent.run` trong threadpool (`def` endpoint hoặc `run_in_threadpool`) để một request chậm không làm các request khác chờ theo.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** tạo child observation bằng `langfuse_client.start_as_current_observation(...)` (context manager) thay vì chỉ gắn thêm `@observe` lên hàm `retrieve`/`generate`. Context manager cho phép (1) cập nhật `usage_details`/`cost_details`/`completion_start_time` sau khi có response, (2) tự quyết định input/output chỉ là preview đã scrub thay vì để decorator capture argument thô chứa PII, (3) đánh dấu `level=ERROR` + `tool_success=false` khi retrieval lỗi rồi re-raise, (4) giữ quan hệ cha-con vì observation mới luôn là con của span hiện tại (`lab-agent-run`). Metadata prompt vẫn cập nhật trên root sau khi retrieval đóng, nên test contract cũ vẫn đúng.
- **Một lỗi/blocker đã gặp:** (0) Trace đầu tiên `52ebefaa11631f3932f57fafc717170d` có root 1684 ms nhưng `retrieval` 0 ms + `llm-generation` 152 ms, tức khoảng 1.5 giây không thuộc span nào. (1) `validate_logs.py` đọc toàn bộ `data/logs.jsonl`, nên sau khi sửa code các dòng baseline cũ (`correlation_id: "MISSING"`) vẫn làm điểm thấp. (2) Sau khi thêm child observation, fake client trong `tests/test_agent_prompt_trace.py` không có `start_as_current_observation` nên test cũ sẽ lỗi.
- **Cách tìm nguyên nhân và xử lý:** (0) Khoảng trống nằm giữa retrieval và generation, đúng chỗ `resolve_prompt` gọi Langfuse lấy prompt khi cache còn trống. Tôi thêm span `prompt-resolve` có `prompt_resolve_ms`; trace sau đó cho thấy lần fetch lạnh mất 1166 ms (`req-0000c002`), còn khi cache ấm chỉ 0–1 ms ([07-trace-waterfall.txt](evidence/07-trace-waterfall.txt)). Nếu không có span này, một sự cố Langfuse chậm sẽ trông như thời gian bị mất không rõ ở đâu. (1) Chuyển log baseline sang [`evidence/baseline/logs-baseline.jsonl`](evidence/baseline/logs-baseline.jsonl), khởi động lại API rồi đo lại (30/100 → 100/100). (2) Mở rộng fake client để ghi lại từng observation và thêm test kiểm tra retrieval/generation, model, usage, cost, không có PII thô và trường hợp retrieval lỗi; test cũ về prompt metadata giữ nguyên assertion. Ngoài ra tôi cũng nhận thấy latency phía client khi chạy `--concurrency 5` là 324–804 ms trong khi `latency_ms` phía server của cùng các request chỉ 151–155 ms ([practice/concurrency-5.txt](evidence/practice/concurrency-5.txt)): endpoint `async def` gọi `agent.run` đồng bộ nên các request xếp hàng trên event loop. Header `x-response-time-ms` phản ánh được thời gian chờ này, còn `latency_ms` thì không.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics trả lời "có vấn đề gì và từ lúc nào" trên toàn bộ traffic (ví dụ P95 tăng trong khi TTFT không đổi); logs cho phép lọc trong đúng khoảng đó để chọn một request cụ thể bằng `correlation_id` và thấy các field của nó; trace của chính request đó chia thời gian/lỗi ra từng span (`retrieval` hay `llm-generation`) để khoanh vùng root cause. Chỉ kết luận khi cả ba lớp cùng chỉ về một nguyên nhân.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt thay đổi hành vi như một lần deploy nhưng không đi qua code, nên mỗi trace phải ghi `prompt_name/label/version` để biết request dùng version nào; token/cost trên generation cho biết một thay đổi (prompt dài hơn, output dài hơn) tốn thêm bao nhiêu — practice `cost_spike` làm cost/request tăng ~4.4 lần mà traffic không đổi; SLO và error budget quyết định khi nào phải dừng thay đổi để ưu tiên ổn định; rollback bằng cách chuyển label `production` là cách khôi phục nhanh nhất vì không cần deploy.
- **Điều quan trọng nhất đã học:** redaction phải nằm trong pipeline logging trước bước render/ghi file và phủ mọi field, không dựa vào việc từng chỗ gọi log nhớ tự scrub; và alert nên được đặt theo số đo baseline thực tế — ngưỡng SLO 3000 ms không bắt được `rag_slow` (2657 ms).
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** evidence Langfuse là output text từ Public API, chưa có ảnh chụp UI. Quality score là heuristic trên câu trả lời cố định của FakeLLM nên gần như không đổi (0.8–0.9). Request lỗi 500 trả `correlation_id` trong header `x-request-id` nhưng không trong body. Alert mới được định nghĩa trong YAML, chưa nối với hệ thống gửi Slack thật.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
