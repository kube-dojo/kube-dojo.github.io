---
revision_pending: false
title: "Module 1.3: Grafana"
slug: platform/toolkits/observability-intelligence/observability/module-1.3-grafana
sidebar:
  order: 4
---

> **Comprehensive Toolkit Track Evaluation Path** | Architectural Complexity Level: `[MEDIUM]` | Estimated Completion Timeframe: 40-45 minutes of focused reading and practical exercises

Prerequisites: complete Module 1.1 on Prometheus metrics collection and Module 1.2 on OpenTelemetry tracing before starting this module. You should already be comfortable reading PromQL, recognizing Kubernetes workload labels, and explaining why modern services need metrics, logs, and traces instead of a single monitoring feed. Kubernetes examples assume version 1.35 or later; the runnable commands below use the full `kubectl` form so they are copy-paste safe in a fresh shell.

## Learning Outcomes

- Design a Grafana dashboard hierarchy that moves from fleet overview to service diagnosis without overwhelming incident responders.
- Implement dynamic Grafana variables and PromQL template queries that make one dashboard reusable across services, environments, and time ranges.
- Diagnose production incidents by correlating Prometheus metrics, Loki logs, and Tempo traces through Grafana Explore.
- Configure Grafana alerting and notification routing so alerts represent user-impacting risk instead of raw infrastructure noise.
- Evaluate panel types, thresholds, and provisioning strategies for dashboards that must be reviewed, versioned, and operated like production code.

## Why This Module Matters

Hypothetical scenario: late on a holiday shopping night, the platform director at a large online retailer stood in a war room while abandoned carts climbed faster than the checkout team could count them. The main Grafana screen looked calm: CPU was green, memory was green, request rate looked normal, and a wall of tiny panels suggested that every service was healthy. Revenue still dropped by millions because the dashboard answered the questions that engineers had happened to graph, not the questions the incident demanded.

The damaging part was not that Grafana failed. Grafana had faithfully rendered every query it had been given, but the dashboard estate had grown by copy and paste across several years. Some panels looked at staging, some used old labels, several mixed one-minute rates with long averages, and almost none linked business pain to service symptoms. The team spent the most expensive part of the incident trying to identify the dashboard that actually described checkout, then found a third-party payment gateway timeout that should have been obvious from a well-designed service view.

This module treats Grafana as an operational decision system, not as a chart gallery. A good dashboard lets an on-call engineer move from "customers are failing" to "this dependency is saturating" with a small number of deliberate clicks, while a bad dashboard produces confidence without evidence. The difference comes from hierarchy, variables, panel selection, alert routing, and disciplined links between metrics, logs, and traces.

You will also practice a harder habit: designing for the tired reader. During incidents, people do not have infinite attention, and they should not be asked to decode a dashboard taxonomy while a service is burning. Grafana becomes powerful when its visual language is boring in the best possible way: service overviews are predictable, thresholds have meaning, variables are reusable, and every alert points toward the next diagnostic action.

## Grafana in the LGTM Observability Stack

Grafana sits at the human-facing edge of an observability system. Prometheus, Loki, Tempo, and Mimir store different kinds of telemetry, but Grafana turns those signals into an interface where engineers can compare, question, and explain system behavior. That role sounds simple until you operate a large platform, because the hard problem is not drawing a line chart; the hard problem is preserving enough context that the line chart still means something during pressure.

The LGTM stack gives each telemetry type a clear responsibility. Loki stores logs with label-aware indexing, Tempo stores distributed traces, Grafana presents and explores the data, and Mimir extends Prometheus-style metrics storage for larger and longer-running environments. You do not need all of these tools to use Grafana, but understanding their boundaries helps you avoid the common mistake of trying to force every question into one data source.

```
┌─────────────────────────────────────────────────────────────────┐
│                     GRAFANA ECOSYSTEM                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  GRAFANA (Visualization)                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐│    │
│  │  │Dashboards│  │ Explore  │  │ Alerting │  │  Users   ││    │
│  │  │          │  │          │  │          │  │  & Auth  ││    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘│    │
│  │                                                         │    │
│  │  ┌──────────────────────────────────────────────────┐  │    │
│  │  │              DATA SOURCE PLUGINS                 │  │    │
│  │  │  Prometheus │ Loki │ Tempo │ Elasticsearch │ ...  │  │    │
│  │  └──────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│           ┌──────────────────┼──────────────────┐              │
│           ▼                  ▼                  ▼              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│  │  Prometheus  │   │    Loki      │   │    Tempo     │       │
│  │   (Mimir)    │   │   (logs)     │   │   (traces)   │       │
│  │   metrics    │   │              │   │              │       │
│  └──────────────┘   └──────────────┘   └──────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

Prometheus-style metrics are best when you need trends, rates, ratios, and alertable thresholds. Logs are best when you need the exact application statement, request identifier, validation error, or stack trace behind a symptom. Traces are best when a request crosses many services and the relevant clue is the sequence of spans rather than one isolated metric. Grafana brings these views together, but the engineer still has to design the path between them.

Think of Grafana as the airport control tower for telemetry. The tower does not fly the aircraft, maintain the runway, or sell the tickets, but it gives operators a shared picture of movement, congestion, risk, and direction. If that picture omits the runway that matters or labels aircraft inconsistently, the control tower becomes a beautifully lit source of confusion. The same is true for dashboards that cannot connect customer symptoms to service boundaries.

A useful Grafana deployment starts with data source ownership. Prometheus data sources should be named so engineers know which cluster, tenant, or environment they query. Loki and Tempo should share labels such as `service`, `namespace`, `cluster`, and `trace_id` wherever possible, because correlation depends on shared vocabulary. Without that vocabulary, Explore mode becomes a manual search exercise at the exact moment when teams need speed.

Pause and predict: if a dashboard queries Prometheus with `service="checkout"` but Loki logs use `app="checkout-api"`, what part of the incident workflow becomes slower? The answer is not simply "logs are harder to find." Every link, variable, annotation, and trace pivot now needs custom translation, so each responder must remember local naming history before they can investigate the failure.

The war story from the retailer illustrates a broader rule: Grafana cannot compensate for weak telemetry contracts. If application metrics lack stable labels, dashboards must guess. If traces do not carry identifiers into logs, Explore cannot pivot cleanly. If alert labels do not match routing policy, urgent incidents land in the wrong channel. Good Grafana work therefore begins one layer below the screen, with labels and data sources that make correlation possible.

For Kubernetes environments, this label discipline should start with workloads and services. A deployment may be called `checkout-api`, a namespace may be `payments`, and a team may own the service through a label such as `team=commerce`. The exact scheme can vary, but Grafana becomes much easier to operate when Prometheus scrape labels, Loki log labels, and Tempo resource attributes converge on the same names. The dashboard should feel like a map, not a translation exam.

## Designing Dashboards Around Golden Signals

The Four Golden Signals are a practical dashboard design constraint because they force every service view to answer four questions before it indulges in local detail. Latency asks how long requests take, traffic asks how much load arrives, errors ask what share of work fails, and saturation asks how close the system is to a limit. These signals do not explain every failure, but they make the first diagnostic layer consistent across teams.

```
FOUR GOLDEN SIGNALS
─────────────────────────────────────────────────────────────────

