export const meta = {
  name: 'audit-2026-07-01-comprehensive',
  description: 'Audit toàn diện: amazon_fr worker MỚI + Dashboard routing + regression sweep (find→adversarial verify→escalate→completeness)',
  phases: [
    { title: 'Find', detail: '9 dimension — trọng tâm amazon_fr worker mới' },
    { title: 'Verify', detail: 'adversarial refute + dedup vs Bugs/ từng finding' },
    { title: 'Escalate', detail: 'refuter độc lập thứ 2 cho high/critical' },
    { title: 'Completeness', detail: 'critic tìm vùng/failure-mode chưa cover' },
  ],
}

// ───────── Bối cảnh dùng chung ─────────
const CONTEXT = 'Reviews_Project/audit/00-context.md'
const BASE = 'ef7e652' // commit nền audit trước (06-29). Code MỚI kể từ đây CHƯA audit: amazon_fr worker (~822 dòng), Dashboard routing (~55), orchestrator (+1).
const READ_INSTR =
  `Bạn đang audit hệ Redis+RQ crawler phân tán (Docker Compose). CWD = repo root, đường dẫn tương đối từ đó.\n` +
  `ĐỌC TRƯỚC: ${CONTEXT} (file map, invariant, danh sách bug + trạng thái, fix gần đây, quy ước). Dùng Read/Grep/Bash.\n` +
  `Đọc CODE THẬT — KHÔNG tin line number trong doc/bug cũ; tự xác minh line hiện tại bằng Grep. Trích mọi nhận định dạng file:line.\n` +
  `TRỌNG TÂM: worker **workers/amazon_fr/** là MỚI, CHƯA TỪNG audit (thêm ở commit ceee225, sửa extractor ở 1cc22f3 SAU audit 06-29). ` +
  `Amazon chống bot rất mạnh → nghi ngờ false-success, leak resource, http-status không check, render-guard chết, timeout, proxy rotation. ` +
  `So sánh amazon_fr với fnac/newark/manomano/orchestra để phát hiện LỆCH CHUẨN.\n` +
  `DEDUP: chạy \`ls Bugs/\` để biết bug đã biết (filename có (FIXED) = đã fix). Nếu finding trùng claim/file/cơ chế BUG-XX thì đặt maybe_duplicate_of=BUG-XX; ngược lại "none".`

const FINDINGS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['dimension', 'findings'],
  properties: {
    dimension: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['title', 'severity', 'description', 'file_line', 'why_real', 'maybe_duplicate_of'],
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          description: { type: 'string' },
          file_line: { type: 'string' },
          why_real: { type: 'string', description: 'trigger cụ thể + hậu quả thực' },
          maybe_duplicate_of: { type: 'string', description: 'BUG-XX nếu trùng bug đã biết, else "none"' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['title', 'is_real', 'is_new', 'severity', 'reason'],
  properties: {
    title: { type: 'string' },
    is_real: { type: 'boolean', description: 'sau khi CỐ HẾT SỨC bác bỏ mà vẫn đứng vững' },
    is_new: { type: 'boolean', description: 'KHÔNG trùng bất kỳ BUG-XX đã có trong Bugs/ (kể cả (FIXED))' },
    severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'refuted'] },
    reason: { type: 'string', description: 'bằng chứng file:line cho real/new/severity' },
  },
}

const GAPS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['gaps'],
  properties: {
    gaps: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['area', 'why_risky', 'suggested_probe'],
        properties: {
          area: { type: 'string' },
          why_risky: { type: 'string' },
          suggested_probe: { type: 'string' },
        },
      },
    },
  },
}

