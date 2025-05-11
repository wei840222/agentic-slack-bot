import uuid
from typing import List

import streamlit as st
from langchain.tools import BaseTool

from agent.tool import create_google_search_tool, create_markitdown_crawler_tool, Artifact
from config import AgentConfig

st.set_page_config(
    page_title="Custom Google Search",
    page_icon="🌏",
    layout="wide",
)


@st.cache_resource
def get_agent_config() -> AgentConfig:
    config = AgentConfig()
    config.checkpointer_mongodb_async = False
    config.get_logger().debug("config loaded", config=config)
    return config


@st.cache_resource
def get_google_search_tool() -> BaseTool:
    return create_google_search_tool(get_agent_config())


@st.cache_resource
def get_markitdown_crawler_tool() -> BaseTool:
    return create_markitdown_crawler_tool(get_agent_config())


@st.cache_data
def get_search_results(query: str, num_results: int, crawl: bool = False) -> List[Artifact]:
    google_search = get_google_search_tool()
    artifacts: List[Artifact] = google_search.invoke(
        input={
            "id": str(uuid.uuid4()),
            "type": "tool_call",
            "name": google_search.name,
            "args": {"query": query},
        },
        config={
            "configurable": {
                "google_search_num_results": num_results,
            },
        },
    ).artifact
    if crawl:
        crawler = get_markitdown_crawler_tool()
        for artifact in artifacts:
            artifact["markdown"] = crawler.invoke(
                input={
                    "id": str(uuid.uuid4()),
                    "type": "tool_call",
                    "name": crawler.name,
                    "args": {"url": artifact["link"]},
                },
            ).content
    return artifacts


st.title("Custom Google Search 🌏")

st.sidebar.header("Document")
st.sidebar.markdown(
    "[Custom Search JSON API](https://developers.google.com/custom-search/v1/overview)")


col1, col2 = st.columns(2)
with col1:
    query = st.text_input(
        "Search query, e.g., '台北天氣', 'K8S 是什麼'", value="台北天氣")
with col2:
    num_results = st.number_input(
        "Number of results", min_value=1, max_value=10, value=3)

crawl = st.checkbox("Crawl search results in markdown", value=False)

if query:
    if results := get_search_results(query, num_results, crawl):
        for result in results:
            st.markdown(f"[{result['title']}]({result['link']})")
            st.write(result["content"])
            if crawl and "markdown" in result:
                with st.expander("Full Content in Markdown"):
                    st.markdown(result["markdown"])
            st.write("---")
    else:
        st.markdown("No search results found.")
