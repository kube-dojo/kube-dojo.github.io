# Open Questions: Chapter 3 — The Physical Bridge

Surfaced from `brief.md` *Conflict Notes* and the Yellow/Red entries in `sources.md`. Each question identifies the specific evidence needed to resolve it. Drafting cannot rely on any open-question item until its evidence is in hand.

## Resolution Required Before Drafting

### Q1. Did Shannon read Nakashima before submitting the thesis?

- **Question:** Is there any documented evidence that Shannon read Nakashima's 1936 English-language summary in *Nippon Electrical Communication Engineering* (No. 3, May 1936, pp. 197-226) before submitting his thesis on August 10, 1937?
- **Why it matters:** The chapter's stance per `brief.md` is independent simultaneous discovery. If a documented path showed Shannon had access to Nakashima's English summary (e.g., MIT library acquisition records, Bell Labs library acquisition records, or a citation in any Shannon working paper between 1936 and 1937), the framing must shift. Currently no such path is documented; the parsimonious reading is that Shannon did not read Nakashima before 1937.
- **Evidence needed:** MIT Institute Archives — engineering library acquisition records 1936-1937; Vannevar Bush Papers, Library of Congress — internal reading lists or correspondence about Japanese engineering literature; Bell Labs library acquisition records (Shannon was at Bell Labs in summers and would join in 1941). Also: any handwritten or typewritten Shannon draft from 1936-1937 that lists Japanese sources.
- **Status:** Yellow. The negative claim ("Shannon did not read Nakashima before 1937") is inherently hard to verify; the chapter should phrase it as "the documented record does not place Nakashima's work in Shannon's 1937 reading" rather than as an absolute.

### Q2. Howard Gardner's exact phrasing and page

- **Question:** What is the exact passage in Howard Gardner's *The Mind's New Science* (1985) where he calls Shannon's thesis "possibly the most important, and also the most famous, master's thesis of the century"? What page?
- **Why it matters:** The phrase circulates widely in popularizations, often without the qualifier "possibly." If the chapter quotes it, the quotation must be exact and page-anchored.
- **Evidence needed:** Gardner 1985 *The Mind's New Science* — physical or e-book access. Standard library or interlibrary loan.
- **Status:** Yellow. Non-blocking if the chapter chooses to skip the superlative claim and rely on the thesis's own technical content for the framing.

### Q3. Shannon's day-to-day MIT work in 1936-1937

- **Question:** What was Shannon's specific day-to-day role as a research assistant in the MIT Department of Electrical Engineering during the 1936-1937 academic year? What setup-problem tasks did Bush actually assign him?
- **Why it matters:** Scene 1's framing — that the analyzer setup-problem motivated the thesis — is plausible from secondary biographies but currently anchored only via the Shannon 1938 byline footnote (which establishes employment but not specific tasks).
- **Evidence needed:** MIT Institute Archives — Bush, Caldwell, Shannon files; Vannevar Bush Papers, Library of Congress — Shannon-related correspondence; Soni & Goodman 2017 *A Mind at Play* page anchors for Shannon's MIT period.
- **Status:** Yellow. Soni & Goodman 2017 should be acquired before prose drafting. Other archives are physical-access blocked.

### Q4. The Rockefeller grant's exact disbursement schedule and conditions

- **Question:** What was the actual disbursement schedule of the March 1936 $85,000 grant? Were there reporting requirements? Did Rockefeller review the analyzer's progress?
- **Why it matters:** The infrastructure-thesis works partly because the grant was sustained enough that Bush could plan a multi-year engineering program. Verifying that this is what actually happened (vs. assumed) tightens the claim.
- **Evidence needed:** Rockefeller Foundation archival records (RF1.1/224/2/23 et seq.), Rockefeller Archive Center, Sleepy Hollow NY.
- **Status:** Red. Will likely require physical archive access or correspondence with RAC archivists.

## Lower-Priority Questions (Do Not Block Drafting)

### Q5. Bush as Shannon's mentor

- **Question:** What was the specific mentoring relationship between Bush and Shannon in 1936-1937? Did Bush suggest the relay-network problem? Did Shannon find it independently?
- **Why it matters:** Tightens Scene 1's biographical depth. Currently the chapter says only "Shannon arrived at MIT during the period when..." — a Soni & Goodman page anchor or a Hagley/MIT correspondence document would let the chapter make a sharper claim.
- **Evidence needed:** Soni & Goodman 2017 *A Mind at Play*; Vannevar Bush Papers, Library of Congress.
- **Status:** Yellow. Non-blocking.

### Q6. Hitchcock's role beyond the formal advisor designation

- **Question:** What did F. L. Hitchcock specifically contribute to the thesis as supervisor? Was he a hands-off administrative advisor or a substantively engaged mathematical mentor?
- **Why it matters:** The chapter currently cites Hitchcock only as the supervisor of record. If Hitchcock substantively shaped the thesis's mathematical approach (e.g., the perfect-induction proof method), that's worth a sentence. If he was purely administrative, that's also worth noting briefly to avoid misleading readers.
- **Evidence needed:** Soni & Goodman 2017 (likely covers this); MIT Institute Archives.
- **Status:** Yellow. Non-blocking.

