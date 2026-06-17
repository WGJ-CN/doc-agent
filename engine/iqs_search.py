"""
阿里云 IQS 信息查询服务 — 搜索和网页解析工具
供 document_generate.py 和 document_design_generate.py 共用

API 参考：
  搜索：POST https://cloud-iqs.aliyuncs.com/search/unified
  解析：POST https://cloud-iqs.aliyuncs.com/readpage/basic
  认证：Authorization: Bearer <API_KEY>
"""
import json
import time
import urllib.request
import urllib.error

# ================= 配置 =================
IQS_API_KEY = "XEjwVWXnXE9YjaEESBJVkWgRZrgETfI2YTMxZWU0NA"  # TODO: 替换为实际 API Key
IQS_SEARCH_URL = "https://cloud-iqs.aliyuncs.com/search/unified"
IQS_READPAGE_URL = "https://cloud-iqs.aliyuncs.com/readpage/basic"
SEARCH_NUM_RESULTS = 5
READPAGE_MAX_AGE = 30  # 缓存天数


def _iqs_request(url: str, body: dict, timeout: int = 30) -> dict:
    """发送 IQS API 请求"""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {IQS_API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  [IQS HTTP {e.code}] {err_body[:300]}")
        return {"error": f"HTTP {e.code}", "detail": err_body[:500]}
    except Exception as e:
        print(f"  [IQS 请求失败] {e}")
        return {"error": str(e)}


def search(query: str, num_results: int = SEARCH_NUM_RESULTS) -> dict:
    """
    调用 IQS 通用搜索 API。
    返回：{"results": [{"title": ..., "url": ..., "text": ..., "score": ...}, ...]}
    """
    print(f"  [IQS 搜索] {query[:80]}...")

    body = {
        "query": query,
        "engineType": "LiteAdvanced",
        "contents": {
            "mainText": True,
            "markdownText": False,
            "summary": True,
            "rerankScore": True
        },
        "advancedParams": {
            "numResults": num_results
        }
    }

    resp = _iqs_request(IQS_SEARCH_URL, body)

    if "error" in resp:
        return resp

    # 响应格式: {"pageItems": [...], "sceneItems": [...], ...}
    items = resp.get("pageItems", []) or resp.get("data", {}).get("pageItems", [])

    results = []
    for item in items:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("link", "") or item.get("url", ""),
            "text": item.get("mainText", "") or item.get("snippet", ""),
            "summary": item.get("summary", ""),
            "score": item.get("rerankScore", 0),
            "hostname": item.get("hostname", "")
        })

    print(f"  [IQS 搜索] 返回 {len(results)} 条结果")
    return {"results": results}


def read_page(url: str, max_age: int = READPAGE_MAX_AGE) -> dict:
    """
    调用 IQS 网页解析 API，获取网页可读内容。
    返回：{"title": ..., "content": ..., "url": ...}
    """
    print(f"  [IQS 解析] {url[:80]}...")

    body = {
        "url": url,
        "maxAge": max_age
    }

    resp = _iqs_request(IQS_READPAGE_URL, body)

    if "error" in resp:
        return {"title": "", "content": "", "url": url, "error": resp["error"]}

    # 响应格式: {"requestId": ..., "data": {"statusCode": 200, "html": "...", "metadata": {...}}}
    data = resp.get("data", resp)
    html_content = data.get("html", "") or data.get("rawHtml", "") or ""
    metadata = data.get("metadata", {})

    return {
        "title": metadata.get("title", "") or data.get("title", ""),
        "content": _strip_html(html_content),
        "url": url
    }


def _strip_html(html_text: str) -> str:
    """简单去除 HTML 标签，提取纯文本"""
    import re
    # 移除 script/style 标签及其内容
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 合并空白
    text = re.sub(r'\s+', ' ', text)
    # 解码常见 HTML 实体
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    return text.strip()