Every dashboard should answer these questions:

1. LATENCY - How long does it take?
   └── Histogram quantiles (p50, p95, p99)

2. TRAFFIC - How much load are we handling?
   └── Requests per second

3. ERRORS - What's failing?
   └── Error rate as percentage

4. SATURATION - How "full" is the system?
   └── CPU, memory, queue depth


DASHBOARD LAYOUT
─────────────────────────────────────────────────────────────────
┌────────────────────────────────────────────────────────────────┐
│  SERVICE: $service    ENVIRONMENT: $env    TIME: $__interval  │
├────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ │
│  │    Latency      │ │    Traffic      │ │    Errors       │ │
│  │    (p99)        │ │    (RPS)        │ │    (%)          │ │
│  │   STAT PANEL    │ │   STAT PANEL    │ │   STAT PANEL    │ │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────┐│
│  │                      REQUEST RATE                         ││
│  │  ════════════════════════════════════════════════         ││
│  │                                                           ││
│  └───────────────────────────────────────────────────────────┘│
│  ┌───────────────────────────────────────────────────────────┐│
│  │                      LATENCY                              ││
│  │  ────────── p99  ────────── p95  ────────── p50           ││
│  │                                                           ││
│  └───────────────────────────────────────────────────────────┘│
│  ┌───────────────────────────────────────────────────────────┐│
│  │                      ERROR RATE                           ││
│  │  ════════════════════════════════════════════════         ││
│  │                                                           ││
│  └───────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────────┘
```

Latency should usually be shown as histogram quantiles rather than averages. The average request can look acceptable while the slowest users experience checkout delays, login timeouts, or failed uploads. A p50 line tells you what a typical user sees, while p95 and p99 show whether the tail is drifting. Tail latency is often where queueing, retries, database locks, and overloaded dependencies first become visible.

Traffic belongs near latency because load changes the interpretation of every other signal. A spike in p99 latency during a tenfold traffic increase may point toward capacity, while the same spike during normal traffic points toward a dependency, code change, or data issue. Grafana panels should make this comparison easy by aligning time ranges, sharing variables, and avoiding hidden transformations that make one panel look smoother than another.

Errors should be displayed as a ratio whenever possible. A raw count of five hundred errors sounds terrible until you learn that the service handled fifty million requests, while fifty errors can be urgent if the service only handled a few hundred checkout attempts. The ratio also gives alerting policies a more stable foundation because it describes user impact instead of merely describing volume.

Saturation is the signal that explains whether the system is running out of something. CPU, memory, disk, file descriptors, connection pools, queue depth, and concurrency limits all belong here, but not every service needs every saturation panel on its first screen. Start with the resource most likely to constrain the service, then link to deeper component dashboards for the rest. A dashboard that shows every resource equally often hides the one resource that matters.

Before running this, what output do you expect if a service receives normal traffic, has flat error rate, and shows sharply rising p99 latency? A strong hypothesis is that the service is waiting on an internal or external dependency, because the error path has not yet surfaced while request duration has already changed. Grafana should help you test that hypothesis by placing dependency latency and trace links close to the service latency panel.

Hierarchy matters because not every responder needs the same detail at the same moment. A Level 1 overview should show whether the platform is broadly healthy, which services are contributing most to user-visible pain, and where to drill down. A Level 2 service dashboard should focus on one service boundary and its dependencies. A Level 3 component dashboard should expose pod, container, runtime, and application internals for detailed diagnosis.

```
DASHBOARD ORGANIZATION
─────────────────────────────────────────────────────────────────

LEVEL 1: Overview Dashboard
├── All services at a glance
├── Traffic heatmap
├── Error hotspots
└── Click to drill down

LEVEL 2: Service Dashboard
├── Golden signals for one service
├── Dependencies (upstream/downstream)
├── Resource utilization
└── Click to drill down

LEVEL 3: Component Dashboard
├── Individual pods/instances
├── Detailed metrics
├── Debug information
└── Linked to logs/traces
```

A practical example is an authentication service that depends on a database, a cache, and an identity provider. The overview dashboard should show that authentication is failing, not that one pod has an interesting CPU curve. The service dashboard should reveal whether latency, errors, traffic, or saturation changed first. The component dashboard should then help inspect the individual pods, connection pools, and runtime metrics after the service-level story is clear.

The most useful dashboards also encode meaning in layout. Put the most urgent customer-facing indicators near the top, keep time series aligned vertically when they should be compared, and reserve dense tables for investigation rather than first glance. Color should support decisions, not decoration. Green, yellow, and red thresholds must map to defined risk levels, otherwise responders learn to ignore colors that do not match operational reality.

Many organizations drift into dashboard sprawl because every team starts from a copy of the last dashboard that roughly worked. After months of changes, the copies disagree on labels, thresholds, units, and panel titles. A better pattern is to maintain a small set of service templates and use variables for the parts that legitimately differ. The next section shows how those variables turn a one-off dashboard into a reusable diagnostic instrument.

## Implementing Dynamic Variables and Reusable Queries

Dynamic variables are one of Grafana's strongest defenses against dashboard sprawl. A query variable can ask Prometheus for available services, a custom variable can offer known percentiles, an interval variable can adapt query resolution to the selected time range, and a data source variable can switch between clusters or tenants. The point is not cleverness; the point is giving one well-reviewed dashboard enough flexibility to describe many services safely.

```
GRAFANA VARIABLES
─────────────────────────────────────────────────────────────────

