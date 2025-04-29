import signal
import asyncio

from common import get_logger
from config import Config
from slack import SlackBot
from agent import create_agent

logger = get_logger()


def graceful_shutdown(sig: signal.Signals, task_to_cancel: set[asyncio.Task]) -> None:
    logger.info("received exit signal", sig=sig.name)
    for task in task_to_cancel:
        logger.info("cancelling task", task=task)
        task.cancel()


async def main() -> None:
    config = Config()
    logger.debug("config loaded", config=config)

    agent = create_agent(config.agent)
    logger.debug("agent created", agent=agent.get_config_jsonschema())

    loop = asyncio.get_running_loop()
    task_to_cancel = {asyncio.current_task()}
    for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, graceful_shutdown, sig, task_to_cancel)

    async with SlackBot(config.slack, agent, logger) as bot:
        try:
            await bot.run()
        except asyncio.exceptions.CancelledError:
            logger.info("slack handler cancelled")

if __name__ == "__main__":
    asyncio.run(main())
