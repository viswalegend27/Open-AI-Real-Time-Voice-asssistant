const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusEl = document.getElementById('status');
// Used to set User transcript
const userTranscriptEl = document.getElementById('userTranscript');
const aiTranscriptEl = document.getElementById('aiTranscript');
// Used to set AI transcript audio element
const aiAudioEl = document.getElementById('aiAudio');

let peerConnection = null;
let dataChannel = null;
let audioStream = null;
let currentAIResponse = '';
let isStreaming = false;
let sessionId = null;
let summaryInProgress = false; // Prevent duplicate summary attempts
let summaryIntroComplete = false; // Track if AI finished intro before summary

// -----------------------
// Streaming transcript state (new robust approach)
// -----------------------
// committedTranscript: everything already finalized (one string, may contain newlines)
// streamingLine: the single in-progress line (will be replaced repeatedly)
let committedTranscript = '';
let streamingLine = '';

// -----------------------
// Generate unique session ID
// -----------------------
function generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

// -----------------------
// Save message to database
// -----------------------
async function saveMessageToDatabase(role, content) {
    if (!sessionId || !content) return;
    try {
        //  [API CALL] save user or assistant message to backend
        // Handled by save_conversation() in views.py
        await fetch('/api/conversation', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({session_id: sessionId, role, content })
        });
        console.log(`💾 Saved ${role} message to database`);
    } catch (e) {
        console.error('Failed to save message:', e);
    }
}

// ==========================================
// Status Update
// ==========================================
function updateStatus(message, type = 'info') {
    // Add icon prefix based on type
    const iconMap = { success: '✅', error: '❌', warning: '⏳', info: '🚗' };
    statusEl.textContent = `${iconMap[type] || iconMap.info} ${message}`;
    statusEl.className = 'status';
    if (type === 'error') statusEl.classList.add('status-error');
    else if (type === 'success') statusEl.classList.add('status-success');
    else if (type === 'warning') statusEl.classList.add('status-warning');
}

// ==========================================
// Update Transcripts (user + AI static)
// ==========================================
function updateUserTranscript(text) {
    if (userTranscriptEl.classList.contains('empty')) {
        userTranscriptEl.classList.remove('empty');
        userTranscriptEl.textContent = '';
    }
    userTranscriptEl.textContent += `${text}\n`;
    userTranscriptEl.scrollTop = userTranscriptEl.scrollHeight;
}

function updateAITranscript(text) {
    if (aiTranscriptEl.classList.contains('empty')) {
        aiTranscriptEl.classList.remove('empty');
        aiTranscriptEl.textContent = '';
    }
    aiTranscriptEl.textContent += `${text}\n`;
    aiTranscriptEl.scrollTop = aiTranscriptEl.scrollHeight;
}

// ==========================================
// New streaming helpers (robust single-line update)
// ==========================================

// startStreamingResponse(prefix)
//   NOTE: Call this when an AI response starts (response.created).
//   prefix: typically "Ishmael: "
function startStreamingResponse(prefix = 'Ishmael: ') {
    // If aiTranscript still has the placeholder intro (class 'empty'), do NOT treat it as committed text.
    const aiEl = document.getElementById('aiTranscript');
    if (aiEl && aiEl.classList.contains('empty')) {
        // Clear the placeholder and start with empty committedTranscript
        committedTranscript = '';
        aiEl.classList.remove('empty');
        aiEl.textContent = ''; // remove the intro text from DOM
    } else {
        // No intro placeholder — preserve existing committed transcript (trim trailing newlines)
        committedTranscript = (aiEl ? aiEl.textContent : '') .replace(/\n+$/, '');
    }
    streamingLine = prefix; // initialize in-progress line
    // Render initial state (committed + streaming)
    aiTranscriptEl.classList.remove('empty');
    aiTranscriptEl.textContent = (committedTranscript ? committedTranscript + '\n' : '') + streamingLine;
    aiTranscriptEl.scrollTop = aiTranscriptEl.scrollHeight;
    isStreaming = true;
}

// updateStreamingAITranscript(text)
//   NOTE: Call this for each delta update. text should be the full in-progress line
//   e.g. "Ishmael: Hello, I can help you with..."
function updateStreamingAITranscript(text) {
    streamingLine = text;

    // Render only one in-progress line while keeping committed content intact
    if (committedTranscript) {
        aiTranscriptEl.textContent = committedTranscript + '\n' + streamingLine;
    } else {
        aiTranscriptEl.textContent = streamingLine;
    }
    aiTranscriptEl.scrollTop = aiTranscriptEl.scrollHeight;

    // DEBUG: helpful console trace while testing
    // DEBUG: console.debug('updateStreamingAITranscript → streamingLine length:', streamingLine.length);
}