QUERY VARIABLE (dynamic from data source)
  Name: service
  Query: label_values(http_requests_total, service)
  Result: Dropdown with all services

CUSTOM VARIABLE (static list)
  Name: percentile
  Values: 50,90,95,99
  Result: Dropdown with percentile options

INTERVAL VARIABLE (time-based)
  Name: interval
  Values: 1m,5m,15m,1h
  Auto: Based on time range

DATASOURCE VARIABLE
  Name: datasource
  Type: prometheus
  Result: Switch between Prometheus instances

TEXT VARIABLE (user input)
  Name: filter
  Type: text
  Result: Free-text filter input
```

The simplest useful variable is usually `service`. It lets a responder choose a service from live label values instead of editing queries or navigating many nearly identical dashboards. That only works if the underlying metrics expose a reliable label, so the dashboard design and instrumentation design are connected. If half your metrics use `service` and half use `job`, the variable becomes a source of partial truth.

Interval variables solve a different problem. A five-second query interval may be appropriate during a ten-minute incident window, but it becomes expensive and noisy across a month of historical data. Grafana's built-in interval behavior can scale the query window as the time picker changes, which protects both the browser and the data source. The tradeoff is that wider intervals smooth short spikes, so critical alert rules should still run independently of dashboard resolution.

```promql
# In dynamic PromQL queries, use $variable or ${variable} interpolation syntax.
rate(http_requests_total{service="$service"}[$interval])

# Multi-value variable selections pair with regular expression matching.
rate(http_requests_total{service=~"$service"}[$interval])

# Percentile calculations can be selected through a custom template variable.
histogram_quantile(0.$percentile,
  sum by (le)(rate(http_request_duration_bucket{service="$service"}[$interval]))
)
```

The distinction between equality and regular expression matching is operationally important. If a variable allows multiple values or an `All` option, a selector such as `service="$service"` may silently stop matching what you expect. The regex form `service=~"$service"` is usually needed for multi-select behavior. That choice should be deliberate, because overly broad regex matching can also produce expensive queries when the label space is large.

Dashboard variables should be reviewed with the same seriousness as application configuration. A variable that refreshes on every time range change can create unnecessary load against a busy Prometheus server, while a variable that never refreshes can hide newly deployed services. The right refresh mode depends on how often labels change and how costly the query is. Grafana gives you the mechanism, but operational judgment decides the refresh behavior.

```json
{
  "templating": {
    "list": [
      {
        "name": "service",
        "type": "query",
        "datasource": "Prometheus",
        "query": "label_values(http_requests_total, service)",
        "multi": true,
        "includeAll": true,
        "allValue": ".*",
        "refresh": 2
      },
      {
        "name": "interval",
        "type": "interval",
        "auto": true,
        "auto_min": "10s",
        "options": [
          {"value": "1m", "text": "1 minute resolution"},
          {"value": "5m", "text": "5 minute resolution"},
          {"value": "15m", "text": "15 minute resolution"}
        ]
      }
    ]
  }
}
```

A worked example helps make this concrete. Suppose the payments team owns five services in production and two in staging, all emitting `http_requests_total` with `service`, `namespace`, and `status` labels. One dashboard can expose `environment`, `namespace`, `service`, and `interval` variables, then reuse the same panels across all seven targets. The dashboard owner updates threshold policy once, and every service view receives the corrected behavior.

Which approach would you choose here and why: one dashboard per service, or one dashboard with service and namespace variables? The reusable dashboard is usually better when services share instrumentation and ownership expectations. Dedicated dashboards still make sense for unusual services with distinctive internals, but the shared template should remain the default because it reduces review cost and prevents metric drift from hiding inside dozens of copies.

Variables can also make dashboards dangerous when they remove too much context. An `All` option across every service in every namespace may produce slow, high-cardinality queries and misleading aggregate averages. Text variables can be useful for expert filtering, but they can also let users create ad-hoc selectors that nobody else can reproduce. A mature platform team documents which variables are intended for incident response and which are for exploratory analysis.

The healthiest pattern is to pair variables with clear titles and repeated label conventions. A panel title such as "p99 latency for `$service` in `$namespace`" is more useful than "Latency" because screenshots and incident notes retain context. Grafana dashboards often become artifacts in post-incident reviews, so the selected variable values need to be visible in the story long after the browser tab closes.

## Choosing Panels, Thresholds, and Visual Language

Panel choice changes how quickly people interpret telemetry. Time series panels are ideal for trends, stat panels are ideal for one decisive number, gauges are useful when a value moves toward a limit, and tables are best when responders need ranked detail. A dashboard full of visually impressive panels can still be slow to read if every panel asks the viewer to interpret a different visual grammar.

```
TIME SERIES CONFIGURATION
─────────────────────────────────────────────────────────────────

LEGEND
├── Format: {{service}} - {{method}}
├── Placement: Bottom or Right
└── Hide if too many series (use tooltip)

AXES
├── Left Y: Main metric (e.g., RPS)
├── Right Y: Secondary (e.g., error %)
└── Label units explicitly

THRESHOLDS
├── Warning: Yellow line
├── Critical: Red line
└── Fill below threshold for visibility

