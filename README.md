# CourseCompass

基于 RAG 架构为 UNSW 研究生构建的 AI 选课顾问，支持自然语言问答、多轮对话与课程精准检索。

Live Demo：https://frontend-pink-eight-23.vercel.app/

<img width="1348" height="930" alt="image" src="https://github.com/user-attachments/assets/810bd186-40e2-40a0-8f8e-e48ebda3073d" />

---

## 功能特性

- **自然语言选课咨询** — 用中文描述学习目标，AI 推荐匹配课程并给出对比分析
- **精准课程检索** — FAISS 语义检索 + BM25 关键词检索，RRF 融合排序，课程代码精确召回
- **流式回答** — GPT-5.6 Sol 逐 token 输出，SSE 实时推送，回答附带来源课程卡片
- **多轮对话** — 自动改写问题为 standalone question，保持跨轮检索准确性
- **多会话管理** — 新建、切换、删除会话，标题自动生成，历史持久化
- **用户系统** — Google OAuth / 邮箱密码登录，头像上传，对话记录导出（JSON）

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 15 (App Router) · TypeScript · Tailwind CSS |
| 后端 | FastAPI · Python · Server-Sent Events |
| AI / RAG | LangChain · OpenAI GPT-5.6 Sol · text-embedding-3-small |
| 检索 | FAISS · BM25 · Reciprocal Rank Fusion |
| 认证 | Supabase Auth · Google OAuth · JWT (ES256) |
| 数据库 | Supabase (PostgreSQL) · Row Level Security |
| 存储 | Supabase Storage |

---

## 项目结构

```
CourseCompass/
├── frontend/                  # Next.js 前端
│   ├── app/
│   │   ├── page.tsx           # 主页（ChatWindow）
│   │   ├── auth/              # 登录页 & OAuth 回调
│   │   └── doc/               # 相关资料页
│   ├── components/
│   │   ├── ChatWindow.tsx     # 核心对话界面
│   │   ├── Sidebar.tsx        # 会话列表侧边栏
│   │   ├── MessageBubble.tsx  # 消息气泡
│   │   ├── SourceCards.tsx    # 来源课程卡片
│   │   ├── ChatInput.tsx      # 输入框
│   │   └── SettingsModal.tsx  # 设置弹窗
│   └── lib/
│       ├── api.ts             # SSE 流式请求
│       └── supabase.ts        # Supabase 客户端
├── backend/                   # FastAPI 后端
│   ├── app/
│   │   ├── main.py            # 服务入口
│   │   ├── dependencies.py    # JWT 鉴权
│   │   ├── schemas.py         # Pydantic 模型
│   │   └── rag/
│   │       ├── chain.py       # RAG 流水线
│   │       ├── retriever.py   # 混合检索（BM25 + FAISS）
│   │       ├── vectorstore.py # FAISS 索引管理
│   │       └── loader.py      # 课程数据加载
│   ├── scripts/
│   │   └── build_index.py     # 构建 FAISS 索引
│   └── faiss_index/           # 持久化向量索引
├── output/
│   └── unsw_8543_courses.json # 爬取的课程数据
└── supabase/
    └── schema.sql             # 数据库表、RLS 策略、权限与头像存储桶
```

---

## 快速开始

### 前置要求

- Node.js 18+
- Python 3.11+
- Supabase 项目（Auth 需启用邮箱或 Google 登录；表和存储桶由 `supabase/schema.sql` 创建）
- OpenAI API Key

### 1. 配置环境变量

**`backend/.env`**
```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-5.6-sol                      # 可选，对话模型，默认 gpt-5.6-sol
OPENAI_PARSER_MODEL=                          # 可选，查询解析模型，默认同 OPENAI_MODEL
OPENAI_EMBEDDING_MODEL=text-embedding-3-small # 可选，需与 FAISS 索引一致，修改后须重建索引
SUPABASE_URL=https://your-project.supabase.co
```

**`frontend/.env.local`**
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. 初始化数据库

在 Supabase Dashboard → SQL Editor 中执行 `supabase/schema.sql`。该脚本可重复执行，会一并创建数据表、行级安全策略、`authenticated` 角色的表权限，以及头像存储桶 `avatars` 及其策略。

### 3. 构建向量索引

```bash
cd backend
pip install -r requirements.txt
python -m scripts.build_index
```

