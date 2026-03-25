from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from typing import List, Optional
from datetime import datetime
from app.services.notification_service import NotificationService
from app.routers.admin_router import ADMIN_EMAILS

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    NotificationType, User, Community, CommunityMember, CommunityInvitation,
    InvitationStatus, CommunityRole, UserProgress, UserSettings
)
from pydantic import BaseModel


router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CommunityCreate(BaseModel):
    """Create a new community"""
    name: str
    description: Optional[str] = None
    is_private: bool = True
    max_members: int = 100


class CommunityUpdate(BaseModel):
    """Update community details"""
    name: Optional[str] = None
    description: Optional[str] = None
    max_members: Optional[int] = None


class InviteMemberRequest(BaseModel):
    """Invite user to community by name"""
    first_name: str
    last_name: str


class CommunityResponse(BaseModel):
    """Community info"""
    id: int
    name: str
    description: Optional[str]
    created_by: int
    creator_name: str
    member_count: int
    max_members: int
    is_private: bool
    created_at: datetime
    user_role: Optional[str] = None  # User's role in this community
    community_image_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class MemberResponse(BaseModel):
    """Community member info"""
    user_id: int
    name: str
    email: str
    role: str
    joined_at: datetime
    accuracy: float
    total_recitations: int
    current_streak: int
    
    class Config:
        from_attributes = True


class InvitationResponse(BaseModel):
    """Invitation info"""
    id: int
    community_id: int
    community_name: str
    invited_by_id: int
    invited_by_name: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class JoinRequestResponse(BaseModel):
    """Join request info"""
    id: int
    community_id: int
    community_name: str
    requester_id: int
    requester_name: str
    requester_email: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============================================================================
# COMMUNITY CRUD
# ============================================================================

