/* Bounded SSE framing, usable by browser and Node-based contract tests. */
(() => {
  class AssistantFrames {
    constructor(onEvent) { this.onEvent = onEvent; this.buffer = ''; this.total = 0; this.sequence = 0; this.requestId = null; this.runId = null; }
    feed(text) {
      this.total += new TextEncoder().encode(text).length;
      if (this.total > 4000000) throw new Error('Chat stream exceeded its limit.');
      this.buffer += text;
      let position;
      while ((position = this.buffer.indexOf('\n\n')) >= 0) {
        const frame = this.buffer.slice(0, position); this.buffer = this.buffer.slice(position + 2);
        if (new TextEncoder().encode(frame).length > 150000) throw new Error('Chat event exceeded its limit.');
        const data = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
        if (!data) continue;
        const event = JSON.parse(data);
        if (!event || event.schema_version !== 1 || !['status', 'text_delta', 'complete', 'error', 'proposal'].includes(event.type) ||
            !Number.isInteger(event.sequence) || event.sequence !== this.sequence + 1 || typeof event.run_id !== 'string' ||
            typeof event.request_id !== 'string') throw new Error('Invalid chat event.');
        if (this.requestId && (event.request_id !== this.requestId || event.run_id !== this.runId)) throw new Error('Chat stream identity changed.');
        if (event.type === 'text_delta' && typeof event.text !== 'string') throw new Error('Invalid chat text.');
        this.sequence = event.sequence; this.requestId = event.request_id; this.runId = event.run_id;
        this.onEvent(event);
      }
      if (new TextEncoder().encode(this.buffer).length > 150000) throw new Error('Chat frame exceeded its limit.');
    }
    finish() { if (this.buffer.trim()) throw new Error('Chat stream ended in an incomplete frame.'); }
  }
  if (typeof module !== 'undefined') module.exports = AssistantFrames;
  else window.AssistantFrames = AssistantFrames;
})();
