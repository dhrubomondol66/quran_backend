from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserProgress, UserSettings
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/leaderboard")
def get_leaderboard(
    period: str = Query("all_time", pattern="^(all_time|this_week|this_month)$"),  # ✅ Fixed deprecation
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get leaderboard rankings based on ACCURACY
    
    Ranking criteria (in order):
    1. Average accuracy (primary)
    2. Number of recitation attempts (tiebreaker)
    3. Total time spent (secondary tiebreaker)
    
    Only users with at least 5 recitations are ranked
    """
    
    # Get current user's progress
    current_user_progress = db.query(UserProgress).filter(
        UserProgress.user_id == current_user.id
    ).first()
    
    # Base query - only include users with sufficient recitations
    MIN_RECITATIONS = 5
    
    # ✅ FIX: Join UserProgress -> User -> UserSettings
    query = db.query(
        User.id,
        User.email,
        User.first_name,
        User.last_name,
        UserProgress.average_accuracy,
        UserProgress.total_recitation_attempts,
        UserProgress.total_time_spent_seconds,
        UserProgress.current_streak
    ).join(
        UserProgress, User.id == UserProgress.user_id  # Join User to UserProgress
    ).join(
        UserSettings, User.id == UserSettings.user_id  # Join User to UserSettings
    ).filter(
        and_(
            UserSettings.show_on_leaderboard == True,
            UserProgress.total_recitation_attempts >= MIN_RECITATIONS
        )
    )
    
    # Order by: accuracy DESC, then attempts DESC, then time DESC
    leaderboard_data = query.order_by(
        desc(UserProgress.average_accuracy),
        desc(UserProgress.total_recitation_attempts),
        desc(UserProgress.total_time_spent_seconds)
    ).limit(limit).all()
    
    # Format response
    rankings = []
    user_rank = None
    
    for idx, row in enumerate(leaderboard_data, start=1):
        user_data = {
            "rank": idx,
            "user_id": row.id,
            "name": f"{row.first_name or ''} {row.last_name or ''}".strip() or row.email.split('@')[0],
            "email": row.email,
            "accuracy": round(row.average_accuracy, 1),
            "total_recitations": row.total_recitation_attempts,
            "time_spent_hours": round(row.total_time_spent_seconds / 3600, 1),
            "streak": row.current_streak,
            "rank_change": 0
        }
        
        rankings.append(user_data)
        
        # Track current user's rank
        if row.id == current_user.id:
            user_rank = user_data
    
    # If current user not in top results, calculate their rank
    if not user_rank and current_user_progress:
        if current_user_progress.total_recitation_attempts >= MIN_RECITATIONS:
            # ✅ FIX: Same join structure for counting
            users_above = db.query(UserProgress).join(
                User, UserProgress.user_id == User.id
            ).join(
                UserSettings, User.id == UserSettings.user_id
            ).filter(
                and_(
                    UserSettings.show_on_leaderboard == True,
                    UserProgress.total_recitation_attempts >= MIN_RECITATIONS,
                    UserProgress.average_accuracy > current_user_progress.average_accuracy
                )
            ).count()
            
            user_rank = {
                "rank": users_above + 1,
                "user_id": current_user.id,
                "name": f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or "You",
                "email": current_user.email,
                "accuracy": round(current_user_progress.average_accuracy, 1),
                "total_recitations": current_user_progress.total_recitation_attempts,
                "time_spent_hours": round(current_user_progress.total_time_spent_seconds / 3600, 1),
                "streak": current_user_progress.current_streak,
                "rank_change": 0
            }
        else:
            # User doesn't have enough recitations yet
            user_rank = {
                "rank": None,
                "message": f"Complete {MIN_RECITATIONS - current_user_progress.total_recitation_attempts} more recitations to join the leaderboard",
                "accuracy": round(current_user_progress.average_accuracy, 1) if current_user_progress.average_accuracy else 0,
                "total_recitations": current_user_progress.total_recitation_attempts
            }
    elif not user_rank:
        # User has no progress at all
        user_rank = {
            "rank": None,
            "message": f"Complete {MIN_RECITATIONS} recitations to join the leaderboard",
            "accuracy": 0,
            "total_recitations": 0
        }
    
    # Get top 3 for podium display
    top_3 = rankings[:3] if len(rankings) >= 3 else rankings
    other_rankings = rankings[3:] if len(rankings) > 3 else []
    
    # ✅ FIX: Total participants count
    total_participants = db.query(UserProgress).join(
        User, UserProgress.user_id == User.id
    ).join(
        UserSettings, User.id == UserSettings.user_id
    ).filter(
        and_(
            UserSettings.show_on_leaderboard == True,
            UserProgress.total_recitation_attempts >= MIN_RECITATIONS
        )
    ).count()
    
    return {
        "period": period,
        "ranking_criteria": "Accuracy (minimum 5 recitations required)",
        "top_3": top_3,
        "other_rankings": other_rankings,
        "current_user": user_rank,
        "total_participants": total_participants
    }