### Q7. Nakashima's reception in the West before 1949

- **Question:** Did any Western researcher cite Nakashima's English-language *Nippon Electrical Communication Engineering* summaries before Shannon's 1949 *BSTJ* paper?
- **Why it matters:** The Piesch (1939) and Plechl-Duschek (1946) papers cite Nakashima per TICSP-40 references [14] and [15]. Whether any English-language Western work cited Nakashima before 1949 is unclear; the chapter currently treats Shannon's 1949 paper as the first Western citation, which is true *for Shannon* but not necessarily *for the West as a whole*.
- **Evidence needed:** TICSP-40 reprint excerpts (already accessed) for the Piesch and Plechl-Duschek citations of Nakashima; AIEE Transactions 1937-1948 for any additional Western citations.
- **Status:** Yellow. The chapter should phrase the 1949 claim narrowly as "Shannon's first major citation of Nakashima's work" rather than as "the first Western citation."

### Q8. The "5 relays to 3" folk claim's origin

- **Question:** Where does the "Shannon proved a 5-relay circuit could be minimized to 3" folk claim come from? It appears in the legacy chapter prose at `src/content/docs/ai-history/ch-03-the-physical-bridge.md`, but it does not match the primary source.
- **Why it matters:** Tracking the folk claim's origin would help the chapter explain (briefly) why it's wrong without making the explanation read as a takedown of any specific source.
- **Evidence needed:** Search of popular Shannon biographies and anniversary articles — *IEEE Spectrum* 2016 centennial coverage, *Wired* and *New Yorker* profiles of Shannon, Soni & Goodman 2017.
- **Status:** Yellow. Non-blocking. Present the correct numbers (13 → 6 contact occurrences; not a physical-relay count). See `claim-ledger-2339.md` row 1.

### Q9. The "tertiary parallel discovery" thread

- **Question:** Were there any other 1930s researchers besides Shannon, Nakashima, Piesch, and Plechl-Duschek who approached relay-network algebra independently?
- **Why it matters:** Useful context for how widespread the insight was. TICSP-40 mentions [21] Yamada's claim that Akira Nakashima published the first paper on switching theory in the world; the question is whether that's strictly true or whether other 1930s candidates exist.
- **Evidence needed:** TICSP-40 references [3] Goto 1949, [16] Sasao 1999 Appendix A; Yamada 2004 *IEEJ Trans. FM*; broader histories of computing (Williams 1985, Aspray 1990, Ceruzzi 1998).
- **Status:** Yellow. Non-blocking. The chapter's three-name parallel-discovery framing (Shannon, Nakashima, Piesch / Plechl-Duschek) is the standard one.

## Notes on resolution sequence

The order of attempted resolution:

1. ✅ **Done (Claude anchor-hunt 2026-04-28):** Shannon 1937 thesis (MIT DSpace) — 14 Green claims promoted.
2. ✅ **Done (Claude anchor-hunt 2026-04-28):** Shannon 1938 *Trans. AIEE* paper (Wiley 1993 reissue) — 8 Green claims promoted; pp.713-723 endpoints anchored via ADS + Wikipedia.
3. ✅ **Done (Claude anchor-hunt 2026-04-28):** Stanković & Astola 2008 (TICSP Report 40) — 6 Green claims promoted on Nakashima context.
4. ✅ **Done (Claude anchor-hunt 2026-04-28):** Owens 1986 *Technology and Culture* — 5 Green claims promoted on Bush/analyzer context.
5. **Tractable:** Soni & Goodman 2017 *A Mind at Play* — physical or e-book access. Would resolve Q3, Q5, Q6, partially Q8.
6. **Tractable:** Gardner 1985 *The Mind's New Science* — physical or e-book access. Would resolve Q2.
7. **Tractable:** Mindell 2002 *Between Human and Machine* — physical or e-book access. Would tighten Scene 1 with additional Bush-MIT-DA institutional anchors.
8. **Tractable:** Yamada 2004 *IEEJ Trans. FM* (open access on J-STAGE). Would partially resolve Q9.
9. **Archive-blocked:** MIT Institute Archives — Bush, Caldwell, Shannon files. Would resolve Q3, Q5, Q6.
10. **Archive-blocked:** Vannevar Bush Papers, Library of Congress. Would resolve Q1, Q3, Q5.
11. **Archive-blocked:** Rockefeller Foundation archival records (RF1.1/224/2/23). Would resolve Q4.

Rows 5-8 are tractable without physical archive trips. Rows 9-11 require either archive access or correspondence with archivists. The chapter has now reached `capacity_plan_anchored` status: every Prose Capacity Plan layer cites at least one source identifier with verified page anchors, and the Scene-Level Claim Table has 27+ Green claims. Promotion of additional scenes from Yellow to Green is a stretch upgrade pursued via rows 5-8 next.
