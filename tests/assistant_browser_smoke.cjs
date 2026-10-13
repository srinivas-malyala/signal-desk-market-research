/* Opt-in browser QA against tests/assistant_ui_fixture.py, never live services. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:960}});
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:8769/');
    await page.locator('#assistant-question').fill('Compare AAPL and MSFT');
    await page.locator('#assistant-send').click();
    await page.waitForFunction(() => document.querySelector('#assistant-status').textContent.startsWith('Research complete.'));
    assert.ok(await page.locator('#assistant-transcript').innerText().then(text => text.includes('<script>')));
    assert.equal(await page.evaluate(() => window.injected), undefined);
    await page.locator('#assistant-proposal-list article').first().waitFor();
    const draft = page.locator('#assistant-proposal-list article').first();
    assert.equal(await draft.getByRole('button', {name:'Confirm — execution available in M5'}).isDisabled(),true);
    await draft.locator('textarea').fill('{"ticker":"MSFT","watchlist_name":"Primary"}');
    await draft.getByRole('button',{name:'Create revised draft'}).click();
    await page.waitForFunction(() => document.querySelector('#assistant-proposal-list').textContent.includes('revision 2'));
    await page.locator('#assistant-proposal-list article').filter({hasText:'revision 2'}).getByRole('button',{name:'Dismiss',exact:true}).click();
    await page.waitForFunction(() => document.querySelector('#assistant-proposal-list').textContent.includes('dismissed'));
    await page.locator('#assistant-reload').click();
    await page.waitForFunction(() => document.querySelector('#assistant-status').textContent.startsWith('History reloaded.'));
    await page.screenshot({path:'/tmp/assistant-m3-desktop.png',fullPage:false});
    await page.locator('#assistant-question').fill('slow research');
    await page.locator('#assistant-send').click();
    await page.waitForFunction(() => !document.querySelector('#assistant-stop').disabled);
    await page.waitForFunction(() => document.querySelector('#assistant-transcript').lastElementChild.querySelector('p').textContent.includes('Synthetic answer.'));
    await page.locator('#assistant-stop').click();
    await page.waitForFunction(() => document.querySelector('#assistant-status').textContent.startsWith('Stopped local delivery.'));
    await page.waitForTimeout(750);
    await page.locator('#assistant-reload').click();
    await page.waitForFunction(() => document.querySelector('#assistant-status').textContent.startsWith('History reloaded.'));
    assert.ok((await page.locator('#assistant-transcript').innerText()).includes('interrupted'));
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'/tmp/assistant-m3-mobile.png',fullPage:false});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
    assert.deepEqual(errors, []);
    console.log('Desktop/mobile, streaming, literal HTML, reload and stop browser smoke passed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode=1; });
