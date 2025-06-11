from langchain_core.runnables import Runnable
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.prebuilt import create_react_agent

from config import AgentConfig, SlackConfig
from .tool import create_google_search_tool, create_markitdown_crawler_tool, create_get_slack_conversation_replies_tool, create_get_slack_conversation_history_tool, create_search_slack_conversation_tool


def create_web_research_agent(agent_config: AgentConfig) -> Runnable:
    "prompt_name: web_research_agent_system_prompt"

    model = agent_config.load_chat_model()
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


def create_slack_conversation_agent(agent_config: AgentConfig, slack_config: SlackConfig) -> Runnable:
    "prompt_name: slack_conversation_agent_system_prompt"

    model = agent_config.load_chat_model()
    tools = [create_get_slack_conversation_replies_tool(
        slack_config), create_get_slack_conversation_history_tool(slack_config), create_search_slack_conversation_tool(slack_config)]

    def create_system_prompt(state: AgentState, config: RunnableConfig) -> list[AnyMessage]:
        prompt_template = PromptTemplate.from_template(
            agent_config.get_prompt("slack_conversation_agent_system_prompt").text)
        system_message = SystemMessage(prompt_template.format(
            context=config["configurable"]["slack_conversation_agent_context"]))
        return [system_message] + state["messages"]

    return create_react_agent(
        name="slack_conversation_agent",
        state_schema=AgentState,
        config_schema=AgentConfig,
        model=model,
        tools=tools,
        prompt=create_system_prompt,
    )
