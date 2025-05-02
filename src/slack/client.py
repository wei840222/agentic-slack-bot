import re
import json
import logging
import backoff
from enum import Enum
from typing import Any, Dict, List, TypedDict, Any, List, Dict, Optional, Tuple

from pydantic import BaseModel
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError

from config.logger import LoggerConfig
from config import SlackConfig


class SlackChannelHistory(TypedDict):
    channel: str
    pages: List[Dict[str, Any]]


class SlackMessage(TypedDict):
    user: str
    type: str
    subtype: str | None
    ts: str
    thread_ts: str | None
    client_msg_id: str
    text: str
    team: str
    parent_user_id: str
    blocks: List[Dict[str, Any]]
    channel: str
    event_ts: str
    channel_type: str
    reply_count: int | None
    latest_reply: str | None
    reactions: List[Dict[str, Any]]


class SlackEventType(Enum):
    MESSAGE = "message"
    APP_MENTION = "app_mention"
    REACTION_ADDED = "reaction_added"


class SlackEvent(BaseModel):
    type: SlackEventType
    data: Dict[str, Any]
    user: str
    channel: str
    message_id: Optional[str] = None
    session_id: Optional[str] = None


class SlackMessageReferenceArtifact(BaseModel):
    title: str
    link: str
    content: Optional[str] = None


class SlackMessageReference(BaseModel):
    name: str
    icon_emoji: str
    artifacts: List[SlackMessageReferenceArtifact] = []


def slack_api_error_is_not_retryable(e: SlackApiError):
    return e.response.status_code != 429


class BaseSlackClient:
    def __init__(self, config: SlackConfig, logger: Optional[logging.Logger] = None):
        self.logger = logger or LoggerConfig().get_logger()
        self.config = config

    @staticmethod
    def clean_markdown(text: str) -> str:
        text = re.sub(r"^```[^\n]*\n", "```\n", text, flags=re.MULTILINE)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"_\1_", text)
        text = re.sub(r"_([^_]+)_", r"_\1_", text)
        text = re.sub(r"^\s*[-*]\s", "• ", text, flags=re.MULTILINE)
        return text

    @staticmethod
    def get_thread_url_info(url: str) -> Tuple[str, float]:
        """
        Extract the channel ID and thread ts from a Slack Thread URL.
        example: https://xxxx.slack.com/archives/C0000000000/p1741964293697769

        Args:
            url: The thread URL to extract the channel ID and thread ts from.

        Returns:
            A tuple containing the channel ID and thread ts.
        """
        match = re.search(r"/archives/([^/]+)/p(\d+)", url)
        if match:
            return match.group(1), int(match.group(2)) / 1000000
        raise ValueError(f"Invalid Slack Thread URL: {url}")


