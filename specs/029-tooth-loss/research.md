# Research: Open Dental's tables for spec 029 (task T001)

**Source.** Open Dental's own source code, which is public under the GPL:
- repository: https://github.com/OpenDental/OpenDental
- release branch `24_3`, commit `d804c19` (2025-04-01)
- folder `OpenDentBusiness/TableTypes/`, one C# class per table

Each class names its database table and documents every column. The table name comes from the class's
`CrudTable` attribute, or is the class name lowercased when that attribute names none. Read 2026-10-30.

opendental.com, which publishes the same schema as documentation, is not reachable from the build container, so
the source was used instead.

Only the names, types and meanings below are recorded here, in our own words. Columns added for #379 (the
data-dictionary ERD) were checked in the same source on 2026-10-31. No source code is copied. Only
the columns spec 029 needs are listed; each table has more.

## Tables and columns

### `patient`
*(Patient.cs)*

| Column | Type | Meaning |
|---|---|---|
| `PatNum` | bigint | primary key |
| `Birthdate` | date | age is never stored; it is computed from this |
| `Gender` | enum PatientGender | |
| `PatStatus` | enum PatientStatus | |
| `ClinicNum` | bigint | FK to `clinic`; 0 when no clinics are used |
| `PriProv` | bigint | FK to `provider`; the primary provider |
| `DateFirstVisit` | date | set automatically |
| `SmokingSnoMed` | string | the most recent smoking status, as a SNOMED code |
| `Zip` | string | postcode; a real extract keeps at most the first 3 digits |
| `Guarantor` | bigint | FK to `patient`: the head of household |
| `MedUrgNote` | string | free-text medical alert; would hold PHI |
| `Premed` | bool | needs premedication before appointments |
| `Language` | string | primary language, as a code |
| `AdmitDate` | date | hospital admission date; can precede the first visit |
| `SiteNum` | bigint | FK to `site`, a place of care such as a school or nursing home; 0 when none |
| `ResponsParty` | bigint | FK to `patient`: who is responsible for finances |
| `DateTimeDeceased` | datetime | date of death; would hold PHI |

### `procedurelog`
*(Procedure.cs; table name set by `CrudTable`)*

| Column | Type | Meaning |
|---|---|---|
| `ProcNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient` |
| `ProcDate` | date | the date shown as performed; for a planned procedure, the date planned or empty |
| `DateComplete` | date | when first set complete |
| `DateTP` | date | when first treatment-planned |
| `ProcStatus` | enum ProcStat | 1 TP (planned), 2 Complete, 3 Existing Cur Prov, 4 Existing Other Prov, 5 Referred, 6 Deleted, 7 Condition |
| `CodeNum` | bigint | FK to `procedurecode` |
| `ToothNum` | string | blank, 1–32 or A–T (primary); supernumerary +50 |
| `Surf` | string | surfaces, or a quadrant, sextant or arch code |
| `Dx` | bigint | FK to `definition.DefNum`: the diagnosis, from the practice's own list (category Diagnosis) |
| `Prognosis` | bigint | FK to `definition.DefNum` (category Prognosis) |
| `DiagnosticCode`, `DiagnosticCode2`–`4` | string | diagnosis codes sent with medical claims |
| `IcdVersion` | byte | 9 or 10: which ICD version the diagnostic codes are |
| `IsPrincDiag` | bool | the principal diagnosis on a medical claim |
| `ProvNum` | bigint | FK to `provider` |
| `ClinicNum` | bigint | FK to `clinic` |
| `AptNum` | bigint | FK to `appointment` |
| `ProcFee` | double | fee |
| `ToothRange` | string | teeth of a multi-tooth procedure, comma-separated |
| `Priority` | bigint | FK to `definition.DefNum`: the treatment priority |
| `PlaceService` | enum PlaceOfService | where it was done (office, school, nursing facility, mobile unit, ...) |
| `Prosthesis` | char | blank no, I initial, R replacement |
| `MedicalCode` | string | optional medical procedure code |
| `UnitQty` | int | units billed, 1 by default |
| `SiteNum` | bigint | FK to `site` |

### `procedurecode`
*(ProcedureCode.cs)*

