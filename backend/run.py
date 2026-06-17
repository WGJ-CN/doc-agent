import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env
load_dotenv()

# 添加项目根目录到 Python 路径（用于 engine 等跨目录导入）
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=9006,
        reload=True,
        access_log=False,
    )
