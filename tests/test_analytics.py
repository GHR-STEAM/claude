"""
Comprehensive tests for analytics and reporting system.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from src.backend.analytics import AnalyticsEngine, ReportType


@pytest.fixture
def mock_db():
    """Mock MongoDB database."""
    db = MagicMock()
    db.__getitem__ = MagicMock()
    return db


@pytest.fixture
def analytics_engine(mock_db):
    """Create AnalyticsEngine with mocked database."""
    with patch('src.backend.analytics.get_db_pool') as mock_pool:
        mock_pool_instance = MagicMock()
        mock_pool_instance.get_database.return_value = mock_db
        mock_pool.return_value = mock_pool_instance

        engine = AnalyticsEngine()
        engine.db = mock_db
        return engine


class TestActivityReport:
    """Tests for activity report generation."""

    def test_generate_activity_report_basic(self, analytics_engine, mock_db):
        """Test basic activity report generation."""
        mock_activities = [
            {
                "_id": "activity1",
                "name": "Soccer",
                "category": "Sports",
                "participants": ["student1", "student2"],
            },
            {
                "_id": "activity2",
                "name": "Chess Club",
                "category": "Games",
                "participants": ["student3", "student4", "student5"],
            },
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.count_documents.return_value = 2
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_activity_report()

        assert report["report_type"] == ReportType.ACTIVITY_SUMMARY.value
        assert report["total_activities"] == 2
        assert report["total_participants"] == 5
        assert report["average_participants_per_activity"] == 2.5
        assert "generated_at" in report

    def test_generate_activity_report_categories(self, analytics_engine, mock_db):
        """Test category breakdown in activity report."""
        mock_activities = [
            {"_id": "a1", "category": "Sports", "participants": []},
            {"_id": "a2", "category": "Sports", "participants": []},
            {"_id": "a3", "category": "Arts", "participants": []},
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.count_documents.return_value = 3
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_activity_report()

        assert report["category_count"] == 2
        assert report["categories"]["Sports"] == 2
        assert report["categories"]["Arts"] == 1

    def test_generate_activity_report_empty(self, analytics_engine, mock_db):
        """Test activity report with no activities."""
        mock_activities_collection = MagicMock()
        mock_activities_collection.count_documents.return_value = 0
        mock_activities_collection.find.return_value = []
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_activity_report()

        assert report["total_activities"] == 0
        assert report["total_participants"] == 0
        assert report["average_participants_per_activity"] == 0

    def test_popular_activities(self, analytics_engine, mock_db):
        """Test identification of popular activities."""
        mock_activities = [
            {"_id": "popular", "participants": list(range(30))},
            {"_id": "moderate", "participants": list(range(10))},
            {"_id": "unpopular", "participants": []},
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.count_documents.return_value = 3
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_activity_report()

        assert report["most_popular_activities"][0]["name"] == "popular"
        assert report["most_popular_activities"][0]["participants"] == 30


class TestParticipationReport:
    """Tests for participation analytics."""

    def test_participation_rate_calculation(self, analytics_engine, mock_db):
        """Test participation rate calculation."""
        mock_activities = [
            {"_id": "a1", "participants": ["s1", "s2"]},
            {"_id": "a2", "participants": ["s3"]},
            {"_id": "a3", "participants": []},
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_participation_report()

        assert report["total_activities_analyzed"] == 3
        assert report["activities_with_participants"] == 2
        assert report["activities_without_participants"] == 1
        assert report["participation_rate"] == 66.67

    def test_participation_distribution(self, analytics_engine, mock_db):
        """Test participation distribution tracking."""
        mock_activities = [
            {"_id": "a1", "participants": ["s1", "s2", "s3"]},
            {"_id": "a2", "participants": []},
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_participation_report()

        assert len(report["participation_distribution"]) == 2
        assert report["participation_distribution"][0]["participants"] == 3
        assert report["participation_distribution"][1]["participants"] == 0

    def test_participation_empty(self, analytics_engine, mock_db):
        """Test participation report with no activities."""
        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = []
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_participation_report()

        assert report["participation_rate"] == 0
        assert report["total_activities_analyzed"] == 0


class TestTrendsReport:
    """Tests for trends analysis."""

    def test_trends_category_distribution(self, analytics_engine, mock_db):
        """Test category distribution in trends."""
        mock_activities = [
            {"_id": "a1", "category": "Sports", "participants": []},
            {"_id": "a2", "category": "Sports", "participants": []},
            {"_id": "a3", "category": "Arts", "participants": []},
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_trends_report(days=30)

        assert report["analysis_period_days"] == 30
        assert report["category_distribution"]["Sports"] == 2
        assert report["category_distribution"]["Arts"] == 1

    def test_participation_trends_levels(self, analytics_engine, mock_db):
        """Test participation trend level classification."""
        mock_activities = [
            {"_id": "a1", "participants": list(range(25))},  # high
            {"_id": "a2", "participants": list(range(10))},  # medium
            {"_id": "a3", "participants": list(range(3))),   # low
            {"_id": "a4", "participants": []},               # no participation
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_trends_report(days=30)

        assert report["participation_trends"]["high_participation"] == 1
        assert report["participation_trends"]["medium_participation"] == 1
        assert report["participation_trends"]["low_participation"] == 1
        assert report["participation_trends"]["no_participation"] == 1

    def test_growth_indicator(self, analytics_engine, mock_db):
        """Test growth indicator calculation."""
        mock_activities = [
            {"_id": f"a{i}", "participants": list(range(i % 10))}
            for i in range(10)
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_trends_report(days=30)

        assert "growth_indicator" in report
        assert "status" in report["growth_indicator"]
        assert "growth_rate" in report["growth_indicator"]


class TestTeacherPerformance:
    """Tests for teacher performance metrics."""

    def test_teacher_performance_report(self, analytics_engine, mock_db):
        """Test teacher performance calculation."""
        mock_teachers = [
            {"_id": "teacher1", "display_name": "Mr. Smith"},
            {"_id": "teacher2", "display_name": "Ms. Johnson"},
        ]

        mock_activities = [
            {"_id": "a1", "teacher": "teacher1", "participants": ["s1", "s2"]},
            {"_id": "a2", "teacher": "teacher1", "participants": ["s3"]},
            {"_id": "a3", "teacher": "teacher2", "participants": list(range(5))},
        ]

        mock_teachers_collection = MagicMock()
        mock_teachers_collection.find.return_value = mock_teachers
        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = mock_activities

        def getitem_side_effect(key):
            if key == "teachers":
                return mock_teachers_collection
            elif key == "activities":
                return mock_activities_collection

        mock_db.__getitem__.side_effect = getitem_side_effect

        report = analytics_engine.generate_teacher_performance_report()

        assert report["total_teachers"] == 2
        assert "teacher1" in report["teacher_statistics"]
        assert report["teacher_statistics"]["teacher1"]["activities_count"] == 2
        assert report["teacher_statistics"]["teacher1"]["total_participants"] == 3

    def test_teacher_no_activities(self, analytics_engine, mock_db):
        """Test teacher with no activities."""
        mock_teachers = [
            {"_id": "teacher1", "display_name": "Mr. Smith"},
        ]

        mock_activities = []

        mock_teachers_collection = MagicMock()
        mock_teachers_collection.find.return_value = mock_teachers
        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = mock_activities

        def getitem_side_effect(key):
            if key == "teachers":
                return mock_teachers_collection
            elif key == "activities":
                return mock_activities_collection

        mock_db.__getitem__.side_effect = getitem_side_effect

        report = analytics_engine.generate_teacher_performance_report()

        assert report["teacher_statistics"]["teacher1"]["activities_count"] == 0
        assert report["teacher_statistics"]["teacher1"]["average_participation"] == 0


class TestEnrollmentReport:
    """Tests for enrollment statistics."""

    def test_enrollment_totals(self, analytics_engine, mock_db):
        """Test enrollment total calculation."""
        mock_activities = [
            {"_id": "a1", "capacity": 30, "participants": list(range(25))},
            {"_id": "a2", "capacity": 20, "participants": list(range(15))},
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_enrollment_report()

        assert report["total_enrollments"] == 40
        assert report["average_activity_size"] == 20.0

    def test_capacity_analysis(self, analytics_engine, mock_db):
        """Test capacity analysis classification."""
        mock_activities = [
            {"_id": "a1", "capacity": 20, "participants": list(range(20))},  # at capacity
            {"_id": "a2", "capacity": 20, "participants": list(range(17))},  # near capacity
            {"_id": "a3", "capacity": 20, "participants": list(range(5))},   # has space
            {"_id": "a4", "capacity": 0, "participants": []},                # no limit
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_enrollment_report()

        assert report["capacity_analysis"]["at_capacity"] == 1
        assert report["capacity_analysis"]["near_capacity"] == 1
        assert report["capacity_analysis"]["has_space"] == 1
        assert report["capacity_analysis"]["no_limit"] == 1


class TestAnalyticsDashboard:
    """Tests for comprehensive analytics dashboard."""

    def test_dashboard_includes_all_reports(self, analytics_engine, mock_db):
        """Test that dashboard includes all report types."""
        mock_teachers_collection = MagicMock()
        mock_teachers_collection.find.return_value = []
        mock_activities_collection = MagicMock()
        mock_activities_collection.count_documents.return_value = 0
        mock_activities_collection.find.return_value = []

        def getitem_side_effect(key):
            if key == "teachers":
                return mock_teachers_collection
            elif key == "activities":
                return mock_activities_collection

        mock_db.__getitem__.side_effect = getitem_side_effect

        dashboard = analytics_engine.get_analytics_dashboard()

        assert "dashboard_generated_at" in dashboard
        assert "activity_summary" in dashboard
        assert "participation" in dashboard
        assert "trends" in dashboard
        assert "teacher_performance" in dashboard
        assert "enrollment" in dashboard

    def test_dashboard_timestamp(self, analytics_engine, mock_db):
        """Test dashboard timestamp is UTC."""
        mock_db.__getitem__.return_value = MagicMock(
            find=MagicMock(return_value=[]),
            count_documents=MagicMock(return_value=0)
        )

        dashboard = analytics_engine.get_analytics_dashboard()

        assert "dashboard_generated_at" in dashboard
        # Verify timestamp is ISO format
        parsed_time = datetime.fromisoformat(dashboard["dashboard_generated_at"].replace("Z", "+00:00"))
        assert parsed_time.tzinfo is not None


class TestReportExport:
    """Tests for report export functionality."""

    def test_export_activity_summary_csv(self, analytics_engine, mock_db):
        """Test CSV export of activity summary."""
        mock_activities = [
            {
                "_id": "activity1",
                "category": "Sports",
                "participants": ["s1", "s2"],
            },
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.count_documents.return_value = 1
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        csv_content = analytics_engine.export_report_csv(ReportType.ACTIVITY_SUMMARY)

        assert "Activity Summary Report" in csv_content
        assert "Total Activities" in csv_content
        assert "Total Participants" in csv_content
        assert isinstance(csv_content, str)

    def test_export_csv_contains_values(self, analytics_engine, mock_db):
        """Test CSV export contains actual values."""
        mock_activities = [
            {"_id": "a1", "category": "Sports", "participants": list(range(5))},
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.count_documents.return_value = 1
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        csv_content = analytics_engine.export_report_csv(ReportType.ACTIVITY_SUMMARY)

        assert "1" in csv_content  # total activities
        assert "5" in csv_content  # total participants


class TestReportTypes:
    """Tests for report type enumeration."""

    def test_report_type_values(self):
        """Test all report types are defined."""
        assert ReportType.ACTIVITY_SUMMARY.value == "activity_summary"
        assert ReportType.PARTICIPATION.value == "participation"
        assert ReportType.TRENDS.value == "trends"
        assert ReportType.TEACHER_PERFORMANCE.value == "teacher_performance"
        assert ReportType.ENROLLMENT.value == "enrollment"


class TestAnalyticsEdgeCases:
    """Tests for edge cases and error handling."""

    def test_division_by_zero_protection(self, analytics_engine, mock_db):
        """Test protection against division by zero."""
        mock_activities_collection = MagicMock()
        mock_activities_collection.count_documents.return_value = 0
        mock_activities_collection.find.return_value = []
        mock_db.__getitem__.return_value = mock_activities_collection

        # Should not raise ZeroDivisionError
        report = analytics_engine.generate_activity_report()
        assert report["average_participants_per_activity"] == 0

    def test_missing_optional_fields(self, analytics_engine, mock_db):
        """Test handling of missing optional fields."""
        mock_activities = [
            {"_id": "a1"},  # Missing category and participants
        ]

        mock_activities_collection = MagicMock()
        mock_activities_collection.count_documents.return_value = 1
        mock_activities_collection.find.return_value = mock_activities
        mock_db.__getitem__.return_value = mock_activities_collection

        report = analytics_engine.generate_activity_report()

        assert report["categories"]["Uncategorized"] == 1
        assert report["total_participants"] == 0

    def test_growth_indicator_insufficient_data(self, analytics_engine, mock_db):
        """Test growth indicator with insufficient data."""
        mock_activities = [{"_id": "a1", "participants": []}]

        indicator = analytics_engine._calculate_growth_indicator(mock_activities)

        assert indicator["status"] == "insufficient_data"
        assert indicator["growth_rate"] == 0

    def test_growth_indicator_no_data(self, analytics_engine, mock_db):
        """Test growth indicator with no data."""
        indicator = analytics_engine._calculate_growth_indicator([])

        assert indicator["status"] == "no_data"
        assert indicator["growth_rate"] == 0
