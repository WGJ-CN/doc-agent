import openai
import json
import os

# ================= 配置 =================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

client = openai.OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)


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


# ================= 阶段1：生成大纲（软件设计文档专用） =================
def generate_outline(material: str, doc_type: str = "软件设计文档") -> dict:
    """
    从原始素材抽取大纲，根据 doc_type 微调章节重点。
    软件设计文档固定章节：
      1.引言  2.总体架构设计  3.构件设计  4.接口设计
      5.数据设计  6.数据库设计  附录
    """
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
        {"id": "6", "title": "6. 数据库设计",
         "points": [
             "数据库选型与理由",
             "ER 图或表关系描述（Mermaid erDiagram）",
             "核心表结构设计（字段名、类型、主键、外键、索引）",
             "分库分表或读写分离策略（如适用）"
         ]},
        {"id": "appendix", "title": "附录",
         "points": ["关键类图或序列图（Mermaid 格式）", "配置项说明", "性能与安全设计方案补充"]}
    ]

    system_prompt = (
        "你是一位资深软件架构师。请根据提供的项目资料，生成《" + doc_type + "》的详细大纲。\n"
        "资料可能包含代码片段，请从中逆向提取系统架构、模块划分、接口、数据结构和数据库设计信息，作为设计依据。\n"
        "大纲需要体现以下要求：\n"
        "1. 总体架构设计部分必须明确系统分层和模块分割方案，不能只并列列出模块名称。\n"
        "2. 文档需包含至少三个 Mermaid 图：一个架构图（第2章）、一个流程图（第3章）、一个 ER 图（第6章）。\n"
        "3. 章节结构固定为：1.引言 2.总体架构设计 3.构件设计 4.接口设计 5.数据设计 6.数据库设计 附录。\n"
        "4. 构件设计（第3章）需覆盖核心模块的内部结构、类/组件设计、关键算法和错误处理。\n"
        "5. 数据设计（第5章）需描述核心数据结构和模块间数据流转。\n"
        "6. 数据库设计（第6章）需包含表结构设计和 ER 关系。\n"
        "7. 每个章节的要点需要具体、可执行，不要泛泛而谈。\n"
        "8. 请在 JSON 中输出大纲对象，格式为：\n"
        "   {\n"
        '     "doc_type": "文档标题",\n'
        '     "sections": [\n'
        '       {"id": "章节编号", "title": "章节标题", "points": ["要点1", "要点2", ...]}\n'
        "     ]\n"
        "   }\n"
        "9. 仅输出 JSON，不要包含其他文字。"
    )
    user_prompt = (
        f"===== 章节模板（供参考，请根据资料微调） =====\n"
        f"{json.dumps(default_sections, ensure_ascii=False, indent=2)}\n"
        f"===== 模板结束 =====\n\n"
        f"===== 项目资料 =====\n{material}\n===== 资料结束 ====="
    )

    print("🔍 正在生成大纲...")
    raw = call_deepseek(system_prompt, user_prompt, json_mode=True)
    try:
        outline = json.loads(raw)
    except json.JSONDecodeError:
        print("⚠️ JSON 解析失败，使用默认大纲")
        outline = {"doc_type": doc_type, "sections": default_sections}
    print("✅ 大纲生成完毕")
    return outline


def build_sections_description(outline: dict) -> str:
    """将大纲字典转为可读的章节描述文本"""
    lines = []
    sections = outline.get("sections", [])
    for i, sec in enumerate(sections):
        sec_id = sec.get("id", str(i + 1))
        title = sec.get("title", f"章节{sec_id}")
        points = sec.get("points", [])
        lines.append(f"## {title}")
        for pt in points:
            lines.append(f"  - {pt}")
        lines.append("")
    return "\n".join(lines)


