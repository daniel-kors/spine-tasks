# Направление 2. Инфраструктура ассистента коммерческих предложений

## Результат подготовки

Необходимо создать десять автономных решений: импорт исторического реестра, извлечение требований, поиск аналогов, расчёт стоимости, проверку полноты, сборку структурированного черновика, версионирование результатов, согласование человеком, долгоживущий процесс в Temporal и автономную проверку качества.

Решения не используют реальные коммерческие документы. Любое подключение
языковой модели имеет программную заглушку. Отправка предложения клиенту не
реализуется.

## Из каких файлов должно состоять решение


| Работа | Обязательные файлы внутри `src/<имя_пакета>/`                                          |
| ------ | -------------------------------------------------------------------------------------- |
| 01     | `models.py`, `csv_reader.py`, `normalizer.py`, `repository.py`, `service.py`, `cli.py` |
| 02     | `models.py`, `rule_extractor.py`, `model_extractor.py`, `validator.py`, `cli.py`       |
| 03     | `models.py`, `baseline.py`, `cognee_client.py`, `analogue_finder.py`, `cli.py`         |
| 04     | `models.py`, `rules.py`, `calculator.py`, `cli.py`                                     |
| 05     | `models.py`, `policy_loader.py`, `gate.py`, `questions.py`, `cli.py`                   |
| 06     | `models.py`, `generator.py`, `validator.py`, `renderer.py`, `cli.py`                   |
| 07     | `models.py`, `repository.py`, `diff.py`, `service.py`, `cli.py`                        |
| 08     | `models.py`, `approval_service.py`, `repositories.py`, `routes.py`, `main.py`          |
| 09     | `models.py`, `workflow.py`, `activities.py`, `worker.py`, `starter.py`                 |
| 10     | `models.py`, `metrics.py`, `runner.py`, `report.py`, `cli.py`                          |


В каждой работе должны быть быстрые модульные проверки основной логики. Если
есть SQLite, HTTP, Cognee или Temporal, добавьте отдельный файл связных проверок.
Настоящий вызов языковой модели всегда выделяется в отдельную необязательную
проверку с маркером `llm`.

## Последовательность выполнения

1. Создайте файлы и пустые функции с указанными сигнатурами.
2. Скопируйте нужные JSON, JSONL, CSV и Markdown из
  `synthetic-data/02-commercial-proposal-assistant/`, не изменяя содержимое.
3. Запустите программу с заглушками и получите самый простой успешный результат.
4. Добавьте проверки неправильных данных.
5. Добавьте хранение и защиту от повторных команд.
6. Только после этого подключите Cognee, языковую модель, HTTP или Temporal.
7. Сравните результат настоящего переходника с заглушкой по одному контракту.
8. Выполните ручной сценарий и сохраните пример ожидаемого вывода в README.

## Готовые синтетические исходные данные

Все данные уже находятся в
`synthetic-data/02-commercial-proposal-assistant/`. Не придумывайте новые
исторические кейсы, запросы или сметы для выполнения обязательной части.

Основной реестр `historical-cases.csv` содержит 12 кейсов: по четыре
`corporate_site`, `ecommerce` и `crm_implementation`. Связанные запросы находятся
в `requests/`, сметы — в `estimates/`. Относительные пути из CSV уже согласованы с
раскладкой каталогов.

Дополнительные готовые данные:

- `historical-case-001-updated.csv` — изменение одной исходной строки;
- `historical-cases-invalid.csv` — неизвестный тип работ и отсутствующие файлы;
- `historical-cases-beta.csv` — данные другой рабочей области;
- `new-requests/` — 15 новых запросов;
- `evals/extraction-v1.jsonl` — 25 размеченных запросов;
- `pricing/cases.jsonl` — 10 заранее рассчитанных денежных примеров;
- `policies/v1.json` — правила полноты;
- `evals/v1.jsonl` — 36 примеров итоговой проверки;
- `expected/` и `templates/` — результаты заглушек, уточнения и шаблон документа.

Перед началом прочитайте README набора. Не исправляйте намеренные пропуски в
запросах и ошибочные строки реестра: они нужны для отрицательных сценариев.

---



## Задание 01. Импорт реестра с сохранением исходных редакций



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'typer>=0.12,<1' 'aiosqlite>=0.20,<1' \
  'structlog>=24,<26'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```

CSV читается стандартным `csv.DictReader`; Pandas не используется, нужно
явно обработывать каждую строку и ошибку. `aiosqlite` хранит указатель защиты от повторов,
JSONL с запретом перезаписи — исходные данные, Structlog — отчёты по строкам.

### Минимальный модуль чтения CSV

```python
class CsvRegistryConnector:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def fetch(self) -> AsyncIterator[dict[str, str]]:
        with self.path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                yield dict(row)
