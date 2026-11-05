# PR #608 review: draw d3, the OMOP dental ERD, in the data-dictionary format

Closes #607. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Verdict
One blocker: the PNGs aren't rendered. Hold the merge until the owner renders them or accepts `.drawio` links.

## Checks
- **Format:** d3 uses `dictionary_erd`, like gold and silver, with the same legend, subject areas, colours and
  entity view. It is in `test_erd_format.py`'s parametrised tests: layout, lines and legend.
- **Names:** CDM tables and columns keep their official names (AGENTS.md, "SQL and data names"). The extension and
  view names match `omop/ddl/dental_extension.sql`.
- **No PHI, no note text:** the profile comes from seeded synthetic tables, with `note_text` dropped before
  profiling. A test checks this. `note_text` and `person_source_value` are marked red as PHI in a real extract.
- **Nothing lost from the old d3:** design C's tooth columns, the site self-reference, the site_event link to
  measurement and the perio_chart pivot are all kept. The local concepts are now concept rows, profiled.
  The design A/B/C note now sits in the open-question text on `measurement.tooth_number`.
- **Wording:** no use of "diagnose". The note_nlp row says "the status found".

## Blocking
- The PNGs (`d3_erd_omop_dental_full.png`, `_entity.png`) aren't rendered. GitHub doesn't preview `.drawio`, so
  until they are, d3 shows no picture.
