"""
Advanced search system for the High School Management System API.

This module provides:
    - Full-text search capabilities
    - Advanced filtering and sorting
    - Search result ranking
    - Search caching and optimization

Usage:
    >>> from search import SearchEngine
    >>> engine = SearchEngine()
    >>> results = engine.search_activities("soccer", filters={"day": "Monday"})
"""

import logging
from typing import List, Dict, Any, Optional
from enum import Enum
import re
from datetime import datetime, timezone

from .performance import get_db_pool, cache
from .pagination import PaginationHelper

logger = logging.getLogger(__name__)


class SearchCategory(str, Enum):
    """Search result categories."""
    ACTIVITY = "activity"
    TEACHER = "teacher"


class SortBy(str, Enum):
    """Sort options for search results."""
    RELEVANCE = "relevance"
    NAME = "name"
    DATE = "date"
    POPULARITY = "popularity"


class SearchEngine:
    """Advanced search engine with full-text and advanced filtering."""

    def __init__(self):
        """Initialize search engine with database connection."""
        self.pool = get_db_pool()
        self.db = self.pool.get_database()
        self.activities_collection = self.db['activities']
        self.teachers_collection = self.db['teachers']

    @cache(ttl=600)
    def search_activities(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: SortBy = SortBy.RELEVANCE,
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Search for activities using full-text and keyword matching.

        Args:
            query: Search query string
            filters: Optional filters (day, category, time range, etc.)
            sort_by: Sort criteria
            skip: Number of results to skip
            limit: Maximum results to return

        Returns:
            dict: Search results with metadata
        """
        filters = filters or {}
        logger.info(f"Searching activities: query='{query}', filters={filters}")

        # Build MongoDB query
        mongo_query = self._build_activity_query(query, filters)

        # Get total count
        total_count = self.activities_collection.count_documents(mongo_query)

        # Execute search with sorting
        sort_field = self._get_sort_field(sort_by)
        results = list(
            self.activities_collection.find(mongo_query)
            .sort(sort_field, -1 if sort_by == SortBy.POPULARITY else 1)
            .skip(skip)
            .limit(limit)
        )

        # Format results
        formatted_results = [
            {
                "id": str(result.get("_id", "")),
                "name": result.get("_id"),
                "description": result.get("description", ""),
                "category": result.get("category", ""),
                "participants_count": len(result.get("participants", [])),
                "schedule": result.get("schedule_details", {}),
                "teacher": result.get("teacher", ""),
                "location": result.get("location", ""),
            }
            for result in results
        ]

        return {
            "query": query,
            "total_results": total_count,
            "returned": len(formatted_results),
            "skip": skip,
            "limit": limit,
            "sort_by": sort_by.value,
            "results": formatted_results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @cache(ttl=600)
    def search_teachers(
        self,
        query: str,
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Search for teachers by name or details.

        Args:
            query: Search query
            skip: Number of results to skip
            limit: Maximum results to return

        Returns:
            dict: Search results
        """
        logger.info(f"Searching teachers: query='{query}'")

        # Build search regex
        search_regex = {"$regex": query, "$options": "i"}

        mongo_query = {
            "$or": [
                {"_id": search_regex},
                {"display_name": search_regex},
                {"email": search_regex},
            ]
        }

        total_count = self.teachers_collection.count_documents(mongo_query)

        results = list(
            self.teachers_collection.find(mongo_query)
            .skip(skip)
            .limit(limit)
        )

        formatted_results = [
            {
                "username": result.get("_id"),
                "display_name": result.get("display_name", ""),
                "email": result.get("email", ""),
                "activities_count": len(result.get("activities", [])),
            }
            for result in results
        ]

        return {
            "query": query,
            "total_results": total_count,
            "returned": len(formatted_results),
            "skip": skip,
            "limit": limit,
            "results": formatted_results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _build_activity_query(self, query: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build MongoDB query for activity search.

        Args:
            query: Search query
            filters: Filter criteria

        Returns:
            dict: MongoDB query
        """
        mongo_query = {}

        # Text search
        if query and query.strip():
            search_regex = {"$regex": query, "$options": "i"}
            mongo_query["$or"] = [
                {"_id": search_regex},
                {"description": search_regex},
                {"category": search_regex},
            ]

        # Apply filters
        if filters.get("day"):
            mongo_query["schedule_details.days"] = {"$in": [filters["day"]]}

        if filters.get("category"):
            mongo_query["category"] = filters["category"]

        if filters.get("teacher"):
            mongo_query["teacher"] = filters["teacher"]

        if filters.get("start_time"):
            mongo_query["schedule_details.start_time"] = {"$gte": filters["start_time"]}

        if filters.get("end_time"):
            mongo_query["schedule_details.end_time"] = {"$lte": filters["end_time"]}

        if filters.get("min_participants"):
            mongo_query[f"participants.{filters['min_participants'] - 1}"] = {"$exists": True}

        return mongo_query

    def _get_sort_field(self, sort_by: SortBy) -> str:
        """
        Get MongoDB sort field for given sort criteria.

        Args:
            sort_by: Sort criteria

        Returns:
            str: MongoDB field name
        """
        sort_fields = {
            SortBy.RELEVANCE: "_id",
            SortBy.NAME: "_id",
            SortBy.DATE: "created_at",
            SortBy.POPULARITY: "participants",
        }
        return sort_fields.get(sort_by, "_id")

    def get_search_suggestions(self, partial_query: str, limit: int = 5) -> Dict[str, List[str]]:
        """
        Get search suggestions based on partial query.

        Args:
            partial_query: Partial search string
            limit: Maximum suggestions

        Returns:
            dict: Suggestions grouped by category
        """
        if not partial_query or len(partial_query) < 2:
            return {"activities": [], "teachers": []}

        search_regex = {"$regex": f"^{re.escape(partial_query)}", "$options": "i"}

        activity_suggestions = list(
            self.activities_collection.find(
                {"_id": search_regex},
                {"_id": 1}
            )
            .limit(limit)
        )

        teacher_suggestions = list(
            self.teachers_collection.find(
                {"_id": search_regex},
                {"_id": 1}
            )
            .limit(limit)
        )

        return {
            "activities": [a["_id"] for a in activity_suggestions],
            "teachers": [t["_id"] for t in teacher_suggestions],
        }

    def get_trending_activities(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get trending activities based on participation.

        Args:
            limit: Maximum results

        Returns:
            list: Trending activities
        """
        pipeline = [
            {
                "$addFields": {
                    "participant_count": {"$size": {"$ifNull": ["$participants", []]}}
                }
            },
            {"$sort": {"participant_count": -1}},
            {"$limit": limit},
            {
                "$project": {
                    "name": "$_id",
                    "participants": "$participant_count",
                    "category": 1,
                    "teacher": 1,
                }
            }
        ]

        results = list(self.activities_collection.aggregate(pipeline))
        logger.info(f"Retrieved {len(results)} trending activities")

        return results

    def search_by_category(
        self,
        category: str,
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Search activities by category.

        Args:
            category: Activity category
            skip: Number of results to skip
            limit: Maximum results to return

        Returns:
            dict: Search results
        """
        query = {"category": category}
        total_count = self.activities_collection.count_documents(query)

        results = list(
            self.activities_collection.find(query)
            .skip(skip)
            .limit(limit)
        )

        return {
            "category": category,
            "total_results": total_count,
            "returned": len(results),
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
