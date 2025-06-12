#!/bin/sh

export PYTHONPATH=$PYTHONPATH:$(pwd)/src

case "$@" in
   "slack-bot")
        python -m slack_bot
    ;;

    "rag-slack-loader")
        python -m rag_loader.slack
    ;;

    "mcp-server")
        python -m mcp_server
    ;;

    "streamlit-web")
        streamlit run --browser.gatherUsageStats false ./src/streamlit_web/👋_Hello.py
    ;;

    *)
        echo "not support command: $@"
        echo "available commands: slack-bot, rag-slack-loader, mcp-server, streamlit-web"
    ;;
esac
