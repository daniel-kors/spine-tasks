# Направление 1. Инфраструктура базы знаний и агента вопросов и ответов

## Результат подготовки

Необходимо создать десять автономных решений. Каждое показывает один инфраструктурный механизм: хранение редакций, разбиение документов, повторяемую загрузку, контракт получения контекста, подключение Cognee, проверку ссылок на источники, разграничение доступа, HTTP-интерфейс, измерение качества и длительную переиндексацию в Temporal.

Работы 01–04 не требуют языковой модели. Работа 05 использует Cognee, но обязана
иметь программную заглушку. Работы 06–10 можно проверить без сети.

## Из каких файлов должно состоять решение

Ниже указана обязательная раскладка файлов. Можно добавлять файлы, но нельзя размещать весь код в `main.py`.


| Работа | Обязательные файлы внутри `src/<имя_пакета>/`                                      |
| ------ | ---------------------------------------------------------------------------------- |
| 01     | `models.py`, `checksum.py`, `repository.py`, `service.py`, `cli.py`                |
| 02     | `models.py`, `parser.py`, `manifest.py`, `cli.py`                                  |
| 03     | `models.py`, `runner.py`, `idempotency.py`, `logging.py`, `cli.py`                 |
| 04     | `models.py`, `contracts.py`, `fake_retriever.py`, `demo.py`                        |
| 05     | `models.py`, `cognee_client.py`, `cognee_retriever.py`, `projections.py`, `cli.py` |
| 06     | `models.py`, `composer.py`, `validator.py`, `service.py`                           |
| 07     | `models.py`, `policy.py`, `authorized_retriever.py`, `audit.py`                    |
| 08     | `schemas.py`, `service.py`, `dependencies.py`, `routes.py`, `main.py`              |
| 09     | `models.py`, `checks.py`, `runner.py`, `report.py`, `cli.py`                       |
| 10     | `models.py`, `workflow.py`, `activities.py`, `worker.py`, `starter.py`             |


Для каждого задания создайте минимум два файла проверок:

- `tests/test_<основная_логика>.py` — быстрые модульные проверки;
- `tests/test_<внешняя_граница>.py` — проверка JSONL, SQLite, HTTP, Cognee или
Temporal в зависимости от задания.



## Как выполнять каждое задание

Не пытайтесь написать всё решение сразу. Используйте одинаковую последовательность:

1. Создайте каталог решения и установите перечисленные библиотеки.
2. Скопируйте в решение нужные файлы из
   `synthetic-data/01-knowledge-base-and-qa/`, сохранив их имена и содержимое.
3. Создайте модели и убедитесь, что неверный пример ими отклоняется.
4. Создайте интерфейс между основной логикой и внешней библиотекой.
5. Напишите первую падающую проверку из условия.
6. Реализуйте минимальный код, чтобы эта проверка прошла.
7. По одному добавьте остальные сценарии ошибок и повторного запуска.
8. Создайте командную или HTTP-оболочку только после готовности основной логики.
9. Выполните ручной сценарий из раздела «Как выглядит готовое решение».
10. Запустите все команды проверки из общего README на чистом каталоге.



## Готовые синтетические исходные данные

Все исходные данные уже находятся в
`synthetic-data/01-knowledge-base-and-qa/`. Не придумывайте и не набирайте их
заново: точное содержимое файлов является частью постановки и используется в
ожидаемых результатах.

Перед началом задания прочитайте
`synthetic-data/01-knowledge-base-and-qa/README.md`. Для заданий 01–03 копируйте
нужные документы из `documents/` в `data/fixtures/`. Для заданий 04–08 используйте
`access-map.json`, `retriever/fake-results.json` и документы. Для задания 09
используйте готовый файл `evals/v1.jsonl`. Для ручной проверки Cognee предназначен
`questions/manual-check.jsonl`.

В наборе уже определены две редакции `travel-policy`, документы рабочих областей
`alpha` и `beta`, закрытый источник `engineering-only`, пустой файл и намеренно
повреждённая строка JSONL. Файл `access-map.json` задаёт рабочую область,
идентификатор редакции, группу доступа и признак актуальной редакции. Эти значения
нельзя заменять случайными данными в проверках.

---



## Задание 01. Хранилище неизменяемых редакций



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'typer>=0.12,<1'
uv add --dev 'pytest>=8,<9' 'ruff>=0.6,<1'
```

`hashlib.sha256()` вычисляет контрольную сумму, `pathlib.Path` читает файл, Pydantic
проверяет и сериализует контракт, Typer превращает обычные функции в команды.

### Минимальный работающий пример

```python
from hashlib import sha256
from pathlib import Path

def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while block := stream.read(64 * 1024):
            digest.update(block)
    return digest.hexdigest()
```

Сначала напишите проверку этой функции, затем хранилище. Команда Typer не должна
содержать бизнес-логику: она разбирает параметры, вызывает `register_file` и
печатает `result.model_dump_json(indent=2)`.

### Ситуация

Файл может измениться, но старый ответ должен оставаться объяснимым. Нужно
хранить не только «последний текст», а всю историю наблюдавшихся версий.

### Как выглядит готовое решение

После запуска команды регистрации в `data/revisions.jsonl` появляется одна
строка JSON. Повтор той же команды не меняет файл. После изменения документа
появляется вторая строка с новым `revision_id`, но тем же `source_id`. Команда
`history` печатает обе редакции по времени. В `service.py` находится правило
«создавать или вернуть существующую редакцию», а `repository.py` отвечает только
за чтение и запись. Это разделение наставник проверяет при просмотре кода.

### Что создать

Отдельный пакет `source-revisions` с командной программой и JSONL-хранилищем.

```text
01-source-revisions/
  pyproject.toml
  src/source_revisions/
    models.py
    checksum.py
    repository.py
    service.py
    cli.py
  tests/
    test_service.py
    test_repository.py
  data/fixtures/
```



### Обязательные контракты

```python
class SourceRevision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    revision_id: UUID
    workspace_id: str
    source_id: str
    checksum_sha256: str
    media_type: str
    original_path: str
    observed_at: datetime
    is_tombstone: bool = False

