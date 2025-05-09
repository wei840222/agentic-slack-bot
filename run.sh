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
        streamlit run --theme.base=dark ./src/streamlit_web/👋_Hello.py
    ;;

   *)
        echo "not support command: $@"
        echo "available commands: slack-bot, mcp-server, web"
   ;;
esac
