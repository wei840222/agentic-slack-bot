from typing import List, Tuple, Annotated, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg
from langchain.tools import BaseTool, tool

from config import SlackConfig, AgentConfig
from slack_bot.client import SlackClient
from agent.chain import create_make_title_chain
from .types import Artifact

_slack_client: Optional[SlackClient] = None


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

        contents = []
        attachment_keys = ["service_name", "title", "title_link", "text"]
        for reply in replies:
            if reply["type"] != "message":
                continue
            if reply.get("subtype", "") == "bot_message":
                content = f"""
Post Author:
{reply['username']}

Post:
{reply['text']}
""".strip()
                attachments = reply.get("attachments", [])
                attachment_contents = []
                for attachment in attachments:
                    attachment_content = ""
                    for key in attachment_keys:
                        if key in attachment:
                            attachment_content += f"> {key}: {attachment[key]}\n"
                    attachment_contents.append(attachment_content.strip())
                if attachment_contents:
                    content += f"\n\nAttachments:\n{'\n\n'.join(attachment_contents)}"
                contents.append(content)
            else:
                content = f"""
User:
<@{reply['user']}>

Message:
{reply['text']}
""".strip()
                attachments = reply.get("attachments", [])
                attachment_contents = []
                for attachment in attachments:
                    attachment_content = ""
                    for key in attachment_keys:
                        if key in attachment:
                            attachment_content += f"{key}: {attachment[key]}\n"
                    attachment_contents.append(attachment_content.strip())
                if attachment_contents:
                    content += f"\n\nAttachments:\n{'\n\n'.join(attachment_contents)}"
                contents.append(content)

        content = "\n\n---\n\n".join(contents)
        agent_config = AgentConfig.from_runnable_config(config)
        title = create_make_title_chain(agent_config).invoke(
            input={"input": content}, config=config)
        artifacts = [Artifact(title=clean_title(title),
                              link=url, content=content)]
        return content, artifacts

    get_slack_conversation_replies.description = config.get_prompt(
        "get_slack_conversation_replies_tool").text

    return get_slack_conversation_replies
