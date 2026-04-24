# CourseCompass 技术文档与面试准备

## 项目概述

CourseCompass 是一个基于 RAG（检索增强生成）的 UNSW 课程智能问答系统。用户可以用自然语言查询 8500+ 门课程信息，系统通过混合检索 + 大语言模型生成准确的课程推荐和解答。

---

## 一、技术选型与理由

### 前端：Next.js 15 + React 19 + TypeScript + Tailwind CSS

**选择理由：**
- **Next.js App Router**：内置文件路由、服务端中间件（用于鉴权跳转）、SSR/SSG 支持。本项目主要用其 middleware 在服务端拦截未认证请求，避免前端闪烁。
- **React 19**：最新稳定版，配合 App Router 使用 Server Components 理念，组件结构清晰。
- **TypeScript**：强类型约束，前后端共享接口定义（`Message`、`Conversation`、`CourseSource`），减少运行时错误。
- **Tailwind CSS**：原子化样式，无需维护独立 CSS 文件，快速原型开发。自定义了品牌色 `brand: #FFD100`。

### 后端：FastAPI + Python

**选择理由：**
- **FastAPI**：原生支持异步、自动生成 OpenAPI 文档、Pydantic 集成，非常适合 AI/ML 服务。相比 Flask，内置 async 支持对 SSE 流式响应至关重要。
- **Pydantic**：数据校验和序列化，与 LangChain 生态天然兼容。

### AI/RAG：LangChain + OpenAI + FAISS + BM25

**选择理由：**
- **LangChain**：提供 RAG 所需的抽象层（Document Loader、VectorStore、Chain），减少重复开发。
- **OpenAI GPT-4.1-nano**：成本低、速度快，课程信息问答不需要最强模型，nano 足够准确。
- **text-embedding-3-small**：OpenAI 最新小型嵌入模型，性价比高，适合大批量课程文档编码。
- **FAISS（CPU）**：Facebook 开源的向量检索库，本地持久化，无需额外向量数据库服务，部署简单。
- **BM25**：经典关键词检索，对课程代码（如 `COMP9020`）的精确匹配远优于语义检索。

### 混合检索：RRF（倒数排名融合）

**选择理由：**
- 单纯语义检索可能漏掉精确课程代码；单纯 BM25 无法理解"计算机视觉类课程"这样的语义查询。
- RRF 无需归一化分数，直接基于排名融合，避免两种检索的分数量纲不一致问题。
- BM25 权重设为 2.0，强调课程代码精确匹配的重要性。

### 数据库/认证：Supabase（PostgreSQL + Auth + Storage）

**选择理由：**
- **Supabase** 提供一站式 BaaS：数据库、认证、存储、实时订阅，无需自建用户系统。
- **Row Level Security（RLS）**：数据库层面隔离用户数据，即使 API 层有漏洞也不会越权访问。
- **Google OAuth 集成**：Supabase 原生支持，几行配置即可。
- **JWT（ES256）**：非对称签名，后端通过 JWKS 验证，无需共享密钥。

### 爬虫：Selenium

**选择理由：**
- UNSW 课程手册页面通过 JavaScript 动态渲染，静态 HTTP 请求无法获取完整数据。
- Selenium 驱动真实浏览器，可处理动态内容，成功爬取 8543 门课程。

---

## 二、核心技术实现细节

### 2.1 RAG Pipeline（检索增强生成）

```
用户问题
    ↓
[问题改写] GPT-4.1-nano 将多轮对话问题改写为独立问题
    ↓
[混合检索]
  ├─ FAISS 语义检索 → Top 30 候选
  └─ BM25 关键词检索 → Top 20 候选
    ↓
[RRF 融合排序] → Top-K 文档
    ↓
[Prompt 构建] 系统提示 + RAG 上下文 + 对话历史
    ↓
[GPT-4.1-nano 生成] 流式输出
    ↓
SSE 流式返回前端
```

#### 问题改写（Condense Question）

```python
# chain.py
if history:
    standalone_q = condense_llm.invoke(condense_prompt)
    # 正则保护：提取原始问题中的课程代码
    codes = re.findall(r'[A-Z]{4}\d{4}', original_question)
    if codes and not all(c in standalone_q for c in codes):
        standalone_q += " " + " ".join(codes)
```

