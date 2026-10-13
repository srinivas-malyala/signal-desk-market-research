/* Review-only drafts. Never authorizes or executes a business mutation. */
(() => {
  const root = document.querySelector('#assistant-proposal-list');
  if (!root) return;
  async function request(path, body) {
    const options = body ? {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content},body:JSON.stringify(body)} : {};
    const response = await fetch(path,{credentials:'same-origin',...options});
    const value = await response.json();
    if (!response.ok) throw new Error(value.message || 'Draft request failed.');
    return value;
  }
  window.loadAssistantProposals = async conversation => {
    root.replaceChildren(); if (!conversation) return;
    try {
      const result = await request(`/api/assistant/conversations/${encodeURIComponent(conversation)}/proposals`);
      if (!result.proposals.length) { root.textContent = 'No stored drafts for this conversation.'; return; }
      for (const draft of result.proposals) {
        const card = document.createElement('article'); card.className='assistant-message';
        const heading = document.createElement('h4'); heading.textContent=`${draft.payload.type} · revision ${draft.revision} · ${draft.state}`;
        const preview = document.createElement('pre'); preview.textContent=JSON.stringify(draft.payload,null,2); preview.style.whiteSpace='pre-wrap';
        const label=document.createElement('label'); label.textContent='Editable arguments (JSON; creates a new revision)';
        const editor=document.createElement('textarea'); editor.value=JSON.stringify(draft.payload.arguments,null,2); editor.rows=6; editor.maxLength=450000; label.append(editor);
        const status=document.createElement('p'); status.setAttribute('role','status');
        const revise=document.createElement('button'); revise.type='button'; revise.textContent='Create revised draft';
        const dismiss=document.createElement('button'); dismiss.type='button'; dismiss.textContent='Dismiss';
        const confirm=document.createElement('button'); confirm.type='button'; confirm.textContent='Confirm — execution available in M5'; confirm.disabled=true;
        const checkLabel=document.createElement('label'); const check=document.createElement('input'); check.type='checkbox'; checkLabel.append(check,document.createTextNode(' I reviewed this exact draft. This does not execute it.'));
        const expired=new Date(draft.expires_at)<=new Date(); editor.disabled=revise.disabled=dismiss.disabled=draft.state!=='pending'||expired;
        const expiry=document.createElement('small'); expiry.textContent=`Expires ${new Date(draft.expires_at).toLocaleString()} · hash ${draft.payload_hash}`;
        const mutate=async(operation, extra={})=>{try{await request(`/api/assistant/proposals/${encodeURIComponent(draft.id)}/${operation}`,{payload_hash:draft.payload_hash,...extra});await window.loadAssistantProposals(conversation);}catch(error){status.textContent=error.message;}};
        revise.onclick=()=>{try{mutate('revise',{arguments:JSON.parse(editor.value)});}catch(error){status.textContent='Arguments must be valid JSON.';}};
        dismiss.onclick=()=>mutate('dismiss');
        card.append(heading,preview,expiry,label,checkLabel,revise,dismiss,confirm,status);root.append(card);
      }
    } catch(error) { root.textContent=error.message; }
  };
})();