def search_standards(doc_type: str, keywords: list[str]) -> dict:
    """
    搜索文档写作规范：先搜索，再解析 top 结果页面。

    doc_type: "requirements" (需求) 或 "design" (设计)
    keywords: 搜索关键词列表

    返回包含标准参考信息的 dict，供 Agent tool handler 使用
    """
    # 构建搜索词
    if doc_type == "requirements":
        base_query = "软件需求规格说明书 引言 功能需求 数据需求 接口需求 如何编写 每章内容要求 格式规范 写作要点"
    else:
        base_query = "软件设计文档 引言 总体架构 构件设计 接口设计 数据设计 数据库设计 每个章节 编写指南 内容要求 格式规范"

    kw_str = " ".join(keywords) if keywords else ""
    query = f"{base_query} {kw_str}".strip()

    # 第一步：搜索
    search_result = search(query)

    if "error" in search_result:
        return _fallback_standards(doc_type)

    results = search_result.get("results", [])
    if not results:
        return _fallback_standards(doc_type)

    # 第二步：解析 top 2 结果页面获取详细内容
    parsed_pages = []
    for r in results[:2]:
        url = r.get("url", "")
        if url:
            page = read_page(url)
            content = page.get("content", "")
            if content:
                parsed_pages.append({
                    "title": page.get("title") or r.get("title", ""),
                    "url": url,
                    "content": content[:3000]
                })
            time.sleep(0.5)

    # 构建返回结果
    all_snippets = []
    for r in results:
        text = r.get("text", "") or r.get("summary", "")
        if text:
            all_snippets.append(f"### {r.get('title', '')}\n{text[:1000]}\n来源: {r.get('hostname', '')}")

    parsed_texts = []
    for p in parsed_pages:
        parsed_texts.append(f"### [解析] {p['title']}\n{p['content']}")

    return {
        "search_query": query,
        "search_results_count": len(results),
        "search_snippets": "\n\n".join(all_snippets) if all_snippets else "无搜索摘要",
        "parsed_pages_count": len(parsed_pages),
        "parsed_content": "\n\n---\n\n".join(parsed_texts) if parsed_texts else "",
        "standards_summary": _build_standards_summary(doc_type)
    }


def _fallback_standards(doc_type: str) -> dict:
    """搜索失败时的兜底标准信息"""
    if doc_type == "requirements":
        return {
            "standards": [
                {"name": "IEEE 830-1998", "title": "IEEE Recommended Practice for SRS"},
                {"name": "GB/T 9385-2008", "title": "计算机软件需求规格说明规范"},
                {"name": "GB/T 8567-2006", "title": "计算机软件文档编制规范"}
            ],
            "fallback": True,
            "search_results_count": 0
        }
    else:
        return {
            "standards": [
                {"name": "IEEE 1016-2009", "title": "IEEE Standard for Software Design Descriptions"},
                {"name": "GB/T 8567-2006", "title": "计算机软件文档编制规范 - 软件设计说明"}
            ],
            "fallback": True,
            "search_results_count": 0
        }


def _build_standards_summary(doc_type: str) -> str:
    """构建各章节写作规范摘要（嵌入搜索结果返回给 Agent）"""
    if doc_type == "requirements":
        return (
            "需求文档各章节编写要点：\n"
            "1.引言：明确编写目的、读者对象、术语定义、参考资料\n"
            "2.功能需求：按业务流程顺序描述，使用步骤化语言（第一步...第二步...），体现决策分支和条件依赖，避免FR-001并列罗列\n"
            "3.数据需求：列出所有输入输出数据的字段名、类型、约束、取值范围\n"
            "4.接口需求：描述与外部系统的交互协议、API端点、请求/响应格式、状态码\n"
            "附录：补充Mermaid流程图源码、示例数据、关键图示\n"
            "通用：专业术语首次出现给出全称并统一，所有描述必须基于素材不编造"
        )
    else:
        return (
            "设计文档各章节编写要点：\n"
            "1.引言：编写目的、术语定义、设计依据\n"
            "2.总体架构设计：系统分层描述（表现层/业务层/数据层），模块分割方案及依赖关系，技术选型理由，附Mermaid架构图\n"
            "3.构件设计：各模块职责、核心类的属性方法（不贴代码，描述设计意图）、关键算法流程、错误处理策略，附Mermaid流程图\n"
            "4.接口设计：接口名称、请求响应格式、参数类型、序列化方案、异常处理与状态码\n"
            "5.数据设计：核心数据结构定义（字段/类型/约束）、数据字典、模块间数据流转\n"
            "6.数据存储设计：存储方案选型理由，数据库则含ER图和表结构，内存/文件则描述存储结构和读写机制\n"
            "附录：类图/序列图(Mermaid)、配置说明、性能安全方案\n"
            "通用：所有描述基于代码提炼设计意图，不描述代码本身，不提及文件名"
        )
