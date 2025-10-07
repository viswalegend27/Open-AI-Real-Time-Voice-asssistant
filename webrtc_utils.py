import asyncio
import os
import json
import tempfile
import numpy as np
import soundfile as sf

from aiortc import MediaStreamTrack, RTCIceCandidate, RTCPeerConnection, RTCSessionDescription

# -- OPENAI AND AI AGENT HANDLER --
import openai
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

async def handle_audio_file(audio_file):
    filename, wav_bytes, content_type = audio_file
    transcript = None
    if OPENAI_API_KEY is None:
        print("[ERROR] OPENAI_API_KEY env variable not set!")
        return "[System: OpenAI key missing]"
    # Transcribe using OpenAI Whisper
    wav_bytes.seek(0)
    client = openai.AsyncClient(api_key=OPENAI_API_KEY)
    transcript_obj = await client.audio.transcriptions.create(
        model="whisper-1",
        file=wav_bytes,
        filename=filename,
        response_format="text"
    )
    transcript = transcript_obj.text if hasattr(transcript_obj, "text") else transcript_obj
    print(f"[OPENAI] Transcription: {transcript}")
    # Generate AI assistant response (ChatGPT)
    chat = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful and concise AI voice assistant."},
            {"role": "user", "content": transcript}
        ]
    )
    response = chat.choices[0].message.content
    print(f"[OPENAI] Assistant: {response}")
    # You could hook this to a TTS service or web client
    return response

