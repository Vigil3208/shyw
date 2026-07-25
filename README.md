# 景区讲解词多平台营销内容助手 · 后端

基于 FastAPI、LangChain 和 LangGraph 的内容生成 API。输入一段景区官方讲解词，系统会先抽取并锁定事实，再并行生成小红书、短视频和朋友圈三类内容，最后执行独立事实校验。

仓库同时提供一个零构建依赖的原生 HTML 前端示例，用于直接联调生成接口。

## 核心能力

- 从讲解词中抽取年代、人物、地点、数字、面积、票价和开放时间等事实。
- 并行生成小红书文案、短视频口播脚本和朋友圈/海报文案。
- 使用 `〖事实〗` 标记生成结果中的事实，方便前端高亮和人工复核。
- 独立校验输出结构、事实标记和原文外数字。
- 使用 SQLite 保存会话、事实库、输出版本、校验详情和运行日志。
- 使用 LangGraph SQLite checkpointer 持久化 Agent 执行状态。
- 支持单独重新生成某一平台内容，不覆盖其他平台结果。
- 模型调用超时、结构不合格或事实校验失败时，可按单平台降级到本地确定性生成，二次校验后保留恢复记录。
- 无模型密钥时可切换到本地确定性模式，方便前端联调和自动化测试。

## 技术栈

| 类型 | 技术 | 用途 |
| --- | --- | --- |
| 语言 | Python 3.11+ | 后端开发语言 |
| Web 框架 | FastAPI | REST API、参数校验、OpenAPI 文档 |
| 数据模型 | Pydantic v2 | 请求、响应和结构化模型输出 |
| JSON 容错 | json-repair | 修复兼容模型返回的轻微 JSON 格式错误 |
| Agent 编排 | LangGraph | 事实抽取、三路并行生成、事实校验 |
| LLM 接入 | LangChain、langchain-openai | OpenAI 及兼容接口调用 |
| 持久化 | SQLite | 会话、事实、版本化输出和日志 |
| Agent 检查点 | langgraph-checkpoint-sqlite | LangGraph 会话状态持久化 |
| 服务运行 | Uvicorn | ASGI Server |
| 包管理 | uv | 虚拟环境、依赖锁定、命令运行 |
| 测试 | pytest、FastAPI TestClient | 单元测试和接口测试 |

## 处理流程

```text
讲解词输入
   ↓
输入校验 / 敏感信息检测
   ↓
事实抽取 Agent
   ├── 小红书 Agent ──┐
   ├── 短视频 Agent ──┼── 事实校验 Agent ── 保存结果
   └── 朋友圈 Agent ──┘
```

三个平台 Agent 在同一个 LangGraph super-step 中并行执行。单路失败时，已成功的其他结果仍会保留。

## 项目结构

```text
wenan/
├── wenan_backend/
│   ├── app.py          # FastAPI 应用与路由
│   ├── service.py      # 生成与重生成业务流程
│   ├── workflow.py     # LangGraph 多 Agent 编排
│   ├── agents.py       # 模型调用及本地生成实现
│   ├── facts.py        # 事实抽取、高亮、敏感信息检测
│   ├── validation.py   # 事实和输出格式校验
│   ├── repository.py   # SQLite 持久化
│   ├── schemas.py      # 请求、响应和领域模型
│   ├── config.py       # 环境变量配置
│   └── cli.py          # wenan-api 命令入口
├── frontend/           # 原生 HTML/CSS/JavaScript 联调示例
├── tests/              # 自动化测试
├── .env.example        # 环境变量模板
├── pyproject.toml      # 项目和依赖配置
└── uv.lock             # 锁定依赖版本
```

## 快速开始

### 1. 安装依赖

需要先安装 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。

```powershell
uv sync --extra dev
```

### 2. 选择运行模式

本地联调模式不调用外部模型：

```powershell
$env:APP_MODEL_MODE = "local"
```

使用 OpenAI 模型：

```powershell
$env:APP_MODEL_MODE = "openai"
$env:OPENAI_API_KEY = "你的 API Key"
$env:OPENAI_MODEL = "gpt-5-mini"
```

使用 LongCat OpenAI 兼容接口：

```powershell
$env:APP_MODEL_MODE = "auto"
$env:LONGCAT_API_KEY = "你的 LongCat API Key"
$env:LONGCAT_URL = "https://api.longcat.chat/openai/v1"
$env:LONGCAT_MODEL = "LongCat-2.0"
```

也可以复制配置模板，应用会在启动时自动加载：

