from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserProgress, UserActivity, UserAchievement, Achievement, ActivityType
from datetime import datetime, timedelta
from typing import Optional

router = APIRouter()

def get_or_create_progress(db: Session, user_id: int) -> UserProgress:
    """Get or create user progress record"""
    progress = db.query(UserProgress).filter(UserProgress.user_id == user_id).first()
    if not progress:
        progress = UserProgress(user_id=user_id)
        db.add(progress)
        db.commit()
        db.refresh(progress)
    return progress

@router.get("/my-progress")
def get_my_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's progress (for Progress screen)"""
    
    progress = get_or_create_progress(db, current_user.id)
    
    # Calculate total ayahs (6,236 in Quran)
    total_ayahs_in_quran = 6236
    
    # Get daily time spent for last 7 days
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    daily_time = db.query(
        func.date(UserActivity.date).label('day'),
        func.sum(UserActivity.duration_seconds).label('total_seconds')
    ).filter(
        UserActivity.user_progress_id == progress.id,
        UserActivity.date >= seven_days_ago
    ).group_by(func.date(UserActivity.date)).all()
    
    # Format weekly time data for chart (in minutes per day)
    weekly_data = {}
    day_labels = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
    
    for i in range(7):
        date = (datetime.utcnow() - timedelta(days=6-i)).date()
        day_letter = day_labels[i]
        weekly_data[day_letter] = 0
    
    for activity in daily_time:
        day_of_week = activity.day.weekday()  # 0=Monday, 6=Sunday
        day_letter = day_labels[day_of_week]
        minutes = int(activity.total_seconds / 60)
        weekly_data[day_letter] += minutes
    
    # Get recent achievements
    recent_achievements = db.query(UserAchievement, Achievement).join(
        Achievement
    ).filter(
        UserAchievement.user_progress_id == progress.id
    ).order_by(desc(UserAchievement.unlocked_at)).limit(5).all()
    
    achievements_list = []
    for user_ach, ach in recent_achievements:
        achievements_list.append({
            "id": ach.id,
            "name": ach.name,
            "description": ach.description,
            "icon": ach.icon,
            "is_new": user_ach.is_new,
            "unlocked_at": user_ach.unlocked_at
        })
    
    # Calculate total hours and minutes spent
    total_hours = int(progress.total_time_spent_seconds / 3600)
    total_minutes = int((progress.total_time_spent_seconds % 3600) / 60)
    
    # Calculate weekly time
    total_weekly_seconds = sum([v * 60 for v in weekly_data.values()])
    weekly_hours = int(total_weekly_seconds / 3600)
    weekly_minutes = int((total_weekly_seconds % 3600) / 60)
    
    return {
        "surahs_read": progress.total_surahs_read,
        "total_surahs": 114,
        "time_spent": {
            "hours": total_hours,
            "minutes": total_minutes,
            "total_display": f"{total_hours}h {total_minutes}m" if total_hours > 0 else f"{total_minutes}m"
        },
        "current_streak": progress.current_streak,
        "overall_progress": {
            "ayahs_recited": progress.total_ayahs_recited,
            "total_ayahs": total_ayahs_in_quran,
            "percentage": int((progress.total_ayahs_recited / total_ayahs_in_quran) * 100) if progress.total_ayahs_recited > 0 else 0
        },
        "accuracy": {
            "average": round(progress.average_accuracy, 1),
            "total_recitations": progress.total_recitation_attempts,
            "correct_recitations": progress.correct_recitations
        },
        "weekly_activity": {
            "data": weekly_data,
            "total_time": f"{weekly_hours}h {weekly_minutes}m" if weekly_hours > 0 else f"{weekly_minutes}m"
        },
        "recent_achievements": achievements_list
    }

