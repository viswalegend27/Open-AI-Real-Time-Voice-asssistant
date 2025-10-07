#!/usr/bin/env python3
"""Test Whisper transcription with the debug audio file"""

from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Find the most recent debug audio file
import glob
debug_files = glob.glob("debug_audio_*.wav")
if not debug_files:
    print("❌ No debug audio files found!")
    exit(1)

latest_file = max(debug_files, key=os.path.getmtime)
print(f"Testing with: {latest_file}")
print(f"File size: {os.path.getsize(latest_file)} bytes")

# Test 1: Simple transcription (how webrtc_utils.py currently does it)
print("\n=== Test 1: Using file tuple (current method) ===")
with open(latest_file, 'rb') as f:
    try:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=(latest_file, f, 'audio/wav'),
            language="en",
            temperature=0.0,
            prompt="Transcribe exactly what the user says. Common phrases: 'hello', 'hi', 'am I audible'."
        )
        print(f"✅ Result: '{transcript.text}'")
    except Exception as e:
        print(f"❌ Error: {e}")

# Test 2: Direct file path (simpler method)
print("\n=== Test 2: Using file object directly ===")
with open(latest_file, 'rb') as f:
    try:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="en",
            temperature=0.0,
            prompt="Transcribe exactly what the user says. Common phrases: 'hello', 'hi', 'am I audible'."
        )
        print(f"✅ Result: '{transcript.text}'")
    except Exception as e:
        print(f"❌ Error: {e}")

# Test 3: Without prompt
print("\n=== Test 3: Without prompt ===")
with open(latest_file, 'rb') as f:
    try:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="en",
            temperature=0.0
        )
        print(f"✅ Result: '{transcript.text}'")
    except Exception as e:
        print(f"❌ Error: {e}")

print("\n=== File Details ===")
import wave
try:
    with wave.open(latest_file, 'rb') as wav:
        print(f"Channels: {wav.getnchannels()}")
        print(f"Sample width: {wav.getsampwidth()} bytes")
        print(f"Frame rate: {wav.getframerate()} Hz")
        print(f"Frames: {wav.getnframes()}")
        print(f"Duration: {wav.getnframes() / wav.getframerate():.2f} seconds")
except Exception as e:
    print(f"Could not read WAV details: {e}")
