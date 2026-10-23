---
citations_verified: true
title: "Module 1.4: TCO & Budget Planning"
slug: on-premises/planning/module-1.4-tco-budget
sidebar:
  order: 5
---

> **Complexity**: `[MEDIUM]` | Time: 60 minutes
>
> **Prerequisites**: [Module 1.2: Server Sizing](../module-1.2-server-sizing/), [FinOps Fundamentals](/k8s/finops/module-1.1-finops-fundamentals/)

---

## What You'll Be Able to Do

After completing this module, you will be able to:

1. **Design** a comprehensive TCO model that captures hardware, staffing, facilities, networking, support contracts, and opportunity costs across a 3 and 5 year horizon.
2. **Evaluate** cloud versus on-premises economics with discounted cash projections that include reserved-instance discounts, egress, managed-service fees, and realistic refresh cycles.
3. **Plan** budget proposals that withstand CFO scrutiny by separating CapEx from OpEx, surfacing hidden costs, and documenting every pricing assumption with a date and source.
4. **Diagnose** the budgeting blind spots that cause on-premises projects to overshoot estimates by two to three times, and apply contingency, sensitivity, and decision-point patterns that catch them before they hit the board.

---

## Why This Module Matters

In 2023 a logistics company presented its board with a plan to migrate from AWS to on-premises Kubernetes. The infrastructure team built the case on a single number: hardware. They priced servers, switches, and storage at three hundred and eighty thousand dollars, walked the CFO through the spreadsheet, and got approval the same week. Twelve months later the actual run rate was one point one million dollars and rising. They had not budgeted for colocation at seventy two thousand a year, redundant internet circuits at thirty six thousand, a part-time facilities manager at forty five thousand, two extra engineers at three hundred and fifty thousand combined, hardware support contracts at thirty eight thousand, or one hundred and eighty thousand in professional services to wire the first racks. The "savings" against cloud disappeared completely, and the team spent a quarter explaining the variance instead of shipping product.

The infrastructure team was not incompetent. They were engineers, not financial modelers, and they did what engineers do best: they costed the things they could touch. They missed the costs that arrive on monthly invoices, the costs that require finance partners to forecast, and the costs that show up only when a hard drive fails at two in the morning. This module exists so the next person in that meeting walks in with a model that captures the iceberg, not just the tip. By the end you will know what categories belong in the spreadsheet, how to defend each line, and how to compare the answer fairly to a real cloud bill rather than a list-price strawman.

Hardware sits at the top of the iceberg. Below the waterline you find staffing, power, cooling, colocation, networking, support contracts, software licences, insurance, compliance, training, and the opportunity cost of engineers maintaining infrastructure instead of shipping features. The submerged portion is typically three to five times the hardware cost over a three year horizon, and the ratio gets worse at smaller scale because fixed costs do not amortise across a tiny fleet.

---

## What You'll Learn

This module walks through the full cost taxonomy for on-premises Kubernetes, explains how to build a defensible 3 year and 5 year TCO model, contrasts CapEx and OpEx and the financial implications of each, shows how to calculate power and cooling correctly using PUE, develops a staffing model that accounts for automation maturity, and closes with a cloud breakeven analysis that survives contact with a finance partner. The same techniques apply to colocation, edge, and hybrid models, with adjustments noted where the math diverges.

---

## Cost Taxonomy

Before you can model anything you need an exhaustive list of cost categories. Most failed budgets fail not because the team got a number wrong, but because a whole category was missing from the sheet. Walk through the taxonomy below and treat it as a checklist: every line either has a value or has an explicit "not applicable, because…" note. A blank line is a question waiting to bite you.

### Capital Expenditure (CapEx)

Capital expenditure is one-time spend that the finance team capitalises on the balance sheet and depreciates over the asset's useful life, usually three to five years for servers and longer for facility-grade switches. The depreciation schedule matters because it changes the per-month cost the CFO sees and it determines when an asset becomes a candidate for refresh. If you depreciate over three years and run for five, the back two years look spectacularly cheap on the books even though maintenance costs are climbing.

