import json
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple, List

from slack_bolt.app.async_app import AsyncApp, AsyncAssistant
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_bolt.context.say.async_say import AsyncSay
from slack_bolt.context.set_suggested_prompts.async_set_suggested_prompts import AsyncSetSuggestedPrompts
from slack_bolt.context.set_status.async_set_status import AsyncSetStatus
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from emoji_sentiment import EmojiSentiment
from langchain_core.runnables import Runnable
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from .client import SlackEvent, SlackEventType, SlackAsyncClient, SlackMessageReference, SlackMessageReferenceArtifact
from config import SlackConfig
from common import get_logger


class SlackBot:
    emoji_sentiment = EmojiSentiment(round_to=4)

    def __init__(self, config: SlackConfig, agent: Runnable, logger: Optional[logging.Logger] = None):
        self.logger = logger or get_logger()
        self.config = config
        self.app = AsyncApp(token=config.bot_token)
        self.client = SlackAsyncClient(config, self.app.client, logger)
        self.agent = agent
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
        await say(self.config.resources.assistant.greeting_message)
        await set_suggested_prompts(prompts=self.config.resources.assistant.greeting_prompts)

    async def _handle_assistant_message(self, body: Dict[str, Any], set_status: AsyncSetStatus, ack: AsyncAck) -> None:
        self.logger.info("got slack assistant message event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        if "subtype" not in body["event"] and body["event"]["text"].strip() != "":
            event = SlackEvent(type=SlackEventType.MESSAGE,
                               data=body["event"], message_id=body["event"]["client_msg_id"])
            await self.event_queue.put(event)
            await set_status(self.config.resources.assistant.thinking_message)
        await ack()

    async def _handle_message(self, body: Dict[str, Any], ack: AsyncAck) -> None:
        self.logger.info("got slack message event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        if "subtype" not in body["event"] and body["event"]["text"].strip() != "":
            event = SlackEvent(type=SlackEventType.MESSAGE,
                               data=body["event"], message_id=body["event"]["client_msg_id"])
            await self.event_queue.put(event)
            await self.client.add_reaction(event, self.config.resources.emoji["loading"])
        await ack()

    async def _handle_app_mention(self, body: Dict[str, Any], ack: AsyncAck) -> None:
        self.logger.info("got slack app_mention event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        if "edited" not in body["event"]:
            event = SlackEvent(type=SlackEventType.APP_MENTION,
                               data=body["event"], message_id=body["event"]["client_msg_id"])
            await self.event_queue.put(event)
            await self.client.add_reaction(event, self.config.resources.emoji["loading"])
        await ack()

    async def _handle_reaction_added(self, body: Dict[str, Any], ack: AsyncAck) -> None:
        self.logger.info("got slack reaction_added event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        await self.event_queue.put(SlackEvent(type=SlackEventType.REACTION_ADDED, data=body["event"]))
        await ack()

    async def _process_message_event(self, event: SlackEvent) -> None:
        event.session_id = await self.client.find_session_id(
            event, in_replies=self.config.assistant)

        result = await self.agent.ainvoke(
            input={
                "messages": [HumanMessage(content=event.data["text"])]
            },
            config={
                "metadata": {
                    "user_id": event.data["user"],
                    "message_id": event.message_id,
                    "session_id": event.session_id,
                },
                "configurable": {
                    "thread_id": event.session_id,
                },
            })
        self.logger.debug("agent_result", agent_result=result)

        if not self.config.assistant:
            await self.client.remove_reaction(event, self.config.resources.emoji["loading"])

        content, references = self.parse_agent_result(result)
        await self.client.reply_markdown(event, content, references, in_replies=self.config.assistant)

    async def _process_app_mention_event(self, event: SlackEvent) -> None:
        event.session_id = await self.client.find_session_id(
            event, in_replies=True)

        result = await self.agent.ainvoke(
            input={
                "messages": [HumanMessage(content=event.data["text"])]
            },
            config={
                "metadata": {
                    "user_id": event.data["user"],
                    "message_id": event.message_id,
                    "session_id": event.session_id,
                },
                "configurable": {
                    "thread_id": event.session_id,
                },
            })
        self.logger.debug("agent_result", agent_result=result)

        content, references = self.parse_agent_result(result)
        await self.client.remove_reaction(event, self.config.resources.emoji["loading"])
        await self.client.reply_markdown(event, content, references, in_replies=True)

    async def _process_reaction_added_event(self, event: SlackEvent) -> None:
        pass

    def parse_agent_result(self, result: Dict[str, Any]) -> Tuple[str, List[SlackMessageReference]]:
        content: str | list[str | dict] = result["messages"][-1].content

        if isinstance(content, list):
            text_item = []
            for result_item in result:
                match result_item:
                    case str():
                        if result_item.strip() == "":
                            continue
                        text_item.append(result_item)
                    case _:
                        self.logger.warning("unknown result item type", result_item=json.dumps(
                            result_item, ensure_ascii=False))
            if len(text_item) <= 0:
                text_item.append("...")
            content = "\n".join(text_item)
        content = content.strip()

        references: List[SlackMessageReference] = []
        found_ai_message = False
        for message in result["messages"][::-1]:
            if isinstance(message, AIMessage):
                if found_ai_message:
                    break
                found_ai_message = True
                continue
            if not isinstance(message, ToolMessage):
                continue
            tool_message = message
            if isinstance(tool_message.artifact, list) and len(tool_message.artifact) > 0 and tool_message.name in self.config.resources.artifact_icon_emoji.keys():
                references.append(SlackMessageReference(
                    name=self.config.resources.tool_reference_message,
                    icon_emoji=self.config.resources.artifact_icon_emoji[tool_message.name],
                    artifacts=[SlackMessageReferenceArtifact(title=artifact["title"], link=artifact["link"]) for artifact in tool_message.artifact if isinstance(
                        artifact["title"], str) and isinstance(artifact["link"], str)]
                ))
                break

        return content, references
