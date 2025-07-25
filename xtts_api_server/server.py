from TTS.api import TTS
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Query, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse,StreamingResponse

from pydantic import BaseModel
import uvicorn
from typing import Optional

import os
import time
from pathlib import Path
import shutil
from loguru import logger
from argparse import ArgumentParser
from pathlib import Path
from uuid import uuid4
import tempfile
import io
import json

from xtts_api_server.tts_funcs import TTSWrapper,supported_languages,InvalidSettingsError
from xtts_api_server.RealtimeTTS import TextToAudioStream, CoquiEngine
from xtts_api_server.modeldownloader import check_stream2sentence_version,install_deepspeed_based_on_python_version
import sys

# Remove the default logger to avoid conflicts
logger.remove()
# Add a new logger for console output, ensuring it doesn't prompt for input
logger.add(sys.stdout, format="{time} {level} {message}", level="INFO", enqueue=True)

# Default Folders , you can change them via API
DEVICE = os.getenv('DEVICE',"cuda")
OUTPUT_FOLDER = os.getenv('OUTPUT', 'output')
SPEAKER_FOLDER = os.getenv('SPEAKER', 'speakers')
LATENT_SPEAKER_FOLDER = os.getenv('LATENT_SPEAKER','latent_speaker_folder')
MODEL_FOLDER = os.getenv('MODEL', 'xtts_models')
BASE_HOST = os.getenv('BASE_URL', '127.0.0.1:8020')
BASE_URL = os.getenv('BASE_URL', '127.0.0.1:8020')
MODEL_SOURCE = os.getenv("MODEL_SOURCE", "local")
MODEL_VERSION = os.getenv("MODEL_VERSION","v2.0.2")
LOWVRAM_MODE = os.getenv("LOWVRAM_MODE") == 'true'
DEEPSPEED = os.getenv("DEEPSPEED") == 'true'
USE_CACHE = os.getenv("USE_CACHE") == 'true'

# STREAMING VARS
STREAM_MODE = os.getenv("STREAM_MODE") == 'true'
STREAM_MODE_IMPROVE = os.getenv("STREAM_MODE_IMPROVE") == 'true'
STREAM_PLAY_SYNC = os.getenv("STREAM_PLAY_SYNC") == 'true'

if(DEEPSPEED):
  install_deepspeed_based_on_python_version()
  
# Create an instance of the TTSWrapper class and server
app = FastAPI()
XTTS = TTSWrapper(OUTPUT_FOLDER,SPEAKER_FOLDER,LATENT_SPEAKER_FOLDER,MODEL_FOLDER,LOWVRAM_MODE,MODEL_SOURCE,MODEL_VERSION,DEVICE,DEEPSPEED,USE_CACHE)

# Check for old format model version
XTTS.model_version = XTTS.check_model_version_old_format(MODEL_VERSION)
MODEL_VERSION = XTTS.model_version

# Create version string
version_string = ""
if MODEL_SOURCE == "api" or MODEL_VERSION == "main":
    version_string = "latest"
else:
    version_string = MODEL_VERSION

# Load model
if STREAM_MODE or STREAM_MODE_IMPROVE:
    # Load model for Streaming
    check_stream2sentence_version()

    logger.warning("'Streaming Mode' has certain limitations, you can read about them here https://github.com/daswer123/xtts-api-server#about-streaming-mode")

    if STREAM_MODE_IMPROVE:
        logger.info("You launched an improved version of streaming, this version features an improved tokenizer and more context when processing sentences, which can be good for complex languages like Chinese")
        
    model_path = XTTS.model_folder
    
    engine = CoquiEngine(specific_model=MODEL_VERSION,use_deepspeed=DEEPSPEED,local_models_path=str(model_path))
    stream = TextToAudioStream(engine)
else:
  logger.info(f"Model: '{version_string}' starts to load,wait until it loads")
  XTTS.load_model() 

if USE_CACHE:
    logger.info("You have enabled caching, this option enables caching of results, your results will be saved and if there is a repeat request, you will get a file instead of generation")

