"""
Comprehensive tests for backup and recovery system.
"""

import pytest
import json
import hashlib
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from src.backend.backup import BackupManager


@pytest.fixture
def mock_db():
    """Mock MongoDB database."""
    db = MagicMock()
    db.__getitem__ = MagicMock()
    db.list_collection_names = MagicMock(return_value=["activities", "teachers", "students"])
    return db


@pytest.fixture
def backup_manager(mock_db):
    """Create BackupManager with mocked database."""
    with patch('src.backend.backup.get_db_pool') as mock_pool:
        mock_pool_instance = MagicMock()
        mock_pool_instance.get_database.return_value = mock_db
        mock_pool.return_value = mock_pool_instance

        manager = BackupManager()
        manager.db = mock_db
        return manager


class TestBackupCreation:
    """Tests for backup creation functionality."""

    def test_create_backup_success(self, backup_manager, mock_db):
        """Test successful backup creation."""
        mock_activities = [{"_id": "a1", "name": "Activity 1"}]
        mock_teachers = [{"_id": "t1", "name": "Teacher 1"}]
        mock_students = [{"_id": "s1", "name": "Student 1"}]

        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = mock_activities
        mock_teachers_collection = MagicMock()
        mock_teachers_collection.find.return_value = mock_teachers
        mock_students_collection = MagicMock()
        mock_students_collection.find.return_value = mock_students
        mock_backups_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.inserted_id = "backup_id_123"
        mock_backups_collection.insert_one.return_value = mock_result
        mock_backup_logs_collection = MagicMock()

        def getitem_side_effect(key):
            if key == "activities":
                return mock_activities_collection
            elif key == "teachers":
                return mock_teachers_collection
            elif key == "students":
                return mock_students_collection
            elif key == "backups":
                return mock_backups_collection
            elif key == "backup_logs":
                return mock_backup_logs_collection
            return MagicMock()

        mock_db.__getitem__.side_effect = getitem_side_effect
        mock_db.list_collection_names.return_value = ["activities", "teachers", "students"]
        backup_manager.backups_collection = mock_backups_collection
        backup_manager.backup_logs_collection = mock_backup_logs_collection

        backup_id = backup_manager.create_backup(description="Test backup")

        assert backup_id == "backup_id_123"
        assert mock_backups_collection.insert_one.called
        assert mock_backup_logs_collection.insert_one.called

    def test_create_backup_with_description(self, backup_manager, mock_db):
        """Test backup creation with description."""
        mock_db.__getitem__.return_value = MagicMock(find=MagicMock(return_value=[]))
        mock_backups_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.inserted_id = "backup_id"
        mock_backups_collection.insert_one.return_value = mock_result
        backup_manager.backups_collection = mock_backups_collection
        backup_manager.backup_logs_collection = MagicMock()

        backup_manager.create_backup(description="Custom description")

        # Verify the backup record includes the description
        call_args = mock_backups_collection.insert_one.call_args[0][0]
        assert call_args["description"] == "Custom description"

    def test_create_backup_calculates_checksum(self, backup_manager, mock_db):
        """Test that backup creation calculates checksum."""
        mock_db.__getitem__.return_value = MagicMock(find=MagicMock(return_value=[]))
        mock_backups_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.inserted_id = "backup_id"
        mock_backups_collection.insert_one.return_value = mock_result
        backup_manager.backups_collection = mock_backups_collection
        backup_manager.backup_logs_collection = MagicMock()

        backup_manager.create_backup()

        # Verify checksum is present
        call_args = mock_backups_collection.insert_one.call_args[0][0]
        assert "checksum" in call_args
        assert len(call_args["checksum"]) == 64  # SHA256 hex length

    def test_backup_includes_collections(self, backup_manager, mock_db):
        """Test that backup includes collection information."""
        mock_activities = [{"_id": "a1"}]
        mock_teachers = [{"_id": "t1"}]

        mock_db.list_collection_names.return_value = ["activities", "teachers"]
        mock_db.__getitem__.side_effect = lambda key: MagicMock(
            find=MagicMock(return_value=mock_activities if key == "activities" else mock_teachers)
        )

        mock_backups_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.inserted_id = "backup_id"
        mock_backups_collection.insert_one.return_value = mock_result
        backup_manager.backups_collection = mock_backups_collection
        backup_manager.backup_logs_collection = MagicMock()

        backup_manager.create_backup()

        call_args = mock_backups_collection.insert_one.call_args[0][0]
        assert call_args["collections"] == 2


