# Premier Progressive — серверная тестовая версия

Самостоятельный Progressive для локального Linux: PostgreSQL 16, FastAPI, транзакционный учёт одного казино, пять общих фондов, столы/устройства, терминальный NumPad workflow, административный интерфейс, SSE, отчёты и отдельные credentials CMS.

**Это не допущенная к реальным ставкам система.** Подключены дизайн опубликованного Progressive и настоящий Baccarat MAX, включая графику и 11 MP4. F4 сохраняет раунд; финансы остаются серверными. Рабочая CMS не подключалась и не менялась. Флаг `production_released` всегда false. См. [блокеры](docs/RELEASE_GATE.md).

- [Установка сервера, TLS, backup/restore, upgrade](docs/INSTALL.md)
- [Linux kiosk, клавиши, инструкция дилера и администратора](docs/OPERATIONS.md)
- [Архитектура, финансовые правила, конкурентность и бизнес-день](docs/ARCHITECTURE.md)
- [Версионированное API и CMS contract](docs/API.md)
- [Контроллер и simulator](docs/CONTROLLER.md)
- [Результаты проверок](docs/TEST_RESULTS.md)

## Тест на Windows

[Инструкция для Windows и Docker Desktop](docs/WINDOWS_TEST.md): получение через GitHub и сборка без установки Python на компьютер.

## Краткий старт в отдельной тестовой установке

На Ubuntu/Debian с установленным Docker Engine и Compose v2:

```sh
cp .env.example .env
chmod 600 .env
# В .env: уникальный POSTGRES_PASSWORD (openssl rand -hex 32), локальное DNS-имя и свободный HTTPS-порт.
docker compose up -d db
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
PATH="$PWD/.venv/bin:$PATH" ./scripts/prepare-wheels.sh
docker compose build app
docker compose run --rm app python -m app.bootstrap
# Интерактивно ввести уникальный пароль первого администратора, не менее 12 символов.
docker compose up -d --wait
```

После установки доверенного локального CA открыть HTTPS-адрес сервера `/admin`, зарегистрировать стол, выполнить `pair_create` и открыть показанный адрес `/table/<table_id>` на терминале и ввести код этого стола. Никаких стандартных паролей или автоматического импорта браузерных денег.

## Разработка

Работать в существующем checkout: облачная задача уже изолирована, отдельный Git worktree не нужен.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
export DATABASE_URL='postgresql://<user>:<password>@127.0.0.1:<port>/<isolated_database>'
.venv/bin/python -m app.bootstrap
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8321
```

`REQUIRE_TLS=0` допустим только для изолированных локальных тестов с binding 127.0.0.1; Compose всегда требует TLS. Проверки используют отдельную БД `progressive_test`, уничтожают **только её** public schema и требуют тестовый PostgreSQL на 127.0.0.1:55432. Команды и безопасные ограничения приведены в TEST_RESULTS.

Материалы пользователя и публичные исходники: [сверка источников](docs/SOURCE_RECONCILIATION.md).

Подтверждённые решения владельца: [OWNER_DECISIONS.md](docs/OWNER_DECISIONS.md). Baccarat history теперь серверная; отдельные столы/версии лимитов, grouped winning boxes, sequential approvals и non-jackpot reporting реализованы.

Тестирование без kiosk/NumPad: [WEB_TEST.md](docs/WEB_TEST.md). В админке у TEST столов есть ссылка «Тест в браузере»; ?test_controls=1 включает экранные клавиши через обычный серверный workflow.