| Column | Type | Meaning |
|---|---|---|
| `CodeNum` | bigint | primary key |
| `ProcCode` | string | the D-code (CDT), or a medical or custom code |
| `Descript`, `AbbrDesc` | string | description, abbreviation |
| `TreatArea` | enum TreatmentArea | tooth, surface, quadrant, arch, mouth |
| `DiagnosticCodes` | string | up to 4 default ICD-10 codes, comma-separated |
| `ProcCat` | bigint | FK to `definition.DefNum`: the procedure category |
| `IsProsth` | bool | crown, bridge, denture or partial |
| `IsHygiene` | bool | a hygiene procedure |
| `MedicalCode` | string | a matching medical code, optional |
| `IsRadiology` | bool | a radiology procedure |

### `treatplan`
*(TreatPlan.cs)*

| Column | Type | Meaning |
|---|---|---|
| `TreatPlanNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient` |
| `DateTP` | date | date of the plan |
| `TPStatus` | enum TreatPlanStatus | 0 Saved, 1 Active, 2 Inactive |
| `Signature` | string | the signature captured when the plan was signed; empty when unsigned; would hold PHI |

### `proctp`
*(ProcTP.cs: a planned procedure, copied into a saved plan)*

| Column | Type | Meaning |
|---|---|---|
| `ProcTPNum` | bigint | primary key |
| `TreatPlanNum` | bigint | FK to `treatplan` |
| `PatNum` | bigint | FK to `patient` |
| `ProcNumOrig` | bigint | FK to `procedurelog`, to compare with the original |
| `ToothNumTP` | string | display text of the tooth number |
| `ProcCode` | string | display text, not a key |
| `Descript` | string | the procedure's description as text saved with the plan; can be edited (#379) |
| `Dx` | string | the diagnosis *text* at the time the plan was saved (not a key) |
| `Prognosis` | string | the prognosis text |
| `ItemOrder` | int | its order within the plan, fixed when the plan is saved |
| `Priority` | bigint | FK to `definition.DefNum`: the treatment priority |
| `Surf` | string | surfaces, quadrant or arch, as text |
| `ProcAbbr` | string | the code's abbreviation, as text; editable |
| `ProvNum` | bigint | FK to `provider` |
| `DateTP` | date | the date it was planned |
| `ClinicNum` | bigint | FK to `clinic` |

### `perioexam`
*(PerioExam.cs)*

| Column | Type | Meaning |
|---|---|---|
| `PerioExamNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient` |
| `ExamDate` | date | |
| `ProvNum` | bigint | FK to `provider` |

### `periomeasure`
*(PerioMeasure.cs: one row per exam, tooth and kind of measure)*

| Column | Type | Meaning |
|---|---|---|
| `PerioMeasureNum` | bigint | primary key |
| `PerioExamNum` | bigint | FK to `perioexam` |
| `SequenceType` | enum PerioSequenceType | 0 Mobility, 1 Furcation, 2 GingMargin (recession), 3 MGJ, 4 Probing, 5 SkipTooth, 6 BleedSupPlaqCalc, 7 CAL |
| `IntTooth` | int | 1–32; every measure belongs to a tooth |
| `ToothValue` | int | for whole-tooth measures (mobility, skip tooth); -1 means not measured |
| `MBvalue`, `Bvalue`, `DBvalue`, `MLvalue`, `Lvalue`, `DLvalue` | int | the six sites; -1 means not measured |

The source says three things the plan has to follow:
- **CAL is not stored.** Sequence type 7 (CAL) is never saved; Open Dental computes it on the fly. So
  attachment loss must be computed from probing depth (type 4) and gingival margin (type 2): CAL = probing
  depth + recession.
- **Gingival margin values of 100 and up encode negative numbers** (a margin above the cementoenamel junction):
  100 − value. So 105 means −5.
- **Bleeding, suppuration, plaque and calculus are one bit-flag sum per site** (type 6): bleeding 1, suppuration 2,
  plaque 4, calculus 8. Bleeding on probing is `value & 1`.

