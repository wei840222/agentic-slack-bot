from typing import List, Tuple

import urllib3
import requests
import ua_generator
from markitdown import MarkItDown
from langchain.tools import BaseTool, tool

from config import AgentConfig
from .types import Artifact

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def create_markitdown_crawler_tool(config: AgentConfig) -> BaseTool:
    @tool(response_format="content_and_artifact")
    def markitdown_crawler(url: str) -> Tuple[str, List[Artifact]]:
        "prompt_name: markitdown_crawler_tool"

        user_agent = ua_generator.generate(device="desktop", platform=(
            "windows", "macos"), browser=("chrome", "edge", "firefox", "safari"))
        requests_session = requests.Session()
        requests_session.headers.update(user_agent.headers.get())
        requests_session.verify = False
        markitdown = MarkItDown(enable_plugins=False,
                                requests_session=requests_session)
        result = markitdown.convert_url(url)

        return result.markdown.strip(), [Artifact(title=result.title, link=url)]

    markitdown_crawler.description = config.get_prompt(
        "markitdown_crawler_tool").text

    return markitdown_crawler
