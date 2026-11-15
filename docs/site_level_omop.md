# Site-level periodontal data in OMOP (spec 006)

> Personal learning project; synthetic data; public sources only. See [DISCLAIMER](../DISCLAIMER.md).

Dental charts record measurements at **sites** (six per tooth), but the
classifications need **person-visit** measures, and OMOP has no standard way to
say which tooth or site a row belongs to. This page shows the gap with working
code: site-level synthetic charts, the derived-measure layer between sites and
phenotypes, both classification systems, three storage designs compared on
Postgres (Lakebase), a concept-mapping table and an Atlas feasibility check.

## 1. Site-level charts

`python/health_transformation_lab_nlp/sites.py`, `scripts/22_build_sites.py`

- 32 teeth (universal numbering) × 6 sites: mesio-buccal, buccal, disto-buccal,
  mesio-lingual, lingual, disto-lingual. Interproximal = MB, DB, ML, DL.
- Per site: probing depth (PD), clinical attachment loss (CAL), bleeding on probing.
- Per tooth: present / missing (other cause / periodontitis), furcation class, mobility degree.
- Generated from each charted visit's chart so the derived measures reproduce it
  (max interproximal CAL, max PD, teeth lost exactly; bleeding share on the same side of 10%).
  Tested: the stage from the sites equals the stage from the chart.
- Dry run, on the 4,343-visit build before #467: 3,437 charted exams, 611,154 site rows, 109,984 tooth rows.

## 2. The derived-measure layer

The middle step that OMOP and Atlas don't provide. Per exam:

| Derived measure | Used by |
|---|---|
| Max PD, max interproximal CAL, % sites bleeding, teeth lost to periodontitis, teeth present | 2017 AAP/EFP stage (with complexity: PD, < 20 teeth) |
| Max furcation class, max mobility degree | 2017 AAP/EFP complexity |
| % teeth with interproximal CAL ≥ 1 mm | 2017 extent (localized / generalized) |
| Number of **different teeth** with interproximal CAL ≥ 3 / 4 / 6 mm, PD ≥ 4 / 5 mm; interproximal sites with PD ≥ 5 mm | 2012 CDC/AAP |

Python `sites.derive`, R `r/R/07_sites.R`, SQL `omop/sql/site_designs/derived_tail.sql`:
identical results (parity test and Postgres test).

## 3. Both classification systems from the same sites

| System | Rules | In code |
|---|---|---|
| 2017 AAP/EFP (staging, grading, extent) | AAP worksheet ([staging_grading.md](staging_grading.md)) | `sites.aap_from_derived` → `labels.label_chart` |
| 2012 CDC/AAP surveillance (Eke et al., *J Periodontol* 2012) | Severe: ≥ 2 interproximal sites CAL ≥ 6 mm on different teeth and ≥ 1 interproximal site PD ≥ 5 mm. Moderate: ≥ 2 interproximal sites CAL ≥ 4 mm on different teeth, or ≥ 2 interproximal sites PD ≥ 5 mm on different teeth. Mild: ≥ 2 interproximal sites CAL ≥ 3 mm and ≥ 2 interproximal sites PD ≥ 4 mm on different teeth, or 1 site PD ≥ 5 mm | `sites.cdc_aap`, SQL `CASE` in `derived_tail.sql` |

Dry run cross-tab (`data/sites/aap_vs_cdc.csv`), same mouths:

| 2017 stage ↓ / CDC/AAP → | none | mild | moderate | severe |
|---|---|---|---|---|
| healthy | 911 | 0 | 0 | 0 |
| gingivitis | 776 | 0 | 0 | 0 |
| stage I | 742 | 0 | 0 | 0 |
| stage II | 433 | 157 | 7 | 0 |
| stage III | 16 | 4 | 155 | 152 |
| stage IV | 0 | 0 | 27 | 57 |

The 2017 system calls periodontitis in many mouths CDC/AAP calls "none" (stage I
can never meet CDC/AAP, which needs CAL ≥ 3 mm on two teeth). The size of the gap
here reflects how the generator spreads loss across sites, a placeholder.
Reporting prevalence under CDC/AAP makes it comparable with NHANES (action item B6).

## 4. Three storage designs, compared

Same mouths, three schemas, each with the full CDM 5.4 + dental extension, on
Postgres 16 (Lakebase is managed Postgres). `health_transformation_lab_nlp/site_designs.py`,
`scripts/23_site_designs.py`; SQL in `omop/sql/site_designs/`. The figures below were measured on the build
before #467 (3,437 charted exams), as the dry run above was.