SERIES OVERRIDES
├── Error series: Red
├── Success series: Green
└── Specific series styling
```

Time series panels should show changes over time, not merely prove that data exists. Keep units explicit, avoid mixing unrelated axes unless the relationship is clear, and prefer a small number of meaningful series over a dense bundle of lines. If a panel contains many services, the legend and tooltip become part of the interface design. Hide or group noisy series when they prevent the responder from seeing the signal.

Stat panels work well for error percentage, current p99 latency, burn rate, or request volume because they answer "what is the value right now?" without forcing the reader to inspect a graph. Their weakness is context. A stat panel can tell you that error rate is three percent, but it cannot tell you whether that value appeared suddenly or rose over two hours. Pair stat panels with time series panels when trend matters.

```json
{
  "type": "stat",
  "title": "Critically Important Transactional Error Rate",
  "targets": [
    {
      "expr": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m])) * 100",
      "legendFormat": ""
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "percent",
      "thresholds": {
        "mode": "absolute",
        "steps": [
          {"color": "green", "value": null},
          {"color": "yellow", "value": 1},
          {"color": "red", "value": 5}
        ]
      },
      "mappings": [],
      "color": {"mode": "thresholds"}
    }
  },
  "options": {
    "colorMode": "background",
    "graphMode": "none",
    "textMode": "value"
  }
}
```

Thresholds deserve careful governance. A red threshold should mean that a responder needs to consider action, not that a number looks subjectively high. If the service has an SLO, derive thresholds from the error budget, latency objective, or saturation limit that threatens the objective. If there is no SLO yet, document the threshold as provisional and revisit it after the team has enough production history.

Hypothetical scenario: imagine a team that celebrated having hundreds of alert rules and dashboards because coverage looked impressive in a quarterly reliability review. During a database pool failure, the on-call engineer received separate pages for CPU, memory, disk input, latency, and queue depth across the same service. The first alerts were technically true but operationally noisy, so by the time the latency alert arrived, the engineer had already learned to dismiss the incident as routine background noise.

```
Dashboard / Alert Audit (illustrative, round numbers)
─────────────────────────────────────────────────────────────────
Total dashboards:            ~300
Dashboards viewed monthly:   a small minority of them
Total alert rules:           ~800
Alerts per week:             ~150
Actionable (true positives): a small fraction
MTTA (Mean Time to Ack):     well above the 5-minute target
Incidents missed to fatigue: several across two quarters
─────────────────────────────────────────────────────────────────
Pattern: most pages were noise, so responders stopped trusting them
```

The remediation was not a prettier dashboard. The team deleted redundant alerts, tied paging to user-impacting symptoms, moved infrastructure warnings into ticket workflows, and rebuilt the dashboard hierarchy around SLOs. Grafana became more useful when there were fewer panels because each panel earned its place. This is a recurring lesson in observability: a smaller number of trusted signals usually beats a larger number of unowned signals.

Panel titles should read like claims, not labels. "Checkout p99 latency by dependency" is better than "Latency" because it tells the reader which service, which statistic, and which grouping to inspect. "HTTP 5xx percentage" is better than "Errors" because it clarifies the numerator and denominator. When titles are specific, incident notes become easier to write, and postmortem readers can reconstruct the diagnostic path from screenshots.

Annotations are another part of visual language. Deployment markers, feature flag changes, incident starts, and maintenance windows can explain why a graph changed when it did. Without annotations, teams often waste time rediscovering recent releases or asking chat channels whether anything changed. A dashboard that overlays events on telemetry reduces social lookup work and makes the timeline visible to everyone in the room.

The panel selection rule is simple: choose the visualization that answers the operational question with the least interpretation. Use time series for trends, stat panels for urgent single values, tables for ranked comparisons, heatmaps for distribution density, and logs or traces for evidence. Avoid building a dashboard that merely demonstrates Grafana's catalog of panels. During a production incident, variety is less valuable than clarity.

## Configuring Alerting and Notification Routing

Grafana alerting turns queries into decisions, so it must be designed more conservatively than dashboards. A dashboard can tolerate exploratory panels, but an alert interrupts people and changes their behavior. Every alert should have a clear owner, a clear reason for waking someone, and enough labels and annotations to route the notification to the right place. Without those properties, alerting becomes an expensive attention leak.

```yaml
# Unified alerting configuration for mathematical rule evaluation.
apiVersion: 1
groups:
  - name: production-critical-service-alerts
    folder: High-Priority-Production-Environment
    interval: 1m
    rules:
      - uid: severely-high-error-rate-detected
        title: Dangerously High Service Error Rate
        condition: C
        data:
          # Query A: isolate failed inbound requests.
          - refId: A
            datasourceUid: prometheus
            model:
              expr: sum(rate(http_requests_total{status=~"5.."}[5m]))

          # Query B: aggregate all inbound requests.
          - refId: B
            datasourceUid: prometheus
            model:
              expr: sum(rate(http_requests_total[5m]))

          # Expression C: derive continuous failure percentage.
          - refId: C
            datasourceUid: __expr__
            model:
              type: math
              expression: $A / $B * 100
              conditions:
                - evaluator:
                    type: gt
                    params: [5]

        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "The calculated service error rate is {{ $values.C }} percent"
```

Notice that the example alert calculates a ratio rather than paging on a raw count. The ratio is easier to reason about because it accounts for traffic volume and maps more naturally to user impact. The `for: 5m` clause also matters because it prevents a one-sample blip from waking the team. Alerting always balances speed against noise, and that balance should be explicit in the rule definition.

Labels drive routing and grouping, so they are part of the alert contract. A `severity` label helps decide whether a notification pages a human or lands in a work queue. A `team` or `service` label helps route the event to the owner. Environment labels prevent staging alerts from waking production responders. When labels are missing, the notification policy has to guess, and guesses become painful during incidents.

```yaml
# Organizational notification contact points and routing definitions.
apiVersion: 1
contactPoints:
  - name: dedicated-engineering-slack-alerts
    receivers:
      - uid: primary-slack-integration-channel
        type: slack
        settings:
          url: https://hooks.slack.com/services/YOUR/WEBHOOK/HERE
          recipient: "#critical-production-alerts"
          title: "Critical Infrastructure Notification: {{ .CommonLabels.alertname }}"
          text: "Detailed Informational Summary Statement: {{ .CommonAnnotations.summary }}"

  - name: primary-pagerduty-escalation-path
    receivers:
      - uid: primary-pagerduty-integration-webhook
        type: pagerduty
        settings:
          integrationKey: "<TOKEN>"
          severity: "Categorized Alert Escalation Severity Level: {{ .CommonLabels.severity }}"
