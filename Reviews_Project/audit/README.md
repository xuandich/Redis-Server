# Audit Harness — re-audit theo 5 pha, chạy nhiều lần

Bộ khung re-audit chia thành **5 pha độc lập**, mỗi pha là 1 script workflow riêng. Mục tiêu: mỗi lần chạy là một mẻ nhỏ → **không bao giờ chạm session limit**, và bạn **đọc kết quả giữa các pha** rồi mới quyết pha sau.

> Bối cảnh: lần chạy gộp 67-agent (`wf_2a6903b4`) bị cắt vì 37 agent verify chết ở session limit. Tách find↔verify + chunk-được khắc phục triệt để.

## Quy tắc chung

- Mọi agent đọc [`00-context.md`](00-context.md) trước (file map, danh sách bug, fix gần đây, quy ước).
- Mỗi script nhận `args` để chạy **một phần** → pha nặng gọi lại nhiều lần với `args` khác.
- Script **return** dữ liệu cho main loop; main loop ghi ra `results/`. Script không tự ghi file.
- Chạy 1 pha:
  ```
  Workflow({ scriptPath: "Reviews_Project/audit/phaseN-....workflow.js", args: <tùy pha> })
  ```
- Bị đứt giữa chừng? Resume cùng session: `Workflow({ scriptPath: "...", resumeFromRunId: "<runId>" })` — agent đã xong trả cache.
- **`args` đến script dưới dạng JSON string** (không phải object) → mọi script đã tự `JSON.parse` đầu vào; truyền `args` là mảng/object JSON bình thường, script lo phần parse.

## Thứ tự & cách chạy

### Pha 1 — verify-fixes  `phase1-verify-fixes.workflow.js`
Verify các fix vừa làm có đúng + không regression.
`args`: mảng bug ID, vd `["BUG-13","BUG-60","BUG-61"]` (hoặc `[{id:"BUG-13", focus:"..."}]`).
→ main loop ghi `results/phase1-verify-fixes_<date>.json`.

### Pha 2 — reconcile-bugs  `phase2-reconcile-bugs.workflow.js`
Đối chiếu trạng thái thực tế của bug OPEN với code.
`args`: mảng nhóm `[{label, ids:"16,17,18", focus:"..."}]` **hoặc** mảng ID `["16","17"]`.
Chunk: chạy 2-3 lần, mỗi lần vài nhóm. → `results/phase2-reconcile_<batch>.json`.

### Pha 3 — flow-accuracy  `phase3-flow-accuracy.workflow.js`
Đối chiếu flow map §8 của review mới nhất với code (line shift / logic đổi).
`args`: mảng `[{area, prompt}]` hoặc bỏ trống = 3 area mặc định (happy-path, recovery, redis-keys+contract).
→ `results/phase3-flow_<date>.json`.

### Pha 4 — audit-find  `phase4-audit-find.workflow.js`
Fan-out tìm bug MỚI theo dimension (CHỈ tìm, chưa verify).
`args`: mảng `[{key, prompt}]` hoặc bỏ trống = 8 dimension mặc định. Chunk: chạy theo nhóm dimension.
→ main loop gộp findings ghi `results/findings-pending.json` (hàng đợi chờ verify).

### Pha 5 — audit-verify  `phase5-audit-verify.workflow.js`
Adversarial verify (cố bác bỏ) + dedup từng finding. **Chạy nhiều lần tới cạn.**
`args`: mảng finding (1 batch, ~10-12 cái) lấy từ `results/findings-pending.json`.
Vòng lặp do main loop điều phối:
1. Đọc `findings-pending.json`, lấy ~12 cái đầu làm `args`.
2. Chạy pha 5 → nhận verdicts → append `results/verdicts.json`, xoá 12 cái đã verify khỏi pending.
3. Lặp tới khi pending rỗng.
→ finding `is_real && is_new` → tạo `Bugs/BUG-XX`; bị bác → ghi mục "đã bác bỏ" của review.

### Pha 6 — worker-correctness  `phase6-worker-correctness.workflow.js`  ⚠️ CÓ ĐIỀU KIỆN
Kiểm **tính ĐÚNG hành vi cào** của worker (selector/navigation/parse/validation) — KHÁC pha 1-5 (vốn soi tầng tích hợp/queue/phân loại). Per-domain.
`args`: `["fnac","newark"]` (mặc định nếu bỏ args) · `{domains:[]}` = no-op.
Trả `staticConfirmable` (đẩy được qua pha 5 verify) và `needsRuntime` (phải chạy worker trên HTML thật mới chốt — pha 5 không bác/xác nhận được bằng đọc code).
**🚦 CHỈ chạy khi code worker đổi.** Worker code ít đổi → bình thường BỎ QUA. Kiểm có đổi:
```
git diff --name-only <commit-chạy-pha6-lần-trước>.. -- workers/
```
Nếu không có thay đổi trong `workers/*/sourceCode | run.py | Dockerfile` → không cần chạy.

## Cadence — khi nào chạy pha nào
- **Re-audit thường lệ** (sau mỗi đợt fix / định kỳ): **pha 1 → 5**. Đây là vòng chuẩn.
- **Pha 6**: CHỈ kích hoạt khi `workers/` có thay đổi code. Không nằm trong vòng thường lệ.

## Sau khi xong các pha
Main loop tổng hợp `results/*` → viết snapshot review mới `Reviews_Project/<date>_flow-audit.md` (theo format các file cũ) + cập nhật `00-context.md` §4/§5.

## Cỡ mỗi pha (để không vỡ limit)
P1 ~4-6 · P2 ~9 (chunk được) · P3 ~3 · P4 ~8 (chunk được) · P5 ~10-12/lần (lặp) · P6 ~1/domain (chỉ khi worker đổi). Không pha nào gộp find+verify nữa.