### `toothinitial`
*(ToothInitial.cs: the chart's starting state)*

| Column | Type | Meaning |
|---|---|---|
| `ToothInitialNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient` |
| `ToothNum` | string | 1–32 or A–Z |
| `InitialType` | enum ToothInitialType | 0 Missing, 1 Hidden, 2 Primary, then shifts, rotations and drawings |
| `Movement` | float | shift in mm, or rotation or tipping in degrees |

A tooth recorded missing with no procedure is `InitialType` 0. It carries no reason and no date.

### `definition`
*(Def.cs; table name set by `CrudTable`)*

| Column | Type | Meaning |
|---|---|---|
| `DefNum` | bigint | primary key |
| `Category` | enum DefCat | which list the item belongs to. `Diagnosis`, `Prognosis` and `TxPriorities` are the ones spec 029 reads |
| `ItemName` | string | the item's text, e.g. a diagnosis name |
| `ItemValue` | string | extra information, used differently by each category |
| `ItemOrder` | int | its place in the list, from 0 |
| `IsHidden` | bool | hidden from the list; old items stay, with their keys |

The diagnosis on a procedure (`procedurelog.Dx`) is therefore an item in the practice's **own** list, not a
standard code. Standard codes, when present, are in `DiagnosticCode` (ICD-9 or ICD-10, per `IcdVersion`).

### `disease`
*(Disease.cs: a patient's medical problem)*

| Column | Type | Meaning |
|---|---|---|
| `DiseaseNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient` |
| `DiseaseDefNum` | bigint | FK to `diseasedef` |
| `ProbStatus` | enum ProblemStatus | 0 Active, 1 Resolved, 2 Inactive |
| `DateStart`, `DateStop` | date | may be empty when unknown |
| `PatNote` | string | free-text note on the problem; would hold PHI |

### `diseasedef`
*(DiseaseDef.cs: the list of problems)*

| Column | Type | Meaning |
|---|---|---|
| `DiseaseDefNum` | bigint | primary key |
| `DiseaseName` | string | |
| `Icd10Code`, `ICD9Code`, `SnomedCode` | string | standard codes for the problem, e.g. diabetes |
| `IsHidden` | bool | hidden from the list |

### `clinic`
*(Clinic.cs)*

| Column | Type | Meaning |
|---|---|---|
| `ClinicNum` | bigint | primary key; used by patient, procedurelog and others |
| `Description` | string | |
| `Abbr` | string | short name |
| `Address` | string |  |
| `Address2` | string |  |
| `City` | string |  |
| `State` | string |  |
| `Zip` | string |  |
| `Phone` | string |  |
| `Fax` | string |  |

## Further tables of a research extract (#381)
Checked in the same source (`24_3`, `d804c19`) on 2026-10-31. Only Open Dental's own columns are listed. An extract
may add its own (a research ID in place of `PatNum`, days since the first visit, insurance types copied from the
insurance tables, age); those aren't Open Dental's and stay out. Open Dental's `language` table holds the
software's screen translations, not patient languages, so it isn't here.

### `provider`
*(Provider.cs)*

| Column | Type | Meaning |
|---|---|---|
| `ProvNum` | bigint | primary key |
| `Suffix` | string | credentials, e.g. DDS, RDH |
| `Specialty` | bigint | FK to `definition.DefNum` (category ProviderSpecialties) |
| `IsSecondary` | bool | a hygienist or other secondary provider |
| `IsNotPerson` | bool | a billing entity or placeholder, not a person |
| `CustomID` | string | a practice's own provider ID |

### `appointment`
*(Appointment.cs)*

| Column | Type | Meaning |
|---|---|---|
| `AptNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient` |
| `ProvNum` | bigint | FK to `provider`: the dentist |
| `ProvHyg` | bigint | FK to `provider`: the hygienist |
| `AptDateTime` | datetime | when it is scheduled |
| `Pattern` | string | its length, as a time pattern |
| `ClinicNum` | bigint | FK to `clinic` |
| `IsHygiene` | bool | a hygiene appointment |
| `ProcDescript` | string | the procedures booked, as text |

### `medication`
*(Medication.cs)*

| Column | Type | Meaning |
|---|---|---|
| `MedicationNum` | bigint | primary key |
| `MedName` | string | name |
| `GenericNum` | bigint | FK to `medication`: its generic |
| `Notes` | string | free text |
| `RxCui` | bigint | RxNorm concept |

### `medicationpat`
*(MedicationPat.cs)*

| Column | Type | Meaning |
|---|---|---|
| `MedicationPatNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient` |
| `MedicationNum` | bigint | FK to `medication` |
| `PatNote` | string | free text about this patient's use; would hold PHI |
| `DateStart` | date | may be empty |
| `DateStop` | date | may be empty |
| `ProvNum` | bigint | FK to `provider`: prescriber |
| `IsCpoe` | bool | prescribed here (computerised order entry) |

### `allergy`
*(Allergy.cs)*

| Column | Type | Meaning |
|---|---|---|
| `AllergyNum` | bigint | primary key |
| `AllergyDefNum` | bigint | FK to `allergydef` |
| `PatNum` | bigint | FK to `patient` |
| `Reaction` | string | free text; would hold PHI |
| `StatusIsActive` | bool | still active |

### `allergydef`
*(AllergyDef.cs)*

| Column | Type | Meaning |
|---|---|---|
| `AllergyDefNum` | bigint | primary key |
| `Description` | string | the allergen |
| `IsHidden` | bool | hidden from the list |
| `SnomedType` | enum SnomedAllergy | kind of allergy |
| `MedicationNum` | bigint | FK to `medication`, for a drug allergy |
| `UniiCode` | string | the substance's UNII code, for a non-drug allergy |

### `sheet`
*(Sheet.cs)*

| Column | Type | Meaning |
|---|---|---|
| `SheetNum` | bigint | primary key: one filled-in form, e.g. an exam form |
| `SheetType` | enum SheetTypeEnum | kind of form |
| `PatNum` | bigint | FK to `patient` |
| `DateTimeSheet` | datetime | when it was filled in |
| `Description` | string | the form's name |
| `ClinicNum` | bigint | FK to `clinic` |

### `sheetfield`
*(SheetField.cs)*

| Column | Type | Meaning |
|---|---|---|
| `SheetFieldNum` | bigint | primary key: one answer on a form |
| `SheetNum` | bigint | FK to `sheet` |
| `FieldName` | string | the field |
| `FieldValue` | string | the answer; free text can hold PHI |
| `RadioButtonGroup` | string | which question a radio answer belongs to |
| `ReportableName` | string | a stable name for reporting |

### `vitalsign`
*(Vitalsign.cs)*

| Column | Type | Meaning |
|---|---|---|
| `VitalsignNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient` |
| `BpSystolic` | int | systolic blood pressure |
| `BpDiastolic` | int | diastolic blood pressure |
| `Pulse` | int | pulse |
| `DateTaken` | date |  |

### `patientrace`
*(PatientRace.cs)*

| Column | Type | Meaning |
|---|---|---|
| `PatientRaceNum` | bigint | primary key; a patient can have several |
| `PatNum` | bigint | FK to `patient` |
| `CdcrecCode` | string | race or ethnicity code (CDC Race and Ethnicity) |

### `cdcrec`
*(Cdcrec.cs)*

| Column | Type | Meaning |
|---|---|---|
| `CdcrecNum` | bigint | primary key |
| `CdcrecCode` | string | the code |
| `HeirarchicalCode` | string | its place in the hierarchy (Open Dental's spelling) |
| `Description` | string |  |

### `site`
*(Site.cs)*

| Column | Type | Meaning |
|---|---|---|
| `SiteNum` | bigint | primary key: a place of care outside the office (school, nursing home) |
| `Description` | string |  |
| `Note` | string | free text |
| `Zip` | string | postcode |
| `PlaceService` | enum PlaceOfService | kind of place |

### `procnote`
*(ProcNote.cs)*

| Column | Type | Meaning |
|---|---|---|
| `ProcNoteNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient` |
| `ProcNum` | bigint | FK to `procedurelog` |
| `EntryDateTime` | datetime | when written |
| `Note` | string | the clinical note; would hold PHI |

### `document`
*(Document.cs; checked 2026-10-31 for #385)*

| Column | Type | Meaning |
|---|---|---|
| `DocNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient`: the patient's image folder |
| `DateCreated` | datetime | when the image was taken or added |
| `DocCategory` | bigint | FK to `definition` (category 18, ImageCats): the image folder, e.g. radiographs |
| `ImgType` | tinyint | enum ImageType: 0 document, 1 radiograph, 2 photo, 3 file, 4 attachment |
| `ToothNumbers` | string | optional tooth numbers on the image, comma separated (universal numbering) |
| `Description` | string | free text describing the image; could hold PHI |
| `FileName` | string | the image file's name; could hold PHI |

Open Dental stores the image and these fields only. It has no column for bone loss or any other reading of the
image: a dentist's reading is free text in a note, and a reading tool keeps its own results.

### `ehrmeasureevent`
*(EhrMeasureEvent.cs)*

| Column | Type | Meaning |
|---|---|---|
| `EhrMeasureEventNum` | bigint | primary key |
| `DateTEvent` | datetime |  |
| `EventType` | enum EhrMeasureEventType | e.g. a tobacco use assessment |
| `PatNum` | bigint | FK to `patient` |
| `MoreInfo` | string | free text; would hold PHI |
| `CodeValueResult` | string | the result, e.g. a SNOMED smoking status |
| `DateStartTobacco` | date | when tobacco use began, if known |
| `TobaccoCessationDesire` | byte | 0–10 |

### `patfield`
*(PatField.cs)*

| Column | Type | Meaning |
|---|---|---|
| `PatFieldNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient` |
| `FieldName` | string | a practice-defined patient field, e.g. research consent |
| `FieldValue` | string | its value |

### `snomed`
*(Snomed.cs)*

| Column | Type | Meaning |
|---|---|---|
| `SnomedNum` | bigint | primary key |
| `SnomedCode` | string | the code |
| `Description` | string |  |

## Treatment plans: one planned procedure, many copies (added for #377)

From the same classes:
- A planned procedure is a `procedurelog` row with `ProcStatus` 1 (TP). It is the one record of the plan.
- Saving a treatment plan (`treatplan`) copies each planned procedure into `proctp`. A patient can have several
  plans saved on one date (alternatives offered to the patient), and new plans saved at later exams copy the same
  planned procedure again. So one `procedurelog` row can have many `proctp` copies. `proctp.ProcNumOrig` points
  back to it.
- The `proctp` columns `ProcCode`, `Descript`, `ToothNumTP`, `Dx` and `Prognosis` are text saved with the plan,
  not keys. They aren't joined to `procedurecode` or `definition`, and they can be edited, so a copy can differ
  from the procedure it came from. `procedurelog` instead holds keys: `CodeNum` → `procedurecode`, `Dx` →
  `definition.DefNum`.
- When the planned procedure is done, the same `procedurelog` row is set complete (`ProcStatus` 2,
  `DateComplete`). A plan that is never followed leaves it at 1.

So: count planned procedures from `procedurelog`, use `proctp` only for when and how often each was planned, and
check the copies against the original instead of trusting them.

## Diagnosis lists change

`definition` rows of category Diagnosis are whatever the practice entered. When a practice moves from an older
periodontal classification to the 2017 AAP/EFP one, it adds new items and stops using (or hides, `IsHidden`) the
old ones; old procedures keep pointing at the old items. A mapping from items to periodontal / other / none must
therefore cover every list the practice has used, and the switch is a date range, not a day.

## What this changes in spec 029

1. **CAL is computed, not read**: probing + gingival margin per site, decoding the 100+ convention (plan
   step 2 and the silver features).
2. **Bleeding** comes from bit 1 of sequence type 6, not from a column of its own.
3. **Two kinds of diagnosis on an extraction:**
   - `Dx`, the practice's own diagnosis list, joined to `definition` (category Diagnosis), which is free text;
   - `DiagnosticCode` with `IcdVersion`, where a standard ICD code was entered.

   The practice's list is the main source. ICD codes are filled only for medical claims, so the generator writes
   them on a small share, and the silver step maps the practice's list by a declared lookup (a parameter, since
   every practice's list differs), using the ICD code only to check it (#377).
4. **A third way a tooth is missing**: an extraction recorded with `ProcStatus` 4, "Existing Other Prov"
   (done elsewhere, before this practice). It has a code and a tooth, usually no diagnosis and often no real
   date. It joins "missing at the first exam" among the teeth the model is applied to.
5. **Smoking** is `patient.SmokingSnoMed` (a SNOMED code). **Diabetes** is a `disease` row whose `diseasedef`
   has an ICD-10 code in E10–E11.
6. **Office**: `ClinicNum` on `patient` and `procedurelog` is the office for the per-office consistency check
   (FR-009).

## Why teeth are missing: published reasons for extraction by age (US7, #429)

The generator needs, for teeth already missing at a patient's first visit, how often the reason is periodontitis
and how often something else (caries, fracture, orthodontic, failed treatment, other), by age. Every figure below was
checked against the paper (PubMed record, and the PMC full text where open); none is invented. References items
63-67 in [docs/references.md](../../docs/references.md).

### The source used: Suzuki et al. 2022 (Japan, second nationwide survey)

Suzuki S, Sugihara N, Kamijo H, Morita M, Kawato T, Tsuneishi M, Kobayashi K, Hasuike Y, Sato T. *Reasons for tooth
extractions in Japan: the second nationwide survey.* Int Dent J 2022;72(3):366-372.
doi:10.1016/j.identj.2021.05.008, PMID 34193342, PMC9275201.

- **Population:** 2,345 of 5,250 dentists sampled systematically (every 10th) from the Japan Dental Association's
  2018 directory (44.8%) recorded every permanent tooth extracted in one week, 4-10 June 2018: 7,809 teeth from
  6,398 patients aged 10-106 (194 of 8,003 left out for missing data).
- **Reasons** (six groups): caries, periodontal disease, fracture, orthodontics, impacted teeth, others.
- **Table 2** gives teeth by reason, age band and sex. Pooling men and women (counts added from Table 2, read in the
  PMC full text on 2026-11-01) for the ages the synthetic patients have (25-85):

| Age band | Caries | Periodontal | Fracture | Orthodontic | Impacted | Others | Teeth, impacted left out | Periodontal share |
|---|---|---|---|---|---|---|---|---|
| 25-34 | 278 | 31 | 32 | 20 | 126 | 127 | 488 | 0.064 |
| 35-44 | 290 | 120 | 63 | 8 | 81 | 94 | 575 | 0.209 |
| 45-54 | 350 | 301 | 184 | 4 | 37 | 75 | 914 | 0.329 |
| 55-64 | 340 | 627 | 270 | 0 | 16 | 70 | 1,307 | 0.480 |
| 65-74 | 472 | 1,008 | 443 | 0 | 5 | 93 | 2,016 | 0.500 |
| 75+ (75-79, 80-84, 85+) | 469 | 841 | 402 | 1 | 3 | 77 | 1,790 | 0.470 |

  For example, 25-34 is men 150/18/18/0/54/55 plus women 128/13/14/20/72/72. The paper's totals: periodontal 40.4%
  (men) and 34.9% (women), caries 30.2% and 29.0%, fracture 16.8% and 19.2%; periodontal disease predominant over 55.
- **What the generator takes:** the periodontal share by band (last column), as `open_dental.ENTRY_PERIO_SHARE_BY_AGE`.
  Impacted teeth are left out of the denominator because they are mostly third molars, which the label and the stage
  count leave out by default (spec Edge Cases); the paper doesn't say how many third molars fall under other reasons
  (caries is the main reason for upper third molars, 51.1%), so some third molars stay in the denominator.
  Everything other than periodontal (caries, fracture, orthodontic, others) is `other` in the answer key.

### Other sources, and where they disagree

- **Aida J, Ando Y, Akhter R, Aoyama H, Masui M, Morita M.** *Reasons for permanent tooth extractions in Japan.*
  J Epidemiol 2006;16(5):214-219. doi:10.2188/jea.16.214, PMID 16951541, PMC7683702. The first Japanese survey:
  2,001 dentists (39.1%), one week of February 2005, 9,115 teeth from 7,499 patients. Caries 32.7% and fracture of
  teeth weakened by caries or endodontics 10.6% (43.3% together), periodontal disease 41.8%; caries or fracture
  common in every age group over 15, periodontal disease predominant over 45 (abstract). Same pattern as Suzuki;
  its age breakdown is a figure, not a table, so Suzuki's counts are used.
- **Murray H, Locker D, Kay EJ.** *Patterns of and reasons for tooth extractions in general dental practice in
  Ontario, Canada.* Community Dent Oral Epidemiol 1996;24(3):196-200. doi:10.1111/j.1600-0528.1996.tb00841.x,
  PMID 8871019. 128 dentists, 6,143 patients in a reference week: periodontal disease 35.9% of teeth lost, caries
  28.9%; orthodontics the main reason in childhood, periodontal disease above caries after 40 (abstract). Agrees with
  the Japanese surveys on the age pattern.
- **McCaul LK, Jenkins WM, Kay EJ.** *The reasons for extraction of permanent teeth in Scotland: a 15-year follow-up
  study.* Br Dent J 2001;190(12):658-662. doi:10.1038/sj.bdj.4801068, PMID 11453155. 352 general dental
  practitioners (82.8%), one week in 1999: caries the commonest reason in every age group over 20, where in 1984
  periodontal disease had been the main reason over 40 (abstract). **Disagrees** with the above after 40.
- **Chestnutt IG, Binnie VI, Taylor MM.** *Reasons for tooth extraction in Scotland.* J Dent 2000;28(4):295-297.
  doi:10.1016/s0300-5712(99)00069-x, PMID 10722904. 139 practitioners, one week of November 1994, 917 teeth from
  613 patients: caries 51%, periodontal disease 21%, orthodontics 11%, failed endodontics 4%, trauma, pericoronitis
  and other 5.5%, patient request 7.5%; the periodontal share rose from 31 to 60 and fell after (abstract).
- **Broers DLM, Dubois L, de Lange J, Su N, de Jongh A.** *Reasons for tooth removal in adults: a systematic
  review.* Int Dent J 2022;72(1):52-57. doi:10.1016/j.identj.2021.01.011, PMID 33648772, PMC9275356. Three studies
  (Greece twice, Croatia; 4,396 extractions, adults, third molars left out): caries 36.0-55.3%, periodontitis
  24.8-38.1%, trauma 0.8-4.4%, periapical disease 7.3-19.1%, orthodontics 2.5-7.2%, other 4.5-9.2%, patient request
  3.6-5.9% (abstract and full text). No age breakdown.

**Choice and reason.** The sources agree that caries and its sequelae dominate young adults' extractions and that
the periodontal share rises with age; they disagree on how far (periodontal the main reason after 40-55 in Japan
and Ontario; caries still the main one in Scotland 1999 and in the review's three studies). Suzuki et al. 2022 is
used because it is the only one with a full table of counts by age band that could be checked here, it is the most
recent, it is a national sample, and its categories map onto ours. Its overall periodontal share (37.6% of all 7,809 teeth, sexes pooled) is at
the top of the review's range (24.8-38.1%), so the synthetic mix leans periodontal; a lower share is a parameter away.

### Caveats

- **Extractions in one week, applied to teeth already missing.** The surveys count extractions done at a given age
  (incidence). A tooth missing at a first visit at 60 may have been lost at 30. Using the share for the patient's
  current age band is an approximation, and probably overstates the periodontal share for older patients, whose
  earlier losses were more often caries.
- **Japan, not the US.** No US survey with age bands was found; the age pattern matches Ontario's.
- **Counts per patient are not calibrated.** The synthetic perio losses at entry come from the spec 006 charts
  (about 0.2-0.35 teeth per patient, flat with age), which this story doesn't change. Matching the share therefore
  gives more non-periodontal teeth to younger patients than older ones; the share, not the count, is what the
  evaluation needs.
- **Which teeth.** `Params.entry_other_tooth_weights` (molars 3, premolars 2, canines and incisors 1) is this repo's
  choice, not a cited figure. Suzuki et al. give reasons by tooth type only as a figure (in the text: the lower first
  molar is most often extracted for fracture, 34.7%; the upper third molar for caries, 51.1%), with no table to set
  the weights from.
