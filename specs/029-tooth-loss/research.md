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

## Insurance (spec 032 US6, #445)
Checked in the same source (`24_3`, `d804c19`, `OpenDentBusiness/TableTypes/`) on 2026-11-01. A patient's coverage
is `patplan` (one row per plan covering them, ordered by `Ordinal`), which points to a subscription (`inssub`: who
holds the plan), which points to the plan (`insplan`), which points to its carrier (`carrier`). Open Dental stores
no "private or public" type: the plan's `FilingCode` (an e-claims filing code in its own table) or the carrier is
what a practice reads it from. The synthetic extract reads it from the carrier through a declared lookup
(`open_dental.CARRIER_INSURANCE_TYPE`); `FilingCode` and its table are left out.

### `carrier`
*(Carrier.cs)*

| Column | Type | Meaning |
|---|---|---|
| `CarrierNum` | bigint | primary key |
| `CarrierName` | string | name of the carrier |
| `Address` | string |  |
| `Address2` | string | second line of address |
| `City` | string |  |
| `State` | string | 2 characters in the US |
| `Zip` | string | postcode |
| `Phone` | string |  |
| `ElectID` | string | electronic payer ID for e-claims |
| `IsHidden` | bool | hidden from the pick list |

### `insplan`
*(InsPlan.cs)*

| Column | Type | Meaning |
|---|---|---|
| `PlanNum` | bigint | primary key |
| `GroupName` | string | optional |
| `GroupNum` | string | optional |
| `PlanType` | string | blank percentage (default), `p` PPO percentage, `f` flat copay, `c` capitation |
| `CarrierNum` | bigint | FK to `carrier` |
| `IsMedical` | bool | medical rather than dental insurance |
| `IsHidden` | bool | hidden from the pick list |
| `MonthRenew` | byte | month 1–12 the plan renews; 0 calendar year |

### `inssub`
*(InsSub.cs)*

| Column | Type | Meaning |
|---|---|---|
| `InsSubNum` | bigint | primary key |
| `PlanNum` | bigint | FK to `insplan` |
| `Subscriber` | bigint | FK to `patient.PatNum`: who holds the plan |
| `DateEffective` | date | when the plan took effect; 0001-01-01 if not set |
| `DateTerm` | date | when it ended; 0001-01-01 if not set |
| `ReleaseInfo` | bool | release of information signature on file |
| `AssignBen` | bool | assignment of benefits signature on file |
| `SubscriberID` | string | the number the insurer assigned |

### `patplan`
*(PatPlan.cs)*