class TestBackupListing:
    """Tests for backup listing functionality."""

    def test_list_backups_success(self, backup_manager, mock_db):
        """Test successful backup listing."""
        from bson import ObjectId

        backup_time = datetime.now(timezone.utc)
        mock_backups = [
            {
                "_id": ObjectId(),
                "created_at": backup_time,
                "description": "Backup 1",
                "collections": 3,
                "total_documents": 100,
                "size_bytes": 10000,
                "status": "completed",
            },
        ]

        mock_backups_collection = MagicMock()
        mock_backups_collection.find.return_value = MagicMock(
            sort=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=mock_backups)))
        )
        backup_manager.backups_collection = mock_backups_collection

        backups = backup_manager.list_backups(limit=50)

        assert len(backups) == 1
        assert backups[0]["description"] == "Backup 1"
        assert backups[0]["collections"] == 3

    def test_list_backups_sorted_by_date(self, backup_manager, mock_db):
        """Test backups are sorted by creation date."""
        mock_backups_collection = MagicMock()
        mock_find = MagicMock()
        mock_backups_collection.find.return_value = mock_find
        backup_manager.backups_collection = mock_backups_collection

        backup_manager.list_backups(limit=10)

        # Verify sort is called with created_at in descending order
        mock_find.sort.assert_called_once_with("created_at", -1)

    def test_list_backups_respects_limit(self, backup_manager, mock_db):
        """Test backup list respects limit parameter."""
        mock_backups_collection = MagicMock()
        mock_find = MagicMock()
        mock_sort = MagicMock()
        mock_backups_collection.find.return_value = mock_find
        mock_find.sort.return_value = mock_sort
        mock_sort.limit.return_value = []
        backup_manager.backups_collection = mock_backups_collection

        backup_manager.list_backups(limit=25)

        mock_sort.limit.assert_called_once_with(25)

    def test_list_backups_empty(self, backup_manager, mock_db):
        """Test listing with no backups."""
        mock_backups_collection = MagicMock()
        mock_backups_collection.find.return_value = MagicMock(
            sort=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=[])))
        )
        backup_manager.backups_collection = mock_backups_collection

        backups = backup_manager.list_backups()

        assert backups == []


class TestBackupInfo:
    """Tests for backup info retrieval."""

    def test_get_backup_info_success(self, backup_manager, mock_db):
        """Test successful backup info retrieval."""
        from bson import ObjectId

        backup_id = str(ObjectId())
        backup_time = datetime.now(timezone.utc)
        mock_backup = {
            "_id": ObjectId(backup_id),
            "created_at": backup_time,
            "description": "Test backup",
            "collections": 3,
            "total_documents": 150,
            "size_bytes": 15000,
            "checksum": "abc123" * 10 + "abcd",
            "status": "completed",
        }

        mock_backups_collection = MagicMock()
        mock_backups_collection.find_one.return_value = mock_backup
        backup_manager.backups_collection = mock_backups_collection

        info = backup_manager.get_backup_info(backup_id)

        assert info["id"] == backup_id
        assert info["description"] == "Test backup"
        assert info["checksum"] == "abc123" * 10 + "abcd"

    def test_get_backup_info_not_found(self, backup_manager, mock_db):
        """Test backup info retrieval for non-existent backup."""
        mock_backups_collection = MagicMock()
        mock_backups_collection.find_one.return_value = None
        backup_manager.backups_collection = mock_backups_collection

        with pytest.raises(ValueError, match="Backup not found"):
            backup_manager.get_backup_info("nonexistent_id")


