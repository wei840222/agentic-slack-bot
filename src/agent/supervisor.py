from langchain.chat_models import init_chat_model
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph_supervisor import create_supervisor

from config import AgentConfig, SlackConfig
from .agent import create_web_research_agent, create_slack_conversation_agent


def create_supervisor_graph(agent_config: AgentConfig, slack_config: SlackConfig) -> StateGraph:
    """
    prompt_name: supervisor_agent_system_prompt

    LangGraph command hand-off will raise error on Langfuse ui. It's normal.
    https://github.com/langfuse/langfuse/issues/5035
    """

    provider, model = agent_config.model.split("/", maxsplit=1)

    model = init_chat_model(model, model_provider=provider,
                            google_api_key=agent_config.google_api_key)
    web_research_agent = create_web_research_agent(agent_config)
    slack_conversation_agent = create_slack_conversation_agent(
        agent_config, slack_config)

    def create_system_prompt(state: AgentState, config: RunnableConfig) -> list[AnyMessage]:
        prompt_template = PromptTemplate.from_template(
            agent_config.get_prompt("supervisor_agent_system_prompt").text)
        system_message = SystemMessage(prompt_template.format(
            context=config["configurable"]["context"]))
        return [system_message] + state["messages"]

    supervisor_graph = create_supervisor(
        model=model,
        agents=[web_research_agent, slack_conversation_agent],
        state_schema=AgentState,
        config_schema=AgentConfig,
        prompt=create_system_prompt,
        add_handoff_messages=True,
        add_handoff_back_messages=True,
        handoff_tool_prefix="delegate_to_",
        output_mode="full_history",
        include_agent_name="inline",
        supervisor_name="supervisor_agent",
    )

    return supervisor_graph.compile(checkpointer=agent_config.get_checkpointer(async_mongodb=agent_config.checkpointer_mongodb_async))