class RegisterResult(BaseModel):
    status: Literal["created", "unchanged"]
    revision: SourceRevision

class RevisionRepository(Protocol):
    def find_by_checksum(
        self, workspace_id: str, source_id: str, checksum: str
    ) -> SourceRevision | None: ...
    def save(self, revision: SourceRevision) -> None: ...
    def history(self, workspace_id: str, source_id: str) -> list[SourceRevision]: ...
```



### Пошаговая реализация

1. Создайте модели со временем в часовом поясе UTC и запретом неизвестных полей.
2. Реализуйте чтение файла блоками и SHA-256 без загрузки всего файла в память.
3. Сделайте `InMemoryRevisionRepository`.
4. Напишите `register_file(workspace_id, source_id, path, media_type)`.
5. При первом вызове создавайте UUID и объект редакции.
6. При повторе с той же контрольной суммой возвращайте `unchanged` и прежнюю редакцию.
7. При изменении содержимого создавайте новую редакцию, не удаляя старую.
8. Сделайте `JsonlRevisionRepository`: одна строка JSON — одна редакция.
9. Добавьте команды `register`, `history` и `tombstone`.
10. В README приведите полный сценарий v1 → v2 → history.



### Команды демонстрации

```bash
uv run python -m source_revisions.cli register \
  --workspace alpha --source travel-policy --file data/fixtures/travel-policy-v1.md
uv run python -m source_revisions.cli register \
  --workspace alpha --source travel-policy --file data/fixtures/travel-policy-v2.md
uv run python -m source_revisions.cli history \
  --workspace alpha --source travel-policy
