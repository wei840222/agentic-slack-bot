from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.messages.utils import trim_messages, count_tokens_approximately
from langchain_core.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.prebuilt import create_react_agent

from config import AgentConfig
from .tool import create_google_search_tool, create_markitdown_crawler_tool


def create_agent(agent_config: AgentConfig) -> Runnable:
    logger = agent_config.get_logger()
    provider, model = agent_config.model.split("/", maxsplit=1)

    model = init_chat_model(model, model_provider=provider,
                            google_api_key=agent_config.google_api_key)

    tools = [create_google_search_tool(
        agent_config), create_markitdown_crawler_tool(agent_config)]

    def trim_messages_hook(state: AgentState) -> AgentState:
        full_messages = state["messages"]

        if not isinstance(full_messages[-1], HumanMessage) or len(full_messages) == 1:
            return {"messages": []}

        trimmed_messages = trim_messages(
            full_messages,
            strategy="last",
            token_counter=count_tokens_approximately,
            max_tokens=agent_config.checkpointer_max_tokens,
            start_on=HumanMessage,
            end_on=HumanMessage,
        )
        if trimmed_messages[0].id == full_messages[0].id:
            return {"messages": []}

        dropped_messages = []
        for message in full_messages:
            if message.id == trimmed_messages[0].id:
                break
            dropped_messages.append(message)

        logger.debug("trimmed", trimmed_messages=trimmed_messages,
                     dropped_messages=dropped_messages)

        return {"messages": [RemoveMessage(REMOVE_ALL_MESSAGES)] + trimmed_messages}

    def create_system_prompt(state: AgentState, config: RunnableConfig) -> list[AnyMessage]:
        prompt_template = PromptTemplate.from_template(
            agent_config.get_prompt("system").text)
        system_message = SystemMessage(prompt_template.format(
            context=config["configurable"]["context"]))
        return [system_message] + state["messages"]

    return create_react_agent(
        state_schema=AgentState,
        config_schema=AgentConfig,
        model=model,
        tools=tools,
        pre_model_hook=trim_messages_hook,
        prompt=create_system_prompt,
        checkpointer=agent_config.get_checkpointer(),
    )


def create_web_research_agent(agent_config: AgentConfig) -> Runnable:
    provider, model = agent_config.model.split("/", maxsplit=1)

    model = init_chat_model(model, model_provider=provider,
                            google_api_key=agent_config.google_api_key)

    tools = [create_google_search_tool(
        agent_config), create_markitdown_crawler_tool(agent_config)]

    def create_system_prompt(state: AgentState) -> list[AnyMessage]:
        return [SystemMessage(agent_config.get_prompt("web_research_agent_system_prompt").text)] + state["messages"]

    return create_react_agent(
        name="web_research_agent",
        state_schema=AgentState,
        config_schema=AgentConfig,
        model=model,
        tools=tools,
        prompt=create_system_prompt,
    )
