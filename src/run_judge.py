from judge_utils import (
    MODEL_ANSWERS_PATH,
    QUESTIONS_PATH,
    RESULTS_PATH,
    build_prompt,
    call_judge,
    make_error_result,
    parse_judge_json,
    read_json,
    write_json,
)


def main():
    """命令行批量评分入口。"""
    questions = read_json(QUESTIONS_PATH)
    model_answers = read_json(MODEL_ANSWERS_PATH)

    # 用题目 id 建立索引，方便快速匹配。
    question_map = {item["id"]: item for item in questions}
    results = []

    for model_answer_item in model_answers:
        question_id = model_answer_item.get("question_id")
        question = question_map.get(question_id)

        if question is None:
            results.append(
                make_error_result(
                    model_answer_item,
                    f"没有找到 question_id 对应的题目：{question_id}",
                )
            )
            continue

        try:
            prompt = build_prompt(question, model_answer_item)
            raw_result = call_judge(prompt)
            results.append(parse_judge_json(raw_result, model_answer_item))
        except Exception as error:
            results.append(make_error_result(model_answer_item, str(error)))

    write_json(RESULTS_PATH, results)
    print(f"评分完成，结果已保存到：{RESULTS_PATH}")


if __name__ == "__main__":
    main()
