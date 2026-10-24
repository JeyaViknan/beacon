# Set up healthchecks.io and PagerDuty (M7 checkpoint)

About 15 minutes, all free. Do healthchecks.io first (2 minutes), then PagerDuty, then store all three values with **one** run of `make secrets`.

What you'll end up with:

| Value | Comes from | Stored in SSM as | Used by |
|---|---|---|---|
| healthchecks.io **ping URL** | healthchecks.io check | `/beacon/healthchecks_ping_url` | processor, after every clean batch |
| PagerDuty **Integration Key** (Events API v2) | service "Beacon Products" | `/beacon/pagerduty_routing_key` | notifier: DOWN, RECOVERED, ACK |
| PagerDuty **Integration URL** (Amazon CloudWatch) | service "Beacon Platform" | `/beacon/pagerduty_ops_url` | SNS `beacon-ops-alerts` → PagerDuty (no Beacon code in the path) |

---

## 1. healthchecks.io: the dead-man's switch

1. Sign up at **https://healthchecks.io** (free *Hobbyist* plan: 20 checks, no card).
2. In your project, click **Add Check**:
   - **Name:** `beacon-processor`
   - **Schedule:** *Simple*. **Period:** `1 minute`. **Grace time:** `5 minutes`.
   - Save.
3. Copy the **ping URL**, which looks like `https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`. Keep it private: anyone with it can make the check look healthy.
4. **Integrations:** email to your sign-up address is on by default. That's enough. (Optional: after PagerDuty is set up, add the *PagerDuty* integration here too.)

The check shows *new* until the first ping arrives, then *up*. If pings stop for more than 6 minutes, you get an email: **"beacon-processor is DOWN"** → [runbook](../runbooks/dead-mans-switch.md).

## 2. PagerDuty: pages for products and for Beacon itself

1. Sign up at **https://www.pagerduty.com/sign-up/**. Choose the **Free** plan (up to 5 users). If a trial of a paid plan starts instead, you can switch to Free later under *Account Settings → Billing*. Beacon needs nothing beyond Free.
2. **Phone:** install the **PagerDuty** app from the App Store, log in, and allow notifications. In the app: *Profile → Notification Rules*. For *high-urgency* incidents, add **Push notification: immediately**.
3. Create the **product** service:
   1. **Services → Service Directory → + New Service**.
   2. **Name:** `Beacon Products`. **Description:** *Products monitored by Beacon*. Continue.
   3. **Escalation policy:** use the default (it pages you).
   4. **Integrations:** search **Events API V2**, select it, **Create Service**.
   5. On the service's **Integrations** tab, open *Events API V2* and copy the **Integration Key** (32 characters).
4. Create the **platform** service, for Beacon's own alarms:
   1. **+ New Service** → **Name:** `Beacon Platform`.
   2. **Integrations:** search **Amazon CloudWatch**, select it, **Create Service**.
   3. Copy the **Integration URL** (`https://events.pagerduty.com/integration/…/enqueue`).

## 3. Store the three values

```bash
aws login --profile beacon --region ap-south-1
export AWS_PROFILE=beacon
make secrets
```

Press **Enter** to skip the password, JWT and VAPID prompts; they keep their current values. Paste:
- *PagerDuty integration key for PRODUCT alerts* → the **Integration Key** from step 2.3
- *PagerDuty integration URL for BEACON PLATFORM* → the **Integration URL** from step 2.4
- *healthchecks.io ping URL* → the URL from step 1.3

The Lambdas pick the values up within 5 minutes. healthchecks.io should turn **up** shortly after.

## 4. Subscribe PagerDuty to Beacon's alarms (one deploy)

The CloudWatch → PagerDuty link is an SNS subscription that Terraform creates only once the URL is in SSM. Approve the latest run under **GitHub → Actions → Deploy** (or run `make plan && make apply` locally). PagerDuty confirms the subscription automatically.

## 5. Prove it works (M7 "done when")

```bash
make test-alarm
```
Expect within about a minute an **ALARM** email and a PagerDuty incident on **Beacon Platform**, then an **OK** email and the incident resolving on its own.

```bash
make demo-break
```
Within 1–2 minutes: a 🔴 DOWN push (once the app is installed), an email, and a PagerDuty incident on **Beacon Products**. Then:

```bash
make demo-fix
```
🟢 RECOVERED, and the PagerDuty incident resolves.
