from functools import cache

from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from config import AgentConfig
from .tool import create_google_search_tool


@cache
def get_memory_saver():
    return MemorySaver()


def create_agent(config: AgentConfig) -> Runnable:
    provider, model = config.model.split("/", maxsplit=1)
    model = init_chat_model(model, model_provider=provider,
                            google_api_key=config.google_api_key)

    tools = [create_google_search_tool()]

    return create_react_agent(
        model=model,
        tools=tools,
        checkpointer=get_memory_saver(),
        prompt=config.prompt.system,
        config_schema=AgentConfig,
    )
