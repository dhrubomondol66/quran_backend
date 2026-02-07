"""
Voice Recitation Service
=========================
Handles speech-to-text, evaluation, and session management for live recitation.
Integrates OpenAI Whisper and custom evaluation logic.
"""

import os
import base64
import io
import wave
import tempfile
import uuid
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass, field
from pydantic import BaseModel

# OpenAI for Whisper
from openai import AsyncOpenAI

# Import evaluation components from teammate's code
from app.services.evaluation_service import (
    RecitationEvaluator,
    EvaluationResult,
    WordFeedback,
    WordStatus
)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class RecitationSession:
    """Stores ongoing recitation session data"""
    session_id: str
    surah_number: int
    ayah_start: int
    ayah_end: int
    reference_text: str
    user_id: Optional[int]
    audio_chunks: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


class ProcessingResult(BaseModel):
    """Result from processing a recitation session"""
    success: bool
    
    # Transcription
    transcribed_text: str = ""
    transcription_confidence: str = "low"
    duration_seconds: Optional[float] = None
    
    # Evaluation
    overall_accuracy: float = 0.0
    total_words: int = 0
    correct_words: int = 0
    partial_words: int = 0
    incorrect_words: int = 0
    missing_words: int = 0
    extra_words: int = 0
    word_feedback: List[WordFeedback] = []
    suggestions: List[str] = []
    
    # Error
    error: Optional[str] = None


# ============================================================================
# VOICE SERVICE
# ============================================================================

class VoiceRecitationService:
    """
    Manages voice recitation sessions with real-time processing.
    Combines speech-to-text and evaluation.
    """
    
    def __init__(self):
        self.openai_client: Optional[AsyncOpenAI] = None
        self.evaluator = RecitationEvaluator()
        self.sessions: Dict[str, RecitationSession] = {}
        
        # Initialize OpenAI if API key is available
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.openai_client = AsyncOpenAI(api_key=api_key)
    
    def is_available(self) -> bool:
        """Check if STT service is available"""
        return self.openai_client is not None
    
    def create_session(
        self,
        surah_number: int,
        ayah_start: int,
        ayah_end: int,
        reference_text: str,
        user_id: Optional[int] = None
    ) -> RecitationSession:
        """Create a new recitation session"""
        
        session = RecitationSession(
            session_id=str(uuid.uuid4()),
            surah_number=surah_number,
            ayah_start=ayah_start,
            ayah_end=ayah_end,
            reference_text=reference_text,
            user_id=user_id
        )
        
        self.sessions[session.session_id] = session
        return session
    
    async def add_audio_chunk(self, session_id: str, audio_base64: str):
        """Add audio chunk to session"""
        session = self.sessions.get(session_id)
        if session:
            session.audio_chunks.append(audio_base64)
    
    def remove_session(self, session_id: str):
        """Remove session from memory"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    async def process_session(self, session_id: str) -> ProcessingResult:
        """
        Process complete recording:
        1. Combine audio chunks
        2. Transcribe with Whisper
        3. Evaluate against reference
        """
        
        session = self.sessions.get(session_id)
        if not session:
            return ProcessingResult(
                success=False,
                error="Session not found"
            )
        
        if not session.audio_chunks:
            return ProcessingResult(
                success=False,
                error="No audio data received"
            )
        
        if not self.is_available():
            return ProcessingResult(
                success=False,
                error="OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
            )
        
        try:
            # Step 1: Combine audio chunks into single WAV
            combined_audio = self._combine_audio_chunks(session.audio_chunks)
            
            # Step 2: Transcribe with Whisper
            transcription = await self._transcribe_audio(combined_audio)
            
            if not transcription["success"]:
                return ProcessingResult(
                    success=False,
                    error=transcription.get("error", "Transcription failed")
                )
            
            # Step 3: Evaluate against reference text
            evaluation = self.evaluator.evaluate(
                reference_text=session.reference_text,
                user_text=transcription["text"],
                surah_number=session.surah_number,
                ayah_start=session.ayah_start,
                ayah_end=session.ayah_end
            )
            
            # Return combined result
            return ProcessingResult(
                success=True,
                transcribed_text=transcription["text"],
                transcription_confidence=transcription.get("confidence", "medium"),
                duration_seconds=transcription.get("duration"),
                overall_accuracy=evaluation.overall_accuracy,
                total_words=evaluation.total_words,
                correct_words=evaluation.correct_words,
                partial_words=evaluation.partial_words,
                incorrect_words=evaluation.incorrect_words,
                missing_words=evaluation.missing_words,
                extra_words=evaluation.extra_words,
                word_feedback=evaluation.word_feedback,
                suggestions=evaluation.suggestions
            )
        
        except Exception as e:
            return ProcessingResult(
                success=False,
                error=f"Processing error: {str(e)}"
            )
    
    def _combine_audio_chunks(self, chunks: List[str]) -> bytes:
        """Combine base64 audio chunks into single WAV file"""
        
        if len(chunks) == 1:
            # Single chunk - just decode
            return base64.b64decode(chunks[0])
        
        # Multiple chunks - need to combine WAV data
        # For simplicity, we'll just decode and concatenate
        # Note: This assumes chunks are compatible WAV format
        combined = b""
        for chunk in chunks:
            audio_bytes = base64.b64decode(chunk)
            combined += audio_bytes
        
        return combined
    
    async def _transcribe_audio(self, audio_bytes: bytes) -> Dict:
        """Transcribe audio using OpenAI Whisper API"""
        
        try:
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name
            
            try:
                # Transcribe with Whisper
                with open(temp_path, 'rb') as audio_file:
                    response = await self.openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="ar",  # Arabic
                        response_format="verbose_json"
                    )
                
                text = response.text.strip()
                duration = getattr(response, 'duration', None)
                
                # Estimate confidence based on text length
                confidence = "high" if len(text) > 10 else "medium" if len(text) > 3 else "low"
                
                return {
                    "success": True,
                    "text": text,
                    "confidence": confidence,
                    "duration": duration
                }
            
            finally:
                # Clean up temp file
                try:
                    os.remove(temp_path)
                except:
                    pass
        
        except Exception as e:
            return {
                "success": False,
                "text": "",
                "error": str(e)
            }


# ============================================================================
# SINGLETON
# ============================================================================

_voice_service: Optional[VoiceRecitationService] = None


def get_voice_service() -> VoiceRecitationService:
    """Get singleton voice service instance"""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceRecitationService()
    return _voice_service
