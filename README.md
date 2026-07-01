# 医学推理自动评分 MVP

> 这是一个用于作品集展示的 GitHub 版本。真实 API Key 不应提交到仓库；运行时请自行复制 `.env.example` 为 `.env` 并填写配置。

## 项目目标

这个项目用于读取医学推理评测题、读取模型回答，并调用 OpenAI-compatible Judge API 自动评分，最后输出 JSON 评分结果。

当前版本支持两种方式：

1. 命令行批量读取 `data/model_answers.json` 后评分。
2. Streamlit 本地页面手动粘贴单条模型回答后评分。

## 文件结构

```text
medical_reasoning_eval/
├── data/
│   ├── questions.json
│   └── model_answers.json
├── src/
│   ├── app.py
│   ├── judge_utils.py
│   └── run_judge.py
├── results/
│   └── judged_results.json
├── .env.example
├── requirements.txt
└── README.md
```

## 如何填写 model_answers.json

如果使用命令行批量评分，把模型回答粘贴到 `data/model_answers.json` 中。示例：

```json
[
  {
    "question_id": "MR-001",
    "model_name": "DeepSeek",
    "model_answer": "这里粘贴模型回答"
  }
]
```

如果有多条回答，可以继续在数组里添加对象。`question_id` 需要和 `data/questions.json` 里的题目 `id` 对应。

如果担心手写 JSON 出错，可以直接使用 Streamlit 页面粘贴回答。

## 如何配置 .env

复制 `.env.example`，新建一个 `.env` 文件：

```text
JUDGE_API_KEY=你的API密钥
JUDGE_BASE_URL=https://api.openai.com/v1
JUDGE_MODEL=你的Judge模型名称
```

如果使用第三方 OpenAI-compatible API，把 `JUDGE_BASE_URL` 和 `JUDGE_MODEL` 改成对应服务提供的值。

## 安装依赖

```powershell
pip install -r requirements.txt
```

## 运行命令行批量评分

```powershell
python src/run_judge.py
```

## 运行 Streamlit 前端

```powershell
streamlit run src/app.py
```

打开页面后，选择题目，点击“复制题目”，选择或输入模型名称，粘贴模型回答，然后点击“开始评分”。

页面底部会显示当前已保存结果的基础汇总和历史评分记录，包括模型平均分、可用率、分数分布、题目平均分、常见错误，以及每条评分的题号、模型、分数和评分理由。
历史评分记录支持下载保存、打开单条详情和删除选中记录。

项目已配置 Streamlit 的 `viewer` 工具栏模式，减少 Clear caches 等开发者菜单或快捷键对复制操作的干扰。

## 生成结果汇总

当 `results/judged_results.json` 中已经有评分结果后，可以运行：

```powershell
python src/summarize_results.py
```

脚本会统计每个模型的平均分、可用率、1-5 分分布、每道题平均分和常见错误类型。

## 生成 Markdown 报告

当评分结果整理完成后，可以运行：

```powershell
python src/generate_report.py
```

脚本会生成适合作品集展示的 Markdown 报告。

## 结果输出位置

评分结果会保存到：

```text
results/judged_results.json
```

汇总结果会保存到：

```text
results/summary.json
```

Markdown 报告会保存到：

```text
results/report.md
```

仓库中保留了示例文件：

```text
results/example_judged_results.json
results/summary.example.json
results/report.md
```

其中 `results/judged_results.json` 是本地运行时生成/更新的文件，默认不提交到 GitHub。
