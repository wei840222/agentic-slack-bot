import streamlit as st

from config import SlackConfig
from slack_bot.client import SlackClient

st.set_page_config(
    page_title="Slack Conversations",
    page_icon="💬",
    layout="wide",
)


@st.cache_resource
def get_slack_config() -> SlackConfig:
    config = SlackConfig()
    config.get_logger().debug("config loaded", config=config)
    return config


@st.cache_resource
def get_slack_client() -> SlackClient:
    config = get_slack_config()
    return SlackClient(config)


st.title("Slack Conversations 💬")

st.sidebar.header("Document")
st.sidebar.markdown(
    "[conversations.history](https://api.slack.com/methods/conversations.history)")
st.sidebar.markdown(
    "[conversations.replies](https://api.slack.com/methods/conversations.replies)")

client = get_slack_client()


col1, col2, col3 = st.columns(3)
with col1:
    channel_url = st.text_input(
        "Channel url", value="https://helenworkspacegroup.slack.com/archives/C08HWC49T9A")
with col2:
    history_page_size = st.number_input(
        "Page size", min_value=1, max_value=100, value=3)
with col3:
    history_limit = st.number_input(
        "Page number limit", min_value=1, value=1)


if channel_url:
    channel_id = client.get_channel_url_info(channel_url)
    if historys := client.fetch_conversations_history(channel_id, size=history_page_size, limit=history_limit):
        st.markdown(f"**Channel ID**")
        st.markdown(f"`{channel_id}`")
        with st.expander("Historys"):
            st.write(historys)
    else:
        st.markdown("No messages found.")


st.write("---")

col11, col12 = st.columns(2)
with col11:
    message_url = st.text_input(
        "Message url", value="https://helenworkspacegroup.slack.com/archives/C08HWC49T9A/p1746204212036359")
with col12:
    message_limit = st.number_input(
        "Message number limit", min_value=1, max_value=150, value=1)

if message_url:
    channel_id, thread_ts = client.get_thread_url_info(message_url)
    if messages := client.fetch_conversations_replies(channel_id, thread_ts, limit=message_limit):
        st.markdown(f"**Channel ID**")
        st.markdown(f"`{channel_id}`")
        st.markdown(f"**Thread TS**")
        st.write(thread_ts)
        with st.expander("Messages"):
            st.write(messages)
    else:
        st.markdown("No messages found.")
