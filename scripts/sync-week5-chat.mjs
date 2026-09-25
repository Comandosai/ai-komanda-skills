// Mechanical generation: canonical skill + references -> self-contained chat copy.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const body=s=>s.replace(/^---\n[\s\S]*?\n---\n/,'').trim();
const header=`ПЛОСКАЯ ВЕРСИЯ ДЛЯ ЧАТА БЕЗ ОБЩЕЙ ПАПКИ.
Работай по загруженным файлам и этому разговору. Путь означает логическую область;
вместо папок используй префиксы kontekst-, dela-, agenty-, vyhod-, arhiv-.
Не говори, что изменил оригинал загрузки: выдай новую версию для скачивания или
полный текст с именем. Текстовые результаты можно сохранить в .txt, HTML в .html.
Самостоятельно между чатами файлы не переходят. Живое обновление и отдельные
исполнители доступны только если у среды действительно есть такие инструменты.
Ссылки references ниже относятся к разделам ЭТОГО документа; все они включены.

`;
const deps={
 'mehanik':[],
 'naladit-komandu':['references/platformy.md','references/progony.md'],
 'pokazat-dela':['references/dannye.md'],
 'otchet':['references/nedelya-3.md','references/nedelya-5.md']
};
for(const [name,refs] of Object.entries(deps)){
 let text=header+body(read(name+'/SKILL.md'))+'\n';
 for(const ref of refs) text+='\n\n# Вложенная инструкция: '+ref+'\n\n'+body(read(name+'/'+ref))+'\n';
 if(name==='naladit-komandu') text=text.replaceAll('assets/shablon-shemy.html','shablon-shemy.html');
 if(name==='pokazat-dela') text=text.replaceAll('assets/shablon-dashboarda.html','shablon-dashboarda.html')+'\nБез доступа к scripts/build_dashboard.py используй режим снимка. Скрипт не входит в загрузки чат-пакета и не нужен для ручного подсчёта.\n';
 fs.writeFileSync(path.join(root,'chatgpt',name+'.txt'),text);
}
for(const template of ['shablon-shemy.html','shablon-dashboarda.html']){
 const skill=template.includes('shemy')?'naladit-komandu':'pokazat-dela';
 fs.copyFileSync(path.join(root,skill,'assets',template),path.join(root,'chatgpt',template));
}
