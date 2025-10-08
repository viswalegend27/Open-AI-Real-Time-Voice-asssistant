const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusEl = document.getElementById('status');
const userTranscriptEl = document.getElementById('userTranscript');
const aiTranscriptEl = document.getElementById('aiTranscript');
// 1 Getting our audio element responsible for recieving
const aiAudioEl = document.getElementById('aiAudio');

let peerConnection = null;
let dataChannel = null;
let audioStream = null;
let currentAIResponse = '';
let isStreaming = false;

// ==========================================
// Status Update
// ==========================================
function updateStatus(message, type = 'info') {
    // Add icon prefix based on type
    let icon = '🚗';
    if (type === 'success') icon = '✅';
    else if (type === 'error') icon = '❌';
    else if (type === 'warning') icon = '⏳';
    
    statusEl.textContent = `${icon} ${message}`;
    statusEl.className = 'status';
    
    if (type === 'error') {
        statusEl.classList.add('status-error');
    } else if (type === 'success') {
        statusEl.classList.add('status-success');
    } else if (type === 'warning') {
        statusEl.classList.add('status-warning');
    }
}

// ==========================================
// Update Transcripts
// ==========================================
function updateUserTranscript(text) {
    if (userTranscriptEl.classList.contains('empty')) {
        userTranscriptEl.classList.remove('empty');
        userTranscriptEl.textContent = '';
    }
    userTranscriptEl.textContent += text + '\n';
    userTranscriptEl.scrollTop = userTranscriptEl.scrollHeight;
}

function updateAITranscript(text) {
    if (aiTranscriptEl.classList.contains('empty')) {
        aiTranscriptEl.classList.remove('empty');
        aiTranscriptEl.textContent = '';
    }
    aiTranscriptEl.textContent += text + '\n';
    aiTranscriptEl.scrollTop = aiTranscriptEl.scrollHeight;
}

function updateStreamingAITranscript(text) {
    // Update only the currently streaming response
    if (aiTranscriptEl.classList.contains('empty')) {
        aiTranscriptEl.classList.remove('empty');
        aiTranscriptEl.textContent = '';
    }
    
    const lines = aiTranscriptEl.textContent.split('\n');
    
    // If we're streaming, replace the last line; otherwise append new line
    if (isStreaming && lines.length > 0 && lines[lines.length - 1].startsWith('Ishmael:')) {
        lines[lines.length - 1] = text;
    } else {
        // Append as new line
        if (aiTranscriptEl.textContent && !aiTranscriptEl.textContent.endsWith('\n')) {
            lines.push(text);
        } else {
            lines[lines.length - 1] = text;
        }
    }
    
    aiTranscriptEl.textContent = lines.join('\n');
    aiTranscriptEl.scrollTop = aiTranscriptEl.scrollHeight;
}

