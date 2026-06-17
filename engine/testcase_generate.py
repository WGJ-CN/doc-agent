"""
测试用例生成引擎（通用 + DRG 专用双路径）

  检测到 DRG 项目 → 程序选编码 + ruzu 验算 + LLM 写 NL
  非 DRG 项目     → LLM 两阶段生成（大纲 → 用例）
"""
import openai
import json
import os
import sys
import random

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

DRG_DIR = r"C:\Users\32198\Desktop\work\1\软件工程智能体\drg-project\engine"

client = openai.OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


# ================= 工具函数 =================

def load_material(filepath: str) -> str:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def jl(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def call_llm(system: str, user: str, temp=0.3, max_tok=4096, json_mode=False) -> str:
    kwargs = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temp, "max_tokens": max_tok,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content.strip()


def _codes(items):
    if not isinstance(items, list):
        return []
    return [x["code"] for x in items if isinstance(x, dict) and "code" in x]


# ================= DRG 检测 =================

def _is_drg_project(material: str) -> bool:
    keywords = ["DRG", "入组", "MDC", "ADRG", "CHS-DRG", "诊断相关分组",
                "主要诊断", "并发症等级", "MCC", "排除表"]
    return any(kw.lower() in material.lower() for kw in keywords)


# ================= 通用路径：LLM 两阶段 =================

def _generic_outline(material: str) -> dict:
    default = [
        {"id": "1", "title": "功能测试", "points": ["核心功能正常流程", "异常输入处理", "边界条件"]},
        {"id": "2", "title": "集成测试", "points": ["模块间接口调用", "数据流转正确性"]},
        {"id": "3", "title": "非功能测试", "points": ["性能指标", "安全测试"]},
    ]
    system = (
        "你是测试工程师。根据项目文档生成测试计划大纲。覆盖功能、集成、边界、异常场景。"
        "输出JSON：{\"sections\":[{\"id\":\"\",\"title\":\"\",\"points\":[]}]}，仅输出JSON。\n\n"
        f"{material}"
    )
    user = f"===== 模板 =====\n{json.dumps(default, ensure_ascii=False, indent=2)}\n请微调后输出。"
    raw = call_llm(system, user, temp=0.2, max_tok=2048, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"sections": default}


def _generic_testcases(material: str, outline: dict) -> list:
    secs = ""
    for s in outline.get("sections", []):
        secs += f"- {s['title']}：{'；'.join(s['points'])}\n"

    system = (
        "你是测试工程师。根据项目文档和测试大纲，生成详细测试用例。每个用例包含：\n"
        "- id: 编号\n"
        "- purpose: 测试目标\n"
        "- steps: 测试步骤（列表）\n"
        "- expected: 预期结果\n"
        "- natural_language: 自然语言场景描述\n"
        "输出纯JSON数组[{...}]。\n\n"
        f"===== 大纲 =====\n{secs}\n===== 文档 =====\n{material}"
    )
    raw = call_llm(system, "请生成测试用例JSON数组。", temp=0.4, max_tok=8000, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


# ================= DRG 路径：程序构造 + ruzu 验算 =================

def _drg_build_cases() -> list:
    sys.path.insert(0, DRG_DIR)
    from ruzu import group_full

    rules = jl(os.path.join(DRG_DIR, "adrg_rules.json"))
    drg_table = jl(os.path.join(DRG_DIR, "drg_table.json"))
    mcc_table = jl(os.path.join(DRG_DIR, "mcc_table.json"))
    cc_table = jl(os.path.join(DRG_DIR, "cc_table.json"))
    exclusion = jl(os.path.join(DRG_DIR, "exclusion_table.json"))
    c2n = jl(os.path.join(DRG_DIR, "code2name.json"))

    mcc_map = {}
    for t, entries in mcc_table.items():
        for e in entries:
            mcc_map[e["code"]] = t
    cc_map = {}
    for t, entries in cc_table.items():
        for e in entries:
            cc_map[e["code"]] = t
    excl_clean = {k: [e["code"] for e in v] for k, v in exclusion.items()}

    def n(c):
        return c2n.get(c, c) if c else ""

    mdc_diag = {}
    for key, entry in rules.items():
        if key.startswith("MDC") and "主诊表" in key:
            cs = _codes(entry.get("包含以下主要诊断", []))
            if cs:
                mdc_diag[key[3]] = cs

    by_prefix = {}
    for c, e in rules.items():
        if not c.startswith("MDC"):
            by_prefix.setdefault(c[0], []).append(c)

    # 随机选取 ADRG：MDCA 固定几个，其余每类随机抽
    picks = []
    for c in ["AA1", "AB1", "AH2"]:
        if c in rules:
            picks.append(c)
    if "P" in by_prefix:
        picks.append(random.choice(by_prefix["P"]))

    # 每个 MDC 随机抽 1 个有手术的 ADRG
    for p in "BCDEFGHIJKLMNQRSTUVWX":
        if p in by_prefix:
            candidates = [c for c in by_prefix[p]
                          if _codes(rules[c].get("包含以下主要手术或操作", []))
                          or "同时包含以下手术或操作" in rules[c]]
            if candidates:
                picks.append(random.choice(candidates))

    # 随机选取 ~10 个
    random.shuffle(picks)
    picks = picks[:random.randint(8, 12)]

    cases = []
    for code in picks:
        entry = rules[code]

        md = ""
        for f in ["包含以下主要诊断", "主要诊断", "包含以下诊断"]:
            cs = _codes(entry.get(f, []))
            if cs:
                md = cs[0]
                break
        ods = _codes(entry.get("其他诊断", []))[:3]
        mp = ""
        for f in ["包含以下主要手术或操作", "主要手术或操作", "主要手术或操作1"]:
            cs = _codes(entry.get(f, []))
            if cs:
                mp = cs[0]
                break
        if not mp:
            gs = entry.get("同时包含以下手术或操作", [])
            if isinstance(gs, list):
                for g in gs:
                    if isinstance(g, dict):
                        cs = _codes(g.get("and_group", []))
                        if cs:
                            mp = cs[0]
                            break
        ops = _codes(entry.get("手术或操作1", []))[:2]

        if not md and code[0] in mdc_diag:
            md = random.choice(mdc_diag[code[0]])
        if not md:
            fallback = {"AA1": "J96.900", "AB1": "K72.900", "AH2": "J12.800"}
            md = fallback.get(code, "Z00.000")
        # MDCP 补新生儿诊断
        if code.startswith("P") and md == "Z00.000":
            md = random.choice(["P07.000", "P05.000", "P22.000"])
        if code == "AH2":
            ods, mp, ops = ["Z93.000"], "96.7201", []

        md, mp = md or "Z00.000", mp or ""
        age = 3 if code.startswith("P") else 50 * 365

        try:
            r = group_full(md, ods, mp, ops, age, rules, drg_table, mcc_map, cc_map, excl_clean)
        except Exception as e:
            print(f"  [跳过] {code}: {e}")
            continue

        cat = {"A": "先期分组-MDCA", "P": "先期分组-MDCP",
               "Y": "先期分组-MDCY", "Z": "先期分组-MDCZ"}.get(code[0], f"常规MDC-MDC{code[0]}")
        case = {
            "id": code,
            "purpose": f"测试{cat}-{code}：{entry.get('name','')}",
            "path": f"先期分组/MDC匹配 → {cat} → {code} → {r.get('DRG','')}",
            "input": {
                "gender": "男", "age_days": age,
                "main_diagnosis": {"code": md, "name": n(md)},
                "other_diagnoses": [{"code": c, "name": n(c)} for c in ods],
                "main_procedure": {"code": mp, "name": n(mp)},
                "other_procedures": [{"code": c, "name": n(c)} for c in ops],
            },
            "expected": {
                "mdc": r.get("MDC", ""), "adrg": r.get("ADRG"),
                "adrg_name": r.get("ADRG_NAME", ""), "drg": r.get("DRG"),
                "drg_name": r.get("DRG_NAME", ""), "complication": r.get("COMPLICATION", "NONE"),
            },
            "natural_language": "",
        }
        cases.append(case)
        ok = "OK" if r.get("STATUS") in ("SUCCESS", "DRG_FALLBACK") else r.get("STATUS", "?")
        print(f"  [{len(cases)}] {code} → {r.get('MDC','?')}/{r.get('ADRG','?')}/{r.get('DRG','?')} [{ok}]")

    # 并发症变体
    comp_templates = [
        ("MCC成立", "A00.100x001"), ("CC成立", "E11.600x051"),
        ("NONE", "E11.900"), ("MCC被排除", "K86.000"), ("CC被排除", "K80.000x002"),
    ]
    random.shuffle(comp_templates)
    # 随机选 1~2 个 ADRG 做并发症变体
    eligible = [c for c in cases if c["id"] not in ("AH2", "ZZ1", "PB1")
                and c["input"]["main_procedure"]["code"]]
    random.shuffle(eligible)
    for case in eligible[:random.randint(1, 2)]:
        adrg = case["id"]
        inp = case["input"]
        md = inp["main_diagnosis"]["code"]
        mp = inp["main_procedure"]["code"]
        # 随机选 2~4 个并发症模板
        for label, od in random.sample(comp_templates, min(len(comp_templates), random.randint(2, 4))):
            try:
                r = group_full(md, [od], mp, [], inp["age_days"],
                               rules, drg_table, mcc_map, cc_map, excl_clean)
            except Exception:
                continue
            new_comp = r.get("COMPLICATION", "NONE")
            if new_comp == case["expected"]["complication"]:
                continue
            v = {
                "id": f"{adrg}-{label}",
                "purpose": f"测试并发症-{label}",
                "path": f"MDC匹配 → {adrg} → 并发症判定({label}) → {r.get('DRG','')}",
                "input": {
                    "gender": "男", "age_days": inp["age_days"],
                    "main_diagnosis": {"code": md, "name": n(md)},
                    "other_diagnoses": [{"code": od, "name": n(od)}],
                    "main_procedure": {"code": mp, "name": n(mp)},
                    "other_procedures": [],
                },
                "expected": {
                    "mdc": r.get("MDC", ""), "adrg": r.get("ADRG"),
                    "adrg_name": r.get("ADRG_NAME", ""), "drg": r.get("DRG"),
                    "drg_name": r.get("DRG_NAME", ""), "complication": new_comp,
                },
                "natural_language": "",
            }
            cases.append(v)
            print(f"  [并发症] {adrg}-{label}: DRG={r.get('DRG','?')}")
            if len([c for c in cases if c["id"].startswith(adrg + "-")]) >= 5:
                break

    return cases


# ================= NL + Markdown =================

def _add_nl(cases: list):
    brief = []
    for c in cases:
        inp = c["input"]
        ad = inp.get("age_days", 18250)
        ag = f"{ad}天（新生儿）" if ad < 29 else f"{ad // 30}个月" if ad < 365 else f"{ad // 365}岁"
        brief.append({
            "id": c["id"], "gender": inp["gender"], "age_desc": ag,
            "main_diag": inp["main_diagnosis"]["name"],
            "other_diags": [d["name"] for d in inp.get("other_diagnoses", []) if d.get("name")],
            "main_proc": inp["main_procedure"]["name"],
            "other_procs": [p["name"] for p in inp.get("other_procedures", []) if p.get("name")],
        })
    system = (
        "你是临床医师。请把以下结构化病例写成简短的自然语言描述（80~150字）。"
        "融入主诉、现病史、既往史、诊疗经过。不出现ICD编码和DRG术语。"
        "若诊断名看起来是占位符，不要编造具体疾病——围绕手术叙述。"
        "输出JSON：{\"cases\":[{\"id\":\"...\",\"text\":\"...\"}]}，仅输出JSON。"
    )
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": system},
                   {"role": "user", "content": json.dumps(brief, ensure_ascii=False)}],
        temperature=0.5, max_tokens=4096, response_format={"type": "json_object"},
    )
    try:
        data = json.loads(resp.choices[0].message.content.strip())
        nl = {x["id"]: x["text"] for x in data.get("cases", [])}
        for c in cases:
            if c["id"] in nl:
                c["natural_language"] = nl[c["id"]]
        print(f"[NL] {len(nl)} 段")
    except Exception as e:
        print(f"[NL] 失败: {e}")


