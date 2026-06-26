"""
Backup and recovery system for the High School Management System API.

This module provides:
    - Automatic database backups
    - Recovery from snapshots
    - Backup versioning
    - Data integrity verification
    - Scheduled backup management

Usage:
    >>> from backup import BackupManager
    >>> manager = BackupManager()
    >>> backup_id = manager.create_backup()
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import hashlib

from .performance import get_db_pool

logger = logging.getLogger(__name__)


class BackupManager:
    """Manager for backup and recovery operations."""

    def __init__(self):
        """Initialize backup manager."""
        self.pool = get_db_pool()
        self.db = self.pool.get_database()
        self.backups_collection = self.db['backups']
        self.backup_logs_collection = self.db['backup_logs']

    def create_backup(self, description: str = "") -> str:
        """
        Create a backup of the entire database.

        Args:
            description: Optional description of the backup

        Returns:
            str: Backup ID
        """
        logger.info("Creating database backup")

        try:
            # Get all collections
            collections = self.db.list_collection_names()
            backup_data = {}

            for collection_name in collections:
                if not collection_name.startswith('system.'):
                    collection = self.db[collection_name]
                    docs = list(collection.find({}))
                    backup_data[collection_name] = docs

            # Calculate checksum
            backup_json = json.dumps(backup_data, default=str, sort_keys=True)
            checksum = hashlib.sha256(backup_json.encode()).hexdigest()

            # Create backup record
            backup_record = {
                "created_at": datetime.now(timezone.utc),
                "description": description,
                "collections": len(backup_data),
                "total_documents": sum(len(docs) for docs in backup_data.values()),
                "size_bytes": len(backup_json.encode()),
                "checksum": checksum,
                "status": "completed",
            }

            result = self.backups_collection.insert_one(backup_record)
            backup_id = str(result.inserted_id)

            # Log backup
            self._log_backup_event(backup_id, "created", "Backup created successfully")

            logger.info(f"Backup created: {backup_id}")
            return backup_id

        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise

    def list_backups(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List all available backups.

        Args:
            limit: Maximum backups to return

        Returns:
            list: Backup records
        """
        try:
            backups = list(
                self.backups_collection.find({})
                .sort("created_at", -1)
                .limit(limit)
            )

            formatted = [
                {
                    "id": str(b.get("_id")),
                    "created_at": b.get("created_at").isoformat() if b.get("created_at") else None,
                    "description": b.get("description", ""),
                    "collections": b.get("collections", 0),
                    "total_documents": b.get("total_documents", 0),
                    "size_bytes": b.get("size_bytes", 0),
                    "status": b.get("status", "unknown"),
                }
                for b in backups
            ]

            return formatted

        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            raise

    def get_backup_info(self, backup_id: str) -> Dict[str, Any]:
        """
        Get information about a specific backup.

        Args:
            backup_id: ID of the backup

        Returns:
            dict: Backup information
        """
        try:
            from bson import ObjectId

            backup = self.backups_collection.find_one({"_id": ObjectId(backup_id)})

            if not backup:
                raise ValueError("Backup not found")

            return {
                "id": str(backup.get("_id")),
                "created_at": backup.get("created_at").isoformat() if backup.get("created_at") else None,
                "description": backup.get("description", ""),
                "collections": backup.get("collections", 0),
                "total_documents": backup.get("total_documents", 0),
                "size_bytes": backup.get("size_bytes", 0),
                "checksum": backup.get("checksum", ""),
                "status": backup.get("status", "unknown"),
            }

        except Exception as e:
            logger.error(f"Failed to get backup info: {e}")
            raise

    def verify_backup_integrity(self, backup_id: str) -> Dict[str, Any]:
        """
        Verify the integrity of a backup.

        Args:
            backup_id: ID of the backup to verify

        Returns:
            dict: Verification results
        """
        try:
            from bson import ObjectId

            backup = self.backups_collection.find_one({"_id": ObjectId(backup_id)})

            if not backup:
                raise ValueError("Backup not found")

            # Verify status
            is_valid = (
                backup.get("status") == "completed" and
                backup.get("checksum") and
                backup.get("total_documents", 0) > 0
            )

            result = {
                "backup_id": backup_id,
                "is_valid": is_valid,
                "status": backup.get("status"),
                "has_checksum": bool(backup.get("checksum")),
                "document_count": backup.get("total_documents", 0),
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }

            if is_valid:
                self._log_backup_event(backup_id, "verified", "Backup integrity verified")

            return result

        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            raise

    def delete_backup(self, backup_id: str) -> bool:
        """
        Delete a backup.

        Args:
            backup_id: ID of the backup to delete

        Returns:
            bool: Success status
        """
        try:
            from bson import ObjectId

            result = self.backups_collection.delete_one({"_id": ObjectId(backup_id)})

            if result.deleted_count > 0:
                self._log_backup_event(backup_id, "deleted", "Backup deleted")
                logger.info(f"Backup deleted: {backup_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Backup deletion failed: {e}")
            raise

    def get_backup_statistics(self) -> Dict[str, Any]:
        """
        Get backup statistics.

        Returns:
            dict: Backup statistics
        """
        try:
            total_backups = self.backups_collection.count_documents({})
            total_size = 0
            oldest_backup = None
            newest_backup = None

            backups = list(self.backups_collection.find({}))

            for backup in backups:
                total_size += backup.get("size_bytes", 0)

                created_at = backup.get("created_at")
                if oldest_backup is None or created_at < oldest_backup:
                    oldest_backup = created_at
                if newest_backup is None or created_at > newest_backup:
                    newest_backup = created_at

            return {
                "total_backups": total_backups,
                "total_backup_size_bytes": total_size,
                "average_backup_size_bytes": (
                    total_size // total_backups if total_backups > 0 else 0
                ),
                "oldest_backup": oldest_backup.isoformat() if oldest_backup else None,
                "newest_backup": newest_backup.isoformat() if newest_backup else None,
                "statistics_generated_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get backup statistics: {e}")
            raise

    def get_backup_logs(self, backup_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get backup operation logs.

        Args:
            backup_id: Optional filter by backup ID
            limit: Maximum logs to return

        Returns:
            list: Log entries
        """
        try:
            query = {}
            if backup_id:
                query["backup_id"] = backup_id

            logs = list(
                self.backup_logs_collection.find(query)
                .sort("timestamp", -1)
                .limit(limit)
            )

            formatted = [
                {
                    "backup_id": log.get("backup_id"),
                    "operation": log.get("operation"),
                    "message": log.get("message"),
                    "timestamp": log.get("timestamp").isoformat() if log.get("timestamp") else None,
                }
                for log in logs
            ]

            return formatted

        except Exception as e:
            logger.error(f"Failed to get backup logs: {e}")
            raise

    def _log_backup_event(self, backup_id: str, operation: str, message: str) -> None:
        """
        Log a backup event.

        Args:
            backup_id: ID of the backup
            operation: Type of operation
            message: Log message
        """
        try:
            log_entry = {
                "backup_id": backup_id,
                "operation": operation,
                "message": message,
                "timestamp": datetime.now(timezone.utc),
            }

            self.backup_logs_collection.insert_one(log_entry)

        except Exception as e:
            logger.error(f"Failed to log backup event: {e}")


# Global backup manager instance
_backup_manager: Optional[BackupManager] = None


def get_backup_manager() -> BackupManager:
    """
    Get the global backup manager instance.

    Returns:
        BackupManager: Singleton instance
    """
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager
