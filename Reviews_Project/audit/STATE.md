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

## Chu trình hiện tại — ✅ ĐÓNG. AUDIT 2026-07-01 (worker MỚI amazon_fr + Dashboard routing)

- **Bắt đầu/Đóng**: 2026-07-01
- **Commit nền**: `57ec6b4` (HEAD). Diff audit từ `ef7e652`: amazon_fr worker MỚI ~822 dòng (thêm `ceee225`, extractor sửa `1cc22f3`), Dashboard routing ~55, orchestrator +1.
- **Phạm vi**: 1 Workflow toàn diện `find→verify→escalate→completeness` (9 dim, 5 cho amazon_fr). Đợt đầu session-limit 9 agent → **resume same-session** (`resumeFromRunId=wf_47eb1727-597`) cache-hit 41, chạy nốt 10. Maintainer đọc code thật adjudicate resource-leak.
- **Kết quả**: ✅ **9 bug MỚI BUG-99..107** (1 HIGH · 3 MED · 5 LOW). File bug + report `2026-07-01_flow-audit.md` + context §4/§5/§6 đã cập nhật.

### Tiến độ
| Pha | Trạng thái | runId | Kết quả |
|---|---|---|---|
| find→verify→escalate→completeness | ✅ done | `wf_47eb1727-597` | 51 agent, 37 finding → 21 confirmedFinal (survives_escalation) → dedup **9 bug**. Payload: `results/final-2026-07-01.json` |

### Chốt quan trọng
- **BUG-81**: fix ĐÃ CÓ & ĐÚNG (`app.py:724` urlparse+strip port). Cờ "MISSING" của STATE 06-29 là **LỖI THỜI** — đã xóa. Rename `(FIXED)` chính đáng.
- **06-29 cycle**: ĐÃ ĐÓNG từ trước (BUG-82..98 đã commit `8705ef6`); phần "chờ tạo file / P5 HOÃN" trong STATE cũ là tàn dư — dọn.
- BUG-99 (HIGH false-success amazon_fr) = ưu tiên fix số 1.

### ⏭️ Việc tiếp theo (tồn đọng, ngoài phạm vi diff 07-01)
- [ ] Fix BUG-99..102 (xem §5 report 07-01).
- [ ] *(tồn từ trước)* BUG-91 (heartbeat SimpleWorker — áp cả amazon_fr 300s), BUG-77 (pubsub leak), BUG-84/88, BUG-74/69.

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
| 2026-06-29 | Re-audit P1+P6+P4+P5 (coordinator budget-aware) | BUG-82 → BUG-98 | *(chốt qua commit `8705ef6`, không có file review riêng)* |
| 2026-07-01 | Worker MỚI amazon_fr + Dashboard routing | BUG-99 → BUG-107 | [2026-07-01](../2026-07-01_flow-audit.md) |
