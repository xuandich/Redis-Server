export const meta = {
  name: 'audit-phase0-coordinator',
  description: 'Điều phối re-audit P1→P5(+P6): đọc budget.spent(), tính token còn lại, co giãn wave, dừng cứng ở 95% token + return graceful kèm nextArgs',
  phases: [
    { title: 'P1 verify-fixes', detail: 'verify fix gần đây' },
    { title: 'P6 worker-correctness', detail: 'kiểm hành vi cào worker đổi' },
    { title: 'P4 audit-find', detail: 'tìm bug mới theo dimension' },
    { title: 'P5 audit-verify', detail: 'adversarial verify findings' },
  ],
}

// ════════════════════════════════════════════════════════════════════════
//  COORDINATOR — chạy LOGIC y hệt 6 pha gốc (cùng prompt/schema) nhưng do
//  coordinator điều phối theo TOKEN, không theo số-agent cố định.
//
//  Cơ chế kiểm soát token (đòi hỏi của user):
//   • TOTAL  = budget.total (nếu phiên có "+Nk") ?? args.totalBudget ?? mặc định
//   • hardCeiling  = TOTAL * stopFrac          (mặc định 0.95 — TRẦN CỨNG)
//   • agentCeiling = TOTAL * (stopFrac - synthReserve)  (mặc định 0.90 — agent dừng ở đây,
//                    chừa 5% cho main-loop tổng hợp review + checkpoint → tổng phiên ≤ 95%)
//   • estPerAgent  = ước lượng token/agent, cập nhật EWMA sau mỗi wave (động).
//   • Mỗi wave: fitN = floor(headroom / estPerAgent) → số agent vừa-túi-tiền.
//     headroom < estPerAgent  ⟹ DỪNG, trả phần dư qua nextArgs (resume lượt sau).
//
//  An toàn dữ liệu: coordinator KHÔNG ghi file (workflow không có FS). Nó trả
//  toàn bộ kết quả + nextArgs cho MAIN LOOP; main loop ghi results/ + STATE.md.
//  Dừng ở 90% (không phải 100%) ⟹ luôn return graceful ⟹ không mất finding.
// ════════════════════════════════════════════════════════════════════════

const A = (typeof args === 'string') ? safeParse(args) : (args || {})
function safeParse(s) { try { return JSON.parse(s) } catch (e) { return {} } }

const TOTAL        = budget.total || A.totalBudget || 300000
const stopFrac     = A.stopFrac ?? 0.95
const synthReserve = A.synthReserveFrac ?? 0.05
const hardCeiling  = Math.floor(TOTAL * stopFrac)
const agentCeiling = Math.floor(TOTAL * (stopFrac - synthReserve))
const CONC         = A.concurrency || 6
const MODE         = A.mode || 'auto'   // 'auto' = P1/P6/P4 rồi P5 | 'find' = chỉ P1/P6/P4 (an toàn: ghi findings ra đĩa trước) | 'verify' = chỉ P5
let estPerAgent    = (A.resume && A.resume.estPerAgent) || 18000

const k = n => Math.round(n / 1000) + 'k'
log(`COORDINATOR [mode=${MODE}] · TOTAL=${k(TOTAL)} (${budget.total ? 'budget.total' : (A.totalBudget ? 'args' : 'default')}) · agentCeiling=${k(agentCeiling)} (90%) · hardCeiling=${k(hardCeiling)} (95%) · est/agent=${k(estPerAgent)}`)

// ── Context dùng chung (copy từ các pha gốc) ──────────────────────────────
const CONTEXT = 'Reviews_Project/audit/00-context.md'
const READ = `Bạn đang audit hệ Redis+RQ crawler (CWD = repo root). ĐỌC TRƯỚC: ${CONTEXT} (file map, danh sách bug + trạng thái, fix gần đây, quy ước). Dùng Read/Grep/Bash, đường dẫn tương đối từ repo root. Đọc CODE THẬT — KHÔNG tin line number doc cũ, tự xác minh bằng Grep. Trích file:line.`

