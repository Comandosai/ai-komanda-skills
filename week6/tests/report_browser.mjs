import {createRequire} from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';

const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const shots=fs.mkdtempSync(path.join(os.tmpdir(),'week6-report-browser-'));
const browser=await chromium.launch({headless:true,...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{})});
const context=await browser.newContext({offline:true});

for(const rel of ['assets/shablon-hakatona.html','demo/final-report/PREZENTACIYA-HAKATON.html']){
 for(const width of [1440,390]){
  const page=await context.newPage();
  await page.setViewportSize({width,height:1000});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('file://'+path.join(root,rel));
  assert.equal(await page.locator('.slide').count(),9,rel);
  assert.equal(await page.locator('#count').textContent(),'1 / 9',rel);
  const layout=await page.evaluate(()=>({scrollWidth:document.documentElement.scrollWidth,innerWidth}));
  const overflowing=await page.evaluate(()=>[...document.querySelectorAll('*')].map(e=>({tag:e.tagName,cls:e.className,id:e.id,right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width,scroll:e.scrollWidth})).filter(x=>x.right>innerWidth+1||x.scroll>x.width+1).slice(0,8));
  assert.ok(layout.scrollWidth<=layout.innerWidth,rel+' width '+width+' '+JSON.stringify({layout,overflowing}));
  await page.locator('#mode').click();
  for(let i=0;i<9;i++){
   assert.equal(await page.locator('.slide.active').count(),1,rel);
   await page.screenshot({path:path.join(shots,path.basename(rel)+'-'+width+'-'+i+'.png')});
   await page.keyboard.press('ArrowRight');
  }
  await page.keyboard.press('n');assert.ok(await page.locator('body').evaluate(e=>e.classList.contains('notes')));
  assert.deepEqual(errors,[],rel);
  await page.close();
 }
}

const source=fs.readFileSync(path.join(root,'assets/shablon-hakatona.html'),'utf8');
const payload={meta:{process:'Безопасность'},hero:{title:'<img src=x onerror="window.pwned=1">',facts:[]},pipeline:{in:[],run:[],doc:null},roles:[],steps:[],metrics:[],money:{formula:[],costs:[]},wins:[],limits:[],plan:[],opps:[],feedback:{scores:[],valued:[]},missing:[]};
const hostile=source.replace(/(<script id="dannye" type="application\/json">)\s*[\s\S]*?\s*(<\/script>)/,(_,a,b)=>a+'\n'+JSON.stringify(payload).replaceAll('<','\\u003c')+'\n'+b);
const hostilePath=path.join(shots,'hostile.html');fs.writeFileSync(hostilePath,hostile);
const page=await context.newPage();await page.goto('file://'+hostilePath);
assert.match(await page.locator('[data-field="title"]').textContent(),/^<img/);
assert.equal(await page.locator('[data-field="title"] img').count(),0);
assert.equal(await page.evaluate(()=>window.pwned),undefined);
await browser.close();
console.log('PASS report template: 9 screens, offline desktop/mobile, controls, safe text. Screenshots: '+shots);