```

Однозначную контрольную сумму вычисляйте так:

```python
payload_bytes = json.dumps(row, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
checksum = hashlib.sha256(payload_bytes).hexdigest()
```

Служба последовательно выполняет проверку повтора → сохранение исходной строки →
приведение к общей форме → сохранение кейса → создание отчёта. Если приведение к
общей форме завершается ошибкой, исходная редакция всё равно остаётся.

### Ситуация

Исторический реестр приходит из внешнего источника и может меняться. До
приведения к общей форме нужно сохранить точную наблюдавшуюся строку и её
контрольную сумму.

### Как выглядит готовое решение

Команда импорта читает 12 строк CSV. В `data/raw-records.jsonl` сохраняются
исходные строки, в `data/cases.db` — приведённые к общей форме записи, а на экран
выводится отчёт: сколько строк добавлено, пропущено и отвергнуто. Второй запуск
того же файла ничего не добавляет. Изменение комментария одной строки создаёт
только одну новую исходную редакцию.

### Что создать

```text
01-registry-importer/
  pyproject.toml
  src/registry_importer/
    models.py
    connector.py
    normalizer.py
    repository.py
    service.py
    cli.py
  tests/
  data/fixtures/
```



### Контракты

```python
class RawRecord(BaseModel):
    connection_id: str
    external_id: str
    workspace_id: str
    payload: dict[str, str]
    checksum: str
    observed_at: datetime

class HistoricalCase(BaseModel):
    case_id: str
    workspace_id: str
    work_type: Literal["corporate_site", "ecommerce", "crm_implementation", "other"]
    request_path: str
    estimate_path: str
    source_checksum: str

class RegistryConnector(Protocol):
    async def fetch(self) -> AsyncIterator[dict[str, str]]: ...
```



### Пошаговая реализация

1. Реализуйте модуль чтения `CsvRegistryConnector`.
2. Сформируйте контрольную сумму из однозначно сериализованной исходной строки.
3. Сначала сохраните `RawRecord` в JSONL без перезаписи старых строк.
4. Затем нормализуйте запись в `HistoricalCase`.
5. Никогда не заменяйте исходные данные приведённой к общей форме моделью.
6. Добавьте `ImportReceipt`: создано, не изменилось, ошибочно и предупреждения.
7. Ключ защиты от повторов: идентификатор подключения + внешний идентификатор +
  контрольная сумма.
8. Изменение комментария должно создавать новую исходную редакцию.
9. Ошибка одной строки не должна останавливать остальные.
10. Добавьте команды `import` и `history --external-id`.



### Обязательные тесты

- повторный импорт не создаёт вторую редакцию;
- изменение одной ячейки создаёт редакцию;
- неизвестный тип работ преобразуется в `other` и создаёт предупреждение;
- отсутствующий файл запроса создаёт понятную ошибку строки;
- две рабочие области не смешиваются;
- исходные данные можно воспроизвести после однозначной сериализации.

Минимальная связная проверка использует `tmp_path` и настоящие CSV/SQLite, но не
сеть:

```python
async def test_second_import_is_unchanged(tmp_path: Path) -> None:
    csv_path = write_registry(tmp_path, rows=[valid_row("case-001")])
    service = await build_service(tmp_path)
    first = await service.import_all(CsvRegistryConnector(csv_path), "alpha")
    second = await service.import_all(CsvRegistryConnector(csv_path), "alpha")
    assert first.created == 1
    assert second.unchanged == 1
```



### Готово, если

Командная программа импортирует 12 правильных записей, отдельно показывает
предупреждения и историю
изменённой строки.

### Усложнение

Добавьте переходник Google Sheets только для чтения. Основные проверки всё равно должны работать
на исходном CSV без сети и учётных данных.

---



## Задание 02. Извлечение требований как отдельная возможность системы



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'typer>=0.12,<1'
uv add --optional llm 'openai>=1,<3'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```

Версия на правилах использует `re.finditer`, чтобы получить границы фрагментов.
Переходник языковой модели
использует асинхронный клиент и просит JSON по Pydantic-схеме; точная модель задаётся
через `LLM_MODEL`, ключ — через переменную окружения.

### Пример извлечения по правилу

```python
DEADLINE = re.compile(r"(?:до|за)\s+(\d+)\s+(?:дней|недель|месяцев)", re.I)

def extract_deadlines(source_id: str, text: str) -> list[Requirement]:
    result = []
    for match in DEADLINE.finditer(text):
        result.append(Requirement(
            requirement_id=stable_id("deadline", match.start(), match.end()),
            category="deadline",
            text=match.group(0),
            origin="stated",
            confidence=1.0,
            evidence=(EvidenceSpan(source_id=source_id, char_start=match.start(),
                                   char_end=match.end(), excerpt=match.group(0)),),
        ))
    return result
```



### Как проверять подключение языковой модели

Не подменяйте внутренности `openai`. Введите собственный интерфейс
`StructuredCompletionClient` с методом `complete(prompt, response_model)`.
Модульная проверка подставляет подготовленный JSON,
а одна проверка с маркером `llm` обращается к настоящему поставщику модели.

### Ситуация

Свободный запрос нужно преобразовать в типизированные требования, сохранив точное
место в исходном тексте и отличая факт от предположения.

### Как выглядит готовое решение

Команда получает `request.md` и создаёт `requirements.json`. Для каждого явно
указанного требования сохранены начало и конец фрагмента. Небольшая программа
`highlight.py` печатает исходный текст и заключает найденные места в квадратные
скобки. Предположения записаны отдельно и не помечены как слова клиента. Основные
проверки работают с разборщиком по правилам и программной заглушкой модели.

### Модели

```python
class EvidenceSpan(BaseModel):
    source_id: str
    char_start: int
    char_end: int
    excerpt: str

class Requirement(BaseModel):
    requirement_id: str
    category: Literal["goal", "scope", "integration", "deadline", "content", "constraint"]
    text: str
    origin: Literal["stated", "inferred"]
    confidence: float = Field(ge=0, le=1)
    evidence: tuple[EvidenceSpan, ...]

class ExtractRequirementsInput(BaseModel):
    workspace_id: str
    request_id: str
    text: str
    schema_version: str

class RequirementExtractor(Protocol):
    async def extract(self, data: ExtractRequirementsInput) -> tuple[Requirement, ...]: ...
```



### Пошаговая реализация

1. Реализуйте `RuleBasedExtractor` для сроков, интеграций и числового масштаба.
2. Для каждого явно указанного требования вычислите границы символов.
3. Проверьте `input.text[start:end] == excerpt`.
4. Создайте программируемую заглушку `FakeExtractor`.
5. Необязательно добавьте переходник языковой модели со структурированным
  результатом Pydantic.
6. После ответа модели обязательно перепроверьте границы и ссылки на исходный текст.
7. Предполагаемое требование не может иметь происхождение `stated` без
  совпадающего фрагмента.
8. Сохраните версию извлекателя, версию инструкции и имя модели в служебных сведениях.
9. Для проверки используйте 25 готовых размеченных запросов из
  `synthetic-data/02-commercial-proposal-assistant/evals/extraction-v1.jsonl`.



### Обязательные тесты

- точный срок и интеграция извлекаются с правильными границами фрагментов;
- выдуманный языковой моделью фрагмент отклоняется;
- отсутствие срока не превращается в явно указанное требование;
- инструкция «игнорируй предыдущие правила» остаётся частью клиентского текста;
- символы Unicode не ломают позиции;
- заглушка позволяет запустить проверки без сети.



### Готово, если

Команда `extract request.md` выводит JSON, и каждый явно указанный факт можно подсветить в
исходном тексте по сохранённым позициям.

---



## Задание 03. Поиск похожих исторических кейсов



### Библиотеки и установка

```bash
uv add 'cognee>=1,<2' 'pydantic>=2.8,<3' 'pydantic-settings>=2,<3'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```



### Как инструмент работает в этой задаче

Сначала каждый исторический кейс превращается в самостоятельный текст:

```text
CASE_ID: case-003
WORK_TYPE: crm_implementation
REQUEST: Внедрить CRM для отдела из 20 человек...
ESTIMATE_CODES: DISCOVERY, CRM_SETUP, TRAINING
```

Затем тексты запоминаются и извлекаются как фрагменты:

```python
await cognee.remember(case_texts, dataset_name="alpha_analogues_v1",
                      self_improvement=False)
chunks = await cognee.recall(
    query_text=query_text,
    query_type=SearchType.CHUNKS,
    datasets=["alpha_analogues_v1"],
    top_k=10,
)
```

`CASE_ID:` нужен, чтобы переходник сопоставил результат с основной записью. Не
используйте текст Cognee как единственное место хранения сметы.

Локальные каталоги решения задаются до `import cognee`. Модульные проверки
используют `FakeCogneeClient`; проверка настоящей библиотеки помечается
`integration` и `llm`.

### Проверка исходного варианта поиска

```python
def test_same_type_and_requirements_rank_first() -> None:
    finder = BaselineAnalogueFinder(cases())
    result = asyncio.run(finder.find(crm_query()))
    assert result[0].case_id == "case-003"
    assert "work_type" in result[0].matched_features
```



### Ситуация

Нужно найти аналоги не только по одинаковым словам, но сохранить объяснение,
почему конкретный кейс был выбран.

### Как выглядит готовое решение

Команда `find` печатает таблицу из трёх строк: идентификатор примера, итоговая
показатель похожести, совпавший тип работ, совпавшие требования и редакции
источников. Есть две
реализации поиска: простая по правилам и через Cognee. При отключённом Cognee
простая реализация продолжает работать. Исходные запросы и сметы по-прежнему
читаются из локального хранилища, а не из поискового индекса.

### Контракты

```python
class AnalogueQuery(BaseModel):
    workspace_id: str
    work_type: str
    requirements: tuple[Requirement, ...]
    limit: int = Field(ge=1, le=10)

class AnalogueCandidate(BaseModel):
    case_id: str
    score: float
    matched_features: tuple[str, ...]
    source_revision_ids: tuple[str, ...]

class AnalogueFinder(Protocol):
    async def find(self, query: AnalogueQuery) -> tuple[AnalogueCandidate, ...]: ...
```



### Пошаговая реализация

1. Создайте текстовое представление кейса из запроса и заголовков строк сметы.
2. Реализуйте исходный показатель: совпадение типа работ даёт 0.5, совпадение
  категорий — 0.2, похожесть слов — 0.3.
3. Округляйте показатель только для отображения, не при сортировке.
4. При равенстве сортируйте по идентификатору кейса.
5. Индексируйте представления в Cognee в отдельном наборе для каждой рабочей области.
6. Реализуйте `CogneeAnalogueFinder` за тем же интерфейсом.
7. Объедините отбор по полям и результаты смыслового поиска.
8. Для каждого кандидата верните совпавшие признаки и идентификаторы редакций
  источников.
9. Создайте заглушку поиска аналогов для прикладных проверок.
10. Подготовьте команду сравнения, которая читает 15 готовых файлов из
  `synthetic-data/02-commercial-proposal-assistant/new-requests/`.



### Обязательные тесты

- другой тип работ понижается, но не обязательно исключается;
- чужая рабочая область отсутствует;
- каждый кандидат имеет объяснение и редакцию источника;
- порядок стабилен;
- Cognee недоступен — исходный вариант продолжает работать либо возвращается
явно задокументированный результат ограниченного режима;
- модульные проверки не требуют Cognee или языковой модели.



### Готово, если

Для трёх новых запросов необходимо показать первые три результата исходного
варианта и Cognee, объяснить различия.

---



## Задание 04. Детерминированный расчёт стоимости



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'typer>=0.12,<1'
uv add --dev 'pytest>=8,<9' 'hypothesis>=6,<7'
```

Денежная логика использует только стандартный `decimal.Decimal`. Pydantic
принимает значения из строк JSON, Typer даёт команды, Hypothesis проверяет
общие свойства расчёта.

### Полный порядок вычисления

```python
CENT = Decimal("0.01")

def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)

