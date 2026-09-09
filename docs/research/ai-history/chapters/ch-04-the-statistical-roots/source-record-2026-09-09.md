# Chapter 4 source record — Yellow-claim recheck (2026-09-09)

Research-only record for #2340 SOURCE-RECORD. It does not edit published
prose, accept the chapter, or replace a later prose-quality review. The
2026-09-05 model-analogy packet is inherited, not reopened.

## Retrieval record

Checked 2026-09-09. Hashes are SHA-256 of the retrieved bytes.

| File | URL | Bytes | SHA-256 |
|---|---|---|---|
| Hayes 2013 print PDF | https://www.americanscientist.org/sites/americanscientist.org/files/201321152149545-2013-03Hayes.pdf | 1,120,436 | `f8a964ce213c8e268f87223b3b4ebb59451256d898e363d829f7edd8ba30a3aa` |
| Seneta 2006 | https://www.maths.usyd.edu.au/u/eseneta/senetamcfinal.pdf | 193,084 | `f84c647b5e6e965c00f16e35c4f0c961162434b6aa5acb4697f971c11f0ffef6` |
| Shannon 1948 (Harvard reflow) | https://people.math.harvard.edu/~ctm/home/text/others/shannon/entropy/entropy.pdf | 366,296 | `6e4e3411984f3edf99dbfe8b941cb5e8a321379ff0cae6ae5c1f592ad8882ca8` |
| Markov 1913, Link trans. | https://alpha60.de/research/markov/DavidLink_AnExampleOfStatistical_MarkovTrans_2007.pdf | 144,532 | `f87b1692404adaeec9a1525cd3fa3f14e34f85175ebda35b006c7b9bafa775b2` |
| Link 2006 *Chains* | https://alpha60.de/research/markov/DavidLink_ChainsToTheWest_2007.pdf | 361,940 | `9640f4f94824786af9d7ec8e2e25a168e90bbd3770ed08b31e7352f7fb3fd87b` |
| Basharin et al. 2004 (UF mirror) | https://faculty.eng.ufl.edu/meyn/wp-content/uploads/sites/671/archive/spm_files/Markov-Work-and-life.pdf | 3,562,207 | `d8835ad33297aff52bd002c7803f966016a21d4fc67f31f45f94fba4e060134d` |
| Sheynin 2004 translations | https://www.probabilityandfinance.com/sheynin/005_ProbabilityandStatisticRussianPapers.pdf | 1,310,089 | `9db05464877b56c85790d8746607b8c5a21c02ae118d31d97ca9d6c09061b001` |
| JEHPS 2006 Markov 1906 reprint | https://www.jehps.net/Novembre2006/Markov3pdf.pdf | 21,031,177 | `32a5e7a4e388e1ffd3855b671ab39c8194b0d021c673f632bcb21c8b2880a887` |
| Kolmogorov 1950 Chelsea EN | https://web.uni-miskolc.hu/~matgt/pdf/valseg/Kolmogorov.pdf | 1,256,646 | `427e0fd315c5bec6c123838ed9510acb7ac354755dd7ac5ddc34b236d9891674` |

Ondar 1981 was not retrieved (Springer record only). Nekrasov 1902 was not retrieved. The JEHPS reprint is a 12-page image scan with no extractable text in this session; do not invent its page locators.

## Claim dispositions

1. **Petersburg/Moscow ideology (published ~74).** Hayes print p.94: Moscow University as an Orthodox “stronghold”; seminary background; “A secular republican from Petersburg was confronting an ecclesiastical monarchist from Moscow.” Basharin printed p.6 independently gives a Moscow-school / free-will vs Petersburg contrast. Still secondary only. Keep Yellow; attribute the neat polarity to Hayes (with Basharin as a second secondary), not as a primary institutional fact.

2. **Hayes-mediated correspondence (published ~77/90).** “Abuse of mathematics”: Hayes print p.94, no letter date. Basharin printed p.17, citing Ondar [25], places the phrase on a 2 Nov 1910 postcard about Chuprov, *Essays on the Theory of Statistics*, p.195. “Pure analysis… indifference”: Hayes print p.95 only in this recheck; Ondar still unseen. Treat both as Hayes/Basharin quotations of Ondar, not as directly verified letters. Seneta 2006 p.3 remains the independent secondary for the late-1910 “fiery post-cards.”

3. **Markov 1906 support.** Seneta 2006 p.3 (counterexample to Markov’s reading of Nekrasov 1902) and Hayes print p.95 (two-state; four transitions in (0,1)) still hold. Sheynin 2004, item 11 (PDF pp.91–95, section [2]) now supplies an English rendering of the two-state LLN case (`p'` after A, `p''` otherwise). Basharin printed p.13 adds that the journal text appeared in 1907 with later sections. Kazan 1906 pagination and the image-only JEHPS reprint are not page-anchored here. Do not add proof detail.

4. **Shannon Fréchet vs Kolmogorov (published ~114/126).** Shannon 1948 Harvard PDF pp.7–8: §4 names “discrete Markoff processes”; footnote 6 is Fréchet 1938 only. No Markov, Kolmogorov, or Khinchin citation. Kolmogorov 1950 Chelsea printed pp.12–13, §6, defines Markov chains and points to von Mises and Hostinský 1931, not to Shannon. Link 2006 *Chains* printed pp.571–572 records Shannon→Fréchet and Bru’s Bologna-1928 Hostinský→Fréchet/Khinchin/Kolmogorov synthesis. Separate the evidenced Fréchet footnote from that secondary transmission sketch.

5. **Digital-storage / “only a computer can answer” (published ~124).** No source in this packet supports absolute digital-storage limits or that named mathematical questions require a computer. Shannon’s punched-card/relay remarks are about the bit as a unit, not n-gram matrices. Defer both claims; do not invent a hardware narrative.

6. **Modern LLM comparison (published ~128–131).** Inherited from `model-analogy-corrections-2026-09-05.md` and PR #2370. No new model claims.

7. **Optional δ check.** Markov 1913 (Link) printed p.596: `p1 = 1104/8638 ≈ 0.128`, `p0 ≈ 0.663`, `δ = p1 − p0 = 0.128 − 0.663 = −0.535`. Rechecked from those printed figures only. This is this sample’s diagnostic, not a general validation rule.

## Later prose hedges (not applied here)

Attribute the ideology line to Hayes; mark the two letters as Hayes/Basharin via Ondar; keep 1906 at secondary-plus-Sheynin-translation level; say Shannon cites Fréchet, not Kolmogorov; withdraw or hedge the storage/computer close.

## Non-acceptance

No whole-chapter, Ukrainian, or editorial-program acceptance follows. Historical lifecycle labels in `status.yaml` are not current acceptance.
