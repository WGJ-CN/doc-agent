import openai
import json
import os

# ================= 配置 =================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

from iqs_search import search_standards as iqs_search_standards

client = openai.OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)

MAX_REWRITES = 3
PASS_SCORE = 8


# ================= 工具函数 =================
def load_material(filepath: str) -> str:
    """读取整理的素材文本文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def call_deepseek(system_prompt: str, user_prompt: str,
                  temperature: float = 0.3, max_tokens: int = 4096,
                  json_mode: bool = False) -> str:
    """封装 API 调用"""
    kwargs = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content.strip()


# ================= Agent 工具定义 =================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_writing_standards",
            "description": "搜索需求规格说明书的写作规范和标准模板（如 IEEE 830、GB/T 9385、GB/T 8567），"
                           "获取标准文档结构要求、章节规范和质量标准。这是生成文档的第一步。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "搜索关键词，如 ['IEEE 830', 'GB/T 9385', '需求文档结构']"
                    }
                },
                "required": ["keywords"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_outline",
            "description": "根据写作规范、项目素材和重点关注领域，生成需求规格说明书的结构化大纲。",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "大纲需重点关注的领域，如业务流程、功能需求、数据需求、接口需求"
                    }
                },
                "required": ["focus_areas"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_document",
            "description": "根据已生成的大纲和项目素材，生成完整的需求规格说明书 Markdown 文档。"
                           "必须先生成大纲后才能调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "score_document",
            "description": "对已生成的文档进行质量评分（满分 10 分），从完整性、准确性、结构性、"
                           "可读性、格式规范五个维度评估，并给出具体反馈。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rewrite_document",
            "description": "根据评分反馈和改进意见重写文档。仅在上一轮评分低于 8 分时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "feedback": {
                        "type": "string",
                        "description": "上一轮评分的具体反馈和改进建议"
                    }
                },
                "required": ["feedback"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "文档质量已达标（评分 >= 8 分）或已达到最大重写次数，结束生成流程。",
            "parameters": {
                "type": "object",
                "properties": {
                    "final_score": {
                        "type": "number",
                        "description": "最终文档评分"
                    },
                    "summary": {
                        "type": "string",
                        "description": "生成过程总结"
                    }
                },
                "required": ["final_score", "summary"]
            }
        }
    }
]


# ================= 内部生成函数 =================

def _search_standards(args: dict) -> dict:
    """通过阿里云 IQS API 搜索需求文档写作规范"""
    keywords = args.get("keywords", [])
    return iqs_search_standards("requirements", keywords)


def _generate_outline(material: str, doc_type: str, focus_areas: list, standards_info: dict | None = None) -> dict:
    """调用 API 生成大纲 — 使用详细章节模板"""
    focus_str = "、".join(focus_areas) if focus_areas else "功能需求、数据需求、接口需求"

    default_sections = [
        {"id": "1", "title": "1. 引言",
         "points": ["编写目的与范围", "核心术语定义", "参考资料"]},
        {"id": "2", "title": "2. 功能需求",
         "points": [
             "核心业务流程（需体现顺序和决策逻辑）",
             "功能点描述（使用步骤化描述，而非并列编号）",
             "特殊规则或边界条件",
             "非功能约束（性能、可靠性等，1~3条）"
         ]},
        {"id": "3", "title": "3. 数据需求",
         "points": [
             "输入数据的必要字段",
             "输出数据的字段",
             "核心数据字典或代码表"
         ]},
        {"id": "4", "title": "4. 接口需求",
         "points": [
             "与外部模块/系统的交互接口",
             "内部API设计（如适用）"
         ]},
        {"id": "appendix", "title": "附录",
         "points": ["关键示例或图示（如Mermaid流程图源文本）"]}
    ]

    sections_desc = json.dumps(default_sections, ensure_ascii=False, indent=2)

    system_prompt = (
        f"你是一位软件需求分析师。请根据提供的项目资料，生成《{doc_type}》的详细大纲。\\n"
        "资料可能包含代码片段，请从中逆向提取业务规则和功能逻辑，作为需求依据。\\n"
        "大纲需要体现以下要求：\\n"
        f"1. 重点关注领域：{focus_str}\\n"
        "2. 功能需求部分必须明确强调业务流程的先后顺序和条件依赖，不能只列并列功能点。\\n"
        "   建议在要点中注明「流程步骤：第一步...第二步...」或「决策树顺序」。\\n"
        "3. 文档需包含至少一个流程图（Mermaid格式），请在功能需求或附录的要点中注明「插入Mermaid流程图」。\\n"
        "4. 章节结构固定为：1.引言 2.功能需求 3.数据需求 4.接口需求 附录。\\n"
        "5. 每个章节的要点需要具体、可执行，不要泛泛而谈。\\n"
        "6. 大纲要点必须严格基于素材内容提取，不得编造素材中不存在的章节或要点。\\n"
        "7. 参考模板如下（可在此基础上增删要点，但必须覆盖素材中的实际内容）：\\n"
        f"{sections_desc}\\n"
        "8. 请在 JSON 中输出大纲对象，格式为：\\n"
        '   {{"sections": [ 每个章节对象包含 id, title, points 数组 ]}}\\n'
        "9. 不要输出任何额外解释。\\n"
        "\n===== 搜索到的写作规范（请严格遵循） =====\n" + (json.dumps(standards_info, ensure_ascii=False, indent=2) if standards_info else "") + "\n===== 规范结束 =====\n"
        f"\\n===== 项目资料 =====\\n{material}\\n===== 资料结束 ====="
    )

    raw = call_deepseek(system_prompt, "请生成大纲 JSON。", temperature=0.2, max_tokens=2048, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"sections": [], "_raw": raw}


def _build_sections_desc(outline: dict) -> str:
    """将大纲对象转为可读描述"""
    sections = outline.get("sections", [])
    lines = []
    for sec in sections:
        sid = sec.get("id", "")
        title = sec.get("title", "")
        points = sec.get("points", [])
        lines.append(f"### {sid}. {title}")
        for p in points:
            lines.append(f"  - {p}")
    return "\n".join(lines)



def _clean_document(text: str) -> str:
    """移除文档开头的客套话/元文本，只保留从第一个 # 标题开始的内容"""
    import re
    m = re.search(r"^#\s+", text, re.MULTILINE)
    if m:
        return text[m.start():].strip()
    lines = text.split("\n")
    skip_phrases = ["好的", "遵照", "根据您", "以下是", "我将", "好的,", "OK", "以下为",
                    "这是", "为您生成", "已生成", "根据要求", "按照要求", "根据大纲", "现在", "接下来"]
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("#") or (s and not any(p in s for p in skip_phrases)):
            return "\n".join(lines[i:]).strip()
    return text.strip()


