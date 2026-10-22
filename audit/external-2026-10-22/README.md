# External audit, 22 October 2026

An independent reviewer audited this repository at `11eb119` together with safety-governor and
found three failures here (his findings 3, 4 and 5). This folder keeps the exchange on the record,
criticism included.

| File | What it is |
|---|---|
| [MEMO.md](MEMO.md) | The reviewer's memo, verbatim and unedited (it covers all three repositories) |
| [RESPONSE.md](RESPONSE.md) | Our answer, finding by finding, with the fixes and tests |
| `repro_hs.py` | Findings 3, 4 and 5: `PYTHONPATH=. python3 audit/external-2026-10-22/repro_hs.py` prints REPRODUCED on `11eb119` and NOT reproduced after the fix |
| `repro_rollback.py` | The extra hole found while fixing 5: the gate reloading an older signed policy |

The regressions are `tests/test_audit_2026_10_22.py`: eleven tests, nine of which fail on `11eb119`.
The full record, with the governor's findings and the research recomputation, is in safety-governor:
`audit/external-2026-10-22/` and section 9 of `docs/REVIEW-2026-10-22-fact-check.md`.
