/* Model content is always plain text. No HTML, links or action execution. */
(() => {
  const root = document.querySelector('#assistant');
  if (!root) return;
  const $ = id => root.querySelector(`#assistant-${id}`);
  const transcript = $('transcript'), question = $('question'), select = $('conversation');
  let conversation = '', cursor = null, controller = null, pending = null;
  const status = text => { $('status').textContent = text; };
  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || '';
  const busy = value => { ['send','new','reload','more','conversation'].forEach(id => { $(id).disabled = value; }); $('stop').disabled = !value; };
  async function request(url, options = {}) {
    const response = await fetch(url, {credentials:'same-origin', ...options,
      headers:{'Content-Type':'application/json', 'X-CSRF-Token':csrf(), ...options.headers}});
    if (!response.ok) {
      const value = await response.json().catch(() => ({}));
      throw new Error(`${value.message || 'Chat is unavailable.'} (${value.error_code || response.status})`);
    }
    return response;
  }
  function message(role, text, label = '') {
    const article = document.createElement('article'); article.className = `assistant-message assistant-${role === 'You' ? 'user' : 'answer'}`;
    const heading = document.createElement('strong'); heading.textContent = role;
    const content = document.createElement('p'); content.textContent = text;
    const detail = document.createElement('small'); detail.textContent = label;
    article.append(heading, content, detail); transcript.append(article); return {content, detail};
  }
  async function conversations(append = false) {
    const url = '/api/assistant/conversations' + (append && cursor ? `?before=${encodeURIComponent(cursor)}` : '');
    const result = await (await request(url)).json();
    if (!append) { select.replaceChildren(); select.add(new Option('New conversation','')); }
    for (const item of result.conversations) select.add(new Option(`${item.title} · ${new Date(item.created_at).toLocaleString()}`, item.id));
    cursor = result.next_cursor; $('more').hidden = !cursor; select.value = conversation;
  }
  async function history() {
    window.loadAssistantProposals?.(conversation);
    if (!conversation) { transcript.replaceChildren(); message('Assistant','Ask a question to begin.'); return; }
    const result = await (await request(`/api/assistant/conversations/${encodeURIComponent(conversation)}`)).json();
    transcript.replaceChildren();
    for (const turn of result.turns) {
      const date = new Date(turn.created_at).toLocaleString();
      message('You', turn.user_redacted_at ? '[Expired transcript redacted]' : turn.user_text, date);
      message('Assistant', turn.assistant_redacted_at ? '[Expired transcript redacted]' : (turn.assistant_text || '[No saved answer]'), `${turn.state} · ${date}`);
    }
    status(result.turns.length ? 'History reloaded. Showing the most recent 50 turns.' : 'No messages yet.');
  }
  async function send(event) {
    event.preventDefault(); if (controller) return;
    const text = question.value.trim(); if (!text || text.length > 4000) return;
    controller = new AbortController(); busy(true); $('retry').hidden = true;
    let terminal = false, answer;
    try {
      if (!conversation) {
        const result = await (await request('/api/assistant/conversations',{method:'POST', body:'{}', signal:controller.signal})).json();
        conversation = result.conversation.id; await conversations(); transcript.replaceChildren();
      }
      if (!pending || pending.message !== text || pending.conversation !== conversation) pending = {conversation, message:text, id:crypto.randomUUID()};
      message('You',text); answer = message('Assistant','', 'Generating — not yet saved'); status('Researching…');
      const response = await request(`/api/assistant/conversations/${encodeURIComponent(conversation)}/messages`, {
        method:'POST', signal:controller.signal, body:JSON.stringify({message:text,client_message_id:pending.id})});
      if (response.headers.get('Content-Type')?.includes('application/json')) {
        const result = await response.json(); await history();
        status(`Existing request: ${result.existing_run.state}. No new generation started.`); terminal = true; return;
      }
      if (!response.headers.get('Content-Type')?.includes('text/event-stream') || !response.body) throw new Error('Invalid chat response.');
      const reader = response.body.getReader(), decoder = new TextDecoder('utf-8', {fatal:true});
      const frames = new window.AssistantFrames(value => {
        if (value.type === 'status') status(value.history_omitted ? 'Researching with bounded history; older context was omitted.' : 'Researching…');
        if (value.type === 'text_delta') {
          if (terminal) throw new Error('Text arrived after completion.');
          answer.content.textContent += value.text;
          if (new TextEncoder().encode(answer.content.textContent).length > 100000) throw new Error('Answer exceeded its limit.');
        }
        if (value.type === 'complete') { terminal = true; if (typeof value.text === 'string') answer.content.textContent = value.text; answer.detail.textContent = 'Completed and saved'; status('Research complete. Verify claims independently.'); pending = null; question.value = ''; }
        if (value.type === 'error') { terminal = true; answer.detail.textContent = value.state; status(`Research did not complete (${value.error_code || value.state}). Reload history to check saved state.`); $('retry').hidden = false; }
      });
      try {
        while (true) { const chunk = await reader.read(); if (chunk.done) break; frames.feed(decoder.decode(chunk.value,{stream:true})); }
        frames.feed(decoder.decode()); frames.finish();
        if (!terminal) throw new Error('Connection ended without verified completion.');
      } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
    } catch (error) {
      if (answer) answer.detail.textContent = 'Delivery interrupted — reload to check saved state';
      status(error.name === 'AbortError' ? 'Stopped local delivery. Remote research may continue; reload to check its state.' : error.message);
      $('retry').hidden = !pending;
    } finally { controller = null; busy(false); question.focus(); window.loadAssistantProposals?.(conversation); }
  }
  $('form').addEventListener('submit',send);
  question.addEventListener('keydown',event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); $('form').requestSubmit(); } });
  $('stop').onclick = () => controller?.abort();
  $('retry').onclick = () => { if (pending) { question.value = pending.message; $('form').requestSubmit(); } };
  $('new').onclick = () => { conversation = ''; select.value = ''; pending = null; question.value = ''; $('retry').hidden = true; history(); question.focus(); };
  select.onchange = () => { conversation = select.value; pending = null; history().catch(error => status(error.message)); };
  $('reload').onclick = () => history().catch(error => status(error.message));
  $('more').onclick = () => conversations(true).catch(error => status(error.message));
  conversations().then(() => status('Ready. Ask a question to begin.')).catch(error => status(error.message));
})();
