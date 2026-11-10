"""LangGraph checkpointer: MongoDB in production (survives restarts / separate worker),
in-memory when running on mongomock (tests)."""
from __future__ import annotations

import logging
from functools import lru_cache

from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.db.mongo import get_db

log = logging.getLogger("agents.checkpoint")


@lru_cache
def get_checkpointer():
    db = get_db()
    if not db.is_mock:
        try:
            from langgraph.checkpoint.mongodb import MongoDBSaver

            saver = MongoDBSaver(db.client, db_name=settings.mongo_db, checkpoint_collection_name="langgraph_checkpoints", writes_collection_name="langgraph_writes")
            log.info("Using MongoDB checkpointer for LangGraph")
            return saver
        except Exception as exc:  # pragma: no cover
            log.warning("MongoDB checkpointer unavailable (%s); using MemorySaver", exc)
    return MemorySaver()