**关键点**：LLM 改写问题时可能丢失课程代码，用正则提取后补充回去，确保 BM25 仍能精确匹配。

#### RRF 融合算法

```python
def reciprocal_rank_fusion(faiss_docs, bm25_docs, k=60, bm25_weight=2.0):
    scores = {}
    for rank, doc in enumerate(faiss_docs):
        scores[doc.id] = scores.get(doc.id, 0) + 1 / (k + rank + 1)
    for rank, doc in enumerate(bm25_docs):
        scores[doc.id] = scores.get(doc.id, 0) + bm25_weight / (k + rank + 1)
    return sorted(docs, key=lambda d: scores[d.id], reverse=True)
```

RRF 公式：`score = 1/(K + rank)`，K=60 是平滑参数，防止排名靠前的文档分数过高。

#### FAISS 索引管理

- 索引持久化到 `backend/faiss_index/`（`index.faiss` + `index.pkl`）
- 使用单例模式：`_vectorstore_instance` 全局缓存，FastAPI lifespan hook 预热
- 构建索引：`scripts/build_index.py` 批量嵌入 8543 门课程，一次性写入磁盘

### 2.2 流式响应（SSE）

**后端（FastAPI）：**

```python
# chat.py
async def event_generator():
    # 1. 先发送 sources
    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
    # 2. 流式 token
    async for chunk in llm_chain.astream(input):
        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
    # 3. 结束信号
    yield "data: [DONE]\n\n"

return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**前端（Next.js）：**

```typescript
// api.ts
const reader = response.body.getReader()
while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const text = decoder.decode(value)
    // 解析 SSE 行，按类型分发回调
    for (const line of text.split('\n')) {
        if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'token') onToken(data.content)
            if (data.type === 'sources') onSources(data.sources)
        }
    }
}
```

**为什么用 SSE 不用 WebSocket？**
- 问答是单向流（服务器→客户端），SSE 够用且更简单
- SSE 基于 HTTP，天然支持断线重连，无需额外协议

### 2.3 认证与鉴权

**JWT 验证流程：**

```
前端请求 → Authorization: Bearer <supabase_jwt>
    ↓
FastAPI dependencies.py
    ↓
fetch JWKS from Supabase → 验证 ES256 签名 → 解码 payload
    ↓
返回 user_id 给路由处理器
```

**前端中间件鉴权：**

```typescript
// middleware.ts
export async function middleware(request: NextRequest) {
    const session = await supabase.auth.getSession()
    if (!session && !isAuthPage) {
        return NextResponse.redirect('/auth')
    }
    if (session && isAuthPage) {
        return NextResponse.redirect('/')
    }
}
```

**Row Level Security（RLS）：**

```sql
-- 用户只能查看自己的对话
CREATE POLICY own_conversations ON conversations
    USING (user_id = auth.uid());

-- 用户只能查看自己对话中的消息
CREATE POLICY own_messages ON messages
    USING (conversation_id IN (
        SELECT id FROM conversations WHERE user_id = auth.uid()
    ));
```

### 2.4 数据库设计

```sql
conversations
├── id UUID PK
├── user_id UUID → auth.users
├── title TEXT
├── created_at TIMESTAMPTZ
└── updated_at TIMESTAMPTZ  ← 触发器自动更新

messages
├── id UUID PK
├── conversation_id UUID → conversations
├── role TEXT ('user' | 'assistant')
├── content TEXT
├── sources JSONB        ← 存储课程来源数组
└── created_at TIMESTAMPTZ

