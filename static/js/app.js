// ==========================================
// Ishmael - Mahindra Sales Assistant
// Your trusted automotive sales consultant
// ==========================================

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusEl = document.getElementById('status');
const userTranscriptEl = document.getElementById('userTranscript');
const aiTranscriptEl = document.getElementById('aiTranscript');
const aiAudioEl = document.getElementById('aiAudio');

let peerConnection = null;
let dataChannel = null;
let audioStream = null;

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

// ==========================================
// Start Conversation
// ==========================================
async function startConversation() {
    try {
        startBtn.disabled = true;
        updateStatus('Connecting to Mahindra assistant...', 'info');

        // 1. Request ephemeral token from our backend
        const response = await fetch('/api/session');
        if (!response.ok) {
            throw new Error(`Failed to get session: ${response.status}`);
        }
        
        const data = await response.json();
        const EPHEMERAL_KEY = data.client_secret.value;

        updateStatus('Preparing consultation session...', 'info');

        // 2. Create RTCPeerConnection
        peerConnection = new RTCPeerConnection();

        // 3. Set up audio element for receiving AI voice
        const audioEl = aiAudioEl;
        audioEl.autoplay = true;

        peerConnection.ontrack = (event) => {
            console.log('Received audio track from OpenAI');
            audioEl.srcObject = event.streams[0];
        };

        // 4. Add local microphone audio track
        updateStatus('Requesting microphone access...', 'warning');
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
        const sdpResponse = await fetch(`${baseUrl}?model=${model}`, {
            method: 'POST',
            body: offer.sdp,
            headers: {
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
function handleDataChannelMessage(msg) {
    const type = msg.type;

    // User speech transcription
    if (type === 'conversation.item.input_audio_transcription.completed') {
        const transcript = msg.transcript || '';
        updateUserTranscript(`You: ${transcript}`);
    }

    // AI response text
    if (type === 'response.audio_transcript.done') {
        const transcript = msg.transcript || '';
        updateAITranscript(`Ishmael: ${transcript}`);
    }

    // AI response text delta (streaming)
    if (type === 'response.text.delta') {
        const text = msg.delta || '';
        updateAITranscript(text);
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