// finalizeStreamingResponse(finalText)
//   NOTE: Call this when the AI has finished speaking (response.audio_transcript.done).
//   finalText: the finalized transcript (prefer msg.transcript, fallback to streamingLine)
    function finalizeStreamingResponse(finalText) {
        // Skip if no meaningful final text
        if (!finalText || !finalText.trim() || finalText.trim() === 'Ishmael:') {
            console.debug('⚠️ Skipping empty finalizeStreamingResponse');
            return;
        }

        const lineToAppend = finalText.trim();

        // Prevent duplicate consecutive identical lines
        const lastLine = committedTranscript.split('\n').pop().trim();
        if (lastLine === lineToAppend) {
            console.debug('⚠️ Skipping duplicate finalizeStreamingResponse');
            return;
        }

        // Append finalized line to committedTranscript
        committedTranscript = (committedTranscript ? committedTranscript + '\n' : '') + lineToAppend;

        // Render committed text (no extra empty line if not needed)
        aiTranscriptEl.textContent = committedTranscript.trim() + '\n';
        aiTranscriptEl.scrollTop = aiTranscriptEl.scrollHeight;

        // Reset streaming line
        streamingLine = '';
        isStreaming = false;
    }

// ==========================================
// Start Conversation
// ==========================================
async function startConversation() {
    try {
        // Guard: prevent duplicate starts if already connected
        if (peerConnection && dataChannel) {
            console.warn('Already connected — ignoring startConversation call');
            return;
        }

        startBtn.disabled = true;
        sessionId = generateSessionId();
        console.log('🆔 Session ID:', sessionId);
        updateStatus('Connecting to Mahindra assistant...', 'info');

        // 1. Request ephemeral token from our backend
        const response = await fetch('/api/session');
        if (!response.ok) {
            throw new Error(`Failed to get session: ${response.status}`);
        }

        // 2. Store the session key (ephemeral client secret) from the backend's response
        const data = await response.json();
        const EPHEMERAL_KEY = data.client_secret.value;

        updateStatus('Preparing consultation session...', 'info');

        // 3. Create RTCPeerConnection
        peerConnection = new RTCPeerConnection();

        // 4. Set up audio element for receiving AI voice
        const audioEl = aiAudioEl;
        audioEl.autoplay = true;

        // 5. On receiving audio track from OpenAI, play it via the audio element
        peerConnection.ontrack = (event) => {
            console.log('Received audio track from OpenAI');
            audioEl.srcObject = event.streams[0];
        };

        // 6. Add local microphone audio track (user's voice) to WebRTC
        updateStatus('Requesting microphone access...', 'warning');
        audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const audioTrack = audioStream.getAudioTracks()[0];
        peerConnection.addTrack(audioTrack);
        console.log('Added local audio track');

        updateStatus('Connecting to Ishmael...', 'info');

        // 7. Set up data channel for events (text, transcript, function calls)
        dataChannel = peerConnection.createDataChannel('oai-events');

        dataChannel.addEventListener('open', () => {
            console.log('Data channel opened - consultation ready');
            updateStatus('Connected! How can I help you today?', 'success');
            stopBtn.disabled = false;
        });

        // 8. Data channel: handle messages (e.g. transcript, AI events)
        dataChannel.addEventListener('message', (event) => {
            try {
                const msg = JSON.parse(event.data);
                // Minimal noise: only log non-audio events for clarity
                if (msg.type && !msg.type.includes('audio') && !msg.type.includes('delta')) {
                    console.log('Data channel message:', msg);
                }
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

        // 9. Create and set local offer (start WebRTC negotiation)
        const offer = await peerConnection.createOffer();
        await peerConnection.setLocalDescription(offer);

        // 10. Send offer (SDP) to OpenAI Realtime API and get the answer
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

        // 11. Set remote description (complete WebRTC connection)
        const answerSdp = await sdpResponse.text();
        const answer = {
            type: 'answer',
            sdp: answerSdp,
        };
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
        try { dataChannel.close(); } catch (e) { /* ignore */ }
        dataChannel = null;
    }

    if (peerConnection) {
        try { peerConnection.close(); } catch (e) { /* ignore */ }
        peerConnection = null;
    }

    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
        audioStream = null;
    }

    // Reset streaming transcript state when user explicitly stops
    committedTranscript = aiTranscriptEl.textContent.replace(/\n+$/, '') || '';
    streamingLine = '';
    isStreaming = false;

    startBtn.disabled = false;
    stopBtn.disabled = true;
    updateStatus('Ready to help you find your perfect Mahindra!', 'info');
}

// ==========================================
// Handle Function Calls
// ==========================================
async function handleFunctionCall(functionName, args, callId) {
    console.log(`🔧 Function call: ${functionName}`, args, 'Call ID:', callId);

    if (functionName === 'generate_conversation_summary') {
        if (summaryInProgress) {
            console.log('⏳ Summary already in progress, skipping...');
            return {status: 'in_progress'};
        }

        try {
            summaryInProgress = true;
            summaryIntroComplete = false;

            if (!sessionId) {
                console.warn('⚠️ No session ID available');
                updateAITranscript('Ishmael: We need to have a conversation first before I can generate a summary. Please tell me about your vehicle requirements!');
                updateStatus('Ready', 'info');
                summaryInProgress = false;
                return {status: 'no_session'};
            }

            updateStatus('Generating summary...', 'warning');
            console.log('📊 Calling summary API for session:', sessionId);

            const response = await fetch('/api/generate-summary', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({session_id: sessionId})
            });

            console.log('📡 Summary API response status:', response.status);
            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ API Error:', errorText);
                throw new Error(`API returned ${response.status}`);
            }

            const result = await response.json();
            console.log('📦 Summary result:', result);

            if (result.status === 'success' && result.formatted_summary) {
                console.log('✅ Summary generated successfully');

                // If there's an open dataChannel and callId, tell OpenAI we've handled the function
                if (dataChannel && dataChannel.readyState === 'open' && callId) {
                    const functionResponse = {
                        type: 'conversation.item.create',
                        item: {
                            type: 'function_call_output',
                            call_id: callId,
                            output: JSON.stringify({
                                status: 'success',
                                message: 'Summary generated successfully. Here\'s what we discussed:',
                                summary_text: result.summary.summary || 'Summary generated'
                            })
                        }
                    };

                    console.log('📤 Sending function response to OpenAI:', functionResponse);
                    dataChannel.send(JSON.stringify(functionResponse));
                    // Trigger AI to speak about it
                    dataChannel.send(JSON.stringify({type: 'response.create'}));
                }

                // Wait for AI to speak via realtime audio events, then show formatted summary
                // NOTE: previously you used a fixed timeout (3s). Avoid racing with audio; display
                // the formatted summary after a short delay but it's safe to display immediately too.
                setTimeout(() => {
                    updateAITranscript(result.formatted_summary);
                    saveMessageToDatabase('assistant', result.formatted_summary);
                    console.log('📝 Summary displayed');
                    updateStatus('Connected! How can I help you?', 'success');
                    summaryInProgress = false;
                }, 3000);

                return result;
            } else if (result.status === 'error' && result.message && result.message.includes('No messages found')) {
                console.warn('⚠️ Not enough conversation data');
                updateAITranscript('Ishmael: We just started our conversation! Let\'s discuss your vehicle needs first, and then I\'ll provide a comprehensive summary.');
                updateStatus('Connected! How can I help you?', 'success');
                summaryInProgress = false;
                return {status: 'insufficient_data'};
            } else {
                summaryInProgress = false;
                throw new Error(result.message || 'Failed to generate summary');
            }
        } catch (error) {
            console.error('❌ Summary generation error:', error);
            updateStatus('Connected! How can I help you?', 'success');
            summaryInProgress = false;
            updateAITranscript('Ishmael: I\'d be happy to provide a summary once we\'ve had a proper conversation! Please tell me about your vehicle requirements - budget, usage, preferences - and I\'ll give you personalized recommendations.');
            return {error: error.message};
        }
    }

    // Handle other function calls (recommendations, analysis, etc.)
    if (functionName === 'analyze_user_needs' || functionName === 'get_user_recommendations') {
        console.log(`📊 ${functionName} called - processing...`);
        return {status: 'acknowledged'};
    }
}

