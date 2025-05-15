from typing import List, Tuple, Annotated, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg
from langchain.tools import BaseTool, tool
from qdrant_client import QdrantClient, models

from config import SlackConfig, AgentConfig
from config.client import QdrantConfig

from slack_bot.client import SlackClient
from slack_bot.types import message_to_text
from agent.chain import create_make_title_chain
from .types import Artifact

_slack_client: Optional[SlackClient] = None
_qdrant_client: Optional[QdrantClient] = None


def clean_title(title: str) -> str:
    """Clean a title by removing special characters."""
    return ''.join(filter(lambda x: x not in "|&/<>\"'\\\n", title))


def create_get_slack_conversation_replies_tool(config: SlackConfig) -> BaseTool:
    global _slack_client

    if _slack_client is None:
        _slack_client = SlackClient(config)

    @tool(response_format="content_and_artifact")
    def get_slack_conversation_replies(url: str, single_message: Optional[bool], config: Annotated[RunnableConfig, InjectedToolArg]) -> Tuple[str, List[Artifact]]:
        "prompt_name: get_slack_conversation_replies_tool"

        channel_id, ts = _slack_client.get_thread_url_info(
            url, not single_message)

        replies = _slack_client.fetch_conversations_replies(
            channel_id, ts)

        contents = [message_to_text(reply) for reply in replies]
        content = "\n\n---\n\n".join(
            [content for content in contents if content is not None])

        agent_config = AgentConfig.from_runnable_config(config)
        title = create_make_title_chain(agent_config).invoke(
            input={"input": content}, config=config)
        artifacts = [Artifact(title=clean_title(title),
                              link=url, content=content)]
        return content, artifacts

    get_slack_conversation_replies.description = config.get_prompt(
        "get_slack_conversation_replies_tool").text

    return get_slack_conversation_replies


def create_get_slack_conversation_history_tool(config: SlackConfig) -> BaseTool:
    global _slack_client

    if _slack_client is None:
        _slack_client = SlackClient(config)

    @tool(response_format="content_and_artifact")
    def get_slack_conversation_history(url: str, message_count: Optional[int], config: Annotated[RunnableConfig, InjectedToolArg]) -> Tuple[str, List[Artifact]]:
        "prompt_name: get_slack_conversation_history_tool"

        channel_id = _slack_client.get_channel_url_info(url)

        history = _slack_client.fetch_conversations_history(
            channel_id, 1, message_count or 10)

        contents = [message_to_text(message)
                    for page in history["pages"]
                    for message in page["messages"]]
        content = "\n\n---\n\n".join(
            [content for content in contents if content is not None])

        content = "\n\n---\n\n".join(contents)
        agent_config = AgentConfig.from_runnable_config(config)
        title = create_make_title_chain(agent_config).invoke(
            input={"input": content}, config=config)
        artifacts = [Artifact(title=clean_title(title),
                              link=url, content=content)]
        return content, artifacts

    get_slack_conversation_history.description = config.get_prompt(
        "get_slack_conversation_history_tool").text

    return get_slack_conversation_history


def create_search_slack_conversation_tool(slack_config: SlackConfig, qdrant_config: QdrantConfig) -> BaseTool:
    global _qdrant_client

    if _qdrant_client is None:
        _qdrant_client = qdrant_config.get_qdrant_client()

    @tool(response_format="content_and_artifact")
    def search_slack_conversation(query: str, channel_ids: Optional[List[str]], num_results: Optional[int], config: Annotated[RunnableConfig, InjectedToolArg]) -> Tuple[str, List[Artifact]]:
        "prompt_name: search_slack_conversation_tool"

        agent_config = AgentConfig.from_runnable_config(config)

        results = _qdrant_client.query_points(
            collection_name="slack",
            query=agent_config.load_embeddings_model().embed_query(query),
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.channel_id",
                        match=models.MatchAny(any=channel_ids),
                    )
                ]
            ) if channel_ids else None,
            limit=num_results or agent_config.slack_search_default_num_results,
            score_threshold=agent_config.slack_search_score_threshold,
        )

        agent_config.get_logger().debug(
            "search_slack_conversation", results=results)

        content = "\n\n===\n\n".join([point.payload["page_content"]
                                     for point in results.points])
        artifacts = [Artifact(title=point.payload["metadata"]["title"],
                              link=point.payload["metadata"]["source"],
                              content=point.payload["page_content"],
                              metadata={"score": point.score, **{k: v for k, v in point.payload["metadata"].items() if k not in {"title", "source", "source_key"}}})
                     for point in results.points]
        return content, artifacts

    search_slack_conversation.description = slack_config.get_prompt(
        "search_slack_conversation_tool").text

    return search_slack_conversation