# Add CORS middleware 
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Help funcs
def play_stream(stream,language):
  if STREAM_MODE_IMPROVE:
    # Here we define common arguments in a dictionary for DRY principle
    play_args = {
        'minimum_sentence_length': 2,
        'minimum_first_fragment_length': 2,
        'tokenizer': "stanza",
        'language': language,
        'context_size': 2
    }
    if STREAM_PLAY_SYNC:
        # Play synchronously
        stream.play(**play_args)
    else:
        # Play asynchronously
        stream.play_async(**play_args)
  else:
    # If not improve mode just call the appropriate method based on sync_play flag.
    if STREAM_PLAY_SYNC:
      stream.play()
    else:
      stream.play_async()

class OutputFolderRequest(BaseModel):
    output_folder: str

class SpeakerFolderRequest(BaseModel):
    speaker_folder: str

class ModelNameRequest(BaseModel):
    model_name: str

class TTSSettingsRequest(BaseModel):
    stream_chunk_size: int
    temperature: float
    speed: float
    length_penalty: float
    repetition_penalty: float
    top_p: float
    top_k: int
    enable_text_splitting: bool

class SynthesisRequest(BaseModel):
    text: str
    speaker_wav: Optional[str] = None
    language: str
    accent: Optional[str] = None
    save_path: Optional[str] = None

class SynthesisFileRequest(BaseModel):
    text: str
    speaker_wav: Optional[str] = None
    language: str
    file_name_or_path: str
    save_path: Optional[str] = None

class TTSStreamRequest(BaseModel):
    text: str
    speaker_wav: Optional[str] = None
    language: str
    save_path: Optional[str] = None

class StoreLatentsRequest(BaseModel):
    speaker_name: str
    language: str
    latents: dict  # Should contain 'gpt_cond_latent' and 'speaker_embedding' keys

@app.get("/speakers_list")
def get_speakers():
    speakers = XTTS.get_speakers()
    return speakers

@app.get("/speakers")
def get_speakers():
    speakers = XTTS.get_speakers_special()
    return speakers

@app.get("/languages")
def get_languages():
    languages = XTTS.list_languages()
    return {"languages": languages}

@app.get("/get_folders")
def get_folders():
    speaker_folder = XTTS.speaker_folder
    output_folder = XTTS.output_folder
    model_folder = XTTS.model_folder
    return {"speaker_folder": speaker_folder, "output_folder": output_folder,"model_folder":model_folder}

@app.get("/get_models_list")
def get_models_list():
    return XTTS.get_models_list()

@app.get("/get_tts_settings")
def get_tts_settings():
    settings = {**XTTS.tts_settings,"stream_chunk_size":XTTS.stream_chunk_size}
    return settings