```
┌─────────────────────────────────────────────────────────────┐
│                    CAPEX COMPONENTS                          │
│                                                               │
│  COMPUTE                                                     │
│  ├── Servers (CPU, RAM, NVMe)          $8K-25K per node     │
│  ├── GPU accelerators (if needed)      $10K-40K per GPU     │
│  └── Spare parts (drives, PSUs, RAM)   5-10% of server cost│
│                                                               │
│  NETWORKING                                                  │
│  ├── Spine switches (100GbE)           $15K-40K each        │
│  ├── ToR switches (25GbE)              $3K-8K each          │
│  ├── Management switches (1GbE)        $500-2K each         │
│  ├── Cabling (fiber + copper)          $2K-5K per rack      │
│  ├── Firewalls / load balancers        $5K-50K              │
│  └── Out-of-band management network    $1K-3K              │
│                                                               │
│  STORAGE (if not using server-local)                        │
│  ├── SAN/NAS (enterprise)              $50K-500K            │
│  └── Dedicated Ceph nodes              $10K-20K each        │
│                                                               │
│  INFRASTRUCTURE                                              │
│  ├── Racks (42U)                       $1K-3K each          │
│  ├── PDUs (redundant A+B)             $500-2K per rack      │
│  ├── UPS (if not colo-provided)        $5K-20K             │
│  └── KVM / console access              $1K-5K              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

A few traps hide in this list. Spare parts are the single most common omission because most teams treat them as a "we will buy when something fails" line, but a real spares budget covers at least one hot spare drive per server class, two power supplies per rack, and enough memory DIMMs to repopulate a failed slot without ordering. Cabling looks trivial until you discover that pre-terminated MPO trunks for a 100GbE spine cost more than the patch panel they plug into. Out-of-band management is not optional in a serious on-prem build: when the production network goes down at three in the morning, the only way you reach a misbehaving node is through a separate physical path that includes its own switches, its own DHCP, and ideally its own cellular failover.

> **Pause and predict**: A team presents their on-premises budget to the CFO showing only the CapEx line items above. The CFO approves. List at least four cost categories that will cause the project to exceed estimates within the first year, and for each one explain why a hardware-focused team is likely to forget it. Write your list down, then read the OpEx section and check yourself.

### Operating Expenditure (OpEx)

Operating expenditure is recurring spend that hits the income statement every month. OpEx is where on-prem budgets quietly bleed, because each line is small enough to feel ignorable but the sum dominates the model. Where CapEx is a single signature, OpEx is twelve months of invoices that finance teams rarely revisit unless someone forces a true-up. You want to force one annually.

```
┌─────────────────────────────────────────────────────────────┐
│                    OPEX COMPONENTS                           │
│                                                               │
│  FACILITY (monthly)                                          │
│  ├── Colocation (per rack)             $800-2,500/mo        │
│  ├── Power (per kW)                    $80-150/kW/mo        │
│  ├── Cooling (included in colo or      ~40% of power cost   │
│  │   separate HVAC cost)                                     │
│  ├── Internet circuits (redundant)     $500-3,000/mo        │
│  └── Cross-connects to other cages     $200-500/mo each     │
│                                                               │
│  STAFFING (annual, fully loaded)                             │
│  ├── Infrastructure engineer           $150K-220K           │
│  ├── Network engineer (shared)         $70K-110K (0.5 FTE)  │
│  ├── Security engineer (shared)        $80K-120K (0.5 FTE)  │
│  └── On-call compensation              $15K-30K/person/yr   │
│                                                               │
│  MAINTENANCE (annual)                                        │
│  ├── Hardware support contract          3-5% of hardware    │
│  │   (Dell ProSupport, HPE Pointnext)  cost per year        │
│  ├── Software licenses                 $0-50K (RHEL, etc.)  │
│  └── Professional services             $20K-100K (one-time) │
│                                                               │
│  HIDDEN COSTS                                                │
│  ├── Opportunity cost (eng not         Hard to quantify     │
│  │   building product)                                       │
│  ├── Insurance (equipment)             $2K-10K/yr           │
│  ├── Compliance/audit                  $10K-50K/yr          │
│  └── Training & conferences            $5K-15K/yr           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

Notice that "fully loaded" appears next to every staffing number. Salary is roughly two thirds of what an engineer actually costs the company once you add employer payroll taxes, health benefits, retirement contributions, equipment, software seats, office costs, and the share of recruiting and HR they consume. The standard multiplier is 1.3 for low-cost markets and 1.5 for high-cost ones, applied to base salary. If your CFO sees a budget line that says `$150K per engineer` and assumes that includes overhead, you will discover the gap when the actual departmental ledger arrives and the headcount line is fifty percent higher than your model. Be explicit about which version of the number you used and label it on the line.

The hidden-costs block deserves its own paragraph because it captures the categories that boards routinely cut from budgets and then complain about later. Insurance is easy to justify when a single failed UPS can damage a quarter million dollars of equipment. Compliance shows up the moment your auditor asks for SOC2 evidence about physical controls and you discover you have no logs from the colo provider. Training is what keeps your team employable, which is what keeps them at your company instead of taking the rare bare-metal Kubernetes skillset to a competitor. None of these lines are optional in practice, only in theory, and theory does not pay invoices.

---

## Power and Cooling Calculations

Power is the cost line that most surprises engineering teams when they leave cloud. In a hyperscaler bill power is invisible: it is wrapped into the per-hour instance rate. On-prem you pay for it explicitly, you pay for the cooling needed to remove the heat that power generated, and you pay for the inefficiency of the facility delivering both. Three numbers determine your monthly power bill: the watts your servers actually draw, the cooling overhead expressed as PUE, and the rate per kilowatt-hour your facility charges you.

### Per-Server Power

Server power is not a single number. Idle draw is what you pay for empty servers and what you use to size UPS ride-through. Full-load draw is what you pay for under sustained traffic and what you must respect when you fill a rack's PDUs. The realistic operating point sits somewhere in between, governed by your average utilisation. Most Kubernetes clusters land between forty and sixty percent average CPU utilisation, which translates to roughly four hundred watts on a modern dual-socket node. Use that as a planning anchor and verify with measurements once production traffic is flowing.

```
┌─────────────────────────────────────────────────────────────┐
│                 POWER ESTIMATION                             │
│                                                               │
│  Component           Idle Power    Full Load                 │
│  ─────────────────   ──────────   ─────────                 │
│  Dual Xeon/EPYC      120W         500-600W                  │
│  RAM (512GB DDR5)    20W          40W                       │
│  NVMe (4x 3.84TB)   8W           20W                       │
│  NICs (2x 25GbE)    5W           15W                       │
│  Fans + PSU loss     30W          60W                       │
│  ─────────────────   ──────────   ─────────                 │
│  Total per server    ~180W        ~700W                     │
│                                                               │
│  GPU server (4x A100): add 1,200W at full load              │
│                                                               │
│  Typical K8s utilization: 40-60% = ~400W average            │
│                                                               │
│  Per rack (8 servers):                                       │
│    Average: 8 x 400W = 3.2 kW                              │
│    Peak: 8 x 700W = 5.6 kW                                 │
│                                                               │
│  Monthly power cost:                                         │
│    3.2 kW x 730 hours x $0.12/kWh = $280/month             │
│    Plus cooling (PUE 1.4): $280 x 1.4 = $392/month         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

Two practical points come out of that block. First, peak power, not average power, determines how many servers fit in a rack. A rack rated for 7 kilowatts fills at ten servers on average load but only eight on peak, and if you cram eleven you trip a breaker the first time a batch job runs hot on every node simultaneously. Always size rack density against peak draw with a fifteen percent headroom. Second, GPU servers change the math entirely. A single rack of eight nodes carrying four A100s each can pull twenty kilowatts continuously, which exceeds the per-rack envelope of most colocation cages and requires a separate, more expensive high-density contract. Decide whether GPU workloads belong in a different rack or even a different facility before you sign a colo agreement.

### PUE (Power Usage Effectiveness)

[PUE is the ratio of total facility power to IT power](https://www.iso.org/standard/30134-2), and it is the single multiplier that determines how cheaply your servers get cooled. A perfect facility would deliver one watt of cooling and overhead per watt of compute, but no real facility is perfect. Hyperscalers using free-air cooling and chilled water reach 1.1 to 1.2. A modern, well-run colocation provider lands at 1.3 to 1.4. An older facility runs at 1.6, and a poorly designed room can exceed 2.0. The number matters because every watt your servers draw gets multiplied by PUE before billing.

```
Total facility power
PUE = ─────────────────
      IT equipment power

