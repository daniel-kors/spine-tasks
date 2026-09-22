# Cognee retriever

Задание 05 направления «База знаний и агент вопросов и ответов». Проект строит
версионируемую проекцию знаний, хранит атомарную ссылку на активную версию и
выдаёт контекст через контракт задания 04. Cognee скрыт за `CogneeClient`.

Установленная и зафиксированная версия: `cognee==1.6.0`.

## Подготовка

Выполняйте команды из каталога `intern-tasks/05-cognee-retriever`:

```bash
uv sync --python 3.11
```

Скопируйте `.env.example` в `.env`. Для офлайн-режима менять значения не нужно.
Для настоящего Cognee установите `COGNEE_PROVIDER=real` и заполните
`LLM_API_KEY`. `.env` исключён из Git.

Все системные данные, кеш и журналы Cognee направляются в `.local/` до первого
импорта библиотеки. Первый реальный импорт может загрузить словарь токенизации,
поэтому настоящий режим требует разрешённого доступа к сети.

## Исходные данные проекции

Документы, карта доступа, вопросы и заглушка скопированы без изменения из
`synthetic-data/01-knowledge-base-and-qa/`. Каталог `data/fixtures/manifests/`
содержит производные JSONL-манифесты актуальных редакций. Их можно воспроизвести:

```bash
uv run python scripts/prepare_fixture_manifests.py
```

Рабочие команды никогда не изменяют эти манифесты.

## Построение и автоматическая активация

```bash
uv run python -m cognee_retriever.cli build-index --workspace alpha --manifests data/fixtures/manifests
```

Создаётся новая версия со статусом `building`. После загрузки и контрольного
поиска она становится `ready`, затем атомарно `active`. Версии и активная ссылка
хранятся в `.local/projections.db`.

Чтобы построить версию без активации:

```bash
uv run python -m cognee_retriever.cli build-index --workspace alpha --manifests data/fixtures/manifests --no-activate
uv run python -m cognee_retriever.cli activate-index --projection-id <UUID>
```

## Получение контекста

```bash
uv run python -m cognee_retriever.cli retrieve-context --workspace alpha --user demo-user --scopes all-employees --question "Какой размер суточных?"
```

Результат содержит фрагмент `travel-policy` и восстановленный `ContextReference`.
Порядок ответа клиента не меняется.

Проверка закрытого источника:

```bash
uv run python -m cognee_retriever.cli retrieve-context --workspace alpha --user demo-user --scopes all-employees --question "Какое кодовое имя прототипа?"
uv run python -m cognee_retriever.cli retrieve-context --workspace alpha --user engineer --scopes engineering --question "Какое кодовое имя прототипа?"
```

Первый вызов вернёт пустой список, второй — разрешённый `engineering-only`.

## Десять вопросов ручной проверки

```bash
uv run python -m cognee_retriever.cli manual-check
```

Команда читает готовые вопросы и создаёт `build/manual-check-results.jsonl`.
В нём нет текстов документов или ответов: только наличие ожидаемого источника,
отсутствие запрещённого, длительность и восстановимость `ContextReference`.
Офлайн-заглушка сопоставляет только точные заранее настроенные вопросы, поэтому
оценивать смысловой поиск следует с `COGNEE_PROVIDER=real`.

## Перестроение

```bash
uv run python -m cognee_retriever.cli rebuild --workspace alpha --manifests data/fixtures/manifests
```

`rebuild` всегда перечитывает исходные JSONL-манифесты и создаёт новый набор.
Если удалить производные данные клиента из `.local/` и повторить команду,
логическая база восстанавливается из манифестов. При любом сбое новая версия
становится `failed`, а прежняя активная ссылка не меняется.

## Состав пакета

- `models.py` — модели контекста и версии проекции;
- `cognee_client.py` — интерфейс, реальный ленивый переходник и офлайн-заглушка;
- `cognee_retriever.py` — преобразование результатов и проверка доступа;
- `projections.py` — построение и атомарная активация через SQLite;
- `local_paths.py` — локальные пути до импорта Cognee;
- `fake_retriever.py` — заглушка задания 04 для быстрых проверок;
- `manual_check.py` — безопасный отчёт по десяти готовым вопросам;
- `cli.py` — `build-index`, `retrieve-context`, `rebuild`, `activate-index`.

## Локальные проверки

```bash
uv run ruff check .
uv run pytest -q -m 'not integration and not llm'
uv run python -m compileall -q src tests
```

Модульные тесты используют `FakeCogneeClient` и не обращаются к сети. Они проверяют
преобразование ответа, порядок результатов, границы рабочей области и доступа,
жизненный цикл проекции, неизменность манифестов и настройку локальных путей до
первого импорта Cognee.

Проверка настоящего Cognee запускается отдельно:

```bash
uv run pytest -q -m integration
```

Без `LLM_API_KEY` она получает статус `skipped`, как требуют общие правила.
