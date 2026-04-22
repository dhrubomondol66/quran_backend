import os
import uuid
import shutil
from fastapi import UploadFile, HTTPException
from app.config import UPLOAD_DIR, BACKEND_URL

async def upload_image(file: UploadFile, folder: str = "quran_app") -> str:
    """
    Save image to local disk (Render Disk)
    Returns: Full URL of uploaded image
    """
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only images allowed.")
    
    # Validate file size (max 5MB)
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 5MB.")
    
    await file.seek(0)  # Reset file pointer
    
    try:
        # Create target directory
        target_dir = os.path.join(UPLOAD_DIR, folder)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
        if not file_extension:
            file_extension = ".jpg"
            
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(target_dir, unique_filename)
        
        # Save file to disk
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Return the public URL
        # e.g., https://your-app.onrender.com/uploads/profiles/xyz.jpg
        relative_path = os.path.join(folder, unique_filename)
        # Ensure we use forward slashes for the URL
        url_path = relative_path.replace(os.sep, "/")
        return f"{BACKEND_URL}/uploads/{url_path}"
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")