| Column | Type | Meaning |
|---|---|---|
| `PatPlanNum` | bigint | primary key |
| `PatNum` | bigint | FK to `patient`: who is covered |
| `Ordinal` | byte | 1 primary, 2 secondary, ...; 0 is not used |
| `IsPending` | bool | coverage pending |
| `Relationship` | int | Relat enum: 0 self, 1 spouse, 2 child, ... (the enum's own file was not read; the extract uses 0 and 1 only) |
| `PatID` | string | optional patient ID that overrides the subscriber ID on e-claims |
| `InsSubNum` | bigint | FK to `inssub` |

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

### How the generator reaches the shares

The spec 006 mouth decides the periodontal losses at entry; this story adds, per patient, a Poisson number of
non-periodontal ones with mean `Params.entry_other_teeth_by_age` for the age band. For the share `s` in a band
where the mean periodontal count per patient is `m`, the mean is `m (1 - s) / s`. `m` was measured with the
non-periodontal means at zero, pooled over generator seeds 101-105 at 6,000 patients each (30,000 patients):

| Age band | `m`, periodontal teeth at entry per patient | Target share `s` | Mean non-periodontal teeth (default) |
|---|---|---|---|
| 25-34 | 0.247 | 0.064 | 3.61 |
| 35-44 | 0.253 | 0.209 | 0.96 |
| 45-54 | 0.264 | 0.329 | 0.54 |
| 55-64 | 0.302 | 0.480 | 0.33 |
| 65-74 | 0.285 | 0.500 | 0.28 |
| 75+ | 0.311 | 0.470 | 0.35 |

The periodontal counts are heavy-tailed (a stage IV mouth loses many teeth at once), so one seed's share in a band
can sit 0.03-0.05 from the target; `test_open_dental.py` checks a 6,000-patient extract within 0.05.

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

## Shared risk factors: smoking and diabetes on tooth loss for other reasons (US8, #433)

US7 drew the non-periodontal teeth missing at entry from age and tooth type only. The generator needs, for a
patient who smokes or has diabetes, how much more often teeth are lost for reasons other than periodontitis
(caries and its sequelae, fracture, failed treatment). Every figure below was checked against the paper (PubMed
record, and the PMC full text where named) on 2026-11-01; none is invented. References items 68-71 in
[docs/references.md](../../docs/references.md).

**What the sources say, in one line:** smoking and diabetes raise tooth loss overall, but nearly all of that excess
is periodontal; for caries-related loss the published effects are small and not statistically significant. The
generator uses the point estimates, so non-periodontal loss rises a little with smoking and diabetes, as the
sources say, and no more.

### Smoking: Mai et al. 2013 (Buffalo OsteoPerio Study), the one cause-specific source

Mai X, Wactawski-Wende J, Hovey KM, LaMonte MJ, Chen C, Tezal M, Genco RJ. *Associations between smoking and tooth
loss according to the reason for tooth loss: the Buffalo OsteoPerio Study.* J Am Dent Assoc 2013;144(3):252-265.
doi:10.14219/jada.archive.2013.0112, PMID 23449901, PMC3842224.

- **Population:** 1,106 postmenopausal women (Women's Health Initiative, Buffalo, NY), oral examination for missing
  teeth (third molars aside) and self-reported reason for each loss; smoking by questionnaire.
- **Outcome groups:** 206 women with no tooth loss (reference), 108 with any loss to periodontal disease, 792 with
  loss to caries and none to periodontal disease (methods: "those who lost any teeth due to caries (but none due to
  PD)"), so the caries group is exactly a non-periodontal-loss group.
- **Table 3, multivariable-adjusted ORs** (age, education, income, BMI, diabetes history, calcium supplement use,
  dental visit frequency), tooth loss due to caries against no tooth loss:

| Exposure | OR (95% CI), caries loss | OR (95% CI), periodontal loss, for contrast |
|---|---|---|
| current smoker (n = 23 in the caries group) | 0.91 (0.38-2.18) | 4.07 (1.27-13.03) |
| ever smoker | 1.19 (0.86-1.65) | 3.09 (1.78-5.34) |
| packs a day < 1 | 1.05 (0.72-1.55) | 2.24 (1.15-4.37) |
| packs a day 1 to < 2 | 1.38 (0.86-2.21) | 3.17 (1.56-6.45) |
| packs a day 2 or more | 1.41 (0.59-3.39) | 10.39 (3.41-31.68) |
| pack-years 26 or more | 1.46 (0.87-2.44) | 6.83 (3.40-13.72) |

  P for trend over packs a day, caries: 0.220. The authors: "no significant associations between smoking and tooth
  loss due to caries".
- **What the generator takes:** the packs-a-day ORs, since `synthetic.draw_risk` gives cigarettes a day:
  `Params.entry_other_smoking_ratios = ((1, 1.05), (20, 1.38))`, i.e. 1-19 cigarettes a day (under a pack) 1.05, 20
  or more (a pack or more; the synthetic maximum is 30, so the 2-pack category doesn't arise) 1.38. Current smokers
  only; the synthetic patient has no former-smoker history for the rate (the extract's ex-smoker SNOMED code is
  drawn for display only).

**Other smoking sources, all-cause, for context.**
- Ojima M, Hanioka T, Tanaka K, Aoyama H. *Cigarette smoking and tooth loss experience among young adults: a
  national record linkage study.* BMC Public Health 2007;7:313. doi:10.1186/1471-2458-7-313, PMID 17976246,
  PMC2186324. Japan, 1999 national surveys linked, 1,314 adults aged 20-39: current smoking and 1+ tooth lost,
  adjusted OR 2.21 (1.40-3.50) in men and 1.70 (1.13-2.55) in women; current smoking and decayed teeth 1.67
  (1.28-2.20) (abstract). At these ages most tooth loss is not periodontal (Suzuki 2022, Table 2: 6% periodontal at
  25-34), so this points to a larger smoking effect on non-periodontal loss in young adults than Mai et al. found
  in older women. It is all-cause and cross-sectional, so it is recorded, not used; a larger ratio is a parameter
  away.
- Hanioka T, Ojima M, Tanaka K, Matsuo K, Sato F, Tanaka H. *Causal assessment of smoking and tooth loss: a
  systematic review of observational studies.* BMC Public Health 2011;11:221. doi:10.1186/1471-2458-11-221, PMID
  21477320. 8 high-quality studies, 58,755 people: all reported significant, usually moderate, associations with
  all-cause tooth loss (abstract). No cause-specific figure.

### Diabetes: no cause-specific incidence ratio found; the all-cause adjusted OR is used

- **Cause-specific, within extractions:** Suzuki S, Sugihara N, Kamijo H, Morita M, Kawato T, Tsuneishi M, Kobayashi
  K, Hasuike Y, Sato T. *Self-reported diabetes mellitus and tooth extraction due to periodontal disease and dental
  caries in the Japanese population.* Int J Environ Res Public Health 2021;18(17):9024. doi:10.3390/ijerph18179024,
  PMID 34501613, PMC8430558. The 2018 Japanese survey (the same as Suzuki 2022, US7), patients over 40: 4,625
  extracted teeth, 3,750 patients, third molars left out. Table 4, OR that an extracted tooth was extracted for
  caries, diabetes against none: 0.70 (0.58-0.86) unadjusted; 0.85 (0.68-1.06) adjusted for sex, age, location,
  number of teeth, tooth type and smoking (Model 4). For periodontal disease: 1.42 (1.17-1.72) and 1.23 (1.01-1.50).
  The authors: "an association with dental caries was not observed". This compares reasons among extracted teeth,
  not the rate of loss per patient, so it can't be used as a rate ratio; it says the extra extractions in diabetes
  are mostly periodontal.
- **All-cause, adjusted:** Ahmadinia AR, Rahebi D, Mohammadi M, Ghelichi-Ghojogh M, Jafari A, Esmaielzadeh F,
  Rajabi A. *Association between type 2 diabetes (T2D) and tooth loss: a systematic review and meta-analysis.* BMC
  Endocr Disord 2022;22(1):100. doi:10.1186/s12902-022-01012-8, PMID 35418054, PMC9006550. 22 studies: pooled OR
  1.87 (1.62-2.13) unadjusted and 1.20 (1.10-1.30) adjusted; cohort studies 1.29 (1.07-1.51), cross-sectional 1.15
  (1.06-1.23) (abstract).
- **All-cause, unadjusted:** Weijdijk LPM, Ziukaite L, Van der Weijden GAF, Bakker EWP, Slot DE. *The risk of tooth
  loss in patients with diabetes: a systematic review and meta-analysis.* Int J Dent Hyg 2022;20(1):145-166.
  doi:10.1111/idh.12512, PMID 33973353. 10 studies, risk ratio 1.63; higher with poor control (abstract).
- **What the generator takes, and why:** `Params.entry_other_diabetes_ratio = 1.20`, the adjusted all-cause OR, for
  HbA1c 6.5% or more (the extract's own rule for listing type 2 diabetes). No source gives the rate of
  non-periodontal tooth loss per patient by diabetes. The all-cause figure includes periodontal loss, which diabetes
  raises (Suzuki 2021), so 1.20 is an upper bound for non-periodontal loss; Suzuki 2021's within-extraction OR of
  0.85 for caries says the true ratio is lower, possibly near 1. The upper bound is used because the point of US8 is
  that the two kinds of loss can share patients; 1.0 is a parameter away. One ratio for controlled and uncontrolled
  diabetes: no source gives a cause-specific split by control.

### Dental attendance and socioeconomic status: recorded, not modelled

- Akhter R, Hassan NM, Aida J, Zaman KU, Morita M. *Risk indicators for tooth loss due to caries and periodontal
  disease in recipients of free dental treatment in an adult population in Bangladesh.* Oral Health Prev Dent
  2008;6(3):199-207. PMID 19119574. 868 teeth, 582 patients: extraction for caries associated with dental attendance
  pattern (P = 0.004); for periodontal disease with education (P = 0.018) and smoking (P = 0.032) (abstract). The
  abstract gives P values, not effect sizes, and the full text wasn't available here.
- Mai et al. 2013 adjust for dental visit frequency and income but don't report their own ORs.
- The synthetic patient has no attendance or deprivation attribute (`synthetic.draw_risk` gives cigarettes a day and
  HbA1c only), so neither enters the rate. Adding one means a new seeded patient attribute and a source with an
  effect size; it is left for a follow-up.

### How the generator applies them

For a patient with rate ratio `r` (smoking ratio × diabetes ratio), the Poisson mean is `mean_band × r / r̄`, where
`r̄` is the mean of `r` over `Params.entry_other_norm_draws` (20,000) patients drawn by `synthetic.draw_risk` on
its own fixed stream. Smoking and diabetes are drawn independently of age, so `r̄` is the same in every band, and
dividing by it keeps each band's mean count, and so its periodontal share (US7), where it was. With the defaults
`r̄` is 1.040 (`entry_other_rate_norm`). An OR is used as a rate ratio: for a common outcome the OR overstates the
risk ratio, which here works against the small effects found, so the generator is, if anything, generous to the
shared risk.

**Checked on generated extracts (SYNTHETIC).** Pooled over generator seeds 13 and 101-107 at 6,000 patients each
(48,000 patients), the mean non-periodontal count per patient by band is 3.61, 0.96, 0.55, 0.33, 0.27 and 0.35
(declared 3.61, 0.96, 0.54, 0.33, 0.28, 0.35), and the periodontal share is 0.062, 0.194, 0.332, 0.490, 0.534 and
0.474 against the targets 0.064, 0.209, 0.329, 0.480, 0.500, 0.470 (before US8, the same seeds: 0.055, 0.188, 0.344,
0.483, 0.536, 0.470). One 6,000-patient extract is noisier: at seed 13 the 65-74 and 75+ bands sit 0.07 from target
after the change, because the periodontal counts are heavy-tailed and the extract is a fresh sample (the main stream
moves with the number of teeth present), so `test_open_dental.py` pools seeds 13-15 (within 0.03). On the seed 13
extract, the non-periodontal count against the age band's mean (observed / expected) is 1.13 for daily smokers, 1.06
for occasional smokers, 1.15 for patients with diabetes listed and 0.97 for never-smokers without it; the defaults
give 1.20, 1.03, 1.18 and 0.96 in expectation.

### Caveats

- **Weak, not significant.** None of the non-periodontal effects used is statistically significant on its own; they
  are the best point estimates available, not established effects.
- **Women over 50, USA (smoking); Japan (diabetes within extractions); pooled, mostly Asian and European (diabetes
  all-cause).** Applied to synthetic patients aged 25-85 of both sexes.
- **Prevalence ORs as rate ratios on a count.** Mai et al. model any caries loss against none; the generator scales
  the mean count.
- **Expected effect on the model:** small. The non-periodontal teeth still come mostly in young mouths (US7's
  shares), and smoking and diabetes are uncommon in the synthetic patients (about 8% smoke 10 or more a day; about
  8% have HbA1c 6.5% or more), so the missing-at-entry AUC is expected to fall only a little.