class SlackClient(BaseSlackClient):
    def __init__(self, config: SlackConfig, client: Optional[WebClient] = None, logger: Optional[logging.Logger] = None):
        super().__init__(config, logger)
        self.client = client or WebClient(token=config.bot_token)

    def fetch_conversations_history(self, channel: str, limit: Optional[int], size: int = 100) -> SlackChannelHistory:
        result = SlackChannelHistory(channel=channel, pages=[])
        pages = 1

        history = self.client.conversations_history(
            channel=channel, include_all_metadata=True, limit=size)
        result["pages"].append(history.data)
        self.logger.info(
            "fetch conversations history",
            page=pages,
            messages=len(history.data["messages"]),
            has_more=history.data["has_more"])

        while limit is not None and pages < limit:
            pages += 1
            if not history.data["has_more"]:
                break
            cursor = history.data["response_metadata"]["next_cursor"]
            history = self.client.conversations_history(
                channel=channel, include_all_metadata=True, cursor=cursor, limit=size)
            result["pages"].append(history.data)
            self.logger.info(
                "fetch channel history",
                page=pages,
                messages=len(history.data["messages"]),
                cursor=cursor,
                has_more=history.data["has_more"])

        self.logger.debug("slack.client.conversations_history",
                          slack_channel_history=json.dumps(result, ensure_ascii=False))

        return result

    @backoff.on_exception(backoff.expo, SlackApiError, max_time=60, giveup=slack_api_error_is_not_retryable, logger=LoggerConfig().get_logger())
    def fetch_conversations_replies(self, channel: str, thread_ts: str, limit: int = 150) -> List[SlackMessage]:
        self.logger.info("fetching conversations replies",
                         channel=channel, thread_ts=thread_ts)
        messages = []
        cursor = None

        page_limit = limit
        if page_limit > 1000:
            page_limit = 1000

        while True:
            if cursor:
                response = self.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts,
                    inclusive=True,
                    limit=page_limit,
                    cursor=cursor,
                    include_all_metadata=True,
                )
            else:
                response = self.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts,
                    inclusive=True,
                    limit=page_limit,
                    include_all_metadata=True,
                )
            messages.extend(response["messages"])
            if len(messages) >= limit:
                break
            if not response.get("has_more"):
                break
            cursor = response["response_metadata"]["next_cursor"]

        self.logger.debug("slack.client.conversations_replies", slack_thread_replies=json.dumps(
            messages, ensure_ascii=False))

        return messages

    def find_session_id(self, event: SlackEvent, in_replies: bool = False) -> str:
        session_id = ""

        if in_replies and "thread_ts" in event.data:
            replies = self.fetch_conversations_replies(
                event.channel, event.data["thread_ts"], 30)
            if len(replies) > 0:
                for reply in replies:
                    if "client_msg_id" in reply:
                        session_id = reply["client_msg_id"]
                        break

        else:
            conversations = self.fetch_conversations_history(
                event.channel, 1, size=30)
            for message in conversations["pages"][0]["messages"]:
                if "subtype" in message or message["text"].strip() == "":
                    continue

                try:
                    current_session_id = message["metadata"]["event_payload"]["reply_session_id"]
                    if session_id == "":
                        session_id = current_session_id
                    elif session_id != current_session_id:
                        break
                except:
                    pass

        if session_id == "":
            session_id = event.data["client_msg_id"]

        return session_id

    def add_reaction(self, event: SlackEvent, reaction: str) -> None:
        response = self.client.reactions_add(
            channel=event.channel,
            timestamp=event.data["ts"],
            name=reaction.strip(":"),
        )
        self.logger.debug("slack.client.reactions_add", reaction=reaction,
                          slack_response=json.dumps(response.data, ensure_ascii=False))

    def remove_reaction(self, event: SlackEvent, reaction: str) -> None:
        response = self.client.reactions_remove(
            channel=event.channel,
            timestamp=event.data["ts"],
            name=reaction.strip(":"),
        )
        self.logger.debug("slack.client.reactions_remove", reaction=reaction,
                          slack_response=json.dumps(response.data, ensure_ascii=False))

    def reply_markdown(self, event: SlackEvent, markdown: str, references: Optional[List[SlackMessageReference]] = None, in_replies: bool = False) -> None:
        blocks = [{
            "type": "markdown",
            "text": markdown
        }]

        if references:
            for reference in references:
                artifact_text = "\n".join(
                    [f"<{artifact.link}|{artifact.title}>" for artifact in reference.artifacts])
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"{reference.icon_emoji} *{reference.name}*\n{artifact_text}"
                    }]
                })

        blocks.append({
            "type": "context",
            "elements": [{
                    "type": "mrkdwn",
                    "text": self.config.get_message("content_disclaimer_message").text
            }]
        })

        response = self.client.chat_postMessage(
            channel=event.channel,
            thread_ts=event.data["ts"] if in_replies else None,
            text=self.clean_markdown(markdown),
            blocks=blocks,
            unfurl_links=False,
            unfurl_media=False,
            metadata={
                "event_type": f"reply_{event.type.value}",
                "event_payload": {
                    "reply_message_id": event.message_id or event.data["client_msg_id"],
                    "reply_session_id": event.session_id or event.message_id or event.data["client_msg_id"],
                }
            }
        )
        self.logger.debug("slack.client.chat_postMessage", blocks=blocks,
                          slack_response=json.dumps(response.data, ensure_ascii=False))

    def reply_blocks(self, event: SlackEvent, text: str, blocks: List[Dict[str, Any]], in_replies: bool = False) -> None:
        response = self.client.chat_postMessage(
            channel=event.channel,
            thread_ts=event.data["ts"] if in_replies else None,
            text=text,
            blocks=blocks,
            unfurl_links=False,
            unfurl_media=False,
            metadata={
                "event_type": f"reply_{event.type.value}",
                "event_payload": {
                    "reply_message_id": event.message_id or event.data["client_msg_id"],
                    "reply_session_id": event.session_id or event.message_id or event.data["client_msg_id"],
                }
            }
        )

        self.logger.debug("slack.client.chat_postMessage", blocks=blocks,
                          slack_response=json.dumps(response.data, ensure_ascii=False))


