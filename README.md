# agentic-slack-bot

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/wei840222/agentic-slack-bot)

You need to prepare .env file like following to run the bot.

```
LOG_LEVEL=DEBUG
SLACK_APP_TOKEN=xapp-xxxxx
SLACK_BOT_TOKEN=xoxb-xxxxx
SLACK_BOT_ID=U000000000
SLACK_WORKSPACE_URL=https://xxxxxworkspacegroup.slack.com
SLACK_ASSISTANT=true
PROMPT_PROVIDER=langsmith
AGENT_CHECKPOINTER_PROVIDER=mongodb
AGENT_CHECKPOINTER_MONGODB_URI=mongodb://xxx:xxx@localhost:27017
AGENT_TRACKING_PROVIDER=langsmith
RAG_MODEL=google_vertexai/gemini-2.0-flash
LANGSMITH_PROJECT=xxxxxx
LANGSMITH_API_KEY=lsv2_xxxxxxxxx
GOOGLE_API_KEY=xxxxxxxx
GOOGLE_CSE_ID=xxxxxxxx
QDRANT_HOST=xxxxxx.cloud.qdrant.io
QDRANT_API_KEY=xxxxxxxxxx
```

How to run local ?

1. `./run.sh slack-bot` to run slack bot
2. `./run.sh rag-slack-loader` to load data from slack to qdrant
3. `./run.sh mcp-server` run mcp server
4. `./run.sh streamlit-web` to run demo website