def calculate(lines: tuple[EstimateLineInput, ...], discount_rate: Decimal,
              tax_rate: Decimal) -> EstimateTotals:
    ensure_one_currency(lines)
    subtotal_value = money(sum((line.quantity * line.unit_price.amount for line in lines),
                               start=Decimal("0")))
    discount_value = money(subtotal_value * discount_rate)
    taxable_value = subtotal_value - discount_value
    tax_value = money(taxable_value * tax_rate)
    total_value = taxable_value + tax_value
    currency = lines[0].unit_price.currency
    return EstimateTotals(
        subtotal=Money(amount=subtotal_value, currency=currency),
        discount=Money(amount=discount_value, currency=currency),
        tax=Money(amount=tax_value, currency=currency),
        total=Money(amount=money(total_value), currency=currency),
    )
```

Правило должно явно определить допустимый диапазон `0 <= discount_rate <= 0.30`
и `0 <= tax_rate <= 1`. Пустую смету либо запретите, либо верните нули — решение
зафиксируйте и протестируйте.

### Проверка общих свойств расчёта

```python
@given(st.decimals(min_value="0.01", max_value="100000", places=2))
def test_total_never_less_than_zero(price: Decimal) -> None:
    totals = calculate((line(quantity="1", price=str(price)),), Decimal("0"), Decimal("0.2"))
    assert totals.total.amount >= 0
