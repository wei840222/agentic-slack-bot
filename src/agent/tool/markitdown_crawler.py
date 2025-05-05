from typing import List, Tuple, Dict

from langchain.tools import BaseTool, tool
import ua_generator
import requests
from markitdown import MarkItDown

from config import AgentConfig


def create_markitdown_crawler_tool(config: AgentConfig) -> BaseTool:
    @tool(response_format="content_and_artifact")
    def markitdown_crawler(url: str) -> Tuple[str, List[Dict]]:
        "Scrape a URL to Markdown format."

        user_agent = ua_generator.generate(device="desktop", platform=(
            "windows", "macos"), browser=("chrome", "edge", "firefox", "safari"))
        requests_session = requests.Session()
        requests_session.headers.update(user_agent.headers.get())
        markitdown = MarkItDown(enable_plugins=False,
                                requests_session=requests_session)
        result = markitdown.convert_url(url)

        return result.markdown.strip(), [{"title": result.title, "link": url}]

    markitdown_crawler.description = config.get_prompt(
        "markitdown_crawler_tool").text

    return markitdown_crawler