const S_FIX = { type: 'object', additionalProperties: false,
  required: ['bug_id','fix_present','fix_correct','regression_risk','issues','verdict'],
  properties: {
    bug_id: { type: 'string' }, fix_present: { type: 'boolean' },
    fix_correct: { type: 'boolean' },
    regression_risk: { type: 'string', enum: ['none','low','medium','high'] },
    issues: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['severity','description','file_line'],
      properties: { severity: { type: 'string', enum: ['critical','high','medium','low','nit'] },
        description: { type: 'string' }, file_line: { type: 'string' } } } },
    verdict: { type: 'string' } } }

const S_FIND = { type: 'object', additionalProperties: false,
  required: ['dimension','findings'],
  properties: { dimension: { type: 'string' },
    findings: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['title','severity','description','file_line','why_real','maybe_duplicate_of'],
      properties: { title: { type: 'string' },
        severity: { type: 'string', enum: ['critical','high','medium','low'] },
        description: { type: 'string' }, file_line: { type: 'string' },
        why_real: { type: 'string' }, maybe_duplicate_of: { type: 'string' } } } } } }

const S_WORKER = { type: 'object', additionalProperties: false,
  required: ['domain','findings'],
  properties: { domain: { type: 'string' },
    findings: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['concern_type','location','description','impact','needs_runtime','severity'],
      properties: { concern_type: { type: 'string', enum: ['selector-fragility','navigation-logic','parse-correctness','missing-validation','error-handling','other'] },
        location: { type: 'string' }, description: { type: 'string' }, impact: { type: 'string' },
        needs_runtime: { type: 'boolean' }, severity: { type: 'string', enum: ['high','medium','low'] } } } } } }

const S_VERDICT = { type: 'object', additionalProperties: false,
  required: ['title','is_real','is_new','severity','reason'],
  properties: { title: { type: 'string' }, is_real: { type: 'boolean' }, is_new: { type: 'boolean' },
    severity: { type: 'string', enum: ['critical','high','medium','low','refuted'] }, reason: { type: 'string' } } }

const DEFAULT_DIMS = [
  { key: 'false-success', prompt: 'Phân loại result manomano/orchestra (Playwright mới) + fnac/newark: gate success theo NỘI DUNG cào (title/price/html thật) hay chỉ http_code/có-html? 3xx? 200-with-block/captcha? main.py read-back đè failed?' },
  { key: 'worker-resilience', prompt: 'Vòng đời worker thread: backoff slot-wait, restart loop, RQ work() return-không-raise, register_birth/death, heartbeat TTL, stale rq:worker:*, graceful stop, death-penalty.' },
  { key: 'dashboard-integrity', prompt: 'Dashboard/app.py: submit validation/routing (_extract_domain_from_url, ret_key vs URL), clear/stop (rq:queue prefix), pagination, SCAN dedup, decode_responses bytes-key.' },
  { key: 'retry-lifecycle', prompt: 'retry_count end-to-end: double-increment, reset window, job_id collision khi re-enqueue, non-atomic GET+SETEX orchestrator↔worker, dashboard đọc/ghi retry_count. Job retry vô hạn hoặc drop?' },
  { key: 'resource-leaks', prompt: 'Rò container/slot/browser: orphan container khi crash (remove/labels), slot leak (acquire ngoài try/finally), playwright/chrome leak (worker mới), image auto-load no lock.' },
]

// ── Plan: hàng đợi unit theo thứ tự pha (mỗi unit = 1 agent task) ──────────
const R = A.resume || {}
function units(key, def) { return (R.pending && R.pending[key]) ? R.pending[key] : def }

const qP1 = units('P1', (A.fixes || []).map(f => (typeof f === 'string' ? { id: f } : f)))
const qP6 = units('P6', (A.workers || []).map(d => (typeof d === 'string' ? { domain: d } : d)))
const qP4 = units('P4', (Array.isArray(A.dimensions) && A.dimensions.length) ? A.dimensions
                        : (A.dimensions === 'none' ? [] : DEFAULT_DIMS))
let collected = R.collectedFindings || A.findings || []   // findings chờ P5 verify (từ P4 + P6 static; mode=verify nhận qua A.findings)

