"""
Database query optimization utilities for the High School Management System API.

This module provides:
    - Automatic index creation on startup
    - Query EXPLAIN analysis utilities
    - Index status reporting
    - Slow query detection helpers

Usage:
    >>> from query_optimization import init_indexes, explain_query, get_index_status
    >>> init_indexes(db)
    >>> status = get_index_status(db)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


INDEX_DEFINITIONS = {
    "activities": [
        {"key": "_id", "unique": True},
        {"key": "schedule_details.days", "unique": False},
        {"key": "schedule_details.start_time", "unique": False},
        {"key": "schedule_details.end_time", "unique": False},
        {"key": "participants", "unique": False},
    ],
    "teachers": [
        {"key": "_id", "unique": True},
        {"key": "username", "unique": True},
    ],
}


def init_indexes(db) -> Dict[str, List[str]]:
    """Create all defined indexes on the database collections.

    Args:
        db: MongoDB database instance

    Returns:
        dict: Mapping of collection name to list of created index names
    """
    created = {}

    for collection_name, indexes in INDEX_DEFINITIONS.items():
        collection = db[collection_name]
        created_indexes = []

        for idx_def in indexes:
            try:
                name = collection.create_index(
                    idx_def["key"],
                    unique=idx_def.get("unique", False),
                    background=True,
                )
                created_indexes.append(name)
                logger.info(f"Index '{name}' ensured on '{collection_name}'")
            except Exception as e:
                logger.warning(
                    f"Index on '{collection_name}.{idx_def['key']}' failed: {e}"
                )

        created[collection_name] = created_indexes

    return created


def explain_query(collection, query: Dict[str, Any]) -> Dict[str, Any]:
    """Run EXPLAIN on a MongoDB query to analyze execution plan.

    Args:
        collection: MongoDB collection
        query: Query filter dict

    Returns:
        dict: Simplified explanation with key metrics
    """
    try:
        explanation = collection.find(query).explain()

        winning_plan = explanation.get("queryPlanner", {}).get("winningPlan", {})
        execution_stats = explanation.get("executionStats", {})

        return {
            "query": query,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "index_used": winning_plan.get("inputStage", {}).get("indexName", "COLLSCAN"),
            "total_docs_examined": execution_stats.get("totalDocsExamined", 0),
            "total_keys_examined": execution_stats.get("totalKeysExamined", 0),
            "execution_time_ms": execution_stats.get("executionTimeMillis", 0),
            "n_returned": execution_stats.get("nReturned", 0),
            "stage": winning_plan.get("stage", "UNKNOWN"),
            "is_indexed": "indexName" in str(winning_plan),
        }
    except Exception as e:
        logger.error(f"EXPLAIN failed: {e}")
        return {"error": str(e), "query": query}


def get_index_status(db) -> Dict[str, List[Dict[str, Any]]]:
    """Get index information for all collections.

    Args:
        db: MongoDB database instance

    Returns:
        dict: Mapping of collection name to list of index info
    """
    result = {}

    for collection_name in INDEX_DEFINITIONS.keys():
        collection = db[collection_name]
        try:
            indexes = list(collection.list_indexes())
            result[collection_name] = [
                {
                    "name": idx["name"],
                    "key": dict(idx["key"]),
                    "unique": idx.get("unique", False),
                    "size": idx.get("size", 0),
                }
                for idx in indexes
            ]
        except Exception as e:
            logger.error(f"Failed to list indexes for '{collection_name}': {e}")
            result[collection_name] = []

    return result


def analyze_slow_queries(
    collection, query: Dict[str, Any], threshold_ms: int = 100
) -> Optional[Dict[str, Any]]:
    """Analyze a query and return details if it's slower than threshold.

    Args:
        collection: MongoDB collection
        query: Query filter dict
        threshold_ms: Slow query threshold in milliseconds

    Returns:
        dict or None: Query analysis if slow, None otherwise
    """
    analysis = explain_query(collection, query)

    if "error" in analysis:
        return None

    exec_time = analysis.get("execution_time_ms", 0)
    if exec_time > threshold_ms:
        analysis["is_slow"] = True
        analysis["threshold_ms"] = threshold_ms
        logger.warning(
            f"Slow query detected: {exec_time}ms (threshold: {threshold_ms}ms) - "
            f"docs_examined={analysis.get('total_docs_examined', 0)}"
        )
        return analysis

    return None
