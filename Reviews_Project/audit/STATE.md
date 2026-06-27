# Audit STATE — trạng thái LIVE của chu trình (đọc file này ĐẦU TIÊN để biết chạy gì tiếp)

> **Main loop CẬP NHẬT file này sau MỖI `Workflow()` return** (checkpoint). Đây là nguồn duy nhất trả lời "đang ở đâu / việc nào xong / việc nào dở / lệnh tiếp theo là gì". Khi quay lại sau khi đứt (limit/đóng máy), đọc file này là tiếp tục được ngay.
>
> Quy ước trạng thái: `✅ done` · `🟡 in-progress (còn deferred)` · `⬜ chưa chạy` · `⏭️ skip (không cần)`.

> ### 🔒 An toàn khi đứt + đổi session (đọc kỹ)
> - **`resumeFromRunId` chỉ dùng trong CÙNG session** (cache agent-đã-xong nằm ở journal session). Session mới KHÔNG resume được bằng runId → **chạy lại mẻ pending còn dở** (rẻ nhờ guard ≤6). Vẫn ghi runId ở bảng dưới để (a) resume same-session, (b) trỏ tới `agent-*.jsonl` forensics.
> - **Khôi phục cross-session/sau khi xóa = nhờ các artifact git**, KHÔNG nhờ runId. Nên: khi chu trình ĐANG DỞ, checkpoint = cập nhật STATE.md **+ commit ép** 2 file hàng đợi (chúng bị gitignore):
>   ```
>   git add -f Reviews_Project/audit/results/findings-pending.json Reviews_Project/audit/results/verdicts.json
>   git add Reviews_Project/audit/STATE.md && git commit -m "checkpoint audit: <pha> mẻ <n>"
>   ```
>   → Xóa sạch + đổi máy vẫn `git restore` lại đủ để chạy tiếp. Chu trình ĐÓNG xong thì 2 file JSON có thể bỏ khỏi git lại (review đã chốt nội dung).

---

## Chu trình hiện tại — RE-AUDIT TOÀN DIỆN (logic mới chunked)

- **Bắt đầu**: 2026-06-27 (chiều)
- **Commit nền**: `16438da`
- **Phạm vi**: re-audit chuẩn pha 1→5 từ đầu, dùng guard cỡ-mẻ mới. Pha 6 skip (workers/ không đổi từ 06-27).
- **Trạng thái tổng**: ✅ **HOÀN TẤT** → review [`2026-06-27b_flow-audit.md`](../2026-06-27b_flow-audit.md), bug mới **BUG-77 → BUG-80**

### Tiến độ từng pha

| Pha | Trạng thái | runId | Kết quả | Deferred còn lại |
|---|---|---|---|---|
| P1 verify-fixes (BUG-13,60,61,20,24,49) | ✅ done | `wf_9ffe76c2` | 6/6 fix ĐÚNG, 0 regression (vài nit) | — |
| P2 reconcile (dashboard/slot/worker — 23 bug) | ✅ done | `wf_b97111c6` | 21 open, 1 partial (BUG-23), 1 fixed | còn ~17 bug LOW chưa nhóm |
| P3 flow-accuracy (3 area) | ✅ done | `wf_89310e2f` | flow đúng; chỉ BUG-60 nay FIXED + line-shift +12 app.py | — |
| P4 find (8 dim, 3 batch) | ✅ done | `wf_4d8e516c`+`wf_9e5c8470`+`wf_c760332e` | 33 finding → 8 new-candidate + 3 borderline; 24 trùng bug cũ | — |
| P5 verify (11 finding, 2 mẻ) | ✅ done | `wf_3906275c`(A=6) + `wf_70dd23f8`(B=5) | **4 confirmed-new** (BUG-77..80) / 7 refuted-hoặc-trùng | — |
| P6 worker-correctness | ⏭️ skip | — | workers/ không đổi từ 06-27 (đã audit) | — |

### Hàng đợi (state máy)

- `results/findings-pending.json`: sẽ ghi sau khi P4 xong
- `results/verdicts.json`: của chu trình 06-27 (sẽ backup trước khi P5 chạy)

### ⏭️ Việc tiếp theo

- [ ] **Rename `Bugs/BUG-60*` → `(FIXED)`** (P1+P3 xác nhận đã fix; file chưa rename).
- [ ] Fix ưu tiên: **BUG-77** (pubsub leak) → còn tồn từ 06-27: **BUG-74** (timeout HIGH), **BUG-69** (manomano false-success HIGH).
- [ ] *(tùy chọn)* Reconcile nốt ~17 bug LOW chưa nhóm ở P2 (36-47, 62-64...).
- [ ] *(tùy chọn)* Runtime-check 7 selector-fragility của 06-27a.

---

## Cách dùng file này để resume (mẫu khi chu trình ĐANG DỞ)

Khi một pha bị đứt giữa chừng, bảng "Tiến độ" sẽ có dòng `🟡 in-progress` kèm **lệnh chạy tiếp chính xác**. Ví dụ:

```
| P5 verify | 🟡 in-progress | wf_xxx | đã verify 6/18, append verdicts.json | 12 cái trong findings-pending.json |
```
→ Lệnh tiếp: `Workflow({ scriptPath: "Reviews_Project/audit/phase5-audit-verify.workflow.js", args: <6 cái đầu còn lại từ findings-pending.json> })`
→ Verify xong: append `verdicts.json`, **xóa 6 cái khỏi `findings-pending.json`**, cập nhật lại dòng này. Lặp tới khi pending rỗng → đổi `🟡` thành `✅`.

Nếu workflow tự cắt mẻ (guard `MAX_*`), field `deferred` trong kết quả = phần chưa chạy → ghi vào cột "Deferred còn lại" + chạy lại pha đó với `args=deferred`.

---

## Lịch sử chu trình (đã đóng)

| Ngày | Phạm vi | Bug mới | Review |
|---|---|---|---|
| 2026-06-19 | Full audit đầu | (nền BUG-01..15) | [2026-06-19](../2026-06-19_flow-audit.md) |
| 2026-06-23 | Full re-audit | BUG-16 → BUG-59 | [2026-06-23](../2026-06-23_flow-audit.md) |
| 2026-06-26 | Re-audit + verify 4 fix | BUG-60 → BUG-68 | [2026-06-26](../2026-06-26_flow-audit.md) |
| 2026-06-27 | 2 worker mới manomano/orchestra | BUG-69 → BUG-76 | [2026-06-27](../2026-06-27_flow-audit.md) |
| 2026-06-27b | Re-audit toàn diện pha 1→5 (chunked) | BUG-77 → BUG-80 | [2026-06-27b](../2026-06-27b_flow-audit.md) |
