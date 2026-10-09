# Ubuntu/Debian: установка независимого сервера

## Предварительные условия

Docker Engine + Compose v2 из официального репозитория Docker; локальные DNS/NTP, постоянный диск, резервное питание и backup destination. PostgreSQL и приложение запускаются отдельно от CMS. На историческом arucms ничего не устанавливалось. Порты 3210/3211 не используются; значение 8443 — настраиваемый исходный выбор, проверьте `ss -lntp` на целевом сервере.

1. Поместить исходники в `/opt/premier-progressive` (либо выбранный путь), открыть README.
2. Скопировать `.env.example` в `.env`, chmod 600. Задать **новый** hex password `openssl rand -hex 32`, внутреннее DNS-имя и свободный HTTPS-порт. Не использовать тестовый пароль облачной базы.
3. DNS-имя должно разрешаться с каждого терминала. Не менять CMS DNS/службы.
4. `docker compose up -d db`; на host нужны python3-pip/venv, затем `./scripts/prepare-wheels.sh` и `docker compose build app`. Скрипт загружает pinned wheels для Python 3.12 и CPU этой машины (x86_64/aarch64); Docker build проверяет SHA-256 и не требует PyPI из контейнера. Для изолированной подготовки можно использовать venv, как в README. Для переноса на другой CPU собрать bundle заново. Docker образы также заранее загрузить в казино с ограниченным интернетом.
5. `docker compose run --rm app python -m app.bootstrap`. Уникальный личный admin password (min 12). Повторный bootstrap отказывается менять существующую БД. Initialization создаёт TEST casino, не переносит localStorage.
6. `docker compose up -d --wait`. Restart policy обеспечивает автозапуск после Docker boot (`systemctl enable --now docker` на целевой машине).
7. Проверить `docker compose ps`, `docker compose logs --tail 50 app`, HTTPS `/health`, вход `/admin`, регистрацию стола и отдельный test round до реального использования.

App/DB не публикуют host ports. Снаружи только Caddy HTTPS. App доверяет forwarded headers внутри отдельной Compose network; не публикуйте его порт и не присоединяйте произвольные контейнеры к этой сети. Не открывайте БД терминалам.

## TLS в локальной сети без интернета

Caddy `tls internal` создаёт собственный CA и сертификат для PROGRESSIVE_HOST. CA и БД сохраняются в volumes.

```sh
docker compose cp tls:/data/caddy/pki/authorities/local/root.crt ./premier-root.crt
# На каждом Linux-терминале, после независимой проверки fingerprint этого CA:
sudo install -m 0644 premier-root.crt /usr/local/share/ca-certificates/premier-progressive.crt
sudo update-ca-certificates
# Если Chromium использует отдельное NSS-хранилище пользователя:
mkdir -p "$HOME/.pki/nssdb"
# libnss3-tools; certutil -N только для НОВОЙ NSS DB, не перезаписывать существующую.
certutil -A -d sql:"$HOME/.pki/nssdb" -n 'Premier local CA' -t 'C,,' -i premier-root.crt
```

Не отключать TLS verification и не применять `--ignore-certificate-errors`. Корневой private key хранить только на сервере, защищать backups Caddy. Публичный CA или собственный существующий enterprise CA возможен через замену Caddy TLS configuration на целевом сервере после review. Терминалы могут работать без внешнего интернета после установки.

## Backup

`./scripts/backup.sh`: PostgreSQL custom-format dump с checksum, mode 0600, каталог 0700. Скрипт не выводит credentials. Для согласованного снимка PostgreSQL использует MVCC; volume не копируется на лету. Dump содержит identities/sessions и персональные metadata: хранить зашифрованно вне сервера, с ограниченным доступом. Внешнее шифрование/перенос и расписание — настройки площадки.

Ежедневно (и перед upgrade) запускать backup сервисным пользователем с Docker permission. Такой доступ равносилен root и должен быть ограничен. Пример cron: `15 4 * * * cd /opt/premier-progressive && ./scripts/backup.sh` (UTC; подобрать время под площадку).

Резервировать `.env` защищённо и Caddy data отдельно; certificate keys не должны попадать в Git. PostgreSQL restore сам по себе не восстанавливает TLS identity.

## Restore без стирания рабочей базы

```sh
./scripts/restore.sh backups/progressive-YYYYMMDDTHHMMSSZ.dump progressive_restore_rehearsal
```

Создаётся **новая** БД; скрипт отказывается использовать штатное имя. Проверить checksum, событие initialization, последний hash цепи, текущие balances, rounds, claims и reconciliation. После испытания и отдельного согласованного maintenance window переключить DATABASE_URL приложения на восстановленную БД. В реальном outage не применять команды к восстановленной и старой БД одновременно. Сессии/устройства из backup пересмотреть и при необходимости отозвать, чтобы исключить старые credentials. Архивы исходников и конфигурации должны соответствовать версии миграций.

## Upgrade

`./scripts/upgrade.sh` делает backup, rebuild и restart без удаления volumes. Сначала испытать release на восстановленной тестовой БД. После запуска migration version проверяется. Текущая схема v1; последующие изменения должны добавлять новую миграцию с проверкой совместимости. Для rollback старого приложения убедиться в совместимости схемы; иначе восстановить проверенный backup в новую БД. **Никогда `docker compose down -v` для обновления.**

## Терминал на том же сервере

Допустим, но URL остаётся HTTPS-адресом сервера. Использовать тот же CA, отдельного kiosk OS user, и только один operator profile. Архитектура допускает отдельные мини-PC для остальных столов.