// ───────── 9 dimension (amazon_fr chiếm 5) ─────────
const DIMENSIONS = [
  { key: 'amazon-false-success', prompt:
    'workers/amazon_fr — PHÂN LOẠI RESULT. Đọc extractor.py + main.py + models.py. Amazon trả 200 kèm trang chặn/captcha/robot-check/"Enter the characters"/dogs-of-amazon vẫn bị coi success? http_code có được kiểm (>=400, ==0, 3xx) trước khi gán status="success"? Có gate nội dung (ASIN/#productTitle/#dp / giá) không, hay chỉ dựa html-truthiness? So với fnac (BUG-49/64/65) và manomano/orchestra (BUG-69/70/89/90). Tìm mọi đường false-success.' },
  { key: 'amazon-resource-leaks', prompt:
    'workers/amazon_fr — RÒ RỈ RESOURCE. Playwright/Chrome context+page/browser có đóng trong finally kể cả khi navigate/goto raise? context tạo NGOÀI try/finally (BUG-98)? _check_proxy_country leak context+page (BUG-97)? orphan Chrome khi khởi tạo raise giữa chừng (BUG-78)? proxy ext/tmp dir leak (BUG-73)? page reuse sau khi đóng (BUG-58)? container orphan (remove/labels).' },
  { key: 'amazon-crawl-logic', prompt:
    'workers/amazon_fr/extractor.py — LOGIC CRAWL. Vòng retry & proxy rotation: proxy chọn random.choice mỗi attempt lặp lại proxy hỏng (BUG-87)? http status điều hướng có kiểm (response = goto(...); response.status) hay bỏ (BUG-84)? render-completeness guard dùng đúng exception class của wait_for_function, hay dead-code (BUG-82/88)? headers/cookies lấy đúng response chính (BUG-83/86)? job_timeout đủ cho N attempt (BUG-96)? heartbeat refresh trong job dài (BUG-91)? Chú ý diff 1cc22f3 sửa extractor — regression?' },
  { key: 'amazon-config-schema-deploy', prompt:
    'workers/amazon_fr — CONFIG/SCHEMA/DEPLOY. config.py + run.py + models.py + requirements.txt + Dockerfile. requirements deps pin chưa (BUG-54/76)? result schema đủ field chuẩn (url,html,headers,http_code,cookies,elapsed_ms,error,status) hay http_code hardcode 200 (BUG-71/53)? domain/timestamp backfill? run.py đọc đúng env (URL/RET_KEY/PROXY_TYPE/REDIS_*) & ghi result:{ret_key} đúng TTL? tar.gz worker-amazon_fr-latest.tar.gz nằm TRONG build context, thiếu .dockerignore (BUG-79)? MAX_CONCURRENT_AMAZON_FR có trong .env/.env.example (BUG-46/66/75)?' },
  { key: 'amazon-integration-orchestrator', prompt:
    'TÍCH HỢP amazon_fr với orchestrator/slot/discovery. redis_server/orchestrator.py discover_worker_domains có nhận amazon_fr đúng (auto-domain từ workers/)? spawn thread số lượng đúng? slot: Σ MAX_CONCURRENT mọi domain vs MAX_CONCURRENT_TOTAL=10 — overcommit? get_job_timeout(amazon_fr)/get_max_concurrent(amazon_fr) fallback ra sao? Image name / start.sh / docker-compose có biết amazon_fr (BUG-62 hardcoded names)? Kiểm diff orchestrator +1 dòng kể từ ' + BASE + '.' },
  { key: 'dashboard-routing', prompt:
    'Dashboard/app.py — ROUTING & SUBMIT (đổi ~55 dòng kể từ ' + BASE + '). submit-job định tuyến theo URL hay ret_key (BUG-51)? _extract_domain_from_url xử lý subdomain/port/amazon.fr đúng (BUG-81 — file đã rename (FIXED) nhưng STATE 06-29 nghi fix MISSING → KIỂM kỹ present+correct)? validate domain amazon_fr được hỗ trợ (BUG-16 unsupported-domain)? preserve retry_count khi submit (BUG-60)? decode_responses/bytes-key (BUG-29)? pagination/clear/stop regression do diff mới?' },
  { key: 'fix-regression-verify', prompt:
    'XÁC MINH FIX + REGRESSION. (a) BUG-81: đọc app.py _extract_domain_from_url — fix present & correct? (STATE 06-29: MISSING). (b) BUG-46 env-dead-amazon: giờ đã có worker amazon_fr → config amazon còn "dead" không, hay đã nối? (c) commit 1cc22f3 "improve amazon_fr" — sửa gì ở extractor/config, có sinh regression (đóng browser sớm, đổi điều kiện success, đổi timeout)? (d) diff Dashboard 55 dòng có phá fix BUG-60/48/43 cũ không? Báo cáo fix nào MISSING/INCORRECT như 1 finding.' },
  { key: 'retry-lifecycle-sweep', prompt:
    'RETRY LIFECYCLE (regression sweep do code mới). retry_count end-to-end với amazon_fr: double-increment, reset window, job_id collision khi re-enqueue, non-atomic GET+SETEX orchestrator↔worker, crash-recovery _retry_stale_jobs cap>=3 + give-up TTL 86400 làm bằng chứng "đã xong" gây drop job (họ BUG-67/94/95). URL "N/A" cho job re-enqueue (BUG-94). Có gì MỚI do amazon_fr/dashboard đổi không.' },
  { key: 'worker-resilience-sweep', prompt:
    'WORKER RESILIENCE (regression sweep). Vòng đời thread/RQ work() return-không-raise, register_birth/death, heartbeat TTL (SimpleWorker không refresh giữa job dài → BUG-91 áp dụng amazon_fr?), stale rq:worker:* tích lũy, pubsub thread leak (BUG-77), graceful stop, death-penalty/slot-leak. amazon_fr có kế thừa cùng ThreadSafeWorker không, hay bỏ sót gì.' },
]

