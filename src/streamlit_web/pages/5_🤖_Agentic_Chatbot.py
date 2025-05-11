import time
import uuid
import datetime
import streamlit as st
from langchain.schema.runnable.config import RunnableConfig
from langchain_core.messages import HumanMessage

from agent import create_supervisor_graph, parse_agent_result
from config import AgentConfig

st.set_page_config(
    page_title="Agentic Chatbot",
    page_icon="🤖",
    layout="wide",
)


@st.cache_resource
def get_agent_config() -> AgentConfig:
    config = AgentConfig()
    config.checkpointer_mongodb_async = False
    config.get_logger().debug("config loaded", config=config)
    return config


logger = get_agent_config().get_logger()


def ensure_new_line(message: str) -> str:
    return "\n\n".join(message.strip().split("\n"))


def handle_chat_input(message, rerun=True):
    st.session_state["is_thinking"] = True
    st.session_state.messages.append(
        {"role": "user", "content": ensure_new_line(message)})
    if rerun:
        st.rerun()


def simulate_stream(message: str):
    for char in message:
        yield char
        if not char.isspace():
            time.sleep(0.02)


st.title("Agentic Chatbot 🤖")

if "messages" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())
    st.session_state["messages"] = [{"role": "assistant", "content": get_agent_config(
    ).get_message("assistant_greeting"), "references": []}]

if "is_thinking" not in st.session_state:
    st.session_state["is_thinking"] = False

for idx, message in enumerate(st.session_state["messages"]):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "references" in message:
            for reference in message["references"]:
                with st.expander(f"{reference.icon_emoji} **{reference.title}**\n\n`#{reference.source}`", expanded=True):
                    st.markdown("\n\n".join(
                        [f"[{artifact.title}]({artifact.link})" for artifact in reference.artifacts]))
        if message["role"] == "assistant" and idx != 0:
            st.markdown(f"`{get_agent_config().get_message(
                "content_disclaimer_message")}`")

if message := st.chat_input(placeholder=get_agent_config().get_message("assistant_placeholder"), disabled=st.session_state["is_thinking"]):
    handle_chat_input(message)

st.sidebar.header("Example Prompts")
for idx, prompt in enumerate(get_agent_config().get_message_dicts("assistant_greeting_prompt")):
    st.sidebar.button(
        prompt["title"], key=idx, icon=prompt["icon"], type="tertiary", help=ensure_new_line(prompt["message"]), on_click=lambda message=prompt["message"]: handle_chat_input(message, rerun=False), disabled=st.session_state["is_thinking"])

if st.session_state["is_thinking"] and st.session_state["messages"][-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner(text=get_agent_config().get_message("assistant_thinking"), show_time=True):
            graph = create_supervisor_graph(get_agent_config())
            message_id = str(uuid.uuid4())
            runnable_config = get_agent_config().get_tracker().inject_runnable_config(RunnableConfig(
                metadata={
                    "user_id": "anonymous",
                    "message_id": message_id,
                    "session_id": st.session_state["session_id"],
                },
                configurable={
                    "context": f"- Current time is {datetime.datetime.now(datetime.timezone.utc).isoformat()}.",
                    "thread_id": st.session_state["session_id"],
                },
                tags=["streamlit", "message"],
                run_id=message_id,
            ))
            result = graph.invoke(
                {"messages": [HumanMessage(content=st.session_state["messages"][-1]["content"])]}, config=runnable_config)
            logger.debug("invoke", result=result,
                         runnable_config=runnable_config)
            content, references = parse_agent_result(
                get_agent_config(), result)

        st.write_stream(simulate_stream(content))
        for reference in references:
            with st.expander(f"{reference.icon_emoji} **{reference.title}**\n\n`#{reference.source}`", expanded=True):
                st.markdown("\n\n".join(
                    [f"[{artifact.title}]({artifact.link})" for artifact in reference.artifacts]))

        st.markdown(f"`{get_agent_config().get_message(
            "content_disclaimer_message")}`")

        st.session_state["messages"].append(
            {"role": "assistant", "content": content, "references": references})
        st.session_state["is_thinking"] = False
        st.rerun()
