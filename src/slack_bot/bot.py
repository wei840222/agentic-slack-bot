import json
import random
import asyncio
import datetime
import logging
from typing import Dict, Any, Optional

from slack_bolt.app.async_app import AsyncApp, AsyncAssistant
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_bolt.context.say.async_say import AsyncSay
from slack_bolt.context.set_suggested_prompts.async_set_suggested_prompts import AsyncSetSuggestedPrompts
from slack_bolt.context.set_status.async_set_status import AsyncSetStatus
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from config import SlackConfig, AgentConfig
from agent.supervisor import create_supervisor_graph
from agent.parser import parse_agent_result
from agent.chain import create_check_new_conversation_chain
from .client import SlackAsyncClient
from .types import SlackEvent, SlackEventType, message_to_text


class SlackBot:
    def __init__(self, slack_config: SlackConfig, agent_config: AgentConfig, logger: Optional[logging.Logger] = None):
        self.logger = logger or slack_config.get_logger()
        self.config = slack_config
        self.agent_config = agent_config
        self.app = AsyncApp(token=self.config.bot_token)
        self.client = SlackAsyncClient(self.config, self.app.client, logger)
        self.handler = AsyncSocketModeHandler(self.app, self.config.app_token)
        self.event_queue = asyncio.Queue()
        self.tracker = self.agent_config.get_tracker()

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
        if self.tracker is not None:
            self.tracker.flush()

    async def _error_handler(self, body: Dict[str, Any]) -> None:
        self.logger.exception("catched exception",
                              slack_body=json.dumps(body, ensure_ascii=False))

    async def _handle_thread_started(self, say: AsyncSay, set_suggested_prompts: AsyncSetSuggestedPrompts):
        await say(self.config.get_message("assistant_greeting"))
        prompts = self.config.get_message_dicts("assistant_greeting_prompt")
        random.shuffle(prompts)
        await set_suggested_prompts(prompts=[{"title": prompt["title"], "message": prompt["message"]} for prompt in prompts[:4]])

    async def _handle_assistant_message(self, body: Dict[str, Any], set_status: AsyncSetStatus, ack: AsyncAck) -> None:
        self.logger.info("got slack assistant message event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        if "subtype" not in body["event"] and body["event"]["text"].strip() != "":
            event = SlackEvent(type=SlackEventType.MESSAGE, data=body["event"], user=body["event"]
                               ["user"], channel=body["event"]["channel"], message_id=body["event"]["client_msg_id"])
            await self.event_queue.put(event)
            await set_status(self.config.get_message("assistant_thinking"))
        await ack()

    async def _handle_message(self, body: Dict[str, Any], ack: AsyncAck) -> None:
        self.logger.info("got slack message event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        if "subtype" not in body["event"] and body["event"]["text"].strip() != "":
            event = SlackEvent(type=SlackEventType.MESSAGE, data=body["event"], user=body["event"]
                               ["user"], channel=body["event"]["channel"], message_id=body["event"]["client_msg_id"])
            await self.event_queue.put(event)
            await self.client.add_reaction(event, self.config.get_emoji("ai_thinking"))
        await ack()

    async def _handle_app_mention(self, body: Dict[str, Any], ack: AsyncAck) -> None:
        self.logger.info("got slack app_mention event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        if "edited" not in body["event"]:
            event = SlackEvent(type=SlackEventType.APP_MENTION, data=body["event"], user=body["event"]
                               ["user"], channel=body["event"]["channel"], message_id=body["event"]["client_msg_id"])
            await self.event_queue.put(event)
            await self.client.add_reaction(event, self.config.get_emoji("ai_thinking"))
        await ack()

    async def _handle_reaction_added(self, body: Dict[str, Any], ack: AsyncAck) -> None:
        self.logger.info("got slack reaction_added event",
                         slack_body=json.dumps(body, ensure_ascii=False))
        await self.event_queue.put(SlackEvent(type=SlackEventType.REACTION_ADDED, data=body["event"], user=body["event"]["user"], channel=body["event"]["item"]["channel"]))
        await ack()

    async def _process_message_event(self, event: SlackEvent) -> None:
        event.session_id = self.client.find_session_id(
            event, in_replies=self.config.assistant)

        runnable_config = await self.create_runnable_config(event, fetch_conversations_replies=False)
        if self.tracker is not None:
            runnable_config = self.tracker.inject_runnable_config(
                runnable_config)

        if not self.config.assistant:
            chain = create_check_new_conversation_chain(
                self.agent_config)
            is_new_conversation = await chain.ainvoke(
                input={"input": event.data["text"]},
                config=runnable_config,
            )
            if is_new_conversation.strip().lower() == "yes":
                await self.client.remove_reaction(event, self.config.get_emoji("ai_thinking"))
                event.session_id = None
                await self.client.reply_blocks(event, self.config.get_message("new_conversation_title"), [
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": self.config.get_message("new_conversation_message"),
                                "emoji": True
                            }
                        ]
                    },
                ])
                return

        agent = create_supervisor_graph(self.agent_config, self.config)
        agent_result = await agent.ainvoke(
            input={
                "messages": [HumanMessage(content=self.client.replace_channel_id_with_url(event.data["text"]))]
            },
            config=runnable_config,
        )
        self.logger.debug("agent_result", agent_result=agent_result)

        if not self.config.assistant:
            await self.client.remove_reaction(event, self.config.get_emoji("ai_thinking"))

        content, references = parse_agent_result(
            self.agent_config, agent_result)
        await self.client.reply_markdown(event, content, references, in_replies=self.config.assistant)

    async def _process_app_mention_event(self, event: SlackEvent) -> None:
        event.session_id = self.client.find_session_id(
            event, in_replies=True)

        runnable_config = await self.create_runnable_config(event)
        if self.tracker is not None:
            runnable_config = self.tracker.inject_runnable_config(
                runnable_config)

        agent = create_supervisor_graph(self.agent_config, self.config)
        agent_result = await agent.ainvoke(
            input={
                "messages": [HumanMessage(content=self.client.replace_channel_id_with_url(event.data["text"]))]
            },
            config=runnable_config,
        )
        self.logger.debug("agent_result", agent_result=agent_result)

        content, references = parse_agent_result(
            self.agent_config, agent_result)
        await self.client.remove_reaction(event, self.config.get_emoji("ai_thinking"))
        await self.client.reply_markdown(event, content, references, in_replies=True)

    async def _process_reaction_added_event(self, event: SlackEvent) -> None:
        if self.tracker is None:
            return

        replies = await self.client.fetch_conversations_replies(event.channel, event.data["item"]["ts"])
        for reply in replies:
            if reply["ts"] == event.data["item"]["ts"]:
                try:
                    self.logger.debug("found reply", reply=json.dumps(
                        reply, ensure_ascii=False))
                    self.tracker.collect_emoji_feedback(reply["metadata"]["event_payload"]["reply_message_id"], event.user,
                                                        reply["metadata"]["event_payload"]["reply_message"], reply["text"], event.data["reaction"], "slack")
                except KeyError:
                    self.logger.warning("no message_id or message found in reply",
                                        reply=json.dumps(reply, ensure_ascii=False))
                break

    async def create_runnable_config(self, event: SlackEvent, fetch_conversations_replies: bool = False) -> RunnableConfig:
        context = f"""
- Your name is <@{self.config.bot_id}> .
- User <@{event.user}> is asking you question.
- Current slack channel id is <#{event.channel}|> .
- Current slack channel url is {self.client.build_channel_url(event.channel)} .
- Current slack conversation url is {self.client.build_thread_url(event.channel, event.data["ts"], event.data["thread_ts"] if "thread_ts" in event.data else None)} .
- Current time is {datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")} .
"""

        if fetch_conversations_replies:
            context += "- Current slack conversations are as follows:"
            replies = await self.client.fetch_conversations_replies(
                event.channel, event.data["thread_ts"] if "thread_ts" in event.data else event.data["ts"])
            for reply in replies:
                context += f"""
<slack_conversation>
{message_to_text(reply)}
</slack_conversation>
    """

        slack_conversation_agent_context = f"""
- Current slack channel id is <#{event.channel}|> .
- Current slack channel url is {self.client.build_channel_url(event.channel)} .
- Current slack conversation url is {self.client.build_thread_url(event.channel, event.data["ts"], event.data["thread_ts"] if "thread_ts" in event.data else None)} .
"""

        return RunnableConfig(
            metadata={
                "user_id": event.user,
                "message_id": event.message_id,
                "session_id": event.session_id,
            },
            configurable={
                "context": context.strip(),
                "slack_conversation_agent_context": slack_conversation_agent_context.strip(),
                "thread_id": event.session_id,
            },
            tags=["slack", event.type.value],
            run_id=event.message_id,
        )
