"""Synthetic contract tests, NOT live Claude/Gemini/Codex agent evaluations."""
import importlib.util
import json
import re
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dashboard', ROOT/'pokazat-dela/scripts/build_dashboard.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = dict(title='Тест', journal='zhurnal.md', steps=['Вход', 'Выход'], actors=['Роль', 'Проверяющий'],
                        cases=['01'], attempts=[], scope_version='1', live=False)
        self.lines = []

    def attempt(self, aid='b1', case='01', series='baseline', touches_known=True):
        folder = self.root/'dela'/case/aid
        folder.mkdir(parents=True)
        for name in ('result.md', 'check.md'):
            (folder/name).write_text('Учебный артефакт, не реальная работа', encoding='utf8')
        a = dict(id=aid, case=case, series=series, synthetic=True, observed=True,
                 touches_known=touches_known, input_hash='sha256:test-'+case, scope_version='1',
                 result=str((folder/'result.md').relative_to(self.root)), check=str((folder/'check.md').relative_to(self.root)))
        self.cfg['attempts'].append(a)
        return a

    def event(self, aid='b1', step='Вход', outcome='готово', actor='Роль', case='01', note=''):
        self.lines.append(f'2026-09-16T10:00:{len(self.lines):02d}+03:00 | {case} | {step} | {actor} | {outcome} | run={aid}; {note}')

    def success(self, aid='b1', case='01'):
        self.event(aid, case=case)
        self.event(aid, step='Выход', case=case)
        self.event(aid, step='Выход', outcome='принято', actor='Проверяющий', case=case)

    def result(self):
        return d.aggregate(self.root, self.cfg, '\n'.join(self.lines))

    def test_zero_is_not_baseline(self):
        data=self.result()
        self.assertEqual(data['attempts'], [])
        self.assertFalse(data['comparison']['comparable'])
        self.assertEqual(data['cases_without_journal'], ['01'])

    def test_fixed_names_in_attempt_folders_preserve_first_series(self):
        legacy = self.root/'dela'/'01'/'02-result.xlsx'
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b'legacy-result')
        for series, aid in [('baseline', 'first'), ('repeat', 'second')]:
            a = self.attempt(aid, series=series)
            folder = self.root/'dela'/'01'/aid
            result, check = folder/'02-result.xlsx', folder/'03-check.md'
            result.write_bytes(series.encode())
            check.write_text('accepted '+series)
            a.update(result=str(result.relative_to(self.root)), check=str(check.relative_to(self.root)))
            self.success(aid)
        data = self.result()
        self.assertEqual(legacy.read_bytes(), b'legacy-result')
        self.assertEqual((legacy.parent/'first'/'02-result.xlsx').read_bytes(), b'baseline')
        self.assertTrue(all(a['complete'] for a in data['attempts']))
        self.assertTrue(data['comparison']['comparable'])

    def test_success_requires_all_steps_and_check(self):
        a=self.attempt(); self.success()
        self.assertTrue(self.result()['attempts'][0]['no_hands'])
        (self.root/a['check']).unlink()
        self.assertFalse(self.result()['attempts'][0]['complete'])

    def test_last_step_only_not_complete(self):
        self.attempt(); self.event(step='Выход'); self.event(step='Выход',outcome='принято')
        self.assertFalse(self.result()['attempts'][0]['complete'])

    def test_prose_under_table_does_not_invalidate_complete(self):
        self.attempt(); self.success()
        self.lines.extend(['', '## Пояснение', 'Журнал заполняет роль после задачи.'])
        data = self.result()
        self.assertTrue(data['attempts'][0]['complete'])
        self.assertTrue(data['attempts'][0]['no_hands'])
        self.assertTrue(any('не таблица' in w for w in data['warnings']))

    def test_malformed_table_row_explains_uncertainty(self):
        self.attempt(); self.success()
        self.lines.append('дата | 01 | потерянное событие')
        a = self.result()['attempts'][0]
        self.assertTrue(a['uncertain'])
        self.assertFalse(a['complete'])
        self.assertTrue(any('6 колонок' in p for p in a['problems']))

    def test_unassigned_case_event_explains_uncertainty(self):
        self.attempt(); self.success()
        self.lines.append('дата | 01 | Вход | я | готово | нет номера попытки')
        self.assertTrue(any('без известной попытки' in p for p in self.result()['attempts'][0]['problems']))

    def test_manual_handoff_not_hidden(self):
        self.attempt(); self.success(); self.event(step='Вход→Выход',actor='я')
        a=self.result()['attempts'][0]
        self.assertTrue(a['complete']); self.assertFalse(a['no_hands']); self.assertEqual(a['touches'],1)

    def test_one_two_three_roles_preserve_attempt_and_count_handoffs(self):
        for count in (1, 2, 3):
            with self.subTest(roles=count):
                self.cfg['steps'] = ['Шаг '+str(i) for i in range(count)]
                self.cfg['attempts'] = []; self.lines = []
                aid = 'roles'+str(count)
                self.attempt(aid)
                for i, step in enumerate(self.cfg['steps']):
                    if i:
                        self.event(aid, step=self.cfg['steps'][i-1]+'→'+step, actor='я')
                    self.event(aid, step=step)
                self.event(aid, step=step, outcome='принято', actor='Проверяющий')
                a = self.result()['attempts'][0]
                self.assertEqual(a['id'], aid)
                self.assertTrue(a['complete'])
                self.assertEqual(a['touches'], count-1)
                self.assertEqual(a['no_hands'], count == 1)

    def test_three_roles_missing_middle_step_is_not_complete(self):
        self.cfg['steps'] = ['Первая', 'Вторая', 'Третья']
        self.attempt()
        self.event(step='Первая')
        self.event(step='Третья')
        self.event(step='Третья', outcome='принято', actor='Проверяющий')
        self.assertFalse(self.result()['attempts'][0]['complete'])

    def test_five_attempt_folders_survive_repeat_for_each_team_size(self):
        for count in (1, 2, 3):
            with self.subTest(roles=count):
                self.cfg['steps'] = ['Шаг '+str(i) for i in range(count)]
                self.cfg['attempts'] = []; self.lines = []
                preserved = {}
                for series in ('baseline', 'repeat'):
                    for n in range(5):
                        case = str(n)
                        aid = f'{series}-{count}-{n}'
                        a = self.attempt(aid, case, series)
                        path = self.root/a['result']
                        path.write_text(aid)
                        if series == 'baseline': preserved[path] = path.read_bytes()
                        for i, step in enumerate(self.cfg['steps']):
                            if i:
                                self.event(aid, step=self.cfg['steps'][i-1]+'→'+step, actor='я', case=case)
                            self.event(aid, step=step, case=case)
                        self.event(aid, step=step, outcome='принято', actor='Проверяющий', case=case)
                data = self.result()
                for path, contents in preserved.items(): self.assertEqual(path.read_bytes(), contents)
                self.assertEqual(data['series']['baseline']['complete'], 5)
                self.assertEqual(data['series']['repeat']['complete'], 5)
                self.assertTrue(data['comparison']['comparable'])
                self.assertEqual(data['comparison']['delta'], 0)

    def test_rework_and_touch_coexist(self):
        self.attempt(); self.event(); self.event(actor='я'); self.event(step='Выход'); self.event(step='Выход',outcome='принято')
        a=self.result()['attempts'][0]
        self.assertEqual(a['cells'][0]['reworks'],1); self.assertEqual(a['touches'],1)
        self.assertFalse(a['no_hands'])

    def test_missing_input_and_tool_failure_stop(self):
        for outcome in ('отказ: данные','отказ: инструмент'):
            with self.subTest(outcome=outcome):
                self.lines=[]; self.cfg['attempts']=[]
                aid=outcome.split(':')[1].strip().replace('данные','data').replace('инструмент','tool')
                self.attempt(aid); self.event(aid,outcome=outcome)
                a=self.result()['attempts'][0]
                self.assertFalse(a['complete']); self.assertEqual(a['cells'][0]['state'],'vstalo')

    def test_restart_invalidates_acceptance(self):
        self.attempt(); self.success(); self.event(step='Выход',outcome='начал')
        self.assertFalse(self.result()['attempts'][0]['complete'])

    def test_upstream_rerun_invalidates_downstream(self):
        self.attempt(); self.success(); self.event()
        self.assertFalse(self.result()['attempts'][0]['complete'])

    def test_rejection_invalidates_acceptance(self):
        self.attempt(); self.success(); self.event(step='Выход',outcome='отклонил',actor='я')
        self.assertFalse(self.result()['attempts'][0]['complete'])

    def test_unknown_touch_tracking_not_zero(self):
        self.attempt(touches_known=False); self.success()
        a=self.result()['attempts'][0]
        self.assertTrue(a['complete']); self.assertFalse(a['no_hands'])

    def test_duplicate_row_not_rework(self):
        self.attempt(); self.success(); self.lines.append(self.lines[0])
        a=self.result()['attempts'][0]
        self.assertEqual(a['cells'][0]['reworks'],0)
        self.assertTrue(a['no_hands'])
        self.assertIn('дубль', self.result()['warnings'][0])

    def test_unknown_actor_is_uncertain(self):
        self.attempt(); self.success(); self.event(actor='кто-то')
        a=self.result()['attempts'][0]
        self.assertTrue(a['uncertain']); self.assertFalse(a['complete'])

    def test_legacy_events_visible_and_not_guessed(self):
        self.attempt(); self.success(); self.lines.append('дата | 01 | Вход | я | готово | без метки')
        data=self.result()
        self.assertEqual(len(data['unassigned']),1); self.assertFalse(data['attempts'][0]['complete'])

    def test_matched_five_pairs_with_improvement(self):
        self.cfg['cases']=[]
        for n in range(5):
            case=str(n); b='b'+case; r='r'+case
            self.attempt(b,case); self.success(b,case)
            self.event(b,step='Вход→Выход',actor='я',case=case)
            self.attempt(r,case,'repeat'); self.success(r,case)
        data=self.result()
        self.assertTrue(data['comparison']['comparable'])
        self.assertEqual(data['comparison']['delta'],5)
        self.assertEqual(data['series']['baseline']['complete'],5)
        self.assertEqual(data['series']['repeat']['complete'],5)

    def test_changed_inputs_not_comparable(self):
        self.attempt(); self.success()
        a=self.attempt('r1',series='repeat'); a['input_hash']='different'; self.success('r1')
        self.assertFalse(self.result()['comparison']['comparable'])

    def test_reused_output_rejected(self):
        b=self.attempt(); self.success()
        a=self.attempt('r1',series='repeat'); a['result']=b['result']; self.success('r1')
        self.assertFalse(any(a['complete'] for a in self.result()['attempts']))

    def test_escape_pipes_and_html(self):
        self.attempt(); self.event(note=r'поле a\|b'); self.event(step='Выход'); self.event(step='Выход',outcome='принято')
        self.assertTrue(self.result()['attempts'][0]['complete'])
        self.cfg['title']='</script><script>alert(1)</script>'
        folder=self.root/'dashboard'; folder.mkdir()
        (folder/'config.json').write_text(json.dumps(self.cfg),encoding='utf8')
        (self.root/'zhurnal.md').write_text('\n'.join(self.lines),encoding='utf8')
        d.build(self.root); d.build(self.root)
        html=(folder/'index.html').read_text(encoding='utf8')
        self.assertNotIn(self.cfg['title'],html)
        self.assertEqual(len(list((folder/'snimki').glob('*.json'))),2)

    def test_path_escape_and_symlink_rejected(self):
        with self.assertRaises(ValueError): d.inside(self.root,'../secret')
        (self.root/'escape').symlink_to(self.root.parent)
        with self.assertRaises(ValueError): d.inside(self.root,'escape/secret')

    def test_participant_process_shapes(self):
        # Only shapes of participants' workflows; all events and files are synthetic.
        for i,(name,steps) in enumerate([
            ('Смета',['Снабженец','Сметчик']),
            ('БТИ',['План','КП']),
            ('Блог',['Подготовка','Автор']),
            ('Производство',['Дашборд','Аналитик смены']),
            ('Технолог',['Расчёт']),
            ('Контент',['Ядро','Согласование','Материалы'])]):
            with self.subTest(process=name):
                self.cfg['steps']=steps; self.cfg['attempts']=[]; self.lines=[]
                aid='shape'+str(i); self.attempt(aid)
                for step in steps: self.event(aid,step=step,actor='я' if step=='Согласование' else 'Роль')
                self.event(aid,step=steps[-1],outcome='принято',actor='Проверяющий')
                a=self.result()['attempts'][0]
                self.assertTrue(a['complete'])
                self.assertEqual(a['no_hands'],'Согласование' not in steps)


