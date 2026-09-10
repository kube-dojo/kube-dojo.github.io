# Remaining complexity-module claims — #2403

Research-only remaining-claim map for
`src/content/docs/platform/foundations/systems-thinking/module-1.4-complexity-and-emergent-behavior.md`
at `65a909fbd82f473498a6e581623d6b0344ef0606` (2026-09-10). Line numbers are from that
revision. This packet does not reopen accepted opener, weather, Cynefin-table,
Cook §3.1, resilience §4.2–4.3, observability/§4.5, robustness, checkout-Q5, quiz,
Part B, or lab packets. No chaos experiment was executed. Published module prose
is unchanged.

## Already-accepted packets (do not reopen)

| Cluster | Research note | Accepted prose |
|---|---|---|
| Opener | `2015-outage-opener.md` (#2381) | Merged opener revision |
| Weather | `complexity-weather-predictability.md` | #2408 |
| Cynefin tables/domains | `cynefin-domain-evidence.md` | #2410 |
| Cook §3.1 (principles 1–8 + Reason) | `cook-layered-defenses-evidence.md` | #2412 |
| Resilience/chaos §4.2–4.3 | `resilience-chaos-evidence.md` | #2414 |
| Edge-of-chaos objective / §4.5 | `observability-without-edge-of-chaos.md` | #2420 |
| Lab Part A | `complexity-lab-evidence.md` (#2438) | #2445 |

## Inspected sources and access

- Richard I. Cook, *How Complex Systems Fail*, Revision D: public HTML at
  https://how.complexsystems.fail/ (principles 8–18 read in full) and
  https://www.adaptivecapacitylabs.com/HowComplexSystemsFail.pdf (35,566 bytes;
  SHA-256 `7e3f303c2e2a7bca1707bc64e832b1adbb4f116b75e770b962ac4f48ff4aea57`;
  `/Count 5`). Same artifact as #2411. Body evidence is extracted text.
- Sidney Dekker, “Why we need new accident models” (2004), extracted from
  https://www.humanfactors.lth.se/fileadmin/lusa/Sidney_Dekker/articles/2004/New_Accident_Models2.pdf
  on 2026-09-10. Later direct download returned HTTP 404; no local bytes or hash.
  Inspected Introduction and the incrementalism discussion. Aerospace case study.
- Dekker, *Drift into Failure* (CRC/Ashgate 2011) publisher preview at
  https://api.pageplace.de/preview/DT0400.9781351942928_A34376077/preview-9781351942928_A34376077.pdf:
  title verso, contents, and preface pages xi–xiii only. Not a full-book inspection.
  The Routledge product page in the module Sources list is bibliographic only.
- Hollnagel, Wears and Braithwaite, *From Safety-I to Safety-II: A White Paper*
  (Resilient Health Care Net, 2015), NHS-hosted copy
  https://www.england.nhs.uk/signuptosafety/wp-content/uploads/sites/16/2015/10/safety-1-safety-2-whte-papr.pdf
  (2,003,126 bytes; SHA-256 `e2b4bf416ddbe149f0c360c23bf730e67718c4b9fdeef8ccf4e672abfab7e3dd`).
  Executive summary inspected via text extraction. Health-care framing; not a
  platform-operations study. https://www.hollnagel.com/safety-ii redirected to a
  lander and is not accepted body evidence.
- U.S.-Canada Power System Outage Task Force, *Final Report on the August 14, 2003
  Blackout* (April 2004), DOE copy
  https://www.energy.gov/sites/default/files/oeprod/DocumentsandMedia/BlackoutFinal-Web.pdf
  (7,012,212 bytes; SHA-256 `118b854a588297c019afc917cddf1c7406be0ce3fdcc3eed412dcea2e51c7397`).
  Inspected Chapter 1 opening (estimated 50 million people), Chapter 3 Group 3
  (vegetation), and Chapter 5 opening (alarm loss after 14:14 EDT; tree contacts
  after 15:05 EDT). Text extraction only; Wikipedia is not a substitute.
- Dave Snowden, “Search for Cynefin equivalents (and its history),” 26 December 2006,
  https://thecynefin.co/search-for-cynefin-equivalents-and-its-history/. Public HTML.
  Quotes his 2000 definition. Later Welsh-curriculum uses are out of scope.
- Stanford Encyclopedia of Philosophy, “Emergent Properties,”
  https://plato.stanford.edu/entries/properties-emergent/. Inspected the British
  Emergentists paragraph and Lewes 1875 bibliography entry. *Problems of Life and
  Mind* vol. 2 was not opened.
- University of Chicago Biological Sciences Division, “Richard I. Cook, MD,
  1953–2022,” 20 September 2022,
  https://biologicalsciences.uchicago.edu/news/richard-cook-obituary/. Institutional
  obituary; not a surgical-team study.

## Remaining claim map

| Module span | Claim | Source class / limit | Disposition |
|---|---|---|---|
| LO1 L20 | Complicated systems are “predictable, decomposable” | Conflicts with accepted 2003 Cynefin packet (knowable ≠ universally predictable) | **Qualify** the objective to match the revised tables. |
| §1.5 L140–142 | 2003 blackout: tens of millions; alarm bug “for years”; vegetation, timing, handoffs; “Swiss Cheese in the wild” | Task Force report supports population scale, that-day alarm failure, and tree contact. “Existed for years” was not in the inspected spans. Reason analogy is author application. Wikipedia is not a primary. | **Rewrite** with the Task Force report. **Remove** the unsourced multi-year bug claim. **Label** the Reason analogy. |
| §3.2 L305–330 | Complex failures “rarely” have a single root cause; muted-alert / peak-timing story as fact | Cook principle 7 rejects isolated root cause; the vignette is unsourced | **Retain** the Cook objection. **Label** the vignette hypothetical. |
| §3.3 L332–356 | Dekker: systems “don’t fail suddenly”; “locally rational” decisions; tech table | 2004 paper: slow incremental drift; decisions that “seemed like perfectly acceptable ideas at the time.” 2011 preface (preview): gradual incremental decline. Exact phrase “locally rational” not in those spans. Tech table is author-built. | **Retain** attributed drift. **Qualify** “locally rational” as a teaching paraphrase. **Label** the table. Do not import the 2011 “no organization is exempt / inevitable by-product” wording as a platform law. |
| §3.4 L359–369 | Cook 8–18 paraphrases; K8s controller example; P17 “most of the time”; P18 game days; “four questions consistently produce” improvements | HTML/PDF principles 8–18 match the named headings. Controllers, game days, and the improvement guarantee are not in those principles. P17 says adaptations are “for the most part, part of normal operations,” not a measured failure-free rate. | **Retain** attributed 8–18. **Label** platform examples. **Qualify** P17 frequency. **Rewrite** P18 without naming game days as Cook’s. **Remove** the improvement guarantee. |
| L384 | “Together, they erode safety margins until failure is inevitable” | Leftover absolute; 2011 preface uses “inevitable” for organizational by-products, not this sentence | **Remove** or attach a scoped Dekker paraphrase in a later prose PR. |
| Further reading L724 | “Cook’s three-page essay” | Same 5-page PDF already rejected as “three pages” in #2411 | **Remove** the page-count claim. |
| Did You Know L491 | Cynefin = habitat/place plus factors “we can never fully understand” | Snowden 2006: noun “habitat,” no direct English equivalent; dictionary gloss is insufficient; community/history and uncertainty appear in his longer gloss | **Qualify**. Do not treat “never fully understand” as the dictionary meaning. |
| Did You Know L489 | Lewes coined “emergence” in 1875 from water’s wetness | SEP: Lewes (1875) first used “emergence” for the philosophical position. Water/wetness is not in the inspected SEP span and the 1875 volume was not read | **Qualify** the coinage. **Remove** or unsourced-label the water anecdote. |
| Did You Know L495 | Cook was an anesthesiologist who “studied how surgical teams avoid killing patients”; insights “apply directly” | Treatise byline is MD / patient safety. UChicago obituary: physician, anesthesiologist, medical accidents. Not a named surgical-team study | **Retain** physician/anesthesiologist. **Qualify** the study description and the “apply directly” transfer. |
| Did You Know L493 | Traffic jams prove the same mechanism as cascading failures | No source inspected | **Label** a limited analogy or **remove** the equivalence. |
| §4.3 L441–450 | Named chaos tools test the listed properties | #2413 already declined to validate this table. No tool run here | **Qualify** as an author tool list, not measured capabilities. |
| §4.4 L452–456 | Safety-I vs Safety-II; Resilience engineering *is* Safety-II | 2015 executive summary: Safety-I = as few things as possible go wrong; Safety-II = as many things as possible go right; combine both. Module URL is dead | **Retain** the contrast with that paper. **Qualify** the synonym. **Replace** the dead URL. |
| §4.6 L475–479 | Game days with product/support/leadership “often teach more” | Author social claim; not in Chaos Principles or the Safety-II summary | **Qualify** as operational suggestion, not a measured outcome. |
| §4.7 L481–483 | Heading “Edge-of-Chaos Checklist” after §4.5 dropped that regime | Leftover title; #2417/#2420 already removed the unsupported population claim | **Rewrite** the heading in a later prose PR. Checklist body is author synthesis. |
| Sources L717–720 | BBC “independent infrastructure failure”; Wikipedia blackout; dead Safety-II URL | Contradicts accepted opener packet; Wikipedia is secondary; URL failed | **Rewrite** the source list to match accepted/this packet. |

## Deferred to later prose PRs

Independent source acceptance of this note precedes any published rewrite. Split later
prose so each PR stays within 200 aggregate lines. Likely slices: (1) Cook §3.4 +
Further Reading page-count + Did You Know Cook; (2) Dekker §3.3 + leftover L384;
(3) blackout §1.5 + Sources; (4) Safety-II URL/synonym + leftover edge-of-chaos
heading + Did You Know etymology/Lewes/traffic. Do not invent replacement incidents,
dialogue, or outcomes. Do not expand the Kubernetes lab. Ukrainian parity stays with
#2291/#1911. This research merge does not close #2403 or accept the foundations track.
