"""
Recitation Evaluation Service
==============================
Word-by-word comparison of recited text against Quran reference.
Adapted from teammate's implementation.
"""

import re
import difflib
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class WordStatus(str, Enum):
    """Status of each word in evaluation"""
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"
    MISSING = "missing"
    EXTRA = "extra"


class WordFeedback(BaseModel):
    """Feedback for a single word"""
    reference_word: str
    user_word: str
    status: WordStatus
    similarity: float  # 0.0 to 1.0
    color: str
    note: Optional[str] = None

    class Config:
        use_enum_values = True


class EvaluationResult(BaseModel):
    """Complete evaluation result"""
    surah_number: Optional[int] = None
    surah_name_ar: Optional[str] = None
    surah_name_en: Optional[str] = None
    ayah_start: Optional[int] = None
    ayah_end: Optional[int] = None
    
    reference_text: str
    user_text: str
    
    overall_accuracy: float
    total_words: int
    correct_words: int
    partial_words: int
    incorrect_words: int
    missing_words: int
    extra_words: int
    
    word_feedback: List[WordFeedback]
    suggestions: List[str] = []


class ArabicTextNormalizer:
    """Normalize Arabic text for comparison"""
    
    DIACRITICS = re.compile(r'[\u064B-\u065F\u0670\u06D6-\u06ED]')
    
    @classmethod
    def normalize(cls, text: str) -> str:
        """Normalize Arabic text"""
        if not text:
            return ""
        
        text = cls.DIACRITICS.sub('', text)
        text = re.sub('[أإآٱ]', 'ا', text)
        text = text.replace('ى', 'ي')
        text = text.replace('ة', 'ه')
        text = text.replace('ـ', '')
        text = text.replace('ؤ', 'و')
        text = text.replace('ئ', 'ي')
        text = text.replace('ء', '')
        text = ' '.join(text.split())
        
        return text.strip()
    
    @classmethod
    def split_words(cls, text: str) -> List[str]:
        """Split Arabic text into words"""
        text = re.sub(r'[^\w\s\u0600-\u06FF]', '', text)
        words = text.split()
        return [w for w in words if w.strip()]


