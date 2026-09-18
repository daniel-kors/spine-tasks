# Source revisions

Задание 01 направления «База знаний и агент вопросов и ответов». Программа
сохраняет неизменяемые записи о наблюдавшихся редакциях документа. Один и тот же
файл при повторной регистрации не создаёт новую запись. Изменение содержимого
создаёт новую редакцию, а `tombstone` отмечает удаление, сохраняя историю.

## Подготовка

Выполняйте команды из каталога `intern-tasks/01-source-revisions`:

```bash
uv sync --python 3.11
```

Версии зависимостей зафиксированы в `uv.lock`. Исходные документы скопированы
без изменений из `synthetic-data/01-knowledge-base-and-qa/documents/alpha/`.
Рабочие результаты хранятся в `data/revisions.jsonl`; этот файл не добавляется
в Git.

## Ручной сценарий v1 → v2 → history

```bash
uv run python -m source_revisions.cli register --workspace alpha --source travel-policy --file data/fixtures/travel-policy-v1.md
uv run python -m source_revisions.cli register --workspace alpha --source travel-policy --file data/fixtures/travel-policy-v1.md
uv run python -m source_revisions.cli register --workspace alpha --source travel-policy --file data/fixtures/travel-policy-v2.md
uv run python -m source_revisions.cli history --workspace alpha --source travel-policy
uv run python -m source_revisions.cli tombstone --workspace alpha --source travel-policy
uv run python -m source_revisions.cli history --workspace alpha --source travel-policy
```

Первая регистрация возвращает `created`, вторая — `unchanged` с тем же
`revision_id`. Регистрация v2 возвращает `created` с новым `revision_id`.
Последняя команда показывает три записи: v1, v2 и отметку об удалении.
Повтор `tombstone` вернёт `unchanged` без новой строки. Для отдельного запуска
можно указать другой файл хранилища параметром `--store`.

## Состав пакета

- `models.py` — проверяемые и неизменяемые контракты;
- `checksum.py` — чтение файла блоками и SHA-256;
- `repository.py` — хранилища в памяти и JSONL;
- `service.py` — правило создания редакции или возврата существующей;
- `cli.py` — команды терминала без предметной логики.

## Локальные проверки

```bash
uv run ruff check .
uv run pytest -q -m 'not integration and not llm'
uv run python -m compileall -q src tests
```

Тесты покрывают повторную регистрацию, изменение содержимого, разделение рабочих
областей, отметку об удалении, ошибочную строку JSONL и неизменяемость модели.
