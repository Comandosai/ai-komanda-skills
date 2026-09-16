// Offline renderer tests with a minimal DOM. Not a browser/visual verification.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const html=read('pokazat-dela/assets/shablon-dashboarda.html');
const code=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
function render(data){
 const elements={root:{innerHTML:''},dannye:{textContent:JSON.stringify(data)}};
 vm.runInNewContext(code,{document:{getElementById:id=>elements[id]},setTimeout:()=>{},location:{reload(){}}});
 return elements.root.innerHTML;
}
assert.match(render(null),/Данные пока не загружены/);
const d={title:'<script>bad</script>',steps:['Вход'],mode:'тест',updated:'2026-09-16',source:'журнал',attempts:[],series:{},comparison:{comparable:false},warnings:[],cases_without_journal:[]};
assert.match(render(d),/нулевой снимок/);
assert.ok(!render(d).includes('<script>bad'));
d.attempts=[{id:'b1',case:'01',series:'baseline',synthetic:true,observed:true,complete:false,no_hands:false,touches:1,touches_known:true,cells:[{state:'vstalo',touches:1,reworks:1}],data_errors:1,tool_errors:0,acceptance:null,problems:['Не хватает цены'],uncertain:false}];
assert.match(render(d),/остановка/);
assert.match(render(d),/переделки: 1/);
assert.match(render(d),/Не хватает цены/);
const guide=read('guide/GUIDE-N5.html'), prompts=JSON.parse(read('guide/prompts.json'));
const decode=s=>s.replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&amp;','&');
for(const [id,value] of Object.entries(prompts)){
 assert.equal(decode(guide.match(new RegExp('<pre id="'+id+'">([\\s\\S]*?)</pre>'))[1]),value);
 assert.ok(guide.includes("cp('"+id+"',this)"));
}
for(const skill of ['naladit-komandu','pokazat-dela','otchet','mehanik']){
 const body=read(skill+'/SKILL.md').replace(/^---\n[\s\S]*?\n---\n/,'').trim()
  .replaceAll('assets/shablon-shemy.html','shablon-shemy.html').replaceAll('assets/shablon-dashboarda.html','shablon-dashboarda.html');
 assert.ok(read('chatgpt/'+skill+'.txt').includes(body),skill+' chat drift');
}
for(const [skill,file] of [['naladit-komandu','shablon-shemy.html'],['pokazat-dela','shablon-dashboarda.html']]) assert.equal(read(skill+'/assets/'+file),read('chatgpt/'+file));
for(const skill of ['naladit-komandu','pokazat-dela','otchet']){
 const content=read(skill+'/SKILL.md');
 for(const ref of content.matchAll(/references\/[a-z0-9-]+\.md/g)) assert.ok(fs.existsSync(path.join(root,skill,ref[0])),ref[0]);
}
console.log('PASS: offline renderer; 7 copy targets; prompt parity; 4 chat copies; 2 templates; references');
