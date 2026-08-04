# 个人知识库系统

一个简单的个人知识库系统，支持文档管理、关键词搜索和语义搜索。

## 功能特性

- **文档管理**：创建、编辑、删除 Markdown 文档，支持文件上传
- **分类与标签**：将文档分类到历史、金融、英语等类别，支持标签管理
- **搜索功能**：
  - 关键词搜索（基于 SQLite LIKE）
  - 语义搜索（目前使用 mock 嵌入，可替换为 Volcengine 等 API）
- **Web 界面**：简洁的浏览器界面，方便使用
- **分类存储**：文档按类别存储在 `data/docs/{category}/` 目录下
- **日志记录**：所有请求和操作都记录在 `data/app.log` 中，方便调试

## 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite + FAISS
- **前端**：HTML + CSS + JavaScript（无框架）
- **部署**：Uvicorn + Nginx（可选）

## 项目结构

```
codex_rag/
├── backend/                 # FastAPI 后端
│   ├── __init__.py
│   ├── main.py              # 主应用入口，API 端点
│   ├── models.py            # SQLAlchemy 数据模型
│   ├── schemas.py           # Pydantic 模式
│   ├── database.py          # 数据库连接配置
│   └── search.py            # 搜索逻辑（FAISS + 嵌入）
├── frontend/                # 前端静态文件
│   ├── index.html           # 主页面
│   ├── style.css            # 样式
│   └── app.js               # 前端交互逻辑
├── data/
│   ├── docs/                # 存储 Markdown 文档文件（按类别分目录）
│   │   ├── history/
│   │   ├── finance/
│   │   └── english/
│   ├── db/                  # SQLite 数据库文件
│   ├── index/               # FAISS 索引文件
│   └── app.log              # 应用日志文件
├── venv/                    # Python 虚拟环境
├── requirements.txt         # Python 依赖
└── README.md                # 项目说明
```

## 安装与运行

### 1. 克隆项目（或创建项目）

```bash
cd /home/ubuntu/codex_rag
```

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 运行应用

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8002 --reload
```

应用将在 http://localhost:8002 启动。

### 5. 配置 Nginx（可选，用于生产环境）

在 Nginx 配置文件中添加反向代理：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

重启 Nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 使用说明

1. **创建文档**：点击 "新建文档" 按钮，填写标题、选择分类、添加标签，上传 .md/.txt 文件或输入内容，点击保存。
2. **搜索文档**：在搜索框输入关键词，点击搜索按钮，支持关键词和语义搜索。
3. **编辑文档**：点击文档列表中的文档，进入编辑模式，修改后点击保存。
4. **删除文档**：在编辑模式下点击 "删除" 按钮。
5. **查看日志**：所有请求和操作都记录在 `data/app.log` 中。

## 配置说明

### 替换语义搜索嵌入（使用 Volcengine）

1. 修改 `backend/search.py`，替换 `mock_embed` 函数为 Volcengine API 调用。
2. 安装 Volcengine Python SDK（如果需要）。
3. 添加 Volcengine API 密钥配置（建议使用环境变量）。

## 注意事项

- 数据备份：`data/` 目录包含数据库、文档、索引和日志文件，建议定期备份。
- 安全性：当前版本没有认证功能，建议在生产环境添加认证或限制访问 IP。
- 性能：语义搜索的索引更新逻辑目前比较简单，大量文档时可优化为增量更新。

## 未来改进

- [ ] 添加用户认证功能
- [ ] 集成 Volcengine 嵌入 API
- [ ] 优化搜索索引更新逻辑
- [ ] 添加 Markdown 预览功能
- [ ] 支持文档批量导入
- [ ] 添加版本历史功能
