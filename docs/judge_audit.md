# Judge audit — Nguyễn Lâm Hoàng, 2A202603448

Calibration dùng CSV replay công khai, FAIL là lớp dương. Lệnh và output ở [checkpoint_results.txt](checkpoint_results.txt).

| Tiêu chí | n | κ | Precision | Recall | TP / FP / FN / TN | Quyết định |
|---|---:|---:|---:|---:|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | 24 / 4 / 6 / 66 | Đạt κ≥0.6, P≥0.8, R≥0.7 trên replay |
| helpful | 100 | 0.375 | 1.000 | 0.300 | 9 / 0 / 21 / 70 | Loại khỏi gate: bỏ sót 21/30 lỗi |

Tone có fail rate quan sát 0.28, sensitivity=0.8, specificity=66/70; Rogan–Gladen hiệu chỉnh thành 0.30. Helpful có observed=0.09, corrected=0.30; hiệu chỉnh prevalence không làm recall của từng case tốt hơn.

## Audit bất đồng

| Case | Human / judge | Ai đúng và lý do | Sửa rubric |
|---|---|---|---|
| H-008 | FAIL / PASS | Người đúng: “em”, “nha”, “anh check” quá suồng sã trong khiếu nại | Thêm ví dụ âm về xưng hô; phân biệt thân thiện và suồng sã |
| H-017 | FAIL / PASS | Theo annotation, người đúng: “bạn”, “nha” không hợp khách lớn tuổi | Ưu tiên “anh/chị”; khi thiếu metadata không tự suy đoán tuổi |
| H-029 | FAIL / PASS | Người đúng: “không cần nhắn thêm” mang tính ra lệnh | Chấm cả câu, không PASS chỉ vì mở đầu “Dạ, vui lòng” |
| H-042 | PASS / FAIL | Người đúng: câu ngắn nhưng đủ ý và lịch sự | Không bắt buộc lời xin lỗi trong mọi reply, không phạt độ ngắn tự thân |
| H-051 | PASS / FAIL | Người đúng: thuật ngữ “refund” được CS cho phép | Thêm glossary từ được phép; không đồng nhất tiếng Anh với thiếu lịch sự |
| H-063 | FAIL / PASS | Người đúng theo note: hứa hoàn thêm ngoài kết quả hệ thống | Cấm hứa không có bằng chứng; số tiền phải kiểm bằng code với ledger |
| H-081 | PASS / FAIL | Note công khai xác nhận nhãn người sai, judge đúng | Chuyển sang tái gán nhãn có người thứ hai duyệt; không sửa CSV để tăng điểm |

Không sửa nhãn/verdict công khai. H-081 cho thấy nhãn người cũng cần audit; các con số calibration giữ nguyên để tái lập. Tuổi khách H-017 đến từ annotation, riêng reply không đủ chứng minh.

## Kết luận

Tone đủ floors trong tập replay; không dùng judge quyết tiền hoặc approval. Helpful bị loại vì κ và recall thấp dù precision hoàn hảo; lời lịch sự không bảo đảm có hướng giải quyết. Cần rubric riêng về hành động tiếp theo và tập người gán nhãn mới trước khi thử lại. Replay 100 mẫu công khai chưa phải held-out; thay model/prompt/rubric phải calibration lại. κ không xác định là FAIL, không coi constant judge là tốt.
