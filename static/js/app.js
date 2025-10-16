(function waitForDomAndInit() {
    function initModule() {
      // -----------------------
      // DOM elements (created after DOM ready)
      // -----------------------
      const startBtn = document.getElementById('startBtn');
      const stopBtn = document.getElementById('stopBtn');
      const statusEl = document.getElementById('status');
      const userTranscriptEl = document.getElementById('userTranscript');
      const aiTranscriptEl = document.getElementById('aiTranscript');
      const aiAudioEl = document.getElementById('aiAudio');
  
      // -----------------------
      // App State
      // -----------------------
      const state = {
        sessionId: null,
        peerConnection: null,
        dataChannel: null,
        audioStream: null,
        isStreaming: false,
        committedTranscript: '',
        streamingLine: '',
        streamingPrefix: 'Ishmael: ',
        currentAIResponse: '',
        summaryInProgress: false,
        summaryCallId: null,
        summaryIntroComplete: false,
        pendingRaf: null, // for requestAnimationFrame batching of UI updates
        networkAbortController: null
      };
  
      // -----------------------
      // Small helpers
      // -----------------------
      function log(...args) { console.log('Ishmael:', ...args); }
      function warn(...args) { console.warn('Ishmael:', ...args); }
      function err(...args) { console.error('Ishmael:', ...args); }
  
      function generateSessionId() {
        return `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
      }
  
      // Safe JSON parse for incoming messages
      function safeJson(text, fallback = {}) {
        try { return JSON.parse(text); } catch (_) { return fallback; }
      }
  
      // Small fetch wrapper that returns parsed JSON or throws
      async function fetchJson(url, opts = {}) {
        if (state.networkAbortController) {
          state.networkAbortController.abort();
        }
        state.networkAbortController = new AbortController();
        opts.signal = state.networkAbortController.signal;
        opts.headers = {...(opts.headers || {}), 'Content-Type': 'application/json'};
        const res = await fetch(url, opts);
        if (!res.ok) {
          const t = await res.text();
          throw new Error(`${res.status} ${res.statusText} - ${t}`);
        }
        try { return await res.json(); } catch (e) { return null; }
      }
  
      // -----------------------
      // Status & transcript UI
      // -----------------------
      const ICONS = { success: '✅', error: '❌', warning: '⏳', info: '🚗' };
  
      function updateStatus(message, type = 'info') {
        if (!statusEl) return;
        statusEl.textContent = `${ICONS[type] || ICONS.info} ${message}`;
        statusEl.className = 'status';
        statusEl.classList.toggle('status-error', type === 'error');
        statusEl.classList.toggle('status-success', type === 'success');
        statusEl.classList.toggle('status-warning', type === 'warning');
      }
  
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
  
      function updateUserTranscript(text) {
        appendToElement(userTranscriptEl, text);
      }
  
      function updateAITranscript(text) {
        appendToElement(aiTranscriptEl, text);
      }
  
      // Use RAF to batch frequent streaming updates to avoid DOM thrash
      function scheduleAIRender() {
        if (state.pendingRaf) return;
        state.pendingRaf = requestAnimationFrame(() => {
          state.pendingRaf = null;
          let render = '';
          if (state.committedTranscript) {
            render = state.committedTranscript + (state.streamingLine ? '\n' + state.streamingPrefix + state.streamingLine : '');
          } else {
            render = state.streamingLine ? state.streamingPrefix + state.streamingLine : '';
          }
          setElementText(aiTranscriptEl, render ? render + '\n' : '');
        });
      }
  
      // -----------------------
      // Streaming Transcript API
      // -----------------------
      function startStreamingResponse(prefix = 'Ishmael: ') {
        state.streamingPrefix = prefix;
        // If placeholder text present, clear it
        if (aiTranscriptEl && aiTranscriptEl.classList.contains('empty')) {
          aiTranscriptEl.classList.remove('empty');
          setElementText(aiTranscriptEl, '');
          state.committedTranscript = '';
        } else {
          state.committedTranscript = (aiTranscriptEl ? aiTranscriptEl.textContent : '').replace(/\n+$/, '');
        }
        state.streamingLine = '';
        state.currentAIResponse = '';
        state.isStreaming = true;
        scheduleAIRender();
      }
  
      function updateStreamingAITranscript(text) {
        // text is evolving line content (no prefix)
        state.streamingLine = text || '';
        scheduleAIRender();
      }
  
      function finalizeStreamingResponse(finalText) {
        if (!finalText || !finalText.trim()) {
          log('Skipping finalize: empty finalText');
          state.isStreaming = false;
          state.currentAIResponse = '';
          state.streamingLine = '';
          return;
        }
  
        // Normalize prefix if included
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
          state.committedTranscript = (state.committedTranscript ? state.committedTranscript + '\n' : '') + lineToAppend;
          setElementText(aiTranscriptEl, state.committedTranscript.trim() + '\n');
        }
  
        // persist (fire & forget)
        saveMessageToDatabase('assistant', `${state.streamingPrefix}${normalized}`).catch(e => warn('saveMessage failed', e));
  
        // reset streaming
        state.streamingLine = '';
        state.currentAIResponse = '';
        state.isStreaming = false;
      }
  
      // -----------------------
      // DB Save wrapper
      // -----------------------
      async function saveMessageToDatabase(role, content) {
        if (!state.sessionId || !content) return;
        try {
          await fetch('/api/conversation', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              session_id: state.sessionId,
              role,
              content
            })
          }).then(res => {
            if (!res.ok) return res.text().then(t => { throw new Error(t || res.status); });
            log(`Saved ${role}`);
          });
        } catch (e) {
          warn('Failed to save message:', e);
        }
      }
  
      // -----------------------
      // Function Call Handler
      // -----------------------
      async function handleFunctionCall(functionName, args = {}, callId = null) {
        log('Function call:', functionName, args, 'callId:', callId);
  
        if (functionName === 'generate_conversation_summary') {
          // Normalize session id fallback
          const callSessionId = (args && args.session_id && args.session_id !== 'current_conversation') ? args.session_id : state.sessionId;
          if (!callSessionId) {
            updateAITranscript("Ishmael: We need to have a conversation first before I can generate a summary. Please tell me about your vehicle requirements!");
            updateStatus('Ready', 'info');
            return { status: 'no_session' };
          }
  
          // Prevent duplicates for same call id
          if (state.summaryInProgress && callId && state.summaryCallId === callId) {
            log('Summary already in progress for same call id, skipping...');
            return { status: 'in_progress' };
          }
  
          state.summaryInProgress = true;
          state.summaryCallId = callId || null;
          updateStatus('Generating summary...', 'warning');
  
          try {
            const res = await fetch('/api/generate-summary', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({ session_id: callSessionId })
            });
  
            if (!res.ok) {
              const t = await res.text();
              throw new Error(t || `Status ${res.status}`);
            }
  
            const result = await res.json();
            log('Summary result:', result);
  
            if (result.status === 'success' && result.formatted_summary) {
              // send function response back to OpenAI if dataChannel open and callId present
              if (state.dataChannel && state.dataChannel.readyState === 'open' && callId) {
                const functionResponse = {
                  type: 'conversation.item.create',
                  item: {
                    type: 'function_call_output',
                    call_id: callId,
                    output: JSON.stringify({
                      status: 'success',
                      message: "Summary generated successfully. Here's what we discussed:",
                      summary_text: result.summary?.summary || 'Summary generated'
                    })
                  }
                };
                try {
                  state.dataChannel.send(JSON.stringify(functionResponse));
                  // request TTS
                  state.dataChannel.send(JSON.stringify({ type: 'response.create' }));
                } catch (e) {
                  warn('Failed to send function response via dataChannel', e);
                }
              }
  
              updateAITranscript(result.formatted_summary);
              await saveMessageToDatabase('assistant', result.formatted_summary);
              updateStatus('Connected! How can I help you?', 'success');

              // Delay clean-up/stop until TTS (audio) for summary has finished playing
              if (!state.pendingSessionClosure) state.pendingSessionClosure = false;
              if (state.awaitingSessionClosure) state.awaitingSessionClosure = false;
              if (window && aiAudioEl) {
                // Set flag so audio event only runs this once
                state.pendingSessionClosure = true;
                console.log("[DEBUG] Set pendingSessionClosure=true, adding audio ended listener");
                aiAudioEl.addEventListener('ended', function onAudioEnd() {
                  console.log("[DEBUG] audio ended event fired, pendingSessionClosure?", state.pendingSessionClosure);
                  if (state.pendingSessionClosure) {
                    stopConversation(true);
                    state.pendingSessionClosure = false;
                    console.log("[DEBUG] stopConversation(true) called by audio ended event");
                  }
                  aiAudioEl.removeEventListener('ended', onAudioEnd);
                }, { once: true });
              }

              // Fallback: if audio never fires .ended, force session end after 8s (for debug/demo only)
              setTimeout(() => {
                if (state.pendingSessionClosure) {
                  stopConversation(true);
                  state.pendingSessionClosure = false;
                  console.log("[DEBUG] Fallback: timed stopConversation executed after waiting for summary TTS");
                }
              }, 8000);

              state.summaryInProgress = false;
              state.summaryCallId = null;
              return result;
            } else if (result.status === 'error' && result.message && result.message.includes('No messages found')) {
              updateAITranscript("Ishmael: We just started our conversation! Let's discuss your vehicle needs first, and then I'll provide a comprehensive summary.");
              updateStatus('Connected! How can I help you?', 'success');
              state.summaryInProgress = false;
              state.summaryCallId = null;
              return { status: 'insufficient_data' };
            } else {
              throw new Error(result.message || 'Failed to generate summary');
            }
          } catch (error) {
            err('Summary generation error:', error);
            state.summaryInProgress = false;
            state.summaryCallId = null;
            updateStatus('Connected! How can I help you?', 'success');
            updateAITranscript("Ishmael: I'd be happy to provide a summary once we've had a proper conversation! Please tell me about your vehicle requirements - budget, usage, preferences - and I'll give you personalized recommendations.");
            return { error: (error && error.message) || String(error) };
          }
        }
  
        // Other function calls (acknowledge)
        if (functionName === 'analyze_user_needs' || functionName === 'get_user_recommendations') {
          log(`${functionName} acknowledged`);
          return { status: 'acknowledged' };
        }
  
        log('Unknown function call:', functionName);
        return { status: 'unknown_function' };
      }
  
      // -----------------------
      // Data channel & message handling
      // -----------------------
      async function handleDataChannelMessage(rawMsg) {
        const msg = (typeof rawMsg === 'string') ? safeJson(rawMsg) : rawMsg;
        const type = msg.type;
        if (type && !type.includes('audio') && !type.includes('delta')) {
          log('Event:', type, msg);
        }
  
        // transcription finished
        if (type === 'conversation.item.input_audio_transcription.completed') {
          const transcript = msg.transcript || '';
          updateUserTranscript(`You: ${transcript}`);
          saveMessageToDatabase('user', transcript).catch(e => warn('save user failed', e));
          return;
        }
  
        // function-call variants (formats handled)
        if (type === 'response.function_call_arguments.done') {
          const functionName = msg.name;
          const args = safeJson(msg.arguments || '{}');
          const callId = msg.call_id || msg.item_id || null;
          await handleFunctionCall(functionName, args, callId);
          state.isStreaming = false;
          state.currentAIResponse = '';
          return;
        }
  
        if (type === 'response.output_item.done' && msg.item?.type === 'function_call') {
          const functionName = msg.item.name;
          const args = safeJson(msg.item.arguments || '{}');
          const callId = msg.item.call_id || msg.item.id || null;
          await handleFunctionCall(functionName, args, callId);
          state.isStreaming = false;
          state.currentAIResponse = '';
          return;
        }
  
        if (type === 'conversation.item.created' && msg.item?.type === 'function_call') {
          const functionName = msg.item.name;
          const args = safeJson(msg.item.arguments || '{}');
          const callId = msg.item.call_id || msg.item.id || null;
          await handleFunctionCall(functionName, args, callId);
          state.isStreaming = false;
          state.currentAIResponse = '';
          return;
        }
  
        // AI response created -> start streaming UI
        if (type === 'response.created') {
          state.currentAIResponse = '';
          startStreamingResponse(state.streamingPrefix);
          return;
        }
  
        // streaming audio transcript deltas
        if (type === 'response.audio_transcript.delta') {
          const delta = msg.delta || '';
          state.currentAIResponse += delta;
          // Ensure streaming flagged
          if (!state.isStreaming) startStreamingResponse(state.streamingPrefix);
          updateStreamingAITranscript(state.currentAIResponse);
          return;
        }
  
        // audio transcript done -> finalize
        if (type === 'response.audio_transcript.done') {
          const transcriptRaw = msg.transcript || state.currentAIResponse;
          const transcript = (transcriptRaw && transcriptRaw.trim()) ? transcriptRaw.trim() : '';
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
  
        // session events
        if (type === 'session.created' || type === 'session.updated') {
          log('Session event:', msg);
          return;
        }
  
        // generic error
        if (type === 'error') {
          err('OpenAI error:', msg);
          updateStatus(`OpenAI error: ${msg.error?.message || 'Unknown'}`, 'error');
        }
      }
  
      // -----------------------
      // Start & Stop conversation (WebRTC + Realtime setup)
      // -----------------------
      async function startConversation() {
        // idempotent guard
        if (state.peerConnection || state.dataChannel) {
          warn('Already connected — ignoring startConversation call');
          return;
        }
  
        try {
          startBtn.disabled = true;
          state.sessionId = generateSessionId();
          log('Session ID:', state.sessionId);
          updateStatus('Connecting to Mahindra assistant...', 'info');
  
          // 1. Get ephemeral key from backend
          const sessionResp = await fetch('/api/session');
          if (!sessionResp.ok) throw new Error(`Failed to get session: ${sessionResp.status}`);
          const sessionData = await sessionResp.json();
          const EPHEMERAL_KEY = sessionData?.client_secret?.value;
          if (!EPHEMERAL_KEY) throw new Error('No ephemeral key returned from backend');
  
          updateStatus('Preparing consultation session...', 'info');
  
          // 2. Setup RTCPeerConnection
          const pc = new RTCPeerConnection();
          state.peerConnection = pc;
  
          // 3. audio element behaviour
          aiAudioEl.autoplay = true;
          pc.ontrack = (ev) => {
            log('Received audio track from OpenAI');
            try { aiAudioEl.srcObject = ev.streams[0]; } catch (e) { warn('Failed to set audio srcObject', e); }
          };
  
          // 4. get user microphone
          updateStatus('Requesting microphone access...', 'warning');
          state.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          const audioTrack = state.audioStream.getAudioTracks()[0];
          if (!audioTrack) throw new Error('No audio track from microphone');
          pc.addTrack(audioTrack);
          log('Added local audio track');
  
          updateStatus('Connecting to Ishmael...', 'info');
  
          // 5. create data channel
          const dc = pc.createDataChannel('oai-events');
          state.dataChannel = dc;
  
          dc.addEventListener('open', () => {
            log('Data channel opened - consultation ready');
            updateStatus('Connected! How can I help you today?', 'success');
            stopBtn.disabled = false;
          });
  
          dc.addEventListener('message', (evt) => {
            try {
              handleDataChannelMessage(evt.data);
            } catch (e) {
              warn('dataChannel message handler error', e);
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
  
          // 6. create local offer
          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);
  
          // 7. exchange SDP with OpenAI Realtime API
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
          const answer = { type: 'answer', sdp: answerSdp };
          await pc.setRemoteDescription(answer);
          log('WebRTC connection established - Mahindra sales consultant ready');
  
        } catch (error) {
          err('Error starting conversation:', error);
          updateStatus(`Error: ${error.message}`, 'error');
          startBtn.disabled = false;
          stopConversation();
        }
      }
  
      function stopConversation(isAuto = false) {
        // close dataChannel
        if (state.dataChannel) {
          try { state.dataChannel.close(); } catch (e) { /* ignore */ }
          state.dataChannel = null;
        }
  
        // close peer connection
        if (state.peerConnection) {
          try { state.peerConnection.close(); } catch (e) { /* ignore */ }
          state.peerConnection = null;
        }
  
        // stop local audio tracks
        if (state.audioStream) {
          try { state.audioStream.getTracks().forEach(track => track.stop()); } catch (e) { /* ignore */ }
          state.audioStream = null;
        }
  
        // Reset streaming transcript state but preserve committed text
        state.committedTranscript = (aiTranscriptEl ? aiTranscriptEl.textContent.replace(/\n+$/, '') : '') || '';
        state.streamingLine = '';
        state.isStreaming = false;
        state.currentAIResponse = '';
  
        // clear abort controller
        if (state.networkAbortController) {
          try { state.networkAbortController.abort(); } catch (e) {}
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
  
      // -----------------------
      // Event wiring
      // -----------------------
      if (startBtn) startBtn.addEventListener('click', () => startConversation());
      if (stopBtn) stopBtn.addEventListener('click', () => stopConversation(false));
  
      window.addEventListener('beforeunload', () => {
        stopConversation();
      });
  
      // initialize UI (handle placeholders robustly)
      function initTranscript(el) {
        if (!el) return;
        const text = (el.textContent || '').trim();
        const lower = text.toLowerCase();
        // If it's empty or contains typical placeholder signals, clear it and mark empty
        if (!text ||
            lower.includes('click') && lower.includes('start') ||
            lower.includes('start conversation') ||
            lower.startsWith('ishmael') ||
            lower.startsWith('you:') ||
            lower.includes('tell me what you') ||
            lower.includes('click "start conversation"')) {
          el.textContent = '';
          el.classList.add('empty');
        }
      }
      initTranscript(userTranscriptEl);
      initTranscript(aiTranscriptEl);
  
      if (stopBtn) stopBtn.disabled = true;
      updateStatus('Ishmael ready', 'info');
  
      log('Ishmael - Mahindra Sales Assistant initialized and ready');
    }
  
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initModule, { once: true });
    } else {
      initModule();
    }
  })();  