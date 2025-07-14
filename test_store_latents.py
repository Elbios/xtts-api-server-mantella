#!/usr/bin/env python3
"""
Test client for store_latents endpoint
"""

import requests
import json
import os
import sys
from pathlib import Path

# Configuration
SERVER_URL = "http://127.0.0.1:8020"
ENDPOINT = "/store_latents"

def test_store_latents():
    """Test the store_latents endpoint"""
    
    # Check if JSON file argument is provided
    if len(sys.argv) < 2:
        print("Usage: python test_store_latents.py <path_to_latents_json> [speaker_name] [language]")
        print("Example: python test_store_latents.py latents.json john_doe en")
        sys.exit(1)
    
    json_file_path = sys.argv[1]
    speaker_name = sys.argv[2] if len(sys.argv) > 2 else "test_speaker"
    language = sys.argv[3] if len(sys.argv) > 3 else "en"
    
    # Check if JSON file exists
    if not os.path.exists(json_file_path):
        print(f"Error: JSON file '{json_file_path}' not found")
        sys.exit(1)
    
    # Load latents from JSON file
    try:
        with open(json_file_path, 'r') as f:
            latents_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file '{json_file_path}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{json_file_path}': {e}")
        sys.exit(1)
    
    # Validate latents structure
    required_keys = ["gpt_cond_latent", "speaker_embedding"]
    for key in required_keys:
        if key not in latents_data:
            print(f"Error: Missing required key '{key}' in latents JSON")
            sys.exit(1)
    
    # Prepare the request
    url = f"{SERVER_URL}{ENDPOINT}"
    
    # JSON payload
    payload = {
        "speaker_name": speaker_name,
        "language": language,
        "latents": latents_data
    }
    
    try:
        print(f"Testing store_latents endpoint...")
        print(f"URL: {url}")
        print(f"Speaker: {speaker_name}")
        print(f"Language: {language}")
        print(f"JSON file: {json_file_path}")
        print(f"GPT conditional latent length: {len(latents_data['gpt_cond_latent'])}")
        print(f"Speaker embedding length: {len(latents_data['speaker_embedding'])}")
        print("-" * 50)
        
        # Make the POST request
        response = requests.post(url, json=payload)
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            
            print("SUCCESS!")
            print(f"Message: {result['message']}")
            print(f"Server file path: {result['file_path']}")
            
        else:
            print(f"FAILED!")
            print(f"Status code: {response.status_code}")
            try:
                error_detail = response.json()
                print(f"Error details: {error_detail}")
            except:
                print(f"Response text: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"FAILED!")
        print(f"Could not connect to server at {SERVER_URL}")
        print("Make sure the XTTS API server is running")
        
    except Exception as e:
        print(f"FAILED!")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_store_latents()