class AudioReceiver(MediaStreamTrack):
    kind = "audio"

    def __init__(self, track, on_complete, min_seconds=3):
        super().__init__()
        self.track = track
        self.buffers = []
        self.on_complete = on_complete
        self.closed = False
        self.sample_rate = 48000
        self.min_seconds = min_seconds
        self.frame_count = 0
        self.process_task = None
        self.sending = False
        self.last_process_time = 0
        self.min_audio_length = 1.5  # Require at least 1.5 seconds
        self.silence_threshold = 0.05  # Much higher threshold to ignore background noise
        self.silence_duration = 3.0    # Wait 3 seconds of silence before processing
        self.last_audio_time = 0
        self.has_speech = False
        self.min_speech_length = 2.5   # Require at least 2.5 seconds of clear speech
        self.speech_volume_sum = 0.0   # Track total speech volume
        self.speech_frame_count = 0    # Count frames with actual speech

        # Half-duplex controls: pause listening while TTS is playing
        self.listening = True
        self.cooldown_until = 0.0  # when > now, ignore incoming frames

        import time
        self.time = time

    async def recv(self):
        try:
            frame = await self.track.recv()
            now = self.time.time()

            # If listening is paused or in cooldown, drop frames quietly
            if (not self.listening) or (now < self.cooldown_until):
                return frame

            pcm = frame.to_ndarray()
            
            # DEBUG: Check frame data
            if self.frame_count % 50 == 0:
                frame_min, frame_max = pcm.min(), pcm.max()
                frame_mean = np.mean(np.abs(pcm))
                print(f"[WebRTC-FRAME] Frame {self.frame_count}: shape={pcm.shape}, dtype={pcm.dtype}, range=[{frame_min}, {frame_max}], mean_abs={frame_mean:.2f}")
            
            self.buffers.append(pcm.copy())
            self.frame_count += 1
            current_time = now
            audio_level = np.sqrt(np.mean(pcm ** 2))
            if audio_level > self.silence_threshold:
                self.last_audio_time = current_time
                self.speech_volume_sum += audio_level
                self.speech_frame_count += 1
                if not self.has_speech:
                    print(f"[WebRTC] Speech detected! (level: {audio_level:.4f})")
                self.has_speech = True
            elif audio_level > 0.001:  # Very quiet audio (background noise)
                if self.frame_count % 100 == 0:
                    print(f"[WebRTC] Low audio: {audio_level:.4f} (threshold: {self.silence_threshold})")
            if len(self.buffers) > 0:
                total_samples = sum(buf.shape[1] for buf in self.buffers)
                audio_length_seconds = total_samples / self.sample_rate
            else:
                audio_length_seconds = 0
            silence_duration = current_time - self.last_audio_time
            has_enough_speech = self.has_speech and audio_length_seconds >= self.min_speech_length
            has_been_silent = silence_duration >= self.silence_duration

            should_process = (
                self.listening and
                (not self.sending) and
                len(self.buffers) > 0 and
                has_enough_speech and
                has_been_silent
            )
            # Fallback: process after 6 seconds to avoid waiting forever
            if (
                self.listening and (not self.sending) and len(self.buffers) > 0 and
                audio_length_seconds >= self.min_audio_length and
                (current_time - self.last_process_time) >= 6
            ):
                should_process = True
                print(f"[WebRTC] Timeout triggered - processing {audio_length_seconds:.1f}s of audio")
            if should_process:
                # Check speech quality before processing
                avg_speech_level = self.speech_volume_sum / max(self.speech_frame_count, 1)
                print(f"[WebRTC] Attempting to process: {audio_length_seconds:.1f}s audio, {silence_duration:.1f}s silence")
                print(f"[WebRTC] Speech quality: {self.speech_frame_count} frames, avg level: {avg_speech_level:.4f}")
                
                # Require minimum speech quality
                if avg_speech_level < 0.03 or self.speech_frame_count < 20:
                    print(f"[WebRTC] Rejecting: Speech quality too low or too few frames")
                    # Clear buffers and reset
                    self.buffers.clear()
                    self.frame_count = 0
                    self.has_speech = False
                    self.speech_volume_sum = 0.0
                    self.speech_frame_count = 0
                else:
                    print(f"[WebRTC] Processing speech: Quality OK")
                    self.sending = True
                    self.last_process_time = current_time
                    self.has_speech = False
                    self.speech_volume_sum = 0.0
                    self.speech_frame_count = 0
                    asyncio.create_task(self.flush_and_process())
            return frame
        except Exception:
            return None

    async def flush_and_process(self):
        """
        Fixed audio processing with correct resampling and normalization.
        """
        if not self.buffers:
            print("[WebRTC-DEBUG] flush_and_process: No buffers to process.")
            self.sending = False
            return
        
        import io
        from scipy import signal
        
        audio_buffers = self.buffers.copy()
        print(f"[WebRTC-DEBUG] buffer count: {len(audio_buffers)}")
        self.buffers.clear()
        self.frame_count = 0
        
        try:
            # Concatenate all audio chunks
            audio_data = np.concatenate(audio_buffers, axis=1)
            print(f"[WebRTC-DEBUG] Concatenated shape: {audio_data.shape}, dtype: {audio_data.dtype}")
            
            # Convert stereo to mono if needed
            if len(audio_data.shape) > 1 and audio_data.shape[0] > 1:
                print(f"[WebRTC-DEBUG] Converting {audio_data.shape[0]} channels to mono")
                audio_data = np.mean(audio_data, axis=0)
            
            # Flatten to 1D array
            audio_data = np.ravel(audio_data)
            print(f"[WebRTC-DEBUG] Flattened shape: {audio_data.shape}, dtype: {audio_data.dtype}")
            
            # CRITICAL FIX: Convert int16 to float32 properly!
            # WebRTC audio comes as int16 (-32768 to 32767), must normalize to float32 (-1.0 to 1.0)
            if audio_data.dtype == np.int16:
                int_min, int_max = audio_data.min(), audio_data.max()
                print(f"[WebRTC-DEBUG] Converting int16 to float32 (range: [{int_min}, {int_max}])")
                print(f"[WebRTC-DEBUG] int16 stats: mean={np.mean(audio_data):.1f}, std={np.std(audio_data):.1f}")
                audio_data = audio_data.astype(np.float32) / 32768.0  # Normalize int16 to -1.0 to 1.0
                print(f"[WebRTC-DEBUG] After normalization (range: [{audio_data.min():.3f}, {audio_data.max():.3f}])")
            elif audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Check audio levels
            max_abs = np.max(np.abs(audio_data))
            rms_level = np.sqrt(np.mean(audio_data ** 2))
            print(f"[WebRTC-DEBUG] Max amplitude: {max_abs:.6f}, RMS level: {rms_level:.6f}")
            
            # Check if audio has actual content
            if max_abs < 0.001:
                print(f"[WebRTC-WARN] Audio is silent! Rejecting...")
                self.sending = False
                return
            
            # Apply smart normalization
            if max_abs < 0.05:  # Very quiet
                print(f"[WebRTC-WARN] Audio very quiet (max: {max_abs:.4f}, RMS: {rms_level:.4f})")
                # Only amplify if RMS is reasonable (not just noise)
                if rms_level > 0.003:
                    target_level = 0.4  # Amplify to 40% of full scale
                    audio_data = audio_data * (target_level / max_abs)
                    print(f"[WebRTC-DEBUG] Amplified to {target_level} (gain: {target_level/max_abs:.1f}x)")
                else:
                    print(f"[WebRTC-WARN] Audio appears to be noise, rejecting...")
                    self.sending = False
                    return
            elif max_abs < 0.2:  # Moderately quiet
                target_level = 0.5
                audio_data = audio_data * (target_level / max_abs)
                print(f"[WebRTC-DEBUG] Normalized to {target_level}")
            
            # FIXED: Correct resampling from 48kHz to 16kHz
            src_rate = self.sample_rate
            target_rate = 16000
            
            if src_rate != target_rate:
                # Check audio before resampling
                pre_resample_stats = f"min={audio_data.min():.4f}, max={audio_data.max():.4f}, mean={np.mean(audio_data):.4f}"
                print(f"[WebRTC-DEBUG] Before resampling: {pre_resample_stats}")
                print(f"[WebRTC-DEBUG] Resampling from {src_rate}Hz to {target_rate}Hz...")
                
                # Calculate GCD for proper resampling ratio
                from math import gcd
                common = gcd(target_rate, src_rate)
                up = target_rate // common
                down = src_rate // common
                
                print(f"[WebRTC-DEBUG] Resample ratio: up={up}, down={down}")
                
                # Use correct resample_poly parameters
                audio_data = signal.resample_poly(audio_data, up, down)
                
                # Check audio after resampling
                post_resample_stats = f"min={audio_data.min():.4f}, max={audio_data.max():.4f}, mean={np.mean(audio_data):.4f}"
                print(f"[WebRTC-DEBUG] After resampling: {post_resample_stats}")
                print(f"[WebRTC-DEBUG] Resampled length: {len(audio_data)} samples ({len(audio_data)/target_rate:.2f}s)")
            
            # Verify audio duration
            duration = len(audio_data) / target_rate
            print(f"[WebRTC-DEBUG] Final audio duration: {duration:.2f}s")
            
            if duration < 0.1:
                print("[WebRTC-WARN] Audio too short (< 0.1s), skipping...")
                self.sending = False
                return
            
            if duration > 8.0:
                print(f"[WebRTC-WARN] Audio too long ({duration:.1f}s > 8s), likely contains silence/noise!")
                print(f"[WebRTC-WARN] Rejecting to prevent hallucinations")
                self.sending = False
                return
            
            # Convert to int16 PCM for WAV (audio is now in -1.0 to 1.0 range)
            audio_int16 = (audio_data * 32767.0).clip(-32768, 32767).astype(np.int16)
            print(f"[WebRTC-DEBUG] Final PCM16 range: [{audio_int16.min()}, {audio_int16.max()}]")
            
            # Verify audio quality
            non_zero = np.count_nonzero(audio_int16)
            total = len(audio_int16)
            zero_count = total - non_zero
            print(f"[WebRTC-DEBUG] Audio quality: {non_zero}/{total} ({100*non_zero/total:.1f}%) non-zero samples")
            print(f"[WebRTC-DEBUG] Zero samples: {zero_count} ({100*zero_count/total:.1f}%)")
            
            # Check if mostly silence/zeros
            if zero_count > (total * 0.9):
                print(f"[WebRTC-ERROR] Audio is 90%+ zeros/silence! This will cause hallucinations!")
                print(f"[WebRTC-ERROR] This suggests audio data is corrupted in the pipeline")
            
            # Sample some values to check
            sample_indices = [0, total//4, total//2, 3*total//4, total-1]
            sample_values = [audio_int16[i] for i in sample_indices]
            print(f"[WebRTC-DEBUG] Sample values at key positions: {sample_values}")
            
            # Write to WAV buffer
            wav_bytes = io.BytesIO()
            sf.write(wav_bytes, audio_int16, target_rate, format='WAV', subtype='PCM_16')
            wav_bytes.seek(0)
            
            wav_size = wav_bytes.getbuffer().nbytes
            print(f"[WebRTC-DEBUG] WAV file size: {wav_size} bytes")
            
            # DEBUGGING: Save audio to file for inspection
            import time
            debug_filename = f"debug_audio_{int(time.time())}.wav"
            try:
                with open(debug_filename, 'wb') as f:
                    f.write(wav_bytes.getvalue())
                print(f"[WebRTC-DEBUG] Saved audio to {debug_filename} for debugging")
            except Exception as e:
                print(f"[WebRTC-DEBUG] Could not save debug file: {e}")
            wav_bytes.seek(0)
            
            # Send to transcription
            filename = 'webrtc_input.wav'
            audio_file = (filename, wav_bytes, 'audio/wav')
            await self.on_complete(audio_file)
            print(f"[WebRTC-DEBUG] Audio sent for transcription!")
            
        except Exception as e:
            print(f"[WebRTC-ERROR] Audio processing failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.sending = False

    async def stop_and_process(self, sample_rate=48000):
        self.sample_rate = sample_rate
        if self.closed:
            return
        self.closed = True
        await self.flush_and_process()

    def set_listening(self, enabled: bool, cooldown: float = 0.0):
        now = self.time.time()
        self.listening = enabled
        # Reset ALL state when changing listening mode
        self.buffers.clear()
        self.frame_count = 0
        self.has_speech = False
        self.last_audio_time = now
        self.speech_volume_sum = 0.0
        self.speech_frame_count = 0
        # Apply cooldown when enabling (to avoid echo from TTS)
        self.cooldown_until = (now + cooldown) if cooldown > 0 else 0.0
        print(f"[WebRTC] Listening set to {enabled}, cooldown_until={self.cooldown_until:.2f}")


def parse_ice_candidate(candict):
    """Helper: converts candict json to RTCIceCandidate"""
    cand_str = candict['candidate']
    parts = cand_str.split()
    if len(parts) >= 8 and parts[0] == 'candidate':
        foundation = parts[1]
        component = int(parts[2])
        protocol = parts[3].lower()
        priority = int(parts[4])
        ip = parts[5]
        port = int(parts[6])
        typ = 'host'
        for i, part in enumerate(parts):
            if part == 'typ' and i + 1 < len(parts):
                typ = parts[i + 1]
                break
        return RTCIceCandidate(
            foundation=foundation,
            component=component, 
            protocol=protocol,
            priority=priority,
            ip=ip,
            port=port,
            type=typ,
            sdpMid=candict.get('sdpMid'),
            sdpMLineIndex=candict.get('sdpMLineIndex')
        )
    return None