-- 索引
CREATE INDEX ON conversations(user_id, updated_at DESC);
CREATE INDEX ON messages(conversation_id, created_at ASC);
```

**JSONB 存储 sources 的原因**：
- sources 结构稳定但不需要单独查询
- JSONB 比关系表更简单，避免多表 JOIN
- PostgreSQL JSONB 支持索引，性能足够

### 2.5 爬虫实现

```python
# crawler/handbook.py
driver = webdriver.Chrome()
driver.get("https://www.handbook.unsw.edu.au/")
# 等待动态内容加载
WebDriverWait(driver, 10).until(EC.presence_of_element_located(...))
# 遍历所有专业、所有课程页面
# 输出：output/unsw_8543_courses.json
```

爬取字段：course_code, name, units_of_credit, offering_terms, faculty, delivery_mode, overview, constraints, url

---

## 三、面试常见问题与回答

### RAG 相关

**Q1：什么是 RAG？为什么用 RAG 而不是直接让模型回答课程问题？**

RAG（Retrieval-Augmented Generation）是在 LLM 生成前先从外部知识库检索相关文档，将其作为上下文注入 Prompt 的范式。

选择 RAG 的原因：
1. **知识时效性**：GPT 训练数据有截止日期，无法知道 UNSW 最新课程安排
2. **幻觉控制**：RAG 提供事实依据，LLM 基于检索到的真实数据回答，减少编造
3. **可溯源**：可以向用户展示答案来自哪些课程文档（sources）
4. **成本**：Fine-tune 模型成本高，RAG 只需维护向量库

---

**Q2：为什么同时使用 FAISS 和 BM25？各自解决什么问题？**

- **FAISS（语义检索）**：将文本转为向量，通过余弦相似度找语义相近的文档。优势是能理解"人工智能相关课程"这类模糊查询；劣势是对精确字符串匹配（如课程代码 `COMP9020`）不敏感。
- **BM25（关键词检索）**：基于词频/逆文档频率的统计检索。优势是精确匹配课程代码；劣势是无法理解语义。

两者互补，通过 RRF 融合后召回率和精确率都提升。

---

**Q3：RRF（倒数排名融合）的原理是什么？为什么不直接对分数加权？**

RRF 公式：`score(d) = Σ 1/(k + rank_i(d))`

原因：
1. **量纲问题**：FAISS 输出余弦相似度（0~1），BM25 输出 TF-IDF 分数（范围不定），直接加权会让某一方主导
2. **鲁棒性**：RRF 只关心排名，对极端分数不敏感
3. **无需归一化**：分数归一化本身就需要经验调参，RRF 避免了这个问题

本项目中 BM25 权重设为 2.0，强调课程代码精确匹配更重要。

---

**Q4：问题改写（Condense Question）的作用是什么？**

多轮对话中，用户可能说"那这门课呢？"，这个问题脱离上下文无法被检索。改写将其变为独立的完整问题（如"COMP9020 的授课时间是什么？"），使检索更准确。

关键挑战：LLM 改写时可能省略课程代码（认为上文已提及），用正则捕获原问题中的课程代码并补充回改写结果，确保不丢失关键信息。

---

**Q5：如何处理 FAISS 的冷启动问题？**

- 用 `scripts/build_index.py` 对 8543 门课程批量嵌入，结果持久化到磁盘（`faiss_index/`）
- FastAPI 的 lifespan hook 在应用启动时预热加载索引
- 单例模式缓存，避免重复加载
- 如果索引文件存在则直接加载，否则重新构建

---

### 系统设计相关

**Q6：后端为什么是无状态的？有什么优缺点？**

本项目后端不存储对话历史（状态由前端维护，每次请求携带完整历史）。

优点：
- 无状态易于水平扩展，任意实例处理任意请求
- 不需要 Session 管理，降低服务端复杂度
- 故障恢复简单

缺点：
- 每次请求携带完整历史，网络开销随对话轮数线性增长
- 历史截断（20条）可能丢失早期上下文

---

**Q7：为什么使用 SSE 而不是 WebSocket？**

问答场景是典型的"请求-流式响应"模式，通信方向是服务器→客户端，WebSocket 的双向通信能力用不到。

SSE 优势：
- 基于标准 HTTP，无需握手升级协议
- 天然支持断线重连（EventSource API）
- 代理和 CDN 支持更好
- 实现更简单（FastAPI `StreamingResponse`）

---

**Q8：如何保证用户数据隔离？**

三层保护：
1. **JWT 认证**：每个请求必须携带有效的 Supabase JWT，验证用户身份
2. **应用层过滤**：查询时加 `WHERE user_id = current_user_id`
3. **数据库 RLS**：即使应用层绕过，PostgreSQL 行级安全策略也会阻止越权访问

---

**Q9：如果课程数据量增长 10 倍，系统如何扩展？**

1. **向量库**：FAISS CPU 版换为 Pinecone/Weaviate 等托管向量数据库，支持分布式索引
2. **嵌入服务**：批量嵌入改为异步队列（Celery + Redis），避免阻塞
3. **BM25**：换为 Elasticsearch，支持分布式关键词检索
4. **后端**：FastAPI 无状态设计天然支持水平扩展，加 Nginx 负载均衡即可
5. **缓存**：高频问题结果缓存到 Redis，减少 LLM 调用

---

### 前端相关

**Q10：为什么用 Next.js 中间件做鉴权而不是在页面组件中检查？**

中间件在服务端 Edge Runtime 运行，在页面渲染前就执行跳转，用户看不到未授权内容的闪烁（FOUC）。如果在页面组件中检查，页面会先渲染，检查完才跳转，体验差且有安全隐患。

---

**Q11：流式 token 如何在 React 中更新 UI？**

```typescript
// 回调驱动状态更新
onToken={(chunk) => {
    setMessages(prev => {
        const last = prev[prev.length - 1]
        return [...prev.slice(0, -1), { ...last, content: last.content + chunk }]
    })
}}
```

使用函数式 setState 避免闭包陷阱，每个 token 追加到最后一条消息的 content 上，React 批量更新 DOM 保证性能。

---

### 数据库相关

**Q12：messages 表的 sources 为什么用 JSONB 而不是单独建表？**

- Sources 只在展示时用到，不需要单独查询或过滤
- Sources 结构固定（code、name、url 等），无需动态字段
- 避免了 JOIN 查询，消息加载更高效
- PostgreSQL JSONB 支持 GIN 索引，若将来需要搜索 sources 也支持

---

**Q13：数据库触发器的作用？**

```sql
CREATE TRIGGER update_conversation_timestamp
    BEFORE UPDATE ON conversations
    EXECUTE FUNCTION update_updated_at_column();