@router.post("/log-activity")
def log_activity(
    activity_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Log user activity
    
    For recitation accuracy tracking:
    {
        "activity_type": "recitation",
        "surah_number": 1,
        "ayah_number": 1,
        "duration_seconds": 60,
        "accuracy_score": 95.5
    }
    
    For time tracking (listening/reading):
    {
        "activity_type": "listening",  # or "reading"
        "surah_number": 1,
        "duration_seconds": 300
    }
    """
    
    progress = get_or_create_progress(db, current_user.id)
    
    # Validate activity type
    activity_type = activity_data.get("activity_type")
    if activity_type not in ["listening", "recitation", "reading"]:
        raise HTTPException(status_code=400, detail="Invalid activity type")
    
    duration = activity_data.get("duration_seconds", 0)
    accuracy = activity_data.get("accuracy_score")
    
    # Calculate points (not primary, but for gamification)
    points = 0
    
    # Create activity record
    activity = UserActivity(
        user_progress_id=progress.id,
        activity_type=ActivityType(activity_type),
        surah_number=activity_data.get("surah_number"),
        ayah_number=activity_data.get("ayah_number"),
        duration_seconds=duration,
        accuracy_score=accuracy,
        points_earned=points
    )
    db.add(activity)
    
    # Update progress metrics
    # ✅ ALWAYS track time spent in app
    progress.total_time_spent_seconds += duration
    
    if activity_type == "recitation":
        # ✅ PRIMARY METRIC: Accuracy
        progress.total_recitation_attempts += 1
        
        if accuracy is not None:
            # Add to total accuracy points
            progress.total_accuracy_points += accuracy
            
            # Calculate new average accuracy
            progress.average_accuracy = progress.total_accuracy_points / progress.total_recitation_attempts
            
            # Count as correct if accuracy >= 80%
            if accuracy >= 80:
                progress.correct_recitations += 1
            
            # Track ayahs recited
            progress.total_ayahs_recited += 1
            
            # Points for gamification (optional)
            points = int(accuracy / 10)  # 95% = 9.5 points
    
    elif activity_type in ["listening", "reading"]:
        # Just track time, no accuracy needed
        points = int(duration / 60)  # 1 point per minute for engagement
    
    activity.points_earned = points
    
    # Update streak
    today = datetime.utcnow().date()
    if progress.last_activity_date:
        last_date = progress.last_activity_date.date()
        if last_date == today:
            pass  # Same day, no change
        elif last_date == today - timedelta(days=1):
            progress.current_streak += 1  # Continue streak
            if progress.current_streak > progress.longest_streak:
                progress.longest_streak = progress.current_streak
        else:
            progress.current_streak = 1  # Streak broken
    else:
        progress.current_streak = 1
    
    progress.last_activity_date = datetime.utcnow()
    
    db.commit()
    
    # Check for new achievements
    check_and_unlock_achievements(db, progress)
    
    return {
        "success": True,
        "points_earned": points,
        "current_streak": progress.current_streak,
        "average_accuracy": round(progress.average_accuracy, 1) if progress.average_accuracy else 0,
        "total_time_today": duration,
        "activity_logged": activity_type
    }

def check_and_unlock_achievements(db: Session, progress: UserProgress):
    """Check and unlock new achievements"""
    
    all_achievements = db.query(Achievement).all()
    user_achievements = db.query(UserAchievement).filter(
        UserAchievement.user_progress_id == progress.id
    ).all()
    
    unlocked_ids = [ua.achievement_id for ua in user_achievements]
    
    for achievement in all_achievements:
        if achievement.id in unlocked_ids:
            continue
        
        should_unlock = False
        
        if achievement.achievement_type == "streak":
            should_unlock = progress.current_streak >= achievement.threshold
        elif achievement.achievement_type == "surahs_completed":
            should_unlock = progress.total_surahs_read >= achievement.threshold
        elif achievement.achievement_type == "time_spent":
            hours_spent = progress.total_time_spent_seconds / 3600
            should_unlock = hours_spent >= achievement.threshold
        elif achievement.achievement_type == "accuracy":
            should_unlock = progress.average_accuracy >= achievement.threshold
        elif achievement.achievement_type == "recitations":
            should_unlock = progress.total_recitation_attempts >= achievement.threshold
        
        if should_unlock:
            user_achievement = UserAchievement(
                user_progress_id=progress.id,
                achievement_id=achievement.id,
                is_new=True
            )
            db.add(user_achievement)
    
    db.commit()

@router.post("/complete-surah/{surah_number}")
def mark_surah_complete(
    surah_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a surah as completed"""
    
    if surah_number < 1 or surah_number > 114:
        raise HTTPException(status_code=400, detail="Invalid surah number")
    
    progress = get_or_create_progress(db, current_user.id)
    progress.total_surahs_read += 1
    
    db.commit()
    
    return {
        "success": True,
        "total_surahs_read": progress.total_surahs_read
    }

@router.post("/start-session")
def start_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a new app session
    Frontend should call this when app opens
    """
    progress = get_or_create_progress(db, current_user.id)
    
    return {
        "session_started": True,
        "current_streak": progress.current_streak,
        "average_accuracy": round(progress.average_accuracy, 1)
    }

@router.post("/end-session")
def end_session(
    session_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    End app session and log total time
    
    Request:
    {
        "duration_seconds": 1800  # 30 minutes
    }
    """
    progress = get_or_create_progress(db, current_user.id)
    duration = session_data.get("duration_seconds", 0)
    
    # Log as general app usage
    activity = UserActivity(
        user_progress_id=progress.id,
        activity_type=ActivityType.READING,  # Generic activity type
        surah_number=0,  # No specific surah
        duration_seconds=duration,
        points_earned=0
    )
    db.add(activity)
    
    progress.total_time_spent_seconds += duration
    db.commit()
    
    return {
        "success": True,
        "total_time_spent": progress.total_time_spent_seconds
    }