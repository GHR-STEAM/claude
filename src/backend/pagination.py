"""
Pagination utilities for the High School Management System API.

This module provides:
    - Paginated query results
    - Cursor-based pagination
    - Metadata about pagination

Usage:
    >>> from pagination import paginate_results
    >>> results = paginate_results(collection, skip=0, limit=10)
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class PaginationMetadata(BaseModel):
    """Metadata about paginated results."""

    current_page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there's a next page")
    has_previous: bool = Field(..., description="Whether there's a previous page")


class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    data: List[Dict[str, Any]] = Field(..., description="Page data")
    metadata: PaginationMetadata = Field(..., description="Pagination metadata")


class PaginationHelper:
    """Helper class for pagination operations."""

    # Default values
    DEFAULT_PAGE = 1
    DEFAULT_PAGE_SIZE = 10
    MAX_PAGE_SIZE = 100
    MIN_PAGE_SIZE = 1

    @staticmethod
    def validate_pagination_params(
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[int, int]:
        """
        Validate and normalize pagination parameters.

        Args:
            skip: Number of items to skip
            limit: Number of items to return

        Returns:
            Tuple of (skip, limit) with validated values

        Raises:
            ValueError: If parameters are invalid
        """
        if skip < 0:
            raise ValueError("skip must be non-negative")

        if limit < PaginationHelper.MIN_PAGE_SIZE:
            raise ValueError(
                f"limit must be at least {PaginationHelper.MIN_PAGE_SIZE}"
            )

        if limit > PaginationHelper.MAX_PAGE_SIZE:
            logger.warning(
                f"limit {limit} exceeds maximum {PaginationHelper.MAX_PAGE_SIZE}, "
                f"capping to maximum"
            )
            limit = PaginationHelper.MAX_PAGE_SIZE

        return skip, limit

    @staticmethod
    def calculate_pagination(
        total_items: int,
        skip: int = 0,
        limit: int = 10,
    ) -> PaginationMetadata:
        """
        Calculate pagination metadata.

        Args:
            total_items: Total number of items
            skip: Number of items skipped
            limit: Items per page

        Returns:
            PaginationMetadata object
        """
        skip, limit = PaginationHelper.validate_pagination_params(skip, limit)

        current_page = (skip // limit) + 1
        total_pages = (total_items + limit - 1) // limit
        has_next = (skip + limit) < total_items
        has_previous = skip > 0

        return PaginationMetadata(
            current_page=current_page,
            page_size=limit,
            total_items=total_items,
            total_pages=total_pages,
            has_next=has_next,
            has_previous=has_previous,
        )

    @staticmethod
    def paginate_list(
        items: List[Any],
        skip: int = 0,
        limit: int = 10,
    ) -> PaginatedResponse:
        """
        Paginate a list of items.

        Args:
            items: List of items to paginate
            skip: Number of items to skip
            limit: Items per page

        Returns:
            PaginatedResponse with paginated items and metadata
        """
        total_items = len(items)
        skip, limit = PaginationHelper.validate_pagination_params(skip, limit)

        # Get the page
        page_items = items[skip : skip + limit]

        # Convert to dicts if they're objects
        data = [
            item.dict() if hasattr(item, "dict") else item
            for item in page_items
        ]

        metadata = PaginationHelper.calculate_pagination(
            total_items, skip, limit
        )

        return PaginatedResponse(data=data, metadata=metadata)

    @staticmethod
    def paginate_query(
        collection,
        query: Dict[str, Any] = None,
        skip: int = 0,
        limit: int = 10,
        sort_field: str = "_id",
        sort_direction: int = 1,
    ) -> PaginatedResponse:
        """
        Paginate MongoDB query results.

        Args:
            collection: MongoDB collection
            query: Query filter (default: empty - all documents)
            skip: Number of items to skip
            limit: Items per page
            sort_field: Field to sort by
            sort_direction: Sort direction (1 for ascending, -1 for descending)

        Returns:
            PaginatedResponse with query results and metadata
        """
        if query is None:
            query = {}

        skip, limit = PaginationHelper.validate_pagination_params(skip, limit)

        # Count total items
        total_items = collection.count_documents(query)

        # Execute query with pagination
        cursor = (
            collection.find(query)
            .sort(sort_field, sort_direction)
            .skip(skip)
            .limit(limit)
        )

        # Convert results to list of dicts
        data = [
            {k: (str(v) if k == "_id" else v) for k, v in doc.items()}
            for doc in cursor
        ]

        metadata = PaginationHelper.calculate_pagination(
            total_items, skip, limit
        )

        return PaginatedResponse(data=data, metadata=metadata)

    @staticmethod
    def get_page_from_offset(skip: int, limit: int) -> int:
        """
        Calculate page number from skip and limit.

        Args:
            skip: Number of items skipped
            limit: Items per page

        Returns:
            Page number (1-indexed)
        """
        if limit <= 0:
            return 1
        return (skip // limit) + 1

    @staticmethod
    def get_offset_from_page(page: int, limit: int) -> int:
        """
        Calculate skip offset from page number.

        Args:
            page: Page number (1-indexed)
            limit: Items per page

        Returns:
            Skip offset
        """
        if page < 1:
            return 0
        return (page - 1) * limit


def paginate_results(
    collection,
    skip: int = 0,
    limit: int = 10,
    query: Optional[Dict[str, Any]] = None,
    sort_field: str = "_id",
) -> PaginatedResponse:
    """
    Convenience function for paginating MongoDB query results.

    Args:
        collection: MongoDB collection
        skip: Number of items to skip
        limit: Items per page
        query: Query filter (optional)
        sort_field: Field to sort by

    Returns:
        PaginatedResponse object

    Example:
        >>> response = paginate_results(activities_collection, skip=0, limit=10)
        >>> print(f"Page {response.metadata.current_page} of {response.metadata.total_pages}")
    """
    return PaginationHelper.paginate_query(
        collection=collection,
        query=query or {},
        skip=skip,
        limit=limit,
        sort_field=sort_field,
    )
