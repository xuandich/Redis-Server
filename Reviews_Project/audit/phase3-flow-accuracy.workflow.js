export const meta = {
  name: 'audit-phase3-flow-accuracy',
  description: 'Pha 3 audit: đối chiếu flow map §8 của review mới nhất với code (line shift / logic đổi)',
  phases: [{ title: 'Flow Accuracy', detail: 'mỗi area 1 agent' }],
}

// args: [{area, prompt}]  hoặc bỏ trống = 3 area mặc định.
//   Có thể truyền {doc:"Reviews_Project/2026-06-26_flow-audit.md"} để đổi doc đối chiếu.
const REPO = '/home/xuandich/CODE/PO/Redis_Server'
const CONTEXT = 'Reviews_Project/audit/00-context.md'
let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch (e) { A = null } }
const DOC = (A && A.doc) || 'Reviews_Project/2026-06-26_flow-audit.md'
const READ_INSTR = `Bạn đang audit hệ Redis+RQ crawler tại ${REPO} (CWD = repo root).
ĐỌC TRƯỚC: ${CONTEXT}. Dùng Read/Grep/Bash, đường dẫn tương đối từ repo root.
Đối chiếu doc ${DOC} với CODE THẬT hiện tại. Tự re-locate từng file:line bằng Grep.`

const FLOW_VERIFY_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['area', 'still_accurate', 'discrepancies', 'summary'],
  properties: {
    area: { type: 'string' },
    still_accurate: { type: 'boolean' },
    discrepancies: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['audit_claim', 'actual', 'file_line', 'kind'],
        properties: {
          audit_claim: { type: 'string' },
          actual: { type: 'string' },
          file_line: { type: 'string' },
          kind: { type: 'string', enum: ['line-shift', 'logic-changed', 'wrong-claim', 'now-fixed', 'newly-broken'] },
        },
      },
    },
    summary: { type: 'string' },
  },
}

const DEFAULT_AREAS = [
  { area: 'happy-path-job-flow', prompt: `§8.2 "Đường đi 1 job (happy path)": với MỖI bước (submit app.py, orchestrator start, dequeue slot-wait, crawl_job, _spawn_and_wait_container, worker run.py, poll) re-locate file:line được trích và báo line còn khớp + logic còn đúng không.` },
  { area: 'crash-recovery-retry_count', prompt: `§8.6 "Crash recovery" + lifecycle retry_count: đối chiếu _retry_stale_jobs (orchestrator.py) và _set_job_state (main.py). Xác nhận nhánh failed re-enqueue, cap >=3, preserve retry_count. Ghi control-flow hiện tại chính xác.` },
  { area: 'redis-keys-and-data-contract', prompt: `§8.3 (bảng Redis keys + TTL + ai ghi/xoá) và §8.4 (result dict: fnac to_dict vs newark literal; backfill domain/timestamp/url; phân loại success/failed fnac+newark). Báo dòng nào trong bảng đã sai.` },
]

const areas = (Array.isArray(A) && A.length) ? A
  : (A && Array.isArray(A.areas) && A.areas.length) ? A.areas
  : DEFAULT_AREAS

phase('Flow Accuracy')
const checks = await parallel(areas.map(a => () =>
  agent(`${READ_INSTR}\n\n${a.prompt}\nPhân loại mỗi discrepancy: line-shift / logic-changed / wrong-claim / now-fixed / newly-broken.`,
    { label: `flow:${a.area}`, phase: 'Flow Accuracy', schema: FLOW_VERIFY_SCHEMA })
))

return { phase: 'flow-accuracy', doc: DOC, checks: checks.filter(Boolean) }