def _generate_document_text(material: str, outline: dict, doc_type: str,
                             feedback: str = "", previous_document: str = "",
                             standards_info: dict | None = None) -> str:
    """生成/重写完整文档（Markdown）。重写时同时传入反馈和上次文档。"""
    sections_desc = _build_sections_desc(outline)

    if feedback:
        prev_doc_section = ""
        if previous_document:
            prev_doc_section = (
                f"===== 上次生成的文档（需要改进） =====\n"
                f"{previous_document}\n"
                f"===== 上次文档结束 =====\n\n"
            )
        system_prompt = (
            "你是一位资深软件需求分析师。请基于上次生成的文档，根据评阅反馈进行局部修改——只改有问题的地方，其他部分原样保留。\n\n"
            f"**需要修正的问题（按位置逐一修改）：**\n{feedback}\n\n"
            f"{prev_doc_section}"
            "**修改原则：**\n"
            "1. 只修改反馈中指出的具体位置和问题，未提及的部分保持原样\n"
            "2. 修改后的内容应符合：功能需求按流程步骤描述，体现决策逻辑和顺序依赖\n"
            "3. 确保包含 Mermaid 流程图（若之前缺失则补充）。Mermaid 规范：LR 横向布局，节点简洁有连线，A -->|标注| B 箭标\n"
            "4. 仅使用素材中的业务规则，严禁编造\n"
            "5. 输出完整修改后的 Markdown 文档\n\n"
            f"===== 文档大纲 =====\n{sections_desc}\n===== 大纲结束 =====\n\n"
            "\n===== 搜索到的写作规范（请严格遵循） =====\n" + (json.dumps(standards_info, ensure_ascii=False, indent=2) if standards_info else "") + "\n===== 规范结束 =====\n"
            f"===== 项目资料 =====\n{material}\n===== 资料结束 ====="
        )
        prompt = f"请基于上次文档，根据反馈逐一修改问题部分，输出完整的《{doc_type}》Markdown 文档。"
    else:
        system_prompt = (
            "你是一位资深软件需求分析师，擅长编写专业的需求规格说明书。\n\n"
            f"请根据提供的大纲和项目资料，撰写完整的《{doc_type}》Markdown 文档。\n\n"
            "**写作要求：**\n"
            "1. 严格按照大纲的章节结构组织全文，使用大纲中指定的章节标题\n"
            "2. 功能需求按流程步骤描述，体现决策逻辑和顺序依赖，不使用 FR-001/FR-002 简单并列\n"
            "   而应将整个决策流程作为一个功能整体，分步骤说明，或对顺序条件明确标注\n"
            "3. 在第2章或附录中，必须插入一个 Mermaid 流程图（用 ```mermaid 代码块包裹），\n"
            "   描述核心业务流程，确保语法正确。Mermaid 规范：用 graph LR 横向布局，节点六字以内，用 A -->|标注| B 箭标风格，不放孤立节点\n"
            "4. 所有专业术语首次出现时给出全称，全文统一\n"
            "5. 数据需求（第3章）必须覆盖功能需求中涉及的所有输入/输出数据字段\n"
            "6. 附录中的示例或图示必须与功能需求逻辑一致\n"
            "7. 仅使用资料中存在的业务规则和代码逻辑，不编造新功能\n"
            "   如果资料中有代码，提取其隐含的业务规则，不要直接复制代码细节\n"
            "8. 输出纯 Markdown\n\n"
            f"===== 文档大纲 =====\n{sections_desc}\n===== 大纲结束 =====\n\n"
            "\n===== 搜索到的写作规范（请严格遵循） =====\n" + (json.dumps(standards_info, ensure_ascii=False, indent=2) if standards_info else "") + "\n===== 规范结束 =====\n"
            f"===== 项目资料 =====\n{material}\n===== 资料结束 ====="
        )
        prompt = f"请生成完整的《{doc_type}》Markdown 文档，从 `# {doc_type}` 开始。"

    result = call_deepseek(system_prompt, prompt, temperature=0.4, max_tokens=8000)
    return _clean_document(result)


