# Beacon — Handover

> Source of truth for building Beacon. Read this file fully before writing code.
> Owner: Jeya Viknan (single admin user).
> Deadline: production-ready and demo-able on Jeya's iPhone by **Mon 26 Oct 2026** (DevOps interview on 27 Oct).

---

## 0. TL;DR

Beacon is a personal **uptime and incident monitor** for every live product Jeya has built: personal projects and client work.
It checks each product every minute, opens an incident when one goes down, alerts Jeya's iPhone **before users notice**, and shows uptime, latency and incident history.

- **Phone-first:** an installable web app (PWA) on iPhone with push notifications.
- **Backend:** AWS serverless, **strictly AWS free tier**.
- **Built to production standard:** Terraform, CI/CD with GitHub Actions (OIDC), alarms on Beacon's own health, runbooks, failure drills and RCAs.
- **No client names anywhere.** Each product has a free-text **note** instead (e.g. "Client work — appointment booking for a clinic chain").

---

## 1. Goals and non-goals

| ID | Goal |
|---|---|
| G1 | Home screen shows every product's live status at a glance. |
| G2 | Tapping a product shows details: uptime, latency, incidents, note, links, stack. |
| G3 | Add, edit, pause, resume and delete products from the phone. Monitoring follows within ~1 minute, no redeploy. |
| G4 | DOWN / RECOVERED alerts reach the phone (Web Push), email and PagerDuty. |
| G5 | Beacon itself runs like a production service: IaC, CI/CD, alarms on its own health, a dead-man's switch, runbooks. |
| G6 | Stays within AWS free tier (see §6 guardrails). |

**Non-goals (v1):** multiple users or teams, public sign-up, client names, SMS alerts, native App Store app, custom domain, multi-region by default (supported as an opt-in, see §8.6).

---

## 2. User and key flows

Single admin user: Jeya.

1. **First run:** open the CloudFront URL in Safari → log in → Share → Add to Home Screen → open from the home screen → Settings → Enable notifications.
2. **Add a product:** "+" → name, kind (Personal / Client work), note, URL to check, optional keyword, live URL, GitHub URL, stack tags, SLO target → Save. It appears on Home and gets checked within ~1 minute.
3. **Outage:** product fails 2 checks in a row → incident opens → push "🔴 DOWN: <name> — HTTP 502" + email + PagerDuty page → Jeya opens the app → Acknowledge.
4. **Recovery:** product passes 2 checks in a row → incident resolves → push "🟢 RECOVERED: <name> — down for 6m 12s" + PagerDuty resolve.
5. **Demo mode (for the interview):** Settings → "Break demo target" → within ~1–2 minutes the phone receives a DOWN alert → "Fix demo target" → RECOVERED alert.

---

## 3. Product requirements (screens)

### 3.1 Home (`/`)
- Header: "Beacon" + overall status pill: "All systems operational" (green) / "1 product down" (red) / "2 degraded" (amber).
- Summary chips: Up · Degraded · Down · Paused (counts).
- Filter tabs: All · Personal · Client work.
- Product cards, sorted **Down → Degraded → Up → Paused**, then by `sortOrder`, then by name. Each card shows:
  - status dot + status text (never colour alone)
  - name, kind badge
  - note (1 line, truncated)
  - uptime 30d (e.g. `99.94%`)
  - last latency (e.g. `312 ms`)
  - "checked 23s ago"
  - 24h strip: 24 small bars, one per hour, coloured by that hour's uptime
- Auto-refresh every 30 s, plus pull-to-refresh / refresh button.
- Empty state: "No products yet — tap + to add your first one."
- If not installed (`navigator.standalone !== true` on iOS), show a dismissible tip: "Tap Share → Add to Home Screen to get alerts."

### 3.2 Product detail (`/p/:id`)
- Big status + "since 2h 14m".
- Open-incident banner (if any): cause, started at, duration ticking, **Acknowledge** button.
- Stats grid:
  - uptime 24h / 7d / 30d
  - avg latency (24h)
  - p95 latency (last hour)
  - SLO target and **error budget remaining** for 30d (minutes)
- Response-time chart (24h, 5-minute buckets; failed buckets marked red).
- 30-day daily uptime bars.
- Incident history (start, duration, cause, state).
- Recent checks (last 20: time, region, HTTP code, latency, error).
- Info: note (full), live URL (opens in browser), GitHub URL, stack chips, check settings.
- Actions: **Test now** (runs a check immediately and shows the result), Pause/Resume, Edit, Delete (with confirmation).

### 3.3 Add / Edit product (`/new`, `/p/:id/edit`)

| Field | Required | Default / validation |
|---|---|---|
| name | yes | 1–60 chars |
| kind | yes | `personal` \| `client` |
| note | no | ≤ 280 chars, free text (no client names needed) |
| checkUrl | yes | `http(s)://` only, public host (SSRF rules §8.4) |
| method | no | `GET` (or `HEAD`) |
| expectedStatus | no | `200-399` (range string) |
| keyword | no | substring that must appear in the body |
| timeoutMs | no | 10000 (1000–15000) |
| intervalMin | no | 1 (1 or 5) |
| latencyWarnMs | no | 2000 |
| openAfter | no | 2 consecutive failures (1–5) |
| resolveAfter | no | 2 consecutive successes (1–5) |
| sloTarget | no | 99.5 (90–99.99) |
| liveUrl | no | URL |
| githubUrl | no | URL |
| stack | no | up to 8 tags |
| sortOrder | no | 100 |

