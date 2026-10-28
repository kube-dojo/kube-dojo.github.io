#!/usr/bin/env python3
"""Deterministic curriculum-wide audit of repeated incident/anecdote use.

Scans every module .md file in scope and counts files (not occurrences) that
mention each tracked incident. Outputs a markdown table sorted by file count,
plus per-incident file lists with a short framing snippet.

Scope:
  src/content/docs/**/*.md
  EXCLUDING: uk/, ai-history/, ai-ml-engineering/history/, index.md files

Usage:
  python3 scripts/audit_incident_reuse.py [--out PATH]

The keyword catalog below is the single source of truth for what counts as
"the same incident." Each incident is matched if ANY of its key phrases
appear (case-insensitive). Phrases are tuned to avoid false positives —
e.g. "Tesla" alone is too broad (matches Nikola Tesla in physics modules),
so we require "Tesla" + a 2018-cryptojacking signal.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCOPE = REPO / "src" / "content" / "docs"
EXCLUDE_DIRS = ("/uk/", "/ai-history/", "/ai-ml-engineering/history/")

# Each incident: a label + a list of regex patterns. A file "contains" the
# incident if ANY of its patterns matches. Patterns are case-insensitive.
# Use phrase-pairs (entity + signal) to avoid name collisions.
INCIDENTS: dict[str, list[str]] = {
    "Knight Capital 2012": [
        r"Knight Capital",
        r"\$4[46]0\s*million.{0,40}45\s*minutes",
    ],
    "Tesla 2018 cryptojacking": [
        # Require Tesla within 800 chars of an unambiguous incident signal.
        # `nvidia-tesla-t4` (GPU model) is filtered: it doesn't co-occur with these signals.
        # Variants of cryptojacking phrasing: cryptojacking, cryptomining, crypto-mining,
        # cryptocurrency mining, mining cryptocurrency, mine cryptocurrency, Monero, xmrig.
        r"Tesla[^a-zA-Z0-9].{0,800}(crypto[\s\-]?(jack|min|miner)|(mining|mine)\s+(cryptocurrency|crypto)|(cryptocurrency|crypto)\s+(mining|miner)|monero|xmrig|redlock|exposed (\w+\s+){0,3}(dashboard|console|admin|infrastructure)|2018.{0,80}(breach|compromise|incident|attack))",
        r"(crypto[\s\-]?(jack|min|miner)|(mining|mine)\s+(cryptocurrency|crypto)|(cryptocurrency|crypto)\s+(mining|miner)|monero|xmrig|redlock).{0,800}Tesla[^a-zA-Z0-9]",
    ],
    "Uber 2022 hardcoded credentials": [
        # Critical: \bUber\b — without word boundary "Uber" matches inside "kUBERnetes".
        # Reverse pattern carries the SAME signal list as the forward pattern (Gemini review on
        # PR #879 caught that "Lapsus breached Uber" or "MFA fatigue used against Uber" would
        # have evaded detection in the original reverse-only-on-hardcoded form).
        r"\bUber\b.{0,400}(hardcoded|hard-coded|admin password|network share|PowerShell|Thycotic|MFA fatigue|2022.{0,40}breach|Lapsus)",
        r"(hardcoded|hard-coded|admin password|network share|PowerShell|Thycotic|MFA fatigue|Lapsus).{0,400}\bUber\b",
    ],
    "Capital One 2019 breach": [
        r"Capital One.{0,200}(2019|WAF|SSRF|metadata|106 million|100 million)",
    ],
    "SolarWinds 2020": [
        # Tightened: bare "SolarWinds" matches modules that mention SolarWinds as a vendor in
        # passing (e.g. as a comparison example, "tools like SolarWinds and Datadog"). Require an
        # incident-specific signal.
        r"SolarWinds.{0,200}(2020|Orion|supply chain|breach|compromise|Sunburst|backdoor|FireEye)",
        r"(Orion|Sunburst|supply chain.{0,40}attack).{0,200}SolarWinds",
    ],
    "Codecov 2021 bash uploader": [
        # Tightened: bare "Codecov" matches modules that reference Codecov as a tool ("upload
        # coverage to Codecov"). Require an incident-specific signal.
        r"Codecov.{0,200}(2021|bash uploader|breach|supply chain|compromise|environment variables|exfiltrat)",
        r"(bash uploader|exfiltrat.{0,40}environment variables).{0,200}Codecov",
    ],
    "Log4Shell / CVE-2021-44228": [
        r"Log4Shell",
        r"CVE-2021-44228",
        r"log4j.{0,40}(vuln|RCE|2021)",
    ],
    "Equifax 2017 breach": [
        r"Equifax",
        r"143\s*million.{0,40}(records|people|consumers)",
        r"147\s*million.{0,40}(records|people|consumers)",
    ],
    "Heartbleed CVE-2014-0160": [
        r"Heartbleed",
        r"CVE-2014-0160",
    ],
    "Maersk NotPetya 2017": [
        r"NotPetya",
        r"Maersk.{0,200}(ransomware|wiper|2017|NotPetya)",
    ],
    "WannaCry 2017": [
        r"WannaCry",
    ],
    "GitLab 2017 db1 incident": [
        # Tightened 2026-05-04: require a specific GitLab-2017-incident signal, not just GitLab + a
        # generic word like "backup". Without this, passing references like "push to GitHub or GitLab,
        # then verify backups" trigger false positives.
        r"GitLab.{0,400}(2017|db1|rm[\s\-]rf|January 31|postmortem of database outage|database outage|production data loss|streamed live|fatigued.{0,40}admin|replication lag)",
        r"(rm[\s\-]rf|backup failed|replication lag|fatigued.{0,40}admin|database outage).{0,400}GitLab",
    ],
    "Cloudflare 2019 regex outage": [
        # Tightened 2026-05-04 (sweep #4 review): bare "2019" / "July" signals matched
        # Verizon BGP leak narratives that mention Cloudflare as one of the affected
        # services. Require a regex/backtracking/date signal unique to the July 2019 incident.
        # Tightened again 2026-06-12 (#1897 networking wave): dropped the
        # "WAF.{0,40}(rule|outage|deployed)" signal — it was NOT unique to the incident and
        # false-matched WAF vendor-comparison Rosetta tables (a WAF module naming Cloudflare
        # near "WAF rules"). The regex / catastrophic-backtrack / "July 2 2019" signals are the
        # genuinely unique ones; the canonical narration carries them.
        r"Cloudflare.{0,200}(regex|catastrophic backtrack|July 2,?\s*2019|July 2019)",
        r"(regex|catastrophic backtrack).{0,200}Cloudflare",
    ],
    "Cloudflare 2020 BGP / config": [
        # Tightened 2026-05-04 (sweep #4 review): bare "BGP" / "2020" / Cloudflare matched
        # Facebook-2021-BGP citations and other unrelated Cloudflare-as-vendor mentions.
        # Require an explicit Cloudflare-2020-BGP signal (year+BGP together, configuration push,
        # backbone announcement, or July 17 2020 date).
        r"Cloudflare.{0,200}(2020.{0,40}BGP|BGP.{0,40}2020|configuration push|July 17,?\s*2020|July 2020.{0,40}BGP|backbone announcement)",
    ],
    "Facebook 2021 BGP outage": [
        # Require Facebook + outage-specific phrasing (not just "Facebook" + "BGP" — too many
        # false positives in MetalLB/Cilium context). Word boundaries on "Meta" (matches inside
        # "metadata") and on "locked out" (matches inside "blocked outbound") — both surfaced by
        # the kcsa/4.5 false positive 2026-05-04.
        r"(Facebook|\bMeta\b).{0,400}(October 2021|2021.{0,40}outage|disappeared from the internet|disconnected.{0,40}data center|six[\s\-]hour outage|\blocked out\b)",
        r"(October 2021|disappeared from the internet|six[\s\-]hour outage|\blocked out\b).{0,400}(Facebook|\bMeta\b)",
    ],
    "AWS S3 us-east-1 2017": [
        r"AWS.{0,80}S3.{0,80}us-east-1",
        r"S3.{0,80}us-east-1.{0,80}(2017|outage)",
    ],
    "CrowdStrike 2024 Falcon outage": [
        r"CrowdStrike.{0,200}(Falcon|2024|July 19|kernel|BSOD|sensor)",
    ],
    "Slack outage": [
        # Tightened: must explicitly reference Slack THE PRODUCT going down, not "notified the team via Slack".
        r"Slack.{0,80}(was down|was unavailable|outage in (January|February) 202[12]|January 4, 2021)",
        r"(was down|was unavailable).{0,80}Slack",
    ],
    "Robinhood / GameStop": [
        r"Robinhood.{0,80}(GameStop|outage|2021|halt)",
    ],
    "TeamTNT cryptojacking": [
        r"TeamTNT",
    ],
    "Kinsing cryptojacking": [
        r"Kinsing",
    ],
    "Sony PSN 2011": [
        r"Sony.{0,80}(PSN|PlayStation Network|2011)",
    ],
    "Code Spaces 2014": [
        r"Code Spaces",
    ],
    "Target 2013 breach": [
        # Tightened 2026-05-04 (sweep #4 review): bare "breach" alternative matched any
        # SLA/SLO content about "internal target ... breaches" since "target" lowercase is
        # a generic word for a goal/metric. Require Target-Corp-2013-specific signals:
        # HVAC vendor, Fazio, 40 million cards, or year+incident verb.
        r"Target.{0,200}(HVAC|40 million.{0,40}(card|customer)|Fazio|2013.{0,40}(breach|hack|attack|stolen)|stolen.{0,40}credit cards)",
    ],
    "ChaosDB 2021": [
        r"ChaosDB",
        r"CosmosDB.{0,80}(Jupyter|metadata|2021|Wiz)",
    ],
    "Argo CD path-traversal CVE-2022-24348": [
        r"CVE-2022-24348",
        # Tightened 2026-06-02 (session 94, CAPA prep): the bare "2022"/"CVE" alternatives
        # false-positived on benign "Argo CD ... graduated 2022" prose (CGOA 1.3/1.5 tripped
        # CI dedup). The literal CVE is already caught above; the only incident-specific
        # fingerprint left is the path-traversal flaw itself.
        r"Argo CD.{0,80}path[- ]?traversal",
    ],
    "3CX 2023 supply chain": [
        # Tightened: 3CX is a product name; bare match risks future tutorial / comparison content.
        r"3CX.{0,200}(2023|supply chain|breach|North Korea|Lazarus|Smooth Operator)",
        r"(supply chain.{0,40}attack|Smooth Operator|North Korea).{0,200}3CX",
    ],
    "MOVEit 2023": [
        # Tightened: MOVEit is a Progress product; bare match flags any module discussing the tool.
        r"MOVEit.{0,200}(2023|breach|Cl0p|exploit|CVE-2023|Progress)",
        r"(Cl0p|CVE-2023-34362).{0,200}MOVEit",
    ],
    "Spring4Shell CVE-2022-22965": [
        r"Spring4Shell",
        r"CVE-2022-22965",
    ],
    "Microsoft 38TB SAS-token leak 2023": [
        r"38\s*TB.{0,80}(SAS|leak)",
        r"Microsoft AI.{0,80}(SAS|2023|leak)",
    ],
    "Toyota 2022 / 2023 GitHub leak": [
        r"Toyota.{0,200}(GitHub|2022|2023|leaked|exposed)",
    ],
    "Mercedes-Benz 2024 GitHub token": [
        r"Mercedes.{0,80}(GitHub|token|2024)",
    ],
    "Netflix Chaos Monkey": [
        r"Chaos Monkey",
    ],
    "Spotify squad model": [
        r"Spotify.{0,80}(squad|tribe|chapter|guild)",
    ],
    "Amazon two-pizza teams": [
        r"two[\s\-]pizza",
    ],
    "Knight Capital generic 'deploy to N of M' trope": [
        r"\b(7|seven) of (8|eight)\s*servers",
    ],
    "Holiday / Black Friday outage trope": [
        # Tightened 2026-05-04: require a fabricated-shape incident — Black Friday + outage + invented
        # dollar figure. Generic pedagogical mentions ("Black Friday traffic spike", "consider a Black
        # Friday checkout scenario") are NOT flagged. Only "company X lost $Y million during
        # Black Friday" patterns are caught — those are the actual no-bullshit-bar violations.
        r"Black Friday.{0,300}(outage|incident|disaster|downtime).{0,200}\$[\d.,]+\s*(million|M\b)",
        r"\$[\d.,]+\s*(million|M\b).{0,200}Black Friday.{0,80}(outage|incident|disaster|downtime)",
        r"holiday.{0,40}(sale|launch).{0,200}(outage|incident|broke|crashed).{0,200}\$[\d.,]+\s*(million|M\b)",
    ],
    "Ericsson 2018 certificate expiration": [
        r"Ericsson.{0,200}(certificate|expired|expir|2018)",
        r"(O2|SoftBank).{0,200}(certificate|expir).{0,200}(2018|December)",
    ],
    "GitHub October 2018 split-brain": [
        r"GitHub.{0,400}(October 21,\s*2018|optical (hardware|cable)|43[\s\-]second|split[\s\-]brain|US-East.{0,40}(database|primary|hub)|webhook payloads?\s*(were\s*)?(permanently\s*)?dropped)",
        r"(October 21,\s*2018|43[\s\-]second|split[\s\-]brain|optical (hardware|cable)|webhook payloads?\s*(were\s*)?(permanently\s*)?dropped).{0,400}GitHub",
    ],
    "Atlassian April 2022 data deletion": [
        r"Atlassian.{0,400}(April 2022|April 5,?\s*2022|delete[\s\-]site|delete script|775 customers|14 days|cloud data deletion)",
        r"(delete[\s\-]site|delete script|775 customers|14 days).{0,200}Atlassian",
    ],
    "Cloudflare BGP June 2022 policy reorder": [
        r"Cloudflare.{0,400}(June 2022|June 21,?\s*2022|policy reorder|REJECT[\s\-]THE[\s\-]REST|nineteen data centers|19 data centers|75 minutes)",
        r"(REJECT[\s\-]THE[\s\-]REST|policy reorder).{0,400}Cloudflare",
    ],
    "GitHub August 2021 MySQL degradation": [
        r"GitHub.{0,400}(August 2021|August 10,?\s*2021|MySQL primary|77[\s\-]minute|seventy[\s\-]seven minute|service discovery misconfiguration|dashboards.{0,40}same.{0,40}database)",
        r"(MySQL primary|dashboards.{0,40}down too).{0,200}GitHub",
    ],
    "Siloscape 2021 Windows container escape": [
        # Distinctive malware name — bare match is safe (no other product/CVE shares the name).
        r"\bSiloscape\b",
    ],
    "XZ Utils backdoor CVE-2024-3094": [
        # Distinctive name + CVE; allow either signal. liblzma alone is too generic (compression
        # library mentions in unrelated tutorials), so require backdoor/CVE context.
        r"\bXZ Utils\b",
        r"CVE-2024-3094",
        r"liblzma.{0,80}(backdoor|CVE-2024-3094)",
        r"(backdoor|obfuscated).{0,80}liblzma",
    ],
    "Fictional / fabricated incident names": [
        # User: "you cannot fool a human" — these are made-up company names with manufactured stats.
        # Enumerate known fabricated names from the explore-agent sample. Add more as discovered.
        r"GlobalTradeX",
        r"GlobalPay\b",
        r"GlobalBank\b",
        r"AcmeCorp",
        r"AcmeCo\b",
        r"FintechCo\b",
        r"PayCorp\b",
        r"ShopWell\b",
        r"FastShop\b",
    ],
    "Templated 'fintech + Black Friday + $X.X million' trope": [
        # Structural reuse of made-up incident: payment/fintech company + holiday + dollar-figure loss.
        # Two-step match: needs all of [payment|fintech|e-commerce|checkout] + [Black Friday|Cyber Monday|holiday] + [$N.N million|$N million].
        r"(payment|fintech|e-?commerce|checkout|retailer).{0,400}(Black Friday|Cyber Monday|holiday).{0,400}\$[\d.]+\s*million",
        r"(Black Friday|Cyber Monday).{0,400}(payment|fintech|e-?commerce|checkout|retailer).{0,400}\$[\d.]+\s*million",
    ],
}


def in_scope(p: Path) -> bool:
    s = str(p)
    if any(d in s for d in EXCLUDE_DIRS):
        return False
    return p.name != "index.md"


def scan() -> tuple[dict[str, list[tuple[Path, str]]], list[Path]]:
    files = sorted(p for p in SCOPE.rglob("*.md") if in_scope(p))
    hits: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for incident, patterns in INCIDENTS.items():
            for pat in patterns:
                m = re.search(pat, text, flags=re.IGNORECASE | re.DOTALL)
                if m:
                    start = max(0, m.start() - 30)
                    end = min(len(text), m.end() + 30)
                    snippet = re.sub(r"\s+", " ", text[start:end]).strip()
                    if len(snippet) > 140:
                        snippet = snippet[:137] + "..."
                    hits[incident].append((path, snippet))
                    break
    return hits, files


def relpath(p: Path) -> str:
    return str(p.relative_to(REPO))


def render_markdown(hits: dict[str, list[tuple[Path, str]]], total: int) -> str:
    incidents_sorted = sorted(
        hits.items(),
        key=lambda kv: (-len(kv[1]), kv[0]),
    )
    lines = []
    lines.append("# Curriculum-wide incident-reuse audit")
    lines.append("")
    lines.append(
        f"Generated by `scripts/audit_incident_reuse.py` over {total} module files in scope."
    )
    lines.append("")
    lines.append(
        "Scope: `src/content/docs/**/*.md`, excluding `uk/`, `ai-history/`, `ai-ml-engineering/history/`, and `index.md` files."
    )
    lines.append("")
    lines.append("## Summary table")
    lines.append("")
    lines.append("| Incident | Files |")
    lines.append("|---|---|")
    for incident, occurrences in incidents_sorted:
        if not occurrences:
            continue
        lines.append(f"| {incident} | {len(occurrences)} |")
    lines.append("")
    lines.append(
        "Hard rule (per user, 2026-05-04): each named incident may appear in at most ONE module. Anything above 1 in the table needs de-duplication."
    )
    lines.append("")
    lines.append("## Per-incident file lists")
    lines.append("")
    for incident, occurrences in incidents_sorted:
        if not occurrences:
            continue
        lines.append(f"### {incident}")
        lines.append("")
        lines.append(f"**Files: {len(occurrences)}**")
        lines.append("")
        for path, snippet in occurrences:
            lines.append(f"- `{relpath(path)}` — _{snippet}_")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO / "docs" / "audits" / "2026-05-04-incident-reuse.md",
    )
    args = ap.parse_args()

    hits, files = scan()
    md = render_markdown(hits, total=len(files))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    print(
        f"wrote {args.out} ({len(files)} files scanned, {sum(1 for v in hits.values() if v)} incidents matched)"
    )
    print()
    print("Top 10 by file count:")
    for incident, occurrences in sorted(hits.items(), key=lambda kv: -len(kv[1]))[:10]:
        if occurrences:
            print(f"  {len(occurrences):3d}  {incident}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
