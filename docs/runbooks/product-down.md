# Runbook: a product is DOWN

**You got:** a push "🔴 DOWN: <product> — HTTP 502 (ap-south-1)", plus email and a PagerDuty page.

## 1. Acknowledge (within minutes)
Tap the notification → the incident banner → **Acknowledge**. That records who owns it and acknowledges the PagerDuty incident, so it stops escalating.

## 2. Confirm it's real
- Look at the cause line: `HTTP 5xx`, `Timeout after …`, `DNS: host not found`, `TLS: certificate expired`, `Keyword "…" missing`.
- Tap **Test now** for a fresh check.
- Open the **live site** from the product page on your phone (another network helps).
- With several probe regions, *failing regions* shows whether it's global or regional.

## 3. Fix the product
That product's own runbook or host. Typical causes by error:

| Error | Usually |
|---|---|
| `HTTP 502/503/504` | App crashed, deploy in progress, upstream down |
| `Timeout after …` | Overloaded, or a database hang |
| `DNS: host not found` | Domain expired / DNS misconfigured |
| `TLS: certificate expired` | Auto-renew failed |
| `Keyword "…" missing` | The page renders an error or maintenance page with HTTP 200 |

## 4. Recovery
After `resolveAfter` passing checks (default 2), Beacon sends 🟢 RECOVERED with the downtime and resolves the PagerDuty incident automatically.

## 5. Afterwards
For client work, or anything over ~15 minutes, write an RCA from [`../incidents/TEMPLATE.md`](../incidents/TEMPLATE.md).
