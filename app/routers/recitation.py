from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import get_current_user
from app.models import User, SubscriptionStatus
import requests
from typing import Optional

router = APIRouter()

ALQURAN_API_BASE = "http://api.alquran.cloud/v1"

# Available reciters with their edition codes
RECITERS = {
    "ar.alafasy": {
        "name": "Mishary Rashid Alafasy",
        "language": "Arabic",
        "style": "Murattal",
        "premium": False
    },
    "ar.abdulbasitmurattal": {
        "name": "Abdul Basit Abdul Samad",
        "language": "Arabic",
        "style": "Murattal",
        "premium": False
    },
    "ar.husary": {
        "name": "Mahmoud Khalil Al-Husary",
        "language": "Arabic",
        "style": "Murattal",
        "premium": True
    },
    "ar.minshawi": {
        "name": "Mohamed Siddiq El-Minshawi",
        "language": "Arabic",
        "style": "Mujawwad",
        "premium": True
    },
    "ar.muhammadayyoub": {
        "name": "Muhammad Ayyub",
        "language": "Arabic",
        "style": "Murattal",
        "premium": True
    },
    "ar.shaatree": {
        "name": "Abu Bakr Al-Shaatri",
        "language": "Arabic",
        "style": "Murattal",
        "premium": True
    }
}

