from langchain_core.runnables import Runnable
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import AgentConfig


def create_check_new_conversation_chain(config: AgentConfig) -> Runnable:
    "prompt_name: check_new_conversation"

    model = config.load_chat_model()
    prompt = ChatPromptTemplate.from_messages([
        HumanMessagePromptTemplate.from_template(
            config.get_prompt("check_new_conversation").text),
    ])

    parser = StrOutputParser()

    return prompt | model | parser


def create_make_title_chain(config: AgentConfig) -> Runnable:
    "prompt_name: make_title"

    model = config.load_chat_model()
    prompt = ChatPromptTemplate.from_messages([
        HumanMessagePromptTemplate.from_template(
            config.get_prompt("make_title").text),
    ])

    parser = StrOutputParser()

    return prompt | model | parser