| | A. Post-coordinated | B. Pre-coordinated | C. Site columns |
|---|---|---|---|
| Idea | MEASUREMENT per site & measure; SITE rows for tooth and tooth-site; SITE_EVENT links them (OHDSI Dentistry Workgroup) | One local concept per measure × tooth × site (`PD\|3\|MB`) | MEASUREMENT gains `tooth_number`, `tooth_site` |
| Base OMOP unchanged? | Yes, plus two extension tables | Yes | No: two columns on a data table |
| Extra concepts | 0 | 672 | 0 |
| Joins to reach (tooth, site) | 5 | 2 | **0** |
| String decoding per query | 1 | 11 | 0 |
| Design-specific SQL | 26 lines | 23 lines | **18 lines** |
| Extra rows | 256,480 SITE + 2,163,414 SITE_EVENT | — | — |
| Storage (measurement, site, site_event, concept) | 529 MB | **276 MB** | 309 MB |
| Derived query, 3,437 exams (before #467) | 6.8 s | 4.2 s | **2.2 s** |
| Matches Python | exactly | exactly | exactly |

All three, on the 3,437 exams of the build before #467: 2,163,414 MEASUREMENT rows (3 per site, 3 per tooth). Timings are
the median of three runs on one machine; ratios matter more than seconds.

**Reading it:** the link-table design (A) keeps base OMOP intact but doubles the
data with a row per measurement in SITE_EVENT and needs five joins for every
site-level question. Pre-coordination (B) fits base OMOP and is compact, but
needs hundreds of concepts that don't exist as standard ones and string
decoding in every query; anything not built in (a new site, surface, or
measure) needs new concepts. Site columns (C) are the simplest and fastest to
query, at the price of changing a CDM table, which is the change some dental
OMOP proposals recommend.

## 5. Concept mapping

| Measure | Level | Standard concept found | Repo uses |
|---|---|---|---|
| Probing depth | site | LOINC **32910-2** Probing depth {Tooth}.{probe site} | local `SITE_PD` |
| Attachment level (CAL) | site | LOINC **32912-8** Attachment level {Tooth}.{probe site}, calculated (PD + recession) | local `SITE_CAL` |
| Bone attachment level | site | LOINC **32914-4** (maxilla, measured) | — |
| Periodontal chart panel | exam | LOINC **86603-8** Periodontal attachment, recommended HL7 CDA R1 set (10 member codes; other members' names not checked) | — |
| Bleeding on probing, furcation, mobility, missing tooth | site / tooth | Not confirmed here; check Athena | local |
| Tooth, tooth surface (anatomic site) | — | SNOMED body-structure concepts for teeth exist; no standard OMOP column to put them in | local SITE concepts |
| Max CAL, max PD, % sites bleeding, counts of teeth over thresholds | exam (derived) | **None** | local `N_TEETH_IP_CAL6` etc. (`omop/vocab/local_concepts.csv`) |
| CDC/AAP category, 2017 stage | person-visit | Stage concepts exist in SNOMED; CDC/AAP categories not found | local |

To do with an Athena download: confirm each LOINC code's OMOP standard status,
map bleeding, furcation, mobility, tooth status and teeth, and propose the derived
measures as new concepts.

## 6. Atlas feasibility

Atlas cohorts (Circe) select people by concept, value range, date window and
occurrence counts. Checked against the criteria above:

| Criterion | From raw site rows | From derived rows written back to MEASUREMENT |
|---|---|---|
| Any site PD ≥ 5 mm | Yes: measurement PD, value ≥ 5 | Yes |
| Max CAL ≥ 5 mm (stage III by CAL) | Yes: any CAL row ≥ 5 | Yes |
| ≥ 2 sites with CAL ≥ 4 mm | Roughly: occurrence count ≥ 2 within the visit | Yes |
| … **on different teeth** | **No**: the tooth isn't a criterion attribute (A, C); in B the concept distinguishes site, not tooth | Yes: `N_TEETH_IP_CAL4` ≥ 2 |
| % sites bleeding ≥ 10 | **No** (needs a ratio over all sites) | Yes: `PERIO_BOP_PCT` ≥ 10 |
| Interproximal sites only | Only in B (choose the interproximal concepts) | Yes |
| Full 2017 stage with complexity | **No** | Yes, as a stored stage, or via the counts |
| CDC/AAP severe | **No** | Yes: `N_TEETH_IP_CAL6` ≥ 2 and `N_SITES_IP_PD5` ≥ 1 at the same visit |

So Atlas can express the classifications only after the derived layer is
computed and **written back as MEASUREMENT rows** (`site_designs.write_back_derived`,
tested on design C). Not tested in a live Atlas instance.

## Out of scope / action items

- ADA standard 1084 (dental clinical data exchange) isn't public; mapping from it needs the standard.
- Primary dentition (teeth A–T) and surfaces (128 for an adult) not generated yet.
- Conditions per tooth (caries, fractures) and devices (implants) not generated.
- Recession and gingival margin are implicit (CAL and PD only).

## Sources

- OHDSI Dentistry Workgroup (Koski R et al.), *Mapping Dental Use Cases to the OMOP-CDM*, OHDSI 2023. [PDF](https://ohdsi.org/wp-content/uploads/2023/10/39-Koski-OHDSIreport-Robert-Koski.pdf)
- Eke PI, Page RC, Wei L, Thornton-Evans G, Genco RJ. *Update of the case definitions for population-based surveillance of periodontitis.* J Periodontol 2012;83:1449–1454; definitions as applied in Eke et al. 2015 ([CDC Stacks](https://stacks.cdc.gov/view/cdc/31519/cdc_31519_DS1.pdf)).
- LOINC [32910-2](https://www.findacode.com/loinc/32910-2--probing-depth-tooth-measured.html), [32912-8](https://findacode.com/loinc/32912-8--att-level-tooth-calc.html), [32914-4](https://autoicdapi.com/reference/loinc/32914-4), panel [86603-8](https://www.findacode.com/loinc/86603-8--periodontal-attachment-recommended-cda-r1-set.html).
- AAP *Staging and Grading Periodontitis* worksheet. [PDF](https://www.perio.org/wp-content/uploads/2019/08/Staging-and-Grading-Periodontitis.pdf)