PUE 1.0 = perfect (impossible)
PUE 1.2 = excellent (hyperscaler DCs)
PUE 1.4 = good (modern colo)
PUE 1.6 = average (older facility)
PUE 2.0 = poor (needs upgrade)

Your effective power cost = IT power cost × PUE
```

Always ask the colocation provider for their measured PUE and the methodology they use to compute it. Some providers quote design PUE, which is what the facility could theoretically achieve, while others quote average measured PUE across the prior twelve months. The latter is the only honest number for budgeting. If a provider refuses to share measured PUE, treat it as a yellow flag and price the contract assuming 1.6, then renegotiate if they later prove better.

---

## Staffing Models

Staffing is where on-prem budgets either succeed or quietly fail. Hardware is a one-time decision, but staffing is a quarter-on-quarter commitment that scales with your fleet, your incident rate, and your automation maturity. Most teams underestimate staffing cost because they reason from headcount, but the question is not "how many engineers do I need" but rather "how many engineer-equivalents does this fleet consume." A senior engineer being paged at three in the morning twice a week consumes far more of the org's capacity than the org-chart implies.

> **Stop and think**: Your organisation currently manages 80 nodes with 2 engineers using Ansible and shell scripts. You want to grow to 200 nodes within the year. Should you hire 2 more engineers, or invest 6 months of one engineer's time in Cluster API and GitOps automation? List the factors beyond cost that influence the decision: hiring lead time, the risk of automation rollout failures, on-call coverage during the build, and the second-order effect on team morale and retention.

### The Nodes-Per-Engineer Ratio

The single most useful number for staffing forecasts is nodes-per-engineer, and it varies wildly with automation level. The table below summarises four maturity tiers. Note that the tiers are about how the team works, not about how good the engineers are, and a brilliant team using shell scripts will still cap out around thirty nodes per engineer because the work itself is irreducibly manual at that tier.

| Automation Level | Nodes per Engineer | Tools |
|-----------------|-------------------|-------|
| Manual (kubectl + scripts) | 20-30 | Shell scripts, manual provisioning |
| Partially automated | 50-80 | Ansible, Terraform, basic CI/CD |
| Fully automated | 100-200 | Cluster API, GitOps, machine health checks |
| Platform team at scale | 200-500 | Custom controllers, self-service portal |

```
┌─────────────────────────────────────────────────────────────┐
│               STAFFING COST MODEL                            │
│                                                               │
│  Cluster Size    Engineers    Annual Staff Cost               │
│  ────────────    ─────────   ─────────────────               │
│  20 nodes        2 (shared)  $200K (0.5 FTE dedicated)      │
│  50 nodes        2           $350K                           │
│  100 nodes       3           $525K                           │
│  200 nodes       4           $700K                           │
│  500 nodes       6-8         $1.2M                           │
│  1000+ nodes     10-15       $2M+                            │
│                                                               │
│  Note: "shared" means engineers also do other work.          │
│  Fully loaded cost = salary × 1.3-1.5 (benefits, tax, etc.)│
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

The numbers above assume a US non-coastal salary anchor of roughly one hundred and seventy five thousand dollars fully loaded per engineer. They are deliberately conservative for a mid-to-senior team. Do not paste them into a budget for a different market without rebasing them, because the on-prem versus cloud verdict swings significantly with staffing cost.

### Regional Staffing Reality Check

The `3 engineers x $175K fully loaded` example is deliberately conservative for a US-centric mid-to-senior infrastructure team. Do not reuse it blindly. The table below gives realistic anchors for fully loaded infrastructure-engineer cost in different markets as of early 2026. If your staffing market is cheaper than the example, the on-prem model improves materially because staffing dominates the OpEx line. If you need scarce specialists in a major metro or twenty-four-by-seven coverage with three shifts, it worsens just as dramatically. Always localise the staffing line before presenting the TCO model as a decision document.

| Market | Typical fully loaded infrastructure engineer cost |
|---|---|
| Central / Eastern Europe | `$90K-130K` |
| Western Europe | `$120K-180K` |
| UK / Ireland | `$140K-200K` |
| US non-coastal | `$150K-210K` |
| US coastal / major tech hubs | `$175K-240K+` |

A second adjustment worth making is on-call. A team that runs production for a payments platform needs continuous coverage, which usually means either a follow-the-sun model with a second team in another timezone or a paid rotation that compensates engineers for being woken up. Both approaches add fifteen to thirty thousand dollars per engineer per year to the staffing line, and neither is captured in base salary. If your model omits on-call compensation, you are either underpaying engineers, eroding retention, or quietly accruing the cost in turnover that finance will eventually notice.

---

> **Pause and predict**: Before looking at the TCO model below, estimate what percentage of the total 3-year on-premises cost is hardware versus staffing for a 100-node cluster. Most engineers guess hardware dominates, because hardware is the part they touch. Write down your guess as a percentage split, then check it against the model. If your intuition is more than fifteen points off, that is a useful piece of self-knowledge to carry into your next budget conversation.

## 3-Year TCO Model

