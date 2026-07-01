import json
from collections import Counter, defaultdict

from judge_utils import RESULTS_PATH, RESULTS_DIR, read_json, write_json


SUMMARY_PATH = RESULTS_DIR / "summary.json"


def make_empty_model_stats():
    """创建单个模型的统计容器。"""
    return {
        "count": 0,
        "valid_score_count": 0,
        "total_score": 0,
        "usable_count": 0,
        "score_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
    }


def summarize_results(results):
    """汇总评分结果，生成适合作品集展示的基础统计。"""
    model_stats = defaultdict(make_empty_model_stats)
    question_scores = defaultdict(list)
    error_tags = Counter()
    fatal_errors = Counter()

    for item in results:
        model_name = item.get("model_name") or "Unknown"
        question_id = item.get("question_id") or "Unknown"
        score = item.get("score")

        model_stats[model_name]["count"] += 1

        # 只有 1-5 的整数分数才参与平均分和分布统计。
        if isinstance(score, int) and 1 <= score <= 5:
            model_stats[model_name]["valid_score_count"] += 1
            model_stats[model_name]["total_score"] += score
            model_stats[model_name]["score_distribution"][str(score)] += 1
            question_scores[question_id].append(score)

        if item.get("usable") is True:
            model_stats[model_name]["usable_count"] += 1

        for tag in item.get("error_tags", []):
            error_tags[tag] += 1

        for fatal_error in item.get("fatal_errors_found", []):
            fatal_errors[fatal_error] += 1

    models = {}
    for model_name, stats in model_stats.items():
        valid_count = stats["valid_score_count"]
        total_count = stats["count"]

        models[model_name] = {
            "count": total_count,
            "valid_score_count": valid_count,
            "average_score": round(stats["total_score"] / valid_count, 2)
            if valid_count
            else None,
            "usable_rate": round(stats["usable_count"] / total_count, 4)
            if total_count
            else None,
            "score_distribution": stats["score_distribution"],
        }

    questions = {}
    for question_id, scores in question_scores.items():
        questions[question_id] = {
            "valid_score_count": len(scores),
            "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        }

    return {
        "total_results": len(results),
        "valid_score_results": sum(
            1
            for item in results
            if isinstance(item.get("score"), int) and 1 <= item.get("score") <= 5
        ),
        "models": dict(sorted(models.items())),
        "questions": dict(sorted(questions.items())),
        "common_error_tags": dict(error_tags.most_common()),
        "common_fatal_errors": dict(fatal_errors.most_common()),
    }


def main():
    results = read_json(RESULTS_PATH, default=[])
    summary = summarize_results(results)
    write_json(SUMMARY_PATH, summary)

    print(f"已读取 {len(results)} 条评分结果")
    print(f"汇总结果已保存到：{SUMMARY_PATH}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
