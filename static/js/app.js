(function waitForDomAndInit() {
  function initModule() {
    // -------------- DOM Elements --------------
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const statusEl = document.getElementById('status');
    const userTranscriptEl = document.getElementById('userTranscript');
    const aiTranscriptEl = document.getElementById('aiTranscript');
    const aiAudioEl = document.getElementById('aiAudio');
    // --- Constants & Config ---
    const AI_NAME = 'Ishmael';
    const AI_PREFIX = `${AI_NAME}: `;
    const OPENAI_MODEL = 'gpt-4o-realtime-preview-2024-12-17';

    // -------------- App State --------------
    const state = {
      sessionId: null,
      peerConnection: null,
      dataChannel: null,
      audioStream: null,
      isStreaming: false,
      committedTranscript: '',
      streamingLine: '',
      streamingPrefix: AI_PREFIX,
      currentAIResponse: '',
      summaryInProgress: false,
      summaryCallId: null,
      pendingRaf: null,
    };

    // -------------- Utility Helpers --------------
    const log = (...args) => console.log(`${AI_NAME}:`, ...args);
    const warn = (...args) => console.warn(`${AI_NAME}:`, ...args);
    const err = (...args) => console.error(`${AI_NAME}:`, ...args);

    function generateSessionId() {
      return `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
    }
    function safeJson(text, fallback = {}) {
      try { return JSON.parse(text); } catch (_) { return fallback; }
    }

    // -------------- Status & Transcript UI --------------
    const ICONS = { success: '✅', error: '❌', warning: '⏳', info: '🚗' };

    function updateStatus(message, type = 'info') {
      if (!statusEl) return;
      statusEl.textContent = `${ICONS[type] || ICONS.info} ${message}`;
      statusEl.className = 'status';
      statusEl.classList.toggle('status-error', type === 'error');
      statusEl.classList.toggle('status-success', type === 'success');
      statusEl.classList.toggle('status-warning', type === 'warning');
    }
    // -------------- Transcript Reset Utility --------------
    function resetTranscriptFields() {
      if (userTranscriptEl) {
        userTranscriptEl.textContent = '';
        userTranscriptEl.classList.add('empty');
      }
      if (aiTranscriptEl) {
        aiTranscriptEl.textContent = '';
        aiTranscriptEl.classList.add('empty');
      }
      state.committedTranscript = '';
      state.streamingLine = '';
      state.isStreaming = false;
      state.currentAIResponse = '';
    }
    resetTranscriptFields();

    function appendToElement(el, text) {
      if (!el) return;
      if (el.classList.contains('empty')) el.classList.remove('empty');
      el.textContent += `${text}\n`;
      el.scrollTop = el.scrollHeight;
    }
    function setElementText(el, text) {
      if (!el) return;
      if (el.classList.contains('empty')) el.classList.remove('empty');
      el.textContent = text;
      el.scrollTop = el.scrollHeight;
    }
    function updateUserTranscript(text) { appendToElement(userTranscriptEl, text); }
    function updateAITranscript(text) { appendToElement(aiTranscriptEl, text); }

    // Renders AI thinking and speaking in real time
    function scheduleAIRender() {
      if (state.pendingRaf) return;
      state.pendingRaf = requestAnimationFrame(() => {
        state.pendingRaf = null;
        let render = '';
        if (state.committedTranscript)
          render = state.committedTranscript + (state.streamingLine ? `\n${state.streamingPrefix}${state.streamingLine}` : '');
        else
          render = state.streamingLine ? `${state.streamingPrefix}${state.streamingLine}` : '';
        setElementText(aiTranscriptEl, render ? `${render}\n` : '');
      });
    }

    // -------------- Transcript Streaming & Finalization --------------
    function startStreamingResponse(prefix = 'Ishmael: ') {
      state.streamingPrefix = prefix;
      if (aiTranscriptEl?.classList.contains('empty')) {
        aiTranscriptEl.classList.remove('empty');
        setElementText(aiTranscriptEl, '');
        state.committedTranscript = '';
      } else {
        state.committedTranscript = (aiTranscriptEl?.textContent || '').replace(/\n+$/, '');
      }
      state.streamingLine = '';
      state.currentAIResponse = '';
      state.isStreaming = true;
      scheduleAIRender();
    }
    function updateStreamingAITranscript(text) {
      state.streamingLine = text || '';
      scheduleAIRender();
    }
    function finalizeStreamingResponse(finalText) {
      if (!finalText?.trim()) {
        log('Skipping finalize: empty finalText');
        state.isStreaming = false;
        state.currentAIResponse = '';
        state.streamingLine = '';
        return;
      }
      const normalized = finalText.startsWith(state.streamingPrefix)
        ? finalText.slice(state.streamingPrefix.length).trim()
        : finalText.trim();
      if (!normalized) {
        log('Skipping finalize: nothing meaningful after prefix normalization');
        return;
      }
      const lastLine = (state.committedTranscript.split('\n').pop() || '').trim();
      const lineToAppend = `${state.streamingPrefix}${normalized}`;
      if (lastLine === lineToAppend.trim()) {
        log('Skipping duplicate finalizeStreamingResponse');
      } else {
        state.committedTranscript = (state.committedTranscript ? `${state.committedTranscript}\n` : '') + lineToAppend;
        setElementText(aiTranscriptEl, `${state.committedTranscript.trim()}\n`);
      }
      saveMessageToDatabase('assistant', lineToAppend).catch(e => warn('saveMessage failed', e));
      state.streamingLine = '';
      state.currentAIResponse = '';
      state.isStreaming = false;
    }
    const MESSAGE_COOLDOWN = 5000; // 2 seconds
    const lastMessageTimestamps = {};
    // -------------- DB Save (User + Assistant) --------------
    async function saveMessageToDatabase(role, content) {
      if (!state.sessionId || !content) return;
      const now = Date.now();
      const key = state.sessionId + '-' + role;
      if (lastMessageTimestamps[key] && now - lastMessageTimestamps[key] < MESSAGE_COOLDOWN) {
        // Too soon! Prevent another call, optionally show a warning or just silently drop.
        warn('Too soon since last message, skipping save.');
        updateStatus('Please wait a moment before sending another message.', 'warning');
        return;
      }
      lastMessageTimestamps[key] = now;
      try {
        await fetch('/api/conversation', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: state.sessionId, role, content })
        }).then(res => {
          if (!res.ok) return res.text().then(t => { throw new Error(t || res.status); });
          log(`Saved ${role}`);
        });
      } catch (e) {
        err('Failed to save message:', e);
        updateStatus('Unable to save conversation message. Please check your connection.', 'error');
      }
    }
    // -------------- My Toast functionality --------------    
    function showToast(message, timeout = 3500) {
        const toast = document.getElementById('toast-message');
        if (!toast) return;
        toast.textContent = message;
        toast.classList.add('show');
        clearTimeout(window._toastTimeout);
        window._toastTimeout = setTimeout(() => {
          toast.classList.remove('show');
        }, timeout);
    }

    // -------------- Function Call Handler --------------
    async function handleFunctionCall(functionName, args = {}, callId = null) {
      log('Function call:', functionName, args, 'callId:', callId);
      // --- Only handles summary requests ---
      if (functionName === 'generate_conversation_summary') {
        const callSessionId = (args?.session_id && args.session_id !== 'current_conversation') ? args.session_id : state.sessionId;
        if (!callSessionId) {
          updateAITranscript(`${AI_PREFIX}We need to have a conversation first before I can generate a summary. Please tell me about your vehicle requirements!`);
          updateStatus('Ready', 'info');
          return { status: 'no_session' };
        }
        if (state.summaryInProgress && callId && state.summaryCallId === callId) {
          log('Summary already in progress for same call id, skipping...');
          updateStatus('Summary is already being generated, please wait...', 'warning');
          updateAITranscript(`${AI_PREFIX}I'm working on your summary. Please wait a moment!`);
          stopConversation(true);
          return { status: 'in_progress' };
        }
        state.summaryInProgress = true;
        state.summaryCallId = callId || null;
        updateStatus('Generating summary...', 'warning');
        stopConversation(true); // Immediately end session on summary request
        showToast("Conversation has ended");
        try {
          // Trigger backend summary generation
          await fetch('/api/generate-summary', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: callSessionId })
          });
        } catch (error) {
          err('Failed to generate summary:', error);
          updateStatus('Sorry, there was an error generating your summary. Please try again or contact support.', 'error');
          updateAITranscript(`${AI_PREFIX}Sorry, I couldn't generate your summary due to an error.`);
        }
        return { status: 'processing' };
      }
      log('Unknown function call:', functionName);
      return { status: 'unknown_function' };
    }

    // -------------- Introductory Message --------------
    function sendIntroductoryMessage(dataChannel) {
      if (!dataChannel) {
        warn('sendIntroductoryMessage: No data channel instance provided');
        return;
      }
      if (dataChannel.readyState !== 'open') {
        warn('sendIntroductoryMessage: Data channel not ready (state:', dataChannel.readyState, ')');
        return;
      }
      try {
        const introEvent = {
          type: 'conversation.item.create',
          item: {
            type: 'message',
            role: 'user',
            content: [
              {
                type: 'input_text',
                text: 'Hello! Please introduce yourself.'
              }
            ]
          }
        };
    
        dataChannel.send(JSON.stringify(introEvent));
    
        // Only send a response event if backend needs both for a response
        const responseEvent = { type: 'response.create' };
        dataChannel.send(JSON.stringify(responseEvent));
    
        log('Introductory message SENT successfully');
      } catch (error) {
        err('sendIntroductoryMessage: Failed to send introductory message:', error);
      }
    }

    // -------------- Data Channel Messaging --------------
    async function handleDataChannelMessage(rawMsg) {
      const msg = (typeof rawMsg === 'string') ? safeJson(rawMsg) : rawMsg;
      const { type } = msg;
      if (type && !type.includes('audio') && !type.includes('delta')) {
        log('Event:', type, msg);
      }
      if (type === 'conversation.item.input_audio_transcription.completed') {
        const transcript = msg.transcript || '';
        updateUserTranscript(`You: ${transcript}`);
        saveMessageToDatabase('user', transcript).catch(e => warn('save user failed', e));
        return;
      }
      // Handle function call events from assistant
      const isFunctionCall = [
        'response.function_call_arguments.done',
        'response.output_item.done',
        'conversation.item.created'
      ].includes(type) && (msg.item?.type === 'function_call' || msg.name);
      if (isFunctionCall) {
        const functionName = msg.name || msg.item?.name;
        const args = safeJson((msg.arguments || msg.item?.arguments) || '{}');
        const callId = msg.call_id || msg.item_id || msg.item?.call_id || msg.item?.id || null;
        await handleFunctionCall(functionName, args, callId);
        state.isStreaming = false;
        state.currentAIResponse = '';
        return;
      }
      if (type === 'response.created') {
        state.currentAIResponse = '';
        startStreamingResponse(state.streamingPrefix);
        return;
      }
      if (type === 'response.audio_transcript.delta') {
        const delta = msg.delta || '';
        state.currentAIResponse += delta;
        if (!state.isStreaming) startStreamingResponse(state.streamingPrefix);
        updateStreamingAITranscript(state.currentAIResponse);
        return;
      }
      if (type === 'response.audio_transcript.done') {
        const transcriptRaw = msg.transcript || state.currentAIResponse;
        const transcript = transcriptRaw?.trim() || '';
        if (!transcript) {
          log('Empty transcript done, ignoring');
          state.currentAIResponse = '';
          state.isStreaming = false;
          return;
        }
        finalizeStreamingResponse(transcript);
        state.currentAIResponse = '';
        state.isStreaming = false;
        return;
      }
      if (type === 'session.created' || type === 'session.updated') {
        log('Session event:', msg);
        return;
      }
      if (type === 'error') {
        err('OpenAI error:', msg);
        updateStatus(`OpenAI error: ${msg.error?.message || 'Unknown'}`, 'error');
      }
    }

    // -------------- Conversation Start/Stop (WebRTC + OpenAI) --------------
    async function startConversation() {
      resetTranscriptFields();
      if (state.peerConnection || state.dataChannel) {
        warn('Already connected — ignoring startConversation call');
        return;
      }
      try {
        startBtn.disabled = true;
        state.sessionId = generateSessionId();
        log('Session ID:', state.sessionId);
        updateStatus('Connecting to Mahindra assistant...', 'info');
        const sessionResp = await fetch('/api/session'); // session call to get ephemeral key
        if (!sessionResp.ok) throw new Error(`Failed to get session: ${sessionResp.status}`);
        const sessionData = await sessionResp.json();
        const EPHEMERAL_KEY = sessionData?.client_secret?.value;
        if (!EPHEMERAL_KEY) throw new Error('No ephemeral key returned from backend');
        updateStatus('Preparing consultation session...', 'info');
        const pc = new RTCPeerConnection();
        state.peerConnection = pc;
        aiAudioEl.autoplay = true;
        aiAudioEl.playsInline = true;
        aiAudioEl.muted = true;
        pc.ontrack = ev => {
          log('Received audio track from OpenAI');
          if (!aiAudioEl.srcObject) {
            try {
              aiAudioEl.srcObject = ev.streams[0];
              aiAudioEl.addEventListener('playing', function onPlaying() {
                setTimeout(() => { aiAudioEl.muted = false; }, 300);
                aiAudioEl.removeEventListener('playing', onPlaying);
              });
            } catch (error) {
              err('Failed to set audio srcObject', error);
              updateStatus('Could not play received audio stream.', 'error');
            }
          }
        };
        updateStatus('Requesting microphone access...', 'warning');
        try {
          state.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (error) {
          err('Microphone access denied:', error);
          updateStatus('Microphone access denied. Please enable microphone permissions and try again.', 'error');
          startBtn.disabled = false;
          stopConversation();
          return;
        }
        const audioTrack = state.audioStream.getAudioTracks()[0];
        if (!audioTrack) throw new Error('No audio track from microphone');
        pc.addTrack(audioTrack);
        log('Added local audio track');
        updateStatus(`Connecting to ${AI_NAME}...`, 'info');
        const dc = pc.createDataChannel('oai-events');
        state.dataChannel = dc;
        dc.addEventListener('open', () => {
          log('Data channel opened - consultation ready');
          updateStatus('Connected! How can I help you today?', 'success');
          stopBtn.disabled = false;
          
          // Send introductory greeting message
          sendIntroductoryMessage(dc);
        });
        dc.addEventListener('message', (evt) => {
          try { handleDataChannelMessage(evt.data); } catch (e) {
            err('dataChannel message handler error', e);
            updateStatus('An error occurred while handling an AI message.', 'error');
          }
        });
        dc.addEventListener('close', () => {
          log('Data channel closed - consultation ended');
          updateStatus('Consultation ended', 'warning');
        });
        dc.addEventListener('error', (error) => {
          err('Data channel error:', error);
          updateStatus('Connection error - please try again', 'error');
        });
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        const baseUrl = 'https://api.openai.com/v1/realtime';
        const model = OPENAI_MODEL;
        let sdpResponse;
        try {
          sdpResponse = await fetch(`${baseUrl}?model=${model}`, {
            method: 'POST',
            body: offer.sdp,
            headers: {
              'Authorization': `Bearer ${EPHEMERAL_KEY}`,
              'Content-Type': 'application/sdp'
            },
          });
        } catch (error) {
          err('Failed to contact OpenAI realtime API:', error);
          updateStatus('Error contacting the AI service. Check your internet connection.', 'error');
          startBtn.disabled = false;
          stopConversation();
          return;
        }
        if (!sdpResponse.ok) {
          err('OpenAI SDP exchange failed:', sdpResponse.status);
          updateStatus('Error connecting to the AI service: ' + sdpResponse.status, 'error');
          startBtn.disabled = false;
          stopConversation();
          return;
        }
        const answerSdp = await sdpResponse.text();
        await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });
        log('WebRTC connection established - Mahindra sales consultant ready');
      } catch (error) {
        err('Error starting conversation:', error);
        updateStatus(`Error: ${error.message}`, 'error');
        startBtn.disabled = false;
        stopConversation();
      }
    }
    // our conversation stop and cleanup
    function stopConversation(isAuto = false) {
      if (state.dataChannel) {
        try { state.dataChannel.close(); } catch (e) {}
        state.dataChannel = null;
      }
      if (state.peerConnection) {
        try { state.peerConnection.close(); } catch (e) {}
        state.peerConnection = null;
      }
      if (state.audioStream) {
        try { state.audioStream.getTracks().forEach(track => track.stop()); } catch (e) {}
        state.audioStream = null;
      }
      if (aiAudioEl) {
        try { aiAudioEl.srcObject = null; aiAudioEl.muted = true; } catch (e) {}
      }
      resetTranscriptFields();
      if (state.networkAbortController) {
        try { state.networkAbortController.abort(); } 
        catch (error) {
          err('Error during cleanup:', error);
          updateStatus('Error cleaning up resources. Please refresh the page.', 'error');
        }
        state.networkAbortController = null;
      }
      startBtn.disabled = false;
      stopBtn.disabled = true;
      if (isAuto) {
        updateStatus('Session ended with summary. Ready for new customer!', 'warning');
      } else {
        updateStatus('Ready to help you find your perfect Mahindra!', 'info');
      }
      log('Conversation stopped and cleaned up');
    }

    // -------------- Event Wiring --------------
    if (startBtn) startBtn.addEventListener('click', () => startConversation());
    if (stopBtn) stopBtn.addEventListener('click', () => stopConversation(false));
    window.addEventListener('beforeunload', () => stopConversation());
    if (stopBtn) stopBtn.disabled = true;
    updateStatus(`${AI_NAME} ready`, 'info');
    log(`${AI_NAME} - Mahindra Sales Assistant initialized and ready`);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initModule, { once: true });
  } else {
    initModule();
  }
})();
