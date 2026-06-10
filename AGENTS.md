# AGENTS.md

## 项目框架

本项目为三层架构的文档自动生成系统：

```
doc-agent/
├── engine/                  # 引擎层（只读，不可修改）
│   └── document_generate.py # 核心文档生成引擎，调用 DeepSeek API
├── backend/                 # 后端层（FastAPI）
│   └── main.py             # REST API 服务，import 并调用 engine
└── frontend/               # 前端层（Vue 3 + Vite + Axios）
    └── src/
        ├── App.vue         # 根组件
        ├── main.js         # 入口
        └── components/     # 业务组件
```

调用链路：`前端(Vue+Axios) → 后端(FastAPI) → 引擎(import,不改)`

## engine/document_generate.py 只读规则

- `engine/document_generate.py` 文件为只读，**绝对不可修改**
- 后端只能通过 `import` 方式使用其中暴露的函数
- 可直接 import 的核心函数：`generate_srs_for_topic(material_file, output_md, doc_type)`
- 引擎内部使用 `if __name__ == "__main__"` 保护，import 时不会执行 main 块
- 引擎依赖 `openai` 包，后端环境需同步安装