```



### Обязательные тесты

- один и тот же файл дважды даёт одну редакцию;
- изменение одного символа создаёт вторую редакцию;
- одинаковый идентификатор источника в двух рабочих областях имеет разную историю;
- tombstone не удаляет предыдущие записи;
- повреждённая JSONL-строка даёт понятную ошибку с номером строки;
- объект редакции нельзя изменить после создания.

Минимальный тест, который должен появиться первым:

```python
def test_same_content_is_registered_once(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("Правило", encoding="utf-8")
    repository = InMemoryRevisionRepository()
    service = RevisionService(repository)

    first = service.register_file("alpha", "policy", path, "text/markdown")
    second = service.register_file("alpha", "policy", path, "text/markdown")

    assert first.status == "created"
    assert second.status == "unchanged"
    assert second.revision.revision_id == first.revision.revision_id
    assert len(repository.history("alpha", "policy")) == 1
```



### Готово, если

Командная программа показывает две содержательные редакции и отметку об удалении
в правильном порядке;
повторный запуск не создаёт дубликатов; все тесты проходят.

### Контрольные вопросы

1. Почему идентификатор источника и контрольная сумма решают разные задачи?
2. Почему путь к файлу недостаточен как идентификатор источника?
3. Что изменится при переносе JSONL в SQL-хранилище?

---



## Задание 02. Разборщик документов и стабильные ссылки на фрагменты



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'typer>=0.12,<1'
uv add --dev 'pytest>=8,<9' 'hypothesis>=6,<7'
# Только для необязательного PDF-этапа:
uv add 'pypdf>=5,<7'
```

Основная версия намеренно не использует готовый разделитель текста: при реализации нужно понять,
откуда берутся границы фрагментов. Hypothesis генерирует тексты с символами
Unicode и помогает поймать
ошибки индексов, которые не видны на ASCII.

### Начальная заготовка разборщика

```python
class DocumentParser(Protocol):
    def parse(self, document: SourceDocument) -> tuple[ParsedChunk, ...]: ...

class MarkdownParser:
    def __init__(self, max_chars: int = 600) -> None:
        self.max_chars = max_chars

    def parse(self, document: SourceDocument) -> tuple[ParsedChunk, ...]:
        # TODO: sections -> paragraphs -> chunks -> locators
        raise NotImplementedError
```

После создания каждого фрагмента выполняйте защитную проверку:

```python
assert original[locator.char_start:locator.char_end] == chunk.text
```



### Ситуация

Ответ должен ссылаться не просто на документ, а на проверяемый фрагмент
конкретной ревизии.

### Как выглядит готовое решение

Команда разбора получает путь к документу и идентификатор редакции, создаёт
`data/manifests/<revision_id>.jsonl` и печатает число фрагментов. Каждая строка
содержит текст и его начало/конец. Команда проверки открывает исходный файл,
вырезает указанный диапазон и сравнивает его с сохранённым текстом. Если 
вручную изменить `char_start`, команда должна завершиться с ненулевым кодом.

Рекомендуемые файлы: `models.py`, `markdown_parser.py`, `manifest.py`, `cli.py`.

### Что создать

Пакет `document-chunks`, который разбирает Markdown/TXT и создаёт описание фрагментов в JSON.

### Обязательные модели

```python
class TextLocator(BaseModel):
    heading: str | None
    char_start: int
    char_end: int

class ParsedChunk(BaseModel):
    chunk_id: str
    workspace_id: str
    source_id: str
    revision_id: UUID
    ordinal: int
    text: str
    locator: TextLocator
```

Идентификатор фрагмента `chunk_id` однозначно рассчитывается из идентификатора
редакции, порядкового номера и текста.

### Пошаговая реализация

1. Прочитайте файл UTF-8, сохранив исходную строку без изменения позиций символов.
2. Выделите Markdown-заголовки и секции.
3. Разбивайте длинную секцию по абзацам с пределом 600 символов.
4. Не разрывайте слово посередине.
5. Для каждого фрагмента вычислите `char_start` и `char_end` в оригинальном тексте.
6. Проверьте инвариант `original[start:end] == chunk.text`.
7. Запишите описание фрагментов в JSONL.
8. Добавьте `verify-manifest`, перечитывающий оригинал и проверяющий все указатели.
9. Для TXT используйте `heading=None`.
10. Ошибки декодирования и пустые файлы оформите типизированными исключениями.



### Обязательные тесты

- каждый locator возвращает точный текст;
- повторный разбор создаёт те же идентификаторы фрагментов;
- два одинаковых абзаца в разных местах имеют разные ordinal/locator;
- символы Unicode и переносы строк не ломают позиции;
- фрагмент не превышает ограничение, кроме одного неделимого слова;
- пустой файл не создаёт фиктивный фрагмент.

Добавьте проверку общего свойства:

```python
@given(st.text(min_size=1).filter(lambda value: "\x00" not in value))
def test_locator_round_trip(text: str) -> None:
    chunks = MarkdownParser(max_chars=80).parse(make_document(text))
    for chunk in chunks:
        assert text[chunk.locator.char_start:chunk.locator.char_end] == chunk.text
```



### Готово, если

`verify-manifest` успешно проверяет все исходные примеры, а ручное изменение описания
делает проверку красной.

### Усложнение

Добавьте разборщик PDF, где указатель содержит номер страницы. Библиотека для PDF
должна быть скрыта за интерфейсом `DocumentParser`.

---



## Задание 03. Повторяемая загрузка каталога документов



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'typer>=0.12,<1' 'aiosqlite>=0.20,<1' \
  'structlog>=24,<26'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```

`aiosqlite` используется только в переходнике к базе данных. Таблица защиты от повторов:

```sql
CREATE TABLE command_results (
  workspace_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  receipt_json TEXT NOT NULL,
  PRIMARY KEY (workspace_id, idempotency_key)
);
```

Запись отчёта и результата защиты от повторов выполняйте в одной транзакции. `structlog`
настройте с `JSONRenderer`; тестируйте события через захватывающий list sink, а не
через сравнение строк консоли.

### Ситуация

Нужно обработать каталог из многих документов. Падение одного файла не должно
ломать остальные, а повторный запуск — создавать дубликаты.

### Как выглядит готовое решение

Вход — каталог из трёх файлов. Выход — один итоговый отчёт с тремя элементами и
по одному файлу описания фрагментов на успешно обработанный документ. Сведения о
повторных командах лежат в `data/runs.db`. Если один файл повреждён, итоговый
отчёт содержит два успеха и одну понятную ошибку. Полный текст документов в базе
команд и журналах отсутствует.

Рекомендуемые файлы: `runner.py`, `idempotency.py`, `models.py`, `logging.py`,
`cli.py`.

### Что создать

Пакет `ingestion-runner`, использующий интерфейсы заданий 01–02 либо их
минимальные локальные копии.

### Контракты

```python
class IngestCommand(BaseModel):
    workspace_id: str
    directory: Path
    idempotency_key: str

class ItemReceipt(BaseModel):
    source_id: str
    status: Literal["indexed", "unchanged", "failed"]
    revision_id: UUID | None
    chunk_count: int
    error_code: str | None

class IngestionReceipt(BaseModel):
    run_id: UUID
    workspace_id: str
    items: tuple[ItemReceipt, ...]
```



### Пошаговая реализация

1. Обнаруживайте только `.md` и `.txt`; сортируйте пути для детерминизма.
2. Запретите symlink, ведущий за пределы входного каталога.
3. На каждый файл вызывайте службу редакций, затем разборщик.
4. Сохраняйте описания фрагментов только после успешного разбора.
5. После каждого файла дописывайте отчёт, чтобы не потерять ход выполнения.
6. Сохраняйте соответствие ключа повторяемости и итогового отчёта в SQLite.
7. При повторе команды возвращайте прежний отчёт без новой обработки.
8. Добавьте `--continue-on-error` для продолжения после ошибки и отдельный режим
  остановки при первой ошибке.
9. Пишите журналы JSON: идентификатор запуска, рабочая область, источник, этап,
  длительность и состояние.
10. Никогда не записывайте полный текст документов в лог.



### Обязательные тесты

- три правильных файла создают три элемента отчёта;
- один битый файл в режиме продолжения не мешает двум правильным;
- повторный ключ защиты от повторов возвращает тот же идентификатор запуска;
- новый ключ и неизменные файлы дают `unchanged`;
- path traversal/symlink отклоняется;
- событие о готовности описания не создаётся до успешного разбора.

Проверка сбоя строится без подмены внутренностей: передайте `FailingParser`,
который падает только для `broken.md`. После вызова проверьте три `ItemReceipt` и
отсутствие описания фрагментов для битого файла. SQLite создавайте как `tmp_path / "runs.db"`,
а не используйте общую базу разработчика.

### Готово, если

После искусственного сбоя можно повторить команду и получить целостный,
объяснимый результат без дубликатов.

---



## Задание 04. Контракт получения контекста и программная заглушка



### Зачем это задание

В следующих заданиях контекст будет получать Cognee. Прикладной код не должен
знать, какие функции есть у Cognee и в каком виде библиотека возвращает данные.
Поэтому сначала нужно определить собственные модели и интерфейс.

Программная заглушка возвращает заранее подготовленный результат для конкретного
вопроса. Она нужна для проверки остальных частей системы без Cognee и языковой
модели. Обработку запроса и выбор подходящих фрагментов позднее полностью возьмёт
на себя Cognee.

### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```



### Как выглядит готовое решение

В `demo.py` создаётся `FakeRetriever`. Для вопроса «Какой размер суточных?» ему
заранее назначается один фрагмент из документа о командировках. Для неизвестного
вопроса заглушка возвращает пустой результат. Для специального вопроса заглушка
может выбросить заданное исключение — так в будущих заданиях будет проверяться
поведение при недоступности Cognee.

Запуск `demo.py` должен напечатать:

```text
Найдено фрагментов: 1
Источник: travel-policy
Редакция: <UUID>
Текст: С 1 сентября суточные ... 1200 рублей в день.
```



### Обязательные модели

```python
class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str
    user_id: str
    scopes: frozenset[str]
    text: str = Field(min_length=1, max_length=2000)


class ContextReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    revision_id: UUID
    chunk_id: str
    locator: dict[str, str | int | None]


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    required_scope: str
    text: str
    reference: ContextReference


class RetrievalResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chunks: tuple[RetrievedChunk, ...]
    strategy: str
    index_version: str


class Retriever(Protocol):
    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...
```

В модели результата нет числового показателя положения фрагмента. Прикладному коду
нужны сам фрагмент и проверяемая ссылка на источник.

### Реализация заглушки

Создайте `fake_retriever.py`:

```python
class FakeRetriever:
    def __init__(
        self,
        answers: dict[str, RetrievalResult],
        errors: dict[str, Exception] | None = None,
    ) -> None:
        self.answers = answers
        self.errors = errors or {}
        self.received_queries: list[RetrievalQuery] = []

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        self.received_queries.append(query)
        if query.text in self.errors:
            raise self.errors[query.text]
        return self.answers.get(
            query.text,
            RetrievalResult(
                chunks=(),
                strategy="configured-fake",
                index_version="fake-v1",
            ),
        )
```

Заглушка не должна открывать файлы, подключаться к базе данных или анализировать
текст вопроса. Она только возвращает настроенный результат.

### Пошаговая реализация

1. Создайте `models.py` и перенесите туда четыре Pydantic-модели.
2. Создайте `contracts.py` с интерфейсом `Retriever`.
3. Создайте `fake_retriever.py` по приведённой заготовке.
4. Подготовьте функции `travel_chunk()` и `security_chunk()` в
  `tests/factories.py`.
5. Настройте заглушку для двух известных вопросов и одного исключения.
6. Создайте `demo.py`, который вызывает заглушку и печатает источник и текст.
7. Напишите общие проверки интерфейса в `tests/test_retriever_contract.py`.
8. Не добавляйте обработку текста вопроса: это ответственность Cognee.



### Обязательные проверки

- правильный вопрос возвращает заранее назначенный фрагмент;
- неизвестный вопрос возвращает пустой `RetrievalResult`;
- настроенная ошибка действительно выбрасывается;
- заглушка сохраняет полученный `RetrievalQuery` в `received_queries`;
- у каждого фрагмента есть рабочая область и `ContextReference`;
- пустой вопрос и неизвестное поле отклоняются Pydantic;
- модели результата нельзя изменить после создания;
- прикладной код импортирует `Retriever`, но не импортирует Cognee.

Пример первой проверки:

```python
async def test_configured_question_returns_chunk() -> None:
    expected = result_with(travel_chunk())
    retriever = FakeRetriever({"Какой размер суточных?": expected})

    actual = await retriever.retrieve(make_query("Какой размер суточных?"))

    assert actual == expected
    assert retriever.received_queries[0].workspace_id == "alpha"
```



### Готово, если

`demo.py` выдаёт заранее подготовленный фрагмент, а все проверки проходят. В
пакете есть только контракт и управляемая заглушка, без самостоятельной обработки
текста вопроса.

---



## Задание 05. Подключение Cognee и перестраиваемая проекция



### Библиотеки и установка

```bash
uv add 'cognee>=1,<2' 'pydantic-settings>=2,<3' 'aiosqlite>=0.20,<1'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```

После установки зафиксируйте реально разрешённую версию командой
`uv lock`. Секрет положите в `.env`, а в Git добавьте только `.env.example`.

### Как работает Cognee

`remember()` принимает текст или файлы, создаёт фрагменты, векторные представления
и графовую проекцию. `recall()` извлекает ответ или найденный контекст. Чтобы
увидеть работу именно поиска, используйте `SearchType.CHUNKS`, а не готовый ответ
языковой модели:

```python
import asyncio
import cognee
from cognee import SearchType

async def demo() -> None:
    await cognee.remember(
        ["Суточные составляют 1200 рублей."],
        dataset_name="alpha_projection_v1",
        self_improvement=False,
    )
    chunks = await cognee.recall(
        query_text="Какой размер суточных?",
        query_type=SearchType.CHUNKS,
        datasets=["alpha_projection_v1"],
    )
    for chunk in chunks:
        print(chunk["id"], chunk["text"], chunk["chunk_index"])

asyncio.run(demo())
```

Ожидается фрагмент с текстом `1200 рублей`. Ответ Cognee преобразуется внутри
`CogneeRetriever`; остальная программа всегда получает ваш `RetrievalResult`.

### Хранение данных внутри каталога решения

До первого `import cognee` установите абсолютные пути:

```python
local = Path(".local").resolve()
os.environ["SYSTEM_ROOT_DIRECTORY"] = str(local / "system")
os.environ["DATA_ROOT_DIRECTORY"] = str(local / "data")
os.environ["CACHE_ROOT_DIRECTORY"] = str(local / "cache")
os.environ["COGNEE_LOGS_DIR"] = str(local / "logs")
```

Это важно протестировать отдельным subprocess-тестом: импорт Cognee до настройки
может уже прочитать configuration.

### Ситуация

Нужно подключить готовый механизм получения контекста Cognee к контракту из
задания 04. Самостоятельно реализовывать поиск или менять порядок результатов не
нужно. Индекс Cognee не считается источником истины: его можно удалить и заново
построить из сохранённых описаний фрагментов.

### Как выглядит готовое решение

`build-index` создаёт новую запись о версии представления знаний со статусом
`building`, передаёт тексты в Cognee и только после успешной проверки меняет
статус на `active`. `retrieve-context` читает имя активного набора из SQLite и возвращает
модели задания 04. При ошибке построения прежняя версия остаётся
активной. Удаление `.local/` и повторное построение восстанавливает поиск из
файлов описания фрагментов.

### Что создать

Пакет `cognee-retriever` с командами `build-index`, `retrieve-context`, `rebuild` и
`activate-index`.

### Пошаговая реализация

1. Добавьте `cognee` и закрепите версию в lock-файле.
2. Все каталоги данных, кеша и журналов направьте внутрь `.local/` решения.
3. Создайте `ProjectionVersion`: идентификатор, имя набора Cognee, идентификаторы
  редакций источников, состояние, время создания и описание ошибки.
4. Прочитайте описания фрагментов; для каждого текста добавьте сведения, позволяющие
  восстановить `ContextReference`.
5. Постройте отдельный набор Cognee для новой версии проекции.
6. Не делайте этот набор активным до полного успеха.
7. Реализуйте `CogneeRetriever` по контракту задания 04.
8. Проверяйте рабочую область и группу доступа до выдачи результата вызывающему коду.
9. Реализуйте атомарно изменяемую ссылку на активную версию в SQLite.
10. Команда `rebuild` всегда заново читает основные описания фрагментов.
11. Сбой rebuild оставляет старую активную версию.
12. Программная заглушка из задания 04 должна оставаться доступной для быстрых
  проверок без Cognee и языковой модели.



### Ручная проверка Cognee

Используйте десять готовых вопросов из
`synthetic-data/01-knowledge-base-and-qa/questions/manual-check.jsonl`:

- четыре вопроса, ответ на которые есть в документах;
- два вопроса, сформулированных другими словами;
- два вопроса, ответа на которые нет;
- два вопроса к закрытому документу.

Для каждого вопроса сохраните только следующие сведения: вернулся ли ожидаемый
источник, отсутствует ли запрещённый источник, сколько занял вызов и можно ли
восстановить `ContextReference`. Порядок, полученный от Cognee, оставляйте без
изменений.

### Обязательные тесты

- набор контрактных проверок проходит для переходника Cognee в отдельном режиме
проверки настоящей библиотеки;
- модульные проверки по умолчанию используют заглушку;
- приложение не импортирует `cognee` напрямую;
- неудачное перестроение не меняет активную версию;
- перестроение не изменяет описания фрагментов и редакции источников;
- запрещённая группа доступа отсутствует в выданном результате.

Разделите suite:

```python
@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("LLM_API_KEY"), reason="LLM_API_KEY is not configured")
async def test_real_cognee_returns_expected_chunk(tmp_path: Path) -> None:
    ...

async def test_adapter_maps_fake_cognee_payload() -> None:
    client = FakeCogneeClient([{"id": "c1", "text": "1200 рублей", "chunk_index": 0}])
    result = await CogneeRetriever(client, metadata_store).retrieve(query())
    assert result.chunks[0].reference.chunk_id == "c1"
```

Не подменяйте внутренности глобального модуля Cognee во всех проверках. Введите
маленький интерфейс `CogneeClient` с методами `remember()` и `recall()` и
подставляйте заглушку.

### Готово, если

Можно удалить `.local/index`, выполнить перестроение из описаний фрагментов и получить ту же
логическую базу знаний. Без ключа поставщика модели все модульные проверки
остаются успешными.

---



## Задание 06. Проверка ответа и ссылок на источники



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3'
uv add --optional llm 'openai>=1,<3'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```

Переходник для совместимого с OpenAI программного интерфейса — необязательный
внешний слой. Основной алгоритм
валидации является обычной чистой функцией и тестируется без модели.

### Как разделить компоненты

```python
class AnswerComposer(Protocol):
    async def compose(
        self, question: str, chunks: tuple[RetrievedChunk, ...]
    ) -> DraftAnswer: ...

def validate_answer(
    draft: DraftAnswer,
    available: tuple[RetrievedChunk, ...],
) -> ValidatedAnswer:
    by_id = {item.reference.chunk_id: item for item in available}
    # TODO: validate every claim, collect references or abstain
```

Заглушка составителя ответа принимает словарь `question -> DraftAnswer`. Переходнику
языковой модели передавайте нумерованные фрагменты (`C1`, `C2`) и требуйте JSON
заданной структуры,
но не доверяйте IDs до выполнения `validate_answer`.

### Ситуация

Генератор текста может сослаться на несуществующий фрагмент или ответить без
доказательств. Нужен отдельный проверяемый слой.

### Как выглядит готовое решение

`compose.py` создаёт предварительный ответ, а `validate.py` независимо решает,
можно ли его показать. На вход проверяющей функции подаются только
предварительный ответ и найденные фрагменты. На выходе всегда одно из двух:
проверенный ответ со ссылками либо отказ с кодами причин. В проверяющем модуле нет
вызова языковой модели.

### Контракты

```python
class Claim(BaseModel):
    text: str
    citation_ids: tuple[str, ...]

class DraftAnswer(BaseModel):
    claims: tuple[Claim, ...]
    summary: str

class ValidatedAnswer(BaseModel):
    status: Literal["answered", "abstained"]
    answer_text: str | None
    citations: tuple[ContextReference, ...]
    reasons: tuple[str, ...]
```



### Пошаговая реализация

1. Создайте интерфейс `AnswerComposer` и заглушку `FakeAnswerComposer`.
2. Заглушка принимает найденные фрагменты и возвращает заранее заданные утверждения.
3. Проверяющий модуль убеждается, что каждая ссылка существует среди полученных фрагментов.
4. Утверждение без citation считается неподтверждённым.
5. Ответ, в котором все утверждения не подтверждены, превращается в отказ отвечать.
6. При частичном покрытии выберите и опишите правило: удалить неподтверждённые
  утверждения или вернуть весь ответ на проверку человеком.
7. Добавьте правило актуальности: при двух редакциях одного источника используется
  только новейшая доступная.
8. Отдельно проверяйте, что цитируемая выдержка действительно существует во фрагменте.
9. Составитель ответа на основе языковой модели сделайте необязательным переходником
  со структурированным результатом.
10. Инструкция внутри документа никогда не передаётся как system instruction.



### Обязательные тесты

- пустой результат поиска приводит к отказу отвечать;
- выдуманный идентификатор фрагмента отклоняется;
- одно утверждение с двумя правильными ссылками принимается;
- старая ревизия при наличии новой помечается stale;
- вредоносный пример «игнорируй правила» остаётся обычным текстом источника;
- заглушка составителя ответа обеспечивает полную проверку без сети.

Минимальный negative test:

```python
def test_unknown_citation_causes_abstention() -> None:
    draft = DraftAnswer(
        claims=(Claim(text="Суточные — 5000", citation_ids=("missing",)),),
        summary="Суточные — 5000",
    )
    result = validate_answer(draft, available=(known_chunk(),))
    assert result.status == "abstained"
    assert "UNKNOWN_CITATION" in result.reasons
```



### Готово, если

Ни один результат со статусом `answered` не содержит утверждения без доступной
правильной ссылки.

---



## Задание 07. Шлюз доступа к знаниям



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'structlog>=24,<26'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```

Здесь не используется готовая библиотека разграничения доступа: цель — создать и
проверить единую точку применения правил. `structlog` передаёт события безопасности
в программируемый приёмник.

### Начальная заготовка обёртки

```python
class AuthorizedRetriever:
    def __init__(self, inner: Retriever, policy: AccessPolicy, audit: AuditSink):
        self.inner = inner
        self.policy = policy
        self.audit = audit

    async def retrieve(self, subject: Subject, text: str) -> RetrievalResult:
        raw = await self.inner.retrieve(to_query(subject, text))
        allowed: list[RetrievedChunk] = []
        for chunk in raw.chunks:
            decision = self.policy.can_read(subject, chunk)
            if decision.allowed:
                allowed.append(chunk)
            else:
                self.audit.record(denied_event(subject, chunk, decision))
        return raw.model_copy(update={"chunks": tuple(allowed)})
```

Сделайте `LeakyRetriever`, который всегда возвращает закрытый фрагмент. Он
доказывает, что шлюз действительно защищает данные, включая ошибочную работу
внутренней службы получения контекста.

### Ситуация

Даже корректную службу получения контекста нельзя вызывать без централизованной
проверки доступа.

### Как выглядит готовое решение

Готовая программа оборачивает любую службу получения контекста в
`AuthorizedRetriever`.
Намеренно неисправная служба возвращает закрытый документ, но внешний вызывающий
код получает пустой список. Одновременно в `security-events.jsonl` появляется
запись с идентификатором документа и причиной запрета, но без закрытого текста.

### Что создать

`access-gateway` — обёртка над любой реализацией `Retriever`.

### Контракты

```python
class Subject(BaseModel):
    user_id: str
    workspace_id: str
    scopes: frozenset[str]

class AccessDecision(BaseModel):
    allowed: bool
    reason_code: str
    policy_version: str

class AccessPolicy(Protocol):
    def can_read(self, subject: Subject, chunk: RetrievedChunk) -> AccessDecision: ...
```



### Пошаговая реализация

1. Реализуйте правило «по умолчанию доступ запрещён».
2. Шлюз требует сведения о пользователе, сам формирует запрос контекста и
  перепроверяет каждый возвращённый фрагмент.
3. Если внутренняя служба получения контекста вернула чужой фрагмент, шлюз удаляет его и
  создаёт запись проверки безопасности.
4. Запись содержит идентификаторы и код причины, но не текст закрытого фрагмента.
5. Добавьте версию правил в служебные сведения результата.
6. Сделайте специально неисправную реализацию `Retriever` для проверки защиты.
7. Добавьте групповую проверку без изменения правила «по умолчанию доступ запрещён».



### Обязательные тесты

- пользователь `all-employees` не видит `engineering`;
- инженер видит обе группы доступа;
- пользователь рабочей области beta не видит alpha;
- неисправная реализация `Retriever` не приводит к утечке;
- отсутствие пользователя или групп не означает полный доступ;
- событие безопасности не содержит закрытый текст.



### Готово, если

Проверка с намеренно «дырявой» службой получения контекста возвращает ноль
закрытых фрагментов и создаёт событие аудита.

---



## Задание 08. Служба вопросов на FastAPI



### Библиотеки и установка

```bash
uv add 'fastapi>=0.115,<1' 'uvicorn[standard]>=0.34,<1' \
  'pydantic-settings>=2,<3' 'structlog>=24,<26'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2' 'httpx>=0.27,<1'
```



### Как работает FastAPI в этой работе

Маршрутизатор преобразует HTTP JSON в `AskRequest`, зависимость возвращает уже
собранную службу `AskQuestion`, а обработчик исключений преобразует прикладную
ошибку в HTTP-ответ.

```python
@router.post("/api/v1/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    service: Annotated[AskQuestion, Depends(get_ask_service)],
) -> AskResponse:
    return await service.execute(request)
```

Запуск:

```bash
uv run uvicorn qa_api.main:app --reload --port 8080
curl -s http://127.0.0.1:8080/health/ready
curl -s -X POST http://127.0.0.1:8080/api/v1/ask \
  -H 'Content-Type: application/json' \
  -d '{"workspace_id":"alpha","user_id":"u-1","scopes":["all-employees"],"question":"Какой размер суточных?","request_id":"r-1"}'
```



### Проверка FastAPI без запуска сетевого порта

```python
async def test_ask_returns_citation(app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/ask", json=valid_request())
    assert response.status_code == 200
    assert response.json()["citations"][0]["source_id"] == "travel-policy"
```

В подготовленном объекте `app` подставляйте службы-заглушки через
`app.dependency_overrides`.

### Ситуация

Нужно предоставить готовый HTTP-интерфейс поверх получения контекста, составления
и проверки ответа.

### Как выглядит готовое решение

Сервер запускается одной командой. Первый запрос возвращает подтверждённый ответ,
второй — отказ из-за отсутствия сведений, третий — не раскрывает документ другой
рабочей области. В `main.py` только создаётся приложение, в `routes.py` находятся
HTTP-методы, а последовательность получения контекста и проверки живёт в `service.py`.
Автоматические проверки вызывают приложение в памяти и не запускают порт.

### Адрес HTTP-метода

`POST /api/v1/ask`

Тело запроса:

```json
{
  "workspace_id": "alpha",
  "user_id": "u-17",
  "scopes": ["all-employees"],
  "question": "За сколько дней подать заявку?",
  "request_id": "demo-001"
}
```

Ответ должен содержать `status`, `answer`, `citations`, `index_version`,
`policy_version`, `trace_id`, `as_of` и `reasons`.

### Пошаговая реализация

1. Создайте прикладную службу `AskQuestion`, не зависящую от FastAPI.
2. Передайте шлюз, составитель, проверяющий модуль и часы через конструктор.
3. Настройте Pydantic `extra="forbid"`.
4. Добавьте единый вид ошибки: код, сообщение, идентификатор трассировки и признак
  допустимости повторной попытки.
5. Реализуйте защиту от повторов в памяти по `request_id`.
6. Ограничьте длину вопроса и число групп доступа.
7. Добавьте ограничение времени ожидания внешнего составителя ответа.
8. Не возвращайте стек вызовов и внутренние инструкции модели.
9. Реализуйте `/health/live` и `/health/ready`; готовность режима с заглушками не требует
  языковой модели.
10. Добавьте минимальную HTML-страницу как необязательное усложнение.



### Обязательные проверки HTTP-интерфейса

- успешный сценарий возвращает ссылку с точным указателем;
- неизвестное поле даёт 422;
- пустой вопрос даёт 422;
- повтор идентификатора запроса возвращает логически тот же ответ;
- чужая рабочая область не возвращает данные;
- превышение времени ожидания составителя даёт управляемый ответ 503 или отказ
отвечать согласно выбранному правилу;
- идентификатор трассировки присутствует и в ответе, и в журналах.



### Готово, если

Наставник может запустить сервер одной командой и выполнить тремя запросами
`curl` успешный сценарий, отказ отвечать и запрос к закрытым сведениям.

---



## Задание 09. Автономная проверка качества



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'typer>=0.12,<1' 'rich>=13,<15'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```

Pydantic проверяет JSONL, Typer создаёт команду `run`, Rich печатает таблицу.
Проверки реализуйте как небольшие чистые функции. Они проверяют наличие нужных
источников, корректность ссылок, отсутствие утечек и правильность отказа отвечать.
Положение фрагмента в выдаче не учитывается.

```python
def expected_sources_found(
    expected: set[str],
    actual: set[str],
) -> bool:
    return not expected or expected.issubset(actual)


def forbidden_sources_found(
    forbidden: set[str],
    actual: set[str],
) -> set[str]:
    return forbidden & actual
```

Напишите отдельную автоматическую проверку для каждой функции и сквозную проверку
кода завершения через
`typer.testing.CliRunner`.

### Ситуация

После смены Cognee, набора документов или инструкции модели нужно обнаруживать
ухудшения, а не судить о качестве ответов «на глаз».

### Как выглядит готовое решение

Одна команда читает 30 проверочных примеров и создаёт `build/report.json` и
`build/report.md`. В отчёте видны общие числа и отдельные провалы с кодами причин.
Хорошая программная заглушка завершает команду с кодом 0. Заглушка, которая
возвращает закрытый источник, завершает ту же команду с кодом 1.

### Формат набора проверочных примеров

Скопируйте готовый файл
`synthetic-data/01-knowledge-base-and-qa/evals/v1.jsonl` в
`data/evals/v1.jsonl`. В нём уже находятся 30 примеров следующего формата:

```json
{
  "case_id": "travel-01",
  "workspace_id": "alpha",
  "scopes": ["all-employees"],
  "question": "Какой срок подачи заявки?",
  "expected_status": "answered",
  "expected_source_ids": ["travel-policy"],
  "required_facts": ["7 рабочих дней"],
  "forbidden_source_ids": ["engineering-only"]
}
```

Не меняйте ожидаемые результаты перед первым запуском. Распределение: 12 вопросов с ответом в документах, 6 вопросов с другой
формулировкой, 4 вопроса без ответа, 4 запроса к закрытым сведениям и 4 примера с
противоречащими друг другу редакциями.

### Пошаговая реализация

1. Загрузите и полностью проверьте набор примеров до первого обращения к системе.
2. Для каждого ответа соберите множество `source_id` из возвращённого контекста и
  множество `source_id` из ссылок готового ответа.
3. Для вопроса с ответом проверьте, что в контексте присутствуют все значения из
  `expected_source_ids`. Их положение в списке значения не имеет.
4. Проверьте каждую ссылку ответа: соответствующий фрагмент должен присутствовать
  в полученном контексте, а его редакция и указатель должны совпадать.
5. Проверьте, что ни контекст, ни ссылки ответа не содержат значения из
  `forbidden_source_ids`.
6. Сопоставьте фактический статус с `expected_status`. Для вопроса без ответа
  ожидается управляемый отказ, а не выдуманный ответ.
7. Проверьте значения из `required_facts` после приведения регистра и пробелов.
  Если нужны варианты записи числа или даты, разрешите для конкретного примера
   регулярное выражение в отдельном поле `required_patterns`.
8. Считайте длительность ответа отдельно: это диагностическое значение, а не
  показатель правильности.
9. Создайте отчёт JSON и читаемую таблицу провалов в Markdown. Для каждого провала
  укажите `case_id`, код проверки, ожидаемое и фактическое значение.
10. В отчёт включите версию набора, имя переходника, версию проекции Cognee и
  время запуска.
11. Введите порог готовности: запрещённых источников — 0; действительных ссылок —
  100%; ожидаемые источники присутствуют не менее чем в 85% подходящих примеров;
    правильный статус ответа или отказа получен не менее чем в 80% примеров.
12. Код завершения процесса должен быть ненулевым при нарушении любого порога.



### Обязательные тесты

- проверяющий модуль правильно распознаёт вручную созданный хороший результат;
- выдуманная ссылка проваливает порог готовности;
- одна утечка запрещённого источника проваливает порог готовности независимо от
остальных результатов;
- отсутствие ожидаемого источника фиксируется независимо от положения остальных
фрагментов;
- пустой или повторяющийся `case_id` отклоняется;
- система-заглушка делает проверку качества воспроизводимой.



### Готово, если

`uv run python -m qa_eval run data/evals/v1.jsonl` создаёт два отчёта и возвращает
корректный код завершения.

---



## Задание 10. Надёжная длительная переиндексация с Temporal



### Библиотеки и установка

```bash
uv add 'temporalio>=1.8,<2' 'pydantic>=2.8,<3'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```



### Как работает Temporal

- Клиент запускает процесс и отправляет ему сигналы или запрашивает состояние.
- Исполнитель регистрирует процесс и операции и слушает очередь заданий.
- Процесс содержит только воспроизводимую логику управления шагами.
- Операция выполняет ввод-вывод и может безопасно повторяться.
- Проверочное окружение поднимает временный сервер; Docker не нужен.

Минимальная связка:

```python
from datetime import timedelta
from temporalio import activity, workflow

@activity.defn
async def index_batch(batch: IndexBatch) -> int:
    return await application_service.index(batch)

@workflow.defn
class ReindexWorkflow:
    def __init__(self) -> None:
        self.processed = 0
        self.cancel_requested = False

    @workflow.signal
    async def request_cancel(self) -> None:
        self.cancel_requested = True

    @workflow.query
    def progress(self) -> ReindexProgress:
        return ReindexProgress(status="running", processed=self.processed, total=0,
                               cancel_requested=self.cancel_requested)

    @workflow.run
    async def run(self, data: ReindexInput) -> ReindexResult:
        for batch in make_batch_descriptors(data):
            if self.cancel_requested:
                return cancelled_result(data, self.processed)
            count = await workflow.execute_activity(
                index_batch,
                batch,
                start_to_close_timeout=timedelta(seconds=30),
            )
            self.processed += count
        return activated_result(data, self.processed)
```

`make_batch_descriptors` работает только с уже переданными данными; процесс не
читает каталог.

### Настоящий исполнитель и программа запуска

```python
client = await Client.connect("localhost:7233")
worker = Worker(client, task_queue="reindex-lab", workflows=[ReindexWorkflow],
                activities=[index_batch])
await worker.run()
```



### Проверка процесса без внешнего сервера

```python
async with await WorkflowEnvironment.start_time_skipping() as env:
    async with Worker(env.client, task_queue="test-q", workflows=[ReindexWorkflow],
                      activities=[fake_index_batch]):
        result = await env.client.execute_workflow(
            ReindexWorkflow.run, input_data, id="reindex-test", task_queue="test-q"
        )
assert result.status == "activated"
```

Для проверки повторных попыток операция-заглушка хранит число вызовов и первые
два раза выбрасывает `RuntimeError`. Для проверки защиты от повторов отдельное
хранилище в памяти запоминает ключ группы; число вызовов может быть равно трём,
но логически записанная группа должна быть одна.

### Ситуация

Построение индекса может занимать долго, временно падать и требовать отмены.
Нужно сделать процесс наблюдаемым и безопасно повторяемым.

### Как выглядит готовое решение

Процесс Temporal разбивает 25 описаний фрагментов на три группы: 10, 10 и 5.
Проверочный вариант операции дважды падает на второй группе, после чего успешно
продолжает. Запрос текущего состояния показывает 10/25, затем 20/25 и 25/25.
При сигнале отмены после первой группы активация новой версии не вызывается.
Отдельные файлы `workflow.py`, `activities.py`, `worker.py` и `starter.py`
показывают четыре разные роли, а не смешивают их в одном модуле.

### Ограничение

Temporal используется только для управления порядком шагов. Разбор документов,
хранение редакций и построение проекции остаются обычными службами и вызываются
из операций Temporal.

### Контракты

```python
class ReindexInput(BaseModel):
    workspace_id: str
    projection_id: str
    manifest_paths: tuple[str, ...]

class ReindexProgress(BaseModel):
    status: str
    processed: int
    total: int
    cancel_requested: bool

class ReindexResult(BaseModel):
    status: Literal["activated", "cancelled", "failed"]
    projection_id: str
    indexed_count: int
```



### Пошаговая реализация

1. Добавьте `temporalio` и создайте процесс `ReindexWorkflow`.
2. Создайте операции `validate_manifests`, `create_projection`, `index_batch`,
  `verify_projection`, `activate_projection`, `mark_failed`.
3. Процесс обрабатывает описания фрагментов группами по 10.
4. Операция получает ключ защиты от повторов
  `workflow_id/activity_id/batch_number`.
5. Настройте время ожидания и повторные попытки для временных ошибок `index_batch`.
6. Ошибку проверки входных данных пометьте как не допускающую повторной попытки.
7. Добавьте запрос состояния `progress`.
8. Добавьте сигнал `request_cancel`; отмена проверяется между группами.
9. Не активируйте неполный или отменённый индекс.
10. Напишите связные проверки через `WorkflowEnvironment.start_time_skipping()`
  и исполнитель с операциями-заглушками.
11. Отдельным необязательным сценарием запустите локальный сервер разработки и
  покажите историю событий в веб-интерфейсе.



### Обязательные тесты

- успешный сценарий вызывает активацию ровно один раз;
- третья группа падает дважды, затем успешно повторяется;
- ошибка проверки входных данных не повторяется;
- отмена после первой группы не вызывает активацию;
- запрос состояния показывает только растущий ход выполнения;
- повторное выполнение операции не дублирует индексируемые элементы;
- проверка с ускоренным временем не ждёт настоящий промежуток между попытками;
- код процесса не читает файлы, сеть, случайные числа или системное время напрямую.



### Готово, если

Все сценарии проходят в проверочном окружении Temporal без Docker. Локальный
сервер является демонстрацией, а не условием модульных и связных проверок.

## Финальное объединение — необязательно

После завершения обязательной часть можно собрать задания 03–10 в
одну локальную службу. При этом нельзя копировать реализации в один большой файл: компоненты связываются
через ранее созданные контракты. Финальная демонстрация должна показать загрузку
двух редакций, безопасное перестроение, вопрос со ссылкой на источник, отказ
отвечать, запрет доступа и отчёт проверки качества.
