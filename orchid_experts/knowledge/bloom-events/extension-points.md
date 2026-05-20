<!-- Source: derived from orchid-website/src/content/concepts/pollen-bloom.mdx and codebase analysis -->

# Extension Points

The Pollen+Bloom system provides multiple extension points for custom behavior. Each uses the component reference pattern (`{class, ...}`) for pluggable implementations.

## Custom Producers

Producers generate signals from external sources. Built-in producers include `SchedulerProducer` (cron/interval), `InternalEmissionProducer` (agent-emitted signals), and `HTTPIngestionProducer` (webhooks, auto-mounted by orchid-api).

To create a custom producer, implement the `OrchidSignalProducer` ABC:

```python
from orchid_ai.core.events.producer import OrchidSignalProducer

class KafkaSignalProducer(OrchidSignalProducer):
    def __init__(self, bootstrap_servers: str, topic: str):
        self._servers = bootstrap_servers
        self._topic = topic

    async def start(self) -> None:
        self._consumer = await self._create_consumer()
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        self._task.cancel()
        await self._consumer.close()

    async def _consume_loop(self) -> None:
        async for message in self._consumer:
            signal = self._parse_signal(message)
            await self._dispatcher.ingest(signal)
```

Register in YAML:

```yaml
events:
  producers:
    - class: myapp.events.producers.KafkaSignalProducer
      bootstrap_servers: kafka:9092
      topic: signals
```

## Custom Processors

Processors drain the queue and execute Blooms. The built-in `AsyncioWorkerPoolProcessor` handles most use cases with configurable concurrency. To create a custom processor:

```python
from orchid_ai.core.events.processor import OrchidSignalProcessor

class DedicatedQueueProcessor(OrchidSignalProcessor):
    async def drain_one(self) -> bool:
        signal = await self._queue.dequeue()
        if signal is None:
            return False
        # Match triggers, execute Blooms
        trigger = await self._match_trigger(signal)
        if trigger:
            await self._execute_bloom(trigger, signal)
        return True
```

## Middleware

Signal ingestion middleware runs on every `dispatcher.ingest()` call before persistence. Middleware can enrich, validate, tag, or filter signals:

```python
from orchid_ai.events.middleware import SignalIngestMiddleware

class GeoEnrichmentMiddleware(SignalIngestMiddleware):
    async def process(self, signal: Signal) -> Signal:
        if ip := signal.payload.get("ip"):
            signal.payload["geo"] = await self._lookup_geo(ip)
        return signal

class FilterMiddleware(SignalIngestMiddleware):
    async def process(self, signal: Signal) -> Signal | None:
        if signal.payload.get("spam_score", 0) > 0.9:
            return None  # Drop the signal
        return signal
```

```yaml
events:
  middleware:
    - class: myapp.events.middleware.GeoEnrichmentMiddleware
    - class: myapp.events.middleware.FilterMiddleware
      spam_threshold: 0.9
```

## Custom Validators

Webhook validators authenticate signal sources. Built-in options are `HMACValidator` (SHA-256 signature) and `BearerValidator` (token check):

```python
from orchid_ai.events.auth import SignalValidator

class JWTValidator(SignalValidator):
    def __init__(self, jwks_url: str, audience: str):
        self._jwks_url = jwks_url
        self._audience = audience

    async def validate(self, body: bytes, headers: dict) -> bool:
        token = headers.get("Authorization", "").replace("Bearer ", "")
        try:
            await self._verify_jwt(token)
            return True
        except Exception:
            return False
```

```yaml
ingestion:
  sources:
    - id: jwt-service
      validator:
        class: myapp.events.auth.JWTValidator
        jwks_url: https://auth.example.com/.well-known/jwks.json
        audience: orchid-signals
      allowed_types: [system.alert.*]
```

## Custom Schedulers

Alternative scheduling backends beyond the built-in `APSchedulerBackend`:

```python
class CeleryScheduler(OrchidScheduler):
    async def add_job(self, schedule_id: str, cron: str, callback) -> None:
        # Register periodic task in Celery Beat
        ...

    async def remove_job(self, schedule_id: str) -> None:
        # Remove from Celery Beat
        ...
```

## Store Backends

Custom storage for the seven events tables (signals, signal_queue, signal_queue_dead_letter, triggers, schedules, job_runs, signal_sources):

```python
class MongoEventStorage(OrchidSignalStore, OrchidJobStore,
                         OrchidScheduleStore, OrchidTriggerStore):
    async def store_signal(self, signal: Signal) -> None:
        await self._db.signals.insert_one(signal.__dict__)

    async def get_signal(self, signal_id: str) -> Signal | None:
        doc = await self._db.signals.find_one({"id": signal_id})
        return Signal(**doc) if doc else None
```

## Extension Registration

All extensions use the same component reference pattern. The class is resolved via `importlib` at startup. Additional fields are passed as keyword arguments to the constructor. Environment variable interpolation is supported for secret fields.
