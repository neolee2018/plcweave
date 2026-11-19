# V002 bench demonstration: independent PDF visual review

Status: **PASS**

Task: `PW-20261022-V002-HIL02-PDF`; owner: `independent-pdf-judge`; deadline: 30 minutes.

Completed UTC: 2026-10-22T10:39:37.864245+00:00

All 50 page images were individually displayed and visually inspected: test document pages 1-44 and instruction-list pages 1-6. No table overflow, cut text, overlap, garbled glyphs, isolated headings or page-number errors were found. Long tables continue with repeated headers; no row content was lost. Neither PDF contains a table of contents.

The test document page 32 explicitly preserves all 55 original hardware cases as UNVERIFIED. Its separate 28 frozen supplemental procedures are reported as 24 PASS / 4 UNVERIFIED. Page 33 clearly labels individual event intervals; an individual event PASS does not upgrade the overall uncertain procedure. Both cover banners and final scope notices preserve full hardware/electrical acceptance as UNVERIFIED.

This review assesses presentation and scope wording; it does not independently approve PLC behavior or hardware acceptance.

## PDF identity

| PDF | Pages | SHA256 |
|---|---:|---|
| Blackbox-Test-Cases_EN.pdf | 44 | `01dd33e3e5f29e8aa02eaaeb3f4ddbf5ec4da9d58e616e775fbcc553be884f32` |
| L01S-Water-PI-il-annotated_EN.pdf | 6 | `7edfdaeb8d500af62fe66582acac6009b5a6432cd17d15eb675b44b9f0b95ec3` |

## Per-page visual inspection

