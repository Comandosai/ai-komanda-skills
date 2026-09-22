# Комплект недели 6

Открыть GUIDE-N6.html. Полный архив участника: downloads/AI-KOMANDA-N6.zip.
Рабочие папки недели 5 не заменять. Материалы помещаются в materialy-nedeli-6.

## Состав

- content.json: единственный источник шагов и промптов; GUIDE-N6.html и prompts.json генерируются.
- instructions/: подробные API/извлечение, VPS, Hermes, платформы; рядом HTML-копии для браузера.
- assets/shablon-hakatona.html: автономный шаблон защиты, не заполненная сдача.
- scripts/: сборка страниц, нового снимка учёта, архива и проверки.
- demo/: детерминированный симулятор отдельно от живого учебного проекта.
- recording/: сценарии видео и контрольная проверка перед съёмкой.
- PROVERKA.md: факты тестирования и оставшиеся внешние проверки.

## Сборка

Из корня репозитория:

```bash
node scripts/sync-week5-chat.mjs
python3 week6/scripts/build_kit.py
python3 -m unittest discover -s week6/tests -v
python3 -m unittest discover -s week6/demo -p 'test_*.py' -v
python3 tests/test_week5.py
node tests/test-render.mjs
node tests/test_guide_copy.mjs
python3 week6/scripts/package_kit.py
```

Новый экран недели 6 не меняет старый build_dashboard.py. Читает только новый
dashboard/week6.json, пишет DASHBOARD-N6.html. Сам наличие файлов не доказывает
качество или реальность автономного запуска.

Публикация GitHub отдельно: архив локален до явной проверки версии и публикации.
Не выдавать существующую ссылку main за ссылку на ещё не опубликованный комплект.
