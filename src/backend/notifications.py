"""
Notification system for the High School Management System API.

This module provides:
    - Real-time notifications
    - Notification subscriptions
    - Email notifications
    - Notification preferences management
    - Notification history tracking

Usage:
    >>> from notifications import NotificationManager
    >>> manager = NotificationManager()
    >>> manager.send_notification(user_id, "Activity Updated", "Soccer activity updated")
"""

import logging
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timezone
import json

from .performance import get_db_pool, cache

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications."""
    ACTIVITY_CREATED = "activity_created"
    ACTIVITY_UPDATED = "activity_updated"
    ACTIVITY_CANCELLED = "activity_cancelled"
    SIGNUP_CONFIRMED = "signup_confirmed"
    SIGNUP_CANCELLED = "signup_cancelled"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    ENROLLMENT_REMINDER = "enrollment_reminder"
    DEADLINE_WARNING = "deadline_warning"
    SCHEDULE_CHANGED = "schedule_changed"
    ANNOUNCEMENT = "announcement"
    SYSTEM_ALERT = "system_alert"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationManager:
    """Manager for notification operations."""

    def __init__(self):
        """Initialize notification manager."""
        self.pool = get_db_pool()
        self.db = self.pool.get_database()
        self.notifications_collection = self.db['notifications']
        self.subscriptions_collection = self.db['subscriptions']
        self.preferences_collection = self.db['preferences']

    def send_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.ANNOUNCEMENT,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channels: Optional[List[NotificationChannel]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Send a notification to a user.

        Args:
            user_id: User to receive notification
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            priority: Priority level
            channels: Channels to send through
            data: Additional data to include

        Returns:
            str: Notification ID
        """
        channels = channels or [NotificationChannel.IN_APP]
        data = data or {}

        notification = {
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": notification_type.value,
            "priority": priority.value,
            "channels": [ch.value for ch in channels],
            "data": data,
            "created_at": datetime.now(timezone.utc),
            "read": False,
            "read_at": None,
        }

        result = self.notifications_collection.insert_one(notification)
        notification_id = str(result.inserted_id)

        logger.info(
            f"Notification sent to {user_id}: {title} "
            f"(ID: {notification_id}, Priority: {priority.value})"
        )

        # Send through configured channels
        self._send_through_channels(user_id, title, message, channels, data)

        return notification_id

    def send_bulk_notification(
        self,
        user_ids: List[str],
        title: str,
        message: str,
        notification_type: NotificationType = NotificationType.ANNOUNCEMENT,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channels: Optional[List[NotificationChannel]] = None,
    ) -> Dict[str, Any]:
        """
        Send notification to multiple users.

        Args:
            user_ids: List of users to notify
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            priority: Priority level
            channels: Channels to send through

        Returns:
            dict: Summary of sent notifications
        """
        channels = channels or [NotificationChannel.IN_APP]
        notifications = [
            {
                "user_id": user_id,
                "title": title,
                "message": message,
                "type": notification_type.value,
                "priority": priority.value,
                "channels": [ch.value for ch in channels],
                "created_at": datetime.now(timezone.utc),
                "read": False,
                "read_at": None,
            }
            for user_id in user_ids
        ]

        if notifications:
            result = self.notifications_collection.insert_many(notifications)
            logger.info(f"Bulk notification sent to {len(result.inserted_ids)} users: {title}")

            return {
                "total_users": len(user_ids),
                "sent": len(result.inserted_ids),
                "title": title,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return {
            "total_users": 0,
            "sent": 0,
            "title": title,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
        skip: int = 0,
    ) -> Dict[str, Any]:
        """
        Get notifications for a user.

        Args:
            user_id: User ID
            unread_only: Only return unread notifications
            limit: Maximum notifications to return
            skip: Number of notifications to skip

        Returns:
            dict: Notifications and metadata
        """
        query = {"user_id": user_id}

        if unread_only:
            query["read"] = False

        total_count = self.notifications_collection.count_documents(query)
        unread_count = self.notifications_collection.count_documents(
            {"user_id": user_id, "read": False}
        )

        notifications = list(
            self.notifications_collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        # Convert to serializable format
        formatted = [
            {
                "id": str(n.get("_id")),
                "title": n.get("title"),
                "message": n.get("message"),
                "type": n.get("type"),
                "priority": n.get("priority"),
                "read": n.get("read"),
                "created_at": n.get("created_at").isoformat() if n.get("created_at") else None,
                "read_at": n.get("read_at").isoformat() if n.get("read_at") else None,
                "data": n.get("data", {}),
            }
            for n in notifications
        ]

        return {
            "user_id": user_id,
            "total": total_count,
            "unread_count": unread_count,
            "returned": len(formatted),
            "skip": skip,
            "limit": limit,
            "notifications": formatted,
        }

    def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """
        Mark notification as read.

        Args:
            notification_id: Notification ID
            user_id: User ID (for validation)

        Returns:
            bool: Success status
        """
        from bson import ObjectId

        result = self.notifications_collection.update_one(
            {"_id": ObjectId(notification_id), "user_id": user_id},
            {
                "$set": {
                    "read": True,
                    "read_at": datetime.now(timezone.utc),
                }
            },
        )

        if result.modified_count > 0:
            logger.info(f"Notification {notification_id} marked as read")
            return True

        return False

    def mark_all_as_read(self, user_id: str) -> int:
        """
        Mark all notifications as read for a user.

        Args:
            user_id: User ID

        Returns:
            int: Number of notifications marked as read
        """
        result = self.notifications_collection.update_many(
            {"user_id": user_id, "read": False},
            {
                "$set": {
                    "read": True,
                    "read_at": datetime.now(timezone.utc),
                }
            },
        )

        count = result.modified_count
        logger.info(f"Marked {count} notifications as read for user {user_id}")

        return count

    def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """
        Delete a notification.

        Args:
            notification_id: Notification ID
            user_id: User ID (for validation)

        Returns:
            bool: Success status
        """
        from bson import ObjectId

        result = self.notifications_collection.delete_one(
            {"_id": ObjectId(notification_id), "user_id": user_id}
        )

        if result.deleted_count > 0:
            logger.info(f"Notification {notification_id} deleted")
            return True

        return False

    def subscribe_to_notification_type(
        self,
        user_id: str,
        notification_type: NotificationType,
        channels: List[NotificationChannel],
    ) -> bool:
        """
        Subscribe user to notification type.

        Args:
            user_id: User ID
            notification_type: Notification type
            channels: Channels to subscribe to

        Returns:
            bool: Success status
        """
        subscription = {
            "user_id": user_id,
            "notification_type": notification_type.value,
            "channels": [ch.value for ch in channels],
            "created_at": datetime.now(timezone.utc),
        }

        result = self.subscriptions_collection.update_one(
            {
                "user_id": user_id,
                "notification_type": notification_type.value,
            },
            {"$set": subscription},
            upsert=True,
        )

        logger.info(
            f"User {user_id} subscribed to {notification_type.value} "
            f"via {[ch.value for ch in channels]}"
        )

        return result.modified_count > 0 or result.upserted_id is not None

    def unsubscribe_from_notification_type(
        self,
        user_id: str,
        notification_type: NotificationType,
    ) -> bool:
        """
        Unsubscribe user from notification type.

        Args:
            user_id: User ID
            notification_type: Notification type

        Returns:
            bool: Success status
        """
        result = self.subscriptions_collection.delete_one(
            {
                "user_id": user_id,
                "notification_type": notification_type.value,
            }
        )

        if result.deleted_count > 0:
            logger.info(f"User {user_id} unsubscribed from {notification_type.value}")
            return True

        return False

    def get_user_subscriptions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get user's notification subscriptions.

        Args:
            user_id: User ID

        Returns:
            list: User subscriptions
        """
        subscriptions = list(
            self.subscriptions_collection.find({"user_id": user_id})
        )

        return [
            {
                "notification_type": s.get("notification_type"),
                "channels": s.get("channels", []),
                "subscribed_at": s.get("created_at").isoformat() if s.get("created_at") else None,
            }
            for s in subscriptions
        ]

    def set_notification_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any],
    ) -> bool:
        """
        Set user notification preferences.

        Args:
            user_id: User ID
            preferences: Preference settings

        Returns:
            bool: Success status
        """
        prefs = {
            "user_id": user_id,
            "email_enabled": preferences.get("email_enabled", True),
            "sms_enabled": preferences.get("sms_enabled", False),
            "push_enabled": preferences.get("push_enabled", True),
            "in_app_enabled": preferences.get("in_app_enabled", True),
            "quiet_hours": preferences.get("quiet_hours", {"enabled": False}),
            "digest_frequency": preferences.get("digest_frequency", "instant"),
            "updated_at": datetime.now(timezone.utc),
        }

        result = self.preferences_collection.update_one(
            {"user_id": user_id},
            {"$set": prefs},
            upsert=True,
        )

        logger.info(f"Preferences updated for user {user_id}")

        return result.modified_count > 0 or result.upserted_id is not None

    def get_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get user notification preferences.

        Args:
            user_id: User ID

        Returns:
            dict: User preferences
        """
        prefs = self.preferences_collection.find_one({"user_id": user_id})

        if not prefs:
            return {
                "email_enabled": True,
                "sms_enabled": False,
                "push_enabled": True,
                "in_app_enabled": True,
                "quiet_hours": {"enabled": False},
                "digest_frequency": "instant",
            }

        return {
            "email_enabled": prefs.get("email_enabled", True),
            "sms_enabled": prefs.get("sms_enabled", False),
            "push_enabled": prefs.get("push_enabled", True),
            "in_app_enabled": prefs.get("in_app_enabled", True),
            "quiet_hours": prefs.get("quiet_hours", {"enabled": False}),
            "digest_frequency": prefs.get("digest_frequency", "instant"),
        }

    def get_notification_statistics(self) -> Dict[str, Any]:
        """
        Get system-wide notification statistics.

        Returns:
            dict: Statistics
        """
        total_notifications = self.notifications_collection.count_documents({})
        unread_count = self.notifications_collection.count_documents({"read": False})

        # Count by type
        type_counts = list(
            self.notifications_collection.aggregate([
                {"$group": {"_id": "$type", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ])
        )

        # Count by priority
        priority_counts = list(
            self.notifications_collection.aggregate([
                {"$group": {"_id": "$priority", "count": {"$sum": 1}}},
            ])
        )

        return {
            "total_notifications": total_notifications,
            "unread_count": unread_count,
            "read_count": total_notifications - unread_count,
            "by_type": {t["_id"]: t["count"] for t in type_counts},
            "by_priority": {p["_id"]: p["count"] for p in priority_counts},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _send_through_channels(
        self,
        user_id: str,
        title: str,
        message: str,
        channels: List[NotificationChannel],
        data: Dict[str, Any],
    ) -> None:
        """
        Send notification through configured channels.

        Args:
            user_id: User ID
            title: Notification title
            message: Notification message
            channels: Channels to send through
            data: Additional data
        """
        prefs = self.get_notification_preferences(user_id)

        for channel in channels:
            if channel == NotificationChannel.EMAIL and prefs.get("email_enabled"):
                self._send_email(user_id, title, message)
            elif channel == NotificationChannel.SMS and prefs.get("sms_enabled"):
                self._send_sms(user_id, title, message)
            elif channel == NotificationChannel.PUSH and prefs.get("push_enabled"):
                self._send_push(user_id, title, message)

    def _send_email(self, user_id: str, title: str, message: str) -> None:
        """Send email notification."""
        logger.info(f"Sending email to {user_id}: {title}")
        # Email sending implementation would go here

    def _send_sms(self, user_id: str, title: str, message: str) -> None:
        """Send SMS notification."""
        logger.info(f"Sending SMS to {user_id}: {title}")
        # SMS sending implementation would go here

    def _send_push(self, user_id: str, title: str, message: str) -> None:
        """Send push notification."""
        logger.info(f"Sending push to {user_id}: {title}")
        # Push notification implementation would go here


# Global notification manager instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """
    Get the global notification manager instance.

    Returns:
        NotificationManager: Singleton instance
    """
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