def _write_md(cases: list, output_md: str, doc_type: str):
    # 概览表
    lines = ["| # | 测试目标 | 预期结果 |", "|---|----------|---------|"]
    for i, c in enumerate(cases):
        exp = c.get("expected", {})
        lines.append(f"| {i+1} | {c.get('purpose','')[:35]} | "
                     f"{exp.get('mdc','')}→{exp.get('adrg','')}→{exp.get('drg','')} |")

    detail = []
    for i, c in enumerate(cases):
        inp = c["input"]
        exp = c.get("expected", {})
        nl = c.get("natural_language", "")
        # 通用用例用 steps，DRG 用例用编码表
        if "steps" in c:
            steps_md = "\n".join(f"{j+1}. {s}" for j, s in enumerate(c.get("steps", [])))
            d = (f"### 用例{i+1}：{c.get('purpose','')}\n\n"
                 f"> {nl}\n\n"
                 f"**测试步骤**：\n\n{steps_md}\n\n"
                 f"**预期结果**：{c.get('expected','')}\n\n---\n\n")
        else:
            d = (f"### 用例{i+1}：{c.get('purpose','')}\n\n"
                 f"> {nl}\n\n"
                 f"| 字段 | 编码 | 名称 |\n|------|------|------|\n")
            d += f"| 主要诊断 | {inp['main_diagnosis']['code']} | {inp['main_diagnosis']['name']} |\n"
            for x in inp.get("other_diagnoses", []):
                if x.get("code"):
                    d += f"| 其他诊断 | {x['code']} | {x['name']} |\n"
            if inp["main_procedure"].get("code"):
                d += f"| 主要手术 | {inp['main_procedure']['code']} | {inp['main_procedure']['name']} |\n"
            for x in inp.get("other_procedures", []):
                if x.get("code"):
                    d += f"| 其他手术 | {x['code']} | {x['name']} |\n"
            d += (f"\n**预期分组**：{exp.get('mdc','')} → {exp.get('adrg','')} {exp.get('adrg_name','')}"
                  f" → {exp.get('drg','')} {exp.get('drg_name','')}（{exp.get('complication','')}）\n\n---\n\n")
        detail.append(d)

    md = f"# {doc_type}\n\n## 覆盖概览\n\n{chr(10).join(lines)}\n\n---\n\n## 详细用例\n\n{''.join(detail)}"
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[MD] {output_md}")