A 3 year horizon is the natural board-level comparison because [cloud reserved instance terms come in one and three year tranches](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-reserved-instances.html), and most server depreciation schedules also run three years. Building the model is a mechanical exercise once the taxonomy is in place: list every CapEx line in year zero, list every OpEx line as an annual recurring number, multiply OpEx by three, and add the totals. The hard part is making sure the cloud comparison column is honest, which means using your real cloud bill or a calculator output dated within a few weeks of the analysis, not a number you remember from a blog post.

### Template

```
┌─────────────────────────────────────────────────────────────┐
│   3-YEAR TCO MODEL (100 K8s nodes on 13 bare-metal servers) │
│   (Each server: 64 cores, 256GB → ~8 K8s nodes per server)  │
│                                                               │
│  YEAR 0 (SETUP)                                              │
│  ────────────────────────────────────────                    │
│  Servers (13 x $15K)                    $195,000            │
│  Networking (switches + cabling)         $45,000            │
│  Storage (Ceph nodes, 3 x $12K)         $36,000            │
│  Racks + PDUs                            $8,000             │
│  Professional services (buildout)        $60,000            │
│  ────────────────────────────────────────                    │
│  CapEx subtotal                         $344,000            │
│                                                               │
│  ANNUAL OPEX                                                 │
│  ────────────────────────────────────────                    │
│  Colocation (3 racks)                    $54,000            │
│  Power + cooling (7kW IT x PUE 1.4      $10,300            │
│    x $0.12/kWh x 8,760 hrs)                                 │
│  Internet (2x circuits)                  $24,000            │
│  Staffing (3 engineers)                 $525,000            │
│  Maintenance contracts                   $16,500            │
│  Software licenses                       $12,000            │
│  Insurance + compliance                  $15,000            │
│  ────────────────────────────────────────                    │
│  OpEx subtotal (per year)              $656,800             │
│                                                               │
│  3-YEAR TOTAL                                                │
│  ────────────────────────────────────────                    │
│  CapEx                                  $344,000            │
│  OpEx (3 years)                       $1,970,400            │
│  ────────────────────────────────────────                    │
│  TOTAL                                $2,314,400            │
│  Per month                               $64,289            │
│                                                               │
│  CLOUD COMPARISON (illustrative AWS pricing check:          │
│  2026-04-17, us-east-1, Linux, m6i.2xlarge equivalent)      │
│  ────────────────────────────────────────                    │
│  On-demand: 100 x $280/mo           $1,008,000 (3 yr)      │
│  1-year RI (no upfront, ~35% off)      $655,000 (3 yr)     │
│  3-year RI (all upfront, ~55% off)     $454,000 (3 yr)     │
│  3-year RI (~40% off sensitivity)     $605,000 (3 yr)      │
│  + EKS fee + storage + data xfer     ~$200,000 (3 yr)      │
│                                                               │
│  VERDICT at 100 nodes (13 servers):                          │
│  Cloud (3yr RI + extras) ≈ $650K vs On-prem ≈ $2.3M        │
│  → Cloud wins decisively (staffing dominates on-prem)       │
│                                                               │
│  Breakeven: ~300-500 nodes where staffing amortizes         │
│  and cloud egress/storage costs grow linearly                │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

Use that cloud block as a dated template, not a universal truth. Pricing assumptions drift faster than most documents do, so stamp the provider, region, date, and instance family every time you use the template, and date-stamp the on-prem hardware quotes too. Compare against your real cloud bill when possible, not list pricing, because most teams already enjoy enterprise discount programs, savings plans, or committed-use discounts that are invisible in calculator output. Always run at least one reserved-commit sensitivity test such as a 40 percent and a 55 percent discount case, because the breakeven line moves materially between the two and a single point estimate will mislead the board.

The verdict in the template is not a universal claim that cloud always wins at 100 nodes. It is a claim about this particular configuration: thirteen mid-range bare metal servers, three engineers in a US salary band, a colo at thirty year-one rack rate, and AWS reserved pricing on m6i-class equivalents. Change any of those inputs materially and the verdict can flip. A team that already has the engineers on payroll for other work, or that runs in a market with cheaper staffing, or that needs ten times the storage with heavy egress, will see different numbers. The template's job is to give you the structure; the verdict is yours to compute against your own inputs.

---

## 5-Year TCO Model

The 3-year model is usually the easiest board-level comparison because cloud reserved-commit terms and common depreciation windows line up neatly. But many on-prem decisions only make sense when you model the extra two years explicitly, and many on-prem decisions only fail when you do. Years 4 and 5 are where teams either prove that a private platform has become efficient, or discover that deferred refreshes, support renewals, and capacity growth erased the apparent savings. The discipline of building a 5-year sheet forces you to answer questions that the 3-year sheet lets you skip: what happens when the warranty expires, when the cluster needs to be twenty percent bigger, and when half the fleet is old enough to retire.

### What Changes In Years 4 And 5

The table below summarises the cost areas where the 3-year and 5-year models diverge. Each row is a question the 3-year model lets you ignore and the 5-year model forces you to answer. If you cannot answer a row honestly, mark it as a known unknown in the model and assign a contingency rather than zero, because zero is the wrong number and the CFO will ask which one of you got it wrong when reality lands.

| Cost area | 3-year assumption | 5-year adjustment |
|---|---|---|
| Servers | initial purchase only | decide whether to keep, expand, or refresh the fleet |
| Maintenance | 3-5% of hardware per year | often rises after year 3 as vendor support ages |
| Capacity growth | often ignored | add new nodes, racks, and network ports for realistic growth |
| Storage | sized for current need | include retention growth, backup growth, or archival tiers |
| Power and colo | steady-state estimate | increase for growth, density changes, or power repricing |
| Staffing | fixed ratio | reflect whether automation improves the nodes-per-engineer ratio |
| Opportunity cost | mostly qualitative | reassess whether the platform now accelerates or slows product work |

Maintenance pricing is the row that catches most teams off guard. Vendor support contracts on three-year-old servers often jump twenty to forty percent at renewal because the vendor wants to push you toward refresh. If you choose to keep the gear, you accept the price increase. If you choose to refresh, you accept a CapEx spike. Either way, the 5-year model needs to show the choice explicitly with both options costed, because hand-waving "we will figure it out" is exactly how the budget gets the year four surprise.

> **Pause and decide**: At your current fleet size, what is your year-four refresh strategy? You have three choices: extend support and run the existing fleet a year longer, refresh one third of the fleet each year on a rolling basis, or do a single bulk refresh in year five. For each option, write down the CapEx pattern, the support cost trajectory, and the operational risk. There is no universally correct answer, but there is a wrong answer for your context, and committing to one before the year-three review is part of how you defend the 5-year number.

### 5-Year Carry-Forward Template

Use the same 100-node and 13-server scenario, but carry the model forward year by year instead of multiplying the 3-year result by five thirds. The carry-forward approach forces you to think about what changes year over year and surfaces the years where cost spikes hit, which the multiplication approach hides inside an averaged number.

```
┌─────────────────────────────────────────────────────────────┐
│               5-YEAR CARRY-FORWARD MODEL                    │
│                                                             │
│  ASSUMPTIONS                                                │
│  ───────────────────────────────────────                    │
│  Workload growth                           15% per year     │
│  Discount rate for NPV                      8%              │
│  Hardware strategy          keep fleet through year 4,      │
│                             partial refresh in year 5       │
│  Support pricing           5% years 1-3, 7% on aging gear   │
│                                                             │
│  YEAR 0 (SETUP)                                              │
│  CapEx                                  $344,000           │
│                                                             │
│  YEAR 1 (BASELINE)                                           │
│  OpEx                                   $656,800           │
│                                                             │
│  YEAR 2 (STEADY STATE)                                       │
│  OpEx                                   $656,800           │
│                                                             │
│  YEAR 3 (STEADY STATE)                                       │
│  OpEx                                   $656,800           │
│                                                             │
│  YEAR 4 (GROWTH WITHOUT FULL REFRESH)                        │
│  2 new servers + optics + rack space      $41,000 CapEx    │
│  Base Year 3 OpEx                        $656,800          │
│  Maintenance uplift on aging hardware     $18,600          │
│  Extra colo + power + network             $12,500          │
│  Staffing flat due to automation           $0              │
│  Year 4 OpEx subtotal                    $687,900          │
│                                                             │
│  YEAR 5 (PARTIAL REFRESH + RETIREMENT)                      │
│  Refresh 6 oldest servers               $120,000           │
│  Retirement / data-destruction credit   -$12,000           │
│  Maintenance on mixed old/new fleet      $28,000           │
│  Extra storage expansion                 $24,000           │
│  Colo + power repricing uplift           $12,000           │
│  Year 5 OpEx subtotal                    $720,800          │
│                                                             │
│  5-YEAR CASH TOTAL                                            │
│  ───────────────────────────────────────                    │
│  CapEx (years 0, 4, 5)                  $493,000          │
│  OpEx (years 1-5)                     $3,379,100          │
│  TOTAL                                 $3,872,100          │
│  NPV @ 8%                              $3,132,000          │
│                                                             │
│  Effective monthly average (5 years)      $64,535          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### How To Use 5-Year Modeling Correctly

