# Sports-science source library

Local source archive and access-status index for the training diary. Downloaded
and reviewed on **2026-09-07** after reading the athlete profile and the complete
diary archive available through **2026-07-24**.

The operational synthesis is in
[EVIDENCE_BASE.md](./EVIDENCE_BASE.md). That file, not any single paper, governs
how evidence is translated into diary decisions.

## Access status

- **Full PDF:** the complete paper was downloaded, validated as a PDF, and read.
- **Full HTML:** the complete applied article was saved and read.
- **Official record:** the DOI/publisher or PubMed record and abstract were
  reviewed, but a clean full-text file was not available. Publisher challenge
  pages are retained only to document the failed access path; they are not
  treated as article text.
- Binary/source downloads in `papers/` and `pubmed-records.xml` are local-only
  and gitignored. The index and synthesis remain versioned.

## Source index

| ID | Source | Topic | Local access | Profile relevance |
|---|---|---|---|---|
| S01 | Allen, Coggan & McGregor (2019), *Training and Racing with a Power Meter*, Performance Manager overview | CTL / ATL / TSB | `papers/coggan-performance-manager.html` — full HTML | Medium: useful load context, never a readiness verdict |
| S02 | Mujika & Padilla (2003), [doi:10.1249/01.MSS.0000074448.73931.11](https://doi.org/10.1249/01.MSS.0000074448.73931.11) | Tapering | Full text reviewed online; official record plus `papers/mujika-padilla-2003-university-source-compilation.pdf` saved locally | High during event taper |
| S03 | Bosquet et al. (2007), [doi:10.1249/mss.0b013e31806010e0](https://doi.org/10.1249/mss.0b013e31806010e0) | Taper meta-analysis | Official PubMed record in `pubmed-records.xml` | High during event taper |
| S04 | Seiler & Kjerland (2006), [doi:10.1111/j.1600-0838.2004.00418.x](https://doi.org/10.1111/j.1600-0838.2004.00418.x) | Intensity distribution | `papers/seiler-kjerland-2006-training-intensity-distribution.pdf` — full PDF | Medium-high as a guardrail against accidental hard days |
| S05 | Issurin (2010), [doi:10.2165/11319770-000000000-00000](https://doi.org/10.2165/11319770-000000000-00000) | Periodization | `papers/issurin-2010-training-periodization.pdf` — full PDF | Medium: planning framework, not a rigid prescription |
| S06 | Plews et al. (2013), [doi:10.1007/s40279-013-0071-8](https://doi.org/10.1007/s40279-013-0071-8) | HRV monitoring | Official PubMed record in `pubmed-records.xml` | High for trend-based HRV interpretation |
| S07 | Buchheit (2014), [doi:10.3389/fphys.2014.00073](https://doi.org/10.3389/fphys.2014.00073) | HR monitoring | `papers/buchheit-2014-monitoring-training-status-hr.pdf` — full PDF | High for multi-signal recovery decisions |
| S08 | Walsh et al. (2021), [doi:10.1136/bjsports-2020-102025](https://doi.org/10.1136/bjsports-2020-102025) | Athlete sleep | `papers/walsh-et-al-2021-sleep-athlete-consensus.pdf` — full PDF | High, especially in taper and heavy blocks |
| S09 | Hirshkowitz et al. (2015), [doi:10.1016/j.sleh.2014.12.010](https://doi.org/10.1016/j.sleh.2014.12.010) | Sleep duration | `papers/hirshkowitz-et-al-2015-sleep-duration-recommendations.pdf` — full PDF | Medium: population reference range |
| S10 | Ohayon et al. (2017), [doi:10.1016/j.sleh.2016.11.006](https://doi.org/10.1016/j.sleh.2016.11.006) | Sleep quality | `papers/ohayon-et-al-2017-sleep-quality-recommendations.pdf` — full PDF | High for continuity/latency interpretation |
| S11 | Jeukendrup (2014), [doi:10.1007/s40279-014-0148-z](https://doi.org/10.1007/s40279-014-0148-z) | Personalized exercise carbohydrate | `papers/jeukendrup-2014-carbohydrate-intake-during-exercise.pdf` — full PDF | Very high for long-ride fueling |
| S12 | Burke et al. (2011), [doi:10.1080/02640414.2011.585473](https://doi.org/10.1080/02640414.2011.585473) | Carbohydrate for training/competition | Publisher metadata saved as HTML plus official record | Very high for pre/during/post targets |
| S13 | Thomas, Erdman & Burke (2016), [PubMed 26891166](https://pubmed.ncbi.nlm.nih.gov/26891166/) | Nutrition and athletic performance | `papers/thomas-et-al-2016-nutrition-athletic-performance.pdf` — full PDF | Very high for energy availability and recovery |
| S14 | Viribay et al. (2020), [doi:10.3390/nu12051367](https://doi.org/10.3390/nu12051367) | 120 g carbohydrate/h | `papers/viribay-et-al-2020-120g-h-mountain-marathon.pdf` — full PDF | Medium as an upper-bound experiment, not a default |
| S15 | Rowlands et al. (2015), [doi:10.1007/s40279-015-0381-0](https://doi.org/10.1007/s40279-015-0381-0) | Glucose-fructose mixtures | `papers/rowlands-et-al-2015-fructose-glucose-endurance.pdf` — full PDF | High for multiple-transportable-carbohydrate strategy |
| S16 | Guest et al. (2021), [doi:10.1186/s12970-020-00383-4](https://doi.org/10.1186/s12970-020-00383-4) | Caffeine and performance | `papers/guest-et-al-2021-caffeine-exercise-performance.pdf` — full PDF | Medium: optional and tolerance-dependent |

## Known access limitations

- A clean standalone PDF was not obtained for S02, but its full text was read
  online and a university-hosted source compilation containing the indexed
  paper was saved locally.
- Clean full-text downloads were not obtained for S03, S06, or S12. Their
  operational use is restricted to claims supported by the official
  abstract/record or an openly readable full-text page.
- S04 is a small observational study in junior male cross-country skiers; it
  does not prove an optimal distribution for a 40-year-old recreational cyclist.
- S14 studied 20 elite male mountain runners who had already trained their gut;
  it does not justify prescribing 120 g/h by default to this athlete.
- S01 describes an applied model. CTL, ATL, TSB, and TSS are useful relative
  summaries but are not direct measurements of fitness, fatigue, or readiness.
