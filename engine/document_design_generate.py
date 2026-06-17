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
    """读取整理后的素材文本文件"""
    with open(filepath, "r", encoding="utf-8") as f:
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
            "description": "搜索软件设计文档的写作规范和标准模板（如 IEEE 1016、GB/T 8567），"
                           "获取标准文档结构要求、章节规范和质量标准。这是生成设计文档的第一步。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "搜索关键词，如 ['IEEE 1016', 'GB/T 8567', '软件设计文档结构']"
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
            "description": "根据写作规范和项目代码素材，生成软件设计文档的结构化大纲。",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "大纲需重点关注的领域，如架构设计、构件设计、接口设计、数据库设计"
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
            "description": "根据已生成的大纲和项目代码素材，生成完整的软件设计文档 Markdown。",
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
            "description": "对已生成的设计文档进行质量评分（满分 10 分），从完整性、准确性、结构性、"
                           "可读性、格式规范五个维度评估。",
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
            "name": "check_code_consistency",
            "description": "检查设计文档是否与项目代码一致，包括架构描述、接口定义、数据结构和数据库"
                           "设计是否与代码实际实现匹配。仅用于软件设计文档，在评分之后调用。",
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
            "description": "根据评分反馈和代码一致性检查结果重写文档。"
                           "在评分 < 8 或文档与代码不一致时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "feedback": {
                        "type": "string",
                        "description": "评分反馈和代码一致性问题的综合描述"
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
            "description": "文档质量已达标且与代码一致，或已达到最大重写次数，结束流程。",
            "parameters": {
                "type": "object",
                "properties": {
                    "final_score": {"type": "number", "description": "最终评分"},
                    "summary": {"type": "string", "description": "生成过程总结"}
                },
                "required": ["final_score", "summary"]
            }
        }
    }
]


# ================= 内部生成函数 =================

def _search_standards(args: dict) -> dict:
    """通过阿里云 IQS API 搜索设计文档写作规范"""
    keywords = args.get("keywords", [])
    return iqs_search_standards("design", keywords)


