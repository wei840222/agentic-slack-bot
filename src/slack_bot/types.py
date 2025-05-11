from enum import Enum
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
