#!/usr/bin/env python3
"""Sổ token audit — học chi phí thật + cộng dồn qua nhiều turn để calibrate budget.

Bối cảnh: code KHÔNG đọc được quota Team thật. Tín hiệu token duy nhất = budget.spent()
(output token của 1 turn, do coordinator trả về). Ledger này:
  • lưu spent từng turn  → học CHI PHÍ THẬT của audit;
  • cộng dồn vào 'currentCycle.spent' → biết đã dùng bao nhiêu cho chu trình đang chạy;
  • 'status' in %used / remaining + khuyến nghị (kết hợp '% quota còn lại' bạn cấp từ /usage).

3 lệnh con:
  start   — mở 1 chu trình mới (đặt cycle budget, reset cộng dồn)
  append  — ghi 1 turn vừa chạy (spent...) + cộng dồn vào chu trình
  status  — in trạng thái + khuyến nghị; kèm --remaining-pct để tính theo quota còn lại

Ví dụ:
  python3 Reviews_Project/audit/ledger.py start  --id 2026-06-29 --budget 300000
  python3 Reviews_Project/audit/ledger.py status --remaining-pct 40
  python3 Reviews_Project/audit/ledger.py append --label "find P1+P6+P4" --total 300000 \
          --spent 182500 --est 16000 --agents 14 --phases "P1,P6,P4" --more
"""
import argparse, json, math, os

LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "token-ledger.json")
F = "{:,}".format


def load():
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as f:
            return json.load(f)
    return {"runs": [], "recommendedTotalBudget": 300000, "maxFullRunSpent": None,
            "currentCycle": {"id": None, "budget": None, "spent": 0, "turns": 0}}


def save(data):
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def recompute_recommend(data):
    """maxFullRunSpent = spent lớn nhất của turn HOÀN TẤT TỰ NHIÊN; đề xuất per-turn = ×1.25."""
    full = [r for r in data.get("runs", []) if not r.get("stopped_by_budget") and not r.get("more_work")]
    mx = max((r["spent"] for r in full), default=None)
    data["maxFullRunSpent"] = mx
    if mx:
        data["recommendedTotalBudget"] = max(150000, int(math.ceil(mx * 1.25 / 25000) * 25000))
    return data


def cmd_start(a, data):
    data["currentCycle"] = {"id": a.id, "budget": a.budget, "spent": 0, "turns": 0}
    data["updated"] = a.id
    save(data)
    print(f"✓ mở chu trình '{a.id}' · cycleBudget = {F(a.budget) if a.budget else '(chưa set)'} · cộng dồn reset = 0")


def cmd_append(a, data):
    rec = {
        "date": a.date, "label": a.label, "total_budget": a.total, "spent": a.spent,
        "pct_total": round(a.spent / a.total * 100) if a.total else None,
        "est_per_agent": a.est, "agents": a.agents,
        "phases": [s for s in a.phases.split(",") if s],
        "stopped_by_budget": a.stopped, "more_work": a.more,
        "quota_pct_delta": a.quota_delta, "note": a.note,
    }
    data.setdefault("runs", []).append(rec)
    cyc = data.setdefault("currentCycle", {"id": a.date, "budget": None, "spent": 0, "turns": 0, "quota_pct": 0})
    cyc["spent"] = cyc.get("spent", 0) + a.spent
    cyc["turns"] = cyc.get("turns", 0) + 1
    cyc["quota_pct"] = round(cyc.get("quota_pct", 0) + (a.quota_delta or 0), 1)
    data["updated"] = a.date
    recompute_recommend(data)
    save(data)
    print(f"✓ turn: {a.label} · spent={F(a.spent)}/{F(a.total)} ({rec['pct_total']}%)"
          + (" [stopped-by-budget]" if a.stopped else "") + (" [more-work]" if a.more else ""))
    print(f"  cộng dồn chu trình '{cyc.get('id')}': {F(cyc['spent'])}" + (f"/{F(cyc['budget'])}" if cyc.get("budget") else "") + f" ({cyc['turns']} turn)")
    print(f"  maxFullRunSpent={data['maxFullRunSpent']} → per-turn đề xuất={F(data['recommendedTotalBudget'])}")


