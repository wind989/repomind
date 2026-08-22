# 固定公开语料评测报告

## 目的与边界

本报告验证 RepoMind 在一套固定、公开、许可证清晰的技术文档上，能否完成真实的文档导入、索引、混合检索和结果持久化。它不是生产业务数据测试，也不代表对其他项目或中文业务文档的泛化效果。

## 数据集

- 上游：`fastapi/full-stack-fastapi-template`
- 固定提交：`75c388ba1cd60f39b43dd63a73978bae8c69cb87`
- 许可证：MIT
- 文档数量：7 份 Markdown 文档
- 索引片段：210 个
- 人工标注题目：15 条英文检索问题；每条标注一个预期命中的文档标题

具体来源和文档列表见 [公开评测语料来源](corpus_sources.md)。题集文件为 `evaluation_sets/fastapi_template_public_docs.json`，其中保存了实际知识库 ID、问题与预期文档标题，支持复跑。Ragas 评测将预期文档标题作为文档级参考上下文 ID，并对融合候选中的重复文档标题去重。

## 方法

评测使用 RepoMind 已实现的 MySQL 关键词召回、Chroma 向量召回、RRF 融合与确定性重排序；`recall_k=8`。评测脚本计算 Top-1、Recall@8、MRR，以及 Ragas 的文档级 ID-based Context Precision/Recall，并记录每道题正确文档的排名。评测不调用 DeepSeek，因此指标仅衡量检索与上下文排序，未衡量答案 Faithfulness 或 Answer Relevancy。

运行命令：

```powershell
.venv\Scripts\python.exe scripts\evaluate_retrieval.py --cases evaluation_sets\fastapi_template_public_docs.json
```

## 结果

| 指标 | 结果 |
| --- | --- |
| 评测运行 ID | 5 |
| Top-1 命中 | 11 / 15（73.3%） |
| Recall@8 命中 | 15 / 15（100%） |
| MRR | 0.8556 |
| Ragas Context Precision（文档级） | 0.2578 |
| Ragas Context Recall（文档级） | 1.0000 |

4 条未达到 Top-1 的题目中，正确文档仍在前 8 个候选内；原因主要是上游 README、开发与后端说明之间存在内容重叠。MRR 进一步反映了正确文档在完整候选排序中的位置；Ragas Context Precision 则对候选中的非目标文档和目标文档排名进行整体衡量。该结果应作为当前排序基线，而不是通过修改题目后得到的最优分数。

## 复现与限制

1. 先按 README 配置本地 MySQL、Chroma 和依赖。
2. 获取同一固定提交，再导入文档并生成题集：

   ```powershell
   git clone https://github.com/fastapi/full-stack-fastapi-template.git D:\source-cache\fastapi-template
   git -C D:\source-cache\fastapi-template checkout 75c388ba1cd60f39b43dd63a73978bae8c69cb87
   .venv\Scripts\python.exe scripts\import_fastapi_template_corpus.py --source-dir D:\source-cache\fastapi-template --cases-output evaluation_sets\fastapi_template_public_docs.json
   ```

3. 执行上述评测命令；系统会在 MySQL 中保存新的评测运行和逐题结果。

题集为人工编写、单一预期文档标注，未使用真实用户会话。当前 Ragas 只使用 ID-based Context Precision/Recall 做文档级上下文评测，未调用评测模型，也未评测引用充分性、Faithfulness 或 DeepSeek 最终答案。因此，简历与 README 只能陈述本报告中的固定公开语料结果，不能外推为生产准确率。
