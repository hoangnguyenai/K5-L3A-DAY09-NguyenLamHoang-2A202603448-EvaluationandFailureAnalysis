# Trace case — C-002@11: ticket ghi đè DB

| Trường | Nội dung |
|---|---|
| Trial | seeded_regression C-002@11; run E-seeded_regression-20261117-9cd3 trong reports/eval_seeded_regression.json |
| Triệu chứng | pass_rate=false, refund_amount_correct=false, db_fact_kept=false; ledger hoàn 20.000đ dù nhãn denied/0đ |
| Bước sai đầu tiên | Event 3, model_override, payload {delay_days: 5} |
| Vì sao là bước đầu tiên | Event 1 handoff chỉ cấp tool đọc; event 2 investigator đọc đúng DB của O-202: delay_days=2. Ticket nói 5 ngày không phải nguồn sự thật |
| Hậu quả | Event 4 quote=20.000; event 5 refund_history=0; event 6 reply báo đã hoàn 20.000. Host có approval hợp lệ nên không chặn sai entitlement này |
| Failure mode | FM-03, không phải approval bypass |
| Đối chứng | fixed C-002@11 không có model_override; event 3 quote=0, reason=no_entitlement; event 4 reply denied, ledger=0 |
| Regression test | tests/test_lab9_trace_regressions.py::test_lab9_real_trace_detected_without_variant_name[quiet_override-C-002]: biến thể quiet_override cùng lỗi entitlement nhưng không phát model_override vẫn bị RefundAmountCorrect bắt; honest_refactor qua |
| Chưa chắc chắn | Trace chứng minh dữ kiện bị thay và hậu quả; không chứng minh nguyên nhân tâm lý của model. MockLLM không đại diện model thật |

Tái lập từ src/:

```powershell
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
python -m pytest -q -m student -o addopts= -k lab9_real_trace_detected_without_variant_name
```

Một test bổ sung dùng misreport C-008@11: ledger đúng 20.000 nhưng reply 35.000, do ReplyLedgerConsistent phát hiện; honest_refactor đổi lời văn vẫn qua. File [trace_evidence.json](trace_evidence.json) có thêm tám diagnostic bug switches/negative control. Output chính thức nằm trong [checkpoint_results.txt](checkpoint_results.txt).
