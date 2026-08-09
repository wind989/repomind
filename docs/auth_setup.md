# 本地管理员与 JWT 操作说明

当前实现为单用户、本地或受信任演示部署：不开放注册，不收集用户资料，只允许由本地环境变量初始化一个管理员。

## 初始化

1. 仅首次执行：

   ```powershell
   .venv\Scripts\python.exe scripts\bootstrap_local_auth.py
   ```

   脚本会向已忽略的 `.env` 写入随机 JWT 密钥、管理员用户名和随机密码，且不会在终端打印密钥或密码。

2. 应用迁移并启动服务：

   ```powershell
   .venv\Scripts\python.exe -m alembic upgrade head
   .venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```

3. 在 PyCharm 中仅查看本地 `.env` 的 `BOOTSTRAP_ADMIN_USERNAME` 和 `BOOTSTRAP_ADMIN_PASSWORD`，不要将它们提交、截图或发送到聊天。

## 登录与 Swagger

- 登录接口：`POST /auth/token`，使用表单字段 `username` 与 `password`。
- 当前用户：`GET /auth/me`。
- 在 Swagger 的 **Authorize** 中输入管理员凭据后，Swagger 会为受保护接口附加 Bearer Token。

访问令牌默认有效期为 60 分钟，可通过 `.env` 的 `ACCESS_TOKEN_EXPIRE_MINUTES` 调整。密码在数据库中只保存 Argon2 哈希，不保存明文；JWT 密钥仅保存在 `.env`。

## 当前限制

这是 P5 的本地管理员认证，不是多用户账号系统：没有注册、找回密码、刷新令牌、角色管理、OAuth 登录或细粒度权限。后续扩展这些能力前需要重新评估数据模型和安全策略。
