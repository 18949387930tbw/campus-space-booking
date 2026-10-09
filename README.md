# 校园场地预约系统 · Campus Space Booking

一个可直接本地运行的全栈项目：FastAPI + SQLModel 后端，React + TypeScript + Vite 前端，
在 SQLite 上以「30 分钟时段」为单位做并发安全的场地预约与管理员审批。

本仓库是在 Full Stack FastAPI Template 基础上改造而来，已经把模板自带的
Items 示例完全替换为真实的「场地 / 预约」领域。

- 后端：[FastAPI](https://fastapi.tiangolo.com) + [SQLModel](https://sqlmodel.tiangolo.com)（SQLite / PostgreSQL 均可）
- 前端：React + TypeScript + Vite + Tailwind + shadcn/ui，客户端由 OpenAPI 自动生成
- 认证：JWT（邮箱 + 密码）
- 测试：pytest（后端，73 个用例）+ 前端 TypeScript 编译校验

[![Test Backend](../../actions/workflows/test-backend.yml/badge.svg)](../../actions/workflows/test-backend.yml)
[![Test Frontend](../../actions/workflows/test-frontend.yml/badge.svg)](../../actions/workflows/test-frontend.yml)

---

## 1. 功能一览

| 角色 | 能力 |
| --- | --- |
| 所有登录用户 | 查看场地列表、创建预约申请、查看/取消自己的预约 |
| 管理员（`role=admin` 或 `is_superuser`） | 上面的全部 + 场地增删改、查看全部预约、审批（通过 / 驳回）、删除预约 |

预约规则（由后端强制执行）：

- 时段粒度为 **30 分钟**，单次预约最长 **4 小时**
- 时间必须落在场地的开放时间内（`open_time` ~ `close_time`）
- 同一场地同一时段不能被重复预约（数据库唯一约束兜底）
- 同一用户不能有互相重叠的进行中预约
- 预约状态机：`pending → approved / rejected / cancelled`，`approved → cancelled`
- 驳回或取消时会释放已占用的时段

---

## 2. 快速开始（Windows，本地运行，无需 Docker）

### 2.1 一键脚本

```powershell
# 首次：创建 venv、装依赖、建库并写入种子数据
.\setup-local.ps1

# 启动前后端（各开一个隐藏窗口，日志写到 backend\*.log / frontend\*.log）
.\run-local.ps1

# 需要单独启动时
.\run-local.ps1 -Backend
.\run-local.ps1 -Frontend

# 停止
.\stop-local.ps1
```

打开：

- 前端开发服务器：http://localhost:5173
- 后端 API 文档：http://localhost:8000/docs
- 登录账号：**`admin@example.com` / `admin12345`**（超级管理员）

### 2.2 手动步骤

```powershell
# 后端
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m app.initial_data     # 建表 + 管理员 + 种子场地
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# 前端（另开一个终端）
cd frontend
npm install
npm run dev
```

### 2.3 只跑“打包后的成品”

```powershell
cd frontend
npm run build      # 产物输出到 backend/app/frontend
cd ..\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# 然后直接访问 http://localhost:8000 ，前端由 FastAPI 一起托管
```

---

## 3. 数据库

默认使用 SQLite，**开箱即用**：仓库根目录的 `.env` 中

```env
DATABASE_URL=sqlite:///./campus_booking.db
```

初始化时会自动写入 3 个演示场地和一个管理员账号：

| 场地 | 位置 | 开放时间 |
| --- | --- | --- |
| Library 101 | Library Building, Floor 1 | 08:00 - 22:00 |
| Innovation Lab | Innovation Center | 09:00 - 21:00 |
| Sports Hall | Sports Center | 07:00 - 23:00 |

想换成 PostgreSQL 时，只要把 `DATABASE_URL` 改成 `postgresql+psycopg://...` 即可，
其余代码无需修改。

---

## 4. API 一览

所有接口都在 `/api/v1` 下，除登录外都需要 `Authorization: Bearer <token>`。

### 场地 `/api/v1/venues`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/venues/` | 登录用户 | 分页列出场地 |
| POST | `/venues/` | 管理员 | 新建场地 |
| GET | `/venues/{venue_id}` | 登录用户 | 查看单个场地 |
| PATCH | `/venues/{venue_id}` | 管理员 | 修改场地 |
| DELETE | `/venues/{venue_id}` | 管理员 | 删除场地（级联删除其预约） |

### 预约 `/api/v1/bookings`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/bookings/` | 登录用户 | 普通用户只看自己，管理员看全部；可用 `status` 过滤 |
| POST | `/bookings/` | 登录用户 | 创建预约（默认 `pending`） |
| GET | `/bookings/{booking_id}` | 本人 / 管理员 | 查看单条预约 |
| POST | `/bookings/{booking_id}/approve` | 管理员 | 通过 |
| POST | `/bookings/{booking_id}/reject` | 管理员 | 驳回（释放时段） |
| POST | `/bookings/{booking_id}/cancel` | 本人 / 管理员 | 取消（释放时段） |
| DELETE | `/bookings/{booking_id}` | 管理员 | 删除记录 |

`POST /bookings/` 请求体示例：

```json
{
  "venue_id": "00000000-0000-0000-0000-000000000000",
  "start_time": "2026-10-12T14:00",
  "end_time": "2026-10-12T15:30",
  "purpose": "小组讨论"
}
```

冲突会返回明确的错误码：`409`（时段被占 / 用户时间冲突 / 非法状态流转），
`422`（时间不对齐、超过 4 小时、超出开放时间等），`403`（越权）。

---

## 5. 核心设计（面试可以讲的点）

1. **时段离散化**：一次预约按 30 分钟切片写入 `booking_slot` 表，每个片段一行。
   `(venue_id, slot_start)` 上加**唯一约束**，即使服务层判断出现竞态，
   数据库也会拒绝重复占位，`IntegrityError` 会被转换成业务异常 `VENUE_SLOT_CONFLICT`。
2. **并发安全**：并发下单测试 `backend/tests/services/test_booking_concurrency.py`
   用多线程同时抢同一时段，断言只有一个成功、其余都拿到冲突错误。
   SQLite 下通过 WAL + `busy_timeout=5000` 降低写锁冲突。
3. **服务层与 API 解耦**：领域逻辑集中在 `app/services/*_service.py`，
   路由层只做鉴权与异常 → HTTP 状态码映射，便于单测。
4. **状态机收口**：所有状态流转都经过 `transition_booking()`，
   非法流转（如已驳回再通过）统一抛 `BookingStateError`。
5. **契约驱动前端**：后端导出 OpenAPI，前端 `npm run generate-client`
   生成类型安全的 SDK，接口改动会在 `tsc` 阶段直接报错。

---

## 6. 运行测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q                 # 全量，约 73 个用例
.\.venv\Scripts\python.exe -m pytest tests\services\test_booking_concurrency.py -q   # 并发安全
```

测试使用独立的 `backend/test.db`，跑完自动删除，不影响开发库。

前端类型检查与构建：

```powershell
cd frontend
npm run build
```

---

## 7. 目录结构

```
backend/
  app/
    api/routes/       # venues.py / bookings.py / login.py / users.py ...
    core/             # 配置、数据库引擎、安全
    models.py         # User / Venue / Booking / BookingSlot 领域模型
    services/         # venue_service.py / booking_service.py 业务逻辑
  tests/              # 单元 + API + 并发测试
frontend/
  src/
    client/           # 由 OpenAPI 生成的类型安全 SDK（不要手改）
    components/       # Venues/ Bookings/ Admin/ ...
    routes/           # TanStack Router 页面
docs/superpowers/
  specs/              # 设计规格
  plans/              # 分步实施计划
```

---

## 8. 常用环境变量（仓库根目录 `.env`，由 `backend` 以 `env_file="../.env"` 读取）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./campus_booking.db` | 数据库连接串 |
| `SECRET_KEY` | `changethis` | JWT 签名密钥，**生产必须改** |
| `FIRST_SUPERUSER` | `admin@example.com` | 初始管理员邮箱 |
| `FIRST_SUPERUSER_PASSWORD` | `admin12345` | 初始管理员密码 |
| `BACKEND_CORS_ORIGINS` | `http://localhost:5173` | 允许的前端来源 |
