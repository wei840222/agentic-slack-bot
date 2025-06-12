import streamlit as st

st.set_page_config(
    page_title="MCP Server",
    page_icon="🛠️",
    layout="wide",
)


@st.cache_resource
def get_video_bytes(file_name: str) -> bytes:
    video_file = open(f"./src/streamlit_web/video/{file_name}", "rb")
    return video_file.read()


st.title("MCP Server 🛠️")


st.sidebar.header("Document")
st.sidebar.markdown(
    "[MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http)")

st.sidebar.markdown(
    "[MCP Inspector](https://github.com/modelcontextprotocol/inspector)")

st.subheader("Overview")
st.markdown("""
The **MCP Server** (Model Context Protocol Server) provides a standardized way to expose AI tools and services through the **Streamable HTTP** transport protocol. This server implementation follows the [MCP Specification](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http) and exposes various tools for:

- **Emoji Analysis**: Get emoji sentiment information
- **Web Scraping**: Convert web pages to markdown format
- **Search**: Google search capabilities
- **Slack Integration**: Access conversation history and search
""")

st.subheader("Architecture")
st.markdown("""
The MCP Server is built using the `FastMCP` framework and exposes endpoints via **Streamable HTTP** transport:

```
Client(Cursor) → HTTP → MCP Server → Tools/Services
```
""")

st.subheader("Integration with Cursor")
st.video(get_video_bytes("mcp-cursor.mp4"))
st.markdown("""
### Step 1: Configure Cursor MCP Settings

1. Open **Cursor** and go to **Preferences** → **Cursor Settings** → **MCP Servers**

2. Add a new MCP server configuration:

```json
{
    "mcpServers": {
        "ai-playground": {
            "url": "https://ai.tailb0283.ts.net/mcp/"
        }
    }
}
```

### Step 2: Refresh Cursor

After adding the configuration, refresh Cursor MCP Settings to load the MCP server.

### Step 3: Verify Integration

1. Open a new chat in Cursor
2. You should see the available tools in the tool list:
    - `emoji_information`
    - `markitdown_crawler`
    - `google_search`
    - `get_slack_conversation_replies`
    - `get_slack_conversation_history`
    - `search_slack_conversation`

### Step 4: Usage Example

In Cursor chat, you can now use commands like:

```
search slack Google 人工智慧新技術有甚麼
```
""")

st.subheader("Testing with MCP Inspector")
st.video(get_video_bytes("mcp-inspector.mp4"))
st.markdown("""
The **MCP Inspector** is a powerful tool for testing and debugging MCP servers locally.

### Step 1: Launch MCP Inspector

```bash
NODE_TLS_REJECT_UNAUTHORIZED=0 npx @modelcontextprotocol/inspector
```

### Step 2: Connect to MCP Server

1. Open the MCP Inspector
2. Choose the "Streamable HTTP" transport
3. Enter the URL of the MCP Server `https://ai.tailb0283.ts.net/mcp/`
4. Click on the "Connect" button

### Step 3: Test Server Capabilities

1. **View Available Tools** The inspector will show all available tools/functions
2. **Test Tool Execution** Click on any tool to test it with sample parameters
3. **Monitor Requests** See real-time request/response data
4. **Debug Issues** Check for errors or unexpected behavior
""")