@router.get("/reciters")
def get_available_reciters(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of available reciters
    Premium users see all reciters, free users see limited options
    """
    is_premium = current_user.subscription_status in [
        SubscriptionStatus.ACTIVE, 
        SubscriptionStatus.LIFETIME
    ]
    
    available_reciters = []
    
    for edition_id, reciter_info in RECITERS.items():
        # Free users only see non-premium reciters
        if not is_premium and reciter_info["premium"]:
            available_reciters.append({
                "id": edition_id,
                "name": reciter_info["name"],
                "language": reciter_info["language"],
                "style": reciter_info["style"],
                "premium": True,
                "locked": True
            })
        else:
            available_reciters.append({
                "id": edition_id,
                "name": reciter_info["name"],
                "language": reciter_info["language"],
                "style": reciter_info["style"],
                "premium": reciter_info["premium"],
                "locked": False
            })
    
    return {
        "user_subscription": current_user.subscription_status,
        "is_premium": is_premium,
        "reciters": available_reciters
    }

@router.get("/surah/{surah_number}/recitation")
def get_surah_recitation(
    surah_number: int,
    reciter: str = "ar.alafasy",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get audio recitation for a specific surah
    
    Parameters:
    - surah_number: Surah number (1-114)
    - reciter: Reciter edition ID (e.g., 'ar.alafasy')
    """
    
    # Validate surah number
    if surah_number < 1 or surah_number > 114:
        raise HTTPException(status_code=400, detail="Invalid surah number. Must be between 1 and 114")
    
    # Check if reciter exists
    if reciter not in RECITERS:
        raise HTTPException(status_code=400, detail="Invalid reciter ID")
    
    # Check if user has access to premium reciter
    is_premium = current_user.subscription_status in [
        SubscriptionStatus.ACTIVE, 
        SubscriptionStatus.LIFETIME
    ]
    
    if RECITERS[reciter]["premium"] and not is_premium:
        raise HTTPException(
            status_code=403, 
            detail="This reciter is only available for premium users. Please upgrade your subscription."
        )
    
    # Fetch recitation from AlQuran API
    try:
        response = requests.get(f"{ALQURAN_API_BASE}/surah/{surah_number}/{reciter}")
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 200:
            raise HTTPException(status_code=404, detail="Recitation not found")
        
        surah_data = data["data"]
        
        # Extract audio URLs from ayahs
        audio_files = []
        for ayah in surah_data.get("ayahs", []):
            if "audio" in ayah:
                audio_files.append({
                    "ayah_number": ayah["numberInSurah"],
                    "audio_url": ayah["audio"],
                    "text": ayah["text"]
                })
        
        return {
            "surah_number": surah_data["number"],
            "surah_name": surah_data["name"],
            "surah_name_english": surah_data["englishName"],
            "reciter": {
                "id": reciter,
                "name": RECITERS[reciter]["name"],
                "style": RECITERS[reciter]["style"]
            },
            "number_of_ayahs": surah_data["numberOfAyahs"],
            "audio_files": audio_files
        }
        
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch recitation: {str(e)}")

@router.get("/ayah/{ayah_number}/recitation")
def get_ayah_recitation(
    ayah_number: int,
    reciter: str = "ar.alafasy",
    current_user: User = Depends(get_current_user)
):
    """
    Get audio recitation for a specific ayah (across all surahs)
    
    Parameters:
    - ayah_number: Ayah number (1-6236)
    - reciter: Reciter edition ID
    """
    
    # Check if user has access to premium reciter
    is_premium = current_user.subscription_status in [
        SubscriptionStatus.ACTIVE, 
        SubscriptionStatus.LIFETIME
    ]
    
    if reciter in RECITERS and RECITERS[reciter]["premium"] and not is_premium:
        raise HTTPException(
            status_code=403, 
            detail="This reciter is only available for premium users."
        )
    
    try:
        response = requests.get(f"{ALQURAN_API_BASE}/ayah/{ayah_number}/{reciter}")
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 200:
            raise HTTPException(status_code=404, detail="Ayah not found")
        
        ayah_data = data["data"]
        
        return {
            "ayah_number": ayah_data["number"],
            "surah_number": ayah_data["surah"]["number"],
            "surah_name": ayah_data["surah"]["name"],
            "ayah_in_surah": ayah_data["numberInSurah"],
            "text": ayah_data["text"],
            "audio_url": ayah_data.get("audio"),
            "reciter": {
                "id": reciter,
                "name": RECITERS[reciter]["name"] if reciter in RECITERS else "Unknown"
            }
        }
        
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch ayah: {str(e)}")

@router.get("/surah/{surah_number}/info")
def get_surah_info(surah_number: int):
    """Get basic information about a surah (text only, no audio)"""
    
    if surah_number < 1 or surah_number > 114:
        raise HTTPException(status_code=400, detail="Invalid surah number")
    
    try:
        response = requests.get(f"{ALQURAN_API_BASE}/surah/{surah_number}")
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 200:
            raise HTTPException(status_code=404, detail="Surah not found")
        
        surah_data = data["data"]
        
        return {
            "number": surah_data["number"],
            "name": surah_data["name"],
            "englishName": surah_data["englishName"],
            "englishNameTranslation": surah_data["englishNameTranslation"],
            "numberOfAyahs": surah_data["numberOfAyahs"],
            "revelationType": surah_data["revelationType"]
        }
        
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch surah info: {str(e)}")

@router.get("/surahs/list")
def get_all_surahs():
    """Get list of all 114 surahs"""
    
    try:
        response = requests.get(f"{ALQURAN_API_BASE}/surah")
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch surahs")
        
        return {
            "total": len(data["data"]),
            "surahs": data["data"]
        }
        
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch surahs: {str(e)}")

@router.get("/surah/{surah_number}/complete-recitation")
async def get_complete_surah_recitation(
    surah_number: int,
    reciter: str = "ar.alafasy",
    current_user: User = Depends(get_current_user)
):
    """
    Get complete surah recitation with all ayahs
    Returns a playlist that can be played sequentially
    """
    
    # Validate and check premium
    if surah_number < 1 or surah_number > 114:
        raise HTTPException(status_code=400, detail="Invalid surah number")
    
    is_premium = current_user.subscription_status in [
        SubscriptionStatus.ACTIVE, 
        SubscriptionStatus.LIFETIME
    ]
    
    if reciter in RECITERS and RECITERS[reciter]["premium"] and not is_premium:
        raise HTTPException(status_code=403, detail="Premium reciter requires subscription")
    
    try:
        response = requests.get(f"{ALQURAN_API_BASE}/surah/{surah_number}/{reciter}")
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 200:
            raise HTTPException(status_code=404, detail="Recitation not found")
        
        surah_data = data["data"]
        
        # Build the complete playlist
        audio_playlist = []
        for ayah in surah_data.get("ayahs", []):
            if "audio" in ayah:
                audio_playlist.append({
                    "index": ayah["numberInSurah"],
                    "url": ayah["audio"],
                    "text": ayah["text"]
                })
        
        return {
            "surah": {
                "number": surah_data["number"],
                "name_arabic": surah_data["name"],
                "name_english": surah_data["englishName"],
                "translation": surah_data["englishNameTranslation"],
                "number_of_ayahs": surah_data["numberOfAyahs"],
                "revelation_type": surah_data["revelationType"]
            },
            "reciter": {
                "id": reciter,
                "name": RECITERS[reciter]["name"],
                "style": RECITERS[reciter]["style"]
            },
            "audio": {
                "total_tracks": len(audio_playlist),
                "playlist": audio_playlist,
                "autoplay_enabled": True
            }
        }
        
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch recitation: {str(e)}")
    