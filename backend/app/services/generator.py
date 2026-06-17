import asyncio
import os
import re
import sys
import threading
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# ---------- 进度推送基础设施 ----------
_progress_buffers: dict[str, list] = {}
_buffers_lock = threading.Lock()


def _push_progress(task_id, step, tool, status="running", detail=None):
    """线程安全地把进度事件追加到回放缓冲区"""
    with _buffers_lock:
        buf = _progress_buffers.get(task_id)
    if buf is not None:
        event = {"step": step, "tool": tool, "status": status}
        if detail:
            event["detail"] = detail
        buf.append(event)


_TOOL_PATTERN = re.compile(r'\[调用工具\]\s*(\w+)')

_STEP_MAP = {
    "search_writing_standards": "searching",
    "generate_outline":          "outline",
    "generate_document":         "writing",
    "score_document":            "scoring",
    "rewrite_document":          "rewriting",
    "check_code_consistency":    "consistency",
    "finish":                    "done",
}

_SEARCH_RESULT = re.compile(r'\[搜索规范\]\s*找到\s*(\d+)\s*条结果.*解析\s*(\d+)\s*个页面')
_SCORE_RESULT = re.compile(r'\[评分\]\s*(\d+)/10')
_SCORE_DIMS = re.compile(r'完整性:(.+?)\s+准确性:(.+?)\s+结构性:(.+?)\s+可读性:(.+?)\s+格式:(.+)')
_REWRITE_RESULT = re.compile(r'第\s*(\d+)\s*次重写')
_CONSISTENCY_RESULT = re.compile(r'\[一致性\]\s*与代码一致:\s*(True|False)')
_FINAL_SCORE = re.compile(r'最终评分：(\d+)/10.*重写次数：(\d+)')
_FINAL_SCORE_DESIGN = re.compile(r'最终评分：(\d+)/10.*代码一致：(True|False).*重写次数：(\d+)')


def _make_progress_writer(task_id, original_write):
    """返回 (write_fn, flush_fn)"""
    state = {"current_step": None}

    def _flush():
        if state["current_step"]:
            _push_progress(task_id, state["current_step"], state["current_step"], status="done")
            state["current_step"] = None

    def _try_detail(s, cur):
        m = _SEARCH_RESULT.search(s)
        if m:
            return f"找到 {m.group(1)} 条标准，解析 {m.group(2)} 个页面"
        m = _SCORE_RESULT.search(s)
        if m:
            return f"评分 {m.group(1)}/10"
        m = _SCORE_DIMS.search(s)
        if m:
            return f"完整:{m.group(1)} 准确:{m.group(2)} 结构:{m.group(3)} 可读:{m.group(4)} 格式:{m.group(5)}"
        m = _REWRITE_RESULT.search(s)
        if m:
            return f"第 {m.group(1)} 次重写"
        m = _CONSISTENCY_RESULT.search(s)
        if m:
            return f"代码一致: {m.group(1)}"
        return None

    def write(s):
        original_write(s)

        m = _TOOL_PATTERN.search(s)
        if m:
            tool_name = m.group(1)
            step = _STEP_MAP.get(tool_name, tool_name)
            if tool_name == "finish":
                _flush()
                return
            if state["current_step"] and state["current_step"] != step:
                _flush()
            state["current_step"] = step
            _push_progress(task_id, step, tool_name, status="running")
            return

        if not state["current_step"]:
            fm = _FINAL_SCORE_DESIGN.search(s) or _FINAL_SCORE.search(s)
            if fm:
                groups = fm.groups()
                if len(groups) == 3:
                    detail = f"最终评分 {groups[0]}/10 | 代码一致 {groups[1]} | 重写 {groups[2]} 次"
                else:
                    detail = f"最终评分 {groups[0]}/10 | 重写 {groups[1]} 次"
                _push_progress(task_id, "done", "done", status="running", detail=detail)
            return

        detail = _try_detail(s, state["current_step"])
        if detail:
            _push_progress(task_id, state["current_step"], state["current_step"], status="running", detail=detail)

    return write, _flush


# ---------- 引擎导入 ----------
sys.path.insert(0, settings.engine_dir)
from document_generate import generate_srs_for_topic
from document_design_generate import generate_design_for_topic
from testcase_generate import generate_testcase_for_topic
from project_scanner import scan_project


def run_with_progress(task_id, material, doc_type, project_path=None, full_doc_name=None):
    original_write = sys.stdout.write
    write_fn, flush_fn = _make_progress_writer(task_id, original_write)
    sys.stdout.write = write_fn
    try:
        return DocumentGenerator.run(
            task_id=task_id,
            material=material,
            doc_type=doc_type,
            project_path=project_path,
            full_doc_name=full_doc_name,
        )
    finally:
        sys.stdout.write = original_write
        flush_fn()
        _push_progress(task_id, "done", "done", status="done")


