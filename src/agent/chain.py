from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import AgentConfig


def create_check_new_conversation_chain(config: AgentConfig) -> Runnable:
    "prompt_name: check_new_conversation"

    provider, model = config.model.split("/", maxsplit=1)
    model = init_chat_model(model, model_provider=provider,
                            google_api_key=config.google_api_key)
    prompt = ChatPromptTemplate.from_messages([
        HumanMessagePromptTemplate.from_template(
            config.get_prompt("check_new_conversation").text),
    ])

    parser = StrOutputParser()

    return prompt | model | parser


def create_make_title_chain(config: AgentConfig) -> Runnable:
    "prompt_name: make_title"

    provider, model = config.model.split("/", maxsplit=1)
    model = init_chat_model(model, model_provider=provider,
                            google_api_key=config.google_api_key)
    prompt = ChatPromptTemplate.from_messages([
        HumanMessagePromptTemplate.from_template(
            config.get_prompt("make_title").text),
    ])

    parser = StrOutputParser()

    return prompt | model | parser
