import asyncio
import signal


from config import SlackConfig, AgentConfig
from .bot import SlackBot


slack_config = SlackConfig()
agent_config = AgentConfig()
logger = slack_config.get_logger()
logger.debug("config loaded", slack_config=slack_config,
             agent_config=agent_config)


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

    async with SlackBot(slack_config, agent_config, logger) as bot:
        try:
            await bot.run()
        except asyncio.exceptions.CancelledError:
            logger.info("slack handler cancelled")

if __name__ == "__main__":
    asyncio.run(main())