```

Notification routing should reflect the difference between urgency and importance. A failed customer checkout path at peak traffic is urgent and important, so it should page. A pod restart in a redundant background worker may be important but not urgent, so it can create a ticket or Slack message. A certificate expiring tomorrow may deserve a high-priority ticket rather than a midnight page. Grafana can route these differently if labels and policies are designed intentionally.

Alert annotations should give responders the next action, not just repeat the graph value. A useful annotation includes the service, the affected SLO or symptom, the dashboard link, the likely first diagnostic query, and the runbook. If an alert says only "high latency," the responder must discover the rest under pressure. If it says "checkout p99 exceeds objective, inspect dependency latency and recent deployment annotations," the alert becomes a starting point.

Silences and maintenance windows are operational tools, not excuses to hide broken alerts. Planned database maintenance, load tests, and regional failovers can temporarily suppress known noisy alerts, but silences should be scoped tightly and expire automatically. Permanent silences usually indicate that the alert is not trusted. If a team keeps silencing an alert, fix the rule, adjust routing, or remove the alert rather than letting the dashboard culture normalize ignored warnings.

The strongest alerting systems are reviewed after incidents. Ask which alerts fired first, which alerts mattered, which alerts were ignored, and whether the dashboard links accelerated diagnosis. Grafana's rule history and notification logs can support that review, but the cultural habit matters more than the feature. Alerting quality improves when teams treat every page as a design decision that can be tested and refined.

## Correlating Metrics, Logs, and Traces in Explore

Dashboards are optimized for known questions, while Explore is optimized for investigation. When an incident does not match an existing panel, Explore lets you build and compare queries across data sources without editing a production dashboard. This is where Grafana becomes a forensic workbench: you can start with a metric spike, add a log query for the same time window, and pivot into a trace that shows the request path.

```
EXPLORE MODE
─────────────────────────────────────────────────────────────────

┌────────────────────────────────────────────────────────────────┐
│  [Prometheus ▼]    [Loki ▼]    [Tempo ▼]                       │
├────────────────────────────────────────────────────────────────┤
│  QUERY: rate(http_requests_total{service="api"}[5m])           │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  [Run Query]  [Add Query]  [Split]                       │ │
│  └──────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  RESULT:                                                       │
│  ════════════════════════════════════════════════              │
│                                          ^                     │
│                                         /                      │
│  ──────────────────────────────────────/──────────             │
│                                                                │
│  [Split] Split panes for comparison                            │
│  [Logs]  Link to Loki for this time range                      │
│  [Traces] Link to Tempo for this trace ID                      │
│                                                                │
└────────────────────────────────────────────────────────────────┘

Use Cases:
• Incident investigation
• Metric exploration
• Query building before dashboard
• Correlating metrics, logs, traces
```

A common investigation begins with Prometheus. You notice that `http_requests_total{status=~"5.."}` rose for the API service, then open Explore at the spike's time range. From there, a Loki query such as `{service="api"} |= "error" | json` can reveal request identifiers, exception messages, or upstream status codes. If the application logs a `trace_id`, Tempo can render the distributed trace that connects the symptom to the slow or failing dependency.

```
SIGNAL CORRELATION
─────────────────────────────────────────────────────────────────

1. Start with metric anomaly
   rate(http_requests_total{status="500"}[5m]) > 0

2. Click "Explore" on spike timestamp

3. Split view → Add Loki
   {service="api"} |= "error" | json

4. Find error with trace_id

5. Split view → Add Tempo
   Paste trace_id → See full trace

6. Identify root cause in upstream service
```

This workflow depends on trace and log context being carried consistently through the application. If the request handler logs a trace identifier, and OpenTelemetry instrumentation attaches service names, operation names, and status attributes, Explore can bridge the signals with little friction. If those fields are missing, Grafana still displays each data type, but the responder becomes the integration layer. That is slower and more error-prone.

Grafana Explore is also a safe place to develop queries before turning them into dashboard panels or alerts. A PromQL expression that looks good in one time range may behave poorly across a longer history, or it may explode into too many series when a variable uses `All`. Testing in Explore helps you observe cardinality, latency, and label shape before a query becomes part of the shared incident interface.

A practical diagnostic habit is to write down the first three questions before opening more panels. For example: did the user-facing error rate rise, did dependency latency change first, and did the change align with a deployment annotation? Explore can answer those questions quickly if you keep the investigation anchored. Without an explicit hypothesis, responders often click through data sources until they find something interesting but not necessarily relevant.

Explore should feed dashboard improvement. If several incidents require the same ad-hoc query, that query probably belongs in a service dashboard or runbook. If responders repeatedly pivot from latency to one Loki filter and one Tempo trace view, make that path a dashboard link. Grafana is most effective when incident learning flows back into the stable interface instead of remaining in chat transcripts and personal browser history.

## Provisioning Dashboards as Code

Manual dashboard editing is useful for exploration, but production dashboards need review, versioning, and repeatability. Treating Grafana configuration as code protects teams from accidental deletion, undocumented UI edits, and environment drift. It also lets dashboard changes travel through the same review process as application changes, which is important because a broken dashboard can slow incident response just as surely as a broken script.

```yaml
# Declarative dashboard provisioning structure.
apiVersion: 1
providers:
  - name: 'primary-default-declarative-provider'
    orgId: 1
    folder: 'Production-Environment-Dashboards'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards/declarative-storage-location
```

Provisioning works best when ownership is clear. A platform team may own shared overview templates, while service teams own their detailed service dashboards. Both groups should follow naming conventions, data source conventions, and review expectations. The goal is not to centralize every panel under one team; the goal is to make dashboard changes auditable and consistent enough that responders can trust them.

Large dashboard JSON files can be difficult to maintain by hand, which is why teams often use Jsonnet and Grafonnet to generate dashboard definitions. Programmatic dashboards allow reusable rows, panels, variables, and threshold policies. The tradeoff is that contributors now need to understand the generation tool as well as Grafana. Use generation when it removes real duplication, not merely because generated dashboards feel more sophisticated.

```jsonnet
// Declarative dashboard definition using Jsonnet and Grafonnet.
local grafana = import 'grafonnet/grafana.libsonnet';
local dashboard = grafana.dashboard;
local row = grafana.row;
local prometheus = grafana.prometheus;
local graphPanel = grafana.graphPanel;

