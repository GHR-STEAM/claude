"""
Analytics and Reporting system for the High School Management System API.

This module provides:
    - Activity statistics and trends
    - Participation analytics
    - Performance metrics
    - Trend analysis and forecasting
    - Report generation

Usage:
    >>> from analytics import AnalyticsEngine
    >>> engine = AnalyticsEngine()
    >>> report = engine.generate_activity_report()
"""

import logging
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from .performance import get_db_pool, cache

logger = logging.getLogger(__name__)


class ReportType(str, Enum):
    """Types of reports."""
    ACTIVITY_SUMMARY = "activity_summary"
    PARTICIPATION = "participation"
    TRENDS = "trends"
    TEACHER_PERFORMANCE = "teacher_performance"
    ENROLLMENT = "enrollment"


class AnalyticsEngine:
    """Engine for generating analytics and reports."""

    def __init__(self):
        """Initialize analytics engine."""
        self.pool = get_db_pool()
        self.db = self.pool.get_database()
        self.activities_collection = self.db['activities']
        self.teachers_collection = self.db['teachers']

    @cache(ttl=3600)
    def generate_activity_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive activity statistics report.

        Returns:
            dict: Activity statistics
        """
        logger.info("Generating activity report")

        total_activities = self.activities_collection.count_documents({})
        activities = list(self.activities_collection.find({}))

        # Calculate statistics
        total_participants = sum(
            len(activity.get("participants") or []) for activity in activities
        )
        avg_participants = (
            total_participants / total_activities if total_activities > 0 else 0
        )

        # Category breakdown
        categories = defaultdict(int)
        for activity in activities:
            category = activity.get("category", "Uncategorized")
            categories[category] += 1

        # Most popular activities
        popular = sorted(
            activities,
            key=lambda a: len(a.get("participants", [])),
            reverse=True
        )[:10]

        return {
            "report_type": ReportType.ACTIVITY_SUMMARY.value,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_activities": total_activities,
            "total_participants": total_participants,
            "average_participants_per_activity": round(avg_participants, 2),
            "categories": dict(categories),
            "category_count": len(categories),
            "most_popular_activities": [
                {
                    "name": a.get("_id"),
                    "participants": len(a.get("participants", [])),
                    "category": a.get("category"),
                }
                for a in popular
            ],
        }

    @cache(ttl=3600)
    def generate_participation_report(self) -> Dict[str, Any]:
        """
        Generate participation analytics report.

        Returns:
            dict: Participation statistics
        """
        logger.info("Generating participation report")

        activities = list(self.activities_collection.find({}))

        participation_stats = {
            "activities_with_participants": 0,
            "activities_without_participants": 0,
            "participation_distribution": [],
            "participation_rate": 0.0,
        }

        for activity in activities:
            participant_count = len(activity.get("participants", []))

            if participant_count > 0:
                participation_stats["activities_with_participants"] += 1
            else:
                participation_stats["activities_without_participants"] += 1

            participation_stats["participation_distribution"].append({
                "activity": activity.get("_id"),
                "participants": participant_count,
            })

        # Calculate participation rate
        total = (
            participation_stats["activities_with_participants"] +
            participation_stats["activities_without_participants"]
        )
        if total > 0:
            participation_stats["participation_rate"] = round(
                (participation_stats["activities_with_participants"] / total) * 100, 2
            )

        return {
            "report_type": ReportType.PARTICIPATION.value,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_activities_analyzed": total,
            **participation_stats,
        }

    @cache(ttl=3600)
    def generate_trends_report(self, days: int = 30) -> Dict[str, Any]:
        """
        Generate trends analysis report.

        Args:
            days: Number of days to analyze

        Returns:
            dict: Trends analysis
        """
        logger.info(f"Generating trends report for last {days} days")

        activities = list(self.activities_collection.find({}))

        # Analyze activity categories
        category_trends = defaultdict(int)
        for activity in activities:
            category = activity.get("category", "Uncategorized")
            category_trends[category] += 1

        # Participation trends
        participation_trend = {
            "high_participation": len([
                a for a in activities
                if len(a.get("participants", [])) > 20
            ]),
            "medium_participation": len([
                a for a in activities
                if 5 < len(a.get("participants", [])) <= 20
            ]),
            "low_participation": len([
                a for a in activities
                if 0 < len(a.get("participants", [])) <= 5
            ]),
            "no_participation": len([
                a for a in activities
                if len(a.get("participants", [])) == 0
            ]),
        }

        return {
            "report_type": ReportType.TRENDS.value,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_period_days": days,
            "category_distribution": dict(category_trends),
            "participation_trends": participation_trend,
            "growth_indicator": self._calculate_growth_indicator(activities),
        }

    @cache(ttl=3600)
    def generate_teacher_performance_report(self) -> Dict[str, Any]:
        """
        Generate teacher performance report.

        Returns:
            dict: Teacher performance metrics
        """
        logger.info("Generating teacher performance report")

        teachers = list(self.teachers_collection.find({}))
        activities = list(self.activities_collection.find({}))

        teacher_stats = {}
        for teacher in teachers:
            teacher_id = teacher.get("_id")
            teacher_activities = [
                a for a in activities if a.get("teacher") == teacher_id
            ]

            total_participants = sum(
                len(a.get("participants", [])) for a in teacher_activities
            )

            teacher_stats[teacher_id] = {
                "activities_count": len(teacher_activities),
                "total_participants": total_participants,
                "average_participation": (
                    total_participants / len(teacher_activities)
                    if teacher_activities else 0
                ),
                "display_name": teacher.get("display_name", ""),
            }

        return {
            "report_type": ReportType.TEACHER_PERFORMANCE.value,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_teachers": len(teachers),
            "teacher_statistics": teacher_stats,
        }

    @cache(ttl=3600)
    def generate_enrollment_report(self) -> Dict[str, Any]:
        """
        Generate enrollment statistics report.

        Returns:
            dict: Enrollment metrics
        """
        logger.info("Generating enrollment report")

        activities = list(self.activities_collection.find({}))

        # Calculate enrollment metrics
        total_enrollments = sum(
            len(a.get("participants", [])) for a in activities
        )

        capacity_analysis = {
            "at_capacity": 0,
            "near_capacity": 0,
            "has_space": 0,
            "no_limit": 0,
        }

        for activity in activities:
            capacity = activity.get("capacity", 0)
            participants = len(activity.get("participants", []))

            if capacity == 0:
                capacity_analysis["no_limit"] += 1
            elif participants >= capacity:
                capacity_analysis["at_capacity"] += 1
            elif participants >= capacity * 0.8:
                capacity_analysis["near_capacity"] += 1
            else:
                capacity_analysis["has_space"] += 1

        return {
            "report_type": ReportType.ENROLLMENT.value,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_enrollments": total_enrollments,
            "average_activity_size": round(
                total_enrollments / len(activities) if activities else 0, 2
            ),
            "capacity_analysis": capacity_analysis,
        }

    @cache(ttl=1800)
    def get_analytics_dashboard(self) -> Dict[str, Any]:
        """
        Get comprehensive analytics dashboard data.

        Returns:
            dict: Dashboard metrics
        """
        logger.info("Generating analytics dashboard")

        activity_report = self.generate_activity_report()
        participation_report = self.generate_participation_report()
        trends_report = self.generate_trends_report()
        teacher_report = self.generate_teacher_performance_report()
        enrollment_report = self.generate_enrollment_report()

        return {
            "dashboard_generated_at": datetime.now(timezone.utc).isoformat(),
            "activity_summary": activity_report,
            "participation": participation_report,
            "trends": trends_report,
            "teacher_performance": teacher_report,
            "enrollment": enrollment_report,
        }

    def _calculate_growth_indicator(self, activities: List[Dict]) -> Dict[str, Any]:
        """
        Calculate growth indicator.

        Args:
            activities: List of activities

        Returns:
            dict: Growth metrics
        """
        if not activities:
            return {"status": "no_data", "growth_rate": 0}

        # Analyze participation growth
        participation_counts = [
            len(a.get("participants", [])) for a in activities
        ]

        if len(participation_counts) < 2:
            return {"status": "insufficient_data", "growth_rate": 0}

        avg_current = participation_counts[-5:] if len(participation_counts) >= 5 else participation_counts[-1:]
        avg_previous = participation_counts[:-5] if len(participation_counts) >= 5 else [0]

        current_avg = sum(avg_current) / len(avg_current) if avg_current else 0
        previous_avg = sum(avg_previous) / len(avg_previous) if avg_previous else 0

        growth_rate = 0
        if previous_avg > 0:
            growth_rate = ((current_avg - previous_avg) / previous_avg) * 100

        return {
            "status": "growing" if growth_rate > 0 else "stable" if growth_rate == 0 else "declining",
            "growth_rate": round(growth_rate, 2),
        }

    def export_report_csv(self, report_type: ReportType) -> str:
        """
        Export report as CSV format.

        Args:
            report_type: Type of report to export

        Returns:
            str: CSV formatted report
        """
        if report_type == ReportType.ACTIVITY_SUMMARY:
            report = self.generate_activity_report()
            csv = "Activity Summary Report\n"
            csv += f"Generated: {report['generated_at']}\n\n"
            csv += f"Total Activities,{report['total_activities']}\n"
            csv += f"Total Participants,{report['total_participants']}\n"
            csv += f"Avg Participants,{report['average_participants_per_activity']}\n"
            return csv

        return "Report generation not supported"


# Global analytics engine instance
_analytics_engine: Optional[AnalyticsEngine] = None


def get_analytics_engine() -> AnalyticsEngine:
    """
    Get the global analytics engine instance.

    Returns:
        AnalyticsEngine: Singleton instance
    """
    global _analytics_engine
    if _analytics_engine is None:
        _analytics_engine = AnalyticsEngine()
    return _analytics_engine
