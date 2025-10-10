// Grabbing references to the buttons and elements
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusEl = document.getElementById('status');
const userTranscriptEl = document.getElementById('userTranscript');
const aiTranscriptEl = document.getElementById('aiTranscript');
// Used to set AI transcript
const aiAudioEl = document.getElementById('aiAudio');

let peerConnection = null;
let dataChannel = null;
let audioStream = null;
let currentAIResponse = '';
let isStreaming = false;
let sessionId = null;
let summaryInProgress = false; // Prevent duplicate summary attempts
let summaryIntroComplete = false; // Track if AI finished intro before summary

// Generate unique session ID
function generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

// Save message to database
async function saveMessageToDatabase(role, content) {
    if (!sessionId || !content) return;
    try {
        //  [API CALL] save user or assistant message to backend
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

// ==> Just shows us the connection status in UI
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
// Update Transcripts
// ==========================================
// === > Below code functionalities used for our Transcript updation in our screen
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

function updateStreamingAITranscript(text) {
    if (aiTranscriptEl.classList.contains('empty')) {
        aiTranscriptEl.classList.remove('empty');
        aiTranscriptEl.textContent = '';
    }
    const lines = aiTranscriptEl.textContent.split('\n');
    if (isStreaming && lines.length > 0 && lines[lines.length - 1].startsWith('Ishmael:')) {
        lines[lines.length - 1] = text;
    } else if (aiTranscriptEl.textContent && !aiTranscriptEl.textContent.endsWith('\n')) {
        lines.push(text);
    } else {
        lines[lines.length - 1] = text;
    }
    aiTranscriptEl.textContent = lines.join('\n');
    aiTranscriptEl.scrollTop = aiTranscriptEl.scrollHeight;
}

// ==========================================
// Start Conversation
// ==========================================
// ==> Starting our conversation with AI
async function startConversation() {
    try {
        startBtn.disabled = true;
        sessionId = generateSessionId();
        console.log('🆔 Session ID:', sessionId);
        updateStatus('Connecting to Mahindra assistant...', 'info');

        // 1. Request ephemeral token from our backend
        // [API CALL] Get OpenAI ephemeral session key from backend
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
// Handle Function Calls
// ==========================================
async function handleFunctionCall(functionName, args, callId) {
    console.log(`🔧 Function call: ${functionName}`, args, 'Call ID:', callId);
    
    if (functionName === 'generate_conversation_summary') {
        // Prevent duplicate calls
        if (summaryInProgress) {
            console.log('⏳ Summary already in progress, skipping...');
            return {status: 'in_progress'};
        }
        
        try {
            summaryInProgress = true;
            summaryIntroComplete = false;
            
            // Validate session has enough data
            if (!sessionId) {
                console.warn('⚠️ No session ID available');
                updateAITranscript('Ishmael: We need to have a conversation first before I can generate a summary. Please tell me about your vehicle requirements!');
                updateStatus('Ready', 'info');
                summaryInProgress = false;
                return {status: 'no_session'};
            }
            
            // Show loading indicator
            updateStatus('Generating summary...', 'warning');
            console.log('📊 Calling summary API for session:', sessionId);
            
            // Call backend API to generate summary
            // [API CALL] Request conversation summary from backend
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
                
                // Send function response back to OpenAI so it can speak about it
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
                    
                    // Trigger AI to respond
                    dataChannel.send(JSON.stringify({type: 'response.create'}));
                }
                
                // Display formatted summary after AI speaks (give it time)
                setTimeout(() => {
                    updateAITranscript(result.formatted_summary);
                    saveMessageToDatabase('assistant', result.formatted_summary);
                    
                    console.log('📝 Summary displayed');
                    updateStatus('Connected! How can I help you?', 'success');
                    summaryInProgress = false;
                }, 3000); // Wait 3 seconds for AI to speak
                
                return result;
            } else if (result.status === 'error' && result.message && result.message.includes('No messages found')) {
                // Not enough conversation data yet
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
            
            // Provide a helpful message instead of generic error
            updateAITranscript('Ishmael: I\'d be happy to provide a summary once we\'ve had a proper conversation! Please tell me about your vehicle requirements - budget, usage, preferences - and I\'ll give you personalized recommendations.');
            
            return {error: error.message};
        }
    }
    
    // Handle other function calls (recommendations, analysis, etc.)
    if (functionName === 'analyze_user_needs' || functionName === 'get_user_recommendations') {
        console.log(`📊 ${functionName} called - processing...`);
        // These can be handled similarly if needed
        return {status: 'acknowledged'};
    }
}

// ==========================================
// Handle Data Channel Messages from OpenAI
// ==========================================
// == AI Transcript and User Transcript == 
function handleDataChannelMessage(msg) {
    const type = msg.type;
    
    // Log ALL events for debugging (can be removed later)
    if (type && !type.includes('audio') && !type.includes('delta')) {
        console.log('📨 Event:', type, msg);
    }

    // User speech transcription
    if (type === 'conversation.item.input_audio_transcription.completed') {
        const transcript = msg.transcript || '';
        updateUserTranscript(`You: ${transcript}`);
        // Save user message to database
        saveMessageToDatabase('user', transcript);
        
        // FALLBACK: Check if user is asking for summary/likings/preferences
        // If OpenAI doesn't call the function, we trigger it ourselves
        const lowerTranscript = transcript.toLowerCase();
        const summaryKeywords = [
            'summary', 'summarize', 'recap', 'what did we discuss',
            'my likings', 'my liking', 'my preferences', 'my preference',
            'what i like', 'what do i like', 'my interests', 'my interest',
            'my requirements', 'my requirement', 'what i want', 'my needs'
        ];
        if (summaryKeywords.some(keyword => lowerTranscript.includes(keyword)) && !summaryInProgress) {
            console.log('🚨 Summary keyword detected in user speech:', transcript);
            console.log('⏳ Waiting 2 seconds to see if OpenAI calls function...');
            setTimeout(() => {
                if (!summaryInProgress) {
                    console.log('🔄 OpenAI didn\'t call function, triggering manually...');
                    handleFunctionCall('generate_conversation_summary', {session_id: sessionId}, null);
                }
            }, 2000);
        }
    }

    // Function/Tool call events - Multiple possible formats
    // Format 1: response.function_call_arguments.done
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
    
    // Format 2: response.output_item.done with function_call
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
    
    // Format 3: conversation.item.created with function_call
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
        isStreaming = true;
    }

    // AI audio transcript delta (streaming in real-time)
    if (type === 'response.audio_transcript.delta') {
        // Don't suppress - let AI speak naturally
        
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
        // Let AI speak naturally about the summary
        
        const transcript = msg.transcript || currentAIResponse;
        
        // Finalize the transcript
        if (transcript) {
            updateStreamingAITranscript(`Ishmael: ${transcript}`);
            // Save AI message to database
            saveMessageToDatabase('assistant', transcript);
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