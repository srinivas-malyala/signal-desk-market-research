const assert = require('node:assert/strict');
const test = require('node:test');
const Frames = require('../dashboard/static/assistant_stream.js');
const event = (sequence = 1, extra = {}) => ({type:'status',schema_version:1,sequence,run_id:'run',request_id:'request',...extra});
const frame = value => `data: ${JSON.stringify(value)}\n\n`;
test('split frames and comments preserve ordered identity', () => {
  const events = [], parser = new Frames(value => events.push(value));
  const data = ': heartbeat\n\n' + frame(event()) + frame(event(2,{type:'text_delta',text:'😀 <script>plain text</script>'}));
  for (const character of data) parser.feed(character);
  parser.finish(); assert.equal(events.length,2); assert.ok(events[1].text.includes('<script>'));
});
test('invalid frames, sequence and changing identity fail closed', () => {
  assert.throws(() => new Frames(() => {}).feed('data: invalid\n\n'));
  assert.throws(() => new Frames(() => {}).feed(frame(event(2))));
  const parser = new Frames(() => {}); parser.feed(frame(event()));
  assert.throws(() => parser.feed(frame(event(2,{run_id:'other'}))));
  assert.throws(() => new Frames(() => {}).feed(frame(event(1,{type:'function_call'}))));
});
test('incomplete and oversized frames are rejected', () => {
  const parser = new Frames(() => {}); parser.feed('data: {}'); assert.throws(() => parser.finish());
  assert.throws(() => new Frames(() => {}).feed('x'.repeat(150001)));
});
