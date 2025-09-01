import os
import asyncio
from googletrans import Translator
from gtts import gTTS
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize translator
translator = Translator()

async def translate_to_hindi(text: str) -> str:
    """
    Translate the given text to Hindi asynchronously using googletrans.
    
    Args:
        text (str): The text to translate.
        
    Returns:
        str: Translated text in Hindi.
    """
    try:
        # Translate the text to Hindi
        translated = await translator.translate(text, src='en', dest='hi')
        return translated.text
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
        return None

async def translate_and_generate_audio(text: str, lang: str = "en", output_file: str = "audio_summary.mp3") -> Optional[str]:
    """
    Generate an audio file from the given text in the specified language.
    
    Args:
        text (str): The text to convert to speech.
        lang (str): Language code (e.g., 'en' for English, 'hi' for Hindi).
        output_file (str): The name of the output audio file.
        
    Returns:
        str: Path to the generated audio file.
        None: If TTS generation fails.
    """
    try:
        logger.info(f"Starting audio generation (lang={lang}), text length: {len(text)} chars")
        
        # Validate input
        if not text or not isinstance(text, str):
            logger.error("Invalid text input")
            return None
            
        # Limit text length to prevent issues
        text = text[:500]  # Limit to 500 characters
        
        # If language is not English, translate first
        target_lang = lang
        if lang != "en":
            logger.info(f"Translating text to {lang}")
            try:
                translated_text = await translate_to_hindi(text)
                if not translated_text:
                    logger.error(f"Translation returned empty result")
                    return None
                text = translated_text
                target_lang = 'hi'
                logger.info(f"Translation completed, new text length: {len(text)} chars")
            except Exception as e:
                logger.error(f"Translation failed: {str(e)}", exc_info=True)
                # Continue with original text if translation fails
                logger.info("Continuing with original text")
        
        # Ensure output directory exists
        output_dir = os.path.dirname(os.path.abspath(output_file))
        if output_dir:  # Only create directory if output_file has a path
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Ensured output directory exists: {output_dir}")
        
        # Generate audio in the specified language
        logger.info(f"Generating TTS for {len(text)} characters in language: {target_lang}")
        try:
            tts = gTTS(
                text=text, 
                lang=target_lang, 
                slow=False,
                lang_check=False  # Disable language check to prevent errors
            )
            
            # Save to a temporary file first
            temp_file = output_file + ".tmp"
            tts.save(temp_file)
            
            # Rename to final filename after successful save
            if os.path.exists(temp_file):
                # Remove destination file if it exists
                if os.path.exists(output_file):
                    os.remove(output_file)
                os.rename(temp_file, output_file)
                
                # Verify file was created and has content
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    file_size = os.path.getsize(output_file)
                    logger.info(f"Successfully generated audio file: {output_file} ({file_size} bytes)")
                    return output_file
                else:
                    logger.error(f"Output file is empty or was not created: {output_file}")
                    return None
            else:
                logger.error(f"Temporary output file was not created: {temp_file}")
                return None
                
        except Exception as e:
            logger.error(f"TTS generation failed: {str(e)}", exc_info=True)
            # Clean up any partial files
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            return None
            
    except Exception as e:
        logger.error(f"Error in generate_audio: {str(e)}")
        return None

# Example usage
async def main():
    # Test with sample data
    overall_summary = "Reliance Industries has shown strong financial performance this quarter, with a 20% increase in profits. The company's announcement to expand into European markets further underscores its growth trajectory. However, it faces criticism from environmental groups regarding its carbon emissions. The overall sentiment score is 0.3"
    
    # Translate and generate audio
    audio_file = await translate_and_generate_audio(overall_summary)
    if audio_file:
        print(f"Audio file generated: {audio_file}")
    else:
        print("Failed to generate audio file.")

if __name__ == "__main__":
    asyncio.run(main())