```powershell
Copy-Item .env.example .env
uv run wenan-api
```

应用启动时会自动从当前工作目录向上查找并加载 `.env`。操作系统中已经存在的同名环境变量优先级更高，不会被 `.env` 覆盖。

### 3. 启动服务

```powershell
uv run wenan-api
```

也可以使用：

```powershell
uv run python main.py
```

默认地址：

- API：`http://127.0.0.1:8000`
- Swagger UI：`http://127.0.0.1:8000/docs`
- OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`
- 健康检查：`http://127.0.0.1:8000/health`
- 前端示例：`http://127.0.0.1:8000/demo/`

### 4. 打开前端示例

服务启动后访问 `http://127.0.0.1:8000/demo/`。页面会先请求 `/health`
确认后端状态，提交表单时再请求 `POST /api/v1/sessions/generate`，并展示三个平台的生成结果。
结果按小红书笔记、短视频分镜和朋友圈九宫格的成品形态预览。
前端为原生 HTML、CSS 和 JavaScript，无需安装 Node.js 或启动额外开发服务器。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_MODEL_MODE` | `auto` | `auto`、`local` 或 `openai` |
| `OPENAI_API_KEY` | 空 | OpenAI API Key；`openai` 模式必填 |
| `OPENAI_MODEL` | `gpt-5-mini` | 使用的模型名称 |
| `OPENAI_BASE_URL` | 空 | OpenAI 兼容接口地址 |
| `LONGCAT_API_KEY` | 空 | LongCat API Key；会映射到 OpenAI 兼容客户端 |
| `LONGCAT_URL` | LongCat 官方地址 | LongCat OpenAI 兼容接口地址 |
| `LONGCAT_MODEL` | `LongCat-2.0` | LongCat 模型名称 |
| `APP_HOST` | `127.0.0.1` | 服务监听地址 |
| `APP_PORT` | `8000` | 服务端口 |
| `APP_DATA_DIR` | `data` | SQLite 数据目录 |
| `APP_MAX_INPUT_CHARS` | `12000` | 讲解词最大字符数 |
| `APP_CORS_ORIGINS` | 本地 3000 端口 | 逗号分隔的前端来源 |
| `MODEL_TIMEOUT_SECONDS` | `14` | 单次模型请求超时 |
| `MODEL_MAX_RETRIES` | `0` | 模型 SDK 最大重试次数 |

`auto` 模式下，存在 `OPENAI_API_KEY` 或 `LONGCAT_API_KEY` 时使用模型，否则自动使用 `local` 模式。若同时配置两组变量，`OPENAI_*` 优先。

LongCat 当前通过 OpenAI 兼容的 Chat Completions 接口接入。代码会自动将完整的 `/chat/completions` 地址规范化为客户端需要的 Base URL，并默认使用 `LongCat-2.0`。为满足本项目的响应时间目标，LongCat 调用默认关闭思考模式。

## 前端接入约定

- API 前缀：`/api/v1`
- 请求格式：`application/json`
- 时间字段：UTC ISO 8601 字符串
- `session_id`：UUID 字符串
- 生成接口为同步接口，前端应设置至少 35 秒的请求超时。
- 生成期间应禁用重复提交，并展示加载状态。
- `outputs` 可能因单路失败而缺少某个平台，前端不要假设三个键始终存在。
- `errors[].recovered === true` 表示模型调用失败但已用本地实现恢复，相关平台仍有可展示结果。
- 只有 `validation.direct_usable === true` 时，才表示三个平台均通过自动校验。
- 票价、开放时间等时效信息即使通过自动校验，发布前仍应提示人工复核。
- 当前版本没有登录和鉴权，部署到公网前需在网关或应用层补充认证。

### 枚举值

```typescript
type Platform = "xiaohongshu" | "video" | "moments";

type SessionStatus =
  | "processing"
  | "success"
  | "partial_failure"
  | "failed";

type ValidationStatus =
  | "passed"
  | "failed"
  | "pending"
  | "not_completed";

type FactType =
  | "era"
  | "date"
  | "person"
  | "place"
  | "organization"
  | "number"
  | "area"
  | "price"
  | "opening_hours"
  | "event"
  | "other";
```

### 前端 TypeScript 类型

```typescript
interface Fact {
  fact_id: string;
  type: FactType;
  source_text: string;
  normalized_value: string;
  source_start: number;
  source_end: number;
  criticality: "critical" | "general";
  review_status: "confirmed" | "pending";
}