dashboard.new(
  'Comprehensive Production Service Architectural Dashboard',
  tags=['production-environment', 'mission-critical-core-service'],
  time_from='now-1h',
)
.addTemplate(
  grafana.template.datasource(
    'datasource',
    'prometheus',
    'Primary Cluster Prometheus Instance',
  )
)
.addTemplate(
  grafana.template.query(
    'service',
    'label_values(http_requests_total, service)',
    datasource='$datasource',
  )
)
.addRow(
  row.new(
    title='Critical Foundational Service Golden Signals',
  )
  .addPanel(
    graphPanel.new(
      'Aggregated Overall System Request Rate Measurement',
      datasource='$datasource',
    )
    .addTarget(
      prometheus.target(
        'sum(rate(http_requests_total{service="$service"}[5m]))',
        legendFormat='Total Overall Requests Per Second',
      )
    )
  )
  .addPanel(
    graphPanel.new(
      'Calculated Mathematical Percentage System Error Rate Measurement',
      datasource='$datasource',
    )
    .addTarget(
      prometheus.target(
        'sum(rate(http_requests_total{service="$service",status=~"5.."}[5m])) / sum(rate(http_requests_total{service="$service"}[5m]))',
        legendFormat='Calculated Severe Error Percentage',
      )
    )
  )
)
```

Provisioned dashboards should be tested in a real or representative Grafana instance before they become the emergency interface. A JSON syntax check is not enough, because a valid dashboard can still query the wrong data source, use a missing label, or render a panel with unreadable units. Reviewers should inspect both the code and the rendered behavior, especially for dashboards that support incident response.

Kubernetes installation examples often use the official Grafana Helm chart, but the production values should be treated carefully. Persistence, authentication, data source provisioning, secret handling, and network policy belong in environment-specific configuration. The quick commands in the lab are intentionally minimal so you can focus on dashboard behavior. A real platform deployment should wire Grafana into your identity provider, secret manager, and backup strategy.

The `k` alias matters in examples because operators use it constantly during incidents. Set `alias k=kubectl` in your shell, then use the short command form consistently once the alias is introduced. The alias does not make Kubernetes safer or more observable, but consistent command examples reduce friction when learners move from reading to testing. In production runbooks, define the alias near the top so nobody wonders whether `k` is a custom tool.

Provisioning also gives teams a way to separate stable dashboard contracts from environment details. The dashboard definition can describe rows, variables, panels, and thresholds, while deployment-specific values can bind data source names, folders, secrets, and organization identifiers. That separation is useful in multi-cluster platforms because the same reviewed dashboard can be promoted from staging to production without rewriting the diagnostic logic. When teams skip that separation, dashboards often become locked to one cluster and quietly fail when copied elsewhere.

A mature review should include a question that is easy to forget: what should happen when a panel has no data? Empty panels are not always harmless. They can mean the service is down, the metric name changed, the label selector is wrong, or the dashboard is looking at the wrong data source. Add descriptions, title context, or companion panels that make "no data" interpretable, especially for dashboards that on-call engineers use during the first minutes of a severe incident.

Finally, make dashboard deletion as intentional as dashboard creation. Grafana estates accumulate abandoned pages because removing a dashboard feels riskier than leaving it in place. Stale dashboards are not neutral; they waste search time, preserve obsolete assumptions, and can send responders toward retired services. A quarterly dashboard review that archives unused pages, checks data source references, and confirms ownership is one of the cheapest reliability improvements a platform team can make.

## Patterns & Anti-Patterns

Grafana patterns are really operational habits encoded into dashboards. The patterns below work because they reduce choices during incidents, preserve context across telemetry types, and make dashboard ownership visible. The anti-patterns fail because they optimize for short-term convenience while creating long-term ambiguity. Use these as review criteria when you inherit an existing Grafana estate.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---|---|---|---|
| Golden-signal service template | Most HTTP, gRPC, or event-processing services with standard metrics | Every responder sees latency, traffic, errors, and saturation in the same order | Keep labels and units consistent across teams so the template remains reusable |
| Dashboard hierarchy | Platforms with many services, teams, or clusters | Overview dashboards direct attention before service dashboards expose detail | Review drill-down links during incidents and after major topology changes |
| Variables with constrained scope | Services that share instrumentation and ownership rules | One reviewed dashboard covers many targets without copy-and-paste drift | Avoid broad `All` selectors against high-cardinality labels unless query cost is known |
| Provisioning as code | Shared dashboards, alert rules, and data source definitions | Changes become reviewable, reproducible, and recoverable | Pair code review with rendered-dashboard checks in a staging Grafana instance |

| Anti-Pattern | What Goes Wrong | Why Teams Fall Into It | Better Alternative |
|---|---|---|---|
| One dashboard per tiny variation | Panels drift until nobody knows which dashboard is authoritative | Copying an existing dashboard is faster than designing variables | Build a parameterized template and reserve bespoke dashboards for truly unusual services |
| Alerting on raw infrastructure symptoms | On-call engineers receive pages that do not map to user impact | CPU and memory are easy to measure and feel concrete | Page on SLO risk or customer symptoms, then show infrastructure panels for diagnosis |
| Hidden query transformations | Graphs look smooth while short incidents disappear | Teams want dashboards that look calm in reviews | Show the interval and aggregation policy, and keep alert evaluation independent |
| Missing links between metrics, logs, and traces | Responders manually translate labels and time ranges during incidents | Each telemetry pipeline was built by a different team | Standardize labels and add dashboard links into Explore, Loki, and Tempo views |

The most important pattern is reviewability. If nobody owns a dashboard, nobody will notice when labels drift, thresholds age, or panels stop answering the original question. A dashboard can be visually attractive and still be operationally abandoned. Treat dashboards like shared code: assign owners, review changes, delete stale panels, and keep the rendered result aligned with the service contract.

## Decision Framework

Start with the incident question, then choose the Grafana technique that answers it with the least cognitive overhead. If the question is "which service is hurting users?", use an overview dashboard with service-level error and latency panels. If the question is "why is this service slow?", use the service dashboard and dependency panels. If the question is "what happened inside one request?", pivot through Explore into logs and traces.

| Decision | Prefer This | Use Something Else When | Tradeoff |
|---|---|---|---|
| Dashboard shape | Hierarchical overview, service, component layers | The environment has only one small service | Hierarchy costs setup time but saves incident attention |
| Service reuse | Variables for service, namespace, data source, and interval | The service has unique domain metrics that dominate diagnosis | Variables reduce drift but can hide context if titles are vague |
| Alert trigger | SLO burn rate, error percentage, or latency objective | No SLO exists and an interim symptom must be monitored | User-impact alerts are trusted, but they require better service definitions |
| Query development | Explore first, then dashboard or alert | The query is already part of a reviewed template | Explore encourages testing, but useful repeated queries should not stay private |
| Dashboard management | Provisioned files or generated dashboards | A prototype is being drafted with a small group | Code review protects production dashboards, but initial exploration is faster in the UI |

Use this flow during design reviews: define the user-facing symptom, identify the service boundary, choose the golden signal that exposes the symptom, select the panel that communicates it fastest, then add links to the next diagnostic layer. Only after that should you add supporting panels. This order keeps dashboards from becoming telemetry museums where every metric is present but no operational argument is clear.

When choosing between a dashboard panel and an alert, ask whether a human must know immediately. Many useful panels should never page anyone. Cache hit rate, goroutine count, pod restart history, and queue depth may be essential for diagnosis but inappropriate as direct pages. Grafana is strongest when dashboards contain rich context and alerts remain selective enough that responders believe them.

For provisioning decisions, ask whether the dashboard is shared, relied on during incidents, or needed in multiple environments. If any answer is yes, put it under version control. UI-only dashboards are acceptable for personal exploration, temporary investigations, and early drafts. The moment a dashboard becomes part of a runbook or alert notification, it deserves the same review and backup discipline as other operational assets.

## Did You Know?

- Grafana was first released in 2014 by Torkel Odegaard, and its early identity was closely tied to Graphite-style time-series visualization before it expanded into a broader observability platform.
- The LGTM acronym commonly refers to Loki, Grafana, Tempo, and Mimir, giving teams an open-source path for logs, dashboards, traces, and horizontally scalable metrics.
- Histogram quantiles such as p95 and p99 are usually more useful than averages for user experience because a small tail of slow requests can represent the users who abandon a transaction.
- A dashboard variable with an unrestricted `All` option can multiply query cost dramatically when it expands across many services, namespaces, or high-cardinality labels.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Copying one dashboard per service | Teams need quick visibility and duplicate the nearest useful page | Implement dynamic Grafana variables for service, namespace, interval, and data source, then review the shared template |
| Paging on CPU without user impact | Infrastructure metrics are easy to collect and feel objective | Configure Grafana alerting around error rate, latency, burn rate, or saturation that threatens an SLO |
| Hiding selected variables in panel titles | Authors assume screenshots preserve dashboard state | Include `$service`, `$namespace`, or `$datasource` in titles where context affects interpretation |
| Mixing short and long rate windows casually | Different panels were created by different people at different times | Standardize query windows, show interval assumptions, and document why exceptions exist |
| Letting Explore findings stay private | Incident responders build useful ad-hoc queries under pressure | Promote repeated Explore queries into dashboards, links, or runbooks after the incident review |
| Using realistic webhook or token examples | Authors paste from an internal setup while documenting alert routing | Use placeholders such as `https://hooks.slack.com/services/YOUR/WEBHOOK/HERE` and `<TOKEN>` in examples |
| Treating provisioning as optional for shared dashboards | Manual edits feel faster than code review | Provision production dashboards and alert rules from reviewed files, then test the rendered result |