```

自动更新 `conversations.updated_at`，前端据此排序对话列表（最近活跃的排前面），无需应用层手动维护时间戳。

---

### 项目综合相关

**Q14：这个项目最大的技术挑战是什么？如何解决的？**

最大挑战是**混合检索的效果调优**：

1. 早期只用 FAISS，用户查"COMP9020"时排名不稳定，因为语义向量对精确代码不敏感
2. 加入 BM25 后分数归一化很麻烦，两个系统的分数范围完全不同
3. 最终采用 RRF 解决量纲问题，再调 BM25 权重到 2.0 强化精确匹配

第二个挑战是**问题改写时课程代码丢失**，通过正则保护解决（详见 2.1 节）。

---

**Q15：如果让你重新设计，会改变什么？**

1. **缓存层**：高频相同问题直接返回缓存，节省 OpenAI 费用
2. **流式 sources**：目前 sources 在检索完成后一次性发送，可以边检索边发送
3. **向量库升级**：FAISS 不支持动态更新，每次新增课程需重建索引；换为 Pinecone 支持实时增量更新
4. **评估体系**：加入 RAGAS 等 RAG 评估框架，量化检索准确率和答案质量
5. **重排序（Reranker）**：在 RRF 之后加 Cross-encoder 重排序，进一步提升 Top-K 精度

---

## 四、技术栈速查表

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 前端框架 | Next.js | 15 | App Router、SSR、中间件鉴权 |
| UI 库 | React | 19 | 组件化 UI |
| 类型系统 | TypeScript | 5.6 | 类型安全 |
| 样式 | Tailwind CSS | 3.4 | 原子化样式 |
| Markdown 渲染 | react-markdown | 9 | 渲染 LLM 输出 |
| 后端框架 | FastAPI | latest | 异步 API、SSE 流式响应 |
| 数据校验 | Pydantic | v2 | 请求/响应模型 |
| LLM | OpenAI GPT-4.1-nano | - | 问答生成、问题改写 |
| 嵌入模型 | text-embedding-3-small | - | 语义向量化 |
| RAG 框架 | LangChain | latest | 链式调用、文档管理 |
| 语义检索 | FAISS (CPU) | - | 向量相似度检索 |
| 关键词检索 | BM25 (rank-bm25) | - | 精确词匹配 |
| 数据库 | PostgreSQL (Supabase) | 15 | 对话/消息持久化 |
| 认证 | Supabase Auth | - | JWT、Google OAuth |
| 文件存储 | Supabase Storage | - | 用户头像 |
| 安全策略 | Row Level Security | - | 数据库级用户隔离 |
| 爬虫 | Selenium | latest | UNSW 课程数据采集 |
| 流式协议 | SSE | - | 实时 token 推送 |
