# Doc-Agent

基于 DeepSeek AI 的文档自动生成系统，支持需求规格说明书和软件设计文档的智能生成。

## 项目结构

```
doc-agent/
├── engine/                  # 引擎层 — 调用 DeepSeek API 生成文档
├── backend/                 # 后端层 — FastAPI REST 服务
├── frontend/                # 前端层 — Vue 3 + Vite
└── materials/               # 素材文件目录
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+

### 1. 克隆项目

```bash
git clone <repo-url>
cd doc-agent
```

### 2. 配置环境变量

```bash
cp .env.example backend/.env
```

编辑 `backend/.env`，填入你的 DeepSeek API Key 和 MySQL 连接信息：

```env
DEEPSEEK_API_KEY=sk-your-actual-key
MYSQL_PASSWORD=your-database-password
```

> 前往 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 获取 API Key。

### 3. 初始化数据库

数据库建表脚本见 `backend/init.sql`。

### 4. 启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python run.py
```

服务默认运行在 `http://localhost:9006`。

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认运行在 `http://localhost:5173`，已配置代理到后端。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/tasks` | 创建文档生成任务 |
| GET | `/api/tasks` | 分页查询历史任务 |
| GET | `/api/tasks/:id` | 查询任务状态与结果 |
| GET | `/api/tasks/:id/download` | 下载生成的 Markdown 文件 |
| DELETE | `/api/tasks/:id` | 删除任务及关联文件 |

## 支持的文档类型

- 需求规格说明书
- 软件设计文档（支持扫描项目代码目录）

## 技术栈

- **AI**: DeepSeek API (deepseek-chat)
- **后端**: FastAPI + SQLAlchemy (async) + aiomysql
- **前端**: Vue 3 + Vite + Axios
- **数据库**: MySQL 8.0
