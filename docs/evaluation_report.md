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
| 评测运行 ID（当前 Docker 数据库） | 1 |
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
   .venv\Scripts\python.exe scripts\import_fastapi_template_corpus.py --source-dir D:\source-cache\fastapi-template --cases-output evaluation_sets\fastapi_template_public_docs.json --env-file .env.docker
   ```

3. 执行上述评测命令；系统会在 MySQL 中保存新的评测运行和逐题结果。

题集为人工编写、单一预期文档标注，未使用真实业务用户会话。它适合做固定版本上的可复现检索回归，不代表生产业务准确率。

## 回答质量评测（已实际运行）

回答层评测与上面的无模型检索基线分开。我们先用当前已导入并完成索引的 7 份公开文档，实际调用 RepoMind `/ask` 生成 15 条问答样本，再由人工根据同一批公开文档补充参考答案。样本文件为 `evaluation_sets/answer_quality.fastapi_public.json`，参考答案原始映射保存在 `evaluation_sets/answer_quality.fastapi_public.references.json`。

生成真实问答样本的命令如下（需要本地 Docker 服务已启动；凭据只从本地环境文件读取，不写入仓库）：

```powershell
.venv\Scripts\python.exe scripts\build_answer_quality_cases.py `
  --retrieval-cases evaluation_sets\fastapi_template_public_docs.json `
  --knowledge-base-id <当前导入语料的知识库 ID> `
  --output evaluation_sets\answer_quality.fastapi_public.json `
  --env-file .env.docker
```

`scripts/evaluate_ragas_answers.py` 接收已完成的问答样本：

```json
{
  "case_key": "case-1",
  "user_input": "用户问题",
  "retrieved_contexts": ["检索到的文档片段"],
  "response": "系统回答",
  "reference": "人工参考答案"
}
```

本次实际运行命令为：

```powershell
.venv\Scripts\python.exe scripts\evaluate_ragas_answers.py `
  --cases evaluation_sets\answer_quality.fastapi_public.json `
  --allow-model-calls --answer-relevancy --factual-correctness
```

本次 15 条样本的聚合结果如下：

| 指标 | 结果 |
| --- | ---: |
| Faithfulness | 0.9233 |
| Answer Relevancy | 0.5624 |
| Factual Correctness | 0.6287 |

这些指标由 Ragas 使用评测模型（Answer Relevancy 额外使用本地 Chroma 向量模型）计算，会产生模型调用成本和波动；它们衡量的是固定公开语料上的当前回答基线，不是生产业务准确率。简历可以在注明数据集与样本数的前提下引用，不能把它们表述成真实企业项目的线上效果。
