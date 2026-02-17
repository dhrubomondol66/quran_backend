from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func
from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserProgress, UserSettings

router = APIRouter()


def calculate_score(accuracy: float, total_recitations: int, max_recitations: int) -> float:
    """
    Leaderboard score formula:
    - 70% accuracy (0-100 scale)
    - 30% recitations (normalized against top user)
    
    Score range: 0 - 100
    """
    if max_recitations == 0:
        return round(accuracy * 0.7, 2)
    
    normalized_recitations = (total_recitations / max_recitations) * 100
    score = (accuracy * 0.7) + (normalized_recitations * 0.3)
    return round(score, 2)


@router.get("/leaderboard")
def get_leaderboard(
    limit: int = Query(100, ge=1, le=100, description="Number of users to return (max 100)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get global leaderboard
    
    Ranking formula: 70% accuracy + 30% recitations (normalized)
    Score range: 0 - 100

    Returns:
    - top_3: Highlighted top 3 users
    - rankings: Full list up to 100 users sorted by score
    - current_user: Current user's rank and stats
    - total_participants: Total users on leaderboard
    """

    MIN_RECITATIONS = 5

    # Get all eligible users
    eligible = db.query(
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
            UserProgress.average_accuracy > 0,
            UserSettings.show_on_leaderboard == True
        )
    ).all()

    if not eligible:
        return {
            "top_3": [],
            "rankings": [],
            "current_user": {"rank": None, "message": f"Complete {MIN_RECITATIONS} recitations to join"},
            "total_participants": 0,
            "min_recitations_required": MIN_RECITATIONS,
            "scoring": "70% accuracy + 30% recitations"
        }

    # Find max recitations for normalization
    max_recitations = max(row.total_recitation_attempts for row in eligible)

    # Calculate scores for all eligible users
    scored = []
    for row in eligible:
        score = calculate_score(row.average_accuracy, row.total_recitation_attempts, max_recitations)
        scored.append({
            "id": row.id,
            "email": row.email,
            "first_name": row.first_name,
            "last_name": row.last_name,
            "accuracy": row.average_accuracy,
            "total_recitations": row.total_recitation_attempts,
            "total_time_spent_seconds": row.total_time_spent_seconds,
            "current_streak": row.current_streak,
            "score": score
        })

    # Sort by score descending, accuracy and recitations as tiebreakers
    scored.sort(key=lambda x: (x["score"], x["accuracy"], x["total_recitations"]), reverse=True)

    # Build top 100 rankings
    rankings = []
    top_3 = []
    user_rank = None

    for idx, row in enumerate(scored[:limit], start=1):
        name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or row["email"].split("@")[0]

        user_data = {
            "rank": idx,
            "user_id": row["id"],
            "name": name,
            "accuracy": round(row["accuracy"], 1),
            "total_recitations": row["total_recitations"],
            "time_spent_hours": round(row["total_time_spent_seconds"] / 3600, 1),
            "streak": row["current_streak"],
            "score": row["score"],
            "is_you": row["id"] == current_user.id
        }

        rankings.append(user_data)

        if idx <= 3:
            top_3.append(user_data)

        if row["id"] == current_user.id:
            user_rank = user_data

    # If current user is outside top 100, find their actual rank
    if not user_rank:
        current_data = next((r for r in scored if r["id"] == current_user.id), None)

        if current_data:
            full_rank = next(
                (i + 1 for i, r in enumerate(scored) if r["id"] == current_user.id),
                None
            )
            name = f"{current_data['first_name'] or ''} {current_data['last_name'] or ''}".strip() or current_data["email"].split("@")[0]

            user_rank = {
                "rank": full_rank,
                "user_id": current_user.id,
                "name": name,
                "accuracy": round(current_data["accuracy"], 1),
                "total_recitations": current_data["total_recitations"],
                "time_spent_hours": round(current_data["total_time_spent_seconds"] / 3600, 1),
                "streak": current_data["current_streak"],
                "score": current_data["score"],
                "is_you": True
            }
        else:
            current_progress = db.query(UserProgress).filter(
                UserProgress.user_id == current_user.id
            ).first()

            remaining = MIN_RECITATIONS - (current_progress.total_recitation_attempts if current_progress else 0)
            user_rank = {
                "rank": None,
                "message": f"Complete {max(0, remaining)} more recitations to join the leaderboard"
            }

    return {
        "top_3": top_3,
        "rankings": rankings,
        "current_user": user_rank,
        "total_participants": len(scored),
        "min_recitations_required": MIN_RECITATIONS,
        "scoring": "70% accuracy + 30% recitations"
    }