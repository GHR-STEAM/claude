"""
Analytics and reporting endpoints for the High School Management System API.
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

from ..analytics import get_analytics_engine, ReportType

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"]
)


@router.get("/activity-summary", response_model=Dict[str, Any])
def get_activity_summary() -> Dict[str, Any]:
    """
    Get activity summary report with statistics.

    Returns:
        dict: Activity statistics including totals and averages
    """
    try:
        engine = get_analytics_engine()
        return engine.generate_activity_report()
    except Exception:
        logger.exception("Activity summary report failed")
        raise HTTPException(status_code=500, detail="Report generation failed") from None


@router.get("/participation", response_model=Dict[str, Any])
def get_participation_report() -> Dict[str, Any]:
    """
    Get participation analytics report.

    Returns:
        dict: Participation statistics
    """
    try:
        engine = get_analytics_engine()
        return engine.generate_participation_report()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/trends", response_model=Dict[str, Any])
def get_trends_report(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
) -> Dict[str, Any]:
    """
    Get trends analysis report.

    Query Parameters:
    - days: Number of days to analyze (1-365, default 30)

    Returns:
        dict: Trends analysis
    """
    try:
        engine = get_analytics_engine()
        return engine.generate_trends_report(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/teacher-performance", response_model=Dict[str, Any])
def get_teacher_performance() -> Dict[str, Any]:
    """
    Get teacher performance report.

    Returns:
        dict: Teacher performance metrics
    """
    try:
        engine = get_analytics_engine()
        return engine.generate_teacher_performance_report()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/enrollment", response_model=Dict[str, Any])
def get_enrollment_report() -> Dict[str, Any]:
    """
    Get enrollment statistics report.

    Returns:
        dict: Enrollment metrics
    """
    try:
        engine = get_analytics_engine()
        return engine.generate_enrollment_report()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@router.get("/dashboard", response_model=Dict[str, Any])
def get_analytics_dashboard() -> Dict[str, Any]:
    """
    Get comprehensive analytics dashboard with all metrics.

    Returns:
        dict: Complete analytics dashboard
    """
    try:
        engine = get_analytics_engine()
        return engine.get_analytics_dashboard()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard generation failed: {str(e)}")


@router.get("/export/activity-summary", response_model=Dict[str, str])
def export_activity_summary_csv() -> Dict[str, str]:
    """
    Export activity summary as CSV.

    Returns:
        dict: CSV formatted report
    """
    try:
        engine = get_analytics_engine()
        csv_content = engine.export_report_csv(ReportType.ACTIVITY_SUMMARY)
        return {
            "format": "csv",
            "content": csv_content,
            "filename": "activity_summary.csv"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