class TestBackupVerification:
    """Tests for backup integrity verification."""

    def test_verify_backup_valid(self, backup_manager, mock_db):
        """Test verification of valid backup."""
        from bson import ObjectId

        backup_id = str(ObjectId())
        mock_backup = {
            "_id": ObjectId(backup_id),
            "status": "completed",
            "checksum": "abc123" * 10 + "abcd",
            "total_documents": 100,
        }

        mock_backups_collection = MagicMock()
        mock_backups_collection.find_one.return_value = mock_backup
        backup_manager.backups_collection = mock_backups_collection
        backup_manager.backup_logs_collection = MagicMock()

        result = backup_manager.verify_backup_integrity(backup_id)

        assert result["is_valid"] is True
        assert result["has_checksum"] is True
        assert result["document_count"] == 100

    def test_verify_backup_invalid_status(self, backup_manager, mock_db):
        """Test verification of backup with invalid status."""
        from bson import ObjectId

        backup_id = str(ObjectId())
        mock_backup = {
            "_id": ObjectId(backup_id),
            "status": "failed",
            "checksum": "abc123" * 10 + "abcd",
            "total_documents": 100,
        }

        mock_backups_collection = MagicMock()
        mock_backups_collection.find_one.return_value = mock_backup
        backup_manager.backups_collection = mock_backups_collection

        result = backup_manager.verify_backup_integrity(backup_id)

        assert result["is_valid"] is False

    def test_verify_backup_missing_checksum(self, backup_manager, mock_db):
        """Test verification of backup missing checksum."""
        from bson import ObjectId

        backup_id = str(ObjectId())
        mock_backup = {
            "_id": ObjectId(backup_id),
            "status": "completed",
            "checksum": None,
            "total_documents": 100,
        }

        mock_backups_collection = MagicMock()
        mock_backups_collection.find_one.return_value = mock_backup
        backup_manager.backups_collection = mock_backups_collection

        result = backup_manager.verify_backup_integrity(backup_id)

        assert result["is_valid"] is False
        assert result["has_checksum"] is False

    def test_verify_backup_logs_event(self, backup_manager, mock_db):
        """Test that verification logs the event."""
        from bson import ObjectId

        backup_id = str(ObjectId())
        mock_backup = {
            "_id": ObjectId(backup_id),
            "status": "completed",
            "checksum": "abc123" * 10 + "abcd",
            "total_documents": 100,
        }

        mock_backups_collection = MagicMock()
        mock_backups_collection.find_one.return_value = mock_backup
        mock_backup_logs_collection = MagicMock()
        backup_manager.backups_collection = mock_backups_collection
        backup_manager.backup_logs_collection = mock_backup_logs_collection

        backup_manager.verify_backup_integrity(backup_id)

        assert mock_backup_logs_collection.insert_one.called


class TestBackupDeletion:
    """Tests for backup deletion."""

    def test_delete_backup_success(self, backup_manager, mock_db):
        """Test successful backup deletion."""
        from bson import ObjectId

        backup_id = str(ObjectId())
        mock_backups_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_backups_collection.delete_one.return_value = mock_result
        backup_manager.backups_collection = mock_backups_collection
        backup_manager.backup_logs_collection = MagicMock()

        success = backup_manager.delete_backup(backup_id)

        assert success is True

    def test_delete_backup_not_found(self, backup_manager, mock_db):
        """Test deletion of non-existent backup."""
        from bson import ObjectId

        backup_id = str(ObjectId())
        mock_backups_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.deleted_count = 0
        mock_backups_collection.delete_one.return_value = mock_result
        backup_manager.backups_collection = mock_backups_collection

        success = backup_manager.delete_backup(backup_id)

        assert success is False

    def test_delete_backup_logs_event(self, backup_manager, mock_db):
        """Test that deletion logs the event."""
        from bson import ObjectId

        backup_id = str(ObjectId())
        mock_backups_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_backups_collection.delete_one.return_value = mock_result
        mock_backup_logs_collection = MagicMock()
        backup_manager.backups_collection = mock_backups_collection
        backup_manager.backup_logs_collection = mock_backup_logs_collection

        backup_manager.delete_backup(backup_id)

        assert mock_backup_logs_collection.insert_one.called


