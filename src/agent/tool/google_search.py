from typing import List, Tuple, Annotated, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import InjectedToolArg
from langchain.tools import BaseTool, tool
from langchain_google_community import GoogleSearchAPIWrapper

from config import AgentConfig
from .types import Artifact


def create_google_search_tool(config: AgentConfig) -> BaseTool:
    @tool(response_format="content_and_artifact")
    def google_search(query: str, num_results: Optional[int] = None, config: Annotated[RunnableConfig, InjectedToolArg] = None) -> Tuple[str, List[Artifact]]:
        "prompt_name: google_search_tool"

        config: AgentConfig = AgentConfig.from_runnable_config(config)
        top_n = num_results or config.google_search_default_top_n
        google_search_api = GoogleSearchAPIWrapper(
            google_api_key=config.google_api_key, google_cse_id=config.google_cse_id)
        results = google_search_api.results(query, num_results=top_n)

        artifacts = [Artifact(title=result["title"], link=result["link"],
                              content=result["snippet"]) for result in results]
        content = "\n\n".join(
            [f"title: {artifact['title']}\nlink: {artifact['link']}\ncontent: {artifact['content']}" for artifact in artifacts])

        return content, artifacts

    google_search.description = config.get_prompt(
        "google_search_tool").text

    return google_search