## Quiz

<details><summary>Your team sees checkout p99 latency rise while traffic and error percentage remain normal. Which Grafana view should you inspect next, and why?</summary>

Start with the service dashboard's dependency latency panels, then pivot into Explore if a dependency looks suspicious. Rising p99 with normal error rate often means requests are still succeeding but waiting longer on a downstream system, queue, or lock. The dashboard should help compare service latency with dependency latency in the same time range. If a dependency spike aligns, use Loki and Tempo to inspect request evidence before changing capacity or rolling back code.

</details>

<details><summary>A dashboard variable uses `service="$service"` and the owner enables multi-select with an `All` option. What failure mode should you expect?</summary>

The query may stop matching correctly because a multi-value variable often expands into a regular expression rather than one exact label value. In PromQL, that usually requires `service=~"$service"` instead of equality. The safer fix is to review the variable's expansion behavior, constrain the allowed values, and test the query in Explore across single, multiple, and all selections. This protects both correctness and query cost.

</details>

<details><summary>An alert fires for high CPU on an authentication service, but customers are not failing and latency is flat. How should the alerting policy change?</summary>

The alert should probably stop paging directly and become supporting diagnostic context unless CPU saturation is known to threaten the service objective. Paging should be reserved for user-impacting symptoms such as high error percentage, latency objective violations, or burn-rate risk. CPU can remain visible on the service dashboard and may create a ticket if it persists. The goal is to preserve trust in pages while keeping resource signals available for diagnosis.

</details>

<details><summary>During an incident, a responder finds the relevant error log but cannot pivot to a trace. What telemetry contract is likely missing?</summary>

The application probably failed to carry or log a trace identifier that Tempo can use for lookup. Grafana can show metrics, logs, and traces, but correlation depends on shared labels and identifiers across the telemetry pipelines. The fix is to ensure OpenTelemetry context propagation is enabled and that logs include fields such as `trace_id` and `service`. Once that contract exists, Explore can move from a Loki record to a Tempo trace much faster.

</details>

<details><summary>A team wants to manage shared dashboards only through the Grafana UI because it is faster. How would you evaluate that choice?</summary>

UI editing is reasonable for prototypes, but it is risky for dashboards used in alerts, runbooks, or production incidents. Shared dashboards should be provisioned from reviewed files so changes are auditable, reproducible, and recoverable. The team can still prototype in the UI, export the result, and move the stable version into source control. That balances fast exploration with production discipline.

</details>

<details><summary>A service dashboard has twenty panels, but responders still ask which metric matters first. What design problem does that reveal?</summary>

The dashboard likely lacks hierarchy and operational prioritization. The first screen should emphasize golden signals and user-facing risk before diving into component detail. Supporting panels are useful, but they should be lower on the page or linked from the service view. A responder should be able to identify the service symptom before reading specialized runtime metrics.

</details>

<details><summary>Your Grafana alert routes every critical notification to the same Slack channel. What routing information is missing?</summary>

The alert labels are not carrying enough ownership, severity, environment, or service context for notification policy to make a precise decision. Grafana routing works best when labels such as `team`, `service`, `severity`, and `environment` are present and consistently populated. Without those labels, every notification looks the same to the router. Add the labels to alert rules, then build contact point policies around real ownership and urgency.

</details>

## Hands-On Exercise

