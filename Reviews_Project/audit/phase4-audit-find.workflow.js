export const meta = {
  name: 'audit-phase4-audit-find',
  description: 'Pha 4 audit: fan-out tìm bug MỚI theo dimension (CHỈ tìm, chưa verify)',
  phases: [{ title: 'Audit Find', detail: 'mỗi dimension 1 agent' }],
}

// args: [{key, prompt}]  hoặc bỏ trống = 8 dimension mặc định. Chunk: truyền subset để chạy mẻ nhỏ.
const REPO = 'thư mục repo hiện tại (CWD của bạn — repo root)'
const CONTEXT = 'Reviews_Project/audit/00-context.md'
const READ_INSTR = `Bạn đang audit hệ Redis+RQ crawler tại ${REPO} (CWD = repo root).
ĐỌC TRƯỚC: ${CONTEXT} (file map, danh sách bug + trạng thái, fix gần đây, quy ước). Dùng Read/Grep/Bash, đường dẫn tương đối từ repo root.
Đọc CODE THẬT — KHÔNG tin line number doc cũ. Để DEDUP: chạy \`ls Bugs/\` xem bug đã biết; nếu finding trùng claim/file/cơ chế của BUG-XX thì đặt maybe_duplicate_of=BUG-XX. Trích file:line.`

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
          why_real: { type: 'string', description: 'trigger cụ thể + hậu quả' },
          maybe_duplicate_of: { type: 'string', description: 'BUG-XX nếu trùng bug đã biết, else "none"' },
        },
      },
    },
  },
}

const DEFAULT_DIMENSIONS = [
  { key: 'retry-lifecycle', prompt: 'retry_count end-to-end: double-increment, reset window, job_id collision khi re-enqueue, non-atomic GET+SETEX giữa orchestrator và worker, dashboard đọc/ghi retry_count. Tìm cách job retry vô hạn hoặc bị drop.' },
  { key: 'worker-resilience', prompt: 'Vòng đời worker thread: backoff slot-wait, restart loop, tương tác RQ work() (return-không-raise), register_birth/register_death, heartbeat TTL, stale rq:worker:* tích lũy, graceful stop, death-penalty.' },
  { key: 'false-success', prompt: 'Phân loại result 2 worker: fnac (sau BUG-49 — còn 3xx? 200-with-block/captcha?), newark (http_code=0, /dp/ substring, html-truthiness). main.py read-back có đè failed không. Dashboard classify đúng không.' },
  { key: 'dashboard-integrity', prompt: 'Dashboard/app.py: submit validation/routing (ret_key vs URL), clear/stop (rq:queue prefix), pagination (page<=0, int parse), SCAN dedup, stats, decode_responses. Tìm false-success report + corruption.' },
  { key: 'resource-leaks', prompt: 'Rò rỉ container/slot/browser: orphan container khi orchestrator/worker crash (remove=True, no labels), slot leak (acquire ngoài try/finally), newark browser/playwright leak, image auto-load no lock.' },
  { key: 'slot-accounting', prompt: 'Slot: Lua atomic, global+domain, release luôn ở finally, EXPIRE/TTL, multi-domain overcommit (Σ domain max > TOTAL), soft pre-check vs hard gate nhất quán.' },
  { key: 'config-deploy', prompt: 'config.py/.env/.env.example/docker-compose.yml/Dockerfile/start.sh/stop.sh/setup_systemd.sh: PROXY_HOST_DIR, dep không pin, build-context, rebuild-on-change, project name, healthcheck, secrets, config chết.' },
  { key: 'path-cwd-robustness', prompt: 'Fragility path/CWD sau move vào redis_server/: discover_worker_domains Path(__file__).parent, cache_file relative, volume mount, WORKDIR. Tìm chỗ vỡ khi chạy local vs container hoặc CWD khác.' },
]

let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch (e) { A = null } }
const allDims = (Array.isArray(A) && A.length) ? A
  : (A && Array.isArray(A.dimensions) && A.dimensions.length) ? A.dimensions
  : DEFAULT_DIMENSIONS

// GUARD cỡ-mẻ: tối đa 3 dimension/lần để không chạm session-limit. Phần dư trả về `deferred` → chạy lại.
const MAX_DIMS_PER_RUN = 3
const dims = allDims.slice(0, MAX_DIMS_PER_RUN)
const deferred = allDims.slice(MAX_DIMS_PER_RUN)
if (deferred.length) log(`⚠️ Mẻ này chạy ${dims.length}/${allDims.length} dimension. CÒN ${deferred.length} → chạy lại pha 4 với args = phần deferred (xem field "deferred" trong kết quả).`)

phase('Audit Find')
const perDim = await parallel(dims.map(d => () =>
  agent(`${READ_INSTR}\n\nDIMENSION: ${d.key}. ${d.prompt}\nTìm bug cụ thể với file:line. Ưu tiên bug MỚI do các fix gần đây sinh ra/lộ ra. Không suy đoán — đọc code thật.`,
    { label: `find:${d.key}`, phase: 'Audit Find', schema: FINDINGS_SCHEMA })
))

// Gộp phẳng + gắn dimension để pha 5 verify (main loop ghi ra results/findings-pending.json)
const findings = perDim.filter(Boolean).flatMap(r =>
  (r.findings || []).map(f => ({ ...f, dimension: r.dimension })))

return { phase: 'audit-find', dimensions: dims.map(d => d.key), count: findings.length, findings, deferred }
