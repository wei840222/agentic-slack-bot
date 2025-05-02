from functools import cache

from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from config import AgentConfig
from .tool import create_google_search_tool


@cache
def get_memory_saver():
    return MemorySaver()


def create_agent(agent_config: AgentConfig) -> Runnable:
    provider, model = agent_config.model.split("/", maxsplit=1)
    model = init_chat_model(model, model_provider=provider,
                            google_api_key=agent_config.google_api_key)

    tools = [create_google_search_tool(agent_config)]

    def create_system_prompt(state: AgentState, config: RunnableConfig) -> list[AnyMessage]:
        return [SystemMessage(PromptTemplate.from_template(agent_config.get_prompt("system").text).format(bot_id=config["metadata"]["bot_id"], channel_id=config["metadata"]["channel_id"]))] + state["messages"]

    return create_react_agent(
        model=model,
        tools=tools,
        checkpointer=get_memory_saver(),
        prompt=create_system_prompt,
        config_schema=AgentConfig,
    )
