# API v1 / CMS contract

Base path `/api/v1`. HTTPS обязателен, `Authorization: Bearer <token>`. Полная структурная схема запросов в `/openapi.json` (генерируется FastAPI); команды имеют серверную валидацию op-specific payload, см. таблицу ниже. Денежные суммы integer TZS; IDs непрозрачные строки. Ошибки: 401 authentication, 403 scope, 409 state/conflict/sequence/lease, 422 malformed. 429 — блокировка login после пяти ошибок на пять минут.

## Credentials/scopes

| Role | Capabilities |
|---|---|
| device | Свой стол; operator lease; confirm/close/claim/mode; read authoritative own round/claims; global pools; public winner events |
| pit | Чтение, remote table commands, pit approvals при соответствующей policy |
| admin | Управление казино, users/devices/tables, funds correction/reversal/approval, actual payment |
| cms_read | Только GET tables/pools/state/wins/events/reports; нет финансовых команд |
| cms_metadata | То же чтение + PATCH winner metadata; **нет** денежных команд |

Персональные admin/pit credentials задаются через principal_create. Для CMS создаётся отдельный principal/token; read не даёт права metadata-write. `principal_revoke` отзывает credentials; действующий SSE тоже перестаёт получать данные после revocation. Срок device/CMS tokens 365 дней, user session 24 часа. Ротация через controlled revoke и новый principal/pairing. Токены не логируются в публичные события.

## HTTP endpoints

- POST `login`: `{name,password}` → token и role. Только TLS, пароль не журналируется.
- POST `logout`: инвалидирует текущую сессию.
- POST `pair`: `{code,name,app_version,table_id?}` → device_id, table_id, token. Код одноразовый, 10 минут; существующее active device сначала revoke. Переданный table_id должен совпасть с pairing code, иначе 409 без расходования кода.
- POST `operator`: device-only `{operator_id}` → 15s lease. Продлевать каждые 5s; второй operator получает 409.
- POST `commands`: `{command_id,op,payload,operator_id?,sequence?}`. Devices требуют operator_id и sequence; admin/pit нет.
- GET `commands/{command_id}`: подтверждённый результат только для исходного principal; 404 означает «не committed», не «нельзя повторить».
- GET `state`: current config, shared pools, tables/rounds/claims, UTC server_time, business_date. Device получает только свой стол/раунд/claims и публичные сведения.
- GET `tables`, `pools`, `wins`, `devices` (devices admin-only).
- GET `events?after=0&limit=100`: durable event cursor, max 1000. CMS/pit/admin. После обработки сохранить последний seq, после reconnect продолжить. История не зависит от online CMS.
- GET `stream?after=0`: SSE с authenticated fetch, **не token в URL**. `winner` содержит win_id, tier/type/amount, table id/number/name, box, show_at/show_until; `state` периодически содержит полный актуальный view. `winner` никогда не содержит winner_name/player_id/PIN.
- GET `reports?start=2026-10-08&end=2026-10-08&table_id=...&format=json|csv`: inclusive business dates.
- PATCH `wins/{win_id}/metadata`: только `winner_name`, `cms_player_id`, `note`, nullable строки с ограничениями длины. Любые amount/tier/approval/payout/table поля дают 422. Изменение журналируется.

## Commands

Все намерения имеют новый UUID command_id. При timeout сначала GET status, затем повторить **те же op/payload/sequence/ID**. Повтор с другим намерением или от другого principal получает 409. Response: `{command_id,result,acknowledgment:{sequence,committed:true}}`.

| op | Payload | Authority |
|---|---|---|
| table_register | number,name, game?,boxes?,minimum?,maximum? | admin |
| table_update | table_id,name?,game?,active?,minimum?,maximum?,boxes? | admin |
| pair_create | table_id | admin |
| device_revoke | device_id,reason | admin |
| principal_create | name,role,password (admin/pit only) | admin; CMS response содержит token |
| principal_revoke | principal_id,reason | admin, self-revoke запрещён |
| confirm | table_id,round_id=table.next_round_id,boxes:[1..N] | device own table / admin / pit |
| close | table_id,round_id | device own table / admin / pit |
| claim | table_id,round_id,box,tier:1..5,type:progressive\|fixed | device own table / admin / pit |
| approve | claim_id | По conditions.approval; upper tiers admin; disputed запрещено |
| reject | claim_id,reason | admin |
| paid | claim_id,reference | admin, только после approval |
| reverse | table_id,round_id,reason | admin |
| adjust | tier,delta (signed integer),reason | admin; только отдельная auditable correction |
| config_update | config:{stake,tiers,announcement_seconds},reason | admin; complete config, версия серверная |
| mode | table_id,mode | device own table / admin / pit; только доступный verified mode |

