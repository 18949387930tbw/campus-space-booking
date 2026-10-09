# 校园场地预约系统：现有仓库原地改造设计

- 日期：2026-10-09
- 状态：待用户审查
- 改造仓库：`C:\Users\OMEN\Documents\Codex\2026-10-08\python-python-campus-space-booking-https\outputs\campus-space-booking`
- 改造方式：在该仓库原地升级，不新建项目，不推翻现有登录、用户管理和本地启动脚本
- 目标岗位：后端开发
- 时间预算：一个月中的主项目，占约 70%

## 1. 背景

当前仓库是 `full-stack-fastapi-template`，已经完成本地化修复：SQLite 替代 PostgreSQL、前端 SWC 替代为 Babel、CORS 支持 `localhost` 和 `127.0.0.1`、增加本地启动脚本，并修复了登录后查询用户时的 UUID 类型错误。

当前业务仍然是模板自带的通用 `Item` 示例。它不能体现校园场地预约，也不能作为后端简历项目讲清楚业务建模、权限、事务和并发控制。因此本设计在保留认证和工程基础设施的前提下，彻底替换 `Item` 业务层。

## 2. 目标与非目标

### 目标

1. 保留现有用户注册、登录、JWT、密码重置、管理员用户管理和本地启动能力。
2. 建立 `Venue`、`Booking`、`BookingSlot` 三个核心业务模型。
3. 提供场地管理、预约创建、取消、审批、拒绝、筛选和分页接口。
4. 实现学生、教师、管理员三种角色的权限边界。
5. 用事务、写锁和数据库唯一约束解决并发抢场地问题。
6. 将原 React 页面替换为场地列表、预约列表、我的预约和管理员审批页面。
7. 提供 pytest、并发测试、README 和 GitHub Actions 验证入口。
8. 保持本地 SQLite 零配置可运行，同时保持 PostgreSQL 兼容的代码路径。

### 非目标

1. 不实现支付、短信、第三方校园统一认证。
2. 不实现邮件通知的实际发送；现有邮件能力保持原样。
3. 不在本项目阶段实现多租户、微服务或消息队列。
4. 不要求 Docker 才能运行。
5. 不保留原 `Item` 页面作为第二套业务；设计完成后按新业务替换。

## 3. 业务模型

### UserRole

新增角色枚举：

- `student`：默认角色，可查看场地、创建和取消自己的预约。
- `teacher`：可查看场地、创建和取消自己的预约。
- `admin`：管理场地、审批预约、取消任意预约、查看全部数据。

现有 `is_superuser` 字段保留，用于兼容模板认证逻辑。管理员判断统一由权限依赖完成，业务代码不直接散落 `is_superuser` 判断。

### Venue

场地字段：

- `id: UUID`
- `name: str`
- `location: str`
- `capacity: int`
- `open_time: time`
- `close_time: time`
- `is_active: bool`
- `description: str | None`
- `created_at: datetime`

规则：`name` 非空且唯一，`capacity > 0`，`open_time < close_time`。

### BookingStatus

预约状态：

- `pending`：已创建，等待管理员审批，占用时间槽。
- `approved`：审批通过，占用时间槽。
- `rejected`：审批拒绝，已释放时间槽。
- `cancelled`：用户或管理员取消，已释放时间槽。

状态转换只允许：

- `pending -> approved`
- `pending -> rejected`
- `pending -> cancelled`
- `approved -> cancelled`

`rejected` 和 `cancelled` 为终态，不允许重新审批。

### Booking

预约字段：

- `id: UUID`
- `venue_id: UUID`
- `user_id: UUID`
- `start_time: datetime`
- `end_time: datetime`
- `purpose: str`
- `status: BookingStatus`
- `decided_by_id: UUID | None`
- `decided_at: datetime | None`
- `created_at: datetime`

时间和规则：

- 所有时间统一以 UTC 存储，API 接收带时区的 ISO 8601 时间。
- 预约时间区间采用半开区间 `[start_time, end_time)`，`10:00-11:00` 和 `11:00-12:00` 不冲突。
- `end_time > start_time`。
- 开始时间必须晚于当前时间。
- 单次预约最长 4 小时。
- 时间必须落在场地开放时间内。
- 时间必须对齐到 30 分钟边界。
- 每个用户在同一时间段不能预约多个场地；该规则由服务层校验。

### BookingSlot

为避免“先查询再插入”的并发竞态，引入：

- `id: UUID`
- `booking_id: UUID`
- `venue_id: UUID`
- `slot_start: datetime`

每个预约按 30 分钟拆成若干时间槽。数据库对 `(venue_id, slot_start)` 建立唯一约束。`pending` 和 `approved` 预约持有时间槽；`rejected` 或 `cancelled` 时删除时间槽。

## 4. API 设计

### 场地接口

- `GET /api/v1/venues/`：分页、按名称和位置筛选、只返回启用场地给普通用户。
- `POST /api/v1/venues/`：仅管理员创建。
- `GET /api/v1/venues/{venue_id}`：查看场地详情。
- `PATCH /api/v1/venues/{venue_id}`：仅管理员修改。
- `DELETE /api/v1/venues/{venue_id}`：仅管理员停用；有未结束预约时返回冲突。

### 预约接口

- `GET /api/v1/bookings/`：支持 `status`、`venue_id`、`start_date`、`end_date`、`mine`、`skip`、`limit`。
- `POST /api/v1/bookings/`：创建预约，成功后状态为 `pending`。
- `GET /api/v1/bookings/{booking_id}`：本人或管理员查看。
- `POST /api/v1/bookings/{booking_id}/approve`：管理员审批通过。
- `POST /api/v1/bookings/{booking_id}/reject`：管理员拒绝。
- `POST /api/v1/bookings/{booking_id}/cancel`：本人或管理员取消。

