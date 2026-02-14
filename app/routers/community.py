"""
Community Router
================
Handles community creation, invitations, member management, and community leaderboards

Features:
- Create communities
- Invite users by name
- Accept/decline invitations
- View community members
- Remove members (creator only)
- Community-specific leaderboard
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, func
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    User, Community, CommunityMember, CommunityInvitation,
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


# ============================================================================
# COMMUNITY CRUD
# ============================================================================

@router.post("/communities", response_model=CommunityResponse)
def create_community(
    community: CommunityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get leaderboard for a specific community
    
    Shows rankings of all community members
    """
    
    # Check if user is member
    membership = db.query(CommunityMember).filter(
        CommunityMember.community_id == community_id,
        CommunityMember.user_id == current_user.id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this community")
    
    community = membership.community
    
    # Get all member IDs
    member_ids = [m.user_id for m in community.members]
    
    if not member_ids:
        return {
            "community_name": community.name,
            "message": "No members in community yet",
            "rankings": [],
            "current_user": None,
            "total_participants": 0
        }
    
    # Get rankings for community members only
    MIN_RECITATIONS = 5
    
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
            User.id.in_(member_ids),
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
    user_rank = None
    
    for idx, row in enumerate(rankings_query, start=1):
        user_data = {
            "rank": idx,
            "user_id": row.id,
            "name": f"{row.first_name or ''} {row.last_name or ''}".strip() or row.email.split('@')[0],
            "accuracy": round(row.average_accuracy, 1),
            "total_recitations": row.total_recitation_attempts,
            "time_spent_hours": round(row.total_time_spent_seconds / 3600, 1),
            "streak": row.current_streak,
            "is_you": row.id == current_user.id
        }
        
        rankings.append(user_data)
        
        if row.id == current_user.id:
            user_rank = user_data
    
    # If current user not in rankings
    if not user_rank:
        current_progress = db.query(UserProgress).filter(
            UserProgress.user_id == current_user.id
        ).first()
        
        if current_progress and current_progress.total_recitation_attempts >= MIN_RECITATIONS:
            better_count = db.query(UserProgress).join(
                User, UserProgress.user_id == User.id
            ).join(
                UserSettings, User.id == UserSettings.user_id
            ).filter(
                and_(
                    User.id.in_(member_ids),
                    UserProgress.total_recitation_attempts >= MIN_RECITATIONS,
                    UserSettings.show_on_leaderboard == True,
                    UserProgress.average_accuracy > current_progress.average_accuracy
                )
            ).count()
            
            user_rank = {
                "rank": better_count + 1,
                "name": "You",
                "accuracy": round(current_progress.average_accuracy, 1),
                "total_recitations": current_progress.total_recitation_attempts,
                "is_you": True
            }
        else:
            user_rank = {
                "rank": None,
                "message": f"Complete {MIN_RECITATIONS - (current_progress.total_recitation_attempts if current_progress else 0)} more recitations"
            }
    
    return {
        "community_id": community.id,
        "community_name": community.name,
        "rankings": rankings,
        "current_user": user_rank,
        "total_participants": len(rankings),
        "total_members": len(member_ids)
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
        user_role=membership.role.value if membership else None
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