```

Добавьте параметризованную проверку, читающую заранее рассчитанные значения из
`synthetic-data/02-commercial-proposal-assistant/pricing/cases.jsonl`.

### Ситуация

Модель может предложить состав работ, но деньги, налоги, скидки и округление
должны рассчитываться обычным кодом.

### Как выглядит готовое решение

На вход подаётся JSON со строками сметы, скидкой и налогом. На выходе получается
JSON с промежуточными суммами: сумма строк, скидка, налог и итог. Для каждой
строки указано основание цены. Один и тот же вход всегда даёт байт-в-байт
одинаковые денежные значения. В модуле расчёта нет вызовов языковой модели,
Cognee или HTTP.

### Модели

```python
class Money(BaseModel):
    amount: Decimal
    currency: Literal["RUB", "USD", "EUR"]

class PricingBasis(BaseModel):
    basis_type: Literal["catalog", "analogue", "manual"]
    reference_id: str
    observed_at: date

class EstimateLineInput(BaseModel):
    code: str
    title: str
    quantity: Decimal
    unit: str
    unit_price: Money
    basis: PricingBasis

class EstimateTotals(BaseModel):
    subtotal: Money
    discount: Money
    tax: Money
    total: Money
```



### Пошаговая реализация

1. Запретите float на публичной границе; JSON принимает decimal как строки.
2. Реализуйте сумму строки: количество × цена единицы.
3. Зафиксируйте порядок: subtotal → discount → taxable base → tax → total.
4. Используйте `ROUND_HALF_UP` до двух знаков после каждой заданной правилами стадии.
5. Не разрешайте смешивать валюты в одной estimate.
6. Добавьте правило максимальной скидки и минимальной цены.
7. Основание цены обязательно для каждой строки.
8. Устаревшее основание не блокирует расчёт, но создаёт предупреждение для проверки.
9. Верните подробный журнал расчёта из чисел и идентификаторов правил, без скрытых
  рассуждений.
10. Сделайте команду, принимающую JSON сметы и печатающую итоги.



### Обязательные тесты

- `0.1 + 0.2` рассчитывается точно;
- количество `2.5` поддерживается;
- отрицательное количество отклоняется;
- смешение RUB/USD отклоняется;
- скидка выше лимита отклоняется;
- налог 20% и округление проверены табличными примерами;
- повторный расчёт идентичен;
- отсутствующее основание цены отклоняется.



### Готово, если

Десять табличных примеров воспроизводят заранее рассчитанные наставником
итоги, и в коде расчёта стоимости отсутствует вызов языковой модели.

---



## Задание 05. Проверка полноты и уточняющие вопросы



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'typer>=0.12,<1'
uv add --dev 'pytest>=8,<9'
```

Правила из JSON загружаются Pydantic-моделью; решение «пройдено/не пройдено»
принимает чистая функция. Здесь не нужны Cognee и языковая модель.

### Стартовый алгоритм

```python
def evaluate(policy: CompletenessPolicy,
             requirements: tuple[Requirement, ...],
             answers: tuple[ClarificationAnswer, ...]) -> GateDecision:
    present = {r.category for r in requirements if r.origin == "stated"}
    present.update(a.category for a in answers if a.value.strip())
    missing = sorted(set(policy.required_categories) - present)
    questions = tuple(question_for(category, policy.version) for category in missing)
    return GateDecision(
        status="pass" if not missing else "clarification_required",
        missing=tuple(to_missing(category) for category in missing),
        questions=questions,
        policy_version=policy.version,
    )
```

Устойчивый идентификатор вопроса вычисляйте как SHA-256 от
`request_id/policy_version/category`
и обрезайте до 16 hex-символов. Так повторный расчёт не создаст дубликаты.

### Минимальный тест

```python
def test_crm_without_integration_requests_clarification() -> None:
    decision = evaluate(crm_policy(), requirements(goal(), scope()), answers=())
    assert decision.status == "clarification_required"
    assert [item.category for item in decision.questions] == ["integration"]
```



### Ситуация

Черновик нельзя строить, если неизвестны данные, критичные для расчёта. Нужен
объяснимый проверяющий шаг, не зависящий от ответа языковой модели.

### Как выглядит готовое решение

Команда получает тип работ и `requirements.json`. Для полного запроса она печатает
`pass`. Для неполного создаёт `clarification-questions.json` и печатает, каких
сведений не хватает. После добавления `clarification-answers.json` повторный
запуск закрывает только вопросы, на которые дан непустой ответ. Решение содержит
версию правил и устойчивые идентификаторы вопросов.

### Конфигурация

Скопируйте готовый файл
`synthetic-data/02-commercial-proposal-assistant/policies/v1.json` в
`policies/v1.json`. Он содержит следующую таблицу правил:

```json
{
  "corporate_site": ["goal", "scope", "content", "deadline"],
  "ecommerce": ["goal", "scope", "integration", "content"],
  "crm_implementation": ["goal", "scope", "integration"]
}
```



### Модели

```python
class MissingInformation(BaseModel):
    category: str
    reason_code: str
    blocking: bool

class ClarificationQuestion(BaseModel):
    question_id: str
    category: str
    text: str
    reason_code: str

class GateDecision(BaseModel):
    status: Literal["pass", "clarification_required"]
    missing: tuple[MissingInformation, ...]
    questions: tuple[ClarificationQuestion, ...]
    policy_version: str
```



### Пошаговая реализация

1. Загрузите версионированные правила и проверьте их схему.
2. Сопоставьте requirements с обязательными категориями.
3. Для каждой отсутствующей категории создайте стабильный reason code.
4. Генерируйте один вопрос на category по шаблону.
5. Языковую модель разрешено использовать только для перефразирования, но не для
  решения о прохождении проверки.
