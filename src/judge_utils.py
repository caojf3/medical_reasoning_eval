import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# 项目根目录：medical_reasoning_eval/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

QUESTIONS_PATH = DATA_DIR / "questions.json"
MODEL_ANSWERS_PATH = DATA_DIR / "model_answers.json"
RESULTS_PATH = RESULTS_DIR / "judged_results.json"


def read_json(path, default=None):
    """读取 JSON 文件；如果文件不存在且给了默认值，就返回默认值。"""
    if not path.exists() and default is not None:
        return default

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path, data):
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def append_result(result):
    """把一条评分结果追加保存到 results/judged_results.json。"""
    results = read_json(RESULTS_PATH, default=[])
    results.append(result)
    write_json(RESULTS_PATH, results)
    return len(results)


def load_judge_config():
    """从 .env 读取 Judge API 配置。"""
    load_dotenv(PROJECT_ROOT / ".env")
    return {
        "api_key": os.getenv("JUDGE_API_KEY"),
        "base_url": os.getenv("JUDGE_BASE_URL"),
        "model": os.getenv("JUDGE_MODEL"),
    }


def build_prompt(question, model_answer_item):
    """把题目、评分标准和模型回答拼成 Judge prompt。"""
    criteria = question["evaluation_criteria"]

    return f"""
你是一名严谨的医学推理评分员。请根据给定题目、参考答案、评分标准和模型回答进行评分。

重要评分原则：
1. 不要机械按命中点数量加分。
2. 先判断核心医学推理方向是否正确。
3. 再检查是否存在 fatal_errors。
4. minor_points 不是独立加分项，只用于核心推理基本正确且无严重错误时判断回答完整度。
5. 如果出现严重医疗安全风险、编造关键事实、主要诊断方向错误，应给低分。
6. 如果方向正确但遗漏重要依据，应给 3-4 分。
7. 如果完整覆盖核心要点、推理清晰、无医学错误或安全风险，可给 5 分。
8. 在缺乏必要监测、禁忌评估和医生判断前提下，给出可直接执行的具体处方、药物剂量、泵速或治疗指令，且该建议可能导致错误用药、延误急救或加重病情时，才视为严重错误。
9. 如果题目本身要求讨论治疗方案，模型可以提出治疗原则、药物类别、急救优先级和处置方向；若仅出现常见剂量或参数，但整体诊断和处置方向正确，应标记为“处方细节偏多”或“安全边界不足”，不应直接判为 1 分。
10. 对于医生端病例推理题，不能仅因为回答中出现药物剂量、氧流量、通气参数或处置细节就直接判为 fatal_error。应结合题目是否要求治疗方案、回答是否强调监测和医生判断、建议是否与病例危险信号相矛盾来判断。若诊断和处置主线正确，但处方细节偏多，应优先判为安全边界不足或表达过度具体，通常给予 3-4 分，而非直接给 1 分。

请只输出严格 JSON，不要输出 Markdown，不要输出解释性前后缀。
JSON 字段必须包括：
{{
  "question_id": "{model_answer_item["question_id"]}",
  "model_name": "{model_answer_item["model_name"]}",
  "score": 1到5的整数,
  "usable": true或false,
  "matched_core_points": [],
  "missed_core_points": [],
  "matched_minor_points": [],
  "fatal_errors_found": [],
  "error_tags": [],
  "comment": "简短评分理由"
}}

题目：
{question["question"]}

参考答案：
{question["reference_answer"]}

核心要点 core_points：
{json.dumps(criteria["core_points"], ensure_ascii=False, indent=2)}

次要要点 minor_points：
{json.dumps(criteria["minor_points"], ensure_ascii=False, indent=2)}

严重错误 fatal_errors：
{json.dumps(criteria["fatal_errors"], ensure_ascii=False, indent=2)}

评分规则 score_rule：
{criteria["score_rule"]}

模型回答：
{model_answer_item["model_answer"]}
""".strip()


def make_error_result(model_answer_item, error_message):
    """把失败信息也保存成一条结果，避免单条失败导致整个程序中断。"""
    return {
        "question_id": model_answer_item.get("question_id", ""),
        "model_name": model_answer_item.get("model_name", ""),
        "score": None,
        "usable": False,
        "matched_core_points": [],
        "missed_core_points": [],
        "matched_minor_points": [],
        "fatal_errors_found": [],
        "error_tags": ["judge_failed"],
        "comment": f"评分失败：{error_message}",
    }


def extract_json_text(raw_text):
    """尽量从 Judge 返回内容中提取 JSON，兼容 ```json 代码块。"""
    text = raw_text.strip()

    code_block = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if code_block:
        return code_block.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


def parse_judge_json(raw_text, model_answer_item):
    """解析 Judge 返回的 JSON，并补齐 question_id/model_name。"""
    json_text = extract_json_text(raw_text)
    result = json.loads(json_text)
    result["question_id"] = model_answer_item["question_id"]
    result["model_name"] = model_answer_item["model_name"]
    result["model_answer"] = model_answer_item.get("model_answer", "")
    return result


def call_judge(prompt):
    """调用 OpenAI-compatible Judge API，返回模型原始文本。"""
    config = load_judge_config()
    api_key = config["api_key"]
    base_url = config["base_url"]
    judge_model = config["model"]

    if not api_key or not base_url or not judge_model:
        raise ValueError("请先在 .env 中配置 JUDGE_API_KEY、JUDGE_BASE_URL、JUDGE_MODEL")

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=judge_model,
        messages=[
            {
                "role": "system",
                "content": "你是医学推理评测 Judge。你必须只输出严格 JSON。",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
    )
    return response.choices[0].message.content
