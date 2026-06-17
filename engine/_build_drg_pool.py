"""
一次性脚本：从 adrg_rules.json 生成 ~50 个已验证用例池
自然语言由简单模板生成，不靠 LLM 瞎编
"""
import json, os, sys, random

DRG_DIR = r"C:\Users\32198\Desktop\work\1\软件工程智能体\drg-project\engine"
sys.path.insert(0, DRG_DIR)
from ruzu import group_full


def jl(p):
    with open(os.path.join(DRG_DIR, p), encoding="utf-8") as f:
        return json.load(f)


rules = jl("adrg_rules.json")
drg_table = jl("drg_table.json")
mcc_t = jl("mcc_table.json")
cc_t = jl("cc_table.json")
excl = jl("exclusion_table.json")
c2n = jl("code2name.json")

mcc_map = {}
for t, es in mcc_t.items():
    for e in es:
        mcc_map[e["code"]] = t
cc_map = {}
for t, es in cc_t.items():
    for e in es:
        cc_map[e["code"]] = t
excl_clean = {k: [e["code"] for e in v] for k, v in excl.items()}


def name(c):
    return c2n.get(c, c) if c else ""


def codes(items):
    if not isinstance(items, list):
        return []
    return [x["code"] for x in items if isinstance(x, dict) and "code" in x]


mdc_diag = {}
for key, entry in rules.items():
    if key.startswith("MDC") and "主诊表" in key:
        cs = codes(entry.get("包含以下主要诊断", []))
        if cs:
            mdc_diag[key[3]] = cs

by_prefix = {}
for c, e in rules.items():
    if not c.startswith("MDC"):
        by_prefix.setdefault(c[0], []).append(c)


def make_case(code, md, ods, mp, ops, age):
    """构造并验算一个用例"""
    md = md or ""
    mp = mp or ""
    if not md and not mp:
        return None
    try:
        r = group_full(md, ods, mp, ops, age, rules, drg_table, mcc_map, cc_map, excl_clean)
    except Exception:
        return None
    cat = {"A": "先期分组-MDCA", "P": "先期分组-MDCP", "Y": "先期分组-MDCY", "Z": "先期分组-MDCZ"}.get(
        code[0], f"常规MDC-MDC{code[0]}")

    md_name = name(md)
    mp_name = name(mp)

    # 简单自然语言模板（不靠 LLM）
    age_y = age // 365 if age >= 365 else f"{age}天"
    gender = "男"
    diag_part = f"因{md_name}入院" if md_name else ""
    proc_part = f"，行{mp_name}" if mp_name else ""
    others = "、".join(name(c) for c in ods[:2]) if ods else ""
    other_part = f"，合并{others}" if others else ""
    nl = f"{gender}，{age_y}岁，{diag_part}{other_part}{proc_part}。"

    return {
        "id": code,
        "purpose": f"测试{cat}-{code}：{entry.get('name','')}",
        "path": f"先期分组/MDC匹配 → {cat} → {code} → {r.get('DRG','')}",
        "input": {
            "gender": gender, "age_days": age,
            "main_diagnosis": {"code": md, "name": md_name},
            "other_diagnoses": [{"code": c, "name": name(c)} for c in ods],
            "main_procedure": {"code": mp, "name": mp_name},
            "other_procedures": [{"code": c, "name": name(c)} for c in ops],
        },
        "expected": {
            "mdc": r.get("MDC", ""), "adrg": r.get("ADRG"),
            "adrg_name": r.get("ADRG_NAME", ""), "drg": r.get("DRG"),
            "drg_name": r.get("DRG_NAME", ""), "complication": r.get("COMPLICATION", "NONE"),
        },
        "natural_language": nl,
    }


# ====== 构建用例池 ======
pool = []

# MDCA: AA1, AB1, AH2
for code in ["AA1", "AB1", "AH2"]:
    if code not in rules:
        continue
    entry = rules[code]
    fallback = {"AA1": "J96.900", "AB1": "K72.900", "AH2": "J12.800"}
    md = fallback.get(code, "Z00.000")
    if code == "AH2":
        ods, mp, ops = ["Z93.000"], "96.7201", []
    else:
        mp = codes(entry.get("包含以下主要手术或操作", []))
        mp = mp[0] if mp else ""
        ods, ops = [], []
    c = make_case(code, md, ods, mp, ops, 50 * 365)
    if c:
        pool.append(c)