def _score_document(document: str, material: str, doc_type: str) -> dict:
    """评分文档"""
    # 截断过长内容，避免超 token 限制
    doc_preview = document
    mat_preview = material

    system_prompt = (
        "你是一位软件需求文档审核专家。请对以下需求规格说明书进行质量评分。\n\n"
        "评分维度（各占 2 分，满分 10 分）：\n"
        "1. 完整性(2分)：是否覆盖所有必要章节和内容\n"
        "2. 准确性(2分)：业务规则描述是否准确。如果文档中出现素材中不存在的功能、数据或规则（即编造），该维度直接 0 分\n"
        "3. 结构性(2分)：章节组织是否合理、流程描述是否有顺序依赖\n"
        "4. 可读性(2分)：语言是否清晰、术语是否统一\n"
        "5. 格式规范(2分)：是否包含 Mermaid 流程图、Markdown 格式是否正确\n\n"
        "返回纯 JSON：\n"
        '{"score": <总分>, "feedback": "<具体反馈和改进建议>", '
        '"dimensions": {"completeness": <>, "accuracy": <>, "structure": <>, "readability": <>, "format": <>}}\n\n'
        f"===== 原始素材 =====\n{mat_preview}\n===== 素材结束 =====\n\n"
        f"===== 待评分文档 =====\n{doc_preview}\n===== 文档结束 ====="
    )

    raw = call_deepseek(system_prompt, "请评分。", temperature=0.2, max_tokens=4096, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"score": 5, "feedback": raw, "dimensions": {}}


# ================= Agent 执行引擎 =================

class AgentState:
    """Agent 状态容器，tool handler 通过此对象共享状态"""
    def __init__(self):
        self.outline: dict | None = None
        self.document: str | None = None
        self.score: float = 0
        self.feedback: str = ""
        self.dimensions: dict = {}
        self.rewrite_count: int = 0
        self.finished: bool = False
        self.summary: str = ""
        self.standards_info: dict | None = None


