import re
import json
import logging
import backoff
from urllib.parse import urlparse, parse_qs
from typing import Any, Dict, List, Optional, Tuple

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError

from config import SlackConfig, LoggerConfig
from agent.parser import Reference
from .types import SlackEvent, SlackMessage, SlackChannelHistory


def slack_api_error_is_not_retryable(e: SlackApiError):
    return e.response.status_code != 429


class BaseSlackClient:
    def __init__(self, config: SlackConfig, logger: Optional[logging.Logger] = None):
        self.logger = logger or config.get_logger()
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
    def get_channel_url_info(url: str) -> str:
        """
        Extract the channel ID and thread ts from a Slack Thread URL.
        example: https://xxxx.slack.com/archives/C0000000000

        Args:
            url: The thread URL to extract the channel ID from.

        Returns:
            A tuple containing the channel ID.
        """
        parsed_url = urlparse(url)
        match = re.search(r"/archives/([^/]+)", parsed_url.path)
        if match:
            return match.group(1)
        raise ValueError(f"Invalid Slack Thread URL: {url}")

    @staticmethod
    def get_thread_url_info(url: str, use_thread_ts: bool = False) -> Tuple[str, float]:
        """
        Extract the channel ID and ts from a Slack Thread URL.
        example: https://xxxx.slack.com/archives/C0000000000/p1741964293697769?thread_ts=1746204212.036359&cid=C08HWC49T9A

        Args:
            url: The thread URL to extract the channel ID and thread ts from.
            use_thread_ts: Whether to use the thread ts from the URL.

        Returns:
            A tuple containing the channel ID and ts.
        """
        parsed_url = urlparse(url)
        match = re.search(r"/archives/([^/]+)/p(\d+)", parsed_url.path)
        if match:
            query = parse_qs(parsed_url.query)
            if use_thread_ts and "thread_ts" in query:
                return match.group(1), float(query["thread_ts"][0])
            return match.group(1), int(match.group(2)) / 1000000
        raise ValueError(f"Invalid Slack Thread URL: {url}")

    @staticmethod
    def find_session_id(event: SlackEvent, in_replies: bool = False) -> str:
        if in_replies:
            thread_ts = event.data["thread_ts"] if "thread_ts" in event.data else event.data["ts"]
            session_key = f"{event.channel}-{thread_ts}"
        else:
            session_key = event.channel

        try:
            with open(f"./output/{session_key}", "r", encoding="utf-8") as f:
                session_id = f.read().strip()
        except FileNotFoundError:
            session_id = ""

        if session_id == "":
            session_id: str = event.data["client_msg_id"]
            with open(f"./output/{session_key}", "w", encoding="utf-8") as f:
                f.write(session_id)

        return session_id

    def replace_channel_id_with_url(self, text: str) -> str:
        return re.sub(r"<#([A-Z0-9]+)\|>",
                      f" {self.config.workspace_url}/archives/\\1 ", text)

    def build_channel_url(self, channel_id: str) -> str:
        """
        Build a Slack Channel URL.
        example: https://xxxx.slack.com/archives/C0000000000

        Args:
            channel_id: The channel ID.

        Returns:
            The Slack Channel URL.
        """
        return f"{self.config.workspace_url}/archives/{channel_id}"

    def build_thread_url(self, channel_id: str, ts: float, thread_ts: Optional[float] = None) -> str:
        """
        Build a Slack Thread URL.
        example: https://xxxx.slack.com/archives/C0000000000/p1741964293697769?thread_ts=1746204212.036359&cid=C08HWC49T9A

        Args:
            channel_id: The channel ID.
            ts: The timestamp of the message.
            thread_ts: The timestamp of the thread.

        Returns:
            The Slack Thread URL.
        """
        if thread_ts is None:
            return f"{self.config.workspace_url}/archives/{channel_id}/p{str(ts).replace('.', '')}"
        else:
            return f"{self.config.workspace_url}/archives/{channel_id}/p{str(ts).replace('.', '')}?thread_ts={str(thread_ts)}&cid={channel_id}"