class DocumentGenerator:
    """文档生成器 - 桥接 FastAPI 与 engine 层"""

    @staticmethod
    def run(task_id, material, doc_type, project_path=None, full_doc_name=None):
        effective_name = full_doc_name or doc_type
        if doc_type == "软件设计文档":
            return DocumentGenerator._run_design(task_id, material, effective_name, project_path)
        elif doc_type == "测试用例":
            return DocumentGenerator._run_testcase(task_id, material, effective_name)
        else:
            return DocumentGenerator._run_srs(task_id, material, effective_name)

    @staticmethod
    def _run_srs(task_id, material, doc_type):
        material_path = os.path.join(settings.output_dir, f"{task_id}_material.txt")
        output_md = os.path.join(settings.output_dir, f"{task_id}.md")
        outline_path = output_md.replace(".md", "_outline.json")
        try:
            with open(material_path, "w", encoding="utf-8") as f:
                f.write(material)
            logger.info("开始生成文档 [%s] type=%s", task_id, doc_type)
            generate_srs_for_topic(material_file=material_path, output_md=output_md, doc_type=doc_type)
            if not os.path.exists(output_md):
                raise RuntimeError("引擎未生成输出文件")
            with open(output_md, "r", encoding="utf-8") as f:
                result_md = f.read()
            outline = None
            if os.path.exists(outline_path):
                with open(outline_path, "r", encoding="utf-8") as f:
                    outline = json.load(f)
            logger.info("文档生成完成 [%s]", task_id)
            return result_md, outline, None
        except Exception as e:
            logger.exception("文档生成失败 [%s]: %s", task_id, e)
            return None, None, str(e)
        finally:
            if os.path.exists(material_path):
                os.remove(material_path)

    @staticmethod
    def _run_design(task_id, material, doc_type, project_path):
        material_path = os.path.join(settings.output_dir, f"{task_id}_material.txt")
        output_md = os.path.join(settings.output_dir, f"{task_id}.md")
        outline_path = output_md.replace(".md", "_outline.json")
        try:
            combined = material or ""
            if project_path:
                if not os.path.isdir(project_path):
                    raise NotADirectoryError(f"项目路径不存在: {project_path}")
                scan_output = os.path.join(settings.output_dir, f"{task_id}_scan.txt")
                file_count = scan_project(project_dir=project_path, output_file=scan_output)
                logger.info("代码扫描完成 [%s]: %d 个文件", task_id, file_count)
                if file_count > 0:
                    with open(scan_output, "r", encoding="utf-8") as f:
                        scanned_code = f.read()
                    if combined:
                        combined = scanned_code + "\n\n===== 用户补充说明 =====\n" + combined
                    else:
                        combined = scanned_code
                if os.path.exists(scan_output):
                    os.remove(scan_output)
            if not combined:
                raise ValueError("素材和项目代码均为空，无法生成文档")
            with open(material_path, "w", encoding="utf-8") as f:
                f.write(combined)
            logger.info("开始生成设计文档 [%s] type=%s", task_id, doc_type)
            generate_design_for_topic(material_file=material_path, output_md=output_md, doc_type=doc_type)
            if not os.path.exists(output_md):
                raise RuntimeError("引擎未生成输出文件")
            with open(output_md, "r", encoding="utf-8") as f:
                result_md = f.read()
            outline = None
            if os.path.exists(outline_path):
                with open(outline_path, "r", encoding="utf-8") as f:
                    outline = json.load(f)
            logger.info("设计文档生成完成 [%s]", task_id)
            return result_md, outline, None
        except Exception as e:
            logger.exception("设计文档生成失败 [%s]: %s", task_id, e)
            return None, None, str(e)
        finally:
            if os.path.exists(material_path):
                os.remove(material_path)

    @staticmethod
    def _run_testcase(task_id, material, doc_type):
        material_path = os.path.join(settings.output_dir, f"{task_id}_material.txt")
        output_md = os.path.join(settings.output_dir, f"{task_id}.md")
        outline_path = output_md.replace(".md", "_outline.json")
        try:
            with open(material_path, "w", encoding="utf-8") as f:
                f.write(material or "")
            logger.info("开始生成测试用例 [%s] type=%s", task_id, doc_type)
            generate_testcase_for_topic(material_file=material_path, output_md=output_md, doc_type=doc_type)
            if not os.path.exists(output_md):
                raise RuntimeError("引擎未生成输出文件")
            with open(output_md, "r", encoding="utf-8") as f:
                result_md = f.read()
            outline = None
            if os.path.exists(outline_path):
                with open(outline_path, "r", encoding="utf-8") as f:
                    outline = json.load(f)
            logger.info("测试用例生成完成 [%s]", task_id)
            return result_md, outline, None
        except Exception as e:
            logger.exception("测试用例生成失败 [%s]: %s", task_id, e)
            return None, None, str(e)
        finally:
            if os.path.exists(material_path):
                os.remove(material_path)