// ───────── PHA 1+2: pipeline find → verify (mỗi dimension verify ngay khi find xong) ─────────
phase('Find')
const perDim = await pipeline(
  DIMENSIONS,
  // stage 1: FIND
  (d) => agent(
    `${READ_INSTR}\n\nDIMENSION: ${d.key}.\n${d.prompt}\n\nTìm bug cụ thể kèm file:line. Ưu tiên bug MỚI do code mới (amazon_fr / dashboard routing) sinh ra hoặc lộ ra. Không suy đoán — đọc code thật. Nếu không có bug thật, trả findings rỗng.`,
    { label: `find:${d.key}`, phase: 'Find', schema: FINDINGS_SCHEMA, effort: 'high' }
  ),
  // stage 2: VERIFY từng finding của dimension đó (adversarial)
  (found, d) => {
    const list = (found && found.findings) || []
    if (!list.length) return []
    return parallel(list.map((f) => () =>
      agent(
        `${READ_INSTR}\n\nADVERSARIAL VERIFY finding sau (dimension ${d.key}). CỐ HẾT SỨC BÁC BỎ bằng cách đọc code thật hiện tại. ` +
        `is_real=true CHỈ KHI bug thật tồn tại trong code hiện tại VÀ có hậu quả thật (không phải lý thuyết). ` +
        `is_new=false nếu trùng cơ chế/file của một BUG-XX đã có trong Bugs/ (finder đoán maybe_duplicate_of=${f.maybe_duplicate_of || 'none'} — TỰ KIỂM bằng cách đọc Bugs/BUG-XX*.md nghi ngờ). ` +
        `Nếu không chắc → nghiêng về refuted/is_real=false.\n\n` +
        `TITLE: ${f.title}\nSEVERITY(claim): ${f.severity}\nWHERE: ${f.file_line}\nDESC: ${f.description}\nWHY REAL(claim): ${f.why_real}`,
        { label: `verify:${String(f.file_line || f.title).slice(0, 26)}`, phase: 'Verify', schema: VERDICT_SCHEMA, effort: 'high' }
      ).then((v) => ({ ...f, dimension: d.key, verdict: v }))
    ))
  }
)

const all = perDim.filter(Boolean).flat().filter(Boolean)
const confirmed = all.filter((x) => x.verdict && x.verdict.is_real && x.verdict.is_new && x.verdict.severity !== 'refuted')
const rejected = all.filter((x) => !(x.verdict && x.verdict.is_real && x.verdict.is_new && x.verdict.severity !== 'refuted'))
log(`Find→Verify xong: ${all.length} finding, ${confirmed.length} confirmed-new sau vòng 1 (rejected/dup ${rejected.length}).`)