| PDF | Page | Result | Observation |
|---|---:|---|---|
| Blackbox-Test-Cases_EN.pdf | 1 | PASS | Cover, setup gate and scope banner fit; section 2 has its introductory paragraph; footer 1/44. |
| Blackbox-Test-Cases_EN.pdf | 2 | PASS | Register map tables fit; rows and bottom footer are separate. |
| Blackbox-Test-Cases_EN.pdf | 3 | PASS | Register map continuation has repeated header and readable cells. |
| Blackbox-Test-Cases_EN.pdf | 4 | PASS | Register map and frozen replay introduction fit; heading 3 stays with text. |
| Blackbox-Test-Cases_EN.pdf | 5 | PASS | STD-001 to STD-004: headings, expected-value tables and retest fields fit. |
| Blackbox-Test-Cases_EN.pdf | 6 | PASS | STD-005 to STD-008: tables and retest fields fit. |
| Blackbox-Test-Cases_EN.pdf | 7 | PASS | STD-009 to STD-011: command table fits without clipping. |
| Blackbox-Test-Cases_EN.pdf | 8 | PASS | STD-012 and STD-013: readable tables with all retest fields. |
| Blackbox-Test-Cases_EN.pdf | 9 | PASS | STD-014 and STD-015: readable tables with all retest fields. |
| Blackbox-Test-Cases_EN.pdf | 10 | PASS | STD-016 rows 1-23: dense table remains readable; continuation follows. |
| Blackbox-Test-Cases_EN.pdf | 11 | PASS | STD-016 rows 24-25 and STD-017: continuation has repeated column header. |
| Blackbox-Test-Cases_EN.pdf | 12 | PASS | STD-018 rows 1-22: long table stays inside printable area; continuation follows. |
| Blackbox-Test-Cases_EN.pdf | 13 | PASS | STD-018 continuation, STD-019 and STD-020: no cut rows or isolated headings. |
| Blackbox-Test-Cases_EN.pdf | 14 | PASS | STD-021 and STD-022: complete tables and retest fields fit. |
| Blackbox-Test-Cases_EN.pdf | 15 | PASS | STD-023 and STD-024: full tables fit above footer. |
| Blackbox-Test-Cases_EN.pdf | 16 | PASS | STD-025 and STD-026: complete tables and retest fields fit. |
| Blackbox-Test-Cases_EN.pdf | 17 | PASS | STD-027 and STD-028: PI tables fit with readable expected values. |
| Blackbox-Test-Cases_EN.pdf | 18 | PASS | STD-029 and STD-030: timing and route tables fit. |
| Blackbox-Test-Cases_EN.pdf | 19 | PASS | STD-031 and STD-032: timer tables fit; heading and content remain together. |
| Blackbox-Test-Cases_EN.pdf | 20 | PASS | STD-033 and STD-034: both long tables fit above footer. |
| Blackbox-Test-Cases_EN.pdf | 21 | PASS | STD-035 and STD-036: tables and fields have clear separation. |
| Blackbox-Test-Cases_EN.pdf | 22 | PASS | STD-037 and STD-038: tables and fields fit. |
| Blackbox-Test-Cases_EN.pdf | 23 | PASS | STD-039 and STD-040: stop-state tables fit. |
| Blackbox-Test-Cases_EN.pdf | 24 | PASS | STD-041 and STD-042: complete tables and retest fields fit. |
| Blackbox-Test-Cases_EN.pdf | 25 | PASS | STD-043 to STD-045: dense page remains readable with no cut rows. |
| Blackbox-Test-Cases_EN.pdf | 26 | PASS | STD-046 and STD-047: complete cancellation/restart tables fit. |
| Blackbox-Test-Cases_EN.pdf | 27 | PASS | STD-048 to STD-050: complete echo/diagnostic tables fit. |
| Blackbox-Test-Cases_EN.pdf | 28 | PASS | STD-051 and STD-052: complete tables and retest fields fit. |
| Blackbox-Test-Cases_EN.pdf | 29 | PASS | STD-053 to STD-055: complete tables and retest fields fit. |
| Blackbox-Test-Cases_EN.pdf | 30 | PASS | Acceptance-oracle section: paragraphs readable; REL-08 continues as normal text. |
| Blackbox-Test-Cases_EN.pdf | 31 | PASS | REL-08 continuation and REL-09/10 fit; validation scope explicitly preserves hardware UNVERIFIED. |
| Blackbox-Test-Cases_EN.pdf | 32 | PASS | 28-procedure result table fits: PASS=24, UNVERIFIED=4; original 55 hardware cases explicitly UNVERIFIED. |
| Blackbox-Test-Cases_EN.pdf | 33 | PASS | Event interval table readable; individual first-frequency PASS does not conceal overall supplemental UNVERIFIED; cleanup and evidence contract fit. |
| Blackbox-Test-Cases_EN.pdf | 34 | PASS | Supplemental section 7 and INIT-001/002/003 fit; INIT-003 parameter table continues with repeated header. |
| Blackbox-Test-Cases_EN.pdf | 35 | PASS | INIT-003 continuation and INIT-004/005/006 fit; table continuation uses repeated headers. |
| Blackbox-Test-Cases_EN.pdf | 36 | PASS | INIT-006 continuation and INIT-007/008/009 fit; no cut rows at page bottom. |
| Blackbox-Test-Cases_EN.pdf | 37 | PASS | INIT-009 continuation, INIT-010 and steady STD-016 rows 1-12 fit. |
| Blackbox-Test-Cases_EN.pdf | 38 | PASS | Steady STD-016 continuation and steady STD-024 rows 1-9 fit with repeated headers. |
| Blackbox-Test-Cases_EN.pdf | 39 | PASS | Steady STD-024 continuation, STD-025/048 and command STD-011 fit. |
| Blackbox-Test-Cases_EN.pdf | 40 | PASS | Command STD-012/013/014 and start of STD-015 fit; continuation has context and table header. |
| Blackbox-Test-Cases_EN.pdf | 41 | PASS | Command STD-015 continuation, STD-019/020 and start of STD-021 fit. |
| Blackbox-Test-Cases_EN.pdf | 42 | PASS | Command STD-021 continuation, STD-022, zero-saturation and gate prerequisite tables fit. |
| Blackbox-Test-Cases_EN.pdf | 43 | PASS | Gate continuation, two-cycle timer and cancel procedure start fit; no orphan headings. |
| Blackbox-Test-Cases_EN.pdf | 44 | PASS | Cancel continuation and jitter procedure fit; final scoped-results UNVERIFIED notice and footer 44/44 are legible. |
| L01S-Water-PI-il-annotated_EN.pdf | 1 | PASS | Cover scope banner and initialization table rows 1-24 fit; banner says 24 PASS/4 UNVERIFIED and original hardware UNVERIFIED. |
| L01S-Water-PI-il-annotated_EN.pdf | 2 | PASS | Initialization continuation and global-clock/setting sections fit; all table headers repeated. |
| L01S-Water-PI-il-annotated_EN.pdf | 3 | PASS | Setting continuation, signed-input and valid-mode sections fit without clipped instructions. |
| L01S-Water-PI-il-annotated_EN.pdf | 4 | PASS | Valid-mode continuation, stop and wake/pre-sleep timer sections fit. |
| L01S-Water-PI-il-annotated_EN.pdf | 5 | PASS | Final-normal and integer PI sections fit with readable operands; no orphan heading. |
| L01S-Water-PI-il-annotated_EN.pdf | 6 | PASS | PI continuation and physical route section include END row 176; final UNVERIFIED scope notice and footer 6/6 fit. |

## Issues and cleanup

Issues: none. PDF SHA256 values match the parent-provided final identities. Footer strings were independently checked on every PDF page.

Only this Markdown report and its JSON companion were written. No serial ports, background processes, GUI sessions or temporary files were created. PDF/HTML files, PLC source, tests and frozen inputs were not modified. Read-only PDF handles were closed.