错误约定：

- `400`：时间非法、超出开放时间、超过 4 小时、时间未对齐。
- `403`：无权限。
- `404`：场地或预约不存在。
- `409`：时间冲突、重复审批、已取消后继续操作、场地存在未结束预约。

## 5. 并发与一致性设计

这是本项目最重要的后端亮点。

创建预约时，服务层必须在一个事务中完成：

1. 开启事务。
2. 锁定目标场地记录；PostgreSQL 使用行锁，SQLite 使用 `BEGIN IMMEDIATE` 串行化写事务。
3. 校验用户、场地、时间和状态。
4. 检查该时段是否已经存在 `pending` 或 `approved` 的冲突预约。
5. 插入 `Booking`。
6. 批量插入 `BookingSlot`。
7. 提交事务。

唯一约束 `(venue_id, slot_start)` 是最后一道数据库保护。即使未来代码路径遗漏了冲突查询，两个并发事务也不可能同时插入同一个场地时间槽。冲突时返回 `409 BOOKING_CONFLICT`，不允许把数据库异常直接暴露给用户。

测试必须覆盖：

- `10:00-11:00` 与 `11:00-12:00` 可以共存。
- `10:00-11:00` 与 `10:30-11:30` 冲突。
- `pending` 和 `approved` 会占用时间槽。
- `rejected` 和 `cancelled` 不占用时间槽。
- 两个线程同时预约同一场地同一时间，只能成功一个，另一个返回 `409`。
- 并发失败后数据库中没有重复时间槽。

## 6. 权限设计

- 普通用户只能查看和取消自己的预约。
- 普通用户不能创建、修改或停用场地。
- 管理员可以查看所有预约并审批、拒绝、取消。
- 管理员不能审批已经进入终态的预约。
- 所有权限判断集中在依赖或服务层，不在前端做“唯一安全控制”。

## 7. 前端改造

保留现有 React、TanStack Router、TanStack Query、表格和表单组件结构，替换 `Items` 页面：

- `/venues`：场地列表、筛选、详情和预约入口。
- `/bookings`：我的预约和创建预约表单。
- `/admin/bookings`：管理员审批和全部预约视图。
- `/admin/venues`：管理员场地管理。
- 侧边栏删除 `Items`，增加 `Venues` 和 `Bookings`。
- 后端路由稳定后运行 `npm run generate-client` 重新生成客户端类型，不手改生成文件。
- 普通用户看不到管理员入口；前端隐藏不是权限边界，后端仍必须返回 `403`。

## 8. 需要修改的主要位置

后端：

- `backend/app/models.py`：新增模型和枚举，移除 `Item`。
- `backend/app/api/routes/items.py`：由 `venues.py` 和 `bookings.py` 替换。
- `backend/app/api/main.py`：注册新路由。
- `backend/app/api/deps.py`：新增角色权限依赖。
- `backend/app/services/booking_service.py`：新增预约事务和并发控制。
- `backend/app/core/db.py`：SQLite 开启 WAL、`busy_timeout` 和写事务配置。
- `backend/app/crud.py`：移除 Item 相关 CRUD，新增场地和预约数据访问函数。
- `backend/tests/`：替换 Item 测试，增加预约、权限、状态机和并发测试。

前端：

- `frontend/src/components/Items/`：替换为 `Venues/` 和 `Bookings/`。
- `frontend/src/routes/_layout/items.tsx`：替换为 `venues.tsx` 和 `bookings.tsx`。
- `frontend/src/routes/_layout/admin.tsx`：扩展或拆分为管理员审批页面。
- `frontend/src/components/Sidebar/AppSidebar.tsx`：更新菜单。
- `frontend/src/client/`：由 OpenAPI 生成。

文档和 CI：

- `README.md`：写清业务、架构、运行方式和测试命令。
- `.github/workflows/test-backend.yml`：保证 SQLite 测试可执行。
- `docs/`：保留本设计和后续实施计划。

## 9. 测试与验收

必须通过的验收命令：

```powershell
cd backend
python -m pytest
```

前端验收：

```powershell
cd frontend
npm run build
```

验收标准：

1. 管理员可以创建和修改场地。
2. 普通用户只能预约启用场地。
3. 预约创建后占用时间槽，取消或拒绝后释放。
4. 状态机非法操作返回 `409` 或 `400`。
5. 并发测试稳定通过。
6. `GET /docs` 能看到新接口。
7. 本地脚本仍可启动前后端。
8. README 能让新机器按步骤运行。

## 10. 里程碑

- 第 1 周：模型、场地 CRUD、分页筛选、迁移和基础测试。
- 第 2 周：预约创建、冲突检测、时间槽、取消和权限。
- 第 3 周：并发锁、并发测试、状态机和异常处理。
- 第 4 周：前端页面、OpenAPI 客户端、README、CI 和演示数据。

## 11. 简历可讲内容

- 使用 FastAPI + SQLModel 建模校园场地预约领域。
- 设计 30 分钟时间槽和唯一约束，解决并发预约竞态。
- 使用事务、行级锁和 SQLite 写锁保证多数据库环境的一致性。
- 实现 RBAC、预约状态机和 REST API 错误语义。
- 使用 pytest 编写多线程并发测试，验证同一时段只能成功一个预约。