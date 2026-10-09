# Controller protocol v1

Аппаратный controller_id — зарегистрированная device identity, привязанная к table_id. Отдельный physical block получает собственные credentials через pairing (в v1 только одно active управляющее device на стол, не параллельно отдельному terminal operator). Для совместного экрана и hardware adapter требуется утверждённая схема единственного command producer/lease.

Transport HTTPS API v1 + authenticated SSE. Команда:

```json
{"command_id":"UUID","operator_id":"unique-connection-owner","sequence":1,"op":"confirm","payload":{"table_id":"ID","round_id":"next_round_id","boxes":[1,3]}}
```

Ответ содержит тот же command_id, `{sequence,committed:true}`, round/participants. До отправки приобрести operator lease. При reconnect GET state, GET command status для неизвестного результата; повторить тем же ID/sequence. Следующий sequence только после committed. Не выполнять локальных денежных действий. Если sequence rejected, получить полное состояние, не переписывать ранее отправленное намерение автоматически новым номером.

Indicators = confirmed round boxes; pending approvals и winner = серверные claims/events; связь = успешный heartbeat/SSE с timeout. Лампочка отражает состояние, не подтверждает приём финансовой операции. После disconnect блокировать кнопки новых финансовых команд, показать fault, при reconnect заново применить полный state.

Simulator: `scripts/controller_simulator.py --url ... --token-file ... --ca ... --box 1`. Token file mode 0600, сертификат проверяется. Выполнять только на TEST installation; simulator действительно подтверждает test stake. Sequence/idempotency/lease покрыты API tests. Реальный USB/physical controller, GPIO, напряжения, распиновка и электрическая безопасность не проверены и не выбраны.
