// app.js
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
      pendingRaf: null,
      networkAbortController: null
  };
  
  // -----------------------
  // Small helpers
  // -----------------------
  function log(...args) { console.log('Ishmael:', ...args); }
  function warn(...args) { console.warn('Ishmael:', ...args); }
  function err(...args) { console.error('Ishmael:', ...args); }
  
  function generateSessionId() {
    // OpenAI session IDs have to be unique per session. 
    return `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
  }
  
  function safeJson(text, fallback = {}) {
    // Safely parse JSON, return fallback on error.
    // If syntax error, return fallback.
    try { return JSON.parse(text); } catch (_) { return fallback; }
  }

  // -----------------------
  // Status & transcript UI
  // -----------------------
  const ICONS = { success: '✅', error: '❌', warning: '⏳', info: '🚗' };
  
  // An simple status updater
  function updateStatus(message, type = 'info') {
  if (!statusEl) return;
  statusEl.textContent = `${ICONS[type] || ICONS.info} ${message}`;
  statusEl.className = 'status';
    statusEl.classList.toggle('status-error', type === 'error');
    statusEl.classList.toggle('status-success', type === 'success');
    statusEl.classList.toggle('status-warning', type === 'warning');
  }

  // Utility function to append text to an element
  // In this case, used for both user and AI transcripts 
  function appendToElement(el, text) {
  if (!el) return;
    if (el.classList.contains('empty')) el.classList.remove('empty');
      el.textContent += `${text}\n`;
      el.scrollTop = el.scrollHeight;
  }
  
  // Making sure the entire text is set properly
  // Reset after streaming updates
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
  
  // Responsible for scheduling AI transcript rendering even while mid-sentence audio responses
  function scheduleAIRender() {
  // Called whenever streaming line updates
  if (state.pendingRaf) return;
  state.pendingRaf = requestAnimationFrame(() => {
    state.pendingRaf = null;
      let render = '';
        if (state.committedTranscript) {
          render = state.committedTranscript + (state.streamingLine ? `\n${state.streamingPrefix}${state.streamingLine}` : '');
    }   else {
    render = state.streamingLine ? `${state.streamingPrefix}${state.streamingLine}` : '';
    }
      setElementText(aiTranscriptEl, render ? `${render}\n` : '');
  });
  }
  
  // -----------------------
  // Streaming Transcript API
  // -----------------------

  // Make our transcript and state are correctly reset/synced before getting new data from AI
  function startStreamingResponse(prefix = 'Ishmael: ') {
  state.streamingPrefix = prefix;
    if (aiTranscriptEl?.classList.contains('empty')) {
      // If empty, make the internal transcript also empty
      aiTranscriptEl.classList.remove('empty');
      setElementText(aiTranscriptEl, '');
      state.committedTranscript = '';
    }   else {
      // Else stream our response
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
  
  // -----------------------
  // DB Save wrapper
  // -----------------------
  // Used to save user and AI messages to backend. As JSON
  async function saveMessageToDatabase(role, content) {
  if (!state.sessionId || !content) return;
    try {
      // -- [TOOL CALL - /api/conversation] (1)--
    await fetch('/api/conversation', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ session_id: state.sessionId, role, content })
    }).then(res => {
    if (!res.ok) return res.text().then(t => { throw new Error(t || res.status); });
    log(`Saved ${role}`);
    });
    }   catch (e) {
    warn('Failed to save message:', e);
  }
  }
  
  // -----------------------
  // Function Call Handler
  // -----------------------
  async function handleFunctionCall(functionName, args = {}, callId = null) {
  log('Function call:', functionName, args, 'callId:', callId);
  // generate conversation summary function handler.
  // Used to check function name is passed in to handler
  if (functionName === 'generate_conversation_summary') {
  const callSessionId = (args?.session_id && args.session_id !== 'current_conversation') ? args.session_id : state.sessionId;
  if (!callSessionId) {
  // It is an predefined transcript message when no session exists.
  // Occurs when user tries to get summary before any conversation. Due to this no AI audio is played.
  updateAITranscript("Ishmael: We need to have a conversation first before I can generate a summary. Please tell me about your vehicle requirements!");
  updateStatus('Ready', 'info');
  return { status: 'no_session' };
  }
  
  // Summart in progress check
  if (state.summaryInProgress && callId && state.summaryCallId === callId) {
  log('Summary already in progress for same call id, skipping...');
  return { status: 'in_progress' };
  }
  
  state.summaryInProgress = true;
  state.summaryCallId = callId || null;
  updateStatus('Generating summary...', 'warning');
  
  try {
  // -- [TOOL CALL - /api/generate-summary] (2)--
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
  // Function response via dataChannel.
  if (state.dataChannel?.readyState === 'open' && callId) {
  const functionResponse = {
    type: 'conversation.item.create',
    item: {
    type: 'function_call_output',
    call_id: callId,
    output: JSON.stringify({
    status: 'success',
    message: "Summary generated successfully. Here's what we discussed:",
    summary_text: result.summary?.summary || 'Summary generated'
  })}};
  try {
  state.dataChannel.send(JSON.stringify(functionResponse));
  state.dataChannel.send(JSON.stringify({ type: 'response.create' }));
  } catch (e) {
  warn('Failed to send function response via dataChannel', e);
  }}
  await saveMessageToDatabase('assistant', result.formatted_summary);
  updateStatus('Connected! How can I help you?', 'success');
  
  state.pendingSessionClosure = true;
  // AI audio end or timeout triggers session closure
  aiAudioEl.addEventListener('ended', function onAudioEnd() {
  if (state.pendingSessionClosure) {
  stopConversation(true);
  state.pendingSessionClosure = false;
  }
  aiAudioEl.removeEventListener('ended', onAudioEnd);
  }, { once: true });
  
  // Session auto-close timeout (in case no audio is played)
  setTimeout(() => {
  if (state.pendingSessionClosure) {
  stopConversation(true);
  state.pendingSessionClosure = false;
  }
  }, 4000);
  
  state.summaryInProgress = false;
  state.summaryCallId = null;
  return result;
  } else if (result.status === 'error' && result.message?.includes('No messages found')) {
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
  }}
  
  log('Unknown function call:', functionName);
  return { status: 'unknown_function' };
  }
  
  // -----------------------
  // Data channel & message handling
  // -----------------------
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
  
  // -----------------------
  // Start & Stop conversation (WebRTC + Realtime setup)
  // -----------------------
  async function startConversation() {
  if (state.peerConnection || state.dataChannel) {
  warn('Already connected — ignoring startConversation call');
  return;
  }
  
  try {
  startBtn.disabled = true;
  state.sessionId = generateSessionId();
  log('Session ID:', state.sessionId);
  updateStatus('Connecting to Mahindra assistant...', 'info');
  
  const sessionResp = await fetch('/api/session');
  if (!sessionResp.ok) throw new Error(`Failed to get session: ${sessionResp.status}`);
  const sessionData = await sessionResp.json();
  const EPHEMERAL_KEY = sessionData?.client_secret?.value;
  if (!EPHEMERAL_KEY) throw new Error('No ephemeral key returned from backend');
  
  updateStatus('Preparing consultation session...', 'info');
  
  const pc = new RTCPeerConnection();
  state.peerConnection = pc;
  
  aiAudioEl.autoplay = true;
  aiAudioEl.playsInline = true; // For mobile/iOS inline playback
  aiAudioEl.muted = true;

  pc.ontrack = (ev) => {
    log('Received audio track from OpenAI');
    // Use only the first audio stream, always detach previous in cleanup on stop
    if (!aiAudioEl.srcObject) {
      try {
        aiAudioEl.srcObject = ev.streams[0];
        aiAudioEl.addEventListener('playing', function onPlaying() {
          setTimeout(() => {
            aiAudioEl.muted = false;
          }, 300); // Longer buffer for smoother playback
          aiAudioEl.removeEventListener('playing', onPlaying);
        });
      } catch (e) {
        warn('Failed to set audio srcObject', e);
      }
    }
  };
  
  updateStatus('Requesting microphone access...', 'warning');
  state.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const audioTrack = state.audioStream.getAudioTracks()[0];
  if (!audioTrack) throw new Error('No audio track from microphone');
  pc.addTrack(audioTrack);
  log('Added local audio track');
  updateStatus('Connecting to Ishmael...', 'info');
  
  const dc = pc.createDataChannel('oai-events');
  state.dataChannel = dc;
  
  dc.addEventListener('open', () => {
  log('Data channel opened - consultation ready');
  updateStatus('Connected! How can I help you today?', 'success');
  stopBtn.disabled = false;
  });
  
  dc.addEventListener('message', (evt) => {
  try { handleDataChannelMessage(evt.data); } catch (e) { warn('dataChannel message handler error', e); }
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
  const model = 'gpt-4o-realtime-preview-2024-12-17';
  const sdpResponse = await fetch(`${baseUrl}?model=${model}`, {
  method: 'POST',
  body: offer.sdp,
  headers: {
  'Authorization': `Bearer ${EPHEMERAL_KEY}`,
  'Content-Type': 'application/sdp'
  },
  });
  if (!sdpResponse.ok) throw new Error(`OpenAI SDP exchange failed: ${sdpResponse.status}`);
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
  
  state.committedTranscript = (aiTranscriptEl?.textContent.replace(/\n+$/, '') || '');
  state.streamingLine = '';
  state.isStreaming = false;
  state.currentAIResponse = '';
  
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
  window.addEventListener('beforeunload', () => stopConversation());
  
  function initTranscript(el) {
  if (!el) return;
  const text = (el.textContent || '').trim().toLowerCase();
  if (!text || /click.*start|start conversation|ishmael|you:|tell me what you|click "start conversation"/.test(text)) {
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