// ==========================================
// Handle Data Channel Messages from OpenAI
// ==========================================
function handleDataChannelMessage(msg) {
    const type = msg.type;

    // Minimal logging for clarity; add more if debugging
    if (type && !type.includes('audio') && !type.includes('delta')) {
        console.log('📨 Event:', type, msg);
    }

    // User speech transcription
    if (type === 'conversation.item.input_audio_transcription.completed') {
        const transcript = msg.transcript || '';
        updateUserTranscript(`You: ${transcript}`);
        saveMessageToDatabase('user', transcript);

        const lowerTranscript = transcript.toLowerCase();

        // Listen for end-conversation commands
        const endKeywords = [
            'end conversation',
            'stop conversation',
            'finish conversation',
            'close conversation',
            'exit conversation',
            'terminate conversation',
            'goodbye',
            'end chat',
            'disconnect'
        ];
        if (endKeywords.some(keyword => lowerTranscript.includes(keyword))) {
            console.log('🛑 End conversation phrase detected in user speech:', transcript);
            updateUserTranscript('You ended the conversation.');
            updateStatus('Conversation ended by user.', 'warning');
            stopConversation();
            return;
        }

        // FALLBACK: trigger summary if user asked verbally and OpenAI didn't call the function
        const summaryKeywords = [
            'summary', 'summarize', 'recap', 'what did we discuss',
            'my likings', 'my liking', 'my preferences', 'my preference',
            'what i like', 'what do i like', 'my interests', 'my interest',
            'my requirements', 'my requirement', 'what i want', 'my needs'
        ];
        if (summaryKeywords.some(keyword => lowerTranscript.includes(keyword)) && !summaryInProgress) {
            console.log('🚨 Summary keyword detected in user speech:', transcript);
            // Give OpenAI a short window to call the function; if not, trigger ourselves
            setTimeout(() => {
                if (!summaryInProgress) {
                    console.log('🔄 OpenAI didn\'t call function, triggering manually...');
                    handleFunctionCall('generate_conversation_summary', {session_id: sessionId}, null);
                }
            }, 2000);
        }
    }

    // Function/Tool call detection (multiple possible formats)
    if (type === 'response.function_call_arguments.done') {
        const functionName = msg.name;
        const args = JSON.parse(msg.arguments || '{}');
        const callId = msg.call_id || msg.item_id || null;

        console.log('🎯 Function call detected (format 1):', functionName, 'ID:', callId);
        handleFunctionCall(functionName, args, callId);

        isStreaming = false;
        currentAIResponse = '';
        return;
    }

    if (type === 'response.output_item.done' && msg.item?.type === 'function_call') {
        const functionName = msg.item.name;
        const args = JSON.parse(msg.item.arguments || '{}');
        const callId = msg.item.call_id || msg.item.id || null;

        console.log('🎯 Function call detected (format 2):', functionName, 'ID:', callId);
        handleFunctionCall(functionName, args, callId);

        isStreaming = false;
        currentAIResponse = '';
        return;
    }

    if (type === 'conversation.item.created' && msg.item?.type === 'function_call') {
        const functionName = msg.item.name;
        const args = JSON.parse(msg.item.arguments || '{}');
        const callId = msg.item.call_id || msg.item.id || null;

        console.log('🎯 Function call detected (format 3):', functionName, 'ID:', callId);
        handleFunctionCall(functionName, args, callId);

        isStreaming = false;
        currentAIResponse = '';
        return;
    }

    // AI response started - clear previous response buffer and mark as streaming
    if (type === 'response.created') {
        currentAIResponse = '';
        // Start our streaming UI state
        startStreamingResponse('Ishmael: ');
    }

    // AI audio transcript delta (streaming)
    if (type === 'response.audio_transcript.delta') {
        const delta = msg.delta || '';
        currentAIResponse += delta;
    
        const aiEl = document.getElementById('aiTranscript');
    
        // If the intro placeholder is still present, clear both DOM and committedTranscript
        if (aiEl && aiEl.classList.contains('empty')) {
            // Remove intro from DOM
            aiEl.classList.remove('empty');
            aiEl.textContent = '';
            // VERY IMPORTANT: also reset committedTranscript so intro isn't re-rendered
            committedTranscript = '';
            streamingLine = ''; // reset streamingLine so startStreamingResponse can initialize cleanly if used
        }
    
        // If streaming hasn't been initialized, do so (defensive)
        if (!isStreaming) {
            startStreamingResponse('Ishmael: ');
        }
    
        // Update the single in-progress line
        updateStreamingAITranscript(`Ishmael: ${currentAIResponse}`);
    }    

    // AI audio transcript complete - finalize and stop streaming mode
    if (type === 'response.audio_transcript.done') {
        const transcriptRaw = msg.transcript || currentAIResponse;
        const transcript = (transcriptRaw && transcriptRaw.trim()) ? transcriptRaw.trim() : '';
    
        // 🟢 Skip if empty (avoids "Ishmael:" blanks)
        if (!transcript) {
            console.debug('⚠️ Skipping empty transcript done event');
            currentAIResponse = '';
            isStreaming = false;
            return;
        }
    
        // Finalize properly
        finalizeStreamingResponse(`Ishmael: ${transcript}`);
        saveMessageToDatabase('assistant', `Ishmael: ${transcript}`);
    
        currentAIResponse = '';
        isStreaming = false;
    }
    

    // Session events (informational)
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