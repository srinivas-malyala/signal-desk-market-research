/* Opt-in only against the synthetic fixture with ASSISTANT_FIXTURE_ACTIONS=true. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async()=>{
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1280,height:960}});
    await page.goto('http://127.0.0.1:8769/');
    await page.locator('#assistant-question').fill('Prepare a watchlist draft');
    await page.locator('#assistant-send').click();
    await page.locator('#assistant-proposal-list article').first().waitFor();
    const card=page.locator('#assistant-proposal-list article').first();
    const confirm=card.getByRole('button',{name:'Confirm exact action'});
    assert.equal(await confirm.isDisabled(),true);
    const editor=card.locator('textarea');const original=await editor.inputValue();
    await editor.fill('{"ticker":"MSFT","watchlist_name":"Primary"}');
    await card.locator('input[type=checkbox]').check();
    assert.equal(await confirm.isDisabled(),true);
    await editor.fill(original);
    await card.locator('input[type=checkbox]').check();
    assert.equal(await confirm.isEnabled(),true);
    await confirm.click();
    await page.waitForFunction(()=>document.querySelector('#assistant-proposal-list').textContent.includes('Saved — verified'));
    await page.locator('#assistant-reload').click();
    await page.waitForFunction(()=>document.querySelector('#assistant-proposal-list').textContent.includes('succeeded'));
    assert.equal(await page.locator('#assistant-proposal-list textarea').isDisabled(),true);
    console.log('Synthetic explicit confirmation, saved receipt and reload passed.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
