# Проверки — 8 октября 2026, Africa/Dar_es_Salaam

Проверялся новый серверный код в пустом checkout, PostgreSQL 16 в Docker, Python 3.12, Chromium headless, изолированные TEST базы. Получены и проверены опубликованные экраны Progressive/Baccarat, шрифты, фоны, графика и галерея 11 MP4; см. SOURCE_RECONCILIATION.md. Реальных ставок, CMS migrations или изменений arucms не было.

## Результат

- Последний полный прогон после подключения опубликованных экранов/F4: **42 passed**, 0 failed, 0 skipped, 18.93 s. Включает 20 concurrent financial table commands и проверки permanent URL/binding/pair-code rollback.
- Одно предупреждение Starlette/AnyIO о deprecated type alias, без failed tests. Explicit pool open устранил другое предупреждение.
- Node physical-key tests прошли: NumPad code при Num Lock off, repeat suppression, password input exclusion и configurable mapping.
- Две независимые Chromium browser contexts: одинаковое объявление, чужой раунд сохраняется, потеря связи блокирует действие, reconnect восстанавливает authoritative state, ошибок JS нет.
- 20 одновременных SSE clients получили один win_id. Финальный короткий замер: **228.4 ms** между первой и последней доставкой; **66 ms** между началом показа в двух браузерах. Общее show_at с буфером 2 секунды. Это один облачный замер, не гарантия сети/физических мониторов и не 20 полноценных hardware terminals.
- Docker image собран и запущен от UID 10001. Pinned wheels получены по проверяемому TLS, SHA-256 manifest проверен в сборке, установка внутри контейнера offline. TLS verification не отключалась.
- Compose: заполненная БД (confirmed round, approved fixed win, pending Royal claim), actual app process restart, funds/rounds/claims сохранились.
- Backup/restore: реальные shipped scripts, restore в новую БД; state, rounds, claims, journal hashes, command fingerprints/responses, principals и migration version идентичны оригиналу.
- Настоящий HTTPS `/health`, login и authenticated state прошли с проверкой Caddy CA (без ignore-certificate-errors/verify=false).
- `install_script` и `start_skill` сохранены в cloud draft и проверены соответствующими командами. Publication/new-task restoration не выполнялись и не проверялись.

## Матрица требований

| № | Проверка из задания | Итог / доказательство |
|---|---|---|
| 1 | Один бокс 5,000; 220/130/70/45/35 | PASS — test_one_box |
| 2 | Семь боксов 35,000; взносы 3,500 | PASS — test_seven_boxes |
| 3 | Повтор Enter/command_id | PASS — idempotency_and_double_enter; stale round guard |
| 4 | Два стола / общий фонд | PASS — concurrent test; дополнительно 20 concurrent table commands |
| 5 | Новый стол без повторного seed | PASS — registration_does_not_seed; 20-table initialization event count=1 |
| 6 | Завершение не сбрасывает фонды | PASS — close_preserves_pools |
| 7 | Игра без ставок | PASS — zero_round_statistics |
| 8 | Неучаствующий бокс | PASS — nonparticipant |
| 9 | Неверный PIN не меняет деньги/объявление | PASS — API login failure + unchanged pools/events |
| 10 | Upper tiers требуют authority | PASS — parametrized tiers 3/4/5; two-stage policy |
| 11 | Progressive reset только tier | PASS — progressive_reset_only_one |
| 12 | Fixed не сбрасывает всё | PASS — fixed_funding, debit/shortfall separately |
| 13 | Повтор approval | PASS — duplicate_approval_and_actual_payment |
| 14 | Отмена auditable | PASS — reversal_audit; original retained |
| 15 | Restart funds/rounds/claims/journal | PASS — API + actual Compose process restart; journal backup compare |
| 16 | Offline блокирует local money | PASS — real browser context offline; unchanged server round |
| 17 | Reconnect без дублей | PASS — browser reconnect + same-ID command/status/sequence API |
| 18 | Общий winner на нескольких терминалах | PASS — 2 browser contexts, 20 SSE clients |
| 19 | Не закрывает чужой раунд | PASS — browser check preserved round_id |
| 20 | Progressive ↔ настоящий Baccarat | PASS — настоящий опубликованный MAX, F4, неизменные фонды/раунд, отдельный ввод, winner поверх MAX и возврат, локальная история сохраняется |
| 21 | NumPad / Num Lock | PASS логики physical event.code и synthetic browser input; **реальный USB/OS reboot не проверен** |
| 22 | Business date до/после 07:00 EAT | PASS — boundary test UTC 03:59:59 / 04:00:00 |
| 23 | CMS read не меняет деньги | PASS — scoped contract 403 |
| 24 | Metadata scope только разрешённые поля | PASS — 200/403/422; financial amount unchanged |
| 25 | Backup в чистую БД | PASS — actual custom dump/restore, populated state/hash/commands equality |
| 26 | Спорные simultaneous claims | PASS — по решению владельца same-tier выплаты последовательные, обе заявки сохраняются; только свой стол paused, сумма при подтверждении |