Build the 5-year sheet as separate yearly rows with CapEx, OpEx, and cumulative total instead of extrapolating from the 3-year total, because the year-over-year shape is information the cumulative number throws away. Tie utilisation and growth to power, cooling, and rack density so that a busier cluster increases PUE-adjusted facility cost rather than staying flat: a fleet that doubles its average CPU draw will not stay at the same power line, and pretending it will makes the OpEx column lie. Make the asset decision explicit each year, choosing between keep, expand, refresh, and retire, because maintenance and support pricing changes with each choice and the choice itself is a budget signal to the board about your operating philosophy. Include network switch lifecycle and OS or distribution subscription renewals if they are part of your operating model, because those often show up after the "servers only" budget has already been approved and they always feel surprising when they do.

Show both nominal cash total and discounted NPV so that finance can compare on-prem spend with cloud reserved-commit terms on equivalent footing. Cash totals overstate the cost of front-loaded CapEx relative to spread-out OpEx, and NPV at the company's cost of capital corrects for that. Run at least three scenarios on top of the base case: utilisation plus twenty percent, cloud pricing minus thirty percent, and a 12-month refresh delay. Each scenario tests a specific risk and the spread between them is your honesty range, the band in which the real number is most likely to land. Boards trust ranges far more than they trust point estimates from engineers, because a single point estimate that ends up wrong is harder to recover credibility from than a range that bracketed reality.

### Practical Interpretation

The 5-year view often changes the conclusion. Cloud still wins when staffing remains flat but the on-prem fleet stays small enough that overhead never amortises across a meaningful workload base. On-prem improves when the team automates aggressively, extends hardware life safely past warranty, and spreads fixed staffing across more workload as the business grows. Hybrid becomes the right answer when only a subset of predictable, steady-state workloads belongs on owned hardware while bursty or experimental work stays elastic. If your 3-year model barely favours on-prem, the 5-year model is where you discover whether that margin is real or imaginary, and the honest answer is more often "imaginary" than infrastructure teams want to admit.

---

## Did You Know?

