import streamlit as st

from config import SlackConfig
from slack_bot.client import SlackClient
from slack_bot.types import message_to_text

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

st.subheader("Conversations History")

col1, col2, col3 = st.columns(3)
with col1:
    channel_url = st.text_input(
        "url", value="https://wei840222-home-infra.slack.com/archives/C090F9D535M")
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
        with st.expander("Text"):
            for page in historys["pages"]:
                for message in page["messages"]:
                    st.code(message_to_text(message), language="markdown")
        with st.expander("JSON"):
            st.write(historys)
    else:
        st.markdown("No messages found.")


st.divider()

st.subheader("Conversations Replies")

col11, col12 = st.columns(2)
with col11:
    message_url = st.text_input(
        "url", value="https://wei840222-home-infra.slack.com/archives/C090X8VPDA9/p1749644769616199?thread_ts=1749644760.262149&cid=C090X8VPDA9")
with col12:
    message_limit = st.number_input(
        "Message number limit", min_value=1, max_value=150, value=3)
use_thread_ts = st.checkbox("Use thread ts", value=True)

if message_url:
    channel_id, thread_ts = client.get_thread_url_info(
        message_url, use_thread_ts)
    if messages := client.fetch_conversations_replies(channel_id, thread_ts, limit=message_limit):
        st.markdown(f"**Channel ID**")
        st.markdown(f"`{channel_id}`")
        st.markdown(f"**Thread TS**")
        st.write(thread_ts)
        with st.expander("Text"):
            for message in messages:
                st.code(message_to_text(message), language="markdown")
        with st.expander("JSON"):
            st.write(messages)
    else:
        st.markdown("No messages found.")
