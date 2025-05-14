#!/bin/sh

export PYTHONPATH=$PYTHONPATH:$(pwd)/src

case "$@" in
   "slack-bot")
        python -m slack_bot
    ;;

    "mcp-server")
        python -m mcp_server
    ;;

    "web")
        streamlit run --theme.base dark --browser.gatherUsageStats false ./src/streamlit_web/👋_Hello.py
    ;;

    "slack-loader")
        python -m loader.slack
    ;;

   *)
        echo "not support command: $@"
        echo "available commands: slack-bot, mcp-server, web, slack-loader"
   ;;
esac
