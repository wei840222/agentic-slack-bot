#!/bin/sh

PYTHONPATH=$PYTHONPATH:$(pwd)/src

case "$@" in
   "slack-bot")
        python -m slack_bot
    ;;

    "mcp-server")
        python -m mcp_server
    ;;

   *)
        echo "not support command: $@"
        echo "available commands: slack-bot, mcp-server"
   ;;
esac
