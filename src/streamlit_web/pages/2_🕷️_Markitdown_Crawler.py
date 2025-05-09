import uuid

import streamlit as st
from langchain.tools import BaseTool

from agent.tool import create_markitdown_crawler_tool
from config import AgentConfig

st.set_page_config(
    page_title="Markitdown Crawler",
    page_icon="🕷️",
    layout="wide",
)


@st.cache_resource
def get_agent_config() -> AgentConfig:
    config = AgentConfig()
    config.checkpointer_mongodb_async = False
    config.get_logger().debug("config loaded", config=config)
    return config


@st.cache_resource
def get_markitdown_crawler_tool() -> BaseTool:
    return create_markitdown_crawler_tool(get_agent_config())


@st.cache_data
def get_crawler_results(url: str) -> str:
    crawler = get_markitdown_crawler_tool()
    return crawler.invoke(
        input={
            "id": str(uuid.uuid4()),
            "type": "tool_call",
            "name": crawler.name,
            "args": {"url": url},
        },
    ).content


st.title("Markitdown Crawler 🕷️")

st.sidebar.header("Document")
st.sidebar.markdown(
    "[Markitdown](https://github.com/microsoft/markitdown)")


url = st.text_input("Url, e.g., 'https://example.com'",
                    value="https://example.com")

if url:
    if markdown := get_crawler_results(url):
        with st.expander("Full Content in Markdown", expanded=True):
            st.markdown(markdown)
