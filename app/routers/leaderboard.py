from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserProgress, UserSettings
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/leaderboard")
def get_leaderboard(
    limit: int = Query(100, ge=1, le=100, description="Number of users to return (max 100)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get global leaderboard
    
    Returns:
    - top_3: Highlighted top 3 users
    - rankings: Full list (up to 100 users)
    - current_user: Current user's rank and stats
    - total_participants: Total users on leaderboard
    """
    
    MIN_RECITATIONS = 5
    
    # Query all eligible users
    rankings_query = db.query(
        User.id,
        User.email,
        User.first_name,
        User.last_name,
        UserProgress.average_accuracy,
        UserProgress.total_recitation_attempts,
        UserProgress.total_time_spent_seconds,
        UserProgress.current_streak
    ).join(
        UserProgress, User.id == UserProgress.user_id
    ).join(
        UserSettings, User.id == UserSettings.user_id
    ).filter(
        and_(
            UserProgress.total_recitation_attempts >= MIN_RECITATIONS,
            UserSettings.show_on_leaderboard == True
        )
    ).order_by(
        desc(UserProgress.average_accuracy),
        desc(UserProgress.total_recitation_attempts),
        desc(UserProgress.total_time_spent_seconds)
    ).limit(limit).all()
    
    # Format rankings
    rankings = []
    top_3 = []
    user_rank = None
    
    for idx, row in enumerate(rankings_query, start=1):
        user_data = {
            "rank": idx,
            "user_id": row.id,
            "name": f"{row.first_name or ''} {row.last_name or ''}".strip() or row.email.split('@')[0],
            "email": row.email,
            "accuracy": round(row.average_accuracy, 1),
            "total_recitations": row.total_recitation_attempts,
            "time_spent_hours": round(row.total_time_spent_seconds / 3600, 1),
            "streak": row.current_streak,
            "is_you": row.id == current_user.id
        }
        
        rankings.append(user_data)
        
        # Top 3
        if idx <= 3:
            top_3.append(user_data)
        
        # Current user
        if row.id == current_user.id:
            user_rank = user_data
    
    # If current user not in top 100, find their rank
    if not user_rank:
        current_progress = db.query(UserProgress).filter(
            UserProgress.user_id == current_user.id
        ).first()
        
        if current_progress and current_progress.total_recitation_attempts >= MIN_RECITATIONS:
            # Count users with better accuracy
            better_count = db.query(UserProgress).join(
                User, UserProgress.user_id == User.id
            ).join(
                UserSettings, User.id == UserSettings.user_id
            ).filter(
                and_(
                    UserProgress.total_recitation_attempts >= MIN_RECITATIONS,
                    UserSettings.show_on_leaderboard == True,
                    or_(
                        UserProgress.average_accuracy > current_progress.average_accuracy,
                        and_(
                            UserProgress.average_accuracy == current_progress.average_accuracy,
                            UserProgress.total_recitation_attempts > current_progress.total_recitation_attempts
                        )
                    )
                )
            ).count()
            
            user_rank = {
                "rank": better_count + 1,
                "user_id": current_user.id,
                "name": "You",
                "email": current_user.email,
                "accuracy": round(current_progress.average_accuracy, 1),
                "total_recitations": current_progress.total_recitation_attempts,
                "time_spent_hours": round(current_progress.total_time_spent_seconds / 3600, 1),
                "streak": current_progress.current_streak,
                "is_you": True
            }
        else:
            user_rank = {
                "rank": None,
                "message": f"Complete {MIN_RECITATIONS - (current_progress.total_recitation_attempts if current_progress else 0)} more recitations to join"
            }
    
    # Get total participant count
    total_participants = db.query(UserProgress).join(
        User, UserProgress.user_id == User.id
    ).join(
        UserSettings, User.id == UserSettings.user_id
    ).filter(
        and_(
            UserProgress.total_recitation_attempts >= MIN_RECITATIONS,
            UserSettings.show_on_leaderboard == True
        )
    ).count()
    
    return {
        "top_3": top_3,
        "rankings": rankings,
        "current_user": user_rank,
        "total_participants": total_participants,
        "min_recitations_required": MIN_RECITATIONS
    }