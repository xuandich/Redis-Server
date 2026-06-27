export const meta = {
  name: 'audit-phase1-verify-fixes',
  description: 'Pha 1 audit: verify các fix gần đây có hiện diện + đúng + không regression',
  phases: [{ title: 'Verify Fixes', detail: 'mỗi bug 1 agent đọc bug-file + code' }],
}

// args: ["BUG-13","BUG-60"]  hoặc  [{id:"BUG-13", focus:"orchestrator.py start_worker_for_domain"}]
const REPO = 'thư mục repo hiện tại (CWD của bạn — repo root)'
const CONTEXT = 'Reviews_Project/audit/00-context.md'
const READ_INSTR = `Bạn đang audit hệ Redis+RQ crawler tại ${REPO} (CWD = repo root).
ĐỌC TRƯỚC: ${CONTEXT} (file map, danh sách bug, fix gần đây, quy ước). Dùng Read/Grep/Bash, đường dẫn tương đối từ repo root.
Đọc CODE THẬT — KHÔNG tin line number trong doc cũ, tự xác minh bằng Grep. Trích mọi nhận định dạng file:line.`

const FIX_VERIFY_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['bug_id', 'fix_present', 'fix_correct', 'regression_risk', 'issues', 'verdict'],
  properties: {
    bug_id: { type: 'string' },
    fix_present: { type: 'boolean' },
    fix_correct: { type: 'boolean', description: 'fix có THỰC SỰ giải quyết bug nó tuyên bố không' },
    regression_risk: { type: 'string', enum: ['none', 'low', 'medium', 'high'] },
    issues: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['severity', 'description', 'file_line'],
        properties: {
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'nit'] },
          description: { type: 'string' },
          file_line: { type: 'string' },
        },
      },
    },
    verdict: { type: 'string', description: 'kết luận 1-3 câu' },
  },
}

let parsed = args
if (typeof parsed === 'string') { try { parsed = JSON.parse(parsed) } catch (e) { parsed = null } }
const raw = Array.isArray(parsed) ? parsed : (parsed && parsed.bugs) || []
if (!raw.length) {
  log('Không có bug ID. Truyền args=["BUG-13","BUG-60",...] hoặc [{id,focus}].')
  return { phase: 'verify-fixes', error: 'no bug ids', results: [] }
}

phase('Verify Fixes')
const results = await parallel(raw.map(item => {
  const id = typeof item === 'string' ? item : item.id
  const focus = (item && item.focus) ? `\nGỢI Ý vùng code: ${item.focus}` : ''
  return () => agent(
    `${READ_INSTR}\n\nVerify ${id} đã được FIX ĐÚNG và KHÔNG gây regression.${focus}\n` +
    `Bước: (1) Đọc Bugs/${id}*.md để biết claim gốc + fix dự kiến. (2) Đọc code được trích (tự xác minh line hiện tại). ` +
    `(3) fix có HIỆN DIỆN không; có THỰC SỰ giải quyết bug không; trace mọi nhánh + exception path + tương tác code khác để tìm regression/cạnh. ` +
    `(4) Nếu fix trải nhiều file, kiểm tất cả. Đừng tin mô tả — đọc code và thử phá.`,
    { label: `verify:${id}`, phase: 'Verify Fixes', schema: FIX_VERIFY_SCHEMA })
}))

return { phase: 'verify-fixes', results: results.filter(Boolean) }
