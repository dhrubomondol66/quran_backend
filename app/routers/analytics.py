"""
Activity Analytics Endpoints
=============================
Add these to your progress router or create a new analytics router

Features:
- Daily activity (hourly breakdown)
- Weekly activity (day by day)
- Monthly activity (week by week)
- Activity streaks and summaries
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
from pydantic import BaseModel

from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserActivity, UserProgress


router = APIRouter()


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class TimeActivity(BaseModel):
    """Activity at a specific time"""
    time: str  # "6:00 AM", "5:03 PM", "11:30 AM", etc.
    time_24h: str  # "06:00", "17:03", "11:30" (for sorting)
    minutes: int
    recitations: int
    timestamp: datetime


class DailyActivityResponse(BaseModel):
    """Daily activity with actual activity times"""
    date: date
    total_minutes: int
    total_recitations: int
    activity_times: List[TimeActivity]  # Actual times user was active
    summary: str  # e.g., "You've read 45 minutes today"


class DayActivity(BaseModel):
    """Activity for a specific day"""
    day: str  # "M", "T", "W", "T", "F", "S", "S"
    date: date
    minutes: int
    recitations: int


class WeeklyActivityResponse(BaseModel):
    """Weekly activity breakdown"""
    week_start: date
    week_end: date
    total_minutes: int
    total_recitations: int
    daily_breakdown: List[DayActivity]
    summary: str  # e.g., "You've read 3 hours and 45 minutes this week"


class WeekSummary(BaseModel):
    """Summary for one week"""
    week_number: int  # 1-5
    week_label: str  # "Week 1", "Week 2", etc.
    week_start: date
    week_end: date
    minutes: int
    recitations: int


class MonthlyActivityResponse(BaseModel):
    """Monthly activity breakdown"""
    month: int  # 1-12
    year: int
    total_minutes: int
    total_recitations: int
    weekly_breakdown: List[WeekSummary]
    summary: str  # e.g., "You've read 18 hours this month"


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/activity/daily", response_model=DailyActivityResponse)
def get_daily_activity(
    target_date: Optional[date] = Query(None, description="Date to get activity for (default: today)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get activity for a specific day showing exact times user was active
    
    Shows actual activity times: "6:30 AM", "5:03 PM", "11:45 AM", etc.
    Groups activities within 15-minute windows for cleaner display
    """
    
    if not target_date:
        target_date = date.today()
    
    # Get user progress
    user_progress = db.query(UserProgress).filter(
        UserProgress.user_id == current_user.id
    ).first()
    
    if not user_progress:
        return DailyActivityResponse(
            date=target_date,
            total_minutes=0,
            total_recitations=0,
            activity_times=[],
            summary="No activity today yet"
        )
    
    # Query activities for the target date
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())
    
    activities = db.query(UserActivity).filter(
        UserActivity.user_progress_id == user_progress.id,
        UserActivity.created_at >= start_of_day,
        UserActivity.created_at <= end_of_day
    ).order_by(UserActivity.created_at).all()
    
    if not activities:
        return DailyActivityResponse(
            date=target_date,
            total_minutes=0,
            total_recitations=0,
            activity_times=[],
            summary="No activity today yet"
        )
    
    # Group activities by 15-minute time windows for cleaner display
    # This prevents showing "6:01 AM, 6:03 AM, 6:05 AM" separately
    time_windows = {}
    
    for activity in activities:
        # Round time to nearest 15 minutes
        activity_time = activity.created_at
        rounded_minute = (activity_time.minute // 15) * 15
        window_time = activity_time.replace(minute=rounded_minute, second=0, microsecond=0)
        
        # Create time key
        time_key = window_time.strftime("%H:%M")
        
        if time_key not in time_windows:
            time_windows[time_key] = {
                "timestamp": window_time,
                "minutes": 0,
                "recitations": 0
            }
        
        minutes = activity.duration_seconds // 60
        time_windows[time_key]["minutes"] += minutes
        time_windows[time_key]["recitations"] += 1
    
    # Calculate totals
    total_minutes = sum(w["minutes"] for w in time_windows.values())
    total_recitations = sum(w["recitations"] for w in time_windows.values())
    
    # Format activity times
    activity_times = []
    for time_key, data in sorted(time_windows.items()):
        timestamp = data["timestamp"]
        
        # Format time in 12-hour format with AM/PM
        time_12h = timestamp.strftime("%I:%M %p").lstrip("0")  # "6:30 AM" not "06:30 AM"
        time_24h = timestamp.strftime("%H:%M")  # For sorting
        
        activity_times.append(TimeActivity(
            time=time_12h,
            time_24h=time_24h,
            minutes=data["minutes"],
            recitations=data["recitations"],
            timestamp=timestamp
        ))
    
    # Generate summary
    if total_minutes == 0:
        summary = "No activity today yet"
    else:
        hours = total_minutes // 60
        mins = total_minutes % 60
        if hours > 0:
            summary = f"You've read {hours} hour{'s' if hours != 1 else ''} and {mins} minutes today"
        else:
            summary = f"You've read {mins} minutes today"
    
    return DailyActivityResponse(
        date=target_date,
        total_minutes=total_minutes,
        total_recitations=total_recitations,
        activity_times=activity_times,
        summary=summary
    )


@router.get("/activity/weekly", response_model=WeeklyActivityResponse)
def get_weekly_activity(
    week_start: Optional[date] = Query(None, description="Start of week (default: this week)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get activity for a week with daily breakdown
    
    Shows: M, T, W, T, F, S, S
    """
    
    # Calculate week start (Monday) if not provided
    if not week_start:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
    
    week_end = week_start + timedelta(days=6)
    
    # Get user progress
    user_progress = db.query(UserProgress).filter(
        UserProgress.user_id == current_user.id
    ).first()
    
    # Query activities for the week
    start_datetime = datetime.combine(week_start, datetime.min.time())
    end_datetime = datetime.combine(week_end, datetime.max.time())
    
    activities = db.query(UserActivity).filter(
        UserActivity.user_progress_id == user_progress.id if user_progress else False,
        UserActivity.created_at >= start_datetime,
        UserActivity.created_at <= end_datetime
    ).all()
    
    # Calculate daily breakdown
    daily_data = {}
    for day_offset in range(7):
        current_date = week_start + timedelta(days=day_offset)
        daily_data[current_date] = {"minutes": 0, "recitations": 0}
    
    total_minutes = 0
    total_recitations = 0
    
    for activity in activities:
        activity_date = activity.created_at.date()
        if activity_date in daily_data:
            minutes = activity.duration_seconds // 60
            daily_data[activity_date]["minutes"] += minutes
            daily_data[activity_date]["recitations"] += 1
            total_minutes += minutes
            total_recitations += 1
    
    # Format daily breakdown
    day_names = ["M", "T", "W", "T", "F", "S", "S"]
    daily_breakdown = []
    
    for day_offset in range(7):
        current_date = week_start + timedelta(days=day_offset)
        daily_breakdown.append(DayActivity(
            day=day_names[day_offset],
            date=current_date,
            minutes=daily_data[current_date]["minutes"],
            recitations=daily_data[current_date]["recitations"]
        ))
    
    # Generate summary
    hours = total_minutes // 60
    mins = total_minutes % 60
    if hours > 0:
        summary = f"You've read {hours} hour{'s' if hours != 1 else ''} and {mins} minutes this week"
    else:
        summary = f"You've read {mins} minutes this week"
    
    return WeeklyActivityResponse(
        week_start=week_start,
        week_end=week_end,
        total_minutes=total_minutes,
        total_recitations=total_recitations,
        daily_breakdown=daily_breakdown,
        summary=summary
    )


@router.get("/activity/monthly", response_model=MonthlyActivityResponse)
def get_monthly_activity(
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12, default: current)"),
    year: Optional[int] = Query(None, ge=2020, le=2100, description="Year (default: current)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get activity for a month with weekly breakdown
    
    Shows: Week 1, Week 2, Week 3, Week 4 (and Week 5 if applicable)
    """
    
    if not month:
        month = date.today().month
    if not year:
        year = date.today().year
    
    # Calculate month boundaries
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    
    # Get user progress
    user_progress = db.query(UserProgress).filter(
        UserProgress.user_id == current_user.id
    ).first()
    
    # Query activities for the month
    start_datetime = datetime.combine(first_day, datetime.min.time())
    end_datetime = datetime.combine(last_day, datetime.max.time())
    
    activities = db.query(UserActivity).filter(
        UserActivity.user_progress_id == user_progress.id if user_progress else False,
        UserActivity.created_at >= start_datetime,
        UserActivity.created_at <= end_datetime
    ).all()
    
    # Split month into weeks (starting from first day of month)
    weeks = []
    current_week_start = first_day
    week_number = 1
    
    while current_week_start <= last_day:
        current_week_end = min(current_week_start + timedelta(days=6), last_day)
        weeks.append({
            "week_number": week_number,
            "week_start": current_week_start,
            "week_end": current_week_end,
            "minutes": 0,
            "recitations": 0
        })
        current_week_start = current_week_end + timedelta(days=1)
        week_number += 1
    
    # Distribute activities into weeks
    total_minutes = 0
    total_recitations = 0
    
    for activity in activities:
        activity_date = activity.created_at.date()
        minutes = activity.duration_seconds // 60
        
        # Find which week this activity belongs to
        for week in weeks:
            if week["week_start"] <= activity_date <= week["week_end"]:
                week["minutes"] += minutes
                week["recitations"] += 1
                break
        
        total_minutes += minutes
        total_recitations += 1
    
    # Format weekly breakdown
    weekly_breakdown = [
        WeekSummary(
            week_number=week["week_number"],
            week_label=f"Week {week['week_number']}",
            week_start=week["week_start"],
            week_end=week["week_end"],
            minutes=week["minutes"],
            recitations=week["recitations"]
        )
        for week in weeks
    ]
    
    # Generate summary
    hours = total_minutes // 60
    summary = f"You've read {hours} hour{'s' if hours != 1 else ''} this month"
    
    return MonthlyActivityResponse(
        month=month,
        year=year,
        total_minutes=total_minutes,
        total_recitations=total_recitations,
        weekly_breakdown=weekly_breakdown,
        summary=summary
    )


@router.get("/activity/summary")
def get_activity_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get overall activity summary
    
    Returns quick stats for today, this week, and this month
    """
    
    user_progress = db.query(UserProgress).filter(
        UserProgress.user_id == current_user.id
    ).first()
    
    if not user_progress:
        return {
            "today_minutes": 0,
            "week_minutes": 0,
            "month_minutes": 0,
            "current_streak": 0,
            "total_recitations": 0
        }
    
    # Today
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_activities = db.query(func.sum(UserActivity.duration_seconds)).filter(
        UserActivity.user_progress_id == user_progress.id,
        UserActivity.created_at >= today_start
    ).scalar() or 0
    
    # This week
    week_start = date.today() - timedelta(days=date.today().weekday())
    week_start_datetime = datetime.combine(week_start, datetime.min.time())
    week_activities = db.query(func.sum(UserActivity.duration_seconds)).filter(
        UserActivity.user_progress_id == user_progress.id,
        UserActivity.created_at >= week_start_datetime
    ).scalar() or 0
    
    # This month
    month_start = date.today().replace(day=1)
    month_start_datetime = datetime.combine(month_start, datetime.min.time())
    month_activities = db.query(func.sum(UserActivity.duration_seconds)).filter(
        UserActivity.user_progress_id == user_progress.id,
        UserActivity.created_at >= month_start_datetime
    ).scalar() or 0
    
    return {
        "today_minutes": today_activities // 60,
        "week_minutes": week_activities // 60,
        "month_minutes": month_activities // 60,
        "current_streak": user_progress.current_streak,
        "total_recitations": user_progress.total_recitation_attempts
    }