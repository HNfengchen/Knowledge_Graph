# auth —— 用户表 + token 颁发

## 目标

把当前「只验证不签发」的 JWT 流补成完整闭环：注册 / 登录 / 续签 / 注销 + 用户表 + 角色权限 + 密码哈希。spec §4.6 + 设计方案 §7。

## 当前状态

- `src/kg_system/api/deps.py:require_user`：仅 `jwt.decode` 验签 + 过期校验，无任何用户实体查找。
- `require_admin`：与 `settings.ADMIN_TOKEN` 字符串比对，单租户硬编码。
- `require_external`：API Key + IP 白名单（已可用）。
- 无 `/auth/*` 路由，无用户表。

## 范围

- **入**：`POST /auth/login {username, password}`、`POST /auth/refresh {refresh_token}`、`POST /auth/logout`、`POST /auth/register`（可由 admin 控制开关）。
- **出**：`{access_token, refresh_token, expires_in}`。
- **不在范围**：OAuth 第三方接入；MFA；社交登录。

## 子任务

- [ ] **T1：用户表与种子**
  - 表定义见 [storage-postgres.md](./storage-postgres.md) T3 `users.py`：`role` 取 `{user, admin, service}`；密码用 `argon2-cffi` 哈希。
  - Alembic 迁移加超管种子 `admin / <env-provided>`。
  - 验收：迁移后 `SELECT count(*) FROM users WHERE role='admin'` ≥ 1。

- [ ] **T2：JWT 工具**
  - 新增 `src/kg_system/auth/jwt.py`：`create_access_token(sub, role, ttl)`、`create_refresh_token(sub, jti)`。
  - 算法配置：`JWT_ALGORITHM=HS256`，`JWT_ACCESS_TTL=900s`，`JWT_REFRESH_TTL=604800s`。
  - claims：`{sub, role, type: "access"|"refresh", jti, iat, exp}`。
  - 验收：单测覆盖签 / 验 / 过期。

- [ ] **T3：refresh token 黑名单**
  - 注销 / 续签时把旧 `jti` 写入 Redis Set `kg:auth:revoked:{jti}` TTL=refresh ttl。
  - `require_user` 增检查（access token 短不查；refresh 必查）。
  - 验收：注销后旧 token 二次使用 401。

- [ ] **T4：/auth router**
  - 新增 `src/kg_system/api/v1/auth.py`：
    - `POST /login` → 校验密码、签 access+refresh、写 `last_login_at`。
    - `POST /refresh` → 验 refresh、查黑名单、轮换签发。
    - `POST /logout` → 把 refresh jti 拉黑 + 当前 access jti 拉黑（短 TTL）。
    - `POST /register`（admin only）→ 创建用户。
  - 验收：`/login` 错密码 401，正确密码返回 access+refresh。

- [ ] **T5：require_user 升级**
  - 解码 access token → 查 `users` 表确认未禁用 → 把 `User` ORM 注入 `request.state.user`。
  - 角色守卫：`require_role("admin")` 装饰器替换 `ADMIN_TOKEN` 比对。
  - `/api/v1/llm/analyze` 切到 `Depends(require_role("admin"))`。
  - 验收：低权限 403。

- [ ] **T6：密码强度**
  - argon2 参数：`time_cost=2, memory_cost=64*1024, parallelism=2`。
  - 注册接口拒绝 < 12 位 / 弱密码（black-list 检查）。

- [ ] **T7：限流登录**
  - Redis 计数 `kg:auth:fail:{ip}:{minute}`，1 分钟内 5 次失败拉黑 15 分钟。
  - 验收：第 6 次返回 429。

- [ ] **T8：审计**
  - 写 `audit_logs` 表（[storage-postgres.md](./storage-postgres.md) T3）：login_success / login_fail / logout / register。

## 依赖

- [storage-postgres.md](./storage-postgres.md) T1–T3 必须先就绪。
- 复用现有 `core/exceptions.py:AuthError`。

## 参考

- spec §4.6 鉴权要求；§5.3 `api/deps.py`。
- 设计方案 §7。