# MDCP: 随机3个
if "P" in by_prefix:
    for code in random.sample(by_prefix["P"], min(3, len(by_prefix["P"]))):
        entry = rules[code]
        md = random.choice(["P07.000", "P05.000", "P22.000"])
        mp = codes(entry.get("包含以下主要手术或操作", []))
        mp = mp[0] if mp else ""
        c = make_case(code, md, [], mp, [], 3)
        if c:
            pool.append(c)

# 常规 MDC: 每个随机1~2个 ADRG
for p in "BCDEFGHIJKLMNQRSTUVWX":
    if p not in by_prefix:
        continue
    candidates = [c for c in by_prefix[p]
                  if codes(rules[c].get("包含以下主要手术或操作", []))
                  or "同时包含以下手术或操作" in rules[c]]
    if not candidates:
        candidates = by_prefix[p][:3]
    for code in random.sample(candidates, min(random.randint(1, 2), len(candidates))):
        entry = rules[code]
        # 从 ADRG 取诊断和手术
        md = ""
        for f in ["包含以下主要诊断", "主要诊断", "包含以下诊断"]:
            cs = codes(entry.get(f, []))
            if cs:
                md = random.choice(cs)
                break
        ods = codes(entry.get("其他诊断", []))[:2]
        if not md and p in mdc_diag:
            md = random.choice(mdc_diag[p])
        mp = ""
        for f in ["包含以下主要手术或操作", "主要手术或操作", "主要手术或操作1"]:
            cs = codes(entry.get(f, []))
            if cs:
                mp = random.choice(cs)
                break
        if not mp:
            gs = entry.get("同时包含以下手术或操作", [])
            if isinstance(gs, list):
                for g in gs:
                    if isinstance(g, dict):
                        cs = codes(g.get("and_group", []))
                        if cs:
                            mp = random.choice(cs)
                            break
        ops = codes(entry.get("手术或操作1", []))[:2]
        c = make_case(code, md, ods, mp, ops, random.choice([40, 50, 60, 70]) * 365)
        if c:
            pool.append(c)

# 并发症变体：对入组成功的用例加变体
comp_templates = [
    ("MCC成立", "A00.100x001"), ("CC成立", "E11.600x051"),
    ("NONE", "E11.900"), ("MCC被排除", "K86.000"), ("CC被排除", "K80.000x002"),
]
for case in pool[:]:
    if case["id"] in ("AH2", "ZZ1") or not case["input"]["main_procedure"]["code"]:
        continue
    md = case["input"]["main_diagnosis"]["code"]
    mp = case["input"]["main_procedure"]["code"]
    for label, od in random.sample(comp_templates, min(3, len(comp_templates))):
        try:
            r = group_full(md, [od], mp, [], case["input"]["age_days"],
                           rules, drg_table, mcc_map, cc_map, excl_clean)
        except Exception:
            continue
        new_comp = r.get("COMPLICATION", "NONE")
        if new_comp == case["expected"]["complication"]:
            continue
        nl = f"{case['natural_language'][:-1]}（并发症：{label}——{name(od)}）。"
        v = {
            "id": f"{case['id']}-{label}",
            "purpose": f"测试并发症-{label}",
            "path": f"MDC匹配 → {case['id']} → 并发症判定({label}) → {r.get('DRG','')}",
            "input": {
                "gender": "男", "age_days": case["input"]["age_days"],
                "main_diagnosis": {"code": md, "name": name(md)},
                "other_diagnoses": [{"code": od, "name": name(od)}],
                "main_procedure": {"code": mp, "name": name(mp)},
                "other_procedures": [],
            },
            "expected": {
                "mdc": r.get("MDC", ""), "adrg": r.get("ADRG"),
                "adrg_name": r.get("ADRG_NAME", ""), "drg": r.get("DRG"),
                "drg_name": r.get("DRG_NAME", ""), "complication": new_comp,
            },
            "natural_language": nl,
        }
        pool.append(v)

# 输出
output = os.path.join(os.path.dirname(__file__), "drg_test_pool.json")
with open(output, "w", encoding="utf-8") as f:
    json.dump(pool, f, ensure_ascii=False, indent=2)
print(f"用例池: {len(pool)} 个 → {output}")

# 统计
cats = {}
for c in pool:
    cats[c["purpose"][:4]] = cats.get(c["purpose"][:4], 0) + 1
print(f"分布: {cats}")
