import re
import json
import asyncio
import logging
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List

from pydantic import BaseModel
from slack_bolt.app.async_app import AsyncApp, AsyncAssistant
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_bolt.context.say.async_say import AsyncSay
from slack_bolt.context.set_suggested_prompts.async_set_suggested_prompts import AsyncSetSuggestedPrompts
from slack_bolt.context.set_status.async_set_status import AsyncSetStatus
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from emoji_sentiment import EmojiSentiment
from langchain_core.runnables import Runnable
from langchain_core.messages import HumanMessage

from config import Config, SlackConfig
from common import get_logger

logger = get_logger()

config = Config()


class SlackEventType(Enum):
    MESSAGE = "message"
    APP_MENTION = "app_mention"
    REACTION_ADDED = "reaction_added"


class SlackEvent(BaseModel):
    type: SlackEventType
    data: Dict[str, Any]
    message_id: Optional[str] = None
    session_id: Optional[str] = None


class ReferenceArtifact(BaseModel):
    title: str
    link: str
    content: Optional[str] = None


class Reference(BaseModel):
    name: str
    icon_emoji: str
    artifacts: List[ReferenceArtifact] = []


class SlackBot:
    emoji_sentiment = EmojiSentiment(round_to=4)

    def __init__(self, config: SlackConfig, agent: Runnable, logger: Optional[logging.Logger] = None):
        self.logger = logger or get_logger()
        self.config = config
        self.agent = agent
        self.app = AsyncApp(token=config.bot_token)
        self.handler = AsyncSocketModeHandler(self.app, config.app_token)
        self.event_queue = asyncio.Queue()

        if self.config.assistant:
            self.assistant = AsyncAssistant()
            self.assistant.thread_started(self._handle_thread_started)
            self.assistant.user_message(self._handle_assistant_message)
            self.app.use(self.assistant)

        # setup event listeners
        self.app.error(self._error_handler)
        if not self.config.assistant:
            self.app.event("message")(self._handle_message)
        self.app.event("app_mention")(self._handle_app_mention)
        self.app.event("reaction_added")(self._handle_reaction_added)

    async def run(self) -> None:
        await self.handler.start_async()

    async def __aenter__(self) -> "SlackBot":
        async def event_worker(queue: asyncio.Queue):
            self.logger.info("event worker started")
            while True:
                try:
                    event: SlackEvent = await queue.get()
                    if not event:
                        self.logger.info(
                            "all event processing tasks completed")
                        break
                    self.logger.info("processing event",
                                     data=event.model_dump_json())
                    match event.type:
                        case SlackEventType.APP_MENTION:
                            await self._process_app_mention_event(event)
                        case SlackEventType.REACTION_ADDED:
                            await self._process_reaction_added_event(event)
                        case SlackEventType.MESSAGE:
                            await self._process_message_event(event)
                        case _:
                            self.logger.warning("unknown event type",
                                                data=event.model_dump_json())
                except Exception as e:
                    self.logger.exception(f"error in worker: {e}")
                finally:
                    queue.task_done()

        asyncio.create_task(event_worker(self.event_queue))

        return self

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        await self.handler.close_async()
        await self.event_queue.put(None)
        self.logger.info("worker received sentinel and exiting")
        await self.event_queue.join()

    async def _error_handler(self, body: Dict[str, Any]) -> None:
        self.logger.exception("catched exception",
                              slack_body=json.dumps(body, ensure_ascii=False))

    async def _handle_thread_started(self, say: AsyncSay, set_suggested_prompts: AsyncSetSuggestedPrompts):
        await say(self.config.i18n.assistant.greeting_message)
        await set_suggested_prompts(prompts=self.config.i18n.assistant.greeting_prompts)

    async def _handle_assistant_message(self, body: Dict[str, Any], set_status: AsyncSetStatus, ack: AsyncAck) -> None:
        self.logger.info("got slack assistant message event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        if "subtype" not in body["event"] and body["event"]["text"].strip() != "":
            event = SlackEvent(type=SlackEventType.MESSAGE,
                               data=body["event"], message_id=body["event"]["client_msg_id"])
            await self.event_queue.put(event)
            await set_status(self.config.i18n.assistant.thinking_message)
        await ack()

    async def _handle_message(self, body: Dict[str, Any], ack: AsyncAck) -> None:
        self.logger.info("got slack message event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        if "subtype" not in body["event"] and body["event"]["text"].strip() != "":
            event = SlackEvent(type=SlackEventType.MESSAGE,
                               data=body["event"], message_id=body["event"]["client_msg_id"])
            await self.event_queue.put(event)
            await self.add_reaction(event, self.config.i18n.loading_emoji)
        await ack()

    async def _handle_app_mention(self, body: Dict[str, Any], ack: AsyncAck) -> None:
        self.logger.info("got slack app_mention event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        if "edited" not in body["event"]:
            event = SlackEvent(type=SlackEventType.APP_MENTION,
                               data=body["event"], message_id=body["event"]["client_msg_id"])
            await self.event_queue.put(event)
            await self.add_reaction(event, self.config.i18n.loading_emoji)
        await ack()

    async def _handle_reaction_added(self, body: Dict[str, Any], ack: AsyncAck) -> None:
        self.logger.info("got slack reaction_added event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        await self.event_queue.put(SlackEvent(type=SlackEventType.REACTION_ADDED, data=body["event"]))
        await ack()

    async def _process_message_event(self, event: SlackEvent) -> None:
        result = await self.agent.ainvoke(
            input={
                "messages": [HumanMessage(content=event.data["text"])]
            },
            config={
                "metadata": {
                    "user_id": event.data["user"],
                    "message_id": event.message_id or event.data["client_msg_id"],
                    "session_id": event.session_id or event.data["channel"],
                },
                "configurable": {
                    "thread_id": event.session_id or event.data["channel"],
                },
            })
        self.logger.debug("agent_result", agent_result=result)

        if not self.config.assistant:
            await self.remove_reaction(event, self.config.i18n.loading_emoji)

        await self.reply_markdown(event, result["messages"][-1].content, reply_in_thread=self.config.assistant)

    async def _process_app_mention_event(self, event: SlackEvent) -> None:
        await asyncio.sleep(1)
        await self.remove_reaction(event, self.config.i18n.loading_emoji)
        await self.reply_markdown(event, event.data["text"], reply_in_thread=True)

    async def _process_reaction_added_event(self, event: SlackEvent) -> None:
        pass

    async def add_reaction(self, event: SlackEvent, reaction: str) -> None:
        response = await self.app.client.reactions_add(
            channel=event.data["channel"],
            timestamp=event.data["ts"],
            name=reaction.strip(":"),
        )
        self.logger.debug("slack_app.client.reactions_add", reaction=reaction,
                          slack_response=json.dumps(response.data, ensure_ascii=False))

    async def remove_reaction(self, event: SlackEvent, reaction: str) -> None:
        response = await self.app.client.reactions_remove(
            channel=event.data["channel"],
            timestamp=event.data["ts"],
            name=reaction.strip(":"),
        )
        self.logger.debug("slack_app.client.reactions_remove", reaction=reaction,
                          slack_response=json.dumps(response.data, ensure_ascii=False))

    async def reply_markdown(self, event: SlackEvent, markdown: str, references: Optional[List[Reference]] = None, reply_in_thread: bool = False) -> None:
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
                    "text": self.config.i18n.content_disclaimer_message
            }]
        })

        response = await self.app.client.chat_postMessage(
            channel=event.data["channel"],
            thread_ts=event.data["ts"] if reply_in_thread else None,
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
        self.logger.debug("slack_app.client.chat_postMessage", blocks=blocks,
                          slack_response=json.dumps(response.data, ensure_ascii=False))

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