def run_agent(material: str, doc_type: str) -> AgentState:
    """
    Agent 模式运行文档生成。
    通过 DeepSeek function calling 驱动：搜索规范→大纲→生成→评分→条件重写→完成。
    """
    st = AgentState()
    
    system_prompt = (
        "你是一个需求规格说明书生成 Agent。\n\n**核心铁律：** 所有文档内容必须严格基于用户提供的项目素材（资料），\n严禁编造、猜测、虚构素材中不存在的任何功能、数据、规则、术语。\n如果素材中找不到某个信息，不得自行补充。\n\n你必须严格按顺序调用工具完成文档生成。\n\n"
        "**执行顺序（不可跳过任何步骤）：**\n"
        f"1. 调用 search_writing_standards — 搜索写作规范\n"
        f"2. 调用 generate_outline(focus_areas=[...]) — 根据规范生成大纲\n"
        f"3. 调用 generate_document — 根据大纲生成完整文档\n"
        f"4. 调用 score_document — 对文档评分\n"
        f"5. 如果评分 < {PASS_SCORE} 且 rewrite_count < {MAX_REWRITES}：调用 rewrite_document 重写，然后回到步骤 4\n"
        f"6. 如果评分 >= {PASS_SCORE} 或 rewrite_count == {MAX_REWRITES}：调用 finish 结束\n\n"
        "每次只调用一个工具，等待结果后再执行下一步。"
    )
    
    user_prompt = (
        f"请为以下项目生成《{doc_type}》。\n\n"
        f"===== 项目资料 =====\n{material}\n===== 资料结束 ====="
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    for iteration in range(1, 21):
        if st.finished:
            break
        
        
        print(f"... Agent 第 {iteration} 轮 ...")
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )
        except Exception as e:
            print(f"Agent API 调用失败: {e}")
            break
        
        msg = response.choices[0].message
        assistant_msg: dict = {"role": "assistant"}
        
        if msg.content:
            assistant_msg["content"] = msg.content
        
        if msg.tool_calls:
            # 记录 tool_calls
            tc_data = []
            for tc in msg.tool_calls:
                tc_data.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                })
            assistant_msg["tool_calls"] = tc_data
            messages.append(assistant_msg)
            
            # 执行每个 tool call
            for tc in msg.tool_calls:
                name = tc.function.name
                print(f"  [调用工具] {name}")
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                
                result_str = ""
                
                if name == "search_writing_standards":
                    data = _search_standards(args)
                    st.standards_info = data
                    summary = data.get("standards_summary", "")
                    sr = data.get('search_results_count', 0)
                    pp = data.get('parsed_pages_count', 0)
                    print(f"    [搜索规范] 找到 {sr} 条结果，解析 {pp} 个页面")
                    if summary:
                        print(f"    [规范摘要]\n{summary}")
                    result_str = json.dumps(data, ensure_ascii=False)
                    
                elif name == "generate_outline":
                    print("    ... 正在生成文档大纲 ...")
                    st.outline = _generate_outline(material, doc_type, args.get("focus_areas", []), st.standards_info)
                    n = len(st.outline.get("sections", []))
                    result_str = json.dumps({"status": "ok", "section_count": n}, ensure_ascii=False)
                    
                elif name == "generate_document":
                    if st.outline is None:
                        result_str = json.dumps({"error": "请先生成大纲"})
                    else:
                        print("    ... 正在生成文档全文 ...")
                        st.document = _generate_document_text(material, st.outline, doc_type, standards_info=st.standards_info)
                        result_str = json.dumps({"status": "ok", "length": len(st.document)}, ensure_ascii=False)
                        
                elif name == "score_document":
                    if st.document is None:
                        result_str = json.dumps({"error": "请先生成文档"})
                    else:
                        print("    ... 正在评分文档 ...")
                        score_data = _score_document(st.document, material, doc_type)
                        st.score = score_data.get("score", 0)
                        st.feedback = score_data.get("feedback", "")
                        st.dimensions = score_data.get("dimensions", {})
                        print(f"    [评分] {st.score}/10")
                        dims = st.dimensions
                        if dims:
                            print(f"    完整性:{dims.get('completeness','-')} 准确性:{dims.get('accuracy','-')} 结构性:{dims.get('structure','-')} 可读性:{dims.get('readability','-')} 格式:{dims.get('format','-')}")
                        if st.feedback:
                            print(f"    [反馈] {st.feedback}")
                        result_str = json.dumps(score_data, ensure_ascii=False)
                        
                elif name == "rewrite_document":
                    if st.rewrite_count >= MAX_REWRITES:
                        result_str = json.dumps({"error": f"已达最大重写次数 {MAX_REWRITES}，请调用 finish"})
                    elif st.outline is None:
                        result_str = json.dumps({"error": "缺少大纲"})
                    else:
                        st.rewrite_count += 1
                        feedback = args.get("feedback", st.feedback)
                        prev_doc = st.document or ""
                        print(f"    ... 第 {st.rewrite_count} 次重写 ...")
                        st.document = _generate_document_text(material, st.outline, doc_type, feedback, prev_doc, st.standards_info)
                        result_str = json.dumps({"status": "ok", "rewrite_count": st.rewrite_count, "length": len(st.document)}, ensure_ascii=False)
                        
                elif name == "finish":
                    st.finished = True
                    st.summary = args.get("summary", "")
                    st.score = args.get("final_score", st.score)
                    result_str = json.dumps({"status": "ok", "message": "流程结束"})
                    
                else:
                    result_str = json.dumps({"error": f"未知工具: {name}"})
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str
                })
                
                if name == "finish":
                    break
        else:
            # 无 tool_calls，模型可能直接回复了文字，推动它继续
            messages.append(assistant_msg)
            if st.document and st.score > 0:
                if st.score < PASS_SCORE and st.rewrite_count < MAX_REWRITES:
                    messages.append({
                        "role": "user",
                        "content": f"当前评分 {st.score}/10，未达标。请调用 rewrite_document 重写。"
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": f"当前评分 {st.score}/10，已达标。请调用 finish 结束。"
                    })
            elif st.outline and not st.document:
                messages.append({"role": "user", "content": "大纲已就绪，请调用 generate_document。"})
            elif not st.outline:
                messages.append({"role": "user", "content": "请先调用 search_writing_standards。"})
    
    return st


