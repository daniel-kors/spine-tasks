# Document chunks

Задание 02 направления «База знаний и агент вопросов и ответов». Программа
разбивает UTF-8 Markdown/TXT на фрагменты и сохраняет для каждого точный диапазон
символов исходного документа. По этому диапазону можно проверить, что цитата
действительно существует в конкретной редакции.

## Подготовка

Выполняйте команды из каталога `intern-tasks/02-document-chunks`:

```bash
uv sync --python 3.11
```

Версии зависимостей зафиксированы в `uv.lock`. Документы в `data/fixtures/`
скопированы без изменений из `synthetic-data/01-knowledge-base-and-qa/documents/`.

## Разбор документа

```bash
uv run python -m document_chunks.cli parse --workspace alpha --source travel-policy --revision 11111111-1111-4111-8111-222222222222 --file data/fixtures/alpha/travel-policy-v2.md
```

Результат появится в:

```text
data/manifests/11111111-1111-4111-8111-222222222222.jsonl
```

Одна строка JSONL описывает один фрагмент: его текст, порядковый номер,
стабильный `chunk_id`, заголовок секции и позиции `char_start`/`char_end`.

## Проверка указателей

```bash
uv run python -m document_chunks.cli verify-manifest --file data/fixtures/alpha/travel-policy-v2.md --manifest data/manifests/11111111-1111-4111-8111-222222222222.jsonl
```

Команда заново читает исходный файл и для каждого фрагмента проверяет:

```python
original[char_start:char_end] == chunk.text
```

Если вручную изменить позицию или текст в манифесте, команда завершится с кодом
1 и укажет строку с несовпадением.

Для TXT укажите `--media-type text/plain`; у его фрагментов `heading` будет
равен `null`. Размер фрагмента можно изменить параметром `--max-chars`.

## Состав пакета

- `models.py` — контракты документа, фрагмента и указателя;
- `parser.py` — интерфейс разборщика и типизированные ошибки;
- `markdown_parser.py` — секции, абзацы, ограничение длины и точные позиции;
- `manifest.py` — запись, чтение и проверка JSONL;
- `cli.py` — команды `parse` и `verify-manifest`.

## Локальные проверки

```bash
uv run ruff check .
uv run pytest -q -m 'not integration and not llm'
uv run python -m compileall -q src tests
```

Тесты проверяют точность указателей, стабильность идентификаторов, Unicode,
ограничение длины, ошибки входных данных и обнаружение повреждённого манифеста.
