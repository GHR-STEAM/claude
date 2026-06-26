"""
Backup and recovery endpoints for the High School Management System API.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, List

from ..backup import get_backup_manager

router = APIRouter(
    prefix="/backup",
    tags=["backup"]
)


@router.post("/create", response_model=Dict[str, str])
def create_backup(
    description: str = Body("", embed=True, description="Backup description")
) -> Dict[str, str]:
    """
    Create a new database backup.

    Body Parameters:
    - description: Optional description for the backup

    Returns:
        dict: Backup ID and confirmation
    """
    try:
        manager = get_backup_manager()
        backup_id = manager.create_backup(description=description)

        return {
            "message": "Backup created successfully",
            "backup_id": backup_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup creation failed: {str(e)}")


@router.get("/list", response_model=Dict[str, Any])
def list_backups(
    limit: int = Query(50, ge=1, le=100, description="Maximum backups to return")
) -> Dict[str, Any]:
    """
    List all available backups.

    Query Parameters:
    - limit: Maximum backups to return (1-100, default 50)

    Returns:
        dict: List of backups with metadata
    """
    try:
        manager = get_backup_manager()
        backups = manager.list_backups(limit=limit)

        return {
            "total": len(backups),
            "backups": backups,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")


@router.get("/{backup_id}", response_model=Dict[str, Any])
def get_backup_info(backup_id: str) -> Dict[str, Any]:
    """
    Get information about a specific backup.

    Path Parameters:
    - backup_id: ID of the backup

    Returns:
        dict: Backup details
    """
    try:
        manager = get_backup_manager()
        return manager.get_backup_info(backup_id)

    except ValueError as e:
        error_msg = str(e)
        if "Invalid backup ID format" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        else:
            raise HTTPException(status_code=404, detail=error_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backup info: {str(e)}")


@router.post("/{backup_id}/verify", response_model=Dict[str, Any])
def verify_backup(backup_id: str) -> Dict[str, Any]:
    """
    Verify the integrity of a backup.

    Path Parameters:
    - backup_id: ID of the backup to verify

    Returns:
        dict: Verification results
    """
    try:
        manager = get_backup_manager()
        return manager.verify_backup_integrity(backup_id)

    except ValueError as e:
        error_msg = str(e)
        if "Invalid backup ID format" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        else:
            raise HTTPException(status_code=404, detail=error_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.delete("/{backup_id}", response_model=Dict[str, str])
def delete_backup(backup_id: str) -> Dict[str, str]:
    """
    Delete a backup.

    Path Parameters:
    - backup_id: ID of the backup to delete

    Returns:
        dict: Status message
    """
    try:
        manager = get_backup_manager()
        success = manager.delete_backup(backup_id)

        if success:
            return {"message": "Backup deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Backup not found")

    except ValueError as e:
        error_msg = str(e)
        if "Invalid backup ID format" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        else:
            raise HTTPException(status_code=404, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.get("/stats/summary", response_model=Dict[str, Any])
def get_backup_statistics() -> Dict[str, Any]:
    """
    Get backup system statistics.

    Returns:
        dict: Statistics about backups
    """
    try:
        manager = get_backup_manager()
        return manager.get_backup_statistics()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.get("/logs/all", response_model=Dict[str, Any])
def get_backup_logs(
    backup_id: str = Query(None, description="Filter by backup ID"),
    limit: int = Query(100, ge=1, le=500, description="Maximum logs to return")
) -> Dict[str, Any]:
    """
    Get backup operation logs.

    Query Parameters:
    - backup_id: Optional filter by backup ID
    - limit: Maximum logs to return (1-500, default 100)

    Returns:
        dict: Log entries
    """
    try:
        manager = get_backup_manager()
        logs = manager.get_backup_logs(backup_id=backup_id, limit=limit)

        return {
            "total": len(logs),
            "logs": logs,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")