6. Ответ менеджера сохраняйте отдельным `ClarificationAnswer`.
7. Повторная проверка использует исходные требования плюс новые ответы.
8. Не перезаписывайте исходный запрос.
9. Дублирующий ответ не создаёт второй закрытый пробел в данных.



### Обязательные тесты

- полный запрос проходит;
- каждая пропущенная обязательная категория создаёт вопрос;
- необязательное поле не блокирует;
- ответ закрывает только связанную категорию;
- смена версии правил отражается в решении;
- неизвестный тип работ использует явно заданные запасные правила;
- одинаковые входы создают устойчивые идентификаторы вопросов.



### Готово, если

Для трёх неполных запросов система останавливается, задаёт минимальный набор
вопросов и проходит после достаточных ответов.

---



## Задание 06. Сборщик типизированного черновика



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'jinja2>=3.1,<4' 'typer>=0.12,<1'
uv add --optional llm 'openai>=1,<3'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```

Pydantic-модель является основной формой черновика. Jinja2 только преобразует
проверенный черновик в Markdown; шаблон не рассчитывает итоговые суммы.
`StrictUndefined` делает
пропущенное поле ошибкой, а не пустой строкой.

### Рендеринг

```python
environment = Environment(
    loader=FileSystemLoader("templates"),
    undefined=StrictUndefined,
    autoescape=False,
)

def render_markdown(draft: ProposalDraft) -> str:
    template = environment.get_template("proposal.md.j2")
    return template.render(proposal=draft.model_dump(mode="json"))
```

Минимальный `proposal.md.j2`:

```jinja2
# Коммерческое предложение
{% for section in proposal.sections %}
## {{ section.title }}
{{ section.body }}
{% endfor %}

**Итого:** {{ proposal.estimate.totals.total.amount }}
{{ proposal.estimate.totals.total.currency }}
```

Готовый образец результата находится в
`synthetic-data/02-commercial-proposal-assistant/expected/proposal.md`. Скопируйте
его в `tests/snapshots/proposal.md`. При изменении шаблона образец обновляется
осознанно и отдельно просматривается проверяющим.

### Ситуация

Нужно собрать редактируемый документ из требований, аналогов и расчётной сметы,
не передавая между этапами историю переписки с моделью.

### Как выглядит готовое решение

Сборщик читает четыре файла: требования, найденные аналоги, рассчитанную смету и
шаблон. Он создаёт `proposal.json`, проверяет его и только затем создаёт
`proposal.md`. В JSON можно проследить, какое требование и какой источник
подтверждают каждый раздел. Изменение шаблона не изменяет входные требования и
смету.

### Модели

```python
class ProposalSection(BaseModel):
    key: str
    title: str
    body: str
    requirement_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]

class ProposalDraft(BaseModel):
    draft_id: UUID
    workspace_id: str
    request_id: str
    template_version: str
    sections: tuple[ProposalSection, ...]
    estimate: Estimate
    assumptions: tuple[str, ...]
    exclusions: tuple[str, ...]
    upstream_artifact_ids: tuple[UUID, ...]
```



### Пошаговая реализация

1. Создайте шаблон JSON с обязательными разделами: краткое описание, объём работ,
  этапы, допущения, исключения и смета.
2. Реализуйте интерфейс `DraftGenerator` и воспроизводимую заглушку генератора.
3. Необязательно добавьте генератор на основе языковой модели со
  структурированным результатом.
4. Проверяющий модуль требует наличия всех разделов шаблона.
5. Каждое явно указанное требование должно быть раскрыто в разделе или явном
  исключении.
6. Каждая ссылка на аналог должна существовать среди переданных кандидатов.
7. Языковая модель предлагает строки, но служба расчёта заново считает итоги.
8. Сохраняйте идентификаторы всех предшествующих результатов.
9. Экспортируйте черновик в Markdown; JSON остаётся основной формой.



### Обязательные тесты

- отсутствующий раздел отклоняется;
- неизвестная ссылка на требование или источник отклоняется;
- нераскрытое требование создаёт ошибку проверки;
- неверный итог генератора заменяется результатом службы расчёта;
- генератор-заглушка создаёт полный черновик без сети;
- смена версии шаблона отражается в черновике.



### Готово, если

По одному полному запросу создаются валидные JSON и Markdown с одинаковым
содержанием и воспроизводимыми итогами.

---



## Задание 07. Версионное хранилище результатов и сравнение изменений



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'aiosqlite>=0.20,<1' 'typer>=0.12,<1'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```



### Схема SQLite и транзакция

```sql
CREATE TABLE artifact_versions (
  artifact_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  workspace_id TEXT NOT NULL,
  content_json TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  parent_version INTEGER,
  PRIMARY KEY (artifact_id, version)
);
CREATE TABLE idempotency (
  workspace_id TEXT NOT NULL,
  key TEXT NOT NULL,
  result_json TEXT NOT NULL,
  PRIMARY KEY (workspace_id, key)
);
```

`save_version` начинает `BEGIN IMMEDIATE`, проверяет защиту от повтора, читает
`MAX(version)`, сравнивает с `expected_version`, вставляет новую запись и
подтверждает транзакцию. При исключении выполняет откат. Это предотвращает две версии с одинаковым
номером в одном SQLite-процессе.

### Сравнение без дополнительной библиотеки

Сопоставляйте разделы по `key`, строки сметы по `code`; для каждого поля
возвращайте `{path, before, after, change_type}`. Сравнение всего JSON как строки
не принимается.

### Проверка конкурирующей записи

```python
async def test_optimistic_lock_rejects_stale_writer(store: ArtifactStore) -> None:
    await store.create(initial_version())
    await store.save(edit(expected=1, key="edit-a"))
    with pytest.raises(VersionConflict):
        await store.save(edit(expected=1, key="edit-b"))
```



### Ситуация

Нужно различать исходный машинный черновик, правки менеджера и утверждённую версию.

