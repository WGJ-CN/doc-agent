import asyncio
import os
import queue
import re
import sys
import threading
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# ---------- 进度推送基础设施 ----------
_progress_queues: dict[str, queue.Queue] = {}
_queues_lock = threading.Lock()


def _push_progress(task_id: str, step: str, tool: str):
    """线程安全地把进度事件推入队列（由引擎线程调用）"""
    with _queues_lock:
        q = _progress_queues.get(task_id)
    if q is not None:
        try:
            q.put_nowait({"step": step, "tool": tool})
        except queue.Full:
            pass


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


def _make_progress_writer(task_id: str, original_write):
    """生成一个替换 sys.stdout.write 的拦截函数"""
    def write(s: str):
        original_write(s)
        m = _TOOL_PATTERN.search(s)
        if m:
            tool_name = m.group(1)
            step = _STEP_MAP.get(tool_name, tool_name)
            _push_progress(task_id, step, tool_name)
    return write


# ---------- 引擎导入 ----------
sys.path.insert(0, settings.engine_dir)
from document_generate import generate_srs_for_topic
from document_design_generate import generate_design_for_topic
from testcase_generate import generate_testcase_for_topic
from project_scanner import scan_project


def run_with_progress(task_id, material, doc_type, project_path=None, full_doc_name=None):
    """在线程中执行生成，自动拦截 stdout 推送步骤事件"""
    original_write = sys.stdout.write
    sys.stdout.write = _make_progress_writer(task_id, original_write)
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
        _push_progress(task_id, "done", "done")


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