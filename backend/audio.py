from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import os
import logging
from datetime import datetime
import uuid
from tts import translate_and_generate_audio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        
        # Make sure the audio directory exists
        os.makedirs('static/audio', exist_ok=True)
        output_path = os.path.join('static', 'audio', filename)
        
        logger.info(f"Starting audio generation for text (length: {len(audio_request.text)} chars)")
        
        # Generate the audio file
        audio_path = await translate_and_generate_audio(
            text=audio_request.text,
            lang=audio_request.language,
            output_file=output_path
        )
        
        if not audio_path or not os.path.exists(audio_path):
            logger.error(f"Audio file not created at expected path: {output_path}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate audio file"
            )
        
        # Get the absolute path for the web URL
        web_path = f"static/audio/{filename}"
        base_url = os.getenv('BASE_URL', 'http://localhost:8000')
        audio_url = f"{base_url}/{web_path}"
        
        logger.info(f"Audio generated successfully at: {audio_url}")
        
        return {
            "success": True,
            "audio_url": audio_url,
            "message": "Audio generated successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio generation failed: {str(e)}"
        )