### 3.4 Incidents (`/incidents`)
Feed of all incidents across products, newest first, with an Open/All filter.

### 3.5 Settings (`/settings`)
- **Enable notifications** button. It must call `Notification.requestPermission()` from a user tap (iOS requirement), then subscribe and POST to the API.
- **Send test notification** (push + email).
- Channel status: Push (subscribed devices count), Email (configured), PagerDuty (configured yes/no).
- Demo: **Break demo target** / **Fix demo target**.
- App version (git SHA), API health, Logout.

### 3.6 Login (`/login`)
Password only (single admin). The JWT is stored in `localStorage`. On iOS, the home-screen app has its own storage, separate from Safari, so log in once inside the installed app.

---

## 4. Architecture

```
                    ┌────────────────────────── iPhone (PWA, Safari engine) ─────────────────────────┐
                    │  React app · service worker · Web Push                                          │
                    └───────────────┬───────────────────────────────────────────▲────────────────────┘
                                    │ HTTPS (same origin)                       │ Web Push (Apple push service)
                         ┌──────────▼──────────┐                                │
                         │  CloudFront (free)  │──/* ──▶ S3 (private, OAC): web app
                         │  + CF Function (SPA │                                │
                         │    rewrite)         │──/api/* ──▶ Lambda Function URL: api
                         └─────────────────────┘                    │           │
                                                                    ▼           │
  EventBridge Scheduler ──every 1 min──▶ Lambda: probe ──reads──▶ DynamoDB: CONFIG#MONITORS (snapshot)
  (one schedule per probe region)            │                      ▲  ▲
                                             │ 1 msg per run        │  │ writes products/config
                                             ▼                      │  │
                                    SQS: beacon-results ──▶ Lambda: processor ──▶ DynamoDB (checks, rollups,
                                    (+ DLQ)                         │                    products, incidents)
                                                                    │ ping each run ──▶ healthchecks.io (dead-man's switch)
                                                                    ▼
                                                     SNS: beacon-product-alerts ──▶ email (Jeya)
                                                                    │
                                                                    └──▶ Lambda: notifier ──▶ Web Push (VAPID) · PagerDuty Events v2

  EventBridge Scheduler ──daily 09:00 IST──▶ Lambda: maintenance (TLS expiry checks, daily summary push, cleanup)
  Lambda: demo-target (Function URL) ── returns 200 or 503 based on SSM /beacon/demo/healthy

  CloudWatch alarms (≤10) ──▶ SNS: beacon-ops-alerts ──▶ email + PagerDuty ("Beacon Platform" service)
```

**Two alert streams, deliberately separate:**
- `beacon-product-alerts`: the products Beacon watches are down or recovered.
- `beacon-ops-alerts`: **Beacon itself** is unhealthy (errors, queue backlog, probes not running).

**Who watches the watcher:**
- The processor pings healthchecks.io after every successful batch.
- If pings stop for more than 5 minutes, healthchecks.io alerts Jeya independently of AWS.

**Control plane vs data plane:**
- The API (control plane) publishes a compact **monitor snapshot** item to DynamoDB whenever products change.
- Probes (data plane) read only that one item per run.
- Probes never query product records directly, and adding or removing a product never needs a redeploy.

---

## 5. Tech stack and rationale

| Layer | Choice | Why |
|---|---|---|
| Mobile app | **PWA**: React 18 + TypeScript (strict) + Vite + `vite-plugin-pwa` (injectManifest) + Tailwind CSS + TanStack Query v5 + React Router v6 + Recharts + react-hook-form + zod | Free; installs on the iPhone home screen; **Web Push works on iOS 16.4+** for home-screen apps; deploys instantly via CI; no Apple Developer fee or App Store review. (Native iOS push would need the $99/yr Apple Developer Program.) |
| Backend compute | AWS Lambda, **Python 3.12, arm64** | Always-free tier (1M requests + 400k GB-s/month); Python is the automation language LeadSquared uses |
| Lambda libraries | `aws-lambda-powertools` (Logger, Tracer, Metrics, event handler, batch), `pydantic` v2, `httpx`, `PyJWT`, `argon2-cffi`, `pywebpush`, `python-ulid` | Production-grade logging/tracing; typed validation |
| API front door | Lambda **Function URL** behind CloudFront `/api/*` | API Gateway is not always-free; Function URLs are free; same origin, so no CORS |
| Scheduling | EventBridge **Scheduler** `rate(1 minute)` | 14M invocations/month free |
| Queue | SQS standard + DLQ | 1M requests/month free; decouples probes from processing; DLQ for poison messages |
| Database | DynamoDB single table, **provisioned** capacity, TTL | 25 GB + 25 RCU/WCU always free; TTL deletes are free |
| Notifications | SNS (email + Lambda), Web Push (VAPID), PagerDuty Events API v2 (free plan) | All free at this volume |
| Secrets | SSM Parameter Store, **standard tier**, SecureString | Free (Secrets Manager costs $0.40/secret/month) |
| Hosting | S3 (private) + CloudFront with OAC, default `*.cloudfront.net` domain | CloudFront always-free 1 TB + 10M requests; no Route 53 (a hosted zone costs $0.50/month) |
| IaC | **Terraform ≥ 1.10**, S3 backend with `use_lockfile = true` | Native S3 locking, no DynamoDB lock table needed |
| CI/CD | GitHub Actions + **OIDC** to AWS | No long-lived AWS keys anywhere |
| Observability | Powertools JSON logs (7-day retention), X-Ray tracing, CloudWatch alarms (≤10) + 1 dashboard, healthchecks.io, PagerDuty | Within always-free limits |