### Как выглядит готовое решение

После генерации в SQLite есть версия 1. Первая правка создаёт версию 2, вторая —
версию 3. Команда сравнения первой и третьей версии показывает изменённый текст,
добавленную строку сметы и новую стоимость. Попытка сохранить правку на основе
устаревшей версии 1 завершается конфликтом и не создаёт четвёртую запись.

### Контракты

```python
class ArtifactVersion(BaseModel):
    artifact_id: UUID
    version: int
    workspace_id: str
    content: dict
    created_by: str
    created_at: datetime
    parent_version: int | None
    evidence_refs: tuple[str, ...]

class SaveVersionCommand(BaseModel):
    artifact_id: UUID
    expected_version: int
    new_content: dict
    actor_id: str
    idempotency_key: str
```



### Пошаговая реализация

1. Реализуйте схему SQLite для результатов, версий и записей защиты от повторов.
2. Версия 1 создаётся генератором.
3. Каждая правка создаёт новую версию без перезаписи старой.
4. Используйте проверку ожидаемой версии `expected_version`.
5. Повтор ключа повторяемости возвращает уже созданную версию.
6. Реализуйте структурное сравнение разделов и строк сметы.
7. Сравнение показывает добавленные, удалённые и изменённые поля, но не меняет данные.
8. Запретите физическое удаление версии.
9. Добавьте запись аудита для каждого изменения.



### Обязательные тесты

- версии идут 1, 2, 3;
- конкурирующая запись с ожидаемой версией 1 после версии 2 получает конфликт;
- повтор команды не создаёт версию 3;
- история другой рабочей области недоступна;
- сравнение правильно показывает изменение количества и текста раздела;
- аудит содержит исполнителя и номера версии до/после.



### Готово, если

Команды демонстрируют создание, две правки, конфликт устаревшего клиента и сравнение
между первой и последней версиями.

---



## Задание 08. HTTP-интерфейс согласования человеком



### Библиотеки и установка

```bash
uv add 'fastapi>=0.115,<1' 'uvicorn[standard]>=0.34,<1' \
  'pydantic>=2.8,<3' 'aiosqlite>=0.20,<1' 'structlog>=24,<26'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2' 'httpx>=0.27,<1'
```



### Разделение ролей

- FastAPI читает путь, тело и заголовки запроса и выбирает код HTTP-ответа.
- `ApprovalService` проверяет роль и допустимость смены состояния.
- `ArtifactRepository` загружает конкретную версию.
- `DecisionRepository` транзакционно сохраняет решение.
- `AuditSink` фиксирует успешные и запрещённые попытки без текста документа.

```python
@router.post("/api/v1/proposals/{proposal_id}/approve")
async def approve(
    proposal_id: UUID,
    body: ApproveRequest,
    actor: Annotated[Actor, Depends(actor_from_headers)],
    service: Annotated[ApprovalService, Depends(get_approval_service)],
) -> DecisionResponse:
    return await service.approve(proposal_id, body.version, actor, body.idempotency_key)
```

Учебные заголовки: `X-Workspace-Id`, `X-Actor-Id`, `X-Actor-Role`. В README явно
напишите, что это не настоящая производственная аутентификация.

### Проверка приложения в памяти

```python
async def test_editor_cannot_approve(app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app)
    headers = {"X-Workspace-Id": "alpha", "X-Actor-Id": "u-1",
               "X-Actor-Role": "editor"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/proposals/{proposal_id}/approve",
            headers=headers,
            json={"version": 2, "idempotency_key": "approve-1"},
        )
    assert response.status_code == 403
```

Добавьте проверку описания OpenAPI: ни один путь не содержит `send`, `email` или
`deliver`.

### Ситуация

Ни один документ не должен стать утверждённым без явного решения человека.

### Как выглядит готовое решение

HTTP-сервис хранит состояние предложения и решения. Сотрудник с ролью редактора
может запросить проверку, но не может утвердить документ. Руководитель утверждает
конкретную версию. После этого метод экспорта отдаёт Markdown. Для черновика или
отклонённой версии экспорт отвечает ошибкой. Метода отправки клиенту в приложении
нет.

### Правила смены состояний

Допустимые состояния:

```text
draft -> review_requested -> approved
draft -> review_requested -> rejected
rejected -> draft
```

Другие переходы запрещены.

### HTTP-методы

- `POST /api/v1/proposals/{id}/request-review`
- `POST /api/v1/proposals/{id}/approve`
- `POST /api/v1/proposals/{id}/reject`
- `GET /api/v1/proposals/{id}/decisions`
- `GET /api/v1/proposals/{id}/export`



### Пошаговая реализация

1. Создайте прикладную службу с правилами смены состояний без FastAPI.
2. Решение содержит идентификатор исполнителя, роль, версию результата, время и
  комментарий.
3. Утверждение разрешено только роли `manager`.
4. Утверждается конкретная версия, а не «последняя вообще».
5. Изменение после утверждения создаёт новый черновик и не меняет утверждённую версию.
6. Экспорт разрешён только для утверждённой версии.
7. Добавьте ключ защиты от повторов к утверждению и отклонению.
8. HTTP-слой извлекает исполнителя из учебных заголовков, но правила проверяет
  прикладная служба.
9. Никакого HTTP-метода `send-to-client` не создавайте.
10. Добавьте единый вид ошибки и идентификатор трассировки.



### Обязательные тесты

- редактор не может утвердить документ;
- руководитель утверждает версию, отправленную на проверку;
- черновик нельзя экспортировать;
- устаревшую версию нельзя случайно утвердить;
- повтор утверждения не создаёт второе решение;
- отклонение требует комментария;
- чужая рабочая область получает 404/403 согласно документированному правилу;
- HTTP-интерфейс не содержит способа отправить документ клиенту.



### Готово, если

Три сценария `curl` показывают утверждение, отклонение и запрещённое действие, а история аудита
однозначно отвечает кто, что и какую версию утвердил.

---



## Задание 09. Долгоживущий процесс подготовки предложения