Дополнительно: malformed float/bool/range input; config snapshots and unchanged balances; append-only trigger и hash-chain; actual cash status отдельно; TLS requirement; login lockout; second-operator lease; sequence replay; principal revocation rechecked inside financial transaction; announcement queue persisted.

## Повторение backend tests только в изоляции

Из checkout, при свободном 55432 и отсутствии одноимённого контейнера:

```sh
docker run -d --name premier-progressive-test -e POSTGRES_PASSWORD=local-test-only -e POSTGRES_DB=progressive -p 127.0.0.1:55432:5432 postgres:16
# Дождаться pg_isready; test password относится только к этой изолированной БД.
docker exec premier-progressive-test createdb -U postgres progressive_test
.venv/bin/python -m pytest -q
node tests/keys.test.mjs
```

Fixture жёстко выбирает `progressive_test`, проверяет current_database и пересоздаёт только её public schema. Не направлять fixture на действующую базу. Обычные dev credentials не являются паролями устанавливаемого продукта.

`tests/live_integration.py` требует отдельный локальный TEST server на 127.0.0.1:8321 (REQUIRE_TLS=0 исключительно loopback) и защищённый `/tmp/premier-test-admin-password`; создаёт реальные test tables/commands и два browser profiles. Файл с секретом не включается в исходный архив. Chromium должен быть установлен; `requirements-test.txt` содержит Playwright.

`tests/compose_checks.py`, `tests/backup_restore.py`, `tests/tls_login.py` — acceptance helpers именно этой изолированной Compose установки с host progressive.test, портом 8443, CA и защищённым compose-admin password file в /tmp. Они создают test fixture и перезапускают **app этой установки**, не CMS. Не запускать на рабочем казино. На целевом Linux следовать INSTALL.md и повторить rehearsal под реальные DNS/credentials.

## Остаточные ограничения

Блокеры и непроверенные интеграции — RELEASE_GATE.md. Не проверены: необязательный CMS production contract, hardware NumPad/controller, reboot/power-loss мини-PC, длительный soak/рост JSONB history, новый cloud task после publication. При новых исходниках требуется повторная проверка view layer и интеграций; текущий серверный тестовый результат не является боевым допуском.

## Постоянные страницы kiosk

Проверены `/table/<table_id>` (200), неизвестный/некорректный ID (404), стабильность ID/URL после rename/restart и неизменность фондов. Pairing code другого стола получает 409 и остаётся пригодным для правильного стола. Device credential чужого стола получает 403 на state/lease/stream и не меняет фонды. В независимых браузерах открывались отдельные постоянные URL; ошибочная привязка блокировалась до игрового ввода.

Последний browser rerun также проверил ссылки kiosk в админке. Выявленный race buffered SSE/offline исправлен: browser offline закрывает stream, свежие buffered события не восстанавливают online, navigator.onLine дополнительно блокирует финансовый ввод; offline banner отображается поверх winner overlay. Повторный сценарий offline/reconnect прошёл без JS errors.

## Проверки после получения досье и ZIP

- Файлы сохранены без исполнения встроенного Progressive financial engine. Числовая модель совпала с серверной тестовой конфигурацией.
- Backend: 35 passed; после уточнения malformed modes отдельно пройден целевой тест переключения (1 passed). Некорректные modes отвергаются 422; отключение текущего режима — 409.
- Облачная browser integration: F4 в обоих направлениях, настоящий Baccarat engine и отдельный ввод, сохранность раунда/фондов/истории, jackpot поверх Baccarat, возврат без потери shoe. Offline блокирует и финансовые команды, и локальный Baccarat ввод. Ошибок JS/загрузки static ресурсов нет.
- Compose app собран заново, работает от UID 10001; up --wait проверяет здоровье. MD5 полного casino state до/после реального process replacement совпал. Сертификат-проверенные HTTPS health и постоянная страница существующего Table 1 возвращают 200. Локальный hostname проверяется с --noproxy, без отключения TLS.
- Публичная галерея и 11 исходных MP4 сохранены; ffprobe подтверждает H.264 1280×720 и длительность 2.8–4.8 s. Это исходное разрешение роликов, не 1080p экспорт.