---

## 6. Free-tier guardrails (HARD RULES)

**Forbidden:** NAT Gateway · ALB/NLB · ECS/Fargate · EC2 · RDS/Aurora · ElastiCache · OpenSearch · API Gateway · Secrets Manager · KMS customer-managed keys · Route 53 hosted zones · CloudWatch Metric Streams · Lambda provisioned concurrency · SSM advanced parameters · Elastic IPs.

| Resource | Limit to respect |
|---|---|
| DynamoDB | Provisioned only; **total** RCU ≤ 25 and WCU ≤ 25 across table + GSIs (table 15/15, GSI1 5/5). TTL on all time-series items. |
| CloudWatch | ≤ 10 alarms, ≤ 10 custom metrics (Powertools EMF metrics count!), ≤ 3 dashboards; log group retention **7 days** on every log group |
| Lambda | 128–256 MB, arm64; probe timeout 50 s; no provisioned concurrency |
| X-Ray | Tracing on, default sampling (100k traces/month free) |
| S3 | One private bucket for the web app (a few MB); state bucket (KBs) |
| Probe regions | Default `["ap-south-1"]` only. Extra regions are opt-in; cross-region transfer costs a few paise/month (document this as a trade-off). |
| Budget | AWS Budget of **$1/month** with email alert at 50% and 100% (created in Terraform bootstrap) |

If a requirement cannot be met within these limits, **stop and ask Jeya**. Never quietly add a paid service.

Note for Jeya: AWS accounts created after 15 Jul 2025 are on the credit-based Free plan; older accounts have the legacy 12-month free tier plus always-free services. Check which one you have in Billing → Free Tier.

---

## 7. Data model — DynamoDB single table `beacon`

Keys: `PK` (S), `SK` (S). GSI1: `GSI1PK` (S), `GSI1SK` (S). TTL attribute: `ttl` (epoch seconds).

| Entity | PK | SK | GSI1PK / GSI1SK | TTL | Notes |
|---|---|---|---|---|---|
| Product | `PRODUCT#<ulid>` | `META` | `PRODUCTS` / `<sortOrder:05d>#<name>` | — | fields from §3.3 + live state below |
| Raw check | `PRODUCT#<id>` | `CHECK#<isoTs>#<region>` | — | 48 h | ok, httpCode, latencyMs, error, region, manual |
| Rollup 5-min | `PRODUCT#<id>` | `R5#<yyyymmddHHMM>` | — | 2 d | upMin, totalMin, latSum, latCount, latMax |
| Rollup hourly | `PRODUCT#<id>` | `RH#<yyyymmddHH>` | — | 8 d | same counters |
| Rollup daily | `PRODUCT#<id>` | `RD#<yyyymmdd>` | — | 400 d | same counters + downMinutes |
| Incident | `PRODUCT#<id>` | `INC#<isoStart>#<ulid>` | `INCIDENTS` / `<isoStart>` | — | see below |
| Push subscription | `PUSHSUB` | `<sha256(endpoint)>` | — | — | endpoint, keys{p256dh,auth}, ua, createdAt |
| Monitor snapshot | `CONFIG` | `MONITORS` | — | — | version, updatedAt, monitors[] (only fields probes need) |
| Settings | `CONFIG` | `SETTINGS` | — | — | quorum, defaults, channel toggles |
| Login throttle | `AUTH` | `THROTTLE` | — | 15 min | failures, lockedUntil |

**Product live-state fields** (updated by the processor):
`status` (`UP|DEGRADED|DOWN|PAUSED|UNKNOWN`), `statusSince`, `lastCheckAt`, `lastLatencyMs`, `lastHttpCode`, `lastError`, `regions` (map region → {ok, at, latencyMs, httpCode, error}), `consecutiveFailures`, `consecutiveSuccesses`, `consecutiveSlow`, `lastEvalMinute`, `openIncidentSk`, `recentLatencies` (ring buffer, last 60 ok latencies), `certExpiresAt`.

**Incident fields:**
`state` (`OPEN|ACKNOWLEDGED|RESOLVED`), `startedAt`, `acknowledgedAt`, `resolvedAt`, `durationSec`, `cause`, `firstError`, `failingRegions`, `timeline` (list of {at, event, detail}).

All times are UTC ISO-8601 in storage. The UI shows IST.

---

## 8. Monitoring engine

### 8.1 Probe (one Lambda per enabled region; triggered every minute)
1. `GetItem CONFIG/MONITORS` (cache in memory for 30 s).
2. Select monitors where `enabled` and `currentMinute % intervalMin == 0`.
3. Run checks concurrently (asyncio + `httpx.AsyncClient`, semaphore 20, total budget ≤ 45 s).
4. Send **one** SQS message per run to `beacon-results` in the home region.