class SlackClient(BaseSlackClient):
    def __init__(self, config: SlackConfig, client: Optional[WebClient] = None, logger: Optional[logging.Logger] = None):
        super().__init__(config, logger)
        self.client = client or WebClient(token=config.bot_token)

    @backoff.on_exception(backoff.expo, SlackApiError, max_time=600, giveup=slack_api_error_is_not_retryable, logger=LoggerConfig().logger)
    def fetch_conversations_history(self, channel: str, limit: Optional[int], size: int = 15) -> SlackChannelHistory:
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

    @backoff.on_exception(backoff.expo, SlackApiError, max_time=600, giveup=slack_api_error_is_not_retryable, logger=LoggerConfig().logger)
    def fetch_conversations_replies(self, channel: str, ts: str, limit: Optional[int] = None) -> List[SlackMessage]:
        self.logger.info("fetching conversations replies",
                         channel=channel, ts=ts)
        messages = []
        cursor = None

        while True:
            if cursor:
                response = self.client.conversations_replies(
                    channel=channel,
                    ts=ts,
                    limit=15,
                    cursor=cursor,
                    include_all_metadata=True,
                )
            else:
                response = self.client.conversations_replies(
                    channel=channel,
                    ts=ts,
                    limit=15,
                    include_all_metadata=True,
                )
            messages.extend(response["messages"])
            if not response.get("has_more"):
                break
            cursor = response["response_metadata"]["next_cursor"]

        self.logger.debug("slack.client.conversations_replies", slack_thread_replies=json.dumps(
            messages, ensure_ascii=False))

        if limit is not None:
            return messages[:limit]
        return messages

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

    def reply_markdown(self, event: SlackEvent, markdown: str, references: Optional[List[Reference]] = None, in_replies: bool = False) -> None:
        blocks = [{
            "type": "markdown",
            "text": markdown
        }]

        if len(blocks[0]["text"]) > 10000:
            blocks[0]["text"] = blocks[0]["text"][:10000]
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": self.config.get_message("ai_reply_too_long_warning_message"),
                        "emoji": True
                    }
                ]
            })
            self.logger.warning("slack.client.reply_markdown got too long message",
                                markdown_length=len(markdown))

        if references:
            for reference in references:
                artifact_text = "\n".join(
                    [f"<{artifact.link}|{artifact.title}>" for artifact in reference.artifacts])
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"{reference.icon_emoji} *{reference.title}*\n`#{reference.source}`\n{artifact_text}"
                    }]
                })

        blocks.append({
            "type": "context",
            "elements": [{
                    "type": "mrkdwn",
                    "text": self.config.get_message("content_disclaimer_message")
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
                    "reply_message": event.data["text"],
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
                    "reply_message": event.data["text"],
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

    @backoff.on_exception(backoff.expo, SlackApiError, max_time=600, giveup=slack_api_error_is_not_retryable, logger=LoggerConfig().logger)
    async def fetch_conversations_history(self, channel: str, limit: Optional[int], size: int = 15) -> SlackChannelHistory:
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

    @backoff.on_exception(backoff.expo, SlackApiError, max_time=600, giveup=slack_api_error_is_not_retryable, logger=LoggerConfig().logger)
    async def fetch_conversations_replies(self, channel: str, ts: str, limit: Optional[int] = None) -> List[SlackMessage]:
        self.logger.info("fetching conversations replies",
                         channel=channel, ts=ts)
        messages = []
        cursor = None

        while True:
            if cursor:
                response = await self.client.conversations_replies(
                    channel=channel,
                    ts=ts,
                    limit=200,
                    cursor=cursor,
                    include_all_metadata=True,
                )
            else:
                response = await self.client.conversations_replies(
                    channel=channel,
                    ts=ts,
                    limit=200,
                    include_all_metadata=True,
                )
            messages.extend(response["messages"])
            if not response.get("has_more"):
                break
            cursor = response["response_metadata"]["next_cursor"]

        self.logger.debug("slack.async_client.conversations_replies", slack_thread_replies=json.dumps(
            messages, ensure_ascii=False))

        if limit is not None:
            return messages[:limit]
        return messages

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

    async def reply_markdown(self, event: SlackEvent, markdown: str, references: Optional[List[Reference]] = None, in_replies: bool = False) -> None:
        blocks = [{
            "type": "markdown",
            "text": markdown
        }]

        if len(blocks[0]["text"]) > 10000:
            blocks[0]["text"] = blocks[0]["text"][:10000]
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": self.config.get_message("ai_reply_too_long_warning_message"),
                        "emoji": True
                    }
                ]
            })
            self.logger.warning("slack.async_client.reply_markdown got too long message",
                                markdown_length=len(markdown))

        if references:
            for reference in references:
                artifact_text = "\n".join(
                    [f"<{artifact.link}|{artifact.title}>" for artifact in reference.artifacts])
                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"{reference.icon_emoji} *{reference.title}*\n`#{reference.source}`\n{artifact_text}"
                    }]
                })

        blocks.append({
            "type": "context",
            "elements": [{
                    "type": "mrkdwn",
                    "text": self.config.get_message("content_disclaimer_message")
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
                    "reply_message": event.data["text"],
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
                    "reply_message": event.data["text"],
                    "reply_message_id": event.message_id or event.data["client_msg_id"],
                    "reply_session_id": event.session_id or event.message_id or event.data["client_msg_id"],
                }
            }
        )

        self.logger.debug("slack.async_client.chat_postMessage", blocks=blocks,
                          slack_response=json.dumps(response.data, ensure_ascii=False))
