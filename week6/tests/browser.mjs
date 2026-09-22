// Real Chromium layout, copy fallback, deck controls and offline checks.
import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const shots=fs.mkdtempSync(path.join(os.tmpdir(),'week6-browser-'));
const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
const context=await browser.newContext({offline:true});
const page=await context.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
for(const width of [1440,390]){
 await page.setViewportSize({width,height:1000});
 await page.goto('file://'+path.join(root,'GUIDE-N6.html'));
 assert.equal(await page.locator('section').count(),10);
 assert.equal(await page.locator('.prompt button').count(),10);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:path.join(shots,`guide-${width}.png`)});
 await page.locator('#trial').scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(shots,`trial-${width}.png`)});
 await page.locator('#trial button').first().click();
 await page.waitForFunction(()=>/Скопировано|Текст выделен/.test(document.querySelector('#trial button').textContent));
 assert.match(await page.locator('#trial button').first().textContent(),/Скопировано|Текст выделен/);
 await page.goto('file://'+path.join(root,'instructions/VPS-HERMES.html'));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:path.join(shots,`vps-${width}.png`)});
 await page.goto('file://'+path.join(root,'assets/shablon-hakatona.html'));
 await page.locator('#mode').click();
 for(let i=0;i<8;i++){
  assert.equal(await page.locator('.slide.active').count(),1);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(shots,`deck-${width}-${i}.png`),fullPage:true});
  await page.keyboard.press('ArrowRight');
 }
 await page.keyboard.press('n');assert.ok(await page.locator('body').evaluate(e=>e.classList.contains('notes')));
 await page.keyboard.press('b');assert.ok(await page.locator('body').evaluate(e=>e.classList.contains('blackout')));
 await page.keyboard.press('Escape');assert.ok(await page.locator('body').evaluate(e=>!e.classList.contains('blackout')));
}
assert.deepEqual(errors,[]);
await browser.close();console.log('PASS Chromium offline, desktop/mobile, copy, 8 slides, controls. Screenshots: '+shots);
