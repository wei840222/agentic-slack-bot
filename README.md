# agentic-slack-bot

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
AGENT_CHECKPOINTER_MONGODB_URI=mongodb+srv://agentic-slack-bot:OSObpkkaF80GgR9D@agent-memory.8flud3o.mongodb.net/?retryWrites=true&w=majority&appName=agent-memory
AGENT_TRACKING_PROVIDER=langsmith
LANGSMITH_PROJECT=xxxxxx
LANGSMITH_API_KEY=lsv2_xxxxxxxxx
GOOGLE_API_KEY=xxxxxxxx
GOOGLE_CSE_ID=xxxxxxxx
QDRANT_HOST=xxxxxx.cloud.qdrant.io
QDRANT_API_KEY=xxxxxxxxxx
```

How to run local ?

```
./run.sh web
./run.sh slack-bot
./run.sh mcp-server
```
