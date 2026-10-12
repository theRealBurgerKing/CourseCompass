# 更新日志

记录 CourseCompass 的所有改动，最新的在最上面。

**维护约定**
- 每次改动都在「未发布」下追加一条；合并并上线后，把它移到对应日期的标题下。
- 每条写清楚三件事：改了什么、为什么改、怎么验证的。已知的遗留问题也写上。
- 分类：**新增** / **变更** / **修复** / **安全** / **文档**。
- 括号里是提交号或 PR 号，方便回溯。

---

## 未发布

（暂无）

---

## 2026-10-13

分支 `fix/hardening`，已通过 PR #3 合并进 `main`（合并提交 `589e6f7`）。**线上部署状态未确认**：README 里的 Railway 地址当前返回 `Application not found`，无法从外部验证。只改后端接口层和少量前端，**没有改任何检索 / 生成逻辑**。

### 修复
- **课程数据路径**（`c6e522b`）：`courses.py` 用 `parent×4` 找仓库根目录的 `output/`，在 Railway（Root Directory 为 `backend`）的 Docker 镜像里会解析成 `/output/...`，导致 `/api/courses` 部署后失败。现改为复用 `loader.DATA_PATH`，两处共用一个常量。聊天不受影响。
- **鉴权阻塞事件循环**（`35b761a`）：`require_auth` 是 `async def`，但 `PyJWKClient` 刷新 JWKS 时是同步网络请求，会卡住其他请求。改为普通 `def`，由 FastAPI 放进线程池执行。校验逻辑和所有 401 报错保持不变。

### 安全
- **聊天输入限制**（`081eb54`，`schemas.py`）：

  | 字段 | 规则 | 超限时 |
  |---|---|---|
  | `message` | 1–2000 字 | 422 |
  | `history` | 只保留最近 20 条 | 静默截断 |
  | `history[].content` | 最长 8000 字 | 静默截断 |
  | `history[].role` | 只能是 `user` / `assistant` | 422 |
  | `conversation_id` | 最长 128 字；已弃用，后端不使用 | 422 |

  `history` 选择截断而不是拒绝，是因为前端每次发送整段会话历史，而 RAG 链路本来只取最后 20 条，拒绝会让长对话报错。8000 字的依据：评测集中最长一条回答约 1545 字。
- **按用户限流**（`081eb54`，新增 `app/rate_limit.py`）：以 JWT 的 `sub` 为 key，内存滑动窗口，每分钟 10 次、每天 200 次，两个窗口同时生效。超限返回 429 + `Retry-After`。可用 `RATE_LIMIT_PER_MINUTE`、`RATE_LIMIT_PER_DAY` 调整。
- **错误脱敏**（`081eb54`，`chain.py`）：流式出错时，浏览器只收到「服务暂时出错，请稍后重试」，完整异常用 `logger.exception` 写入服务端日志。

### 变更
- 删除仓库根目录的 `output/unsw_8543_courses.json`，它与 `backend/output/` 下那份逐字节相同。爬虫产出后需复制到 `backend/output/`。
- 前端 `ChatInput.tsx` 输入框加 `maxLength={2000}`；`lib/api.ts` 对 422 显示「消息为空或超过 2000 字，请精简后重试」（之前 `detail` 是数组，会显示成 `[object Object]`），429 直接展示后端提示。

### 新增
- 后端测试 `backend/tests/`（19 个用例），开发依赖放在 `backend/requirements-dev.txt`（不进生产镜像）。运行：`cd backend && pip install -r requirements-dev.txt && python -m pytest`。
  - `test_chat_limits.py`（11）：长度与角色限制、422、429 + `Retry-After`、默认每分钟 10 次、限流器按用户隔离与窗口滑动、错误不泄露异常文本且仍写日志。
  - `test_auth.py`（8）：有效 token、缺失 header、错误 scheme、过期、他人密钥签名、乱码 token、找不到签名密钥（401 而非 500）、依赖是同步函数。
- 加上原有的 `python -m eval.test_metrics`（10 项）共 29 项通过。测试不调用 OpenAI、不访问网络。

### 文档
- README 补充限流环境变量、测试运行方法、聊天接口限制，并更新目录结构。

### 验证与遗留
- 已验证：后端 29 项测试通过；运行中的后端重载后，无 / 假 token 返回 401，`GET /api/courses/COMP9021` 返回 200；前端 `tsc --noEmit` 通过。
- **未验证**：页面上登录后的真实对话（流式输出是否正常）；`python -m eval.run_eval --retrieval-only`（会调用 OpenAI，且本次没改检索代码）。
- 限流计数在进程内存里，重启清零、多实例各自独立；单实例够用，扩容后应换 Redis 等共享存储。
- 无效 token 时，401 的 `detail` 里仍带 JWT 库的原始报错（如 `Invalid header padding`），信息量很小，未处理。
- 未做的建议项：CI（GitHub Actions）、扩充评测集（hold-out、拒答用例）、前端取消生成（`AbortController`）、拆分 `ChatWindow.tsx`。
- 部署：`main` 若被 Vercel / Railway 跟踪，合并本分支会触发自动部署；上线后请确认 `/api/courses/COMP9021` 返回 200、无 token 调用 `/api/chat` 返回 401。

---

## 2026-10-05

### 新增
- **离线评测**（`1b1c5f2`，PR #2）：`backend/eval/` 下的检索指标（Recall / Precision / MRR / 约束合规）与生成指标（Faithfulness / Context Recall），生成端用独立的 LLM 评判模型（`JUDGE_API_KEY` 等）。含 53 条手工标注的评测集、改造前的基线结果和当前完整评测结果。详见 README「离线评测」。

## 2026-10-04

### 新增
- **按轮查询解析、文档增强、模型由环境变量配置**（`71df184`，PR #1）：每轮先用 LLM 结构化解析出英文检索词、独立问题、课程代码、学期和意图，再做 BM25 + FAISS 混合检索；`scripts/enrich_courses.py` 离线为每门课生成中文简介和关键词，只用于检索，不进给 LLM 的上下文。对话模型、解析模型、向量模型均可通过环境变量配置。

### 变更
- **数据库脚本可重复执行**（`3a9896c`）：`supabase/schema.sql` 改为幂等，并补上 `authenticated` 角色权限和头像存储桶 `avatars` 及其策略。
- 新增 `.env.example`（前后端各一份），收紧 `.gitignore`（`b7bafa9`）。

### 修复
- 找不到匹配的 JWKS 签名密钥时返回 401 而不是 500（`2032b55`）。

## 2026-04-15 至 2026-05-07（早期历史，按提交记录整理）

- **4 月 15–16 日**：项目初始化；爬虫抓取 UNSW 课程数据；搭建前后端；改为 SSE 流式输出；接入 Supabase 登录；优化检索；调整布局，新增设置页和资料页。
- **4 月 20–24 日**：新增 README 与 INTERVIEW.md；新增后端 Dockerfile 和部署配置；把课程数据移入 `backend/` 并修正加载路径；README 补充部署说明和线上演示链接。
- **5 月 7 日**：README 补充项目介绍和截图。