### 4. 启动后端

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 [http://localhost:3000](http://localhost:3000)

---

## 线上部署

前端部署于 **Vercel**，后端部署于 **Railway**（Docker 容器），数据库与认证托管于 Supabase。

```
用户浏览器
    │
    ▼
[Vercel] Next.js 前端
https://frontend-pink-eight-23.vercel.app
    │ /api/* 请求
    ▼
[Railway] FastAPI 后端
https://coursecompass-production-76d5.up.railway.app
    │              │
    ▼              ▼
[OpenAI API]   [Supabase]
```

### 前端（Vercel）

```bash
cd frontend
npx vercel --prod
```

Vercel 环境变量：

| Key | 说明 |
|-----|------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase 项目 URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase 匿名公钥 |
| `NEXT_PUBLIC_API_URL` | Railway 后端域名 |

### 后端（Railway + Docker）

Railway 连接 GitHub 仓库，Root Directory 设为 `backend`，自动检测并使用 `Dockerfile` 构建。

Railway 环境变量：

| Key | 说明 |
|-----|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `SUPABASE_URL` | Supabase 项目 URL |
| `ALLOWED_ORIGINS` | 允许跨域的前端域名，多个用逗号分隔 |

### Supabase OAuth 回调配置

在 Supabase Dashboard → **Authentication → URL Configuration** 中添加：

```
https://frontend-pink-eight-23.vercel.app/auth/callback
```

---

## RAG 检索流程

```
用户问题（+ 对话历史）
  └─► 查询解析（每轮都做，LLM 结构化输出）
        ├─ english_query   英文检索关键词（课程库是英文，BM25 不能分中文）
        ├─ standalone_question  消解指代后的完整问题
        ├─ course_codes    明确提到的课程代码 → 直接固定召回
        ├─ terms           学期条件 → 作为硬过滤
        └─ intent          lookup / compare / recommend / other → 决定返回课程数 3 / 5 / 8 / 6
  └─► 混合检索
        ├─ FAISS 语义检索  top 20（查询 = 英文关键词 + 用户原话）
        └─ BM25 关键词检索 top 20（得分为 0 的不参与）
              └─► RRF 融合 → 学期过滤 → 固定召回的课程排最前
  └─► 用课程原始文本作为 context → 流式生成
  └─► SSE 推送 token + sources
```

**文档增强**：`scripts/enrich_courses.py` 离线为每门课生成中文简介、中英文关键词和适合人群（`backend/output/course_enrichment.json`），
只拼进用于检索的文本；给 LLM 的 context 仍是课程原始数据，避免把生成内容当成事实。
修改课程数据或增强内容后需重建索引：`python -m scripts.enrich_courses && python -m scripts.build_index`。

## 离线评测

评测集 `backend/eval/cases.json`（53 条，手工标注）：每条含 `must`（核心课程）、`acceptable`（也算相关）、`constraints`（学期、课程代码）、`key_points`（回答必须覆盖的事实）。
运行时会先校验标注与课程数据是否一致（课程是否存在、学期是否匹配）。

```bash
cd backend
python -m eval.test_metrics                 # 指标与评测集的单元测试
python -m eval.run_eval --retrieval-only    # 检索端，不调用评判模型，几乎免费
python -m eval.run_eval --full              # 加上生成与 LLM 评判（需要 JUDGE_API_KEY）
# 可选：--out FILE 保存结果，--compare PREV.json 对比上次，--category/--limit 只跑一部分，--no-cache 不用缓存
```

| 端 | 指标 | 含义 |
|---|---|---|
| 检索 | **Recall** | must 课程中被召回的比例 |
| 检索 | **Precision** | 返回课程中属于 must 或 acceptable 的比例；同时给出该 k 下的理论上限 `precision_ceiling` |
| 检索 | **MRR** | 第一个 must 课程排名的倒数（用户直接写出课程代码的用例固定排第一，不计入） |
| 检索 | **Constraint Compliance** | `term_ok`：返回课程是否都满足学期；`code_ok`：用户写出的课程代码是否都返回；`answer_term_ok`：回答里推荐的课程是否都满足学期 |
| 生成 | `oos_code_rate`（诊断） | 回答里的课程代码有多少在给 LLM 的上下文文本中完全没出现过 |
| 生成 | **Faithfulness** | 回答中的**事实断言**有多少被给 LLM 的上下文支持。建议、难度评价等观点类断言不计分，另报 `opinion_rate` |
| 生成 | **Context Recall** | `key_points` 中有多少能仅凭检索到的上下文推出 |

生成端的评判模型与应用模型分开配置（`JUDGE_API_KEY` / `JUDGE_BASE_URL` / `JUDGE_MODEL`，默认 DeepSeek `deepseek-flash`，调用时关闭思考模式），评判 key 不会回退到 `OPENAI_API_KEY`。
解析结果、生成的回答和评判结果缓存在 `backend/eval/.cache/`，改动后重跑只为变化的部分付费。
`eval/baseline_retrieval.json` 是改造前系统（commit `221b409`）在同一套检索指标下的结果，`eval/current_full.json` 是当前系统的完整评测（含回答与评判明细），可用 `--compare` 对比。

