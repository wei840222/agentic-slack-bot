import uuid
from typing import List, Optional

import streamlit as st
from langchain.tools import BaseTool

from agent.tool import create_search_slack_conversation_tool
from agent.tool.types import Artifact
from config import SlackConfig, RagConfig

st.set_page_config(
    page_title="Slack Search",
    page_icon="🔍",
    layout="wide",
)


@st.cache_resource
def get_rag_config() -> RagConfig:
    config = RagConfig()
    config.get_logger().debug("rag config loaded", rag_config=config)
    return config


@st.cache_resource
def get_slack_config() -> SlackConfig:
    config = SlackConfig()
    config.get_logger().debug("slack config loaded", slack_config=config)
    return config


@st.cache_resource
def get_slack_search_tool() -> BaseTool:
    return create_search_slack_conversation_tool(get_slack_config())


@st.cache_data
def get_search_results(query: str, channel_ids: Optional[List[str]], num_results: int) -> List[Artifact]:
    slack_search = get_slack_search_tool()
    artifacts: List[Artifact] = slack_search.invoke(
        input={
            "id": str(uuid.uuid4()),
            "type": "tool_call",
            "name": slack_search.name,
            "args": {"query": query, "channel_ids": channel_ids, "num_results": num_results},
        },
    ).artifact
    return artifacts


st.title("Slack Search 🔍")

st.sidebar.header("Document")
st.sidebar.markdown(
    "[Qdrant Similarity search](https://qdrant.tech/documentation/concepts/search)")
st.sidebar.markdown(
    "[Improve search and RAG quality with ranking API](https://cloud.google.com/generative-ai-app-builder/docs/ranking)")


col1, col2, col3 = st.columns(3)
with col1:
    query = st.text_input(
        "Search query, e.g., 'Google 人工智慧新技術有甚麼', '天氣怎麼樣'", value="Google 人工智慧新技術有甚麼")
with col2:
    CHANNELS = get_rag_config().slack_search_channels
    channel_names = st.multiselect(
        "Select channels to search. Leave empty to search all.",
        [channel["name"] for channel in CHANNELS],
        default=[channel["name"] for channel in CHANNELS],
    )
with col3:
    num_results = st.number_input(
        "Number of results", min_value=1, max_value=10, value=3)

if query:
    if results := get_search_results(query, [channel["id"] for channel in CHANNELS if channel["name"] in channel_names], num_results):
        for result in results:
            st.markdown(f"[{result['title']}]({result['link']})")
            st.code(result["content"], language="markdown")
            st.write(result["metadata"])
            st.divider()
    else:
        st.markdown("No search results found.")