def cmd_status(a, data):
    cyc = data.get("currentCycle") or {"id": None, "budget": None, "spent": 0, "turns": 0}
    rec = data.get("recommendedTotalBudget", 300000)
    mx = data.get("maxFullRunSpent")
    print("=== AUDIT TOKEN STATUS ===")
    print(f"Per-turn budget đề xuất (learned): {F(rec)}")
    print(f"Chi phí 1 chu trình đầy (maxFullRunSpent): {F(mx) if mx else 'chưa có dữ liệu (lần đầu)'}")
    print(f"--- Chu trình hiện tại: {cyc.get('id') or '(chưa mở)'} ---")
    print(f"  cycleBudget: {F(cyc['budget']) if cyc.get('budget') else '(chưa set)'}")
    print(f"  đã dùng (cộng dồn): {F(cyc.get('spent', 0))} output token · {cyc.get('turns', 0)} turn")
    if cyc.get("quota_pct"):
        print(f"  quota /usage tiêu (cộng dồn): {cyc['quota_pct']}%  ← GROUND TRUTH (theo cái này, không theo output)")
    if cyc.get("budget"):
        used = cyc.get("spent", 0)
        pct = round(used / cyc["budget"] * 100) if cyc["budget"] else 0
        remain = max(0, cyc["budget"] - used)
        print(f"  %used: {pct}%  ·  remaining: {F(remain)}")
        nxt = min(remain, rec)
        print(f"  → totalBudget cho turn kế: {F(nxt)} (min của remaining & per-turn cap)")
        if remain <= 0:
            print("  ⛔ Hết cycleBudget → DỪNG chu trình.")
    # Khuyến nghị theo quota Team còn lại (bạn cấp từ /usage)
    if a.remaining_pct is not None:
        p = a.remaining_pct
        if p >= 50:
            advice = "THOẢI MÁI — chạy full chu trình (P1→P5), per-turn dùng mức đề xuất."
        elif p >= 20:
            advice = "THẬN TRỌNG — chạy nhưng chia nhỏ (mode=find trước, verify sau), theo dõi sát."
        else:
            advice = "HOÃN / chỉ slice nhỏ (vd chỉ P1 verify-fixes) — quota sắp cạn."
        print(f"--- Quota Team còn ~{p}% (bạn cấp) ---")
        print(f"  → Khuyến nghị: {advice}")


def main():
    p = argparse.ArgumentParser(description="Sổ token audit")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="mở chu trình mới")
    s.add_argument("--id", required=True)
    s.add_argument("--budget", type=int, default=None, help="cycleBudget (token) — tùy chọn")

    ap = sub.add_parser("append", help="ghi 1 turn")
    ap.add_argument("--label", required=True)
    ap.add_argument("--date", default="2026-06-29")
    ap.add_argument("--total", type=int, required=True)
    ap.add_argument("--spent", type=int, required=True)
    ap.add_argument("--est", type=int, default=0)
    ap.add_argument("--agents", type=int, default=0)
    ap.add_argument("--phases", default="")
    ap.add_argument("--stopped", action="store_true")
    ap.add_argument("--more", action="store_true")
    ap.add_argument("--quota-delta", type=float, default=None, help="%% quota /usage tiêu turn này (GROUND TRUTH — quan trọng hơn spent)")
    ap.add_argument("--note", default="")

    st = sub.add_parser("status", help="in trạng thái + khuyến nghị")
    st.add_argument("--remaining-pct", type=int, default=None, help="% quota Team còn lại (từ /usage)")

    a = p.parse_args()
    data = load()
    {"start": cmd_start, "append": cmd_append, "status": cmd_status}[a.cmd](a, data)


if __name__ == "__main__":
    main()