- **Colocation pricing varies three to four times by market.** A full rack in Northern Virginia (Ashburn) costs roughly eight hundred to twelve hundred dollars a month. The same rack in London costs fifteen hundred to twenty five hundred a month. In Singapore it can exceed three thousand. Location choice has a massive TCO impact and is one of the few levers you can pull without changing your architecture, which is why finance partners often ask early whether a different region is on the table.
- **Power costs are the fastest-growing component of on-prem TCO.** Electricity prices have increased twenty to forty percent in many markets since 2020, driven by grid stress, fuel cost volatility, and AI-driven demand on regional substations. GPU servers make this worse: a rack of eight GPU servers can draw fifteen to twenty kilowatts, costing fifteen hundred to three thousand dollars a month in power alone, before cooling overhead.
- **Hardware refresh cycles are getting longer.** In 2010 servers were refreshed every three years. Today five-year cycles are common because modern servers using DDR5 and PCIe Gen5 depreciate more slowly, firmware updates extend useful life, and the marginal performance gain of a new generation is smaller than it used to be. The longer cycle materially improves the on-prem TCO case because you amortise the same CapEx across more workload-years.
- **The biggest hidden cost is not hardware, it is hiring.** Finding engineers who can operate bare metal Kubernetes across Linux, networking, storage, and hardware troubleshooting takes three to six months and costs twenty to forty thousand dollars in recruiting fees per hire. Many organisations underestimate this lead time and end up running their planned go-live with two thirds of the team they intended, which silently degrades reliability for the first year.

---

## Common Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| Hardware-only budgeting | Actual cost is 3-5x hardware | Use the full cost taxonomy |
| Forgetting PUE | Power bill is 1.2-1.6x raw IT power | Multiply IT power by measured facility PUE |
| Linear staffing model | Assuming 1 engineer per 50 nodes always | Tie staffing ratio to automation maturity tier |
| Ignoring opportunity cost | Engineers maintaining infra not building product | Include in decision, even if hard to quantify |
| Not negotiating colo | Taking the first quote from the colo provider | Get 3+ quotes; negotiate multi-year commits for 15-25% discounts |
| Comparing list prices | Cloud list vs on-prem actual | Use your real cloud bill; apply RI/CUD discounts |
| No hardware buffer budget | First year always has surprise needs | Add 15-20% contingency to CapEx |
| Forgetting decommission costs | Old hardware needs disposal, data wiping | Budget for certified data destruction and e-waste recycling |

---

## Quiz

### Question 1
Your on-prem cluster uses 5 kW of IT power in a colocation facility with PUE 1.5. Electricity costs $0.12/kWh. Your CFO asks for the total monthly power cost. Walk through the calculation and explain why the PUE multiplier matters.

<details>
<summary>Answer</summary>

**\$657 per month.** The calculation chains three numbers. Total facility power is IT power times PUE, so 5 kW times 1.5 equals 7.5 kW. Hours per month are 730, computed as 24 hours times 365 days divided by 12 months. Monthly cost is therefore 7.5 kW times 730 hours times \$0.12 per kWh, which equals \$657.

The PUE multiplier matters because cooling, lighting, UPS conversion losses, and other facility overhead all show up on the same electricity meter. A PUE of 1.5 means that for every watt your servers draw, you pay for an additional half watt of facility overhead. If you forget the multiplier and bill the CFO \$438 a month, you will discover the gap when the colo invoice arrives and you owe an extra \$219 every month with no budget line to put it on. Always quote IT power and total power separately so the multiplier is visible and defensible.
</details>

### Question 2
You need 3 infrastructure engineers at \$175K fully loaded each to manage 100 nodes. At what node count does this staffing model break even against cloud at \$500 per node per month, assuming staffing stays flat through automation?

<details>
<summary>Answer</summary>

**Approximately 200 nodes.** Staffing alone costs \$525K per year, which is \$43,750 per month. Divide by node count to get the staffing cost per node per month. At 100 nodes that is \$437.50 per node, which is 88 percent of the cloud cost before you have added a single dollar of hardware, colocation, or power. At 200 nodes it drops to \$218.75 per node, which leaves enough headroom for hardware amortised at \$100 to \$200 per node per month and facility at \$50 to \$100 per node per month while still beating cloud at \$500.

The breakeven sits around 200 nodes because that is where the fixed staffing cost amortises across enough workload to leave room for the variable costs. Below 200 nodes, the staffing line dominates and cloud wins on simplicity alone. Above 300 nodes, the gap widens in favour of on-prem because cloud cost scales linearly while on-prem staffing scales sublinearly thanks to automation. The exact number depends on your salary band and your automation maturity, both of which you should rebase before quoting this answer in a real proposal.
</details>

### Question 3
A vendor offers a "free" Kubernetes distribution but charges $2,000 per node per year for enterprise support. You run a 100-node cluster. Is this a good deal, and what conditions would change the answer?

<details>
<summary>Answer</summary>

**Probably not, at face value.** Two thousand per node times 100 nodes is two hundred thousand dollars per year, which exceeds the cost of one fully loaded engineer in the example we have been using. For that money you could hire an engineer who builds internal expertise, owns your specific workloads, and stays with the company instead of being a contractual line.

However, the calculation flips under three conditions. First, if you have fewer than two Kubernetes engineers on staff, the vendor support contract is buying you the on-call coverage and escalation path that you cannot otherwise provide, and the alternative is not "save the money" but "have an outage you cannot resolve." Second, if your industry requires SLA-backed vendor support for regulatory or audit reasons, the contract is a compliance artefact and you are not buying it for the technology. Third, if the distribution bundles features you would otherwise build in-house, such as multi-tenancy, security hardening, or air-gapped registry support, then the cost comparison is against your engineering time to build those features, which usually exceeds two hundred thousand a year for a meaningful subset.

For most organisations above 50 nodes that are not in a regulated industry, investing in team capability is the better long-term decision because the team compounds in value while the support contract just renews. For organisations under 50 nodes or in regulated industries, the support contract often wins.
</details>

### Question 4
Your organisation is choosing between owning a datacenter and using colocation. At what scale and under what conditions does owning become the right answer?

<details>
<summary>Answer</summary>

**Colocation wins for almost everyone.** Building a datacenter costs ten to fifty million dollars and takes twelve to twenty four months from groundbreaking to first server. The economics only work at massive scale, typically a thousand or more servers, or under specific regulatory regimes where physical custody is non-negotiable.

