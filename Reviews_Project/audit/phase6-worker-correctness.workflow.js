export const meta = {
  name: 'audit-phase6-worker-correctness',
  description: 'Pha 6 (CÓ ĐIỀU KIỆN): kiểm tính ĐÚNG hành vi cào của worker — CHỈ chạy khi code worker đổi',
  phases: [{ title: 'Worker Correctness', detail: 'mỗi domain 1 agent đọc extractor/parse/navigation' }],
}

// ⚠️ CHỈ chạy pha này khi workers/*/sourceCode | run.py | Dockerfile thay đổi.
//    Worker code ít đổi → bỏ qua trong re-audit thường lệ (pha 1-5).
//    Kiểm có đổi không:  git diff --name-only <commit-audit-worker-trước>.. -- workers/
//
// args: ["fnac","newark"]  hoặc  [{domain:"fnac"}]  hoặc  {domains:[...]} ;
//       bỏ args = mặc định fnac+newark.  {domains:[]} = no-op (validate parse).
const REPO = '/home/xuandich/CODE/PO/Redis_Server'
const CONTEXT = 'Reviews_Project/audit/00-context.md'
const READ_INSTR = `Bạn đang audit hệ Redis+RQ crawler tại ${REPO} (CWD = repo root).
ĐỌC TRƯỚC: ${CONTEXT}. Dùng Read/Grep/Bash, đường dẫn tương đối từ repo root. Trích file:line.`

const WORKER_FINDINGS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['domain', 'findings'],
  properties: {
    domain: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['concern_type', 'location', 'description', 'impact', 'needs_runtime', 'severity'],
        properties: {
          concern_type: { type: 'string', enum: ['selector-fragility', 'navigation-logic', 'parse-correctness', 'missing-validation', 'error-handling', 'other'] },
          location: { type: 'string', description: 'file:line' },
          description: { type: 'string' },
          impact: { type: 'string', description: 'dữ liệu cào sai/thiếu thế nào' },
          needs_runtime: { type: 'boolean', description: 'true nếu CHỈ chạy thật trên HTML thực mới khẳng định được (đọc code không đủ); false nếu đọc code đủ kết luận' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
    },
  },
}

let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch (e) { A = null } }
let domains
if (Array.isArray(A)) domains = A                       // ["fnac"] hoặc [{domain}] hoặc []
else if (A && Array.isArray(A.domains)) domains = A.domains  // {domains:[...]} — kể cả rỗng
else domains = ['fnac', 'newark']                       // bỏ args → mặc định
domains = domains.map(d => (typeof d === 'string' ? { domain: d } : d))

if (!domains.length) {
  log('Không có domain (truyền ["fnac","newark"] / {domains:[...]}, hoặc bỏ args để dùng mặc định).')
  return { phase: 'worker-correctness', findings: [] }
}

phase('Worker Correctness')
const perDomain = await parallel(domains.map(d => () =>
  agent(
    `${READ_INSTR}\n\nDOMAIN: ${d.domain}. Kiểm TÍNH ĐÚNG HÀNH VI CÀO (không phải bug tích hợp queue/slot — cái đó pha khác lo).\n` +
    `Đọc workers/${d.domain}/sourceCode/extractor.py + main.py + run.py + utils.py (+ display_manager.py / config.py nếu có).\n` +
    `Soi: (1) NAVIGATION / "tìm thấy sản phẩm" — điều kiện xác định đã tới đúng trang sản phẩm có chắc không (vd substring URL quá lỏng như '/dp/')? ` +
    `(2) SELECTOR/PARSE — selector có mong manh, im lặng trả rỗng/sai khi DOM đổi nhẹ? field trích ra có được validate? ` +
    `(3) ERROR-HANDLING quanh trích xuất — có nuốt lỗi thành rỗng/success giả? ` +
    `(4) Phân loại success có phản ánh "đã cào ĐÚNG dữ liệu" không, hay chỉ "có HTML/http_code ok"?\n` +
    `Mỗi concern: needs_runtime=true nếu chỉ chạy thật trên HTML thực mới khẳng định (vd "selector này sai"), false nếu đọc code đủ kết luận (vd "thao tác trên page có thể None"). Trích file:line.`,
    { label: `worker:${d.domain}`, phase: 'Worker Correctness', schema: WORKER_FINDINGS_SCHEMA })
))

const findings = perDomain.filter(Boolean).flatMap(r =>
  (r.findings || []).map(f => ({ ...f, domain: r.domain })))

return {
  phase: 'worker-correctness',
  domains: domains.map(d => d.domain),
  count: findings.length,
  staticConfirmable: findings.filter(f => !f.needs_runtime),   // có thể đẩy qua pha 5 verify
  needsRuntime: findings.filter(f => f.needs_runtime),         // phải chạy worker trên HTML thật mới chốt
}