# ================= 公开接口（签名不变） =================

def generate_srs_for_topic(material_file: str, output_md: str, doc_type: str = "需求规格说明书"):
    """
    为单个主题生成需求规格说明书（Agent 模式）。
    
    后端 import 调用的入口，签名与旧版完全一致。
    """
    print(f"\n{'=' * 50}")
    print(f"... 开始生成：{doc_type}（素材：{material_file}）")
    
    material = load_material(material_file)
    print(f"   素材长度：{len(material)} 字符")
    
    st = run_agent(material, doc_type)
    
    if st.outline:
        outline_path = output_md.replace('.md', '_outline.json')
        with open(outline_path, 'w', encoding='utf-8') as f:
            json.dump(st.outline, f, ensure_ascii=False, indent=2)
        print(f"... 大纲已保存至 {outline_path}")
    
    if st.document:
        with open(output_md, 'w', encoding='utf-8') as f:
            f.write(st.document)
        print(f"... 文档已生成：{output_md}")
        print(f"   最终评分：{st.score}/10 | 重写次数：{st.rewrite_count}")
    else:
        raise RuntimeError("Agent 未生成文档")
    
    if st.feedback:
        print(f"   评分反馈：{st.feedback}...")


# ================= 主入口 =================
if __name__ == "__main__":
    tasks = [
        {
            "material_file": "material_drg.txt",
            "output_md": "DRG入组系统_需求规格说明书.md",
            "doc_type": "DRG入组系统 需求规格说明书"
        },
        {
            "material_file": "material_docgen.txt",
            "output_md": "文档生成智能体_需求规格说明书.md",
            "doc_type": "文档自动生成智能体 需求规格说明书"
        }
    ]

    missing = [t["material_file"] for t in tasks if not os.path.exists(t["material_file"])]
    if missing:
        print("以下素材文件未找到，请准备好后再运行：")
        for f in missing:
            print(f"   - {f}")
        exit(1)

    for task in tasks:
        generate_srs_for_topic(
            material_file=task["material_file"],
            output_md=task["output_md"],
            doc_type=task["doc_type"]
        )

    print("\n... 所有文档生成完毕！")