// ───────── PHA 3: ESCALATE — refuter độc lập thứ 2 cho high/critical confirmed ─────────
phase('Escalate')
const highSev = confirmed.filter((x) => x.verdict.severity === 'high' || x.verdict.severity === 'critical')
const escalated = await parallel(highSev.map((f) => () =>
  agent(
    `${READ_INSTR}\n\nSECOND-OPINION REFUTER (độc lập). Một verifier trước đã xác nhận finding ${f.verdict.severity.toUpperCase()} này là THẬT & MỚI. ` +
    `Nhiệm vụ của bạn: CỐ BÁC BỎ nó lần nữa từ góc khác — đọc code thật, tìm lý do nó KHÔNG xảy ra (guard ở nơi khác, layout container che, bounded bởi 1-job-1-container, đã có bug cũ trùng). ` +
    `Chỉ giữ is_real=true nếu vẫn không bác được.\n\n` +
    `TITLE: ${f.title}\nSEVERITY: ${f.verdict.severity}\nWHERE: ${f.file_line}\nDESC: ${f.description}\nLÝ DO verifier-1 tin là thật: ${f.verdict.reason}`,
    { label: `escalate:${String(f.file_line || f.title).slice(0, 24)}`, phase: 'Escalate', schema: VERDICT_SCHEMA, effort: 'high' }
  ).then((v) => ({ file_line: f.file_line, title: f.title, second: v }))
))
const escMap = {}
for (const e of escalated.filter(Boolean)) escMap[e.file_line + '|' + e.title] = e.second
const confirmedFinal = confirmed.map((f) => {
  const s = escMap[f.file_line + '|' + f.title]
  if (!s) return { ...f, escalate: null, survives: true }
  const survives = s.is_real && s.is_new && s.severity !== 'refuted'
  return { ...f, escalate: s, survives }
})

// ───────── PHA 4: COMPLETENESS CRITIC — vùng chưa cover ─────────
phase('Completeness')
const coveredList = confirmedFinal.filter((x) => x.survives).map((x) => `- [${x.verdict.severity}] ${x.title} (${x.file_line})`).join('\n') || '(chưa có)'
const critic = await agent(
  `${READ_INSTR}\n\nBẠN LÀ COMPLETENESS CRITIC. Đợt audit này nhắm code MỚI kể từ ${BASE}: worker amazon_fr + Dashboard routing. ` +
  `Xem \`git diff --stat ${BASE} HEAD -- workers/ Dashboard/ redis_server/\` và đọc code. ` +
  `Dưới đây là các bug ĐÃ xác nhận đợt này:\n${coveredList}\n\n` +
  `Hỏi: còn VÙNG CODE MỚI / FAILURE-MODE nào CHƯA được probe? (file amazon_fr chưa ai đọc kỹ, nhánh exception chưa xét, tương tác amazon_fr↔recovery/slot/dashboard chưa xét, claim chưa verify). ` +
  `Liệt kê gap cụ thể + cách probe. Nếu phủ đã đủ, trả gaps rỗng.`,
  { label: 'completeness-critic', phase: 'Completeness', schema: GAPS_SCHEMA, effort: 'high' }
)

return {
  base: BASE,
  dimensions: DIMENSIONS.map((d) => d.key),
  total_findings: all.length,
  confirmed_round1: confirmed.length,
  confirmedFinal: confirmedFinal.map((f) => ({
    title: f.title, dimension: f.dimension, file_line: f.file_line,
    severity_final: f.escalate ? f.escalate.severity : f.verdict.severity,
    survives_escalation: f.survives,
    description: f.description, why_real: f.why_real,
    verdict1_reason: f.verdict.reason,
    escalate_reason: f.escalate ? f.escalate.reason : null,
    maybe_duplicate_of: f.maybe_duplicate_of,
  })),
  rejected: rejected.map((x) => ({ title: x.title, file_line: x.file_line, dim: x.dimension, verdict: x.verdict })),
  gaps: (critic && critic.gaps) || [],
}
