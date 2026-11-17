# Chạy Lab 9 theo checkpoint

Mọi lệnh chạy từ `src/`, sau khi cài `requirements.txt` và `requirements-lab9.txt` vào môi trường Python ≥3.11. Đề gốc: [README](lab9-assignment/README.md), [CHECKPOINTS](lab9-assignment/CHECKPOINTS.md), [RUBRIC](lab9-assignment/RUBRIC.md), [SUBMISSION](lab9-assignment/SUBMISSION.md).

## M0–M1: môi trường và eval set

```powershell
python -m lab9.smoke
python -m lab9.evalset --build --check
python -m lab9.evalset --v2 --build
```

Mong đợi: M0 PASS, v1=14 item, v2=28 item, cả hai 0 problem. Nhãn nằm ở labels_v1/v2.json, tách khỏi JSONL item. Xem failure_taxonomy.md và trace_evidence.json để đối chiếu mã FM với trace.

## M2–M3: judge và grader

```powershell
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 7
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
python -m pytest -q tests/test_lab9_evalset.py -o addopts=
python -m pytest -q -m student -o addopts= -k "lab9 and not advanced"
python -m lab9.mutation --detect
```

Tone phải PASS, helpful phải FAIL (exit 1 đúng mong đợi); detection≥80%, false alarms≤10%. Nếu Windows báo không truy cập được Temp/pytest-of-Hoang hoặc cache pytest, thêm `--basetemp "$env:TEMP/lab9-$([guid]::NewGuid())" -p no:cacheprovider` vào lệnh pytest để dùng đường dẫn mới; không cần sửa test, xóa cache hay chạy Administrator.

## M4: baseline và gate

```powershell
python -m lab9.eval --shape swarm --out reports/baseline_v1.json
python -m lab9.eval --shape fixed
python -m lab9.gate --pr reports/eval_fixed.json --baseline reports/baseline_v1.json
python -m lab9.eval --shape seeded_regression
python -m lab9.gate --pr reports/eval_seeded_regression.json --baseline reports/baseline_v1.json
```

Fixed phải exit 0. Seeded regression phải exit 1, danh sách block có pass_rate; Δ=-0.271, CI=[-0.500,-0.057]. Không chỉnh tay reports.

## M5–M7: advanced và integrity

```powershell
python -m pytest -q -m student -o addopts= -k advanced
python -m lab9.eval --shape swarm --spec config/metric_spec_v2.yaml --out reports/baseline_v2.json
python -m lab9.mutation --spec config/metric_spec_v2.yaml --aa 66,77,88,99,110
python -m lab9.mutation --spec config/metric_spec_v2.yaml --baseline reports/baseline_v2.json
python -m lab9.eval --shape slice_regression --spec config/metric_spec_v2.yaml --out reports/eval_v2_slice_regression.json
python -m lab9.traps --pr reports/eval_v2_slice_regression.json --baseline reports/baseline_v2.json --spec config/metric_spec_v2.yaml
```

A/A Δ=0; mutation=3/3, 0 false alarms; traps tổng exit 0 khi gate đã chặn từng trap. Muốn đối chiếu từng trap, dùng các lệnh gate do traps in ra; mỗi lệnh gate phải exit 1 với INTEGRITY/ratchet. Log kiểm chứng ở checkpoint_results.txt.

