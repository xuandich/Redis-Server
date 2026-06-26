export const meta = {
  name: 'audit-phase5-audit-verify',
  description: 'Pha 5 audit: adversarial verify (cố bác bỏ) + dedup từng finding — chạy 1 batch/lần, lặp tới cạn',
  phases: [{ title: 'Adversarial Verify', detail: 'mỗi finding 1 agent skeptic' }],
}

// args: mảng finding (1 BATCH ~10-12 cái) lấy từ results/findings-pending.json.
//   Mỗi finding: {title, severity, file_line, description, why_real, dimension, maybe_duplicate_of}
const REPO = '/home/xuandich/CODE/PO/Redis_Server'
const CONTEXT = 'Reviews_Project/audit/00-context.md'
const READ_INSTR = `Bạn đang audit hệ Redis+RQ crawler tại ${REPO} (CWD = repo root).
ĐỌC TRƯỚC: ${CONTEXT}. Dùng Read/Grep/Bash, đường dẫn tương đối từ repo root.
Để DEDUP: chạy \`ls Bugs/\` + đọc Bugs/BUG-XX*.md nghi trùng. Đọc CODE THẬT, tự xác minh line.`

const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['title', 'is_real', 'is_new', 'severity', 'reason'],
  properties: {
    title: { type: 'string' },
    is_real: { type: 'boolean', description: 'sau khi CỐ HẾT SỨC bác bỏ mà vẫn đứng' },
    is_new: { type: 'boolean', description: 'KHÔNG trùng bất kỳ BUG-XX đã có trong Bugs/' },
    severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'refuted'] },
    reason: { type: 'string', description: 'bằng chứng file:line cho real/new/severity' },
  },
}

let parsed = args
if (typeof parsed === 'string') { try { parsed = JSON.parse(parsed) } catch (e) { parsed = null } }
const batch = Array.isArray(parsed) ? parsed : (parsed && parsed.findings) || []
log(`args type=${typeof args}, batch=${batch.length}`)
if (!batch.length) {
  log('Batch rỗng. Truyền args=<mảng finding> (lấy ~12 cái từ results/findings-pending.json).')
  return { phase: 'audit-verify', error: 'empty batch', verdicts: [] }
}

phase('Adversarial Verify')
const verdicts = await parallel(batch.map((f, i) => () =>
  agent(
    `${READ_INSTR}\n\nADVERSARIAL VERIFY finding sau (dimension ${f.dimension || '?'}). CỐ HẾT SỨC BÁC BỎ bằng cách đọc code thật. ` +
    `Chỉ is_real=true nếu bug THẬT tồn tại trong code hiện tại VÀ có hậu quả thật. ` +
    `is_new=false nếu trùng BUG-XX đã có (finder đoán maybe_duplicate_of=${f.maybe_duplicate_of || 'none'} — tự kiểm).\n\n` +
    `TITLE: ${f.title}\nSEVERITY(claim): ${f.severity}\nWHERE: ${f.file_line}\nDESC: ${f.description}\nWHY REAL(claim): ${f.why_real}`,
    { label: `verify:${String(f.file_line || f.title).slice(0, 28)}`, phase: 'Adversarial Verify', schema: VERDICT_SCHEMA })
    .then(v => ({ finding: f, verdict: v }))
))

const ok = verdicts.filter(Boolean)
const confirmedNew = ok.filter(v => v.verdict && v.verdict.is_real && v.verdict.is_new && v.verdict.severity !== 'refuted')
return {
  phase: 'audit-verify',
  total: ok.length,
  confirmedNew: confirmedNew.map(v => ({ ...v.finding, verdict: v.verdict })),
  rejected: ok.filter(v => !(v.verdict && v.verdict.is_real && v.verdict.is_new && v.verdict.severity !== 'refuted'))
    .map(v => ({ title: v.finding.title, file_line: v.finding.file_line, verdict: v.verdict })),
}
