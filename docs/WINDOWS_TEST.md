# Тест Premier Progressive на Windows из GitHub

Нужен работающий Docker Desktop с Linux containers и Docker Compose v2. Python и Git на Windows не обязательны. Интернет требуется для получения базовых образов и закреплённых Python-пакетов. Все материалы экрана, включая видео, находятся в репозитории.

## Получить систему

Откройте https://github.com/pc-cms/proggresive-jp → Code → Download ZIP. Распакуйте ZIP, откройте папку с README.md и compose.windows.yaml, затем откройте PowerShell в этой папке. Команды не выполняйте из C:\Windows\system32.

Если Git установлен, можно вместо ZIP:

```powershell
git clone https://github.com/pc-cms/proggresive-jp.git
cd proggresive-jp
```

## Запуск

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-windows.ps1
```

Скрипт создаёт случайный пароль PostgreSQL в локальном `.env`, готовит зависимости внутри Docker, собирает приложение и запускает отдельный Compose-проект `premier-progressive-local-test`. При повторном запуске существующий `.env` и база сохраняются. Проекты HAPA он не останавливает. Если существующий `.env` содержит пустой POSTGRES_PASSWORD, задайте уникальное значение локально, не пересылая его в чат.

Далее добавьте созданный на вашем компьютере сертификат в доверенные сертификаты пользователя:

```powershell
certutil -user -addstore Root .\premier-root.crt
```

Перезапустите браузер. Для Firefox при необходимости импортируйте этот файл в доверенные центры сертификации для сайтов через настройки браузера.

Один раз создайте администратора новой базы:

```powershell
docker compose -f compose.windows.yaml exec app python -m app.bootstrap
```

Введите свой уникальный пароль длиной минимум 12 символов. Ввод не отображается. Логин `admin`. Повторная инициализация существующей базы запрещена.

Откройте https://localhost:8443/admin, зарегистрируйте стол Poker либо Baccarat, создайте код подключения и нажмите «Тест в браузере». Введите код и имя устройства; используйте экранную панель кнопок. У стола постоянный адрес `/table/<table_id>?test_controls=1`. Новый сервер получает собственные ID столов; ID из документов старой облачной тестовой базы не используйте.

Подробнее о сценариях: [WEB_TEST.md](WEB_TEST.md). Все операции тестовые; допуск к реальным ставкам не выполнен.

## Остановить и продолжить

```powershell
docker compose -f compose.windows.yaml stop
docker compose -f compose.windows.yaml up -d --wait
```

Не удаляйте Docker volumes и `.env`, если хотите сохранить историю. При занятом порте задайте `$env:PROGRESSIVE_HTTPS_PORT='9443'` до запуска и используйте https://localhost:9443/admin.

Диагностика:

```powershell
docker compose -f compose.windows.yaml ps
docker compose -f compose.windows.yaml logs --tail=100
```

Сборка и запуск Compose проверяются на Linux Docker. PowerShell-сценарий подготовлен для Windows, но его выполнение на Windows пока не проверено. Не публикуйте `.env`, пароли или приватные ключи сертификатов.
