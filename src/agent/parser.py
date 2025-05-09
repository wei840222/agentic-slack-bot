from typing import Dict, Any, Tuple, List, Optional
from collections import OrderedDict
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, ToolMessage

from config import AgentConfig


class ReferenceArtifact(BaseModel):
    title: str
    link: str
    content: Optional[str] = None


class Reference(BaseModel):
    title: str
    source: str
    icon_emoji: str
    artifacts: List[ReferenceArtifact] = []


def parse_agent_result(config: AgentConfig, result: Dict[str, Any]) -> Tuple[str, List[Reference]]:
    content: str | list[str | dict] = result["messages"][-1].content

    if isinstance(content, list):
        text_item = []
        for result_item in result:
            match result_item:
                case str():
                    if result_item.strip() == "":
                        continue
                    text_item.append(result_item)
                case _:
                    raise ValueError(
                        f"unknown result item type: {type(result_item)}")
        if len(text_item) <= 0:
            text_item.append("...")
        content = "\n".join(text_item)
    content = content.strip()

    references = OrderedDict()
    dedupe_artifact = set()
    for message in result["messages"][::-1]:
        if isinstance(message, HumanMessage):
            break
        if not isinstance(message, ToolMessage):
            continue
        if isinstance(message.artifact, list) and len(message.artifact) > 0:
            if message.name not in references:
                references[message.name] = []
            reference = Reference(title=config.get_message("tool_artifact_title"),
                                  source=message.name,
                                  icon_emoji=config.get_emoji(f"{message.name}_tool_artifact_icon"), artifacts=[])
            for artifact in message.artifact:
                if not isinstance(artifact["title"], str) or not isinstance(artifact["link"], str):
                    continue
                key = f"{message.name.strip()}: [{artifact['title'].strip()}]({artifact['link'].strip()})"
                if key in dedupe_artifact:
                    continue
                dedupe_artifact.add(key)
                reference.artifacts.append(ReferenceArtifact(
                    title=artifact["title"].strip(), link=artifact["link"].strip()))
            if len(reference.artifacts) > 0:
                references[message.name].append(reference)

    references = list(references.values())
    references_list = []
    for reference in references:
        references_list.extend(reference)
    references = references_list
    references.reverse()

    return content, references