Colocation gives you four advantages that are hard to replicate. There are no construction or permitting costs, the cooling and power and physical security are amortised across other tenants, redundant utility feeds and generators come bundled, and you can scale racks up or down without capital projects. The flexibility of moving from three racks to ten in the same cage with a phone call is something you cannot price into an owned-facility model.

Owning makes sense when you need full physical control for government or classified workloads, when your scale is large enough that the per-kW operating cost beats colocation rates, when you need custom cooling such as direct liquid cooling for high-density GPU racks that few colo providers offer, or when you have a ten plus year horizon that justifies the construction amortisation. The rule of thumb is that under fifty racks colocation always wins, between fifty and two hundred racks the answer depends on workload specifics, and above two hundred racks with a long horizon you should at least evaluate building. Most organisations never cross those thresholds.
</details>

### Question 5
A team presents a 3-year on-prem TCO that comes in 10 percent below the cloud comparison. The CFO asks for a 5-year extension before approving. The team multiplies their 3-year total by five thirds and presents the new number, which still favours on-prem by a similar margin. Why is this approach wrong, and what should they do instead?

<details>
<summary>Answer</summary>

**The multiplication approach hides the year-four and year-five cost shocks that determine whether the on-prem case actually holds.** A 3-year total is a sum of three years that look very similar to each other: the same hardware running, the same support contract, the same staffing line. The years 4 and 5 do not look like that at all. Vendor support pricing typically jumps twenty to forty percent on aging gear at the year-three renewal, which the multiplication approach treats as zero change. Capacity growth requires additional servers, switches, and rack space, which the multiplication approach ignores. Hardware refresh decisions land in year four or five, which the multiplication approach amortises into a constant rate that does not match reality.

The team should build a carry-forward model with separate rows for each year. Year 4 should reflect maintenance uplift on aging hardware, the CapEx of any growth-driven additions, and any change in colo or power footprint. Year 5 should reflect the chosen refresh strategy, whether that is rolling refresh, full refresh, or extended support with delayed refresh. The model should also discount future cash flows to NPV at the company's cost of capital so finance can compare against cloud reserved-commit terms on equivalent footing. The honest answer the model produces may still favour on-prem, but it will do so on a defensible basis with the year-four spike visible rather than smoothed away.
</details>

### Question 6
Your colocation provider quotes "PUE of 1.3" in their sales material. When you ask for the methodology, they say it is the design specification for the facility. What should you do, and how should you price the contract?

<details>
<summary>Answer</summary>

**Treat the design PUE with skepticism and price the contract assuming a worse number, then renegotiate if they prove better.** Design PUE is the value the facility could theoretically achieve under ideal conditions, with cooling running optimally, partial loading, and benign weather. It is not what you will be billed against. Measured PUE, averaged across the prior twelve months and including seasonal variation, is the only honest budgeting input.

Practically, you should ask for the prior-twelve-month measured PUE in writing, broken down by month so you can see summer cooling spikes. If they refuse, treat that as a yellow flag and price your power line at PUE 1.6 rather than 1.3. The difference matters: at 5 kW IT load and 12 cents per kWh, PUE 1.3 produces a power bill of roughly 570 dollars a month while PUE 1.6 produces 700, and over three years the gap is around 4,700 dollars per 5 kW of compute. If your cluster runs 30 kW of IT load, the gap is 28,000 over three years, which is real money and absolutely worth a hard negotiation up front.

If the provider eventually delivers measured PUE that beats your 1.6 assumption, you can either renegotiate the price downward or treat the underspend as a contingency cushion. Either outcome beats believing a sales number and discovering the gap on month one.
</details>

### Question 7
Your team is debating whether to spend six months of one engineer's time building Cluster API and GitOps automation, or to hire two more engineers to operate the growing fleet manually. The cluster will grow from 80 to 200 nodes either way. Walk through the TCO implications of both choices over three years.

<details>
<summary>Answer</summary>

**The automation path almost always wins on three-year cost, but the hiring path wins on speed and risk.** The hiring path costs roughly \$350K per year in fully loaded staffing for the two extra engineers, totalling about \$1.05M over three years. It is fast: once hired, the team is at capacity within months. It is also low risk in the sense that you know what you are getting. The downside is that the cost is permanent and recurring, and the team's nodes-per-engineer ratio stays at the manual-tier ceiling of around thirty to fifty, capping how far you can scale without further hires.

The automation path costs roughly \$87K of the existing engineer's time during the build, plus six months of slower fleet expansion while the platform is constructed. After year one, the team can manage 200 nodes with the original headcount, which means the savings flip on. Years two and three save the full \$350K per year of avoided staffing, totalling around \$700K of savings against the \$87K invested. The downside is the build risk: Cluster API rollouts can fail, GitOps adoption can stall, and the engineer doing the build is unavailable for production work during the project.

The right answer depends on three factors beyond cost. First, can you actually hire those two engineers in your market within your timeline, given that bare-metal Kubernetes engineers take three to six months to source? Second, do you have an engineer with the experience to lead the automation build, and do you trust them not to over-engineer it? Third, what is the cost of the slower fleet expansion during the six-month build, in terms of product launches deferred or business opportunities missed? In most cases, automation wins because the per-node staffing cost trajectory is the dominant factor in 5-year TCO, but the decision should be made consciously rather than by default.
</details>

### Question 8
You are presenting an on-prem proposal to the board. A skeptical director asks why your three-year cost projection should be trusted given that "infrastructure projects always overrun." How do you respond, and what mechanisms in your model should you point to?

<details>
<summary>Answer</summary>

**Acknowledge the pattern is real, then point to the specific mechanisms in your model that mitigate it.** The director is correct that infrastructure projects routinely overrun, and disputing that fact loses the room. Instead, point to the specific structural choices that make this proposal different.

