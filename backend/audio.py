from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import os
from datetime import datetime
import uuid
from tts import translate_and_generate_audio

router = APIRouter()

# Ensure audio directory exists
os.makedirs('static/audio', exist_ok=True)

class AudioRequest(BaseModel):
    text: str
    language: str = "en"

@router.post("/audio-summary")
async def generate_audio(audio_request: AudioRequest):
    try:
        # Generate a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"audio_{timestamp}_{unique_id}.mp3"
        output_path = f"static/audio/{filename}"
        
        # Generate the audio file
        audio_path = await translate_and_generate_audio(
            text=audio_request.text,
            lang=audio_request.language,
            output_file=output_path
        )
        
        if not audio_path or not os.path.exists(audio_path):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate audio file"
            )
        
        # Return the URL to access the audio file
        base_url = os.getenv('BASE_URL', 'http://localhost:8000')
        return {
            "audio_url": f"{base_url}/static/audio/{filename}",
            "message": "Audio generated successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio generation failed: {str(e)}"
        )
