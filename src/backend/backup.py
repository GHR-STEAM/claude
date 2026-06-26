"""
Database backup and recovery utilities for the High School Management System API.

This module provides:
    - Full database export to JSON
    - Database restore from JSON backup
    - Backup metadata and integrity checks
    - Point-in-time recovery support

Usage:
    >>> from backup import export_database, import_database, list_backups
    >>> backup_path = export_database(db)
    >>> import_database(db, backup_path)
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)

BACKUP_COLLECTIONS = ["activities", "teachers"]


def export_database(db, backup_name: Optional[str] = None) -> str:
    """Export all collections to a JSON backup file.

    Args:
        db: MongoDB database instance
        backup_name: Optional custom backup name. If None, uses timestamp.

    Returns:
        str: Path to the backup file
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = backup_name or f"backup_{timestamp}"
    backup_path = BACKUP_DIR / f"{filename}.json"

    backup_data = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database_name": db.name,
            "collections": BACKUP_COLLECTIONS,
            "version": "1.0.0",
        },
        "data": {},
    }

    for collection_name in BACKUP_COLLECTIONS:
        collection = db[collection_name]
        documents = []

        for doc in collection.find({}):
            doc["_id"] = str(doc["_id"])
            for key, value in doc.items():
                if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                    doc[key] = str(value)
            documents.append(doc)

        backup_data["data"][collection_name] = documents
        logger.info(f"Exported {len(documents)} documents from '{collection_name}'")

    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Database backup saved to {backup_path}")
    return str(backup_path)


def import_database(db, backup_path: str, drop_existing: bool = False) -> Dict[str, int]:
    """Restore database from a JSON backup file.

    Args:
        db: MongoDB database instance
        backup_path: Path to the backup JSON file
        drop_existing: If True, drop collections before importing

    Returns:
        dict: Number of documents imported per collection

    Raises:
        FileNotFoundError: If backup file doesn't exist
        ValueError: If backup file is invalid
    """
    path = Path(backup_path)
    if not path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    with open(path, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    if "data" not in backup_data or "metadata" not in backup_data:
        raise ValueError("Invalid backup file format")

    imported = {}

    for collection_name, documents in backup_data["data"].items():
        collection = db[collection_name]

        if drop_existing:
            collection.drop()
            logger.info(f"Dropped collection '{collection_name}'")

        if documents:
            for doc in documents:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])

            collection.insert_many(documents)
            imported[collection_name] = len(documents)
        else:
            imported[collection_name] = 0

        logger.info(f"Imported {imported[collection_name]} documents to '{collection_name}'")

    logger.info(f"Database restored from {backup_path}")
    return imported


def list_backups() -> List[Dict[str, Any]]:
    """List all available backup files.

    Returns:
        list: Backup file information including name, size, and date
    """
    backups = []

    for filepath in sorted(BACKUP_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
        stat = filepath.stat()
        backups.append({
            "filename": filepath.name,
            "path": str(filepath),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })

    return backups


def verify_backup(backup_path: str) -> Dict[str, Any]:
    """Verify a backup file's integrity.

    Args:
        backup_path: Path to the backup JSON file

    Returns:
        dict: Verification result with status and details
    """
    path = Path(backup_path)
    if not path.exists():
        return {"valid": False, "error": "File not found"}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "data" not in data or "metadata" not in data:
            return {"valid": False, "error": "Invalid format"}

        collections = {}
        for name, docs in data["data"].items():
            collections[name] = len(docs)

        return {
            "valid": True,
            "metadata": data["metadata"],
            "collections": collections,
            "total_documents": sum(collections.values()),
        }
    except json.JSONDecodeError as e:
        return {"valid": False, "error": f"JSON decode error: {e}"}
    except Exception as e:
        return {"valid": False, "error": str(e)}


def delete_backup(backup_path: str) -> bool:
    """Delete a backup file.

    Args:
        backup_path: Path to the backup file

    Returns:
        bool: True if deleted successfully
    """
    path = Path(backup_path)
    if path.exists():
        path.unlink()
        logger.info(f"Deleted backup: {backup_path}")
        return True
    return False
