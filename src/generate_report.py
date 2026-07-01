from collections import Counter, defaultdict

from judge_utils import RESULTS_DIR, RESULTS_PATH, read_json
from summarize_results import summarize_results


REPORT_PATH = RESULTS_DIR / "report.md"


def format_percent(value):
    """把 0-1 的比例转成百分比文本。"""
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def build_model_ranking(summary):
    """生成模型排名表。"""
    models = sorted(
        summary["models"].items(),
        key=lambda item: (
            item[1]["average_score"] is not None,
            item[1]["average_score"] or 0,
        ),
        reverse=True,
    )

    lines = [
        "| 排名 | 模型 | 平均分 | 可用率 | 评分条数 | 1分 | 2分 | 3分 | 4分 | 5分 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rank, (model_name, stats) in enumerate(models, start=1):
        distribution = stats["score_distribution"]
        lines.append(
            "| "
            + " | ".join(
                [
                    str(rank),
                    model_name,
                    str(stats["average_score"]),
                    format_percent(stats["usable_rate"]),
                    str(stats["count"]),
                    str(distribution["1"]),
                    str(distribution["2"]),
                    str(distribution["3"]),
                    str(distribution["4"]),
                    str(distribution["5"]),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def build_question_table(summary):
    """生成题目难度表。"""
    questions = sorted(summary["questions"].items())
    lines = [
        "| 题目 | 有效评分数 | 平均分 |",
        "| --- | --- | --- |",
    ]
    for question_id, stats in questions:
        lines.append(
            f"| {question_id} | {stats['valid_score_count']} | {stats['average_score']} |"
        )
    return "\n".join(lines)


def collect_low_score_cases(results):
    """收集低分或不可用案例，便于报告解释模型短板。"""
    cases = []
    for item in results:
        score = item.get("score")
        if item.get("usable") is False or (isinstance(score, int) and score <= 3):
            cases.append(item)
    return cases


def build_case_section(results):
    """生成典型问题案例。"""
    cases = collect_low_score_cases(results)
    if not cases:
        return "暂无 3 分及以下或 unusable 的典型低分案例。"

    lines = []
    for item in cases[:8]:
        lines.append(
            f"- **{item.get('model_name', '')} / {item.get('question_id', '')} / "
            f"{item.get('score', '')} 分**：{item.get('comment', '')}"
        )
    return "\n".join(lines)


def build_error_section(results, field_name):
    """统计错误标签或严重错误。"""
    counter = Counter()
    for item in results:
        for value in item.get(field_name, []):
            counter[value] += 1

    if not counter:
        return "暂无记录。"

    return "\n".join([f"- {name}：{count} 次" for name, count in counter.most_common()])


def build_conclusion(summary):
    """生成聚焦模型表现和评测发现的结论。"""
    models = sorted(
        summary["models"].items(),
        key=lambda item: item[1]["average_score"] or 0,
        reverse=True,
    )
    questions = sorted(
        summary["questions"].items(),
        key=lambda item: item[1]["average_score"] or 0,
    )

    if not models or not questions:
        return "当前有效评分结果不足，暂不生成模型表现结论。"

    best_model, best_stats = models[0]
    weakest_model, weakest_stats = models[-1]
    hardest_question, hardest_stats = questions[0]
    easiest_question, easiest_stats = questions[-1]

    return (
        f"本轮评测共覆盖 {summary['valid_score_results']} 条有效评分记录，"
        f"整体上各模型在 5 道医学推理题中的表现存在可见差异。"
        f"{best_model} 当前平均分最高，为 {best_stats['average_score']} 分，"
        f"可用率为 {format_percent(best_stats['usable_rate'])}；"
        f"{weakest_model} 当前平均分最低，为 {weakest_stats['average_score']} 分，"
        f"可用率为 {format_percent(weakest_stats['usable_rate'])}。"
        f"从题目维度看，{hardest_question} 平均分最低，为 {hardest_stats['average_score']} 分，"
        f"说明该题更容易暴露模型在核心推理、优先检查选择或安全边界表达上的差异；"
        f"{easiest_question} 平均分最高，为 {easiest_stats['average_score']} 分，"
        f"说明当前模型在该类问题上的回答一致性较好。"
        "后续分析应重点关注低分案例、错误标签和严重错误记录，结合人工复核判断模型失分是来自诊断方向偏移、核心依据遗漏，还是治疗建议表达过度具体。"
    )


def build_coverage_note(results):
    """说明当前模型和题目覆盖情况。"""
    model_names = sorted({item.get("model_name", "") for item in results if item.get("model_name")})
    question_ids = sorted({item.get("question_id", "") for item in results if item.get("question_id")})

    counts = defaultdict(int)
    for item in results:
        counts[item.get("model_name", "")] += 1

    model_text = "、".join([f"{name}（{counts[name]} 条）" for name in model_names])
    question_text = "、".join(question_ids)
    return model_text, question_text


def generate_report(results):
    """生成适合作品集展示的 Markdown 报告。"""
    summary = summarize_results(results)
    model_text, question_text = build_coverage_note(results)

    return f"""# 医学推理大模型自动评分报告

## 1. 项目概述

本项目用于评估不同大模型在医学病例推理任务中的表现。评测流程为：读取医学推理题库，收集模型回答，调用独立 Judge 模型根据参考答案和评分标准进行结构化评分，并汇总不同模型的表现。

## 2. 评测范围

- 题目数量：{len(summary["questions"])} 道
- 评分记录：{summary["total_results"]} 条
- 有效评分：{summary["valid_score_results"]} 条
- 覆盖题目：{question_text}
- 覆盖模型：{model_text}

## 3. 模型总体表现

{build_model_ranking(summary)}

## 4. 题目表现

{build_question_table(summary)}

## 5. 常见错误类型

{build_error_section(results, "error_tags")}

## 6. 严重错误记录

{build_error_section(results, "fatal_errors_found")}

## 7. 典型低分案例

{build_case_section(results)}

## 8. 初步结论

{build_conclusion(summary)}
"""


def main():
    results = read_json(RESULTS_PATH, default=[])
    report = generate_report(results)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"报告已保存到：{REPORT_PATH}")


if __name__ == "__main__":
    main()
