# Infrastructure Log: Chapter 4 — The Statistical Roots

This is a chapter where the *absence* of computing infrastructure is the load-bearing infrastructural fact. Markov's chains were proved, demonstrated, and circulated decades before any digital machine existed. Tracking what each scene actually relied on — pencil, hand-counting, journal printing, library mimeographs — clarifies the gap between mathematical possibility and any practical use.

## Scene 1: The Theological Provocation (1902–1905)

- **Compute:** None. Nekrasov's 1902 paper was a textual argument; Markov's response was correspondence and the beginnings of a theoretical proof.
- **Storage:** Print journals (the Kazan *Izvestiia* and the *Bulletin de l'Académie Impériale des Sciences de St.-Pétersbourg*). Letters between Markov and Chuprov, later collected in Ondar 1981.
- **Distribution:** Russian mathematical journals reaching a small specialist readership. Markov's institutional positions (St. Petersburg University; Imperial Academy of Sciences) gave him a publishing platform; Nekrasov's positions (Moscow University; Russian Orthodox Church-aligned faculty) gave him a similar but ideologically opposed one.
- **Constraint that matters:** None of the dispute's substance ever reached a non-Russian audience until Seneta 2003 (free will / Quetelet / Nekrasov) and Hayes 2013 made it accessible in English.

## Scene 2: The 1906 Counterexample

- **Compute:** Pencil and paper. The 2-state proof in Markov 1906 is symbolic — it does not require numerical computation.
- **Storage:** *Bulletin de la société physico-mathématique de Kasan* (2) 15(4):135–156. A regional Russian university bulletin, in Russian, reaching at most a few dozen specialist subscribers in Russia and a handful abroad. Link 2006 *Chains to the West* notes that the dissemination of Markov's chain results to Western Europe was slow and patchy until German translations of his textbook (1912) and the 1910 *Acta Mathematica* French version of the 1907 paper.
- **Distribution:** Slow. The 1906 paper is one of nine Russian-language chain-dependence papers Markov produced through 1912; their generalized results reach Western Europe primarily through the German translation of his *Calculus of Probability* (Liebmann, 1912) and through targeted French versions in *Acta Mathematica*. (Link 2006 *Chains to the West* pp.562–563.)
- **Constraint that matters:** The 1906 paper exists in Russian only at the time of writing (and remains so in the chapter's window); even mathematically sympathetic Western readers needed German or French to encounter Markov's chain machinery before Liebmann 1912.

## Scene 3: The Bernoulli Bicentenary Lecture (23 January 1913)

- **Compute:** Pencil and paper, by hand, by Markov himself. Hayes 2013 ("Counting Vowels and Consonants") describes attempting to repeat Markov's vowel-pair counting on an English translation of *Onegin*: "Circling double vowels on a printout of the text seemed to go quickly — 10 stanzas in half an hour — but it turned out I had missed 62 of 248 vowel-vowel pairs. Markov was probably faster and more accurate than I am; even so, he must have spent several days on these labors."
- **Workflow (per Markov 1913, Link translation, pp.591–597):**
  1. Selected the first 20,000 letters of *Onegin* — first chapter plus sixteen stanzas of the second.
  2. Eliminated punctuation, spaces, hard signs (ъ), and soft signs (ь) — the latter "are not pronounced independently but modify the pronunciation of the preceding letter" (p.591 footnote 2).
  3. Wrote the resulting stream into 200 tables of ten rows by ten columns.
  4. Counted vowels per column; paired columns 1+6, 2+7, 3+8, 4+9, 5+10; entered five sums per table; summed horizontally and vertically.
  5. Computed the arithmetic mean of vowels per 100 letters (43.19), the unconditional vowel probability (p ≈ 0.432), and the variance (5.114) using the method of least squares (Legendre 1805 / Gauss 1809; Link 2006 *Traces* p.329).
  6. Returned to the unbroken stream to count digram patterns: 1,104 vowel-vowel pairs out of 8,638 vowels (so p1 = 0.128); 3,827 consonant-consonant pairs out of 11,361 consonants-following-something (so p0 = 0.663). (Markov 1913 p.596.)
  7. Counted trigram patterns for the second-order chain: 115 vowel-vowel-vowel and 505 consonant-consonant-consonant (so p1,1 = 0.104, q0,0 = 0.132). (Markov 1913 p.597.)
  8. Computed the empirical and theoretical dispersion coefficients (0.208 observed; 0.300 theoretical for a 1-step chain; 0.195 theoretical for the 2-step chain). (Markov 1913 pp.597–598.)
- **Storage:** Manuscript tables on paper (reproduced as Figure 1 in Link 2006 *Traces* p.327). The published paper contains 40 small tables, each with five columns and five rows of summed counts. Link 2006 *Traces* notes (p.327) that the printed tables "fill an entire page" of the published paper.
- **Distribution:** *Bulletin de l'Académie Impériale des Sciences de St.-Pétersbourg* (6) 7(3):153–162, in Russian only. Translated into German by Link in his 2004 doctoral dissertation; published in English for the first time by Link et al. in 2006.
- **Constraint that matters:** Hand-counting at 20,000 letters with digram and trigram tabulation is tractable for one motivated mathematician over several days. It does not generalize. Markov's repeat exercise on Aksakov's 100,000-letter passage was the practical ceiling reachable without machinery; he reached it once and stopped.

## Scene 4: Forty-Year Silence and Shannon's 1948 Adoption

- **1913–1948 transmission infrastructure:**
  - Russian-language journals (the *Onegin* paper sits unread by Western readers for decades).
  - German translation of Markov's *Calculus of Probability* (Liebmann, 1912) — carries Markov's chain results in textbook form but not the *Onegin* analysis.
  - Fréchet 1938, *Méthode des fonctions arbitraires* (Paris, Gauthier-Villars) — the work Shannon 1948 §4 footnote 6 cites for “detailed treatment.” (Locator: Harvard PDF pp.7–8; §4, not §5.)
  - Kolmogorov 1933 *Grundbegriffe* / 1950 Chelsea EN §6 (printed pp.12–13) defines Markov chains and cites von Mises and Hostinský 1931. Shannon does not cite Kolmogorov. Link 2006 *Chains* pp.571–572 (Bru/Hostinský) is the secondary transmission sketch — do not collapse it into Shannon’s footnote. See `source-record-2026-09-09.md`.
  - Halle 1955 — unpublished mimeograph English translation of Markov 1913, surviving "only in mimeograph form in a few libraries." (Hayes 2013 "The Bootless Academician".)
- **Shannon 1948 compute and storage:**
  - The text approximations in Shannon §3 ("OCRO HLI RGWR..." second-order; "IN NO IST LAT WHEY CRATICT..." third-order) were generated by hand using a book of random numbers and a table of letter / digram / trigram frequencies. Shannon 1948 §3 (PDF p.7): "The first two samples were constructed by the use of a book of random numbers in conjunction with (for example 2) a table of letter frequencies. This method might have been continued for (3), (4) and (5), [but] one opens a book at random and selects a letter at random on the page... [labor] becomes enormous at the next stage."
  - Shannon explicitly notes (§3 PDF p.8): "It would be interesting if further approximations could be constructed, but the labor involved becomes enormous at the next stage." Translation: in 1948, fourth-order English n-gram modeling by hand from books was already beyond what one researcher could practically do.
- **Constraint that matters:** Shannon's worked examples in §3 are themselves a paper-and-pencil-and-book-of-random-numbers exercise. The same constraint Markov hit in 1913 — hand counting at scale — was still active in 1948. The infrastructure for computing transition matrices over real-vocabulary corpora did not exist until the late 1950s and became routine only with the IBM 704 and ENIAC successors.

## Scene 5: Honest Close

- **What was missing in 1922 (Markov's death) that would have been needed for any practical n-gram language model:**
  - Published English access to Markov 1913 (arrived 1955 mimeograph / 2006 print).
  - A theory of communication that needed a stochastic source as input (arrived 1948 with Shannon).
  - Digital storage for larger-than-toy transition matrices, and the claim that only a computer can answer modern MCMC-style questions, remain **unanchored** (2026-09-09). Shannon §3 supports hand labor becoming “enormous”; it does not date digital storage. Defer both claims rather than invent a hardware narrative.
  - Statistical NLP as a research community (arrived in the 1980s–1990s; see forward-references to Ch30 *The Statistical Underground*).
- **Constraint that matters:** Markov did not lack ambition; he lacked a community that wanted his answer. Hayes 2013 ("The Bootless Academician") closes with the observation that Markov "bequeathed us a proof that a Markov chain must eventually settle down to some definite, stable configuration corresponding to the long-term average behavior of the system" — but the practical computational questions ("how long until convergence?", "how to estimate error from premature termination?") that dominate modern Markov-chain research only became answerable when computers could simulate convergence directly, which Markov never lived to see.

## Cross-Chapter Infrastructure Notes

- This chapter is upstream of Ch9 (Shannon-era information theory) — the Markoff-process model in Shannon 1948 §3–§6 is the bridge from Markov's 1913 demonstration to the 20th-century information-theoretic mainstream. Forward-reference Ch9 once, briefly.
- This chapter is upstream of Ch30 (*The Statistical Underground*) — the 1980s statistical-NLP revival that finally made n-gram language models an active research enterprise. Forward-reference Ch30 once at the chapter close, no earlier.
- This chapter is *not* upstream of any deep-learning chapter; the path from Markov to LLMs runs through statistical NLP, not through neural connectionism. Do not write a "Markov foreshadowed LLMs" passage; the boundary contract forbids it.
