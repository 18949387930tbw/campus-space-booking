# 校园场地预约系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 `full-stack-fastapi-template` 仓库内，把通用 Item 示例改造成支持角色权限、预约状态机和并发安全的校园场地预约系统。

**Architecture:** 保留 FastAPI、SQLModel、React 和现有认证体系。后端新增 `Venue`、`Booking`、`BookingSlot` 模型，所有预约通过 `booking_service` 的统一事务入口创建；数据库用 `(venue_id, slot_start)` 唯一约束和场地锁保证并发安全。前端在原 React 工程中替换 Items 页面。

**Tech Stack:** Python 3.13, FastAPI, SQLModel, SQLite（本地）/ PostgreSQL（兼容）, React, TypeScript, TanStack Router/Query, pytest, npm/Vite。

**Spec:** `docs/superpowers/specs/2026-10-09-campus-space-booking-design.md`

## Global Constraints

- 不新建仓库，不创建第二套代码目录。
- 不删除现有登录、JWT、用户管理、密码重置和本地脚本。
- 本地必须支持 SQLite 零配置运行；不得要求 Docker。
- 时间统一按 UTC 处理；预约时间必须对齐 30 分钟边界。
- 单个预约最长 4 小时。
- `pending` 和 `approved` 占用时间槽；`rejected` 和 `cancelled` 释放时间槽。
- 并发测试必须证明同一场地同一时段只能成功一个预约。
- 每个任务先写失败测试，再写最小实现，再运行相关测试。
- 前端生成文件 `frontend/src/client/` 不手改，使用 `npm run generate-client`。

---

### Task 1: 领域模型与 SQLite 连接配置

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/core/db.py`
- Modify: `.env`
- Create: `backend/tests/models/__init__.py`
- Create: `backend/tests/models/test_booking_models.py`

**Interfaces:**
- Produces: `UserRole`, `Venue`, `Booking`, `BookingSlot`, `BookingStatus`, `VenueCreate`, `VenuePublic`, `BookingCreate`, `BookingPublic`
- Produces: `Venue.bookings`, `Booking.slots`, `User.bookings` relationships

**Before Task 1:** install backend test dependencies:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install pytest
```

- [ ] **Step 1: Write failing model tests**

```python
from datetime import UTC, datetime, time, timedelta
import uuid

from sqlmodel import Session, SQLModel, create_engine

from app.models import Booking, BookingSlot, BookingStatus, User, UserRole, Venue


def test_booking_slot_unique_constraint() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    owner_id = uuid.uuid4()
    venue_id = uuid.uuid4()
    booking_id = uuid.uuid4()

    with Session(engine) as session:
        session.add(User(email="u@example.com", hashed_password="x", id=owner_id))
        session.add(Venue(id=venue_id, name="A101", location="A", capacity=30, open_time=time(8, 0), close_time=time(22, 0)))
        session.add(
            Booking(
                id=booking_id,
                venue_id=venue_id,
                user_id=owner_id,
                start_time=datetime(2026, 10, 10, 10, 0),
                end_time=datetime(2026, 10, 10, 11, 0),
                purpose="study",
                status=BookingStatus.pending,
            )
        )
        session.add(
            BookingSlot(booking_id=booking_id, venue_id=venue_id, slot_start=datetime(2026, 10, 10, 10, 0))
        )
        session.commit()


def test_user_defaults_to_student() -> None:
    user = User(email="student@example.com", hashed_password="x")
    assert user.role == UserRole.student
```

- [ ] **Step 2: Run the tests and verify failure**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/models/test_booking_models.py -q
```

Expected: collection/import failure because `Venue`, `Booking`, `BookingSlot`, and `UserRole` do not exist.

- [ ] **Step 3: Implement the models**

In `backend/app/models.py`:

```python
class UserRole(str, Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class BookingStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class VenueBase(SQLModel):
    name: str = Field(unique=True, index=True, max_length=100)
    location: str = Field(max_length=255)
    capacity: int = Field(gt=0)
    open_time: time
    close_time: time
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class Venue(VenueBase, table=True):
    __tablename__ = "venue"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)
    bookings: list["Booking"] = Relationship(back_populates="venue", cascade_delete=True)
    slots: list["BookingSlot"] = Relationship(back_populates="venue", cascade_delete=True)


