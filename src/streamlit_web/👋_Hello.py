import streamlit as st

st.set_page_config(
    page_title="AI Playground",
    page_icon="👋",
    layout="wide",
)

st.title("Welcome to AI Playground! 👋")

st.markdown(
    """
    Welcome to the AI Playground site! This is a platform where developers can quickly test
    and validate proof-of-concept features and understand their practical applications.

    **👈 Select a demo from the sidebar** to explore our available features.
"""
)

st.header("Developer Tools")
st.html(
    """
    <a href="https://modelcontextprotocol.io">
        <img src="https://microsoft.github.io/genaiscript/_astro/mcp.CBnQ_GM8_1eWG7e.webp" height="30" alt="MCP Logo">
    </a>
    """
)
st.markdown(
    """
    **[MCP Server](./MCP_Server)**  
    Model Context Protocol (MCP) Server provides a standardized way to expose AI tools and services through Streamable HTTP transport. It offers emoji analysis, web scraping, search capabilities and Slack integration for enhanced AI development workflows.
"""
)
