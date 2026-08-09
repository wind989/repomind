# 演示材料与验收清单

## 离线演示（默认）

在项目根目录执行：

```powershell
.venv\Scripts\python.exe scripts\demo_offline.py
```

该脚本运行两个隔离 API 场景：

1. 文档处理、建立 fake 索引、提问、引用和检索日志查询；
2. 对已有问答创建、更新并读取匿名反馈。

它使用内存 SQLite、fake 向量库和 fake 回答服务，不会访问 MySQL、DeepSeek 或网络，因此适合录制或课堂演示。

## 真实本地演示（显式操作）

1. 按 README 填写本地 `.env`，执行迁移并启动 FastAPI。
2. 在 Swagger 创建知识库、文档，上传一份不含秘密的样例文档。
3. 等待文档处理任务为 `completed`，调用索引接口。
4. 调用问答接口，再查看 `GET /retrieval-logs/{id}` 和反馈接口。

第 4 步会调用本地 `.env` 中配置的 DeepSeek 服务，可能产生费用；只有在明确需要真实模型演示时才执行。录制截图或视频前，确认其中不显示 `.env`、请求授权头、数据库密码、API 密钥或敏感文档内容。
