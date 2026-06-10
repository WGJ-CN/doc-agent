"""
项目代码扫描工具 —— 递归扫描项目目录，将源代码文件内容汇总输出为 txt 素材文件。
供 document_design_generate.py / document_generate.py 作为 material_file 输入。
"""

import os
from datetime import datetime
from pathlib import Path


# ================= 默认配置 =================
DEFAULT_SKIP_DIRS = {
    "__pycache__", ".git", ".svn", ".hg",
    "node_modules", ".idea", ".vscode",
    "venv", ".venv", "env", ".env",
    "build", "dist", ".next", ".nuxt",
    "target", "vendor", "egg-info",
}

DEFAULT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".vue", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp",
    ".cs", ".rb", ".php", ".swift",
    ".kt", ".scala",
}

DEFAULT_OUTPUT_DIR = "materials"

# 项目根目录（engine/ 的父目录），固定输出到 <项目根>/materials/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ================= 扫描函数 =================
def scan_project(
    project_dir: str,
    output_file: str,
    extensions: set = None,
    skip_dirs: set = None,
    max_file_size_kb: int = 500,
) -> int:
    """
    扫描项目目录，将所有匹配的源代码文件内容写入输出文件。

    参数：
        project_dir:  项目根目录路径
        output_file:  输出 txt 文件路径
        extensions:   要收集的文件扩展名集合（默认 DEFAULT_EXTENSIONS）
        skip_dirs:    要跳过的目录名集合（默认 DEFAULT_SKIP_DIRS）
        max_file_size_kb: 单个文件最大大小（KB），超过则跳过并警告

    返回：
        成功收集的文件数量
    """
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS
    if skip_dirs is None:
        skip_dirs = DEFAULT_SKIP_DIRS

    project_path = Path(project_dir).resolve()
    if not project_path.is_dir():
        raise NotADirectoryError(f"项目目录不存在: {project_dir}")

    # 确保输出目录存在
    output_path = Path(output_file).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    max_bytes = max_file_size_kb * 1024
    file_count = 0

    with open(output_file, "w", encoding="utf-8") as out:
        for filepath in sorted(project_path.rglob("*")):
            # 跳过指定目录
            if any(skip in filepath.parts for skip in skip_dirs):
                continue
            if not filepath.is_file():
                continue
            if filepath.suffix.lower() not in extensions:
                continue

            # 跳过过大文件
            try:
                size = filepath.stat().st_size
            except OSError:
                continue
            if size > max_bytes:
                print(f" 跳过过大的文件 ({size // 1024} KB): {filepath.relative_to(project_path)}")
                continue
            if size == 0:
                continue

            # 读取文件内容
            try:
                content = filepath.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = filepath.read_text(encoding="gbk")
                except Exception:
                    print(f" 无法解码文件，跳过: {filepath.relative_to(project_path)}")
                    continue
            except Exception:
                print(f" 读取失败，跳过: {filepath.relative_to(project_path)}")
                continue

            # 写入输出文件
            rel_path = filepath.relative_to(project_path).as_posix()
            out.write(f"===== {rel_path} =====\n")
            out.write(content)
            if not content.endswith("\n"):
                out.write("\n")
            out.write("\n")
            file_count += 1

    print(f" 扫描完成：收集 {file_count} 个文件 -> {output_file}")
    return file_count


def make_default_output_name(project_dir: str) -> str:
    """根据项目名称和时间戳生成默认输出路径（固定在项目根 materials/ 下）"""
    project_name = Path(project_dir).resolve().name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{project_name}_code_{timestamp}.txt"
    return str(_PROJECT_ROOT / DEFAULT_OUTPUT_DIR / filename)


# ================= 主入口 =================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="扫描项目代码并输出为素材文本文件")
    parser.add_argument("project_dir", help="项目根目录路径")
    parser.add_argument(
        "-o", "--output", default=None,
        help="输出文件路径（默认: materials/<项目名>_code_<时间戳>.txt）"
    )
    parser.add_argument("--ext", nargs="*", default=None, help="自定义文件扩展名（如 .py .java）")
    parser.add_argument("--max-size", type=int, default=500, help="单文件最大大小（KB），默认500")
    args = parser.parse_args()

    custom_exts = set(args.ext) if args.ext else None

    if args.output:
        output_file = args.output
    else:
        output_file = make_default_output_name(args.project_dir)

    scan_project(
        project_dir=args.project_dir,
        output_file=output_file,
        extensions=custom_exts,
        max_file_size_kb=args.max_size,
    )