interface FactValidationItem {
  fact_id: string;
  source_text: string;
  occurrence: string | null;
  status: "consistent" | "unmarked" | "not_used" | string;
  message: string;
}

interface PlatformValidation {
  platform: Platform;
  status: ValidationStatus;
  direct_usable: boolean;
  fact_coverage: number;
  details: FactValidationItem[];
  issues: string[];
}

interface ValidationSummary {
  status: ValidationStatus;
  direct_usable: boolean;
  platforms: Partial<Record<Platform, PlatformValidation>>;
}

interface XiaohongshuContent {
  titles: string[];
  body: string;
  tags: string[];
  cover_suggestion: string;
}

interface VideoShot {
  time_range: string;
  visual: string;
  narration: string;
  subtitle_keywords: string[];
  pace: string;
}

interface VideoContent {
  duration_seconds: number;
  bgm_style: string;
  shots: VideoShot[];
}

interface GridShot {
  position: number;
  content: string;
  composition: string;
  color_tone: string;
  shot_size: string;
}

interface MomentsContent {
  poster_quotes: string[];
  body: string;
  grid: GridShot[];
  pinned_tips: Record<string, string>;
}

type PlatformContent =
  | XiaohongshuContent
  | VideoContent
  | MomentsContent;

interface OutputView {
  output_id: string;
  platform: Platform;
  content: PlatformContent;
  version: number;
  validation_status: ValidationStatus;
  validation_detail: PlatformValidation;
  created_at: string;
}

interface SessionView {
  session_id: string;
  created_at: string;
  updated_at: string;
  original_text: string;
  status: SessionStatus;
  user_instruction: string | null;
  model_name: string;
  prompt_version: string;
  facts: Fact[];
  outputs: Partial<Record<Platform, OutputView>>;
  validation: ValidationSummary | null;
  errors: Array<Record<string, unknown>>;
}
```

## API 接口

### 1. 健康检查

```http
GET /health
```

响应 `200 OK`：

```json
{
  "status": "ok",
  "model_mode": "local",
  "database": "ok"
}
```

### 2. 生成三平台内容

```http
POST /api/v1/sessions/generate
Content-Type: application/json
```

请求体：

```json
{
  "original_text": "拙政园位于苏州市，始建于明代，占地78亩。",
  "user_instruction": "整体语气克制，突出人文感"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `original_text` | `string` | 是 | 景区官方讲解词，不能为空，默认最多 12000 字符 |
| `user_instruction` | `string \| null` | 否 | 补充生成要求，最多 1000 字符 |

响应 `201 Created`，返回完整 `SessionView`。以下为结构示意；为控制篇幅，只展示一个平台输出：

```json
{
  "session_id": "f2574298-674c-41d8-acb0-2ca5c8be9fe1",
  "created_at": "2026-07-25T07:30:00+00:00",
  "updated_at": "2026-07-25T07:30:02+00:00",
  "original_text": "拙政园位于苏州市，始建于明代，占地78亩。",
  "status": "success",
  "user_instruction": "整体语气克制，突出人文感",
  "model_name": "gpt-5-mini",
  "prompt_version": "2026-07-25.v1",
  "facts": [
    {
      "fact_id": "F001",
      "type": "place",
      "source_text": "苏州市",
      "normalized_value": "苏州市",
      "source_start": 5,
      "source_end": 8,
      "criticality": "critical",
      "review_status": "confirmed"
    }
  ],
  "outputs": {
    "xiaohongshu": {
      "output_id": "dd594528-4efd-4ae9-a9d5-753648403a5a",
      "platform": "xiaohongshu",
      "content": {
        "titles": ["标题一", "标题二", "标题三", "标题四", "标题五"],
        "body": "正文中的事实使用〖苏州市〗高亮。",
        "tags": ["#苏州市", "#文旅", "#人文旅行"],
        "cover_suggestion": "使用真实现场图"
      },
      "version": 1,
      "validation_status": "passed",
      "validation_detail": {
        "platform": "xiaohongshu",
        "status": "passed",
        "direct_usable": true,
        "fact_coverage": 1.0,
        "details": [],
        "issues": []
      },
      "created_at": "2026-07-25T07:30:02+00:00"
    }
  },
  "validation": {
    "status": "passed",
    "direct_usable": true,
    "platforms": {
      "xiaohongshu": {
        "platform": "xiaohongshu",
        "status": "passed",
        "direct_usable": true,
        "fact_coverage": 1.0,
        "details": [],
        "issues": []
      },
      "video": {
        "platform": "video",
        "status": "passed",
        "direct_usable": true,
        "fact_coverage": 1.0,
        "details": [],
        "issues": []
      },
      "moments": {
        "platform": "moments",
        "status": "passed",
        "direct_usable": true,
        "fact_coverage": 1.0,
        "details": [],
        "issues": []
      }
    }
  },
  "errors": []
}
```

实际成功响应的 `outputs` 会包含 `xiaohongshu`、`video` 和 `moments` 三个平台。

### 3. 查询会话列表

```http
GET /api/v1/sessions?limit=20&offset=0
```

| 参数 | 默认值 | 范围 | 说明 |
| --- | --- | --- | --- |
| `limit` | `20` | `1-100` | 返回数量 |
| `offset` | `0` | `>= 0` | 分页偏移量 |

响应 `200 OK`：

```json
[
  {
    "session_id": "f2574298-674c-41d8-acb0-2ca5c8be9fe1",
    "created_at": "2026-07-25T07:30:00+00:00",
    "updated_at": "2026-07-25T07:30:02+00:00",
    "status": "success",
    "original_text_preview": "拙政园位于苏州市，始建于明代……"
  }
]
```

### 4. 查询会话详情

```http
GET /api/v1/sessions/{session_id}
```

响应 `200 OK`，返回完整 `SessionView`。前端可保存 `session_id`，在刷新页面后通过此接口恢复事实库、最新平台结果和校验状态。

### 5. 单平台重新生成

```http
POST /api/v1/sessions/{session_id}/outputs/{platform}/regenerate
Content-Type: application/json
```

`platform` 只能是：

- `xiaohongshu`
- `video`
- `moments`

请求体：

```json
{
  "user_instruction": "语气更克制，减少 emoji"
}
```

响应 `200 OK`，返回更新后的完整 `SessionView`。被重新生成的平台 `version` 加一，其他平台的内容和版本保持不变。

## 错误响应

业务错误统一返回：

```json
{
  "error": {
    "code": "session_not_found",
    "message": "会话不存在"
  }
}
```

| HTTP 状态 | `code` | 场景 |
| --- | --- | --- |
| `404` | `session_not_found` | 会话不存在 |
| `422` | `input_too_long` | 讲解词超过配置的字符上限 |
| `422` | `sensitive_information_detected` | 检测到手机号、身份证号或邮箱 |
| `500` | `generation_failed` | 整体生成流程异常 |
| `500` | `regeneration_failed` | 单平台重新生成异常，已有结果不会被覆盖 |

FastAPI 请求格式校验错误使用标准 `detail` 结构：

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "original_text"],
      "msg": "Value error, 讲解词不能为空"
    }
  ]
}
```

## 前端调用示例

```typescript
const API_BASE_URL = "http://127.0.0.1:8000";