// ── runWave: chạy units theo wave co giãn theo budget ─────────────────────
async function runWave(list, makeTask, label) {
  const out = []
  let i = 0
  while (i < list.length) {
    const headroom = agentCeiling - budget.spent()
    if (headroom < estPerAgent) {
      log(`⛔ [${label}] DỪNG: headroom ${k(headroom)} < est/agent ${k(estPerAgent)}. Còn ${list.length - i} unit → nextArgs.`)
      break
    }
    const fitN  = Math.max(1, Math.floor(headroom / estPerAgent))
    const waveN = Math.min(fitN, CONC, list.length - i)
    const slice = list.slice(i, i + waveN)
    const before = budget.spent()
    log(`[${label}] wave ${slice.length} (fit ${fitN}) · spent ${k(before)}/${k(agentCeiling)} · est/agent ${k(estPerAgent)}`)
    const res = await parallel(slice.map(u => () => makeTask(u)))
    const delta = budget.spent() - before
    estPerAgent = Math.max(3000, Math.round(0.4 * estPerAgent + 0.6 * (delta / Math.max(1, slice.length))))
    res.forEach((r, j) => out.push({ unit: slice[j], result: r }))
    i += waveN
  }
  return { done: out, deferred: list.slice(i) }
}

// ── Task builders (logic = pha gốc) ───────────────────────────────────────
const taskP1 = u => agent(`${READ}\n\nVerify ${u.id} đã FIX ĐÚNG + KHÔNG regression.${u.focus ? '\nGỢI Ý: ' + u.focus : ''}\nBước: (1) đọc Bugs/${u.id}*.md (claim+fix dự kiến). (2) đọc code trích (tự xác minh line). (3) fix có hiện diện + thực sự giải quyết? trace mọi nhánh + exception + tương tác để tìm regression. (4) đa file thì kiểm hết. Thử phá.`,
  { label: `P1:${u.id}`, phase: 'P1 verify-fixes', schema: S_FIX })

const taskP6 = u => agent(`${READ}\n\nDOMAIN ${u.domain}: kiểm TÍNH ĐÚNG HÀNH VI CÀO (không phải bug queue/slot). Đọc workers/${u.domain}/sourceCode/extractor.py + main.py + run.py + utils.py (+config.py/models.py nếu có). Soi: (1) NAVIGATION/"tìm thấy sản phẩm" — điều kiện tới đúng trang chắc không (substring URL lỏng?). (2) SELECTOR/PARSE mong manh, im lặng trả rỗng/sai khi DOM đổi? field có validate? (3) ERROR-HANDLING nuốt lỗi thành rỗng/success giả? (4) success phản ánh "cào ĐÚNG dữ liệu" hay chỉ "có html/http ok"? needs_runtime=true nếu chỉ chạy HTML thật mới chốt. file:line.`,
  { label: `P6:${u.domain}`, phase: 'P6 worker-correctness', schema: S_WORKER })

const taskP4 = u => agent(`${READ}\nDEDUP: \`ls Bugs/\`; nếu trùng claim/file/cơ chế BUG-XX → maybe_duplicate_of=BUG-XX, else "none".\n\nDIMENSION ${u.key}. ${u.prompt}\nTìm bug cụ thể file:line. Ưu tiên bug MỚI do fix gần đây / code mới (manomano+orchestra Playwright) sinh ra. Không suy đoán — đọc code thật.`,
  { label: `P4:${u.key}`, phase: 'P4 audit-find', schema: S_FIND })

const taskP5 = u => { const f = u.finding
  return agent(`${READ}\nDEDUP: \`ls Bugs/\` + đọc Bugs/BUG-XX*.md nghi trùng.\n\nADVERSARIAL VERIFY (dimension ${f.dimension || f.domain || '?'}). CỐ HẾT SỨC BÁC BỎ bằng đọc code thật. is_real=true CHỈ khi bug THẬT tồn tại trong code hiện tại + hậu quả thật. is_new=false nếu trùng BUG-XX (finder đoán ${f.maybe_duplicate_of || 'none'} — tự kiểm).\n\nTITLE: ${f.title || f.description}\nSEVERITY(claim): ${f.severity}\nWHERE: ${f.file_line || f.location}\nDESC: ${f.description}\nWHY(claim): ${f.why_real || f.impact || ''}`,
    { label: `P5:${String(f.file_line || f.location || f.title).slice(0, 26)}`, phase: 'P5 audit-verify', schema: S_VERDICT })
    .then(v => ({ finding: f, verdict: v }))
}

