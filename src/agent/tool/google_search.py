from typing import List, Tuple, Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg
from langchain.tools import BaseTool, tool
from langchain_google_community import GoogleSearchAPIWrapper

from config import AgentConfig
from .types import Artifact


def create_google_search_tool(config: AgentConfig) -> BaseTool:
    google_search_api = GoogleSearchAPIWrapper(
        google_api_key=config.google_api_key,
        google_cse_id=config.google_cse_id
    )

    @tool(response_format="content_and_artifact")
    def google_search(query: str, config: Annotated[RunnableConfig, InjectedToolArg]) -> Tuple[str, List[Artifact]]:
        "Search Google for the given query."

        config = AgentConfig.from_runnable_config(config)
        results = google_search_api.results(
            query, num_results=config.google_search_num_results)

        artifacts = [Artifact(title=result["title"], link=result["link"],
                              summary=result["snippet"]) for result in results]
        content = "\n\n".join(
            [f"title: {artifact['title']}\nlink: {artifact['link']}\nsummary: {artifact['summary']}" for artifact in artifacts])

        return content, artifacts

    google_search.description = config.get_prompt(
        "google_search_tool").text

    return google_search
