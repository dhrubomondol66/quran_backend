"""
WebSocket Voice Recitation Router
===================================
Real-time voice recording and evaluation for Quran recitation.
Integrates with existing UserProgress and database.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict
import json
import base64
import asyncio
from datetime import datetime, timedelta  # ✅ ADD timedelta here

from app.database import get_db
from app.models import User, Surah, Ayah, UserProgress, UserActivity, ActivityType
from app.deps import get_current_user_ws, get_current_user  # ✅ ADD get_current_user here
from app.services.voice_service import (
    VoiceRecitationService,
    RecitationSession,
    get_voice_service
)

router = APIRouter()


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@router.websocket("/ws/recite")
async def websocket_recite(
    websocket: WebSocket,
    surah_number: int,
    ayah_start: int,
    ayah_end: Optional[int] = None
):
    """
    WebSocket endpoint for live voice recitation.
    
    **Connection Flow:**
    1. Frontend connects with Surah/Ayah parameters
    2. Backend validates and sends ready signal
    3. Frontend streams audio chunks (base64 WAV)
    4. Backend transcribes and evaluates in real-time
    5. Backend sends accuracy results
    6. Backend saves to database automatically
    
    **Message Format from Frontend:**
    ```json
    {
        "type": "audio_chunk",
        "data": "base64-encoded-wav-chunk",
        "is_final": false
    }
    ```
    
    **Or to end session:**
    ```json
    {
        "type": "end_session"
    }
    ```
    
    **Message Format to Frontend:**
    ```json
    {
        "type": "ready",
        "surah_info": {...}
    }
    ```
    
    ```json
    {
        "type": "transcription",
        "text": "بسم الله الرحمن الرحيم",
        "confidence": "high"
    }
    ```
    
    ```json
    {
        "type": "evaluation",
        "accuracy": 95.5,
        "word_feedback": [...],
        "saved_to_db": true
    }
    ```
    """
    
    await websocket.accept()
    
    # Get database session
    db = next(get_db())
    voice_service = get_voice_service()
    session: Optional[RecitationSession] = None
    
    try:
        # Validate surah/ayah
        ayah_end = ayah_end or ayah_start
        
        # Get reference text from database
        reference_text = await _get_reference_text(
            db, surah_number, ayah_start, ayah_end
        )
        
        if not reference_text:
            await websocket.send_json({
                "type": "error",
                "error": f"Invalid Surah/Ayah: {surah_number}:{ayah_start}-{ayah_end}"
            })
            await websocket.close()
            return
        
        # Get surah info
        surah = db.query(Surah).filter(Surah.number == surah_number).first()
        if not surah:
            await websocket.send_json({
                "type": "error",
                "error": "Surah not found"
            })
            await websocket.close()
            return
        
        # Try to get user (optional for now - you can make it required)
        user = None
        try:
            # You can add JWT token verification here if needed
            # user = await get_current_user_ws(websocket, db)
            pass
        except:
            pass
        
        # Create recitation session
        session = voice_service.create_session(
            surah_number=surah_number,
            ayah_start=ayah_start,
            ayah_end=ayah_end,
            reference_text=reference_text,
            user_id=user.id if user else None
        )
        
        # Send ready signal
        await websocket.send_json({
            "type": "ready",
            "session_id": session.session_id,
            "surah_info": {
                "number": surah.number,
                "name_ar": surah.name_ar,
                "name_en": surah.name_en,
                "ayah_range": f"{ayah_start}-{ayah_end}"
            },
            "reference_text": reference_text,
            "message": "Ready to receive audio. Start reciting!"
        })
        
        # Main loop - receive audio chunks
        while True:
            try:
                # Receive message
                message = await websocket.receive_json()
                msg_type = message.get("type")
                
                if msg_type == "audio_chunk":
                    # Process audio chunk
                    audio_base64 = message.get("data")
                    is_final = message.get("is_final", False)
                    
                    if audio_base64:
                        # Add to session buffer
                        await voice_service.add_audio_chunk(
                            session.session_id,
                            audio_base64
                        )
                        
                        # Send acknowledgment
                        await websocket.send_json({
                            "type": "chunk_received",
                            "chunks_received": len(session.audio_chunks)
                        })
                    
                    # If final chunk, process full recording
                    if is_final:
                        await _process_final_recording(
                            websocket, session, voice_service, db, user
                        )
                
                elif msg_type == "end_session":
                    # User manually ended session
                    if len(session.audio_chunks) > 0:
                        await _process_final_recording(
                            websocket, session, voice_service, db, user
                        )
                    break
                
                elif msg_type == "ping":
                    # Keep-alive
                    await websocket.send_json({"type": "pong"})
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Unknown message type: {msg_type}"
                    })
            
            except WebSocketDisconnect:
                break
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "error": str(e)
                })
    
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "error": str(e)
            })
        except:
            pass
    
    finally:
        # Cleanup
        if session:
            voice_service.remove_session(session.session_id)
        
        try:
            await websocket.close()
        except:
            pass


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _get_reference_text(
    db: Session,
    surah_number: int,
    ayah_start: int,
    ayah_end: int
) -> Optional[str]:
    """Get reference text from database"""
    
    ayahs = db.query(Ayah).filter(
        Ayah.surah_id == db.query(Surah.id).filter(Surah.number == surah_number).scalar_subquery(),
        Ayah.number >= ayah_start,
        Ayah.number <= ayah_end
    ).order_by(Ayah.number).all()
    
    if not ayahs:
        return None
    
    return " ".join(ayah.text for ayah in ayahs)


async def _process_final_recording(
    websocket: WebSocket,
    session: RecitationSession,
    voice_service: VoiceRecitationService,
    db: Session,
    user: Optional[User]
):
    """Process the complete recording - transcribe and evaluate"""
    
    try:
        # Notify processing started
        await websocket.send_json({
            "type": "processing",
            "message": "Transcribing your recitation..."
        })
        
        # Transcribe and evaluate
        result = await voice_service.process_session(session.session_id)
        
        if not result.success:
            await websocket.send_json({
                "type": "error",
                "error": result.error or "Processing failed"
            })
            return
        
        # Send transcription
        await websocket.send_json({
            "type": "transcription",
            "text": result.transcribed_text,
            "confidence": result.transcription_confidence,
            "duration_seconds": result.duration_seconds
        })
        
        # Send evaluation
        await websocket.send_json({
            "type": "evaluation",
            "accuracy": result.overall_accuracy,
            "total_words": result.total_words,
            "correct_words": result.correct_words,
            "partial_words": result.partial_words,
            "incorrect_words": result.incorrect_words,
            "missing_words": result.missing_words,
            "extra_words": result.extra_words,
            "word_feedback": [
                {
                    "reference_word": fb.reference_word,
                    "user_word": fb.user_word,
                    "status": fb.status,
                    "similarity": fb.similarity,
                    "color": fb.color,
                    "note": fb.note
                }
                for fb in result.word_feedback
            ],
            "suggestions": result.suggestions
        })
        
        # Save to database if user is authenticated
        if user:
            saved = await _save_to_database(
                db, user, session, result
            )
            
            await websocket.send_json({
                "type": "saved",
                "saved_to_db": saved,
                "message": "Progress saved!" if saved else "Could not save progress"
            })
        
        # Send completion
        await websocket.send_json({
            "type": "complete",
            "message": "Evaluation complete!"
        })
    
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "error": f"Processing error: {str(e)}"
        })


async def _save_to_database(
    db: Session,
    user: User,
    session: RecitationSession,
    result
) -> bool:
    """Save recitation results to UserProgress and UserActivity"""
    
    try:
        # Get or create user progress
        progress = db.query(UserProgress).filter(
            UserProgress.user_id == user.id
        ).first()
        
        if not progress:
            progress = UserProgress(user_id=user.id)
            db.add(progress)
            db.flush()
        
        # Update progress metrics
        progress.total_recitation_attempts += 1
        
        # Update accuracy
        progress.total_accuracy_points += result.overall_accuracy
        progress.average_accuracy = (
            progress.total_accuracy_points / progress.total_recitation_attempts
        )
        
        # Count as correct if accuracy >= 80%
        if result.overall_accuracy >= 80:
            progress.correct_recitations += 1
        
        # Track ayahs recited (approximate based on ayah range)
        ayah_count = session.ayah_end - session.ayah_start + 1
        progress.total_ayahs_recited += ayah_count
        
        # Update time spent (if duration available)
        if result.duration_seconds:
            progress.total_time_spent_seconds += int(result.duration_seconds)
        
        # Update streak
        today = datetime.utcnow().date()
        if progress.last_activity_date:
            last_date = progress.last_activity_date.date()
            if last_date == today:
                pass  # Same day
            elif last_date == today - timedelta(days=1):
                progress.current_streak += 1
                if progress.current_streak > progress.longest_streak:
                    progress.longest_streak = progress.current_streak
            else:
                progress.current_streak = 1
        else:
            progress.current_streak = 1
        
        progress.last_activity_date = datetime.utcnow()
        
        # Create activity record
        activity = UserActivity(
            user_progress_id=progress.id,
            activity_type=ActivityType.RECITATION,
            surah_number=session.surah_number,
            ayah_number=session.ayah_start,
            duration_seconds=int(result.duration_seconds) if result.duration_seconds else 0,
            accuracy_score=result.overall_accuracy,
            points_earned=int(result.overall_accuracy / 10)  # Simple points calculation
        )
        db.add(activity)
        
        db.commit()
        return True
    
    except Exception as e:
        db.rollback()
        print(f"Database save error: {e}")
        return False


# ============================================================================
# REST ENDPOINT FOR TESTING
# ============================================================================

@router.post("/api/recite/evaluate")
async def evaluate_recitation_rest(
    surah_number: int,
    ayah_start: int,
    ayah_end: Optional[int] = None,
    audio_base64: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    REST endpoint for one-shot recitation evaluation.
    Use this for testing or if WebSocket is not available.
    
    **Request Body:**
    ```json
    {
        "surah_number": 1,
        "ayah_start": 1,
        "ayah_end": 3,
        "audio_base64": "base64-encoded-wav-audio"
    }
    ```
    """
    
    if not audio_base64:
        raise HTTPException(status_code=400, detail="audio_base64 required")
    
    ayah_end = ayah_end or ayah_start
    
    # Get reference text
    reference_text = await _get_reference_text(
        db, surah_number, ayah_start, ayah_end
    )
    
    if not reference_text:
        raise HTTPException(
            status_code=404,
            detail=f"Ayah not found: Surah {surah_number}, Ayah {ayah_start}-{ayah_end}"
        )
    
    # Process
    voice_service = get_voice_service()
    
    # Create temporary session
    session = voice_service.create_session(
        surah_number=surah_number,
        ayah_start=ayah_start,
        ayah_end=ayah_end,
        reference_text=reference_text,
        user_id=current_user.id
    )
    
    # Add audio
    await voice_service.add_audio_chunk(session.session_id, audio_base64)
    
    # Process
    result = await voice_service.process_session(session.session_id)
    
    # Save to database
    if result.success:
        await _save_to_database(db, current_user, session, result)
    
    # Cleanup
    voice_service.remove_session(session.session_id)
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Processing failed")
    
    return {
        "success": True,
        "transcription": {
            "text": result.transcribed_text,
            "confidence": result.transcription_confidence,
            "duration_seconds": result.duration_seconds
        },
        "evaluation": {
            "accuracy": result.overall_accuracy,
            "total_words": result.total_words,
            "correct_words": result.correct_words,
            "partial_words": result.partial_words,
            "incorrect_words": result.incorrect_words,
            "missing_words": result.missing_words,
            "extra_words": result.extra_words,
            "word_feedback": [fb.dict() for fb in result.word_feedback],
            "suggestions": result.suggestions
        },
        "saved_to_db": True
    }