class BookingBase(SQLModel):
    venue_id: uuid.UUID = Field(foreign_key="venue.id", index=True)
    start_time: datetime = Field(index=True)
    end_time: datetime = Field(index=True)
    purpose: str = Field(min_length=1, max_length=255)


class Booking(BookingBase, table=True):
    __tablename__ = "booking"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    status: BookingStatus = Field(default=BookingStatus.pending, index=True)
    decided_by_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    decided_at: datetime | None = None
    created_at: datetime = Field(default_factory=get_datetime_utc)
    user: User | None = Relationship(back_populates="bookings")
    venue: Venue | None = Relationship(back_populates="bookings")
    slots: list["BookingSlot"] = Relationship(back_populates="booking", cascade_delete=True)


class BookingSlot(SQLModel, table=True):
    __tablename__ = "booking_slot"
    __table_args__ = (
        UniqueConstraint("venue_id", "slot_start", name="uq_booking_slot_venue_start"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    booking_id: uuid.UUID = Field(foreign_key="booking.id", index=True)
    venue_id: uuid.UUID = Field(foreign_key="venue.id", index=True)
    slot_start: datetime = Field(index=True)
    booking: Booking | None = Relationship(back_populates="slots")
    venue: Venue | None = Relationship(back_populates="slots")
```

Add `role: UserRole = UserRole.student` to `UserBase`, add `bookings: list["Booking"]` to `User`, and change `.env` to:

```dotenv
DATABASE_URL=sqlite:///./campus_booking.db
```

- [ ] **Step 4: Run the model tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/models/test_booking_models.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models.py backend/app/core/db.py .env backend/tests/models
git commit -m "feat: add booking domain models"
```

### Task 2: SQLite 写事务安全与测试数据库隔离

**Files:**
- Modify: `backend/app/core/db.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_sqlite_config.py`
- Modify: `setup-local.ps1`

**Interfaces:**
- Produces: SQLite WAL, `busy_timeout=5000`, `BEGIN IMMEDIATE` on write transactions
- Produces: test database isolation so tests never depend on `app.db`

- [ ] **Step 1: Write a failing connection test**

```python
from app.core.db import engine


def test_sqlite_uses_wal() -> None:
    with engine.connect() as connection:
        journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar()
        busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar()
    assert journal_mode.lower() == "wal"
    assert busy_timeout >= 5000
```

- [ ] **Step 2: Run it and verify failure**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_sqlite_config.py -q`

Expected: FAIL because WAL and busy timeout are not configured.

- [ ] **Step 3: Implement SQLite configuration**

In `backend/app/core/db.py`, after creating the engine:

```python
if database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _begin_immediate(connection):
        connection.exec_driver_sql("BEGIN IMMEDIATE")
```

In `backend/tests/conftest.py`, set `os.environ["DATABASE_URL"] = "sqlite:///./test.db"` before importing `app` modules. At session teardown, call `engine.dispose()` and remove `backend/test.db`.

- [ ] **Step 4: Run the connection test and existing tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: PASS for model tests and existing authentication tests.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/core/db.py backend/tests/conftest.py setup-local.ps1
git commit -m "test: isolate sqlite tests and configure write locking"
```

### Task 3: 场地 CRUD、分页和权限

**Files:**
- Create: `backend/app/api/routes/venues.py`
- Create: `backend/app/services/venue_service.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/app/api/deps.py`
- Create: `backend/tests/api/routes/test_venues.py`
- Create: `backend/tests/utils/venue.py`

**Interfaces:**
- Consumes: `Venue`, `VenueCreate`, `VenueUpdate`, `VenuePublic`, `VenuesPublic`
- Produces: `GET/POST /api/v1/venues/`, `GET/PATCH/DELETE /api/v1/venues/{venue_id}`
- Produces: `CurrentAdmin` dependency

- [ ] **Step 1: Write failing API tests**

```python
def test_create_venue_as_admin(client, superuser_token_headers):
    response = client.post(
        "/api/v1/venues/",
        headers=superuser_token_headers,
        json={
            "name": "Library 101",
            "location": "Library Building",
            "capacity": 40,
            "open_time": "08:00:00",
            "close_time": "22:00:00",
        },
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Library 101"


def test_create_venue_as_student_is_forbidden(client, normal_user_token_headers):
    response = client.post(
        "/api/v1/venues/",
        headers=normal_user_token_headers,
        json={
            "name": "Forbidden",
            "location": "A",
            "capacity": 10,
            "open_time": "08:00:00",
            "close_time": "22:00:00",
        },
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/api/routes/test_venues.py -q`

Expected: `404 Not Found` or import failure because the route does not exist.

- [ ] **Step 3: Implement dependency and routes**

In `backend/app/api/deps.py`:

```python
def get_current_admin(current_user: CurrentUser) -> User:
    if not current_user.is_superuser and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user


CurrentAdmin = Annotated[User, Depends(get_current_admin)]
```

In `backend/app/api/routes/venues.py`, implement list/create/read/update/delete with `session.exec(select(...))`, `count`, `offset`, `limit`, and `VenuePublic.model_validate`. Register `venues.router` in `backend/app/api/main.py`.

- [ ] **Step 4: Run the venue tests**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/api/routes/test_venues.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/api/routes/venues.py backend/app/services/venue_service.py backend/app/api/main.py backend/app/api/deps.py backend/tests
git commit -m "feat: add venue management api"
```

### Task 4: 预约时间规则与时间槽服务

**Files:**
- Create: `backend/app/services/booking_service.py`
- Create: `backend/tests/services/__init__.py`
- Create: `backend/tests/services/test_booking_rules.py`

**Interfaces:**
- Produces: `validate_booking_window(venue, start_time, end_time, now=None) -> None`
- Produces: `build_slots(start_time, end_time) -> list[datetime]`
- Produces: `find_overlap(session, venue_id, start_time, end_time) -> Booking | None`
- Produces: `create_booking(session, user, data) -> Booking`

- [ ] **Step 1: Write failing rule tests**

```python
def test_build_slots_uses_half_open_interval():
    start = datetime(2026, 10, 10, 10, 0)
    end = datetime(2026, 10, 10, 11, 0)
    assert build_slots(start, end) == [start, datetime(2026, 10, 10, 10, 30)]


def test_build_slots_rejects_unaligned_time():
    with pytest.raises(BookingValidationError):
        build_slots(datetime(2026, 10, 10, 10, 7), datetime(2026, 10, 10, 11, 0))


def test_touching_intervals_do_not_overlap(session, venue, owner):
    first = create_booking(session, owner, BookingCreate(...10:00, 11:00...))
    second = create_booking(session, owner, BookingCreate(...11:00, 12:00...))
    assert first.id != second.id
```

- [ ] **Step 2: Run and verify failure**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/services/test_booking_rules.py -q`

Expected: FAIL because `booking_service` is missing.

- [ ] **Step 3: Implement the service**

Core signatures:

```python
SLOT_MINUTES = 30
MAX_BOOKING_HOURS = 4


def build_slots(start_time: datetime, end_time: datetime) -> list[datetime]:
    current = start_time
    slots: list[datetime] = []
    while current < end_time:
        slots.append(current)
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


def validate_booking_window(venue: Venue, start_time: datetime, end_time: datetime) -> None:
    if end_time <= start_time:
        raise BookingValidationError("end_time must be after start_time")
    if end_time - start_time > timedelta(hours=MAX_BOOKING_HOURS):
        raise BookingValidationError("booking is longer than 4 hours")
    if start_time.minute % 30 or start_time.second or start_time.microsecond:
        raise BookingValidationError("start_time must align to 30 minutes")
    if not (venue.open_time <= start_time.time() and end_time.time() <= venue.close_time):
        raise BookingValidationError("booking is outside venue hours")


def create_booking(session: Session, user: User, data: BookingCreate) -> Booking:
    # Check user overlap, lock venue for PostgreSQL, check overlap, add booking and slots, commit.
```

For PostgreSQL, use `select(Venue).where(Venue.id == data.venue_id).with_for_update()`; for SQLite, the connection-level `BEGIN IMMEDIATE` from Task 2 serializes writes.

- [ ] **Step 4: Run rule tests**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/services/test_booking_rules.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/booking_service.py backend/tests/services
git commit -m "feat: add booking window and slot service"
```

### Task 5: 预约 API、状态机和 RBAC

**Files:**
- Create: `backend/app/api/routes/bookings.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/app/services/booking_service.py`
- Create: `backend/tests/api/routes/test_bookings.py`

**Interfaces:**
- Produces: `POST /api/v1/bookings/`
- Produces: `GET /api/v1/bookings/`
- Produces: `POST /api/v1/bookings/{id}/approve`
- Produces: `POST /api/v1/bookings/{id}/reject`
- Produces: `POST /api/v1/bookings/{id}/cancel`
- Produces: `transition_booking(session, booking, actor, action) -> Booking`

- [ ] **Step 1: Write failing API tests**

```python
def test_student_cannot_approve(client, normal_user_token_headers, pending_booking):
    response = client.post(
        f"/api/v1/bookings/{pending_booking.id}/approve",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403


def test_admin_approves_pending_booking(client, superuser_token_headers, pending_booking):
    response = client.post(
        f"/api/v1/bookings/{pending_booking.id}/approve",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_cancelled_booking_cannot_be_approved(client, superuser_token_headers, cancelled_booking):
    response = client.post(
        f"/api/v1/bookings/{cancelled_booking.id}/approve",
        headers=superuser_token_headers,
    )
    assert response.status_code == 409
```

- [ ] **Step 2: Run and verify failure**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/api/routes/test_bookings.py -q`

Expected: 404 or missing fixture failure because the route does not exist.

- [ ] **Step 3: Implement transition rules**

```python
ALLOWED_TRANSITIONS = {
    BookingStatus.pending: {BookingStatus.approved, BookingStatus.rejected, BookingStatus.cancelled},
    BookingStatus.approved: {BookingStatus.cancelled},
}


def transition_booking(session, booking, actor, action):
    target = {"approve": BookingStatus.approved, "reject": BookingStatus.rejected, "cancel": BookingStatus.cancelled}[action]
    if target not in ALLOWED_TRANSITIONS.get(booking.status, set()):
        raise BookingStateError("invalid booking state transition")
    if action in {"approve", "reject"} and not actor.is_superuser and actor.role != UserRole.admin:
        raise BookingPermissionError()
    if action == "cancel" and booking.user_id != actor.id and not actor.is_superuser and actor.role != UserRole.admin:
        raise BookingPermissionError()
    if target in {BookingStatus.rejected, BookingStatus.cancelled}:
        session.exec(delete(BookingSlot).where(BookingSlot.booking_id == booking.id))
    booking.status = target
    booking.decided_by_id = actor.id
    booking.decided_at = get_datetime_utc()
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking
```

- [ ] **Step 4: Implement routes and run tests**

Use dependencies for `CurrentUser` and `CurrentAdmin`, map service exceptions to `HTTPException` status codes, and register the router in `backend/app/api/main.py`.

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/api/routes/test_bookings.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/api/routes/bookings.py backend/app/api/main.py backend/app/services/booking_service.py backend/tests/api/routes/test_bookings.py
git commit -m "feat: add booking api and state machine"
```

### Task 6: 并发预约测试与故障恢复

**Files:**
- Create: `backend/tests/services/test_booking_concurrency.py`
- Modify: `backend/app/services/booking_service.py`

**Interfaces:**
- Consumes: `create_booking`
- Produces: conflict behavior that maps `IntegrityError` to `BookingConflictError`

- [ ] **Step 1: Write the failing concurrency test**

```python
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

def test_two_concurrent_requests_only_one_succeeds(engine, venue, two_users):
    barrier = Barrier(2)

    def attempt(user):
        with Session(engine) as session:
            barrier.wait()
            try:
                return create_booking(session, user, data)
            except BookingConflictError:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, two_users))

    assert sum(result is not None for result in results) == 1
```

- [ ] **Step 2: Run and verify failure**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/services/test_booking_concurrency.py -q`

Expected: FAIL because the service currently allows two bookings or does not map the uniqueness error.

- [ ] **Step 3: Make conflict handling explicit**

Wrap slot insertion and commit in `try/except IntegrityError` and raise `BookingConflictError("BOOKING_CONFLICT")`. Never expose raw SQLAlchemy errors through the API.

- [ ] **Step 4: Run the concurrency test repeatedly**

Run:

```powershell
cd backend
1..10 | ForEach-Object { .\.venv\Scripts\python.exe -m pytest tests/services/test_booking_concurrency.py -q }
```

Expected: every run passes.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/booking_service.py backend/tests/services/test_booking_concurrency.py
git commit -m "test: verify concurrent booking safety"
```

### Task 7: 删除 Item 后端业务并更新用户测试

**Files:**
- Delete: `backend/app/api/routes/items.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/app/crud.py`
- Modify: `backend/app/models.py`
- Delete/replace: `backend/tests/api/routes/test_items.py`
- Delete/replace: `backend/tests/utils/item.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_sqlite_config.py`

- [ ] **Step 1: Write a regression check**

Add an assertion to a new backend test:

```python
def test_item_route_is_removed(client):
    response = client.get("/api/v1/items/")
    assert response.status_code == 404
```

- [ ] **Step 2: Run and verify failure**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest -q`

Expected: FAIL while Item route is still registered.

- [ ] **Step 3: Remove Item code**

Remove Item imports, routes, relationships, CRUD functions, test helpers, and Item cleanup fixtures. Keep the database table harmless; do not write a destructive migration.

- [ ] **Step 4: Run the complete backend suite**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend
git commit -m "refactor: replace item demo with booking domain"
```

### Task 8: 前端场地与预约页面

**Files:**
- Create: `frontend/src/routes/_layout/venues.tsx`
- Create: `frontend/src/routes/_layout/bookings.tsx`
- Create: `frontend/src/routes/_layout/admin/bookings.tsx`
- Create: `frontend/src/routes/_layout/admin/venues.tsx`
- Create: `frontend/src/components/Venues/*`
- Create: `frontend/src/components/Bookings/*`
- Modify: `frontend/src/components/Sidebar/AppSidebar.tsx`
- Modify: `frontend/src/routeTree.gen.ts` by router generation only
- Generate: `frontend/src/client/*`

- [ ] **Step 1: Generate the frontend client**

Run backend, then run:

```powershell
cd frontend
npm run generate-client
```

Expected: client contains `VenuesService` and `BookingsService` types.

- [ ] **Step 2: Build a minimal failing page test**

Use the existing frontend testing pattern or add a Playwright smoke test asserting the sidebar contains `Venues` and `Bookings`.

Run: `cd frontend; npm test`

Expected: FAIL because the routes are not implemented.

- [ ] **Step 3: Implement pages and forms**

Create pages that call the generated services, display loading/empty/error states, and reuse `DataTable`, dialogs, form controls, and toast patterns already used by the existing Items pages. Keep admin routes guarded by `UsersService.readUserMe()`.

- [ ] **Step 4: Build and test frontend**

Run:

```powershell
cd frontend
npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend
git commit -m "feat: add venue booking frontend"
```

### Task 9: 本地演示数据、README、CI 与最终验收

**Files:**
- Modify: `backend/app/core/db.py`
- Modify: `README.md`
- Modify: `.github/workflows/test-backend.yml`
- Modify: `run-local.ps1`
- Modify: `setup-local.ps1`

- [ ] **Step 1: Add failing smoke checks to the README validation script**

Add a backend test asserting the database seeds three demo venues and the admin account has role `admin`.

- [ ] **Step 2: Run and verify failure**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_seed.py -q`

Expected: FAIL because no demo venues exist.

- [ ] **Step 3: Implement seed data and documentation**

Seed at least:

- `Library 101`
- `Innovation Lab`
- `Sports Hall`

Update README with login credentials, run commands, API routes, concurrency test command, and the design explanation. Update setup script to install pytest/dev dependencies.

- [ ] **Step 4: Run full acceptance**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run build
```

Expected: backend tests pass and frontend build passes.

- [ ] **Step 5: Commit**

```powershell
git add README.md .github/workflows/test-backend.yml run-local.ps1 setup-local.ps1 backend
git commit -m "docs: document and validate campus booking workflow"
```