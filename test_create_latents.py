#!/usr/bin/env python3
"""
Test client for create_latents endpoint
"""

import requests
import json
import os
import sys
from pathlib import Path

# Configuration
SERVER_URL = "http://127.0.0.1:8020"
ENDPOINT = "/create_latents"

def test_create_latents():
    """Test the create_latents endpoint and save latents locally"""
    
    # Check if wav file argument is provided
    if len(sys.argv) < 2:
        print("Usage: python test_create_latents.py <path_to_wav_file> [speaker_name] [language]")
        print("Example: python test_create_latents.py speaker.wav john_doe en")
        sys.exit(1)
    
    wav_file_path = sys.argv[1]
    speaker_name = sys.argv[2] if len(sys.argv) > 2 else "test_speaker"
    language = sys.argv[3] if len(sys.argv) > 3 else "en"
    
    # Check if wav file exists
    if not os.path.exists(wav_file_path):
        print(f"Error: WAV file '{wav_file_path}' not found")
        sys.exit(1)
    
    # Prepare the request
    url = f"{SERVER_URL}{ENDPOINT}"
    
    # Form data for the request
    data = {
        "speaker_name": speaker_name,
        "language": language
    }
    
    # File upload
    files = {
        "wav_file": open(wav_file_path, "rb")
    }
    
    try:
        print(f"Testing create_latents endpoint...")
        print(f"URL: {url}")
        print(f"Speaker: {speaker_name}")
        print(f"Language: {language}")
        print(f"WAV file: {wav_file_path}")
        print("-" * 50)
        
        # Make the POST request
        response = requests.post(url, data=data, files=files)
        
        # Close file
        files["wav_file"].close()
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            
            print("SUCCESS!")
            print(f"Message: {result['message']}")
            print(f"Server file path: {result['file_path']}")
            
            # Save latents locally as JSON
            local_filename = f"{speaker_name}_{language}_latents.json"
            with open(local_filename, 'w') as f:
                json.dump(result['latents'], f, indent=2)
            
            print(f"Latents saved locally to: {local_filename}")
            
            # Print some info about the latents
            latents = result['latents']
            print(f"GPT conditional latent shape: {len(latents['gpt_cond_latent'])}")
            print(f"Speaker embedding shape: {len(latents['speaker_embedding'])}")
            
        else:
            print(f"ERROR: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to server at {SERVER_URL}")
        print("Make sure the XTTS API server is running")
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        
    finally:
        # Ensure file is closed
        if 'files' in locals() and not files["wav_file"].closed:
            files["wav_file"].close()

if __name__ == "__main__":
    test_create_latents()