@router.post("/communities", response_model=CommunityResponse)
def create_community(
    community: CommunityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.email in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin accounts cannot create communities")
    
    """
    Create a new community
    
    Example: "Sunnah Community", "Beginners Circle"
    """
    
    # Create community
    new_community = Community(
        name=community.name,
        description=community.description,
        created_by=current_user.id,
        is_private=community.is_private,
        max_members=community.max_members
    )
    db.add(new_community)
    db.flush()
    
    # Auto-add creator as member with CREATOR role
    creator_membership = CommunityMember(
        community_id=new_community.id,
        user_id=current_user.id,
        role=CommunityRole.CREATOR
    )
    db.add(creator_membership)
    db.commit()
    db.refresh(new_community)
    
    # ✅ NOTIFY ALL USERS ABOUT NEW COMMUNITY
    NotificationService.notify_community_created(
        db=db,
        community_id=new_community.id,
        creator_id=current_user.id
    )
    
    return _format_community_response(new_community, current_user.id, db)


@router.get("/communities", response_model=List[CommunityResponse])
def get_my_communities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all communities current user is a member of
    """
    
    memberships = db.query(CommunityMember).filter(
        CommunityMember.user_id == current_user.id
    ).all()
    
    communities = []
    for membership in memberships:
        community = membership.community
        communities.append(_format_community_response(community, current_user.id, db))
    
    return communities

@router.get("/communities/browse", response_model=List[CommunityResponse])
def browse_communities(
    search: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Browse available communities
    
    Shows:
    - Public communities (is_private = false)
    - Communities user is already a member of
    
    Optionally filter by name search
    """
    
    user_community_ids = [
        m.community_id for m in 
        db.query(CommunityMember).filter(
            CommunityMember.user_id == current_user.id
        ).all()
    ]
    
    query = db.query(Community).filter(
        or_(
            Community.is_private == False,  # Public communities
            Community.id.in_(user_community_ids)  # User's communities
        )
    )
    
    # Add search filter if provided
    if search:
        query = query.filter(
            or_(
                Community.name.ilike(f"%{search}%"),
                Community.description.ilike(f"%{search}%")
            )
        )
    
    communities = query.order_by(desc(Community.created_at)).limit(limit).all()
    
    # Format response
    result = []
    for community in communities:
        result.append(_format_community_response(community, current_user.id, db))
    
    return result

@router.get("/communities/{community_id}", response_model=CommunityResponse)
def get_community(
    community_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get community details
    """
    
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    
    # Check if user is member
    membership = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.user_id == current_user.id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this community")
    
    return _format_community_response(community, current_user.id, db)


@router.put("/communities/{community_id}", response_model=CommunityResponse)
def update_community(
    community_id: int,
    updates: CommunityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update community details (creator only)
    """
    
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    
    # Only creator can update
    if community.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only creator can update community")
    
    # Update fields
    if updates.name is not None:
        community.name = updates.name
    if updates.description is not None:
        community.description = updates.description
    if updates.max_members is not None:
        community.max_members = updates.max_members
    
    community.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(community)
    
    return _format_community_response(community, current_user.id, db)


@router.delete("/communities/{community_id}")
def delete_community(
    community_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete community (creator only)
    """
    
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    
    # Only creator can delete
    if community.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only creator can delete community")
    
    db.delete(community)
    db.commit()
    
    return {"success": True, "message": "Community deleted"}


# ============================================================================
# INVITATIONS
# ============================================================================

@router.post("/communities/{community_id}/invite", response_model=InvitationResponse)
def invite_member(
    community_id: int,
    invite: InviteMemberRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Invite a user to community by their first name and last name
    
    Creator and admins can invite
    """
    
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    
    # Check if user can invite (creator or admin)
    membership = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.user_id == current_user.id
    ).first()
    
    if not membership or membership.role == CommunityRole.MEMBER:
        raise HTTPException(status_code=403, detail="Only creator/admin can invite members")
    
    # Find user by name
    target_user = db.query(User).filter(
        func.lower(User.first_name) == invite.first_name.lower(),
        func.lower(User.last_name) == invite.last_name.lower()
    ).first()
    
    if not target_user:
        raise HTTPException(
            status_code=404, 
            detail=f"User '{invite.first_name} {invite.last_name}' not found"
        )
    
    # Can't invite yourself
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot invite yourself")
    
    # Check if user is already a member
    existing_member = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.user_id == target_user.id
    ).first()
    
    if existing_member:
        raise HTTPException(status_code=400, detail="User is already a member")
    
    # Check if invitation already exists
    existing_invite = db.query(CommunityInvitation).filter(
        CommunityInvitation.community_id == community_id,
        CommunityInvitation.invited_user_id == target_user.id
    ).first()
    
    if existing_invite:
        if existing_invite.status == InvitationStatus.PENDING:
            raise HTTPException(status_code=400, detail="Invitation already sent")
        elif existing_invite.status == InvitationStatus.DECLINED:
            # Allow re-invitation after decline
            existing_invite.status = InvitationStatus.PENDING
            existing_invite.invited_by = current_user.id
            existing_invite.created_at = datetime.utcnow()
            db.commit()
            db.refresh(existing_invite)
            return _format_invitation_response(existing_invite, db)
    
    # Check member limit
    current_members = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id
    ).count()
    
    if current_members >= community.max_members:
        raise HTTPException(status_code=400, detail="Community is full")
    
    # Create invitation
    invitation = CommunityInvitation(
        community_id=community_id,
        invited_by=current_user.id,
        invited_user_id=target_user.id,
        status=InvitationStatus.PENDING
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    
    return _format_invitation_response(invitation, db)


@router.get("/invitations/pending", response_model=List[InvitationResponse])
def get_pending_invitations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all pending community invitations for current user
    """
    
    invitations = db.query(CommunityInvitation).filter(
        CommunityInvitation.invited_user_id == current_user.id,
        CommunityInvitation.status == InvitationStatus.PENDING
    ).order_by(desc(CommunityInvitation.created_at)).all()
    
    return [_format_invitation_response(inv, db) for inv in invitations]


@router.post("/invitations/{invitation_id}/accept")
def accept_invitation(
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Accept community invitation
    """
    
    invitation = db.query(CommunityInvitation).filter(
        CommunityInvitation.id == invitation_id
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    # Must be the invitee
    if invitation.invited_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Invitation is not pending")
    
    # Check member limit
    community = invitation.community
    current_members = db.query(CommunityMember).filter(
        CommunityMember.community_id == community.id
    ).count()
    
    if current_members >= community.max_members:
        raise HTTPException(status_code=400, detail="Community is full")
    
    # Accept invitation - create membership
    membership = CommunityMember(
        community_id=invitation.community_id,
        user_id=current_user.id,
        role=CommunityRole.MEMBER
    )
    db.add(membership)
    
    invitation.status = InvitationStatus.ACCEPTED
    invitation.updated_at = datetime.utcnow()
    
    db.commit()
    
    # ✅ NOTIFY INVITER THAT INVITATION WAS ACCEPTED
    invitee_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
    if not invitee_name:
        invitee_name = current_user.email.split('@')[0]
    
    NotificationService.notify_invite_accepted(
        db=db,
        inviter_id=invitation.invited_by,
        invitee_name=invitee_name,
        community_name=community.name
    )
    
    return {
        "success": True,
        "message": f"Joined {community.name}",
        "community": _format_community_response(community, current_user.id, db)
    }


@router.post("/invitations/{invitation_id}/decline")
def decline_invitation(
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Decline community invitation
    """
    
    invitation = db.query(CommunityInvitation).filter(
        CommunityInvitation.id == invitation_id
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    # Must be the invitee
    if invitation.invited_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Invitation is not pending")
    
    invitation.status = InvitationStatus.DECLINED
    invitation.updated_at = datetime.utcnow()
    db.commit()
    
    # ✅ NOTIFY INVITER THAT INVITATION WAS DECLINED
    decliner_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
    if not decliner_name:
        decliner_name = current_user.email.split('@')[0]
    
    NotificationService.notify_invite_declined(
        db=db,
        inviter_id=invitation.invited_by,
        invitee_name=decliner_name,
        community_name=invitation.community.name
    )
    
    return {
        "success": True,
        "message": "Invitation declined"
    }


# ============================================================================
# MEMBER MANAGEMENT
# ============================================================================

@router.get("/communities/{community_id}/members", response_model=List[MemberResponse])
def get_community_members(
    community_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all members of a community with their stats
    
    All community members can view the member list
    """
    
    # Check if user is member
    membership = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.user_id == current_user.id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this community")
    
    # Get all members
    members = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id
    ).order_by(desc(CommunityMember.joined_at)).all()
    
    members_data = []
    for member in members:
        user = member.user
        progress = db.query(UserProgress).filter(
            UserProgress.user_id == user.id
        ).first()
        
        members_data.append({
            "user_id": user.id,
            "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split('@')[0],
            "email": user.email,
            "role": member.role.value,
            "joined_at": member.joined_at,
            "accuracy": progress.average_accuracy if progress else 0.0,
            "total_recitations": progress.total_recitation_attempts if progress else 0,
            "current_streak": progress.current_streak if progress else 0
        })
    
    return members_data


@router.delete("/communities/{community_id}/members/{user_id}")
def remove_member(
    community_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove a member from community (creator only)
    
    Creator cannot remove themselves
    """
    
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    
    # Only creator can remove members
    if community.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only creator can remove members")
    
    # Cannot remove yourself
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself. Delete community instead.")
    
    # Find membership
    membership = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.user_id == user_id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=404, detail="User is not a member")
    
    # Remove member
    db.delete(membership)
    db.commit()
    
    return {
        "success": True,
        "message": "Member removed from community"
    }


@router.post("/communities/{community_id}/leave")
def leave_community(
    community_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Leave a community (members only, not creator)
    """
    
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    
    # Creator cannot leave, must delete community instead
    if community.created_by == current_user.id:
        raise HTTPException(
            status_code=400, 
            detail="Creator cannot leave. Delete community instead."
        )
    
    # Find membership
    membership = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.user_id == current_user.id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=404, detail="Not a member of this community")
    
    # Leave community
    db.delete(membership)
    db.commit()
    
    return {
        "success": True,
        "message": f"Left {community.name}"
    }


# ============================================================================
# COMMUNITY LEADERBOARD
# ============================================================================

@router.get("/communities/{community_id}/leaderboard")
def get_community_leaderboard(
    community_id: int,
    limit: int = Query(100, ge=1, le=100, description="Number of users to return (max 100)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get leaderboard for a specific community
    Ranking formula: 70% accuracy + 30% recitations (normalized)
    """

    # Check if user is member
    membership = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this community")

    community = membership.community
    member_ids = [m.user_id for m in community.members]

    if not member_ids:
        return {
            "community_id": community.id,
            "community_name": community.name,
            "top_3": [], "rankings": [],
            "current_user": None,
            "total_participants": 0,
            "total_members": 0,
            "scoring": "70% accuracy + 30% recitations"
        }

    MIN_RECITATIONS = 5

    # Get all eligible community members
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
            User.id.in_(member_ids),
            UserProgress.total_recitation_attempts >= MIN_RECITATIONS,
            UserProgress.average_accuracy > 0,
            UserSettings.show_on_leaderboard == True,
            ~User.email.in_(ADMIN_EMAILS)  # ✅ ADD THIS
        )
    ).all()

    if not eligible:
        current_progress = db.query(UserProgress).filter(
            UserProgress.user_id == current_user.id
        ).first()
        remaining = MIN_RECITATIONS - (current_progress.total_recitation_attempts if current_progress else 0)
        return {
            "community_id": community.id,
            "community_name": community.name,
            "top_3": [], "rankings": [],
            "current_user": {"rank": None, "message": f"Complete {max(0, remaining)} more recitations to join"},
            "total_participants": 0,
            "total_members": len(member_ids),
            "scoring": "70% accuracy + 30% recitations"
        }

    # Normalize against community's top user (not global)
    max_recitations = max(row.total_recitation_attempts for row in eligible)

    # Calculate scores
    scored = []
    for row in eligible:
        normalized_rec = (row.total_recitation_attempts / max_recitations) * 100
        score = round((row.average_accuracy * 0.7) + (normalized_rec * 0.3), 2)
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

    # Sort by score
    scored.sort(key=lambda x: (x["score"], x["accuracy"], x["total_recitations"]), reverse=True)

    # Build rankings
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

    # If current user outside top 100
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
                "message": f"Complete {max(0, remaining)} more recitations to join"
            }

    return {
        "community_id": community.id,
        "community_name": community.name,
        "top_3": top_3,
        "rankings": rankings,
        "current_user": user_rank,
        "total_participants": len(scored),
        "total_members": len(member_ids),
        "scoring": "70% accuracy + 30% recitations"
    }

@router.post("/communities/{community_id}/join-request")
def send_join_request(
    community_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.email in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin accounts cannot join communities")
    
    """
    Send a join request to a community
    
    User clicks "Join" on a community, request goes to creator
    """
    
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    
    # Check if user is already a member
    existing_member = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.user_id == current_user.id
    ).first()
    
    if existing_member:
        raise HTTPException(status_code=400, detail="Already a member of this community")
    
    # Check if join request already exists
    existing_request = db.query(CommunityInvitation).filter(
        CommunityInvitation.community_id == community_id,
        CommunityInvitation.invited_user_id == current_user.id
    ).first()
    
    if existing_request:
        if existing_request.status == InvitationStatus.PENDING:
            raise HTTPException(status_code=400, detail="Join request already sent")
        elif existing_request.status == InvitationStatus.DECLINED:
            # Allow re-requesting after decline
            existing_request.status = InvitationStatus.PENDING
            existing_request.created_at = datetime.utcnow()
            existing_request.invited_by = current_user.id  # User is requesting (inviting themselves)
            db.commit()
            db.refresh(existing_request)
            
            # ✅ NOTIFY CREATOR ABOUT RE-REQUESTED JOIN
            requester_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
            if not requester_name:
                requester_name = current_user.email.split('@')[0]
            
            NotificationService.notify_join_request(
                db=db,
                creator_id=community.created_by,
                requester_name=requester_name,
                community_name=community.name,
                request_id=existing_request.id
            )
            
            return {
                "success": True,
                "message": "Join request sent",
                "request_id": existing_request.id
            }
    
    # Check member limit
    current_members = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id
    ).count()
    
    if current_members >= community.max_members:
        raise HTTPException(status_code=400, detail="Community is full")
    
    # Create join request (invitation from user to themselves)
    join_request = CommunityInvitation(
        community_id=community_id,
        invited_by=current_user.id,  # User is the one requesting
        invited_user_id=current_user.id,
        status=InvitationStatus.PENDING
    )
    db.add(join_request)
    db.commit()
    db.refresh(join_request)
    
    # ✅ NOTIFY CREATOR ABOUT JOIN REQUEST
    requester_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
    if not requester_name:
        requester_name = current_user.email.split('@')[0]
    
    NotificationService.notify_join_request(
        db=db,
        creator_id=community.created_by,
        requester_name=requester_name,
        community_name=community.name,
        request_id=join_request.id
    )
    
    return {
        "success": True,
        "message": f"Join request sent to {community.name}",
        "request_id": join_request.id
    }


@router.get("/communities/{community_id}/join-requests", response_model=List[JoinRequestResponse])
def get_join_requests(
    community_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all pending join requests for a community (creator/admin only)
    
    Shows list of users who want to join the community
    """
    
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    
    # Only creator can view join requests
    if community.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only creator can view join requests")
    
    # Get all pending requests where user is requesting to join
    # (invited_by == invited_user_id means it's a join request)
    requests = db.query(CommunityInvitation).filter(
        CommunityInvitation.community_id == community_id,
        CommunityInvitation.status == InvitationStatus.PENDING,
        CommunityInvitation.invited_by == CommunityInvitation.invited_user_id  # Self-invitation = join request
    ).order_by(desc(CommunityInvitation.created_at)).all()
    
    result = []
    for request in requests:
        user = db.query(User).filter(User.id == request.invited_user_id).first()
        if user:
            result.append(JoinRequestResponse(
                id=request.id,
                community_id=community.id,
                community_name=community.name,
                requester_id=user.id,
                requester_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split('@')[0],
                requester_email=user.email,
                status=request.status.value,
                created_at=request.created_at
            ))
    
    return result


@router.post("/communities/{community_id}/join-requests/{request_id}/approve")
def approve_join_request(
    community_id: int,
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Approve a join request (creator only)
    
    Adds the user to the community
    """
    
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    
    # Only creator can approve
    if community.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only creator can approve join requests")
    
    # Get the join request
    join_request = db.query(CommunityInvitation).filter(
        CommunityInvitation.id == request_id,
        CommunityInvitation.community_id == community_id
    ).first()
    
    if not join_request:
        raise HTTPException(status_code=404, detail="Join request not found")
    
    if join_request.status != InvitationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Join request is not pending")
    
    # Check member limit
    current_members = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id
    ).count()
    
    if current_members >= community.max_members:
        raise HTTPException(status_code=400, detail="Community is full")
    
    # Add user to community
    membership = CommunityMember(
        community_id=community_id,
        user_id=join_request.invited_user_id,
        role=CommunityRole.MEMBER
    )
    db.add(membership)
    
    # Update request status
    join_request.status = InvitationStatus.ACCEPTED
    join_request.updated_at = datetime.utcnow()
    
    db.commit()
    
    user = db.query(User).filter(User.id == join_request.invited_user_id).first()
    
    NotificationService.create_notification(
        db=db,
        user_id=join_request.invited_user_id,
        notification_type=NotificationType.COMMUNITY_JOINED,
        title="Join Request Approved! ✅",
        message=f"Your request to join '{community.name}' has been approved! Welcome!",
        related_entity_type="community",
        related_entity_id=community_id
    )
    
    return {
        "success": True,
        "message": f"Approved {user.email} to join {community.name}",
        "user_id": user.id,
        "community_id": community.id
    }


@router.post("/communities/{community_id}/join-requests/{request_id}/reject")
def reject_join_request(
    community_id: int,
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reject a join request (creator only)
    
    User will not be added to the community
    """
    
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    
    # Only creator can reject
    if community.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only creator can reject join requests")
    
    # Get the join request
    join_request = db.query(CommunityInvitation).filter(
        CommunityInvitation.id == request_id,
        CommunityInvitation.community_id == community_id
    ).first()
    
    if not join_request:
        raise HTTPException(status_code=404, detail="Join request not found")
    
    if join_request.status != InvitationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Join request is not pending")
    
    # Reject the request
    join_request.status = InvitationStatus.DECLINED
    join_request.updated_at = datetime.utcnow()
    db.commit()
    
    NotificationService.create_notification(
        db=db,
        user_id=join_request.invited_user_id,
        notification_type=NotificationType.REMOVED_FROM_COMMUNITY,
        title="Join Request Declined ❌",
        message=f"Your request to join '{community.name}' was not approved at this time.",
        related_entity_type="community",
        related_entity_id=community_id
    )
    
    return {
        "success": True,
        "message": "Join request rejected"
    }


@router.get("/my-join-requests", response_model=List[JoinRequestResponse])
def get_my_join_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all join requests sent by current user
    
    Shows status of communities user has requested to join
    """
    
    requests = db.query(CommunityInvitation).filter(
        CommunityInvitation.invited_user_id == current_user.id,
        CommunityInvitation.invited_by == current_user.id  # Self-invitation = join request
    ).order_by(desc(CommunityInvitation.created_at)).all()
    
    result = []
    for request in requests:
        community = request.community
        result.append(JoinRequestResponse(
            id=request.id,
            community_id=community.id,
            community_name=community.name,
            requester_id=current_user.id,
            requester_name="You",
            requester_email=current_user.email,
            status=request.status.value,
            created_at=request.created_at
        ))
    
    return result

@router.get("/communities-leaderboard")
def get_communities_leaderboard(
    limit: int = Query(100, ge=1, le=100, description="Number of communities to return (max 100)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Global community leaderboard

    Each community's score = sum of all members' individual scores
    Individual score = (accuracy * 0.7) + (normalized_recitations * 0.3)

    Returns:
    - top_3: Top 3 highlighted communities
    - rankings: Top 100 communities by score
    - your_community: Current user's community rank (highest ranked community they belong to)
    - total_communities: Total communities on leaderboard
    """

    MIN_RECITATIONS = 5

    # Get all communities
    all_communities = db.query(Community).all()

    if not all_communities:
        return {
            "top_3": [],
            "rankings": [],
            "your_community": None,
            "total_communities": 0,
            "scoring": "Sum of members scores (70% accuracy + 30% recitations)"
        }

    # Get global max recitations for normalization (same baseline as global leaderboard)
    from sqlalchemy import func as sqlfunc
    max_rec_result = db.query(sqlfunc.max(UserProgress.total_recitation_attempts)).join(
        UserSettings, UserProgress.user_id == UserSettings.user_id
    ).filter(
        UserProgress.total_recitation_attempts >= MIN_RECITATIONS,
        UserSettings.show_on_leaderboard == True
    ).scalar()

    max_recitations = max_rec_result or 1

    # Calculate score for each community
    community_scores = []

    for community in all_communities:
        member_ids = [m.user_id for m in community.members]

        if not member_ids:
            continue

        # Get eligible members
        eligible = db.query(
            UserProgress.average_accuracy,
            UserProgress.total_recitation_attempts
        ).join(
            User, UserProgress.user_id == User.id
        ).join(
            UserSettings, User.id == UserSettings.user_id
        ).filter(
            User.id.in_(member_ids),
            UserProgress.total_recitation_attempts >= MIN_RECITATIONS,
            UserProgress.average_accuracy > 0,
            UserSettings.show_on_leaderboard == True,
            ~User.email.in_(ADMIN_EMAILS)
        ).all()

        if not eligible:
            continue

        # Sum of all members' scores
        total_score = 0
        for member in eligible:
            normalized_rec = (member.total_recitation_attempts / max_recitations) * 100
            member_score = (member.average_accuracy * 0.7) + (normalized_rec * 0.3)
            total_score += member_score

        total_score = round(total_score, 2)
        avg_score = round(total_score / len(eligible), 2)

        # Get creator name
        creator = db.query(User).filter(User.id == community.created_by).first()
        creator_name = f"{creator.first_name or ''} {creator.last_name or ''}".strip() or creator.email.split('@')[0] if creator else "Unknown"

        community_scores.append({
            "community_id": community.id,
            "community_name": community.name,
            "description": community.description,
            "total_score": total_score,
            "avg_member_score": avg_score,
            "active_members": len(eligible),
            "total_members": len(member_ids),
            "creator_name": creator_name,
            "is_your_community": any(m.user_id == current_user.id for m in community.members)
        })

    # Sort by total score descending
    community_scores.sort(key=lambda x: (x["total_score"], x["avg_member_score"]), reverse=True)

    # Build rankings
    rankings = []
    top_3 = []
    your_community = None

    for idx, comm in enumerate(community_scores[:limit], start=1):
        entry = {
            "rank": idx,
            "community_id": comm["community_id"],
            "community_name": comm["community_name"],
            "description": comm["description"],
            "total_score": comm["total_score"],
            "avg_member_score": comm["avg_member_score"],
            "active_members": comm["active_members"],
            "total_members": comm["total_members"],
            "creator_name": comm["creator_name"],
            "is_your_community": comm["is_your_community"]
        }

        rankings.append(entry)

        if idx <= 3:
            top_3.append(entry)

        if comm["is_your_community"] and your_community is None:
            your_community = entry

    # If user's community outside top 100
    if not your_community:
        user_comm = next((c for c in community_scores if c["is_your_community"]), None)
        if user_comm:
            full_rank = next(
                (i + 1 for i, c in enumerate(community_scores) if c["community_id"] == user_comm["community_id"]),
                None
            )
            your_community = {
                "rank": full_rank,
                "community_id": user_comm["community_id"],
                "community_name": user_comm["community_name"],
                "total_score": user_comm["total_score"],
                "avg_member_score": user_comm["avg_member_score"],
                "active_members": user_comm["active_members"],
                "total_members": user_comm["total_members"],
                "is_your_community": True
            }
        else:
            your_community = {
                "rank": None,
                "message": "Join or create a community to appear here"
            }

    return {
        "top_3": top_3,
        "rankings": rankings,
        "your_community": your_community,
        "total_communities": len(community_scores),
        "scoring": "Sum of members scores (70% accuracy + 30% recitations)"
    }

@router.post("/communities/{community_id}/upload-image")
async def upload_community_image(
    community_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload community image (creator only)"""
    
    from app.image_utils import upload_image
    
    community = db.query(Community).filter(Community.id == community_id).first()
    if not community:
        raise HTTPException(status_code=404, detail="Community not found")
    
    if community.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only creator can update image")
    
    # Upload to Cloudinary
    image_url = await upload_image(file, folder="quran_app/communities")
    
    # Update community
    community.community_image_url = image_url
    db.commit()
    db.refresh(community)
    
    return {
        "message": "Community image uploaded successfully",
        "image_url": image_url,
        "community": _format_community_response(community, current_user.id, db)
    }
# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _format_community_response(community: Community, user_id: int, db: Session) -> CommunityResponse:
    """Format community for response"""
    creator = db.query(User).filter(User.id == community.created_by).first()
    member_count = db.query(CommunityMember).filter(
        CommunityMember.community_id == community.id
    ).count()
    
    # Get user's role
    membership = db.query(CommunityMember).filter(
        CommunityMember.community_id == community.id,
        CommunityMember.user_id == user_id
    ).first()
    
    return CommunityResponse(
        id=community.id,
        name=community.name,
        description=community.description,
        created_by=community.created_by,
        creator_name=f"{creator.first_name or ''} {creator.last_name or ''}".strip() or creator.email.split('@')[0],
        member_count=member_count,
        max_members=community.max_members,
        is_private=community.is_private,
        created_at=community.created_at,
        user_role=membership.role.value if membership else None,
        community_image_url=community.community_image_url
    )


def _format_invitation_response(invitation: CommunityInvitation, db: Session) -> InvitationResponse:
    """Format invitation for response"""
    inviter = db.query(User).filter(User.id == invitation.invited_by).first()
    community = invitation.community
    
    return InvitationResponse(
        id=invitation.id,
        community_id=community.id,
        community_name=community.name,
        invited_by_id=inviter.id,
        invited_by_name=f"{inviter.first_name or ''} {inviter.last_name or ''}".strip() or inviter.email.split('@')[0],
        status=invitation.status.value,
        created_at=invitation.created_at
    )