Tier config: `{code,name,seed,contribution,fixed,approval}`. Пять уникальных code 1–5. Approval none/pit/admin/pit_admin, для 3–5 только admin/pit_admin. Исходные config на ARCHITECTURE.md. No hidden reset при config update.

`sequence`: следующий номер для устройства, полученный как state.tables[0].device_sequence+1. Не увеличивать при повторе, ошибках или неподтверждённом результате. Новый pairing имеет новую identity и свой counter. ID гарантирует exactly-once effect, sequence блокирует устаревшую/переставленную новую команду. Lease может обновиться при reconnect без изменения финансового намерения.

## Проверяемый CMS mock

`tests/test_api.py::test_cms_scopes_metadata_only` создаёт отдельные read/metadata principals, читает фонды, проверяет 403 для денежного изменения, 403 для metadata через read и 422 для запрещённого amount, подтверждает auditable metadata patch. Это проверка предложенного контракта, не фактическое подключение рабочей CMS.

`python scripts/cms_adapter.py --url <HTTPS> --token-file <mode0600> --ca <root.crt> --cursor-file <path>` выгружает доступные события с durable cursor. Сохранять данные в целевой CMS нужно через её **реальный** контракт после получения доступа; существующих таблиц/endpoint/ключей мы не предполагаем.

Отсутствие CMS не останавливает игру; журнал продолжает хранить события. Реальный CMS read credential не может вызвать финансовые op или записать факт выдачи денег.

Terminal pages: GET `/table/{table_id}` — постоянный kiosk экран зарегистрированного стола; неизвестный ID 404. GET tables/state возвращает kiosk_path. Device-authenticated requests с `X-Premier-Table` другого стола получают 403, до выдачи состояния/выполнения команды/рассылки.

Display modes: table_register разрешает progressive и baccarat. table_update может задать modes из этих двух значений; нельзя удалить текущий режим до переключения. Команда mode меняет только представление и не закрывает/создаёт раунд, не изменяет pools/claims. Старые таблицы сохраняют modes до явного изменения администратором.

## Решения владельца 8 октября

`claims`: payload {table_id, round_id, boxes:[1,2], tier:1, type:"fixed"}; возвращает {claims:[...]}. Все боксы в одной транзакции, общий command_id защищает группу от повторов. Разные комбинации — разные группы. Одна неотклонённая заявка на бокс; tier 1–2 утверждает дилер, tier 3–5 PIT или Admin для новых условий раунда. Параллельные same-tier approvals сериализуются, новых конфликтов по одному лишь совпадению tier нет. Pending останавливает только его стол.

Report: non_jackpot_pool содержит casino_opening/closing и attributed allocated/reversed/net; totals дополнены bets_reversed и bets_net. Эти суммы не вычитают seed/top-up без отдельного финансового решения. Отчёт допускает день/месяц/интервал и table_id, отсутствие table_id означает казино.

Baccarat commands: baccarat_result {table_id,revision,outcome:"P"|"B"|"T",special?:"dragon7"|...}; baccarat_pair {side:"P"|"B"}; baccarat_undo; baccarat_shoe; baccarat_settings {settings:{mode,...}}. Во всех revision/table_id обязательны; stale revision 409. Транспорт/device sequence/operator lease те же. State.tables[].baccarat содержит revision/shoe/hands/history/pending/settings. Limits меняются через администраторский table_update, руки сохраняют limits snapshot. Report.baccarat: recorded/undone/net, player/banker/tie и пары — потоки событий за выбранный business period. Покерные фонды не затрагиваются. table_register game:"baccarat" создаёт отдельный стол MAX и блокирует Progressive wagers.