class PackageTests(unittest.TestCase):
    def test_guide_uses_actual_dashboard_headings(self):
        guide = (ROOT/'guide/GUIDE-N5.html').read_text()
        template = (ROOT/'pokazat-dela/assets/shablon-dashboarda.html').read_text()
        headings = re.findall(r'<h2>([^<]+)</h2>', template)
        self.assertEqual(len(headings), 6)
        for heading in headings: self.assertIn(heading, guide)
        self.assertNotIn('«что чинить»', guide.lower())
        self.assertNotIn('Пока не считаю', guide)

    def test_participant_prompts_hide_internal_series_fields(self):
        prompts = json.loads((ROOT/'guide/prompts.json').read_text())
        for key, prompt in prompts.items():
            for technical in ('baseline', 'repeat', 'trial', 'run=', 'идентификатор', 'контрольные суммы', 'зарегистрируй'):
                self.assertNotIn(technical, prompt, key)

    def test_week5_deliverables_have_no_long_dashes(self):
        for path in [ROOT/'README.md', *list((ROOT/'guide').glob('*')),
                     ROOT/'naladit-komandu/SKILL.md', ROOT/'pokazat-dela/references/dannye.md']:
            text = path.read_text()
            self.assertNotIn(chr(0x2013), text, str(path))
            self.assertNotIn(chr(0x2014), text, str(path))

    def test_seven_guide_prompts(self):
        prompts=json.loads((ROOT/'guide/prompts.json').read_text())
        self.assertEqual(set(prompts),{'p'+str(i) for i in range(1,8)})
        self.assertIn('пять',prompts['p4'])
        self.assertIn('один вопрос',prompts['p7'])

    def test_platform_contract(self):
        s=(ROOT/'naladit-komandu/SKILL.md').read_text()
        self.assertLess(s.index('### ТАКТ 3.'),s.index('### ТАКТ 9.'))
        self.assertIn('не по очереди найма',s)
        self.assertIn('Не объединяй роли из разных процессов',s)
        self.assertIn('Одна роль тоже допустима',s)
        self.assertNotIn('Только Claude Code',s)


if __name__=='__main__': unittest.main()