`tests/view_checks.py` проверяет пять вариантов дизайна, пять фондов/фиксированных выплат, серверные лимиты Baccarat, загрузку видео metadata и галерею 11 роликов. Требует тот же отдельный TEST server/защищённый password file, что live_integration.py. Скриншоты 1920×1080 сохраняются в docs/screenshots. Проверки используют строгую CSP; unsafe-eval/inline разрешения не добавляются.

## Последние решения владельца

Проверены 42 backend tests: sequential same-tier approvals на двух столах и разных боксах одного раунда; чужой стол продолжает ставки при pending; верхние категории доступны PIT или Admin; сумма FIRST FIVE берётся при approval; atomic claims по нескольким боксам; повторная выплата одному боксу запрещена; 4 500 TZS учитываются отдельно с day/table/casino reports и reversal; Baccarat history/shoe/limits snapshots/revision/idempotency/undo/report сохраняются на сервере; отдельный Baccarat table не принимает Progressive wagers.

`tests/owner_rules_browser.py`: два выбранных бокса получили отдельные fixed awards; Baccarat использует SERVER DISPLAY; два результата восстановились после page reload; первый сохранил minimum 5 000, второй — 10 000 после изменения лимитов; JS errors отсутствуют. `live_integration.py` повторно прошёл с двумя браузерами и 20 SSE clients; показ winner/режим/история/offline/binding сохранены, static ошибок нет. Последний короткий delivery spread 228.4 ms, display spread 66 ms — не гарантия физической сети.

Обновлённый Docker app собран и запущен через up --wait. Старый TEST config переведён на PIT OR Admin через dry-run и журналируемое применение версии 2; тест доказывает сохранность старых rounds/pools и идемпотентность helper. Владелец подтвердил исходную формулу FIRST FIVE: стартовая сумма плюс накопленные отчисления текущего фонда; SEVEN — fixed. Hardware deferred пользователем, production_released=false.

После последнего уточнения FIRST FIVE/SEVEN: четыре целевые проверки payout/seed/fixed/sequential/PIT прошли (4 passed, 2.68 s). Код формул не менялся: он совпадает с подтверждённым правилом.

## Веб-тест без kiosk

tests/web_controls_browser.py прошёл: только мышью выбраны боксы 1/3, подтверждены/закрыты ставки, оформлены две fixed выплаты; панель доступна внутри модального окна; Baccarat результат и F4 с сохранением серверной истории; обычная kiosk страница без панели; offline не закрывает денежный раунд; JS errors отсутствуют. Node keys test также прошёл. Backend не менялся, новый full backend run не требовался. Новый Docker image содержит test-controls.mjs, его содержимое проверено через HTTPS с Caddy CA. Публичный веб-адрес не опубликован и пользовательский доступ извне не проверен.

## Получение через GitHub и Windows Docker — 9 октября 2026

Добавлены `compose.windows.yaml`, `scripts/start-windows.ps1` и `docs/WINDOWS_TEST.md`. 128 исходных файлов (~22,4 MiB), без `.env`, виртуального окружения, wheelhouse, резервных копий и ключей, скопированы в отдельный каталог. В Python 3.12 Docker заново скачаны закреплённые зависимости по проверенному TLS; для облачной сети использованы существующий прокси и доверенный CA, без отключения проверки сертификатов. Dockerfile проверил SHA-256 wheels и собрал образ. Отдельный Compose-проект `premier-github-validation` успешно дождался готовности PostgreSQL, приложения и локального сертификата HTTPS. Через HTTPS с доверенным CA проверены вход, создание стола, код подключения, pairing, страница стола и модуль экранных кнопок. Ставка на два бокса дала 10000 TZS и ожидаемые отчисления 70/90/140/260/440. После перезапуска приложения сохранились администратор, ID стола, активный раунд и баланс Royal 12500440. PowerShell-сценарий непосредственно на Windows пока не выполнялся. Данные этой проверки не входят в репозиторий.
