from datetime import datetime, timezone
from uuid import uuid4
from qdrant_client import models
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document

from config import SlackConfig, RagConfig
from agent.chain import create_make_title_chain
from agent.tool import clean_title
from slack_bot.client import SlackClient
from slack_bot.types import message_to_text


rag_config = RagConfig()
slack_config = SlackConfig()
logger = rag_config.get_logger()
logger.debug("config loaded", rag_config=rag_config, slack_config=slack_config)


if __name__ == "__main__":
    qdrant_client = rag_config.get_qdrant_config().get_qdrant_client()

    if not qdrant_client.collection_exists(rag_config.slack_search_collection_name):
        logger.info("Creating collection...")
        qdrant_client.create_collection(
            collection_name=rag_config.slack_search_collection_name,
            vectors_config=models.VectorParams(
                size=rag_config.vector_size, distance=models.Distance.COSINE),
        )
        qdrant_client.create_payload_index(
            collection_name=rag_config.slack_search_collection_name,
            field_name="metadata.source",
            field_schema="keyword"
        )
        qdrant_client.create_payload_index(
            collection_name=rag_config.slack_search_collection_name,
            field_name="metadata.channel_id",
            field_schema="keyword"
        )

    vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=rag_config.slack_search_collection_name,
        embedding=rag_config.load_embeddings_model(),
    )

    slack_client = SlackClient(slack_config, logger=logger)

    for channel in rag_config.slack_search_channels:
        history = slack_client.fetch_conversations_history(
            channel["id"], channel["retrieve_limit"], 100)

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
                        collection_name=rag_config.slack_search_collection_name,
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

                title = create_make_title_chain(rag_config).invoke(
                    input={"input": doc.page_content})
                doc.metadata["title"] = clean_title(title)

                logger.info("Splitting document", metadata=doc.metadata)

                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=rag_config.chunk_size,
                    chunk_overlap=rag_config.chunk_overlap,
                    length_function=len,
                    is_separator_regex=False,
                    separators=["---", "\n\n", "\n", " ", "", ".", ",",
                                ";""!", "?", "；", "，", "、", "。", "！""？"],
                )
                chunks = text_splitter.split_documents([doc])

                logger.info("Deleting old chunks", metadata=doc.metadata)
                qdrant_client.delete(
                    collection_name=rag_config.slack_search_collection_name,
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

                for i in range(0, len(chunks), rag_config.batch_size):
                    logger.info("Adding new chunks", metadata=doc.metadata, total=len(chunks),
                                current_start=i, current_end=i + rag_config.batch_size)
                    batch = chunks[i: i + rag_config.batch_size]
                    vector_store.add_documents(
                        documents=batch, ids=[str(uuid4()) for _ in batch])
