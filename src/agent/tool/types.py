from typing import TypedDict, Optional


class Artifact(TypedDict):
    title: str
    link: str
    content: Optional[str]