### Библиотеки и установка

```bash
uv add 'temporalio>=1.8,<2' 'pydantic>=2.8,<3'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```



### Как работает Temporal здесь

Клиент запускает процесс; исполнитель выполняет зарегистрированный процесс и его
операции. Процесс ожидает сигналы, а его состояние восстанавливается повторным
проигрыванием истории событий. Любой ввод-вывод находится внутри операции.

```python
@activity.defn
async def extract_requirements_activity(data: ExtractInput) -> ArtifactRef:
    return await services.requirement_extractor.execute(data)

@workflow.defn
class PrepareProposalWorkflow:
    def __init__(self) -> None:
        self.status = "extracting"
        self.clarifications: list[ClarificationAnswer] = []
        self.review: ReviewDecision | None = None

    @workflow.signal
    async def submit_clarification(self, answer: ClarificationAnswer) -> None:
        self.clarifications.append(answer)

    @workflow.signal
    async def review_decision(self, decision: ReviewDecision) -> None:
        self.review = decision

    @workflow.query
    def current_status(self) -> WorkflowStatus:
        return build_status(self)

    @workflow.run
    async def run(self, data: PrepareProposalInput) -> PrepareProposalResult:
        requirements = await workflow.execute_activity(
            extract_requirements_activity,
            ExtractInput(request_id=data.request_id),
            start_to_close_timeout=timedelta(seconds=30),
        )
        gate = await run_gate(requirements)
        if gate.needs_clarification:
            self.status = "waiting_clarification"
            await workflow.wait_condition(lambda: bool(self.clarifications))
        # TODO: retrieve -> draft -> pricing -> save -> review
        self.status = "waiting_review"
        await workflow.wait_condition(lambda: self.review is not None)
        return to_result(self.review)
```

В реальном коде `run_gate` тоже должен быть операцией, если он читает сохранённые
результаты. Чистую функцию можно выполнить в процессе только тогда, когда все её
входы уже находятся в истории
и реализация остаётся детерминированной.

### Исполнитель и локальный запуск

```bash
temporal server start-dev
uv run python -m proposal_workflow.worker
uv run python -m proposal_workflow.starter --request request-001
```

Код исполнителя:

```python
client = await Client.connect("localhost:7233")
async with Worker(client, task_queue="proposal-lab",
                  workflows=[PrepareProposalWorkflow],
                  activities=ALL_ACTIVITIES):
    await asyncio.Event().wait()
```



### Проверка с ускоренным временем

```python
async with await WorkflowEnvironment.start_time_skipping() as env:
    async with Worker(env.client, task_queue="test", workflows=[PrepareProposalWorkflow],
                      activities=FAKE_ACTIVITIES):
        handle = await env.client.start_workflow(
            PrepareProposalWorkflow.run, input_data,
            id="proposal-test", task_queue="test",
        )
        await wait_until_status(handle, "waiting_clarification")
        await handle.signal(PrepareProposalWorkflow.submit_clarification, answer)
        await wait_until_status(handle, "waiting_review")
        await handle.signal(PrepareProposalWorkflow.review_decision, approval)
        result = await handle.result()
assert result.status == "approved"
```

Для проверки повторных попыток создайте операцию-замену со счётчиком. Первые два
вызова бросают
`ApplicationError("temporary", non_retryable=False)`, третий возвращает результат.

### Ситуация

Процесс может ждать уточнения или проверки несколько дней. Исполнитель может
перезапуститься, а временно неудачный вызов модели — повториться.

### Как выглядит готовое решение

Процесс Temporal доходит до состояния ожидания уточнения и остаётся в нём, пока
не придёт ответ. Затем создаёт черновик и ждёт решения руководителя. Проверка
останавливает и снова запускает исполнитель между этими событиями: процесс не
начинается заново и не создаёт второй черновик. Текущее состояние можно запросить
в любой момент.

### Контракты

```python
class PrepareProposalInput(BaseModel):
    workspace_id: str
    request_id: str
    workflow_version: str

class WorkflowStatus(BaseModel):
    stage: Literal[
        "extracting", "searching", "waiting_clarification",
        "drafting", "waiting_review", "approved", "rejected", "failed"
    ]
    artifact_ids: tuple[str, ...]
    pending_question_ids: tuple[str, ...]

class PrepareProposalResult(BaseModel):
    status: Literal["approved", "rejected", "failed"]
    approved_artifact_id: str | None
```



### Пошаговая реализация

1. Добавьте набор средств разработки Temporal для Python.
2. Создайте операции: извлечение требований, поиск аналогов, проверка полноты,
  сборка черновика, расчёт сметы, сохранение результата и запрос проверки.
3. Операция вызывает обычную прикладную службу; бизнес-правило не переносится в
  код процесса Temporal.
4. Процесс вызывает шаги последовательно и сохраняет только небольшие
  идентификаторы и типизированные результаты.
5. Если проверка полноты не пройдена, процесс ждёт сигнал `submit_clarification`.
6. После нового ответа повторите извлечение и проверку полноты с ключами защиты
  от повторов.
7. После создания черновика процесс ждёт сигнал `review_decision`.
8. Добавьте запрос текущего состояния `current_status`.
9. Добавьте таймер напоминания; операция напоминания пишет только локальную запись
  аудита и не отправляет письмо.
10. Временная ошибка переходника приводит к повторной попытке; ошибка проверки
  схемы не должна повторяться.
11. Каждая изменяющая данные операция принимает ключ защиты от повторов.
12. Проверяйте процесс через `WorkflowEnvironment.start_time_skipping()` с
  операциями-заглушками.



### Обязательные тесты

- полный запрос доходит до ожидания проверки и после сигнала становится утверждённым;
- неполный запрос ждёт уточнения, затем продолжает;
- исполнитель можно остановить и снова запустить в локальной демонстрации;
- таймер напоминания проверяется без реального ожидания;
- временно падающая операция вызывается трижды, но логически выполняется один раз;
- ошибка проверки данных не зацикливается;
- повторный сигнал утверждения не создаёт два утверждённых результата;
- процесс не выполняет HTTP, работу с файлами, языковой моделью или SQLite напрямую;
- история событий не содержит полного клиентского документа или секретов.