// ==========================================
// Start Conversation
// ==========================================
async function startConversation() {
    try {
        startBtn.disabled = true;
        updateStatus('Connecting to Mahindra assistant...', 'info');

        // 1. Request ephemeral token from our backend
        // 4. Response object is set to recieve payload
        const response = await fetch('/api/session');
        if (!response.ok) {
            throw new Error(`Failed to get session: ${response.status}`);
        }
        
        // Storing the response as it is in original format
        const data = await response.json();
        // 6. Session key recieved
        const EPHEMERAL_KEY = data.client_secret.value;

        updateStatus('Preparing consultation session...', 'info');

        // 2. Create RTCPeerConnection
        peerConnection = new RTCPeerConnection();

        // 3. Set up audio element for receiving AI voice
        const audioEl = aiAudioEl;
        audioEl.autoplay = true;

        peerConnection.ontrack = (event) => {
            console.log('Received audio track from OpenAI');
            // 2 Comming audio stream over WebRTC and assigned to this object
            audioEl.srcObject = event.streams[0];
        };

        // 4. Add local microphone audio track
        updateStatus('Requesting microphone access...', 'warning');
        // Using browser's getUserMedia API to capture User's Audio
        audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        const audioTrack = audioStream.getAudioTracks()[0];
        peerConnection.addTrack(audioTrack);
        console.log('Added local audio track');

        updateStatus('Connecting to Ishmael...', 'info');

        // 5. Set up data channel for events
        dataChannel = peerConnection.createDataChannel('oai-events');
        
        dataChannel.addEventListener('open', () => {
            console.log('Data channel opened - consultation ready');
            updateStatus('Connected! How can I help you today?', 'success');
            stopBtn.disabled = false;
        });

        dataChannel.addEventListener('message', (event) => {
            try {
                const msg = JSON.parse(event.data);
                console.log('Data channel message:', msg);
                handleDataChannelMessage(msg);
            } catch (e) {
                console.error('Error parsing data channel message:', e);
            }
        });

        dataChannel.addEventListener('close', () => {
            console.log('Data channel closed - consultation ended');
            updateStatus('Consultation ended', 'warning');
        });

        dataChannel.addEventListener('error', (error) => {
            console.error('Data channel error:', error);
            updateStatus('Connection error - please try again', 'error');
        });

        // 6. Create and set local offer
        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);

        // 7. Send offer to OpenAI Realtime API
        const baseUrl = 'https://api.openai.com/v1/realtime';
        const model = 'gpt-4o-realtime-preview-2024-12-17';
        // 7 Response recieved is directly sent to Open_AI
        const sdpResponse = await fetch(`${baseUrl}?model=${model}`, {
            method: 'POST',
            body: offer.sdp,
            headers: {
                // Authorization token
                'Authorization': `Bearer ${EPHEMERAL_KEY}`,
                'Content-Type': 'application/sdp'
            },
        });

        if (!sdpResponse.ok) {
            throw new Error(`OpenAI SDP exchange failed: ${sdpResponse.status}`);
        }

        const answerSdp = await sdpResponse.text();
        const answer = {
            type: 'answer',
            sdp: answerSdp,
        };

        // 8. Set remote description
        await peerConnection.setRemoteDescription(answer);
        console.log('WebRTC connection established - Mahindra sales consultant ready');

    } catch (error) {
        console.error('Error starting conversation:', error);
        updateStatus(`Error: ${error.message}`, 'error');
        startBtn.disabled = false;
        stopConversation();
    }
}

// ==========================================
// Stop Conversation
// ==========================================
function stopConversation() {
    if (dataChannel) {
        dataChannel.close();
        dataChannel = null;
    }

    if (peerConnection) {
        peerConnection.close();
        peerConnection = null;
    }

    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
        audioStream = null;
    }

    startBtn.disabled = false;
    stopBtn.disabled = true;
    updateStatus('Ready to help you find your perfect Mahindra!', 'info');
}

// ==========================================
// Handle Data Channel Messages from OpenAI
// ==========================================
// == AI Transcript and User Transcript == 
function handleDataChannelMessage(msg) {
    const type = msg.type;

    // User speech transcription
    if (type === 'conversation.item.input_audio_transcription.completed') {
        const transcript = msg.transcript || '';
        updateUserTranscript(`You: ${transcript}`);
    }

    // AI response started - clear previous response buffer and mark as streaming
    if (type === 'response.created') {
        currentAIResponse = '';
        isStreaming = true;
    }

    // AI audio transcript delta (streaming in real-time)
    if (type === 'response.audio_transcript.delta') {
        const delta = msg.delta || '';
        currentAIResponse += delta;
        
        // Clear placeholder on first delta
        if (aiTranscriptEl.classList.contains('empty')) {
            aiTranscriptEl.classList.remove('empty');
            aiTranscriptEl.textContent = '';
        }
        
        // Update the current streaming line with accumulated response
        updateStreamingAITranscript(`Ishmael: ${currentAIResponse}`);
    }

    // AI audio transcript complete - finalize and stop streaming mode
    if (type === 'response.audio_transcript.done') {
        const transcript = msg.transcript || currentAIResponse;
        
        // Finalize the transcript
        if (transcript) {
            updateStreamingAITranscript(`Ishmael: ${transcript}`);
        }
        
        // Add newline to separate from next response
        aiTranscriptEl.textContent += '\n';
        
        // Reset streaming state
        currentAIResponse = '';
        isStreaming = false;
    }

    // Session updates
    if (type === 'session.created' || type === 'session.updated') {
        console.log('Session event:', msg);
    }

    // Error handling
    if (type === 'error') {
        console.error('OpenAI error:', msg);
        updateStatus(`OpenAI error: ${msg.error?.message || 'Unknown'}`, 'error');
    }
}

// ==========================================
// Event Listeners
// ==========================================
startBtn.addEventListener('click', startConversation);
stopBtn.addEventListener('click', stopConversation);

// Handle page unload
window.addEventListener('beforeunload', () => {
    stopConversation();
});

console.log('🚗 Ishmael - Mahindra Sales Assistant initialized and ready');
