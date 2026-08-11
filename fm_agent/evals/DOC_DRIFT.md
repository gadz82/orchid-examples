# Doc-vs-code drift report — 2026-08-05

Code checked: hydra (develop), notification-be, paas-notification-meta, mailer-service-be.
Corpus files in `outputs/confluence/` are kept verbatim as retrieved; the corrections live in
`golden.draft.yaml` answers and in this report. Use this list to fix the Confluence pages.

## Refuted (doc is wrong)

| # | Doc claim | Code truth | Page to fix |
| --- | --- | --- | --- |
| 1 | Meta registration sends meta.json **minus** notificationGroupId/productCode | Payload is meta.json **plus** injected notificationGroupId + productCode (`{...{notificationGroupId, productCode}, ...meta}`) | 3688956071 |
| 2 | DST for Product API: iss="staff.support", uid required, scope/ver validated | Authorizer requires only tid/iid/pty; sub must be "notification" (key path); iss = calling productCode; scope/ver unvalidated conventions; uid not required | 5368316863 |
| 3 | webhookCallbackEnabled required for scheduled triggers | Not enforced — exists only as TODO comments; only inverse rule enforced (wakeup path mandatory if enabled) | 3407052831 |
| 4 | Delivery status has an Athena workgroup `${envName}-athena-delivery-status-workgroup` | No such workgroup; queries use `${envName}-athena-user-log-workgroup`, same bucket/DB as user logs | 5423235160 |
| 5 | Pipeline job named `create-notification-meta` | Job is `create-metas` (plus manual `create-templates`); runs lms, peerboard, integrationLogging — not lms only | 3688956071 |

## Corrected specifics (doc mostly right, details off)

| # | Topic | Correction | Page |
| --- | --- | --- | --- |
| 6 | Trigger gating | TWO toggles ANDed: TOGGLE_PAAS_NOTIFICATIONS **and** TOGGLE_PAAS_NOTIFICATION_ENABLE_TRIGGERS | 3688890498 |
| 7 | Collector class | `MessengerListener` (listener/), not `MessengerListenerService`; hooks EVENT_AFTER_REQUEST → supervise() | 3687350290 |
| 8 | Event-bus payload | Keys: event_type, notification_ids, event_data, id_author, normalized_event (no `notifications_setup_ids`); one event per setup id, chunked ×5 | 3687350290 |
| 9 | Init defaults | Four, not two: HydraValidationHandler, HydraValidationProvider, **HydraSupervisor, HydraNormalizer** — registered by NotificationApp plugin, not MessengerComponent | 3687350290 |
| 10 | setValidation | Lives on HydraValidationProvider (via getValidationProvider()), not on messengerValidationService; service method for handlers is `registerHandler` | 3687022702 |
| 11 | Custom validators | Implement only `getFilters()`; `matchEntities()` already generic in AbstractValidation | 3687022702 |
| 12 | Factory fallbacks | Scheduled AND event-provider paths fall back to `DefaultHydraScheduledEventProviderHandler`; DefaultHydraScheduledEventHandler is a base class, never a default | 3688792065 |
| 13 | PollingAction | Returns `{success: bool}`; schedules pushed asynchronously by PollingFunction.sendSchedules(), not in the response | 3688792065 |
| 14 | Transports | Six, not five: + `calendar` (migration 20260324160702) | 3407052831 |
| 15 | Triggers | + `scheduled.manual` | 3407052831 |
| 16 | Product DELETE cascade | FK-level; setup_template FK dropped (orphaned), S3 objects and Dynamo mirrors not cleaned; PRODUCT delete also removes its modules | 3407052831 |
| 17 | Poller | Cron fires hourly at :01 unconditionally; producer filters setups (scheduled/event/before-after/enabled); consumer uses product.webhookCallbackScheduler for the URL | 3407052831 |
| 18 | Wake-up queue | DLQ = `wakeupDeadLetterQueue.fifo` (14d); main queue retention 15 min | 5412880531 |
| 19 | Schedule states | Lowercase: to_wake_up/processing/waked_up/**sent**/retry_failed (doc omits sent) | 5412880531 |
| 20 | Fault tolerance | Keys off wakeup_target_time (not "entered PROCESSING >1h"), RECURRING mode only, resets failed_cb_count, recomputes wakeup; rule inactive in develop/integration | 5412880531 |
| 21 | DynamoDB backoff | `1000 + 2^r*15`ms only in claimSchedule; generic batch path is `2^r*15` | 5412880531 |
| 22 | deliveryId transports | Generated for email, slack, pushNotification, calendar — not just email/push | 5423235160 |
| 23 | Firehose/Glue names | Contain `-log-`: firehose-delivery-status-log-stream / glue-delivery-status-log-table | 5423235160 |
| 24 | SNS wire statuses | Only delivered/failed on the topic; queued is log/API-side | 5423235160 |
| 25 | Env var naming | Mailer: DELIVERY_STATUS_SNS_ARN vs notification-be: DELIVERY_STATUS_SNS_TOPIC_ARN — same topic, two names | 5423235160 |
| 26 | Templating | Mustache (mustache ^4.2.0), not "Moustache" | 3134029869 |
| 27 | Poller lambda name | `${envName}-lmb-setup-poller` (asset dir is poller-producer) | 5412880531 / 3258023941 |
| 28 | deliveryStatus filter | Query-string array param, Superadmin-only — not a body filter | 5423235160 |

## Unverifiable from mounted repos

- Local-env wand commands / whitelist / Leapp behavior (repo `docebo/development/local-environment` not mounted) — pages 4044456058.
- notifications-admin Angular lib specifics — page 3406954523.
- Dictionary duplicated in the Legacy codebase — legacy repo not mounted (Hydra side confirmed).
