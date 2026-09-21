# Ingestion runner

Задание 03 направления «База знаний и агент вопросов и ответов». Команда
обрабатывает каталог Markdown/TXT в детерминированном порядке, регистрирует
редакции, создаёт манифесты фрагментов и возвращает единый отчёт. Ошибка одного
документа не скрывает результаты остальных.

## Подготовка

Выполняйте команды из каталога `intern-tasks/03-ingestion-runner`:

```bash
uv sync --python 3.11
```

Версии зависимостей находятся в `uv.lock`. В `data/fixtures/` без изменения
скопированы два документа и пустой файл из синтетического набора направления 01.

## Продолжение после ошибки

```bash
uv run python -m ingestion_runner.cli ingest --workspace alpha --directory data/fixtures --idempotency-key demo-continue-001 --continue-on-error
```

Команда обрабатывает пути в алфавитном порядке и возвращает три элемента:
`empty` со статусом `failed`, а `remote-work` и `travel-policy-v2` со статусом
`indexed`. Для двух успешных файлов создаются манифесты в `data/manifests/`.
Полный отчёт обновляется после каждого файла в `data/reports/<run_id>.json`.

Повторите ту же команду с тем же ключом. Она вернёт прежний отчёт и тот же
`run_id`, не читая документы повторно. Затем используйте новый ключ:

```bash
uv run python -m ingestion_runner.cli ingest --workspace alpha --directory data/fixtures --idempotency-key demo-continue-002 --continue-on-error
```

Неизменившиеся корректные документы получат статус `unchanged`.

## Остановка при первой ошибке

```bash
uv run python -m ingestion_runner.cli ingest --workspace alpha --directory data/fixtures --idempotency-key demo-stop-001 --stop-on-error
```

Поскольку `empty.txt` сортируется первым, отчёт будет содержать один элемент со
статусом `failed`. Результат команды всё равно сохраняется и повторяется целиком.

## Создаваемые данные

- `data/runs.db` — итоговые отчёты и соответствие ключей повторяемости;
- `data/revisions.jsonl` — минимальный локальный реестр редакций;
- `data/manifests/<revision_id>.jsonl` — фрагменты успешных документов;
- `data/reports/<run_id>.json` — наблюдаемый ход выполнения.

Эти рабочие результаты исключены из Git. В SQLite и JSON-журналы не записывается
полный текст документов. Текст фрагментов хранится только в манифестах, где он
связан с `workspace_id`, `source_id` и `revision_id`.

## Состав пакета

- `models.py` — команды и отчёты;
- `runner.py` — порядок обработки и правила ошибок;
- `idempotency.py` — переходник SQLite за интерфейсом `IdempotencyStore`;
- `logging.py` — JSON-журналы и захватывающий list sink;
- `local_services.py` — минимальные переходники к механизмам заданий 01–02;
- `cli.py` — тонкая оболочка командной строки.

## Локальные проверки

```bash
uv run ruff check .
uv run pytest -q -m 'not integration and not llm'
uv run python -m compileall -q src tests
```

Тесты проверяют продолжение после сбоя, повторяемость ключей, статусы неизменных
файлов, изоляцию рабочих областей, границы путей, порядок событий и SQLite.
