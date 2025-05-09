import time
import uuid
import streamlit as st
from langchain.schema.runnable.config import RunnableConfig
from langchain_core.messages import HumanMessage
from langchain.callbacks.streamlit import StreamlitCallbackHandler


from agent import create_supervisor_graph, parse_agent_result
from config import AgentConfig


@st.cache_resource
def get_agent_config() -> AgentConfig:
    config = AgentConfig()
    config.checkpointer_mongodb_async = False
    config.get_logger().debug("config loaded", config=config)
    return config


@st.cache_resource
def get_graph():
    return create_supervisor_graph(get_agent_config())


def simulate_stream(message: str):
    for char in message:
        yield char
        time.sleep(0.02)


logger = get_agent_config().get_logger()

st.title("Agentic Chatbot 🤖")

st.sidebar.header("Example Prompts")
for idx, prompt in enumerate(get_agent_config().get_message_dicts("assistant_greeting_prompt")):
    st.sidebar.markdown(f"**{prompt['title']}**\n\n{prompt['message']}")
    st.sidebar.write("---")

if "messages" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())
    st.session_state["messages"] = []

for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.empty()
        st.markdown(message["content"])
        if "references" in message:
            for reference in message["references"]:
                with st.expander(f"{reference.icon_emoji} **{reference.title}**\n\n`#{reference.source}`", expanded=True):
                    st.markdown("\n\n".join(
                        [f"[{artifact.title}]({artifact.link})" for artifact in reference.artifacts]))

if message := st.chat_input(get_agent_config().get_message("assistant_greeting")):
    with st.chat_message("user"):
        st.markdown(message)
        st.session_state.messages.append({"role": "user", "content": message})

    with st.chat_message("assistant"):
        graph = get_graph()
        message_id = str(uuid.uuid4())
        thinking_placeholder = st.empty()
        runnable_config = get_agent_config().get_tracker().inject_runnable_config(RunnableConfig(
            metadata={
                "bot_id": "agentic-bot",
                "channel_id": "streamlit-web",
                "user_id": "anonymous",
                "message_id": message_id,
                "session_id": st.session_state["session_id"],
            },
            configurable={
                "thread_id": st.session_state["session_id"],
            },
            tags=["streamlit", "message"],
            run_id=message_id,
            callbacks=[StreamlitCallbackHandler(thinking_placeholder)]
        ))
        result = graph.invoke(
            {"messages": [HumanMessage(content=message)]}, config=runnable_config)
        logger.debug("invoke", result=result, runnable_config=runnable_config)
        content, references = parse_agent_result(get_agent_config(), result)
        thinking_placeholder.empty()
        st.write_stream(simulate_stream(content))
        for reference in references:
            with st.expander(f"{reference.icon_emoji} **{reference.title}**\n\n`#{reference.source}`", expanded=True):
                st.markdown("\n\n".join(
                    [f"[{artifact.title}]({artifact.link})" for artifact in reference.artifacts]))

        st.session_state.messages.append(
            {"role": "assistant", "content": content, "references": references})
