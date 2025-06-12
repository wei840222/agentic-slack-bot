import uuid
from typing import List
from mcp.server.fastmcp import FastMCP

from emoji_sentiment import EmojiSentiment, Emoji
from config import AgentConfig, SlackConfig, RagConfig
from agent.tool import create_markitdown_crawler_tool, create_google_search_tool
from agent.tool import create_get_slack_conversation_replies_tool, create_get_slack_conversation_history_tool, create_search_slack_conversation_tool
from agent.tool.types import Artifact


mcp = FastMCP("AI Playground")

agent_config = AgentConfig()
slack_config = SlackConfig()
rag_config = RagConfig()

emoji_sentiment = EmojiSentiment()


@mcp.tool()
def emoji_information(emoji_short_name: str) -> Emoji:
    """
    Get emoji information including name, short names, char, samples, and sentiment score.

    Args:
        emoji_short_name: The short name of the emoji.

    Returns:
        Emoji: The emoji information.
    """
    if (emoji := emoji_sentiment.get(emoji_short_name)) is None:
        raise ValueError(f"Emoji {emoji_short_name} not found")
    return emoji


markitdown_crawler_tool = create_markitdown_crawler_tool(agent_config)


@mcp.tool(description=agent_config.get_prompt("markitdown_crawler_tool").text)
def markitdown_crawler(url: str) -> List[Artifact]:
    "prompt_name: markitdown_crawler_tool"
    return markitdown_crawler_tool.invoke(
        input={
            "id": str(uuid.uuid4()),
            "type": "tool_call",
            "name": markitdown_crawler_tool.name,
            "args": {"url": url},
        },
    ).artifact


google_search_tool = create_google_search_tool(agent_config)


@mcp.tool(description=agent_config.get_prompt("google_search_tool").text)
def google_search(query: str, num_results: int = 3) -> List[Artifact]:
    "prompt_name: google_search_tool"
    return google_search_tool.invoke(
        input={
            "id": str(uuid.uuid4()),
            "type": "tool_call",
            "name": google_search_tool.name,
            "args": {"query": query, "num_results": num_results},
        },
    ).artifact


get_slack_conversation_replies_tool = create_get_slack_conversation_replies_tool(
    slack_config)


@mcp.tool(description=agent_config.get_prompt("get_slack_conversation_replies_tool").text)
def get_slack_conversation_replies(url: str, single_message: bool = False) -> List[Artifact]:
    "prompt_name: get_slack_conversation_replies_tool"
    return get_slack_conversation_replies_tool.invoke(
        input={
            "id": str(uuid.uuid4()),
            "type": "tool_call",
            "name": get_slack_conversation_replies_tool.name,
            "args": {"url": url, "single_message": single_message},
        },
    ).artifact


get_slack_conversation_history_tool = create_get_slack_conversation_history_tool(
    slack_config)


@mcp.tool(description=agent_config.get_prompt("get_slack_conversation_history_tool").text)
def get_slack_conversation_history(url: str, message_count: int = 10) -> List[Artifact]:
    "prompt_name: get_slack_conversation_history_tool"
    return get_slack_conversation_history_tool.invoke(
        input={
            "id": str(uuid.uuid4()),
            "type": "tool_call",
            "name": get_slack_conversation_history_tool.name,
            "args": {"url": url, "message_count": message_count},
        },
    ).artifact


search_slack_conversation_tool = create_search_slack_conversation_tool(
    slack_config)
search_slack_conversation_description = agent_config.get_prompt(
    "search_slack_conversation_tool").text.strip()
search_slack_conversation_description += "\n\nChannels:\n"
search_slack_conversation_description += "\n".join([f"""
- name: {channel["name"]}
  id: {channel["id"]}
  id_from_slack: <#{channel["id"]}|>
  description: {channel["description"]}
""".strip() for channel in rag_config.slack_search_channels])


@mcp.tool(description=search_slack_conversation_description)
def search_slack_conversation(query: str, channel_ids: List[str] = [], num_results: int = 3) -> List[Artifact]:
    "prompt_name: search_slack_conversation_tool"
    return search_slack_conversation_tool.invoke(
        input={
            "id": str(uuid.uuid4()),
            "type": "tool_call",
            "name": search_slack_conversation_tool.name,
            "args": {"query": query, "channel_ids": channel_ids, "num_results": num_results},
        },
    ).artifact