# ================= 阶段2：生成全文（软件设计文档） =================
def generate_full_design(material: str, outline: dict, doc_type: str = "软件设计文档") -> str:
    """
    根据大纲 + 原始素材，生成完整的软件设计文档 Markdown。
    """
    sections_desc = build_sections_description(outline)

    system_prompt = (
        "你是一位资深软件架构师，擅长编写专业的软件设计文档。\n\n"
        "请根据提供的大纲和项目资料，撰写完整的《" + doc_type + "》Markdown 文档。\n\n"
        "**写作要求：**\n"
        "1. 严格按照大纲的章节结构组织全文，使用大纲中指定的章节标题。\n"
        "2. **第2章 总体架构设计**：必须描述系统分层架构和模块分割方案，"
        "说明模块间依赖关系，并插入一个 Mermaid 架构图（用 ```mermaid 代码块包裹）。\n"
        "3. **第3章 构件设计**：必须详细描述每个构件/模块的职责、内部结构、"
        "核心类/组件的关键属性和方法、关键算法流程、错误处理策略，"
        "并插入一个 Mermaid 流程图（用 ```mermaid 代码块包裹）。\n"
        "4. **第4章 接口设计**：必须明确接口名称、请求/响应格式、参数类型、"
        "序列化方案和异常处理方式。\n"
        "5. **第5章 数据设计**：必须描述核心数据结构定义（含字段、类型、约束）、"
        "数据字典和模块间数据流转关系。\n"
        "6. **第6章 数据库设计**：必须包含数据库选型理由、ER 关系描述（插入 Mermaid erDiagram）、"
        "核心表结构（字段名、类型、主键、外键、索引），"
        "如资料涉及分库分表或读写分离需一并说明。\n"
        "7. 所有专业术语首次出现时给出全称，全文统一。\n"
        "8. 只使用资料中存在的设计信息和代码逻辑，不编造新功能；"
        "如果资料中有代码，提取其隐含的设计意图和架构模式，不要直接复制代码细节。\n"
        "9. 附录中的类图、序列图等必须与正文设计逻辑一致。\n"
        "10. 输出纯 Markdown 格式，不要包含额外解释语句。\n\n"
        f"===== 文档大纲 =====\n{sections_desc}\n===== 大纲结束 =====\n\n"
        f"===== 项目资料 =====\n{material}\n===== 资料结束 ====="
    )
    user_prompt = (
        "请现在生成完整的《" + doc_type + "》Markdown 文档，"
        "从 `# " + doc_type + "` 开始。"
    )

    print("📝 正在生成全文（预计 1~2 分钟）...")
    full_md = call_deepseek(system_prompt, user_prompt,
                            temperature=0.4, max_tokens=8000)
    return full_md


# ================= 单文档生成任务 =================
def generate_design_for_topic(material_file: str, output_md: str, doc_type: str = "软件设计文档"):
    """
    为单个主题生成软件设计文档（完整流程：加载素材 → 大纲 → 全文）
    这是后端 import 调用的入口函数。

    参数：
        material_file: 素材文件路径（txt/md）
        output_md: 输出 Markdown 文件路径
        doc_type: 文档类型名称（默认"软件设计文档"）
    """
    print(f"\n{'=' * 50}")
    print(f"📋 开始生成：{doc_type}（素材：{material_file}）")

    # 1. 加载素材
    material = load_material(material_file)
    print(f"   素材长度：{len(material)} 字符")

    # 2. 阶段1：大纲
    outline = generate_outline(material, doc_type)
    outline_path = output_md.replace(".md", "_outline.json")
    with open(outline_path, "w", encoding="utf-8") as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)
    print(f"📁 大纲已保存至 {outline_path}")

    # 3. 阶段2：全文
    design_content = generate_full_design(material, outline, doc_type)

    # 4. 保存
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(design_content)
    print(f"✅ 文档已生成：{output_md}")


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
        print("❌ 以下素材文件未找到，请准备好后再运行：")
        for f in missing:
            print(f"   - {f}")
        exit(1)

    for task in tasks:
        generate_design_for_topic(
            material_file=task["material_file"],
            output_md=task["output_md"],
            doc_type=task["doc_type"]
        )

    print("\n🎉 所有文档生成完毕！")