Message shape:
```json
{"region":"ap-south-1","runAt":"2026-10-24T10:15:00Z","results":[
  {"productId":"01J...","ok":false,"httpCode":502,"latencyMs":431,"error":"HTTP 502","keywordOk":null}
]}
```

### 8.2 Check rules (one product, one region)
`ok = true` only if all of these hold:
- no network, DNS or TLS error
- the response arrives within `timeoutMs`
- the HTTP code is in `expectedStatus`
- `keyword` (if set) is found in the first 1 MB of the body

Error text is short and human-readable: `Timeout after 10000 ms`, `HTTP 502`, `Keyword "Welcome" missing`, `TLS: certificate expired`, `DNS: host not found`.

### 8.3 Processor (SQS trigger, batch size 10, partial batch failure reporting)
For each result:
1. Write the raw check.
2. Update the region entry on the product.
3. Increment R5 / RH / RD rollups with `UpdateItem ADD`.
4. Evaluate the state machine (§8.5).
5. Publish alerts.
6. Ping healthchecks.io once per batch on success.

All writes are idempotent per (product, region, runAt). Use condition expressions so a redelivered message cannot double-count.

### 8.4 SSRF protection (security-critical; covered by tests)
The probe and "Test now" must **refuse**:
- non-http(s) schemes
- hosts resolving to private, loopback, link-local or metadata addresses: `10/8`, `172.16/12`, `192.168/16`, `127/8`, `169.254/16` (incl. `169.254.169.254`), `::1`, `fc00::/7`, `fe80::/10`, `0.0.0.0`

Also:
- Resolve DNS first and check every resolved IP.
- Allow max 3 redirects and re-check each hop.
- Cap the body read at 1 MB.
- Send `User-Agent: BeaconProbe/1.0 (+uptime monitor)`.

The API validates `checkUrl` with the same rules on create/update.

### 8.5 State machine (pure function, fully unit-tested)
- **Region freshness:** a region's latest result counts if it is newer than `2 × intervalMin` minutes.
- **Product failing this evaluation:** failing fresh regions ≥ `quorum`. Default quorum = `ceil(freshRegions / 2)`; with one region, quorum = 1.
- **Counters:** step once per minute. If `runMinute > lastEvalMinute`, step the counters and set `lastEvalMinute`. Otherwise re-evaluate without stepping, so later regions can still change the quorum result for the same minute.
- **Transitions:**
  - Failing → `consecutiveFailures += 1`, `consecutiveSuccesses = 0`. If `consecutiveFailures ≥ openAfter` and no open incident → **open incident**, `status = DOWN`, publish `DOWN` (severity `critical`).
  - Passing → `consecutiveSuccesses += 1`, `consecutiveFailures = 0`. If an incident is open and `consecutiveSuccesses ≥ resolveAfter` → **resolve**, publish `RECOVERED` (severity `critical`, PagerDuty resolve).
  - Passing but `lastLatencyMs > latencyWarnMs` for 3 consecutive evaluations → `status = DEGRADED`, publish `DEGRADED` (severity `warning`, push only, no page). Back under the threshold → `UP` (no alert).
  - Disabled → `PAUSED`; no checks, no alerts. Pausing during an open incident resolves it with cause "paused by user".
