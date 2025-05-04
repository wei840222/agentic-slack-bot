import json
import signal
import asyncio
from langchain_core.tools import ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient, SSEConnection
import langchain_mcp_adapters.tools
from langchain_mcp_adapters.tools import NonTextContent
from mcp.types import CallToolResult, TextContent, EmbeddedResource, TextResourceContents
from config import BaseConfig
from slack import SlackBot

config = BaseConfig()
logger = config.logger.get_logger()
logger.debug("config loaded", config=config)


def graceful_shutdown(sig: signal.Signals, task_to_cancel: set[asyncio.Task]) -> None:
    logger.info("received exit signal", sig=sig.name)
    for task in task_to_cancel:
        logger.info("cancelling task", task=task)
        task.cancel()


async def main() -> None:
    loop = asyncio.get_running_loop()
    task_to_cancel = {asyncio.current_task()}
    for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, graceful_shutdown, sig, task_to_cancel)

    async with SlackBot(config, logger) as bot:
        try:
            def _convert_call_tool_result(call_tool_result: CallToolResult) -> tuple[str | list[str], list[NonTextContent] | None]:
                text_contents: list[TextContent] = []
                non_text_contents = []
                for content in call_tool_result.content:
                    if isinstance(content, TextContent):
                        text_contents.append(content)
                    else:
                        if isinstance(content, EmbeddedResource) and isinstance(content.resource, TextResourceContents) and content.resource.mimeType == "application/json":
                            non_text_contents.append(
                                json.loads(content.resource.text))
                        else:
                            logger.warning(
                                "dropped unsupported non-text content", content=content)

                tool_content: str | list[str] = [
                    content.text for content in text_contents]
                if len(text_contents) == 1:
                    tool_content = tool_content[0]

                if call_tool_result.isError:
                    raise ToolException(tool_content)

                return tool_content, non_text_contents or None

            langchain_mcp_adapters.tools._convert_call_tool_result = _convert_call_tool_result

            async with MultiServerMCPClient(
                {
                    "Crawler": SSEConnection(transport="sse", url="http://localhost:8000/sse")
                }
            ) as client:
                config.agent.mcp_client = client
                await bot.run()
        except asyncio.exceptions.CancelledError:
            logger.info("slack handler cancelled")

if __name__ == "__main__":
    asyncio.run(main())