@app.get("/sample/{file_name:path}")
def get_sample(file_name: str):
    # A fix for path traversal vulenerability. 
    # An attacker may summon this endpoint with ../../etc/passwd and recover the password file of your PC (in linux) or access any other file on the PC
    if ".." in file_name:
        raise HTTPException(status_code=404, detail=".. in the file name! Are you kidding me?") 
    file_path = os.path.join(XTTS.speaker_folder, file_name)
    if os.path.isfile(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    else:
        logger.error("File not found")
        raise HTTPException(status_code=404, detail="File not found")

@app.post("/set_output")
def set_output(output_req: OutputFolderRequest):
    try:
        XTTS.set_out_folder(output_req.output_folder)
        return {"message": f"Output folder set to {output_req.output_folder}"}
    except ValueError as e:
        logger.error(e)
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/set_speaker_folder")
def set_speaker_folder(speaker_req: SpeakerFolderRequest):
    try:
        XTTS.set_speaker_folder(speaker_req.speaker_folder)
        return {"message": f"Speaker folder set to {speaker_req.speaker_folder}"}
    except ValueError as e:
        logger.error(e)
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/switch_model")
def switch_model(modelReq: ModelNameRequest):
    try:
        XTTS.switch_model(modelReq.model_name)
        return {"message": f"Model switched to {modelReq.model_name}"}
    except InvalidSettingsError as e:  
        logger.error(e)
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/set_tts_settings")
def set_tts_settings_endpoint(tts_settings_req: TTSSettingsRequest):
    try:
        XTTS.set_tts_settings(**tts_settings_req.dict())
        return {"message": "Settings successfully applied"}
    except InvalidSettingsError as e: 
        logger.error(e)
        raise HTTPException(status_code=400, detail=str(e))

@app.get('/tts_stream')
async def tts_stream(request: TTSStreamRequest):
    # Validate local model source.
    if XTTS.model_source != "local":
        raise HTTPException(status_code=400,
                            detail="HTTP Streaming is only supported for local models.")
    # Validate language code against supported languages.
    if request.language.lower() not in supported_languages:
        raise HTTPException(status_code=400,
                            detail="Language code sent is either unsupported or misspelled.")
            
    async def generator():
        chunks = XTTS.process_tts_to_file(
            text=request.text,
            speaker_name_or_path=request.speaker_wav,
            language=request.language.lower(),
            stream=True,
        )
        # Write file header to the output stream.
        yield XTTS.get_wav_header()
        async for chunk in chunks:
            # Check if the client is still connected.
            disconnected = await request.is_disconnected()
            if disconnected:
                break
            yield chunk

    return StreamingResponse(generator(), media_type='audio/x-wav')

@app.post("/tts_to_audio/")
async def tts_to_audio(request: SynthesisRequest, background_tasks: BackgroundTasks):
    if STREAM_MODE or STREAM_MODE_IMPROVE:
        try:
            global stream
            # Validate language code against supported languages.
            if request.language.lower() not in supported_languages:
                raise HTTPException(status_code=400,
                                    detail="Language code sent is either unsupported or misspelled.")

            speaker_wav = XTTS.get_speaker_wav(request.speaker_wav)
            language = request.language[0:2]

            if stream.is_playing() and not STREAM_PLAY_SYNC:
                stream.stop()
                stream = TextToAudioStream(engine)

            engine.set_voice(speaker_wav)
            engine.language = request.language.lower()
           
            # Start streaming, works only on your local computer.
            stream.feed(request.text)
            play_stream(stream,language)

            # It's a hack, just send 1 second of silence so that there is no sillyTavern error.
            this_dir = Path(__file__).parent.resolve()
            output = this_dir / "RealtimeTTS" / "silence.wav"

            return FileResponse(
                path=output,
                media_type='audio/wav',
                filename="silence.wav",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    else:
        try:
            if XTTS.model_source == "local":
              logger.info(f"Processing TTS to audio with request: {request}")

            # Validate language code against supported languages.
            if request.language.lower() not in supported_languages:
                raise HTTPException(status_code=400,
                                    detail="Language code sent is either unsupported or misspelled.")

            # Generate an audio file using process_tts_to_file.
            output_file_path = XTTS.process_tts_to_file(
                text=request.text,
                speaker_name_or_path=request.speaker_wav,
                language=request.language.lower(),
                accent=request.accent,
                file_name_or_path=request.save_path
            )
            
            if not XTTS.enable_cache_results:
                background_tasks.add_task(os.unlink, output_file_path)
                
            # Return the file in the response
            return FileResponse(
                path=output_file_path,
                media_type='audio/wav',
                filename="output.wav",
                )

        except Exception as e:
            logger.error(e)
            raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/tts_to_file")
async def tts_to_file(request: SynthesisFileRequest):
    try:
        if XTTS.model_source == "local":
          logger.info(f"Processing TTS to file with request: {request}")

        # Validate language code against supported languages.
        if request.language.lower() not in supported_languages:
             raise HTTPException(status_code=400,
                                 detail="Language code sent is either unsupported or misspelled.")

        # Now use process_tts_to_file for saving the file.
        output_file = XTTS.process_tts_to_file(
            text=request.text,
            speaker_name_or_path=request.speaker_wav,
            language=request.language.lower(),
            file_name_or_path=request.file_name_or_path  # The user-provided path to save the file is used here.
        )
        return {"message": "The audio was successfully made and stored.", "output_path": output_file}

    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/create_latents")
async def create_latents(wav_file: UploadFile = File(...)):
    try:
        # Create temporary file for the uploaded wav
        temp_audio_name = next(tempfile._get_candidate_names()) + ".wav"
        temp_audio_path = os.path.join(tempfile.gettempdir(), temp_audio_name)

        # Write uploaded file to temporary location
        with open(temp_audio_path, "wb") as temp_file:
            content = await wav_file.read()
            temp_file.write(content)

        # Generate latents using XTTS model
        gpt_cond_latent, speaker_embedding = XTTS.model.get_conditioning_latents(temp_audio_path)

        # Convert to lists for JSON serialization
        latents_data = {
            "gpt_cond_latent": gpt_cond_latent.cpu().squeeze().half().tolist(),
            "speaker_embedding": speaker_embedding.cpu().squeeze().half().tolist()
        }

        # Clean up temporary file
        os.unlink(temp_audio_path)

        logger.info("Latents created successfully")

        return {
            "message": "Latents created successfully",
            "latents": latents_data
        }

    except Exception as e:
        # Clean up temporary file if it exists
        if 'temp_audio_path' in locals() and os.path.exists(temp_audio_path):
            os.unlink(temp_audio_path)
        logger.error(f"Error creating latents: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating latents: {str(e)}")

@app.post("/store_latents")
async def store_latents(request: StoreLatentsRequest):
    try:
        # Validate language code
        if request.language.lower() not in supported_languages:
            raise HTTPException(status_code=400, 
                              detail="Language code sent is either unsupported or misspelled.")
        
        # Validate latents structure
        if not isinstance(request.latents, dict):
            raise HTTPException(status_code=400, detail="Latents must be a dictionary")
        
        required_keys = ["gpt_cond_latent", "speaker_embedding"]
        for key in required_keys:
            if key not in request.latents:
                raise HTTPException(status_code=400, 
                                  detail=f"Missing required key '{key}' in latents")
        
        # Create language folder if it doesn't exist
        language_folder = os.path.join(XTTS.latent_speaker_folder, request.language.lower())
        os.makedirs(language_folder, exist_ok=True)
        
        # Save latents to JSON file (will replace if exists)
        json_file_path = os.path.join(language_folder, f"{request.speaker_name.lower()}.json")
        with open(json_file_path, 'w') as json_file:
            json.dump(request.latents, json_file)
        
        logger.info(f"Latents stored for {request.speaker_name} in {request.language} at {json_file_path}")
        
        return {
            "message": f"Latents stored for speaker '{request.speaker_name}' in language '{request.language}'",
            "file_path": json_file_path
        }
        
    except Exception as e:
        logger.error(f"Error storing latents: {e}")
        raise HTTPException(status_code=500, detail=f"Error storing latents: {str(e)}")

@app.on_event("startup")
async def show_disclaimer():
    disclaimer_message = """
    Disclaimer on AI Voice Cloning and Translations:

    Before using any custom voices from a mod to generate AI voice lines or train voice models, please ask for explicit permission from the mod author. This applies to creating voice-over translations or any other modifications involving AI-generated dialogue. If permission is not granted, no voices from that mod should be used or cloned.

    Base Game Voice Models:

    All AI-generated voice models used in this mod are created solely from Skyrim's base game voices. No custom or modded voice assets are used without permission.

    For Users and Mod Creators:

    Mod Creators: If you notice your custom voice has been mistakenly included or referenced, please contact me, and I will promptly remove it.

    Users: If you use any tools related to this mod for voice generation, ensure you have obtained the necessary permissions from the mod authors beforehand.

    Thank you for your understanding!
    """
    print(disclaimer_message)

if __name__ == "__main__":
    disable_quick_edit()
    uvicorn.run(app, host="0.0.0.0", port=8020, log_level="info", access_log=True)
