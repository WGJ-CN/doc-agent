"""
文档生成服务 — 封装引擎调用
"""
import os
import sys
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# 导入引擎（只读，不修改）
sys.path.insert(0, settings.engine_dir)
from document_generate import generate_srs_for_topic      # noqa: E402
from document_design_generate import generate_design_for_topic  # noqa: E402
from testcase_generate import generate_testcase_for_topic  # noqa: E402
from project_scanner import scan_project                  # noqa: E402


class DocumentGenerator:
    """文档生成器 — 桥接 FastAPI 与 engine 层"""

    @staticmethod
    def run(
        task_id: str,
        material: str,
        doc_type: str,
        project_path: str | None = None,
        full_doc_name: str | None = None,
    ) -> tuple[str | None, dict | None, str | None]:
        """
        同步执行文档生成（在独立线程中调用）

        full_doc_name: 自定义文档名称（如"XX系统 软件设计文档"），
                       如果不为空则用它作为文档标题，否则用 doc_type
        """
        effective_name = full_doc_name or doc_type

        if doc_type == "软件设计文档":
            return DocumentGenerator._run_design(task_id, material, effective_name, project_path)
        elif doc_type == "测试用例":
            return DocumentGenerator._run_testcase(task_id, material, effective_name)
        else:
            return DocumentGenerator._run_srs(task_id, material, effective_name)

    @staticmethod
    def _run_srs(task_id: str, material: str, doc_type: str):
        """需求规格说明书生成"""
        material_path = os.path.join(settings.output_dir, f"{task_id}_material.txt")
        output_md = os.path.join(settings.output_dir, f"{task_id}.md")
        outline_path = output_md.replace(".md", "_outline.json")

        try:
            with open(material_path, "w", encoding="utf-8") as f:
                f.write(material)

            logger.info("开始生成文档 [%s] type=%s", task_id, doc_type)
            generate_srs_for_topic(
                material_file=material_path,
                output_md=output_md,
                doc_type=doc_type,
            )

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
    def _run_design(
        task_id: str,
        material: str,
        doc_type: str,
        project_path: str | None,
    ):
        """软件设计文档生成：扫描代码 + 合并素材 + 生成文档"""
        material_path = os.path.join(settings.output_dir, f"{task_id}_material.txt")
        output_md = os.path.join(settings.output_dir, f"{task_id}.md")
        outline_path = output_md.replace(".md", "_outline.json")

        try:
            combined = material or ""

            if project_path:
                if not os.path.isdir(project_path):
                    raise NotADirectoryError(f"项目路径不存在: {project_path}")

                scan_output = os.path.join(settings.output_dir, f"{task_id}_scan.txt")
                file_count = scan_project(
                    project_dir=project_path,
                    output_file=scan_output,
                )
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
            generate_design_for_topic(
                material_file=material_path,
                output_md=output_md,
                doc_type=doc_type,
            )

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
    def _run_testcase(task_id: str, material: str, doc_type: str):
        """DRG 测试用例生成：两阶段 LLM 生成 + ruzu.py 验算，输出可读 Markdown"""
        material_path = os.path.join(settings.output_dir, f"{task_id}_material.txt")
        output_md = os.path.join(settings.output_dir, f"{task_id}.md")
        outline_path = output_md.replace(".md", "_outline.json")

        try:
            with open(material_path, "w", encoding="utf-8") as f:
                f.write(material or "")

            logger.info("开始生成测试用例 [%s] type=%s", task_id, doc_type)
            generate_testcase_for_topic(
                material_file=material_path,
                output_md=output_md,
                doc_type=doc_type,
            )

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
