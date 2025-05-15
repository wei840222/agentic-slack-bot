from typing import Any, Dict, TypedDict, Optional


class Artifact(TypedDict):
    title: str
    link: str
    content: Optional[str]
    metadata: Optional[Dict[str, Any]]