class SlackAsyncClient(BaseSlackClient):
    def __init__(self, config: SlackConfig, client: Optional[AsyncWebClient] = None, logger: Optional[logging.Logger] = None):
        super().__init__(config, logger)
        self.client = client or AsyncWebClient(token=config.bot_token)

    async def fetch_conversations_history(self, channel: str, limit: Optional[int], size: int = 100) -> SlackChannelHistory:
        result = SlackChannelHistory(channel=channel, pages=[])
        pages = 1

        history = await self.client.conversations_history(
            channel=channel, include_all_metadata=True, limit=size)
        result["pages"].append(history.data)
        self.logger.info(
            "fetch conversations history",
            page=pages,
            messages=len(history.data["messages"]),
            has_more=history.data["has_more"])

        while limit is not None and pages < limit:
            pages += 1
            if not history.data["has_more"]:
                break
            cursor = history.data["response_metadata"]["next_cursor"]
            history = await self.client.conversations_history(
                channel=channel, include_all_metadata=True, cursor=cursor, limit=size)
            result["pages"].append(history.data)
            self.logger.info(
                "fetch channel history",
                page=pages,
                messages=len(history.data["messages"]),
                cursor=cursor,
                has_more=history.data["has_more"])

        self.logger.debug("slack.client.conversations_history",
                          slack_channel_history=json.dumps(result, ensure_ascii=False))

        return result

    @backoff.on_exception(backoff.expo, SlackApiError, max_time=60, giveup=slack_api_error_is_not_retryable, logger=LoggerConfig().get_logger())
    async def fetch_conversations_replies(self, channel: str, thread_ts: str, limit: int = 150) -> List[SlackMessage]:
        self.logger.info("fetching conversations replies",
                         channel=channel, thread_ts=thread_ts)
        messages = []
        cursor = None

        page_limit = limit
        if page_limit > 1000:
            page_limit = 1000

        while True:
            if cursor:
                response = await self.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts,
                    inclusive=True,
                    limit=page_limit,
                    cursor=cursor,
                    include_all_metadata=True,
                )
            else:
                response = await self.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts,
                    inclusive=True,
                    limit=page_limit,
                    include_all_metadata=True,
                )
            messages.extend(response["messages"])
            if len(messages) >= limit:
                break
            if not response.get("has_more"):
                break
            cursor = response["response_metadata"]["next_cursor"]

        self.logger.debug("slack.client.conversations_replies", slack_thread_replies=json.dumps(
            messages, ensure_ascii=False))

        return messages

    async def find_session_id(self, event: SlackEvent, in_replies: bool = False) -> str:
        session_id = ""

        if in_replies and "thread_ts" in event.data:
            replies = await self.fetch_conversations_replies(
                event.channel, event.data["thread_ts"], 30)
            if len(replies) > 0:
                for reply in replies:
                    if "client_msg_id" in reply:
                        session_id = reply["client_msg_id"]
                        break

        else:
            conversations = await self.fetch_conversations_history(
                event.channel, 1, size=30)
            for message in conversations["pages"][0]["messages"]:
                if "subtype" in message or message["text"].strip() == "":
                    continue

                try:
                    current_session_id = message["metadata"]["event_payload"]["reply_session_id"]
                    if session_id == "":
                        session_id = current_session_id
                    elif session_id != current_session_id:
                        break
                except:
                    pass

        if session_id == "":
            session_id = event.data["client_msg_id"]

        return session_id

    async def add_reaction(self, event: SlackEvent, reaction: str) -> None:
        response = await self.client.reactions_add(
            channel=event.channel,
            timestamp=event.data["ts"],
            name=reaction.strip(":"),
        )
        self.logger.debug("slack.async_client.reactions_add", reaction=reaction,
                          slack_response=json.dumps(response.data, ensure_ascii=False))

    async def remove_reaction(self, event: SlackEvent, reaction: str) -> None:
        response = await self.client.reactions_remove(
            channel=event.channel,
            timestamp=event.data["ts"],
            name=reaction.strip(":"),
        )
        self.logger.debug("slack.async_client.reactions_remove", reaction=reaction,
                          slack_response=json.dumps(response.data, ensure_ascii=False))

    async def reply_markdown(self, event: SlackEvent, markdown: str, references: Optional[List[SlackMessageReference]] = None, in_replies: bool = False) -> None:
        blocks = [{
            "type": "markdown",
            "text": markdown
        }]

        if references:
            for reference in references:
                artifact_text = "\n".join(
                    [f"<{artifact.link}|{artifact.title}>" for artifact in reference.artifacts])
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"{reference.icon_emoji} *{reference.name}*\n{artifact_text}"
                    }]
                })

        blocks.append({
            "type": "context",
            "elements": [{
                    "type": "mrkdwn",
                    "text": self.config.get_message("content_disclaimer_message").text
            }]
        })

        response = await self.client.chat_postMessage(
            channel=event.channel,
            thread_ts=event.data["ts"] if in_replies else None,
            text=self.clean_markdown(markdown),
            blocks=blocks,
            unfurl_links=False,
            unfurl_media=False,
            metadata={
                "event_type": f"reply_{event.type.value}",
                "event_payload": {
                    "reply_message": event.data.get("text", ""),
                    "reply_message_id": event.message_id or event.data["client_msg_id"],
                    "reply_session_id": event.session_id or event.message_id or event.data["client_msg_id"],
                }
            }
        )
        self.logger.debug("slack.async_client.chat_postMessage", blocks=blocks,
                          slack_response=json.dumps(response.data, ensure_ascii=False))

    async def reply_blocks(self, event: SlackEvent, text: str, blocks: List[Dict[str, Any]], in_replies: bool = False) -> None:
        response = await self.client.chat_postMessage(
            channel=event.channel,
            thread_ts=event.data["ts"] if in_replies else None,
            text=text,
            blocks=blocks,
            unfurl_links=False,
            unfurl_media=False,
            metadata={
                "event_type": f"reply_{event.type.value}",
                "event_payload": {
                    "reply_message_id": event.message_id or event.data["client_msg_id"],
                    "reply_session_id": event.session_id or event.message_id or event.data["client_msg_id"],
                }
            }
        )

        self.logger.debug("slack.client.chat_postMessage", blocks=blocks,
                          slack_response=json.dumps(response.data, ensure_ascii=False))
