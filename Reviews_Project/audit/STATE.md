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

## Chu trình hiện tại — RE-AUDIT 2026-06-29 (coordinator budget-aware)

- **Bắt đầu**: 2026-06-29
- **Commit nền**: `ef7e652` (diff từ `16438da`: manomano+orchestra viết lại Playwright ~1000 dòng; app.py/orchestrator.py/main.py đổi)
- **Phạm vi**: P1 verify 6 fix (69,70,74,81,23,48) · P6 worker-correctness (manomano,orchestra — workers ĐỔI nhiều) · P4 5 dim · P5 verify
- **Engine**: `phase0-coordinator.workflow.js` (budget-aware, dừng cứng 95%, mode find/verify). Token học qua `results/token-ledger.json`.
- **Trạng thái tổng**: ✅ **HOÀN TẤT P1+P6+P4+P5** — tất cả audit logic xong; **17 bug mới (BUG-82..98) chờ tạo file**

### Tiến độ
| Pha | Trạng thái | runId | Kết quả |
|---|---|---|---|
| find (P1+P6+P4) mode=find | ✅ done | `wf_51f1e49a` | spent **253k (84%/300k)**, không chạm trần. P1: 5/6 fix OK; **BUG-81 fix MISSING**. P6: 8 static+3 runtime. P4: 12 finding. → **20 finding** chờ verify |
| P5 verify (20 finding) mode=verify | ⬜ HOÃN (quota 7%) | — | input SẴN SÀNG: `results/verify-input.json` (gọn 20) / nguồn `findings-pending.json`. **Resume**: `Workflow(phase0-coordinator, {mode:"verify", totalBudget:300000, findings:<nội dung verify-input.json>})` |

### 📌 Học token (calibration)
- **find một mình = 253k** output token → cycleBudget 300k QUÁ NHỎ cho cả find+verify. Full cycle ước **~530k**.
- Ledger ghi turn find (more_work=true). Quota Team còn **70%** (user cấp) → đủ chạy tiếp.

### Hàng đợi (state máy)
- `results/findings-pending.json`: **20 finding** (đã ghi từ find).
- `results/verify-input.json`: bản gọn 20 finding để feed P5.
- `results/verdicts.json`: chu trình 06-27b đã backup `verdicts_2026-06-27b.json`.

### ⏭️ Việc tiếp theo
- [ ] Hoàn tất `mode=verify` 20 finding (coordinator tự chunk; nếu defer → chạy nốt nextArgs).
- [ ] **BUG-81**: P1 báo fix MISSING/INCORRECT — kiểm `app.py _extract_domain_from_url`; **KHÔNG** rename `(FIXED)` cho tới khi sửa thật.
- [ ] Sau verify: finding `is_real&&is_new` → tạo `Bugs/BUG-82+`; tổng hợp review `2026-06-29_flow-audit.md`; cập nhật `00-context §5` (ID cao nhất hiện = BUG-81).
- [ ] *(tồn từ trước)* BUG-77 pubsub leak.

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
