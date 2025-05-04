import random
from functools import cache
import requests
from markitdown import MarkItDown
from mcp.server.fastmcp import FastMCP


@cache
def _generate_user_agents(num_agents=100):
    """Generate a list of user agents."""
    generated_agents = []
    chrome_versions = list(range(100, 115))
    safari_versions = ["605.1.15"]
    os_versions_windows = ["10.0"]
    os_versions_mac = ["10_15_7", "11_0_1", "12_0_1", "13_0_1", "13_1"]
    os_versions_linux = ["x86_64"]
    firefox_versions = list(range(100, 115))

    for _ in range(num_agents):
        browser = random.choice(["Chrome", "Safari", "Firefox"])
        os_type = random.choice(["Windows", "Macintosh", "X11"])

        if browser == "Chrome":
            version = random.choice(chrome_versions)
            if os_type == "Windows":
                os_version = random.choice(os_versions_windows)
                agent = f"Mozilla/5.0 (Windows NT {os_version}; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36"
            elif os_type == "Macintosh":
                os_version = random.choice(os_versions_mac)
                agent = f"Mozilla/5.0 (Macintosh; Intel Mac OS X {os_version}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36"
            else:  # Linux
                os_version = random.choice(os_versions_linux)
                agent = f"Mozilla/5.0 (X11; Linux {os_version}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36"
        elif browser == "Safari":
            version = random.choice(safari_versions)
            os_version = random.choice(os_versions_mac)
            agent = f"Mozilla/5.0 (Macintosh; Intel Mac OS X {os_version}) AppleWebKit/{version} (KHTML, like Gecko) Version/16.1 Safari/{version}"
        else:  # Firefox
            version = random.choice(firefox_versions)
            if os_type == "Windows":
                os_version = random.choice(os_versions_windows)
                agent = f"Mozilla/5.0 (Windows NT {os_version}; Win64; x64; rv:{version}.0) Gecko/20100101 Firefox/{version}.0"
            elif os_type == "Macintosh":
                os_version = random.choice(os_versions_mac)
                agent = f"Mozilla/5.0 (Macintosh; Intel Mac OS X {os_version}; rv:{version}.0) Gecko/20100101 Firefox/{version}.0"
            else:  # Linux
                os_version = random.choice(os_versions_linux)
                agent = f"Mozilla/5.0 (X11; Linux {os_version}; rv:{version}.0) Gecko/20100101 Firefox/{version}.0"

        generated_agents.append(agent)

    return generated_agents


def generate_user_agent():
    """Generate a random user agent."""
    return random.choice(_generate_user_agents())


mcp = FastMCP("MarkItDown")


@mcp.tool()
def scrape_url(url: str) -> str:
    """Scrape a URL to Markdown format
    Args:
        url: The URL to scrape
    Returns:
        The Markdown formatted content of the URL
    """
    requests_session = requests.Session()
    md = MarkItDown(enable_plugins=False,
                    requests_session=requests_session)
    requests_session.headers["User-Agent"] = generate_user_agent()
    return md.convert_url(url).markdown.strip()


if __name__ == "__main__":
    mcp.run(transport="sse")
