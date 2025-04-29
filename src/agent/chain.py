from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import AgentConfig


def create_check_new_conversation_chain(config: AgentConfig) -> Runnable:
    provider, model = config.model.split("/", maxsplit=1)
    model = init_chat_model(model, model_provider=provider,
                            google_api_key=config.google_api_key)
    prompt = ChatPromptTemplate.from_messages([
        HumanMessagePromptTemplate.from_template(
            config.prompt.chain["check_new_conversation"]),
    ])

    parser = StrOutputParser()

    return prompt | model | parser