- **Acknowledge** (API): `state = ACKNOWLEDGED`, timeline entry, PagerDuty `acknowledge`. It does not stop the resolve logic.
- **Uptime:**
  - per-minute product verdict: up if not failing
  - `uptime = upMin / totalMin` over the window, excluding paused minutes
  - 24h from R5; 7d from RH; 30d from RD (+ today's partial)
- **Error budget (30d):** `budgetMin = (1 − sloTarget/100) × monitoredMinutes30d`; `remaining = budgetMin − downMinutes30d`.
- **p95 (1h):** from `recentLatencies`.

### 8.6 Multi-region (opt-in)
- Terraform variable `probe_regions` (default `["ap-south-1"]`). Supported: `ap-south-1`, `ap-southeast-1`, `us-east-1`.
- Terraform providers cannot be created in a `for_each`. Declare one aliased provider per supported region and gate each probe module with `count = contains(var.probe_regions, "<region>") ? 1 : 0`.
- Remote probes send SQS messages to the home-region queue.

### 8.7 TLS expiry (maintenance Lambda, daily 09:00 IST)
- For each https product, read the certificate's `notAfter`.
- Store it as `certExpiresAt`.
- Alert `TLS_EXPIRING` (severity `warning`) at ≤ 14 days and again at ≤ 7 days.
- Also send a **daily summary push**, e.g. "12 products · 99.98% up yesterday · 0 incidents".

---

## 9. API (Lambda Function URL, Powertools `LambdaFunctionUrlResolver`)

All routes are under `/api`.
- **Auth:** everything except `/api/health` and `/api/auth/login` requires `Authorization: Bearer <JWT>`.
- **Origin check:** every request must carry `X-Beacon-Origin: <secret>`, which CloudFront adds. Requests without it get 403, which blocks direct calls to the Function URL.

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/api/health` | — | `{status:"ok", version, time}` |
| POST | `/api/auth/login` | `{password}` | `{token, expiresAt}` (JWT HS256, 30 days). Lock for 15 min after 5 failures. |
| GET | `/api/summary` | — | counts by status, overall state |
| GET | `/api/products` | `?kind=` | `ProductSummary[]` incl. `uptime30d`, `strip24h` (24 hourly ratios) |
| POST | `/api/products` | ProductInput | `Product` (and republish the snapshot) |
| GET | `/api/products/{id}` | — | `ProductDetail` (product, stats, openIncident) |
| PATCH | `/api/products/{id}` | partial ProductInput | `Product` (republish snapshot) |
| DELETE | `/api/products/{id}` | — | 204 (delete META, republish snapshot; time-series expires via TTL) |
| POST | `/api/products/{id}/pause` · `/resume` | — | `Product` |
| POST | `/api/products/{id}/test` | — | `CheckResult` (runs the check in the API Lambda with the shared check module; stored with `manual=true`, not counted in uptime) |
| GET | `/api/products/{id}/series` | `?range=24h\|7d\|30d` | points `{t, uptime, latAvg, latMax}` |
| GET | `/api/products/{id}/checks` | `?limit=20` | recent raw checks |
| GET | `/api/products/{id}/incidents` | `?limit=20` | incidents |
| POST | `/api/products/{id}/incidents/{sk}/ack` | — | `Incident` |
| GET | `/api/incidents` | `?state=open\|all&limit=50` | incidents feed (GSI1) |
| POST | `/api/push/subscriptions` | PushSubscription JSON | 201 |
| DELETE | `/api/push/subscriptions` | `{endpoint}` | 204 |
| POST | `/api/notifications/test` | — | 202 (sends a `TEST` alert through SNS) |
| POST | `/api/demo/break` · `/api/demo/fix` | — | 200 (sets SSM `/beacon/demo/healthy` to `false`/`true`) |
| GET / PATCH | `/api/settings` | defaults, quorum | Settings |

Errors use the shape `{error: {code, message}}` with correct HTTP codes (400, 401, 403, 404, 409, 422, 429, 500).

---

## 10. Notifications

**SNS topic `beacon-product-alerts`**
- Message attributes: `event` (`DOWN|RECOVERED|DEGRADED|TLS_EXPIRING|DAILY_SUMMARY|TEST`), `severity` (`critical|warning|info`), `productId`.
- Subscribers:
  - **Email** (Jeya's address; confirm the subscription by clicking the link). Filter policy: `severity` in `critical, warning`, plus `TEST`.
  - **notifier Lambda**:
    - **Web Push** to all subscriptions via `pywebpush` with VAPID. Payload: `{title, body, url:"/p/<id>", tag:"<productId>"}`. Delete subscriptions that return 404/410.
    - **PagerDuty Events API v2** for `critical` only: `trigger` on DOWN and `resolve` on RECOVERED, with `dedup_key = <incident ulid>`. Acknowledgements from the app send `acknowledge`.

**Message text:**
- `🔴 DOWN: Nankiv — HTTP 502 (ap-south-1)`
- `🟢 RECOVERED: Nankiv — down for 6m 12s`
- `🟠 SLOW: Meridian — 3.4 s avg (limit 2 s)`
- `🔐 TLS expiring: Sorry No Proxy — 9 days left`

**Service worker:** handles `push` (show the notification) and `notificationclick` (focus or open `url`).

**SNS topic `beacon-ops-alerts`:** CloudWatch alarms → email + PagerDuty "Beacon Platform" service (SNS HTTPS subscription to the PagerDuty CloudWatch integration URL).

---

## 11. Frontend spec (PWA)

- `web/` folder; Vite + React + TS strict; API base `/api` (same origin).
- **Manifest:**
  - name/short_name `Beacon`, `display: standalone`, dark theme colour
  - icons 192 and 512, plus `apple-touch-icon` 180×180
  - `apple-mobile-web-app-capable=yes`, `apple-mobile-web-app-status-bar-style=black-translucent`
- **Service worker** (`vite-plugin-pwa`, injectManifest):
  - precache the app shell
  - network-first for `/api/*` (cache the last good response for an offline view)
  - push handlers
- **Data fetching:** TanStack Query, `refetchInterval: 30_000` on Home and Detail, `refetchOnWindowFocus: true`.
- **iOS polish:**
  - safe-area insets (`env(safe-area-inset-*)`)
  - 44 px minimum touch targets
  - `-apple-system` font stack
  - no hover-only UI
  - skeleton loaders
  - offline banner when `navigator.onLine === false`
- **Theme:** dark by default; light via `prefers-color-scheme`.
- **Status colours:** up `#22c55e`, degraded `#f59e0b`, down `#ef4444`, paused `#9ca3af`, unknown `#64748b`. Always paired with an icon and a text label.
- **Time display:** IST, relative ("23s ago") with the exact time on tap.
- Forms use react-hook-form + zod with the same validation as §3.3.
- Build-time env: `VITE_VAPID_PUBLIC_KEY`, `VITE_APP_VERSION` (git SHA).

---

## 12. Security

- Single admin password: an argon2id hash stored in SSM `/beacon/admin_password_hash`. Never store the plaintext.
- JWT HS256 secret in SSM `/beacon/jwt_secret`. Tokens expire after 30 days.
- Origin-verify secret: Terraform `random_password`, set as a CloudFront custom origin header and checked by the API.
- CloudFront response headers policy: HSTS, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`. CSP: `default-src 'self'`; `connect-src 'self'`.
- IAM: one role per Lambda, least privilege, resources scoped to `beacon-*` ARNs.
- SSRF guard (§8.4). Input validation with pydantic on every route.
- **No secrets in the repo, in Terraform variables files, or in GitHub.** GitHub only holds the deploy role ARN (OIDC).

**SSM parameters**

Terraform creates these with placeholder values and `lifecycle { ignore_changes = [value] }`. Jeya sets the real values with `scripts/put_secrets.sh`.

| Name | Type |
|---|---|
| `/beacon/admin_password_hash` | SecureString |
| `/beacon/jwt_secret` | SecureString |
| `/beacon/vapid_private_key` | SecureString |
| `/beacon/vapid_subject` | String (`mailto:<Jeya's email>`, set by Jeya) |
| `/beacon/pagerduty_routing_key` | SecureString (optional) |
| `/beacon/healthchecks_ping_url` | SecureString (optional) |
| `/beacon/demo/healthy` | String (`true`) |

---

## 13. Infrastructure (Terraform)

```
infra/
  bootstrap/            # applied ONCE locally by Jeya with his own credentials
    main.tf             # S3 state bucket (versioned, encrypted, public access blocked),
                        # GitHub OIDC provider, deploy role (trust: repo JeyaViknan/beacon,
                        # branch main + environment production), $1 AWS Budget with email alerts
  modules/
    probe/              # lambda + scheduler + IAM + log group for ONE region
  main/
    versions.tf         # terraform >= 1.10, aws provider ~> 5.x, random, archive
    backend.tf          # s3 backend, use_lockfile = true, key = "beacon/main.tfstate"
    providers.tf        # default ap-south-1 + aliases: singapore, virginia
    variables.tf        # probe_regions, alert_email, project = "beacon"
    dynamodb.tf  sqs.tf  sns.tf  lambdas.tf  scheduler.tf  ssm.tf
    site.tf             # S3 + CloudFront (OAC, CF Function for SPA rewrite, /api/* → Function URL origin)
    alarms.tf  dashboard.tf  demo_target.tf
    outputs.tf          # cloudfront_url, api_function_url, table_name, queue_url
```

Key details:
- **SPA routing:** use a **CloudFront Function** (viewer request) on the default behaviour that rewrites extensionless paths to `/index.html`. Do **not** use distribution-wide custom error responses, because they would also rewrite `/api` 404s.
- **`/api/*` behaviour:**
  - origin = Function URL host, `https-only`
  - cache policy `CachingDisabled`
  - origin request policy `AllViewerExceptHostHeader`
  - custom header `X-Beacon-Origin`
  - allowed methods: all
- **Lambda packaging:** CI builds zips into `dist/<fn>.zip` with `pip install --platform manylinux2014_aarch64 --only-binary=:all: --target`. Terraform uses `filename` + `source_code_hash`. A shared package `services/beacon_core` is vendored into each zip.
- **Log groups:** created explicitly with `retention_in_days = 7` before the functions.
- **Probe timing:**
  - EventBridge Scheduler `rate(1 minute)`, flexible time window OFF
  - probe timeout 50 s, memory 256 MB
  - processor 30 s / 256 MB, api 10 s / 256 MB, notifier 15 s / 128 MB, maintenance 120 s / 256 MB
- **SQS:** visibility timeout 6 × processor timeout; DLQ after `maxReceiveCount = 5`; retention 4 days.
- **demo-target Lambda:** a Function URL that returns `200 OK` or `503` based on SSM `/beacon/demo/healthy` (cached 10 s). Seed a product "Beacon Demo Target" (kind personal, note "Used for live demos", `openAfter = 1`, `resolveAfter = 1`) via a seed script or the first-run API.

---

## 14. CI/CD (GitHub Actions)

**`.github/workflows/ci.yml`** (PRs and pushes):
- Python: `ruff check`, `ruff format --check`, `pytest` with coverage. Fail if coverage on `services/beacon_core` is below 85%.
- Web: `npm ci`, `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`.
- Terraform: `terraform fmt -check -recursive`, `terraform init -backend=false`, `terraform validate` (main + module).

**`.github/workflows/deploy.yml`** (push to `main`; GitHub environment `production` with Jeya as required reviewer):
1. OIDC → assume the deploy role (`aws-actions/configure-aws-credentials`, `role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}`).
2. Build the Lambda zips.
3. `terraform init` → `terraform plan -out tfplan` → `terraform apply tfplan`.
4. Build the web app (`VITE_APP_VERSION=${{ github.sha }}`) → `aws s3 sync web/dist s3://<bucket> --delete` → CloudFront invalidation for `/index.html`, `/sw.js` and `/manifest.webmanifest`.
5. Smoke test: `GET <cloudfront>/api/health` = 200 and `GET <cloudfront>/` = 200. Fail the job otherwise.
6. Write a job summary with the deployed version and URLs.

**Repo variables:** `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION=ap-south-1`, `TF_STATE_BUCKET`, `VITE_VAPID_PUBLIC_KEY`. No AWS secrets.

---

## 15. Observability of Beacon itself

**CloudWatch alarms (exactly ≤ 10), all → `beacon-ops-alerts`:**

| # | Alarm | Condition |
|---|---|---|
| 1 | probe-errors | probe `Errors` ≥ 1 in 3 of 5 minutes |
| 2 | probe-not-running | probe `Invocations` < 1 over 5 min, **missing data = breaching** |
| 3 | processor-errors | processor `Errors` ≥ 1 in 5 min |
| 4 | results-queue-age | `ApproximateAgeOfOldestMessage` > 180 s |
| 5 | dlq-not-empty | DLQ `ApproximateNumberOfMessagesVisible` ≥ 1 |
| 6 | notifier-errors | notifier `Errors` ≥ 1 in 5 min |
| 7 | api-errors | api `Errors` ≥ 5 in 5 min |
| 8 | ddb-throttles | table `ThrottledRequests` ≥ 1 in 5 min |
| 9 | processor-duration | processor `Duration` p95 > 20 s for 10 min |

**Dashboard `beacon-ops` (1 of 3 free):**
- invocations, errors and duration per function
- queue depth and age, DLQ depth
- DynamoDB consumed vs provisioned capacity, throttles
- count of products by status

**Custom metrics (≤ 10), via Powertools EMF, namespace `Beacon`:** `ChecksRun`, `ChecksFailed`, `IncidentsOpened`, `IncidentsResolved`, `NotificationsSent`, `NotificationsFailed`, `ProbeRunSeconds`.

**Logs:**
- Structured JSON via Powertools Logger.
- Fields on every line: `correlation_id` (SQS message id / request id), `product_id`, `region`.
- No PII, no secrets.

**Dead-man's switch:** healthchecks.io check with a 1-minute period and 5-minute grace, pinged by the processor.

**Runbooks** (`docs/runbooks/<alarm>.md`), each with: what it means · user impact · how to check (exact console path / CLI) · how to fix · when to escalate.

**RCA template** (`docs/incidents/TEMPLATE.md`): summary, impact, timeline (IST), root cause (5 Whys), detection (how and how fast), resolution, what went well / badly, action items with owners.

**Stretch (only if all milestones are done):** Grafana Cloud free with the CloudWatch data source (read-only IAM role); New Relic Lambda extension.

---

## 16. Testing strategy

- **Unit (no AWS):**
  - state machine (table-driven: open/resolve thresholds, quorum, freshness, degraded, pause, idempotent re-delivery)
  - uptime and error-budget maths
  - SSRF guard (every blocked range + redirect hop)
  - check evaluation (status ranges, keyword, timeout) using `respx` to mock `httpx`
  - JWT and login throttle
- **Integration (moto):** DynamoDB repository, processor end-to-end on a sample SQS batch, API routes via a Function URL event fixture, snapshot publishing.
- **Web:** Vitest + Testing Library: home sorting (Down first), status label rendering, time-ago, form validation, the install-tip logic.
- **Smoke (deploy job):** health + index.
- **Manual acceptance:** §18 demo flow on the real iPhone.

---

## 17. Repo layout

```
beacon/
  HANDOVER.md               # this file
  README.md                 # overview, architecture diagram (mermaid), screenshots, how to run, ops
  Makefile                  # test, lint, build, web, plan, apply, deploy-web, secrets, vapid, hash
  pyproject.toml            # ruff, pytest, coverage config
  services/
    beacon_core/            # shared: models (pydantic), state_machine.py, uptime.py, checks.py,
                            # ssrf.py, repo_dynamo.py, snapshot.py, alerts.py, auth.py, timeutil.py
    probe/app.py
    processor/app.py
    notifier/app.py
    api/app.py              # routes
    maintenance/app.py
    demo_target/app.py
    requirements/<fn>.txt
  tests/unit/  tests/integration/  tests/fixtures/
  web/                      # Vite React PWA
  infra/bootstrap/  infra/modules/probe/  infra/main/
  scripts/
    hash_password.py        # prompts for a password, prints the argon2id hash
    gen_vapid.py            # prints VAPID public/private keys
    put_secrets.sh          # read -s prompts → aws ssm put-parameter --type SecureString --overwrite
    build_lambdas.sh        # builds dist/*.zip for arm64
    seed_demo.py            # creates "Beacon Demo Target" via the API
  docs/
    architecture.md  adr/  runbooks/  incidents/  demo-script.md
    learning/               # one short note per milestone for Jeya's interview prep
  .github/workflows/ci.yml  .github/workflows/deploy.yml
```

---

## 18. Milestones (do in order; stop at each ⛔ USER checkpoint)

| # | Milestone | Done when | Est. |
|---|---|---|---|
| M0 | Scaffold: repo layout, pyproject, ruff, pytest, Makefile, web skeleton, README stub | `make lint test` passes; `npm run build` passes | 0.5 h |
| M1 | `beacon_core`: models, state machine, uptime/SLO maths, time utils | ≥ 30 table-driven tests green; coverage ≥ 85% | 2 h |
| M2 | Checks + SSRF guard + probe Lambda handler | Unit tests for every blocked range and redirect; probe builds the correct SQS message | 1.5 h |
| M3 | Dynamo repo, processor, notifier, api, maintenance, demo_target | moto integration tests green; idempotent re-delivery test passes | 3 h |
| M4 | Terraform bootstrap + main; `scripts/*`; `docs/learning/M4.md` | `terraform validate` clean · ⛔ **Jeya** runs bootstrap apply, sets secrets, runs main apply · `/api/health` = 200 via CloudFront | 3 h |
| M5 | PWA: login, home, detail, forms, incidents, settings, push, install tip | Lighthouse PWA installable · ⛔ **Jeya** installs on iPhone, enables push, receives the test notification | 4 h |
| M6 | CI/CD workflows, OIDC deploy, smoke test | A merge to `main` deploys end to end after approval · ⛔ **Jeya** sets repo vars + environment reviewer | 1.5 h |
| M7 | Ops: alarms, dashboard, PagerDuty, healthchecks, runbooks, RCA template | Test alarm reaches email + PagerDuty · ⛔ **Jeya** creates the PagerDuty + healthchecks accounts and pastes keys via `put_secrets.sh` | 2 h |
| M8 | Real data + drills: Jeya adds his real products; run 2 failure drills; write 2 RCAs; README with diagram + screenshots | Demo flow below works start to finish on the phone | 2 h |

**If time runs short, cut in this order:** Grafana/New Relic (stretch) → multi-region → TLS expiry + daily summary → incidents feed page → 30-day bars.
**Never cut:** state machine tests, SSRF guard, Terraform, CI/CD, push alerts, Beacon's own alarms, runbooks.

**Failure drills (M8):**
1. **Product outage:** "Break demo target" → DOWN push within ~1–2 min → Acknowledge → "Fix" → RECOVERED push. Record the times for the RCA.
2. **Beacon outage:** deploy a processor that raises on purpose (feature branch → main) → messages land in the DLQ → `dlq-not-empty` alarm → PagerDuty page → `git revert` → pipeline redeploys → redrive the DLQ → write the RCA (detection time, recovery time, action items).

---

## 19. Demo flow (final acceptance test, on the iPhone)

1. Open Beacon from the home screen. Home shows all products with live status and "All systems operational".
2. Tap a product (e.g. Nankiv): uptime 24h/7d/30d, latency chart, note, live link, GitHub link.
3. Settings → **Break demo target** → within ~1–2 min: push notification + email + PagerDuty page.
4. Open the alert → incident banner → **Acknowledge**.
5. **Fix demo target** → RECOVERED push with the downtime duration.
6. Show on a laptop or phone browser: the GitHub Actions deploy run, the Terraform code, the CloudWatch ops dashboard, a runbook, and an RCA.

---

## 20. Decisions (ADR summary — expand each in `docs/adr/`)

1. **PWA over native iOS:** free, instant updates through CI, Web Push supported on iOS 16.4+; native push needs the paid Apple Developer Program.
2. **Serverless over containers:** ALB, Fargate and RDS are not always-free; Lambda, DynamoDB, SQS, SNS, EventBridge Scheduler and CloudFront are.
3. **DynamoDB single table, provisioned within 25/25:** fits the free tier; access patterns are known up front.
4. **Snapshot item for probes:** a clean control-plane/data-plane split; probes do one read per run.
5. **Quorum + consecutive thresholds:** prevents false alarms from a single blip or a single region.
6. **Single region by default:** zero cross-region cost; multi-region kept as a documented opt-in.
7. **Function URL behind CloudFront with an origin-verify header:** free, same-origin, and blocks direct access.
8. **SSM Parameter Store over Secrets Manager:** free standard tier.
9. **Two alert streams** (products vs Beacon itself) plus an external dead-man's switch.

---

## 21. Open questions / future

- A custom domain (`beacon.<something>.in`) would need Route 53 or an external DNS provider plus an ACM certificate (free cert, paid hosted zone). Not in v1.
- Public read-only status page per product (`/status/<slug>`). v2.
- Capacitor wrapper for an App Store build. Only if ever needed.

---

## 22. Status (updated after each milestone)

| Milestone | State | Notes |
|---|---|---|
| M0 | done | Scaffold, pinned deps, ruff/pytest/coverage, Makefile, Vite+React+TS+Tailwind skeleton. Python 3.12 via uv. |
| M1 | done | Models, pure state machine (quorum, freshness, same-minute re-eval, degraded, pause/resume, ack), uptime/p95/error budget, time utils. 141 tests, 100% core coverage. ADR 0005. |
| M2 | done | SSRF guard with DNS check + IP pinning (Host/SNI), checks (status ranges, keyword ≤1 MB, ≤3 redirects re-checked, error texts), snapshot cache, probe handler (one SQS msg/run). ADR 0010. |
| M3 | done | Repo (one TransactWriteItems per result, optimistic lock), processor (partial batch failures, healthchecks ping), notifier (Web Push + PagerDuty), API (all §9 routes, origin header, JWT, throttle), maintenance (TLS + daily summary), demo target. Redelivery + concurrent-duplicate tests pass. ADR 0011. |
| M4 | not started | |
| M5 | not started | |
| M6 | not started | |
| M7 | not started | |
| M8 | not started | |
