from typing import TypedDict, Optional


class Artifact(TypedDict):
    title: str
    link: str
    summary: Optional[str]
