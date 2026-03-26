import requests
from sqlalchemy.orm import Session
from app.models import Surah, Ayah
from app.database import SessionLocal, engine, Base

# Editions
TEXT_EDITION = "quran-uthmani"
AUDIO_EDITION = "ar.alafasy"

def load_quran():
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    print(f"📥 Fetching Arabic text ({TEXT_EDITION})...")
    text_res = requests.get(f"https://api.alquran.cloud/v1/quran/{TEXT_EDITION}")
    if text_res.status_code != 200:
        print("❌ Failed to fetch text edition")
        return
    text_data = text_res.json()["data"]

    print(f"📥 Fetching Audio URLs ({AUDIO_EDITION})...")
    audio_res = requests.get(f"https://api.alquran.cloud/v1/quran/{AUDIO_EDITION}")
    if audio_res.status_code != 200:
        print("❌ Failed to fetch audio edition")
        return
    audio_data = audio_res.json()["data"]

    text_surahs = text_data["surahs"]
    audio_surahs = audio_data["surahs"]

    print(f"📦 Processing {len(text_surahs)} surahs...")

    for i in range(len(text_surahs)):
        s = text_surahs[i]
        audio_s = audio_surahs[i]
        
        # Check if Surah already exists
        surah = db.query(Surah).filter(Surah.number == s["number"]).first()
        if not surah:
            surah = Surah(
                number=s["number"],
                name_ar=s["name"],
                name_en=s["englishName"],
                ayah_count=len(s["ayahs"])
            )
            db.add(surah)
            db.flush()  # get surah.id
        else:
            surah.name_ar = s["name"]
            surah.name_en = s["englishName"]
            surah.ayah_count = len(s["ayahs"])
            db.flush()

        # Insert/Update Ayahs
        for j in range(len(s["ayahs"])):
            a = s["ayahs"][j]
            audio_a = audio_s["ayahs"][j]
            
            existing_ayah = db.query(Ayah).filter(
                Ayah.surah_id == surah.id, 
                Ayah.number == a["numberInSurah"]
            ).first()
            
            if existing_ayah:
                existing_ayah.text = a["text"]
                existing_ayah.audio = audio_a.get("audio")
            else:
                ayah = Ayah(
                    surah_id=surah.id,
                    number=a["numberInSurah"],
                    text=a["text"],
                    audio=audio_a.get("audio")
                )
                db.add(ayah)

        if s["number"] % 10 == 0:
            db.commit()
            print(f"💾 Checkpoint: Surah {s['number']} committed")
        else:
            print(f"✅ Surah {s['number']} processed")

    db.commit()
    db.close()
    print("🎉 Quran dataset loaded successfully with text and voice!")

if __name__ == "__main__":
    load_quran()
