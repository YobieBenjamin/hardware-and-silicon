# From problem to code to silicon: how every audit finding gets fixed

The goal is in `GOAL.md`. The governor is meant to be the mechanism that stops bad actions from AI, separate from AI, and possibly mandated on
every AI server. So every problem an audit finds is handled the same way, in the same order, with a test at each
step. Nothing counts as fixed because someone says so.

## The loop

1. **Catalog.** The adversarial audit writes `PROBLEM-CATALOG.tsv`: one row per problem, with severity, scale, the
   attacker, where it is, the evidence, and a failing test (prompt section 5).
2. **Register.** The orchestrator gives each problem a registered name in LABELS.md under the existing `REVIEW-`
   family (review findings), with the plain-sentence title as its meaning. No new prefix is invented. The catalog
   row, the issue and every commit that touches it carry that name.
3. **Reproduce.** The failing test from the audit goes into the repository first, marked as expected to fail, so
   the problem is pinned before anyone touches the design. A problem that cannot be reproduced in code is written
   down as such, with what would reproduce it (hardware, a board, an NDA document).
4. **Fix in code.** The fix goes into the simulation (`govsim/`) and the reference stack (`hardware_ref/`), smallest
   change first. The failing test now passes, every other test still passes, and mutation testing shows the new
   test kills the mutants that would reopen the problem.
5. **Prove.** Where the property is about the hard core, add or extend a proof: the abstract machine (`proofs/`)
   and the formal proofs on the Verilog (`python -m rtl.formal`), with a mutant that the proof must catch.
6. **Verify fresh.** A new auditor, with no knowledge of the fix, re-runs the attack. The row is closed only when
   that attack fails.
7. **Plan for silicon.** Each closed row states what it needs in hardware: an RTL change, a new register or fuse, a
   check in the hard core, a sideband or board change, a rack or fleet protocol. These feed the roadmap to tape-out
   (safety-governor `docs/22-roadmap-to-tapeout.md`) in this order:

   | Stage | What it proves | Where |
   |---|---|---|
   | RTL | the fix exists in the governor's Verilog and passes the formal proofs | `rtl/`, `rtl/formal/` |
   | FPGA | the fix works in a real clocked design beside a real GPU, with measured cost and false-halt rate | `hw/fpga/` |
   | Board | the levers, sidebands and slot (DC-SCM, PCIe CEM, LTPI) behave as the fix needs on real servers | `hw/pinout/`, `docs/interfaces/` |
   | Rack | many governors agree, share budgets and halt together in a real rack | the rack-scale simulation, then a lab rack |
   | Shuttle silicon | the hard core on an open process (Tiny Tapeout, ChipFoundry) | `hw/librelane/` |
   | Production silicon | a production node, with debug fused off, tamper response and a supply chain a regulator can verify | partner foundry |
   | Fleet and mandate | remote attestation that every server has a genuine, current governor; rule distribution and revocation across hundreds of thousands of racks; jurisdiction-specific rulebooks | standards body, regulators, operators |

8. **Track dependencies.** A row that depends on NVIDIA, an OEM, an operator, a standards body or a regulator stays
   open with that dependency named, and the project's public claims say so.

## What "done" means

- A **catastrophic** row is done only when the attack fails in code, in the proof where one applies, and in a fresh
  audit, and its silicon change is in the RTL with a passing formal proof.
- A **serious** or **moderate** row is done when the attack fails in code and in a fresh audit, and its silicon
  change is planned with a stage.
- A **claim** row is done when the sentence matches the evidence.
- The catalog is never deleted. Closed rows keep their history: the failing test, the fix commit, the proof, and the
  fresh audit that confirmed it.

## Order of work

1. Catastrophic rows, server scale first, then rack, then fleet, then mandate.
2. Serious rows in the same order.
3. Claim rows, together with the plain-English comments pass, so the documents never say more than the code.
4. Moderate rows.

Each batch ends with a fresh adversarial audit by a team that has not seen the earlier audits or the fixes.
