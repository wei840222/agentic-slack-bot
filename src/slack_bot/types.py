from enum import Enum
import datetime
from typing import Any, Dict, List, TypedDict, Optional

from pydantic import BaseModel


class SlackMessage(TypedDict):
    type: str
    subtype: str | None

    user: Optional[str]
    username: Optional[str]
    team: Optional[str]
    bot_id: Optional[str]
    bot_profile: Optional[Dict[str, Any]]
    app_id: Optional[str]

    ts: str
    thread_ts: Optional[str]
    edited: Optional[Dict[str, str]]

    client_msg_id: Optional[str]
    parent_user_id: Optional[str]

    reply_count: Optional[int]
    reply_users_count: Optional[int]
    reply_users: Optional[List[str]]
    latest_reply: Optional[str]
    subscribed: Optional[bool]
    is_locked: Optional[bool]

    text: str
    icons: Optional[Dict[str, Any]]
    attachments: Optional[List[Dict[str, Any]]]
    blocks: Optional[List[Dict[str, Any]]]
    reactions: Optional[List[Dict[str, Any]]]
    metadata: Optional[Dict[str, Any]]


def attachments_to_text(message: SlackMessage) -> Optional[str]:
    if message.get("attachments") is None:
        return None

    contents = []
    for attachment in message["attachments"]:
        content = ""
        for key in ("service_name", "title", "title_link", "text"):
            if key in attachment:
                content += f"> {key}: {attachment[key]}\n"
        contents.append(content.strip())

    if contents:
        return "\n\n".join(contents)

    return None


def reactions_to_text(message: SlackMessage) -> Optional[str]:
    if message.get("reactions") is None:
        return None

    contents = []
    for reaction in message["reactions"]:
        contents.append(
            f"> {reaction['name']}: {', '.join([f'<@{user}>' for user in reaction['users']])}")

    if contents:
        return "\n".join(contents)

    return None


def message_to_text(message: SlackMessage) -> Optional[str]:
    if message["type"] != "message":
        return None

    content = f"Time:\n{datetime.datetime.fromtimestamp(float(message['ts']), datetime.timezone.utc).isoformat().replace("+00:00", "Z")}\n\n"

    if message.get("subtype", "") == "bot_message":
        if "username" in message:
            content += f"Post Author:\n{message['username']}\n\n"
        if text := message.get("text", ""):
            content += f"Post:\n{text}\n\n"
    else:
        content += f"User:\n<@{message['user']}>\n\n"
        content += f"Message:\n{message['text']}\n\n"

    if attachments := attachments_to_text(message):
        content += f"Attachments:\n{attachments}\n\n"

    if reactions := reactions_to_text(message):
        content += f"Reactions:\n{reactions}\n\n"

    return content.strip()


class SlackChannelHistoryPage(TypedDict):
    ok: bool
    messages: List[SlackMessage]
    has_more: bool
    is_limited: bool
    pin_count: Optional[int]
    channel_actions_ts: Optional[str]
    channel_actions_count: Optional[int]
    response_metadata: Dict[str, Any]


class SlackChannelHistory(TypedDict):
    channel: str
    pages: List[SlackChannelHistoryPage]


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
