export const meta = {
  name: 'audit-phase2-reconcile-bugs',
  description: 'Pha 2 audit: đối chiếu trạng thái thực tế của bug OPEN với code hiện tại',
  phases: [{ title: 'Reconcile', detail: 'mỗi nhóm bug 1 agent' }],
}

// args:
//   [{label:"dash", ids:"16,29,48", focus:"Dashboard/app.py submit + clear"}]  (nhóm — KHUYẾN NGHỊ)
//   hoặc ["16","17","18"]  (gộp 1 nhóm adhoc)
const REPO = 'thư mục repo hiện tại (CWD của bạn — repo root)'
const CONTEXT = 'Reviews_Project/audit/00-context.md'
const READ_INSTR = `Bạn đang audit hệ Redis+RQ crawler tại ${REPO} (CWD = repo root).
ĐỌC TRƯỚC: ${CONTEXT}. Dùng Read/Grep/Bash, đường dẫn tương đối từ repo root.
Đọc CODE THẬT — KHÔNG tin line number doc cũ, tự xác minh bằng Grep. Trích file:line làm bằng chứng.`

const BUG_STATUS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['bugs'],
  properties: {
    bugs: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['id', 'actual_status', 'evidence', 'note'],
        properties: {
          id: { type: 'string' },
          actual_status: { type: 'string', enum: ['open', 'fixed', 'partially-fixed', 'changed-context', 'not-a-bug', 'cannot-determine'] },
          evidence: { type: 'string', description: 'file:line chứng minh trạng thái' },
          note: { type: 'string' },
        },
      },
    },
  },
}

let parsed = args
if (typeof parsed === 'string') { try { parsed = JSON.parse(parsed) } catch (e) { parsed = null } }
let groups = []
if (Array.isArray(parsed) && parsed.length && typeof parsed[0] === 'object') {
  groups = parsed
} else if (Array.isArray(parsed) && parsed.length) {
  groups = [{ label: 'adhoc', ids: parsed.join(','), focus: '' }]
}
if (!groups.length) {
  log('Không có nhóm bug. Truyền args=[{label,ids,focus}] hoặc ["16","17"].')
  return { phase: 'reconcile-bugs', error: 'no bugs', bugs: [] }
}

// GUARD cỡ-mẻ: tối đa 3 nhóm/lần. Phần dư trả về `deferred` → chạy lại.
const MAX_GROUPS_PER_RUN = 3
const allGroups = groups
groups = allGroups.slice(0, MAX_GROUPS_PER_RUN)
const deferred = allGroups.slice(MAX_GROUPS_PER_RUN)
if (deferred.length) log(`⚠️ Mẻ này chạy ${groups.length}/${allGroups.length} nhóm. CÒN ${deferred.length} → chạy lại với phần deferred.`)

phase('Reconcile')
const perGroup = await parallel(groups.map(g => () =>
  agent(
    `${READ_INSTR}\n\nĐối chiếu trạng thái THỰC TẾ với code của các bug: ${g.ids}.` +
    (g.focus ? `\nVùng focus: ${g.focus}` : '') +
    `\nVới MỖI id: đọc Bugs/BUG-{id}*.md để biết claim, đọc code, quyết actual_status: ` +
    `fixed (code chứng minh đã giải quyết) / open (còn nguyên) / partially-fixed / changed-context / not-a-bug / cannot-determine. ` +
    `Trích file:line làm bằng chứng cho từng verdict.`,
    { label: `status:${g.label}`, phase: 'Reconcile', schema: BUG_STATUS_SCHEMA })
))

const bugs = perGroup.filter(Boolean).flatMap(r => r.bugs || [])
return { phase: 'reconcile-bugs', groups: groups.map(g => g.label), bugs, deferred }