class TestBackupStatistics:
    """Tests for backup statistics."""

    def test_get_backup_statistics(self, backup_manager, mock_db):
        """Test backup statistics calculation."""
        backup_time = datetime.now(timezone.utc)
        mock_backups = [
            {
                "created_at": backup_time,
                "size_bytes": 10000,
            },
            {
                "created_at": backup_time,
                "size_bytes": 20000,
            },
        ]

        mock_backups_collection = MagicMock()
        mock_backups_collection.count_documents.return_value = 2
        mock_backups_collection.find.return_value = mock_backups
        backup_manager.backups_collection = mock_backups_collection

        stats = backup_manager.get_backup_statistics()

        assert stats["total_backups"] == 2
        assert stats["total_backup_size_bytes"] == 30000
        assert stats["average_backup_size_bytes"] == 15000

    def test_statistics_with_no_backups(self, backup_manager, mock_db):
        """Test statistics with no backups."""
        mock_backups_collection = MagicMock()
        mock_backups_collection.count_documents.return_value = 0
        mock_backups_collection.find.return_value = []
        backup_manager.backups_collection = mock_backups_collection

        stats = backup_manager.get_backup_statistics()

        assert stats["total_backups"] == 0
        assert stats["total_backup_size_bytes"] == 0
        assert stats["average_backup_size_bytes"] == 0


class TestBackupLogs:
    """Tests for backup operation logs."""

    def test_get_backup_logs_all(self, backup_manager, mock_db):
        """Test retrieving all backup logs."""
        log_time = datetime.now(timezone.utc)
        mock_logs = [
            {
                "backup_id": "backup1",
                "operation": "created",
                "message": "Backup created",
                "timestamp": log_time,
            },
        ]

        mock_backup_logs_collection = MagicMock()
        mock_backup_logs_collection.find.return_value = MagicMock(
            sort=MagicMock(return_value=MagicMock(limit=MagicMock(return_value=mock_logs)))
        )
        backup_manager.backup_logs_collection = mock_backup_logs_collection

        logs = backup_manager.get_backup_logs()

        assert len(logs) == 1
        assert logs[0]["operation"] == "created"

    def test_get_backup_logs_filtered(self, backup_manager, mock_db):
        """Test retrieving logs filtered by backup ID."""
        mock_backup_logs_collection = MagicMock()
        mock_find = MagicMock()
        mock_backup_logs_collection.find.return_value = mock_find
        backup_manager.backup_logs_collection = mock_backup_logs_collection

        backup_manager.get_backup_logs(backup_id="specific_backup")

        # Verify filter includes backup_id
        call_args = mock_backup_logs_collection.find.call_args[0][0]
        assert call_args["backup_id"] == "specific_backup"

    def test_get_backup_logs_respects_limit(self, backup_manager, mock_db):
        """Test log retrieval respects limit parameter."""
        mock_backup_logs_collection = MagicMock()
        mock_find = MagicMock()
        mock_sort = MagicMock()
        mock_backup_logs_collection.find.return_value = mock_find
        mock_find.sort.return_value = mock_sort
        mock_sort.limit.return_value = []
        backup_manager.backup_logs_collection = mock_backup_logs_collection

        backup_manager.get_backup_logs(limit=50)

        mock_sort.limit.assert_called_once_with(50)


class TestBackupEdgeCases:
    """Tests for edge cases and error handling."""

    def test_backup_with_empty_collections(self, backup_manager, mock_db):
        """Test backup with empty collections."""
        mock_db.list_collection_names.return_value = ["activities", "teachers"]
        mock_db.__getitem__.return_value = MagicMock(find=MagicMock(return_value=[]))

        mock_backups_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.inserted_id = "backup_id"
        mock_backups_collection.insert_one.return_value = mock_result
        backup_manager.backups_collection = mock_backups_collection
        backup_manager.backup_logs_collection = MagicMock()

        backup_id = backup_manager.create_backup()

        call_args = mock_backups_collection.insert_one.call_args[0][0]
        assert call_args["total_documents"] == 0

    def test_backup_checksum_deterministic(self, backup_manager, mock_db):
        """Test that identical backups have same checksum."""
        mock_db.__getitem__.return_value = MagicMock(find=MagicMock(return_value=[]))

        mock_backups_collection = MagicMock()
        mock_result = MagicMock()
        mock_result.inserted_id = "backup_id"
        mock_backups_collection.insert_one.return_value = mock_result
        backup_manager.backups_collection = mock_backups_collection
        backup_manager.backup_logs_collection = MagicMock()

        backup_manager.create_backup()
        first_checksum = mock_backups_collection.insert_one.call_args[0][0]["checksum"]

        mock_backups_collection.reset_mock()
        backup_manager.create_backup()
        second_checksum = mock_backups_collection.insert_one.call_args[0][0]["checksum"]

        assert first_checksum == second_checksum