### Готово, если

Все проверки проходят без Docker в проверочном окружении Temporal. Дополнительно
можно запустить `temporal server start-dev` и показать историю, но это не обязательная
часть проверки.

---



## Задание 10. Проверки качества и порог готовности



### Библиотеки и установка

```bash
uv add 'pydantic>=2.8,<3' 'typer>=0.12,<1' 'rich>=13,<15'
uv add --dev 'pytest>=8,<9' 'pytest-asyncio>=0.23,<2'
```



### Реализация показателей

Не используйте sklearn ради нескольких счётчиков. Для извлечения требований:

```python
def precision_recall(expected: set[str], predicted: set[str]) -> tuple[float, float]:
    true_positive = len(expected & predicted)
    precision = true_positive / len(predicted) if predicted else float(not expected)
    recall = true_positive / len(expected) if expected else float(not predicted)
    return precision, recall

def f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
```

Для поиска реализуйте среднее обратное место и попадание в первые три результата
отдельными функциями. Для расчёта стоимости сравнивайте `Decimal`, не `float`.
Критические ошибки накапливайте отдельно:

```python
critical = [r for r in results if r.leakage or r.arithmetic_mismatch or
            r.automatic_approval]
passed = not critical and aggregate.extraction_f1 >= Decimal("0.80")
raise typer.Exit(code=0 if passed else 1)
```



### Команда запуска и ожидаемые файлы

```bash
uv run python -m proposal_eval run \
  --dataset data/evals/v1.jsonl \
  --json-report build/eval-v1.json \
  --markdown-report build/eval-v1.md
echo $?
```

Успешный запуск возвращает `0`, провал — `1`. JSON содержит результаты всех
примеров; Markdown — общие показатели и минимум десять худших кейсов с кодами причин.

### Проверка команды

```python
def test_leakage_makes_exit_code_nonzero(tmp_path: Path) -> None:
    runner = CliRunner()
    dataset = write_dataset(tmp_path, [case_with_forbidden_source()])
    result = runner.invoke(app, ["run", "--dataset", str(dataset)])
    assert result.exit_code == 1
    assert "CROSS_WORKSPACE_LEAKAGE" in result.stdout
```



### Ситуация

Нужно отдельно проверять извлечение требований, выбор аналогов, полноту данных,
состав черновика и арифметику.

### Как выглядит готовое решение

Одна команда прогоняет 36 примеров, создаёт подробный JSON и понятный отчёт в
Markdown. В нём отдельные разделы для извлечения требований, поиска аналогов,
полноты данных, черновика и расчётов. Любая денежная ошибка, чужой источник или
автоматическое утверждение делает итоговую проверку неуспешной независимо от
среднего значения остальных показателей.

### Набор проверочных примеров

Скопируйте
`synthetic-data/02-commercial-proposal-assistant/evals/v1.jsonl` в
`data/evals/v1.jsonl`. В нём уже находятся 36 примеров:

- 12 на извлечение требований;
- 8 на поиск аналогов;
- 6 на проверку полноты;
- 6 на покрытие требований черновиком;
- 4 на граничные случаи расчёта стоимости.

Пример:

```json
{
  "case_id": "crm-clarify-01",
  "work_type": "crm_implementation",
  "request_text": "Нужно внедрить CRM для отдела продаж",
  "expected_requirement_categories": ["goal", "scope"],
  "expected_missing_categories": ["integration"],
  "expected_analogue_ids": ["case-003"],
  "must_not_approve": true
}
```



### Пошаговая реализация

1. Проверьте уникальность идентификаторов примеров и версию схемы.
2. Для извлечения требований рассчитайте точность, полноту и правильность границ
  фрагментов-оснований.
3. Для поиска рассчитайте попадание в первые три результата и среднее обратное место.
4. Для проверки полноты рассчитайте правильность блокирующего решения.
5. Для черновика проверьте покрытие требований и правильность ссылок на источники.
6. Для расчёта стоимости сравните точные итоговые значения `Decimal`.
7. Отдельно проверяйте критические ошибки: данные чужой рабочей области,
  арифметическое расхождение, неподтверждённый источник и автоматическое утверждение.
8. Одна критическая ошибка должна провалить всю проверку независимо от среднего результата.
9. Создайте отчёты JSON и Markdown с таблицей худших кейсов.
10. Отчёт содержит версии набора примеров, извлекателя, инструкции модели,
  проекции, правил расчёта и процесса.
11. Введите пороги: правильность границ источников 100%, утечки 0, арифметика
  100%, автоматическое утверждение 0, F1 извлечения ≥ 0.8, попадание аналога в
    первые три результата ≥ 0.75.
12. Верните ненулевой код завершения при провале.



### Обязательные тесты

- намеренно плохой извлекатель снижает F1;
- неправильный итог проваливает проверку готовности;
- один чужой источник проваливает проверку готовности;
- отсутствие обязательного вопроса отражается в показателе полноты;
- отчёты воспроизводимы при переходниках-заглушках;
- пустой набор примеров не считается успешным.



### Готово, если

Одна команда выполняет весь набор, сохраняет два отчёта и корректно сигнализирует
успех или провал через код завершения.

## Финальное объединение — необязательно

Псоле завершения обязательной части можно связать задания в
локальный прототип:

1. Импортировать 12 исторических кейсов.
2. Принять новый запрос.
3. Извлечь требования и найти три лучших аналога.
4. Приостановиться для уточнения.
5. Создать черновик и точно рассчитать смету.
6. Сохранить правку как новую версию.
7. Получить явное решение менеджера.
8. Экспортировать только утверждённую версию.
9. Запустить проверку порога готовности.

Компоненты объединяются через контракты предыдущих работ. Не следует переносить
все реализации в один модуль или заменять типизированные результаты общим словарём.