class RecitationEvaluator:
    """Evaluates Quran recitation accuracy"""
    
    def __init__(self):
        self.normalizer = ArabicTextNormalizer()
    
    def _calculate_similarity(self, word1: str, word2: str) -> float:
        """Calculate similarity between two words"""
        if not word1 or not word2:
            return 0.0
        
        w1 = self.normalizer.normalize(word1)
        w2 = self.normalizer.normalize(word2)
        
        if w1 == w2:
            return 1.0
        
        return difflib.SequenceMatcher(None, w1, w2).ratio()
    
    def _get_status_color(self, status: WordStatus) -> str:
        """Get color for word status"""
        colors = {
            WordStatus.CORRECT: "#27ae60",
            WordStatus.PARTIAL: "#f39c12",
            WordStatus.INCORRECT: "#e74c3c",
            WordStatus.MISSING: "#7f8c8d",
            WordStatus.EXTRA: "#9b59b6",
        }
        return colors.get(status, "#95a5a6")
    
    def evaluate(
        self,
        reference_text: str,
        user_text: str,
        surah_number: Optional[int] = None,
        surah_name_ar: Optional[str] = None,
        surah_name_en: Optional[str] = None,
        ayah_start: Optional[int] = None,
        ayah_end: Optional[int] = None
    ) -> EvaluationResult:
        """Evaluate user's recitation"""
        
        ref_words = self.normalizer.split_words(reference_text)
        user_words = self.normalizer.split_words(user_text)
        
        ref_normalized = [self.normalizer.normalize(w) for w in ref_words]
        user_normalized = [self.normalizer.normalize(w) for w in user_words]
        
        correct_count = 0
        partial_count = 0
        incorrect_count = 0
        missing_count = 0
        extra_count = 0
        
        word_feedback: List[WordFeedback] = []
        
        user_idx = 0
        matched_user_indices = set()
        
        for ref_idx, ref_word in enumerate(ref_words):
            best_score = 0.0
            best_user_idx = -1
            best_user_word = ""
            
            search_start = max(0, user_idx - 3)
            search_end = min(len(user_words), user_idx + 10)
            
            for j in range(search_start, search_end):
                if j in matched_user_indices:
                    continue
                
                similarity = self._calculate_similarity(ref_word, user_words[j])
                if similarity > best_score:
                    best_score = similarity
                    best_user_idx = j
                    best_user_word = user_words[j]
            
            if best_score >= 0.85:
                status = WordStatus.CORRECT
                correct_count += 1
                if best_user_idx >= 0:
                    matched_user_indices.add(best_user_idx)
                    user_idx = best_user_idx + 1
            elif best_score >= 0.50:
                status = WordStatus.PARTIAL
                partial_count += 1
                if best_user_idx >= 0:
                    matched_user_indices.add(best_user_idx)
                    user_idx = best_user_idx + 1
            elif best_score >= 0.25:
                status = WordStatus.INCORRECT
                incorrect_count += 1
                if best_user_idx >= 0:
                    matched_user_indices.add(best_user_idx)
                    user_idx = best_user_idx + 1
            else:
                status = WordStatus.MISSING
                missing_count += 1
                best_user_word = ""
                best_score = 0.0
            
            note = None
            if status == WordStatus.PARTIAL:
                note = "Similar to expected word"
            elif status == WordStatus.INCORRECT:
                note = "Different from expected"
            elif status == WordStatus.MISSING:
                note = "Word was not recited"
            
            word_feedback.append(WordFeedback(
                reference_word=ref_word,
                user_word=best_user_word,
                status=status,
                similarity=round(best_score, 3),
                color=self._get_status_color(status),
                note=note
            ))
        
        for j, user_word in enumerate(user_words):
            if j not in matched_user_indices:
                extra_count += 1
                word_feedback.append(WordFeedback(
                    reference_word="",
                    user_word=user_word,
                    status=WordStatus.EXTRA,
                    similarity=0.0,
                    color=self._get_status_color(WordStatus.EXTRA),
                    note="Extra word not in reference"
                ))
        
        total_ref_words = len(ref_words)
        if total_ref_words > 0:
            weighted_score = correct_count + (partial_count * 0.5) + (incorrect_count * 0.25)
            overall_accuracy = (weighted_score / total_ref_words) * 100
        else:
            overall_accuracy = 0.0
        
        suggestions = self._generate_suggestions(
            correct_count, partial_count, incorrect_count,
            missing_count, extra_count, total_ref_words
        )
        
        return EvaluationResult(
            surah_number=surah_number,
            surah_name_ar=surah_name_ar,
            surah_name_en=surah_name_en,
            ayah_start=ayah_start,
            ayah_end=ayah_end,
            reference_text=reference_text,
            user_text=user_text,
            overall_accuracy=round(overall_accuracy, 1),
            total_words=total_ref_words,
            correct_words=correct_count,
            partial_words=partial_count,
            incorrect_words=incorrect_count,
            missing_words=missing_count,
            extra_words=extra_count,
            word_feedback=word_feedback,
            suggestions=suggestions
        )
    
    def _generate_suggestions(
        self, correct: int, partial: int, incorrect: int,
        missing: int, extra: int, total: int
    ) -> List[str]:
        """Generate suggestions"""
        suggestions = []
        
        if total == 0:
            return ["No reference text provided"]
        
        accuracy = (correct + partial * 0.5) / total * 100
        
        if accuracy >= 90:
            suggestions.append("Excellent recitation! Keep practicing.")
        elif accuracy >= 70:
            suggestions.append("Good recitation. Focus on highlighted words.")
        elif accuracy >= 50:
            suggestions.append("Decent attempt. Listen to the Surah more.")
        else:
            suggestions.append("Keep practicing. Listen to a Qari first.")
        
        if missing > total * 0.2:
            suggestions.append(f"You missed {missing} words. Recite more slowly.")
        
        if incorrect > total * 0.1:
            suggestions.append(f"{incorrect} words were incorrect. Review them.")
        
        if extra > 3:
            suggestions.append(f"You added {extra} extra words. Follow the text.")
        
        if partial > correct:
            suggestions.append("Focus on proper pronunciation (tajweed).")
        
        return suggestions