In this exercise, you will build a parameterized Grafana service dashboard and connect it to a Kubernetes-based monitoring workflow. The commands assume a test cluster running Kubernetes 1.35 or later, the Helm CLI, and a namespace dedicated to monitoring experiments. The Kubernetes commands below use the full `kubectl` form so each line is copy-paste runnable without first defining a shell alias.

### Setup

Create or reuse a disposable namespace for the exercise. The Helm commands install Grafana with persistence so your dashboard survives pod restarts in the lab environment. Do not use the example password in a shared or production cluster; it is intentionally plain for a local learning environment where the focus is dashboard behavior rather than secret management.

```bash
# Deploy Grafana by using the officially supported Helm chart.
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

kubectl create namespace critical-monitoring-infrastructure

helm install grafana grafana/grafana \
  --namespace critical-monitoring-infrastructure \
  --set adminPassword=change-this-lab-password \
  --set persistence.enabled=true \
  --set persistence.size=10Gi
```

Wait for the Grafana pod to become ready, then open a local tunnel to the service. In a real platform, Grafana should sit behind the organization's authentication and network controls. For the lab, port forwarding is sufficient because it keeps the exercise small and lets you inspect the UI at `http://127.0.0.1:3000`.

```bash
# Retrieve the generated admin password if you did not set one explicitly.
kubectl get secret -n critical-monitoring-infrastructure grafana -o jsonpath="{.data.admin-password}" | base64 -d

# Establish a local authenticated tunnel to the Grafana service.
kubectl port-forward -n critical-monitoring-infrastructure svc/grafana 3000:80

# Open http://127.0.0.1:3000 in a browser and authenticate as admin.
```

### Tasks

- [ ] Design a Grafana dashboard hierarchy with an overview page, a reusable service page, and a component drill-down page for one Kubernetes workload.
- [ ] Implement dynamic Grafana variables named `service` and `interval`, then use them in at least two PromQL template queries.
- [ ] Evaluate panel types and thresholds by building one stat panel for error percentage and one time series panel for latency.
- [ ] Diagnose a sample latency incident by correlating Prometheus metrics, Loki logs, and Tempo traces in Explore, even if your lab data uses mocked or low-volume signals.
- [ ] Configure Grafana alerting and notification routing for a high error percentage rule, using placeholder contact point secrets only.
- [ ] Export or provision the resulting dashboard JSON so the configuration can be reviewed outside the Grafana UI.

The dashboard variable skeleton below preserves the key fields you should review. Use a query variable for services when your Prometheus data source exposes a stable label. Use an interval variable to keep query resolution aligned with the selected time range. If your lab metric names differ, adapt the queries while preserving the same design goal.

```json
{
  "title": "Comprehensive Parameterized Navigational Service Diagnostic Dashboard",
  "templating": {
    "list": [
      {
        "name": "service",
        "type": "query",
        "datasource": "Prometheus",
        "query": "label_values(up, job)",
        "multi": false,
        "includeAll": false
      },
      {
        "name": "interval",
        "type": "interval",
        "auto": true,
        "auto_min": "10s",
        "options": [
          {"value": "1m", "text": "1 minute measurement interval"},
          {"value": "5m", "text": "5 minute measurement interval"},
          {"value": "15m", "text": "15 minute measurement interval"}
        ]
      }
    ]
  }
}
```

Build the golden-signal panels from these PromQL examples. The request-rate panel establishes traffic context, the error panel expresses failure as a percentage, the latency panel emphasizes tail behavior, and the CPU panel gives a basic saturation indicator. If your services use different metric names, keep the same relationships and adjust labels rather than abandoning the golden-signal structure.

```promql
sum(rate(http_requests_total{job="$service"}[$interval]))
```

```promql
sum(rate(http_requests_total{job="$service",status=~"5.."}[$interval]))
/
sum(rate(http_requests_total{job="$service"}[$interval]))
* 100
```

```promql
histogram_quantile(0.99,
  sum by (le)(rate(http_request_duration_seconds_bucket{job="$service"}[$interval]))
)
```

```promql
avg(rate(process_cpu_seconds_total{job="$service"}[$interval])) * 100
```

<details><summary>Solution guidance</summary>

A strong solution starts with a small overview dashboard that links to the service template instead of copying the service panels. The service template should expose `service` and `interval` variables, use titles that include selected variable context, and place golden signals near the top. The alert rule should use an error percentage expression rather than raw error count and should route through placeholder contact points. The exported dashboard should be readable enough that a reviewer can understand labels, thresholds, and panel intent without opening the Grafana UI first.

</details>

### Success Criteria

- [ ] The dashboard hierarchy lets a responder move from platform overview to service diagnosis to component detail.
- [ ] Dynamic Grafana variables change PromQL query targets without manual query editing.
- [ ] Error, latency, traffic, and saturation panels use clear units, titles, and thresholds.
- [ ] Explore can show a metric query beside a related log or trace query for the same time range.
- [ ] Alert routing labels identify severity, service, environment, and ownership.
- [ ] Dashboard JSON or provisioning files can be reviewed and restored from source control.

## Sources

- [Grafana documentation](https://grafana.com/docs/grafana/latest/)
- [Grafana dashboards documentation](https://grafana.com/docs/grafana/latest/dashboards/)
- [Grafana variables documentation](https://grafana.com/docs/grafana/latest/dashboards/variables/)
- [Grafana provisioning documentation](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [Grafana alerting documentation](https://grafana.com/docs/grafana/latest/alerting/)
- [Grafana contact points documentation](https://grafana.com/docs/grafana/latest/alerting/fundamentals/contact-points/)
- [Grafana Explore documentation](https://grafana.com/docs/grafana/latest/explore/)
- [Grafana Helm charts](https://grafana.github.io/helm-charts)
- [Grafonnet documentation](https://grafana.github.io/grafonnet/API/index.html)
- [Loki documentation](https://grafana.com/docs/loki/latest/)
- [Tempo documentation](https://grafana.com/docs/tempo/latest/)
- [Mimir documentation](https://grafana.com/docs/mimir/latest/)
- [Prometheus querying basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Kubernetes kubectl reference](https://kubernetes.io/docs/reference/kubectl/)

## Next Module

Continue to [Module 1.4: Loki](../module-1.4-loki/) to build the log aggregation layer that makes Grafana investigations richer than metrics alone.