def _generate_outline(material: str, doc_type: str, focus_areas: list, standards_info: dict | None = None) -> dict:
    """调用 API 生成设计文档大纲 — 使用详细章节模板和搜索到的写作规范"""
    focus_str = "、".join(focus_areas) if focus_areas else "架构设计、构件设计、接口设计、数据设计、数据库设计"

    default_sections = [
        {"id": "1", "title": "1. 引言",
         "points": ["编写目的与范围", "核心术语定义", "参考资料与设计依据"]},
        {"id": "2", "title": "2. 总体架构设计",
         "points": [
             "系统分层架构概述（如表现层/业务层/数据层）",
             "模块分割方案及模块间依赖关系",
             "技术选型及关键设计决策说明",
             "插入Mermaid架构图（系统组件图或分层图）"
         ]},
        {"id": "3", "title": "3. 构件设计",
         "points": [
             "各构件/模块职责与内部结构",
             "核心类/组件设计（含关键属性、方法、职责说明）",
             "关键算法或处理流程描述",
             "插入Mermaid流程图（核心业务流程或算法）",
             "错误处理策略"
         ]},
        {"id": "4", "title": "4. 接口设计",
         "points": [
             "外部接口（与第三方系统交互的协议、数据格式）",
             "内部模块间接口（API 定义、参数、返回值）",
             "数据传递格式与序列化方案",
             "接口异常处理与状态码定义"
         ]},
        {"id": "5", "title": "5. 数据设计",
         "points": [
             "核心数据结构定义（含字段、类型、约束）",
             "数据字典或代码表",
             "数据流转关系（模块间数据传递路径）"
         ]},
        {"id": "6", "title": "6. 数据存储设计",
         "points": [
             "数据存储方案选型与理由（数据库/内存/文件等）",
             "如使用数据库：ER 图或表关系描述（Mermaid erDiagram）、核心表结构（字段名、类型、主键、外键、索引）、分库分表策略（如适用）",
             "如使用内存存储：数据结构定义、读写机制、生命周期管理",
             "如使用文件存储：文件格式、目录结构、读写策略"
         ]},
        {"id": "appendix", "title": "附录",
         "points": ["关键类图或序列图（Mermaid 格式）", "配置项说明", "性能与安全设计方案补充"]}
    ]
    sections_desc_template = json.dumps(default_sections, ensure_ascii=False, indent=2)

    system_prompt = (
        f"你是一位资深软件架构师。请根据提供的项目代码资料，生成《{doc_type}》的详细大纲。\n"
        "资料可能包含代码片段，请从中逆向提取系统架构、模块划分、接口设计和数据结构信息，作为设计依据。严禁描述代码文件本身的内容，严禁在文档中提及任何文件名或文件路径——代码只是用来提炼设计的原料，不是描述对象。\n"
        "参考章节结构：1.引言（必选） 2.总体架构设计（必选） 3.构件设计（必选） "
        "4.接口设计（如代码有接口则必选） 5.数据设计（如代码有数据结构则必选） "
        "6.数据存储设计（必选） 附录（必选）。\n"
        "关键：数据存储设计章节始终保留——如使用数据库则描述表结构和ER图，如使用内存字典/文件存储则描述存储结构和读写机制。其他章节根据代码实际情况决定包含哪些，代码完全没有的部分可跳过。\n\n"
        "大纲要求：\n"
        f"1. 重点关注领域：{focus_str}\n"
        "2. 总体架构设计须明确系统分层和模块分割方案，不能只并列列出模块名称\n"
        "3. 文档需包含 Mermaid 架构图（总体架构设计章）和 Mermaid 流程图（构件设计章）；"
        "如果数据存储设计章涉及数据库，还需 ER 图（Mermaid erDiagram）\n"
        "4. 构件设计需覆盖核心模块内部结构、类设计、关键算法和错误处理\n"
        "5. 每个章节要点必须严格基于代码实际内容，不得编造代码中不存在的模块或结构\n"
        "6. 从代码中提取设计，而非描述代码——大纲要点应描述架构和设计意图\n"
        "7. 参考模板如下（可在此基础上增删要点，但必须覆盖代码中的实际内容）：\n"
        f"{sections_desc_template}\n"
        '8. 输出纯 JSON：{{"sections": [每个章节对象包含 id, title, points 数组]}}\n'
        "9. 不输出任何额外解释\n\n"
        "\n===== 搜索到的写作规范（请严格遵循） =====\n" + (json.dumps(standards_info, ensure_ascii=False, indent=2) if standards_info else "") + "\n===== 规范结束 =====\n"
        f"===== 项目代码资料 =====\n{material}\n===== 资料结束 ====="
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
    """生成/重写完整设计文档（Markdown）。重写时同时传入反馈和上次文档。"""
    sections_desc = _build_sections_desc(outline)
    mat_preview = material

    if feedback:
        prev_doc_section = ""
        if previous_document:
            prev_doc_section = (
                f"===== 上次生成的文档（需要改进） =====\n"
                f"{previous_document}\n"
                f"===== 上次文档结束 =====\n\n"
            )
        system_prompt = (
            "你是一位资深软件架构师。请基于上次生成的文档，根据评阅反馈进行局部修改——只改有问题的地方，其他部分原样保留。\n\n"
            f"**需要修正的问题（按位置逐一修改）：**\n{feedback}\n\n"
            f"{prev_doc_section}"
            "**修改原则：**\n"
            "0. 禁止描述代码：不得提及文件名或文件路径，不得贴代码片段\n"
            "1. 只修改反馈中指出的具体位置和问题，未提及的部分原样保留\n"
            "2. 修改后应满足：架构章含Mermaid架构图，构件章含Mermaid流程图\n"
            "3. 所有设计描述必须与代码一致，严禁编造\n"
            "4. 输出完整修改后的 Markdown 文档\n\n"
            f"===== 文档大纲 =====\n{sections_desc}\n===== 大纲结束 =====\n\n"
            "\n===== 搜索到的写作规范（请严格遵循） =====\n" + (json.dumps(standards_info, ensure_ascii=False, indent=2) if standards_info else "") + "\n===== 规范结束 =====\n"
            f"===== 代码资料 =====\n{mat_preview}\n===== 资料结束 ====="
        )
        prompt = f"请基于上次文档，根据反馈逐一修改问题部分，输出完整的《{doc_type}》Markdown 文档。"
    else:
        system_prompt = (
            "你是一位资深软件架构师，擅长编写专业的软件设计文档。\n\n"
            f"请根据大纲和项目代码资料，撰写完整的《{doc_type}》Markdown 文档。\n\n"
            "**写作要求：**\n"
            "0. 禁止描述代码：不得提及任何文件名或文件路径，不得贴代码片段，不得逐行解说代码——项目代码仅用于提炼架构和设计意图，文档中只写设计，不写代码是什么\n"
            "1. 严格按大纲章节结构组织全文\n"
            "2. 总体架构设计章：描述系统分层和模块分割，插入 Mermaid 架构图（```mermaid）\n"
            "3. 构件设计章：详细描述各模块职责、核心类的属性和方法、关键算法、错误处理，"
            "插入 Mermaid 流程图\n"
            "4. 接口设计章（如大纲包含）：明确接口名称、请求/响应格式、参数类型、序列化方案和异常处理\n"
            "5. 数据设计章（如大纲包含）：核心数据结构定义（字段/类型/约束）、数据字典和模块间数据流转\n"
            "6. 数据库设计章（如大纲包含）：数据库选型理由、ER 关系（Mermaid erDiagram）、"
            "核心表结构（字段名/类型/主键/外键/索引）\n"
            "7. 大纲中没有的章节一律不写，不得自行添加\n"
            "8. 所有设计描述必须与代码一致，严禁编造、猜测、虚构代码中不存在的任何设计元素\n"
            "9. 所有专业术语首次出现时给出全称\n"
            "10. 输出纯 Markdown，不要额外解释\n\n"
            f"===== 文档大纲 =====\n{sections_desc}\n===== 大纲结束 =====\n\n"
            "\n===== 搜索到的写作规范（请严格遵循） =====\n" + (json.dumps(standards_info, ensure_ascii=False, indent=2) if standards_info else "") + "\n===== 规范结束 =====\n"
            f"===== 代码资料 =====\n{mat_preview}\n===== 资料结束 ====="
        )
        prompt = f"请生成完整的《{doc_type}》Markdown 文档，从 `# {doc_type}` 开始。"

    result = call_deepseek(system_prompt, prompt, temperature=0.4, max_tokens=8000)
    return _clean_document(result)


def _score_document(document: str, material: str, doc_type: str) -> dict:
    """评分设计文档"""
    doc_preview = document
    mat_preview = material

    system_prompt = (
        "你是一位软件设计文档审核专家。请对以下设计文档进行质量评分。\n\n"
        "评分维度（各占 2 分，满分 10 分）：\n"
        "1. 完整性(2分)：是否覆盖大纲中定义的所有章节，代码中没有的部分不算缺漏\n"
        "2. 准确性(2分)：设计描述是否与代码一致。如果文档出现代码中不存在的架构、接口、数据结构（即编造），该维度直接 0 分\n"
        "3. 结构性(2分)：章节组织是否合理、架构描述是否清晰\n"
        "4. 可读性(2分)：语言是否清晰、术语是否统一\n"
        "5. 格式规范(2分)：是否包含三个 Mermaid 图、Markdown 格式是否正确\n\n"
        "返回纯 JSON：\n"
        '{"score": <总分>, "feedback": "<具体反馈>", '
        '"dimensions": {"completeness": <>, "accuracy": <>, "structure": <>, "readability": <>, "format": <>}}\n\n'
        f"===== 代码资料 =====\n{mat_preview}\n===== 结束 =====\n\n"
        f"===== 待评分文档 =====\n{doc_preview}\n===== 结束 ====="
    )

    raw = call_deepseek(system_prompt, "请评分。", temperature=0.2, max_tokens=4096, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"score": 5, "feedback": raw, "dimensions": {}}


def _check_code_consistency(document: str, material: str) -> dict:
    """检查设计文档与代码的一致性"""
    doc_preview = document
    mat_preview = material

    system_prompt = (
        "你是一位代码审查专家。请检查设计文档中的技术描述是否与项目代码一致。\n\n"
        "检查要点：\n"
        "1. 架构描述（分层、模块划分）是否与代码组织结构一致\n"
        "2. 文档中提到的模块、类、接口是否在代码中有对应实现\n"
        "3. 数据结构描述是否与代码中的类/结构体定义一致\n"
        "4. 数据存储设计是否与代码中的存储实现一致\n\n"
        "5. 是否存在文档描述了但代码中不存在的内容——即编造或虚构的设计元素\n\n"
        "返回纯 JSON：\n"
        '{"is_aligned": <true/false>, "issues": "<不一致的具体问题>", '
        '"suggestions": "<修复建议>"}\n\n'
        f"===== 代码资料 =====\n{mat_preview}\n===== 结束 =====\n\n"
        f"===== 设计文档 =====\n{doc_preview}\n===== 结束 ====="
    )

    raw = call_deepseek(system_prompt, "请检查一致性。", temperature=0.2, max_tokens=4096, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"is_aligned": True, "issues": raw, "suggestions": ""}


# ================= Agent 状态 =================

class AgentState:
    """Agent 状态容器"""
    def __init__(self):
        self.outline: dict | None = None
        self.document: str | None = None
        self.score: float = 0
        self.feedback: str = ""
        self.dimensions: dict = {}
        self.is_aligned: bool = True
        self.alignment_issues: str = ""
        self.rewrite_count: int = 0
        self.finished: bool = False
        self.summary: str = ""
        self.standards_info: dict = {}


# ================= Agent 执行引擎 =================

def run_agent(material: str, doc_type: str) -> AgentState:
    """
    Agent 模式运行设计文档生成。
    流程：搜索规范→大纲→生成→评分→代码一致性检查→条件重写→完成。
    """
    st = AgentState()

    system_prompt = (
        "你是一个软件设计文档生成 Agent。\n\n**核心铁律：** 所有设计文档内容必须严格基于用户提供的项目代码资料，\n严禁编造、猜测、虚构代码中不存在的架构、模块、接口、数据结构、数据库设计。\n如果代码中找不到某个信息，不得自行补充。\n\n你必须严格按顺序调用工具完成设计文档生成。\n\n"
        "**执行顺序（不可跳过）：**\n"
        f"1. search_writing_standards — 搜索设计文档写作规范\n"
        f"2. generate_outline(focus_areas=[...]) — 根据规范和代码生成大纲\n"
        f"3. generate_document — 根据大纲生成完整设计文档\n"
        f"4. score_document — 对文档评分\n"
        f"5. check_code_consistency — 检查文档与代码是否一致\n"
        f"6. 如果评分 < {PASS_SCORE} 或 is_aligned == false："
        f"调用 rewrite_document 重写，回到步骤 4\n"
        f"7. 如果评分 >= {PASS_SCORE} 且 is_aligned == true，或 rewrite_count == {MAX_REWRITES}："
        f"调用 finish\n\n"
        "每次只调用一个工具，等待结果后再执行下一步。"
    )

    user_prompt = (
        f"请为以下项目代码生成《{doc_type}》。\n\n"
        f"===== 项目代码资料 =====\n{material[:10000]}\n===== 资料结束 ====="
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    for iteration in range(1, 25):
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
                    print("    ... 正在生成设计文档大纲 ...")
                    st.outline = _generate_outline(material, doc_type, args.get("focus_areas", []), st.standards_info)
                    n = len(st.outline.get("sections", []))
                    result_str = json.dumps({"status": "ok", "section_count": n}, ensure_ascii=False)

                elif name == "generate_document":
                    if st.outline is None:
                        result_str = json.dumps({"error": "请先生成大纲"})
                    else:
                        print("    ... 正在生成设计文档全文 ...")
                        st.document = _generate_document_text(material, st.outline, doc_type, standards_info=st.standards_info)
                        result_str = json.dumps({"status": "ok", "length": len(st.document)}, ensure_ascii=False)

                elif name == "score_document":
                    if st.document is None:
                        result_str = json.dumps({"error": "请先生成文档"})
                    else:
                        print("    ... 正在评分设计文档 ...")
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

                elif name == "check_code_consistency":
                    if st.document is None:
                        result_str = json.dumps({"error": "请先生成文档"})
                    else:
                        print("    ... 正在检查代码一致性 ...")
                        check_data = _check_code_consistency(st.document, material)
                        st.is_aligned = check_data.get("is_aligned", True)
                        st.alignment_issues = check_data.get("issues", "")
                        print(f"    [一致性] 与代码一致: {st.is_aligned}")
                        if st.alignment_issues:
                            print(f"    [不一致问题] {st.alignment_issues}")
                        result_str = json.dumps(check_data, ensure_ascii=False)

                elif name == "rewrite_document":
                    if st.rewrite_count >= MAX_REWRITES:
                        result_str = json.dumps({"error": f"已达最大重写次数 {MAX_REWRITES}，请调用 finish"})
                    elif st.outline is None:
                        result_str = json.dumps({"error": "缺少大纲"})
                    else:
                        st.rewrite_count += 1
                        print(f"    ... 第 {st.rewrite_count} 次重写 ...")
                        combined_feedback = args.get("feedback", "")
                        if not combined_feedback:
                            parts = [st.feedback]
                            if not st.is_aligned:
                                parts.append(f"代码一致性问题: {st.alignment_issues}")
                            combined_feedback = "; ".join(filter(None, parts))
                        prev_doc = st.document or ""
                        st.document = _generate_document_text(material, st.outline, doc_type, combined_feedback, prev_doc, st.standards_info)
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
            messages.append(assistant_msg)
            if st.document and st.score > 0 and not st.is_aligned:
                # 已检查过一致性，发现问题
                need_rewrite = (
                    st.score < PASS_SCORE or (not st.is_aligned)
                ) and st.rewrite_count < MAX_REWRITES
                if need_rewrite:
                    messages.append({
                        "role": "user",
                        "content": f"评分 {st.score}/10，代码一致性检查发现不一致。请调用 rewrite_document。"
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": f"评分 {st.score}/10，已达质量要求。请调用 finish。"
                    })
            elif st.document and st.score > 0:
                need_rewrite = st.score < PASS_SCORE and st.rewrite_count < MAX_REWRITES
                if need_rewrite:
                    messages.append({
                        "role": "user",
                        "content": f"评分 {st.score}/10，未达标。请调用 rewrite_document。"
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": f"评分 {st.score}/10，达标。下一步请调用 check_code_consistency。"
                    })
            elif st.outline and not st.document:
                messages.append({"role": "user", "content": "大纲已就绪，请调用 generate_document。"})
            elif not st.outline:
                messages.append({"role": "user", "content": "请先调用 search_writing_standards。"})

    return st


# ================= 公开接口（签名不变） =================

def generate_design_for_topic(material_file: str, output_md: str, doc_type: str = "软件设计文档"):
    """
    为单个主题生成软件设计文档（Agent 模式）。
    
    后端 import 调用的入口函数，签名与旧版完全一致。
    """
    print(f"\n{'=' * 50}")
    print(f"... 开始生成：{doc_type}（素材：{material_file}）")

    material = load_material(material_file)
    print(f"   素材长度：{len(material)} 字符")

    st = run_agent(material, doc_type)

    if st.outline:
        outline_path = output_md.replace(".md", "_outline.json")
        with open(outline_path, "w", encoding="utf-8") as f:
            json.dump(st.outline, f, ensure_ascii=False, indent=2)
        print(f"... 大纲已保存至 {outline_path}")

    if st.document:
        with open(output_md, "w", encoding="utf-8") as f:
            f.write(st.document)
        print(f"... 文档已生成：{output_md}")
        print(f"   最终评分：{st.score}/10 | 代码一致：{st.is_aligned} | 重写次数：{st.rewrite_count}")
    else:
        raise RuntimeError("Agent 未生成文档")

    if st.feedback:
        print(f"   评分反馈：{st.feedback}...")
    if st.alignment_issues:
        print(f"   一致性问题：{st.alignment_issues}...")


# ================= 主入口 =================
if __name__ == "__main__":
    tasks = [
        {
            "material_file": "material_example.txt",
            "output_md": "软件设计文档.md",
            "doc_type": "软件设计文档"
        }
    ]

    missing = [t["material_file"] for t in tasks if not os.path.exists(t["material_file"])]
    if missing:
        print("以下素材文件未找到，请准备好后再运行：")
        for f in missing:
            print(f"   - {f}")
        exit(1)

    for task in tasks:
        generate_design_for_topic(
            material_file=task["material_file"],
            output_md=task["output_md"],
            doc_type=task["doc_type"]
        )

    print("\n... 所有文档生成完毕！")
