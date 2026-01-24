import requests
from app.database import SessionLocal, engine, Base
from app.models import Surah, Ayah

URL = "https://api.alquran.cloud/v1/quran/quran-uthmani"

Base.metadata.create_all(bind=engine)

db = SessionLocal()

response = requests.get(URL)
data = response.json()["data"]["surahs"]

for surah in data:
    db_surah = Surah(
        number=surah["number"],
        name_ar=surah["name"],
        name_en=surah["englishName"],
        ayah_count=len(surah["ayahs"]),
    )
    db.add(db_surah)
    db.flush()  # get surah.id

    for ayah in surah["ayahs"]:
        db_ayah = Ayah(
            surah_id=db_surah.id,
            number=ayah["numberInSurah"],
            text=ayah["text"],
        )
        db.add(db_ayah)

db.commit()
db.close()
