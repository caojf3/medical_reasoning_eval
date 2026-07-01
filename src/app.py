import json

import streamlit as st
import streamlit.components.v1 as components

from judge_utils import (
    QUESTIONS_PATH,
    RESULTS_PATH,
    append_result,
    build_prompt,
    call_judge,
    parse_judge_json,
    read_json,
    write_json,
)
from summarize_results import summarize_results


st.set_page_config(page_title="医学推理评分工具", layout="wide")

# 隐藏 Streamlit 默认菜单，避免出现 Clear caches 等与本项目无关的入口。
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)


def show_copy_button(text, button_id):
    """显示一个浏览器复制按钮，用于一键复制题目。"""
    text_json = json.dumps(text, ensure_ascii=False)
    components.html(
        f"""
        <button id="{button_id}" style="
            padding: 0.45rem 0.75rem;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            background: #ffffff;
            cursor: pointer;
            font-size: 14px;
        ">复制题目</button>
        <span id="{button_id}-message" style="margin-left: 10px; color: #0a7f36;"></span>
        <script>
        const button = document.getElementById("{button_id}");
        const message = document.getElementById("{button_id}-message");
        button.onclick = async function() {{
            try {{
                await navigator.clipboard.writeText({text_json});
                message.innerText = "已复制";
            }} catch (error) {{
                message.innerText = "复制失败，请手动选中文本复制";
            }}
        }};
        </script>
        """,
        height=45,
    )


def show_list(title, items):
    """在页面上展示列表字段。"""
    st.subheader(title)
    if not items:
        st.write("无")
        return

    for item in items:
        st.write(f"- {item}")


def get_saved_count():
    """读取当前已经保存的评分条数。"""
    return len(read_json(RESULTS_PATH, default=[]))


def show_summary():
    """展示当前已保存评分结果的汇总统计。"""
    results = read_json(RESULTS_PATH, default=[])
    summary = summarize_results(results)

    st.header("结果汇总")

    col1, col2 = st.columns(2)
    col1.metric("已保存评分数", summary["total_results"])
    col2.metric("有效评分数", summary["valid_score_results"])

    st.subheader("模型表现")
    if summary["models"]:
        for model_name, stats in summary["models"].items():
            with st.expander(f"{model_name}", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("平均分", stats["average_score"])
                col2.metric("可用率", stats["usable_rate"])
                col3.metric("评分条数", stats["count"])
                st.write("1-5 分分布：")
                st.json(stats["score_distribution"], expanded=False)
    else:
        st.write("暂无可汇总的模型结果。")

    st.subheader("题目表现")
    if summary["questions"]:
        st.json(summary["questions"], expanded=False)
    else:
        st.write("暂无可汇总的题目结果。")

    st.subheader("常见错误")
    col1, col2 = st.columns(2)
    with col1:
        st.write("错误标签")
        st.json(summary["common_error_tags"], expanded=False)
    with col2:
        st.write("严重错误")
        st.json(summary["common_fatal_errors"], expanded=False)


def show_history():
    """展示已经保存的每条评分记录。"""
    results = read_json(RESULTS_PATH, default=[])

    st.header("历史评分记录")

    if not results:
        st.write("暂无历史评分记录。")
        return

    history_json = json.dumps(results, ensure_ascii=False, indent=2)
    st.download_button(
        "下载历史评分记录 JSON",
        data=history_json,
        file_name="judged_results.json",
        mime="application/json",
    )

    rows = []
    for index, item in enumerate(results, start=1):
        rows.append(
            {
                "序号": index,
                "题目": item.get("question_id", ""),
                "模型": item.get("model_name", ""),
                "分数": item.get("score", ""),
                "usable": item.get("usable", ""),
                "评分理由": item.get("comment", ""),
                "错误标签": "；".join(item.get("error_tags", [])),
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)

    record_options = [
        f"{index}. {item.get('question_id', '')} | {item.get('model_name', '')} | score={item.get('score', '')}"
        for index, item in enumerate(results, start=1)
    ]
    selected_record = st.selectbox("选择一条历史记录", record_options)
    selected_index = record_options.index(selected_record)
    selected_item = results[selected_index]

    with st.expander("打开选中记录详情", expanded=True):
        st.json(selected_item)

    if st.button("删除选中记录", type="secondary"):
        deleted_item = results.pop(selected_index)
        write_json(RESULTS_PATH, results)
        st.success(
            f"已删除：{deleted_item.get('question_id', '')} | {deleted_item.get('model_name', '')}"
        )
        st.rerun()

    with st.expander("查看完整历史 JSON"):
        st.json(results, expanded=False)


st.title("医学推理自动评分工具")

questions = read_json(QUESTIONS_PATH)
question_map = {item["id"]: item for item in questions}
question_ids = list(question_map.keys())

selected_question_id = st.selectbox("选择题目", question_ids)
selected_question = question_map[selected_question_id]
criteria = selected_question["evaluation_criteria"]

st.header(f"题目 {selected_question_id}")
st.write(selected_question["question"])
show_copy_button(selected_question["question"], f"copy-{selected_question_id}")

with st.expander("查看 reference_answer"):
    st.write(selected_question["reference_answer"])

with st.expander("查看 evaluation_criteria"):
    st.subheader("core_points")
    st.json(criteria["core_points"], expanded=False)

    st.subheader("minor_points")
    st.json(criteria["minor_points"], expanded=False)

    st.subheader("fatal_errors")
    st.json(criteria["fatal_errors"], expanded=False)

    st.subheader("score_rule")
    st.write(criteria["score_rule"])

model_options = ["DeepSeek", "GPT", "Gemini", "Kimi", "Qwen", "Other"]
model_choice = st.selectbox("被评模型名称", model_options)

if model_choice == "Other":
    model_name = st.text_input("请输入模型名称", value="")
else:
    model_name = model_choice

model_answer = st.text_area(
    "粘贴模型回答",
    height=260,
    placeholder="把当前题目的模型回答粘贴到这里",
    key=f"model_answer_{selected_question_id}",
)

if st.button("开始评分", type="primary"):
    if not model_name.strip():
        st.error("请填写模型名称。")
    elif not model_answer.strip():
        st.error("请先粘贴模型回答。")
    else:
        model_answer_item = {
            "question_id": selected_question_id,
            "model_name": model_name.strip(),
            "model_answer": model_answer.strip(),
        }

        try:
            with st.spinner("正在调用 Judge API 评分..."):
                prompt = build_prompt(selected_question, model_answer_item)
                raw_result = call_judge(prompt)
                result = parse_judge_json(raw_result, model_answer_item)
                saved_count = append_result(result)

            st.success("评分完成，结果已保存。")
            st.metric("分数", result.get("score"))
            st.write("usable:", result.get("usable"))
            st.write("评分理由：", result.get("comment", ""))

            show_list("命中的核心点", result.get("matched_core_points", []))
            show_list("遗漏的核心点", result.get("missed_core_points", []))
            show_list("命中的次要点", result.get("matched_minor_points", []))
            show_list("严重错误", result.get("fatal_errors_found", []))
            show_list("错误标签", result.get("error_tags", []))

            with st.expander("查看完整 JSON 结果"):
                st.json(result)

            st.info(f"当前已经保存了 {saved_count} 条评分结果。")
        except Exception as error:
            st.error(f"评分失败：{error}")

st.divider()
st.caption(f"当前已经保存了 {get_saved_count()} 条评分结果。")

st.divider()
show_summary()

st.divider()
show_history()