First, the budget includes a fifteen to twenty percent CapEx contingency line specifically for first-year surprises such as additional spares, unplanned cabling, and integration consulting. The contingency is not slack, it is an estimate of variance based on industry data, and it is documented as such. Second, the OpEx model includes every category from the full taxonomy, not just the obvious ones. Walk the board through the hidden-costs block of insurance, compliance, training, and opportunity cost, and explain that the historical overrun pattern is driven primarily by these missing categories rather than by hardware mispricing. Third, the model includes sensitivity analysis. Show the base case alongside the utilisation-plus-twenty-percent and cloud-pricing-minus-thirty-percent scenarios, so the board sees the range rather than a single point estimate. Fourth, the model is dated and sourced. Every pricing assumption has a provider, a region, and a date, which means the board can re-run the analysis in six months against actual market conditions rather than wondering whether the numbers are stale.

Finally, commit to a quarterly variance review for the first year. The CFO will appreciate that the engineering team is volunteering for the same financial governance that other major capital projects receive, and the review process catches drift before it becomes a year-end surprise. The combination of contingency, taxonomy completeness, sensitivity analysis, dated sourcing, and governance discipline is what separates a defensible model from optimism dressed in spreadsheet form.
</details>

---

## Hands-On Exercise: Build a Complete TCO Model

**Task**: Create both a 3-year and a 5-year TCO model for your organisation's on-premises Kubernetes deployment and compare them to cloud. The goal is not to get the "right" number on the first pass; it is to build a model whose every line you can defend to a CFO and a skeptical engineering peer.

### Steps

1. **Define your requirements.** Document the number of worker nodes, CPU and RAM per node, persistent and ephemeral storage requirements, GPU requirements if any, the number of clusters, and the number of datacenters or sites. These inputs change every downstream number, so version-control the assumptions block at the top of the spreadsheet.
2. **Calculate CapEx** using the cost taxonomy above. Include compute, networking, storage, and infrastructure. Add a fifteen to twenty percent contingency line and label it as such, because finance partners trust visible contingency far more than they trust optimistic point estimates.
3. **Calculate annual OpEx** including all hidden costs: facility, staffing with on-call compensation, maintenance with the appropriate vendor support tier, software licences, insurance, compliance, and training. Mark the staffing line as "fully loaded" with the multiplier you used.
4. **Calculate the 3-year cloud alternative** using your cloud provider's pricing calculator dated within the prior month. Apply realistic discounts (RI or CUD at 30 to 60 percent depending on commitment), and include data transfer, managed Kubernetes fees, persistent storage, and any extra services your workload depends on.
5. **Extend the model to 5 years** with one row per year and explicit assumptions for maintenance renewals at higher rates after year three, workload growth, storage growth, the resulting power and colo increases, hardware refresh and retirement choices, certified disposal or resale credits, the discount rate for NPV, and any expected staffing change driven by automation gains.
6. **Compare and document** the breakeven point in both the base case and at least two stressed cases such as utilisation plus twenty percent and a 12-month refresh delay. Write a one-paragraph verdict that names the conditions under which on-prem wins, the conditions under which cloud wins, and the sensitivity inputs that flip the answer.

### Success Criteria
- [ ] All CapEx categories populated with quotes dated within the prior 90 days
- [ ] All OpEx categories populated, including the staffing line marked as fully loaded
- [ ] Power calculated with measured (not design) PUE from the chosen colocation provider
- [ ] Cloud comparison uses discounted pricing, not list, with the discount source documented
- [ ] 3-year baseline completed and reviewed by a finance partner
- [ ] 5-year carry-forward completed with separate Year 4 and Year 5 CapEx and OpEx rows
- [ ] Refresh, retirement, and support-renewal assumptions documented in writing
- [ ] Breakeven point identified at year 3 and re-checked at year 5
- [ ] Sensitivity analysis includes utilisation `+20%`, cloud pricing `-30%`, and refresh timing changes
- [ ] One-paragraph verdict written, naming the conditions under which the recommendation flips

---

## Key Takeaways

The on-prem versus cloud question is rarely about hardware cost. Hardware accounts for twenty to thirty percent of the total over three years, and the dominant lines are staffing, facility, and operations. A team that argues the case on hardware alone is missing the part of the iceberg that determines the answer, and CFOs have learned to distrust those arguments because they have been burned by them. PUE multiplies your power bill by twenty to sixty percent depending on facility quality, and you should always insist on measured PUE rather than design PUE before signing a colocation contract. A 5-year model is not a longer spreadsheet, it is a different conversation: refresh cycles, maintenance drift, and growth assumptions all change the answer in ways the 3-year model hides. Automation determines your staffing ratio more than any other single factor, and investing in Cluster API and GitOps early pays back in years two through five with margins that dwarf the build cost. Breakeven against cloud typically lands at 150 to 250 nodes for a typical mid-market organisation, and below that band cloud wins on both cost and simplicity. Always get three quotes for colocation, hardware, and support contracts, and never accept the first offer, because vendors expect negotiation and price the first quote accordingly.

---

## Next Module

Continue to [Module 1.5: On-Prem FinOps & Chargeback](../module-1.5-onprem-finops-chargeback/) to turn the multi-year TCO model you just built into ongoing resource tracking, internal billing, and chargeback rates.

## Sources

- [iso.org: 30134 2](https://www.iso.org/standard/30134-2) — ISO/IEC 30134-2 is the authoritative standard defining PUE.
- [docs.aws.amazon.com: ec2 reserved instances.html](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-reserved-instances.html) — AWS documentation explicitly states one-year and three-year RI commitments.
- [NIST Handbook 135e2025: Life-Cycle Costing Manual](https://nvlpubs.nist.gov/nistpubs/hb/2025/NIST.HB.135e2025.pdf) — Authoritative reference for present-value life-cycle costing, NPV, and sensitivity analysis.
- [Amazon EKS Pricing](https://aws.amazon.com/eks/pricing/) — Useful for checking managed-cluster fees and which AWS resource charges sit outside the EKS control-plane fee.