# ================= 顶层编排 =================

def generate_testcase_for_topic(material_file: str = None, output_md: str = None,
                                 output_json: str = None, doc_type: str = "测试用例"):
    if output_md is None and output_json is not None:
        output_md = output_json.replace(".json", ".md")
    elif output_md is None:
        output_md = "测试用例.md"

    print(f"\n{'=' * 50}")
    print(f"测试用例生成智能体")
    print(f"{'=' * 50}")

    material = load_material(material_file) if material_file else ""
    is_drg = _is_drg_project(material)
    print(f"检测: {'DRG项目 → 知识驱动+引擎验证' if is_drg else '通用项目 → LLM生成'}")

    if is_drg:
        print("\n[DRG] 从用例池随机抽取...")
        pool_path = os.path.join(os.path.dirname(__file__), "drg_test_pool.json")
        if not os.path.exists(pool_path):
            print("[FAIL] 用例池不存在，请先运行 _build_drg_pool.py")
            return None
        pool = json.load(open(pool_path, encoding="utf-8"))
        random.shuffle(pool)
        cases = pool[:10]
        print(f"  从 {len(pool)} 个用例中抽取 {len(cases)} 个")
    else:
        print("\n[通用] LLM 两阶段生成...")
        outline = _generic_outline(material)
        cases = _generic_testcases(material, outline)

    if not cases:
        print("[FAIL] 未生成用例")
        return None

    _write_md(cases, output_md, doc_type)
    print(f"\n[OK] {output_md}（{len(cases)} 个用例）")
    return output_md


if __name__ == "__main__":
    generate_testcase_for_topic(output_md="DRG入组测试用例.md")
