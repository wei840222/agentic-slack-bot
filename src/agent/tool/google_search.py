from functools import cache
from typing import List, Tuple, Dict, Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg
from langchain.tools import BaseTool, tool
from langchain_google_community import GoogleSearchAPIWrapper

from config import AgentConfig


@cache
def create_google_search_tool() -> BaseTool:

    config = AgentConfig()
    google_search_api = GoogleSearchAPIWrapper(
        google_api_key=config.google_api_key,
        google_cse_id=config.google_cse_id
    )

    @tool(response_format="content_and_artifact")
    def google_search(query: str, config: Annotated[RunnableConfig, InjectedToolArg]) -> Tuple[str, List[Dict]]:
        "Search Google for the given query."

        config = AgentConfig.from_runnable_config(config)
        results = google_search_api.results(
            query, num_results=config.google_search_num_results)

        return "\n".join([result["snippet"] for result in results]), results

    google_search.description = config.prompt.tool[google_search.name]

    return google_search