// ── Chạy theo thứ tự pha; dừng ngay khi 1 pha bị defer (hết budget) ────────
const result = { P1: [], P6: [], P4: [], P5: [], needsRuntime: [] }
const pending = { P1: [], P6: [], P4: [] }
let stopped = false

if (MODE !== 'verify' && !stopped && qP1.length) {
  phase('P1 verify-fixes')
  const w = await runWave(qP1, taskP1, 'P1')
  result.P1 = w.done.map(x => ({ ...x.result }))
  pending.P1 = w.deferred
  if (w.deferred.length) stopped = true
}

if (MODE !== 'verify' && !stopped && qP6.length) {
  phase('P6 worker-correctness')
  const w = await runWave(qP6, taskP6, 'P6')
  for (const x of w.done) {
    const fs = (x.result && x.result.findings) || []
    result.needsRuntime.push(...fs.filter(f => f.needs_runtime).map(f => ({ ...f, domain: x.unit.domain })))
    collected.push(...fs.filter(f => !f.needs_runtime).map(f => ({ ...f, domain: x.unit.domain, source: 'P6' })))
  }
  pending.P6 = w.deferred
  if (w.deferred.length) stopped = true
}

if (MODE !== 'verify' && !stopped && qP4.length) {
  phase('P4 audit-find')
  const w = await runWave(qP4, taskP4, 'P4')
  for (const x of w.done) {
    const r = x.result
    if (r && r.findings) collected.push(...r.findings.map(f => ({ ...f, dimension: r.dimension || x.unit.key, source: 'P4' })))
  }
  pending.P4 = w.deferred
  if (w.deferred.length) stopped = true
}

// P5: chỉ verify khi P1/P6/P4 đã cạn hàng đợi (không bỏ sót find).
const findsDone = !pending.P1.length && !pending.P6.length && !pending.P4.length
let unverified = collected
if (MODE !== 'find' && !stopped && findsDone && collected.length) {
  phase('P5 audit-verify')
  const vunits = collected.map(f => ({ finding: f }))
  const w = await runWave(vunits, taskP5, 'P5')
  result.P5 = w.done.map(x => x.result).filter(Boolean)
  unverified = w.deferred.map(x => x.finding)   // chưa verify kịp → findings-pending.json
  if (w.deferred.length) stopped = true
}

// ── Tổng hợp + nextArgs cho lượt sau (null nếu xong) ──────────────────────
const spent = budget.spent()
const moreWork = stopped || pending.P1.length || pending.P6.length || pending.P4.length || unverified.length
const confirmedNew = result.P5
  .filter(v => v.verdict && v.verdict.is_real && v.verdict.is_new && v.verdict.severity !== 'refuted')
  .map(v => ({ ...v.finding, verdict: v.verdict }))
const rejected = result.P5
  .filter(v => !(v.verdict && v.verdict.is_real && v.verdict.is_new && v.verdict.severity !== 'refuted'))
  .map(v => ({ title: v.finding.title || v.finding.description, file_line: v.finding.file_line || v.finding.location, verdict: v.verdict }))

const nextArgs = !moreWork ? null : {
  totalBudget: A.totalBudget, stopFrac, synthReserveFrac: synthReserve, concurrency: CONC,
  fixes: A.fixes, workers: A.workers, dimensions: A.dimensions,
  resume: { estPerAgent, pending, collectedFindings: unverified },
}

log(`✅ COORDINATOR xong lượt này · spent ${k(spent)}/${k(hardCeiling)} (${Math.round(spent / TOTAL * 100)}% TOTAL) · ${moreWork ? 'CÒN việc → nextArgs' : 'HẾT việc'}`)

return {
  spent, total: TOTAL, hardCeiling, agentCeiling, pctTotal: Math.round(spent / TOTAL * 100),
  estPerAgent, stoppedByBudget: stopped, moreWork,
  P1: result.P1,
  P6: { staticConfirmable: collected.filter(f => f.source === 'P6'), needsRuntime: result.needsRuntime },
  P4_findingsCollected: collected.length,
  P5: { total: result.P5.length, confirmedNew, rejected },
  unverifiedFindings: unverified,   // → main loop ghi results/findings-pending.json
  nextArgs,                          // → main loop re-invoke nếu khác null
}
