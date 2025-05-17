from datetime import datetime, timezone
from uuid import uuid4
from qdrant_client import models
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document

from config import SlackConfig, AgentConfig
from config.client import QdrantConfig
from agent.chain import create_make_title_chain
from agent.tool import clean_title
from slack_bot.client import SlackClient
from slack_bot.types import message_to_text

slack_config = SlackConfig()
agent_config = AgentConfig()
qdrant_config = QdrantConfig()
logger = slack_config.get_logger()
logger.debug("config loaded", slack_config=slack_config,
             agent_config=agent_config, qdrant_config=qdrant_config)

CHANNELS = [
    {"name": "test-ai-bot", "id": "C08HWC49T9A", "limit": 3},
    {"name": "rss-article", "id": "C03DQ95UCQ4", "limit": 3},
]

COLLECTION_NAME = "slack"

VECTOR_SIZE = 3072
CHUNK_SIZE = 4096
CHUNK_OVERLAP = 1024
BATCH_SIZE = 10

if __name__ == "__main__":
    qdrant_client = qdrant_config.get_qdrant_client()

    if not qdrant_client.collection_exists(COLLECTION_NAME):
        logger.info("Creating collection...")
        qdrant_client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE, distance=models.Distance.COSINE),
        )
        qdrant_client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="metadata.source",
            field_schema="keyword"
        )
        qdrant_client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="metadata.channel_id",
            field_schema="keyword"
        )

    vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=COLLECTION_NAME,
        embedding=agent_config.load_embeddings_model(),
    )

    slack_client = SlackClient(slack_config, logger=logger)

    for channel in CHANNELS:
        history = slack_client.fetch_conversations_history(
            channel["id"], channel["limit"], 100)

        for page in history["pages"]:
            for message in page["messages"]:
                try:
                    if message_to_text(message) is None:
                        continue

                    doc = Document(
                        page_content="",
                        metadata={
                            "type": "chunk",
                            "channel_id": channel["id"],
                            "source": slack_client.build_thread_url(channel["id"], message["ts"]),
                            "user": message["user"] if "user" in message else None,
                            "username": message["username"] if "username" in message else None,
                            "ts": datetime.fromtimestamp(float(message["ts"]), tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                            "latest_reply_ts": datetime.fromtimestamp(float(message["latest_reply"]), tz=timezone.utc).isoformat().replace("+00:00", "Z") if "latest_reply" in message else None,
                        })

                    results, _ = qdrant_client.scroll(
                        collection_name=COLLECTION_NAME,
                        scroll_filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="metadata.source",
                                    match=models.MatchValue(
                                        value=doc.metadata["source"]),
                                ),
                            ],
                        ),
                        limit=1,
                    )

                    if len(results) > 0:
                        existing_metadata = dict(
                            **results[0].payload["metadata"])
                        if "chunk_index" in existing_metadata:
                            del existing_metadata["chunk_index"]
                        if "title" in existing_metadata:
                            del existing_metadata["title"]
                        if existing_metadata == doc.metadata:
                            logger.info("Document not changed, skipping",
                                        metadata=results[0].payload["metadata"])
                            continue

                    logger.info("Loading documents...")
                except KeyError as e:
                    logger.exception("KeyError", error=e, message=message)
                    continue

                for message in slack_client.fetch_conversations_replies(channel["id"], message["ts"]):
                    if (text := message_to_text(message)) is None:
                        continue
                    doc.page_content += f"\n\n---\n\n{text}"
                doc.page_content = doc.page_content.strip().removeprefix("---\n\n")

                title = create_make_title_chain(agent_config).invoke(
                    input={"input": doc.page_content})
                doc.metadata["title"] = clean_title(title)

                logger.info("Splitting document", metadata=doc.metadata)

                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=CHUNK_SIZE,
                    chunk_overlap=CHUNK_OVERLAP,
                    length_function=len,
                    is_separator_regex=False,
                    separators=["---", "\n\n", "\n", " ", "", ".", ",",
                                ";""!", "?", "；", "，", "、", "。", "！""？"],
                )
                chunks = text_splitter.split_documents([doc])

                logger.info("Deleting old chunks", metadata=doc.metadata)
                qdrant_client.delete(
                    collection_name=COLLECTION_NAME,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="metadata.source",
                                    match=models.MatchValue(
                                        value=doc.metadata["source"]),
                                ),
                            ],
                        )
                    ),
                )

                for i in range(len(chunks)):
                    chunks[i].metadata["chunk_index"] = i

                for i in range(0, len(chunks), BATCH_SIZE):
                    logger.info("Adding new chunks", metadata=doc.metadata, total=len(chunks),
                                current_start=i, current_end=i + BATCH_SIZE)
                    batch = chunks[i: i + BATCH_SIZE]
                    vector_store.add_documents(
                        documents=batch, ids=[str(uuid4()) for _ in batch])
