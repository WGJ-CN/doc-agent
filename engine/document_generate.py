import openai
import json
import os

# ================= 配置 =================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 初始化客户端
client = openai.OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)


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


# ================= 阶段1：生成大纲（通用） =================
def generate_outline(material: str, doc_type: str = "需求规格说明书") -> dict:
    """
    从原始素材抽取大纲，根据 doc_type 微调章节重点。
    """
    # 精简章节模板（4章+附录）
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

    system_prompt = (
            "你是一位软件需求分析师。请根据提供的项目资料，生成《" + doc_type + "》的详细大纲。\n"
                                                                             "资料可能包含代码片段，请从中逆向提取业务规则和功能逻辑，作为需求依据。\n"
                                                                             "大纲需要体现以下要求：\n"
                                                                             "1. 功能需求部分必须明确强调业务流程的先后顺序和条件依赖，不能只列并列功能点。\n"
                                                                             "   建议在要点中注明“流程步骤：第一步...第二步...”或“决策树顺序”。\n"
                                                                             "2. 文档需包含至少一个流程图（Mermaid格式），请在功能需求或附录的要点中注明‘插入Mermaid流程图’。\n"
                                                                             "3. 章节结构固定为：1.引言 2.功能需求 3.数据需求 4.接口需求 附录。\n"
                                                                             "4. 每个章节的要点需要具体、可执行，不要泛泛而谈。\n"
                                                                             "5. 请在 JSON 中输出大纲对象，格式为：\n"
                                                                             "   {\n"
                                                                             "     \"sections\": [ 每个章节对象包含 id, title, points 数组 ]\n"
                                                                             "   }\n"
                                                                             "6. 不要输出任何额外解释。\n"
                                                                             f"\n\n===== 项目资料 =====\n{material}\n===== 资料结束 ====="
    )
    user_prompt = "请生成大纲 JSON。"

    raw = call_deepseek(system_prompt, user_prompt,
                        temperature=0.2, max_tokens=2048, json_mode=True)
    try:
        outline = json.loads(raw)
        print("✅ 大纲生成成功")
        return outline
    except json.JSONDecodeError:
        print("⚠️ 大纲解析失败，使用默认大纲")
        return {"sections": default_sections}


# ================= 阶段2：生成全文（通用） =================
def generate_full_srs(material: str, outline: dict, doc_type: str = "需求规格说明书") -> str:
    """根据大纲和原始资料生成完整文档，强调顺序逻辑和Mermaid图"""
    # 将大纲整理成文本描述
    sections_desc = ""
    for sec in outline.get("sections", []):
        points_str = "；".join(sec["points"])
        sections_desc += f"- {sec['title']}：{points_str}\n"

    system_prompt = (
            "你是一位专业的软件文档撰写人。请根据大纲和项目资料，撰写一份完整、规范的《" + doc_type + "》。\n\n"
                                                                                                  "写作规则：\n"
                                                                                                  "1. 严格按大纲章节顺序输出，章节标题使用 `##`。\n"
                                                                                                  "2. 第2章（功能需求）的核心流程必须使用顺序化、步骤化的描述方式，例如：\n"
                                                                                                  "   - 首先，系统应检查...；若满足，则...并结束流程。\n"
                                                                                                  "   - 其次，若不满足，系统应依据...确定...\n"
                                                                                                  "   - 不要使用并列的 FR-001、FR-002 罗列一个决策树中的同级步骤，\n"
                                                                                                  "     而应将整个决策流程作为一个功能整体，分步骤说明，或对顺序条件明确标注。\n"
                                                                                                  "3. 在第2章或附录中，必须插入一个 Mermaid 流程图（用 ```mermaid 代码块包裹），\n"
                                                                                                  "   描述核心业务流程（如入组决策路径或文档生成流程），确保语法正确。\n"
                                                                                                  "4. 所有专业术语首次出现时给出全称，全文统一。\n"
                                                                                                  "5. 数据需求（第3章）必须覆盖功能需求中涉及的所有输入/输出数据字段。\n"
                                                                                                  "6. 附录中的示例或图示必须与功能需求逻辑一致。\n"
                                                                                                  "7. 只使用资料中存在的业务规则和代码逻辑，不编造新功能；\n"
                                                                                                  "   如果资料中有代码，提取其隐含的业务规则，不要直接复制代码细节。\n"
                                                                                                  "8. 输出纯 Markdown 格式，不要包含额外解释语句。\n\n"
                                                                                                  f"===== 文档大纲 =====\n{sections_desc}\n===== 大纲结束 =====\n\n"
                                                                                                  f"===== 项目资料 =====\n{material}\n===== 资料结束 ====="
    )
    user_prompt = (
            "请现在生成完整的《" + doc_type + "》Markdown 文档，"
                                             "从 `# " + doc_type + "` 开始。"
    )

    print("⏳ 正在生成全文（预计 1~2 分钟）...")
    full_md = call_deepseek(system_prompt, user_prompt,
                            temperature=0.4, max_tokens=8000)
    return full_md


# ================= 单文档生成任务 =================
def generate_srs_for_topic(material_file: str, output_md: str, doc_type: str = "需求规格说明书"):
    """
    为单个主题生成文档（完整流程）
    """
    print(f"\n{'=' * 50}")
    print(f"📘 开始生成：{doc_type}（素材：{material_file}）")

    # 1. 加载素材
    material = load_material(material_file)
    print(f"   素材长度：{len(material)} 字符")

    # 2. 阶段1：大纲
    outline = generate_outline(material, doc_type)
    outline_path = output_md.replace('.md', '_outline.json')
    with open(outline_path, 'w', encoding='utf-8') as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)
    print(f"📋 大纲已保存至 {outline_path}")

    # 3. 阶段2：全文
    srs_content = generate_full_srs(material, outline, doc_type)

    # 4. 保存
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(srs_content)
    print(f"✅ 文档已生成：{output_md}")


# ================= 主入口 =================
if __name__ == "__main__":
    # 定义要生成的两份文档
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

    # 检查素材文件是否存在
    missing = [t["material_file"] for t in tasks if not os.path.exists(t["material_file"])]
    if missing:
        print("❌ 以下素材文件未找到，请准备好后再运行：")
        for f in missing:
            print(f"   - {f}")
        exit(1)

    # 依次生成
    for task in tasks:
        generate_srs_for_topic(
            material_file=task["material_file"],
            output_md=task["output_md"],
            doc_type=task["doc_type"]
        )

    print("\n🎉 所有文档生成完毕！")