export async function generateContent(
  originalText: string,
  userInstruction?: string,
): Promise<SessionView> {
  const response = await fetch(`${API_BASE_URL}/api/v1/sessions/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      original_text: originalText,
      user_instruction: userInstruction ?? null,
    }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error?.message ?? data.detail?.[0]?.msg ?? "生成失败");
  }
  return data as SessionView;
}
```

事实高亮可以直接识别 `〖` 和 `〗`，也可以根据 `facts[].source_start/source_end` 在原始讲解词中定位。

## 数据存储

默认生成两个 SQLite 文件：

| 文件 | 内容 |
| --- | --- |
| `data/wenan.sqlite3` | 会话、事实、输出版本、校验详情、运行日志 |
| `data/checkpoints.sqlite3` | LangGraph 执行检查点 |

`data/` 已加入 `.gitignore`。SQLite 适合 Demo 和单机 MVP；需要多实例部署时应迁移到 PostgreSQL 等共享数据库，并替换相应 checkpointer。

## 开发与测试

运行测试：

```powershell
uv run pytest
```

当前测试覆盖：

- 事实抽取与原文位置追溯；
- 手机号和邮箱检测；
- 原文外数字事实拦截；
- 三平台内容生成；
- SQLite 会话恢复；
- 单平台重新生成与版本递增；
- 空输入、敏感信息和不存在会话的接口响应。

## 当前限制

- 不包含前端页面、用户登录、权限和计费。
- 生成接口当前为同步请求，不提供 WebSocket 或 SSE 进度流。
- 不会联网补充讲解词之外的事实。
- 本地确定性模式主要用于联调，不代表模型模式的最终内容质量。
- 自动校验不能替代文旅运营人员对历史事实和时效信息的最终审核。
