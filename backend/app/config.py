"""
应用配置，通过环境变量或 .env 文件加载
"""
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = "Doc-Agent API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # ---- DeepSeek API ----
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # ---- MySQL 数据库 ----
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "doc_agent")

    @property
    def database_url(self) -> str:
        # 本地开发用 SQLite，生产/协作环境配 MYSQL_PASSWORD 后用 MySQL
        pwd = os.getenv("MYSQL_PASSWORD", "")
        if pwd and pwd != "your-mysql-password":
            return (
                f"mysql+aiomysql://{self.MYSQL_USER}:{quote_plus(pwd)}"
                f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
                "?charset=utf8mb4"
            )
        return "sqlite+aiosqlite:///doc_agent.db"

    # 引擎路径
    @property
    def engine_dir(self) -> str:
        return os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "engine")
        )

    # 文件输出目录
    @property
    def output_dir(self) -> str:
        p = os.path.join(os.path.dirname(__file__), "..", "outputs")
        os.makedirs(p, exist_ok=True)
        return p

    # CORS
    CORS_ORIGINS: list[str] = ["*"]


settings = Settings()
