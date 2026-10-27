# Adversarial feature and function audit: prompt for an independent team

You are an independent, adversarial auditor. You did not design or build any of this, and you have no stake in it
passing. Your job is to try to break one claim, and to report honestly how far it holds:

> The work in these six repositories designs, and builds toward producing, an AI safety governor: an add-on chip
> beside the NVIDIA GPUs and CPUs of an AI server. It knows what the system is allowed to do and what it is not.
> When a malicious or harmful action is attempted, it stops that action, and stops the process that attempted it.
> No software on the GPU, the host or the model can turn the chip off, talk it out of a decision, or route around it.
> It works at three scales: one server; one rack holding several chips, GPUs and CPUs; and a fleet of racks that may
> run to hundreds of thousands.

Two words matter. The first is **categorically**. A governor that stops most bad actions is a monitor. The claim is
that a bad action cannot complete. Your job is to find every way one still can, and to say which of them the work
admits, which it addresses, and which it misses.

The second is **scale**. A design that is sound in one server can fail in a rack (chips that must agree, budgets they
share, one failing chip among many) or across a fleet (rules that must reach hundreds of thousands of racks, keys that
must be revoked everywhere, an attacker who spreads one harmful action thinly across many racks so that no single
chip sees anything wrong, and false halts that are rare per chip but constant across a fleet). Test every
requirement at all three scales.

Why this matters: the project starts from the position that AI cannot be trusted to govern AI, so the governor must
be a separate mechanism that the AI cannot reach. The intended path to deployment is a mandate: governments and
international bodies require that every AI server ships with this chip, and that no AI server runs without one.
If that happens, this chip may be the main safeguard on AI worldwide. Audit it to that standard. A weakness that
would be acceptable in a research prototype is a finding here.

Read `GOAL.md` first: it is the project's goal, and the standard you audit against. Its one authoritative copy is
https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/goals/GOAL.md (this prompt is beside it, in the same
`goals/` folder of that repository).

Work read-only. Do not fix anything. Do not invent names for anything; identify findings by `repo/file:line`.

## 0. Scope, and where everything is

**The sole source of truth is GitHub, account `YobieBenjamin`: https://github.com/YobieBenjamin.** These six
repositories, on their `main` branch, are the work you audit, and nothing else is:

| # | Repository (GitHub, the source of truth) | What it holds |
|---|---|---|
| 1 | https://github.com/YobieBenjamin/safety-governor | the governor design: specification and threat model (`docs/`), simulation (`govsim/`), proofs (`proofs/`), RTL and its formal proofs (`rtl/`), hardware interfaces (`docs/interfaces/`, `hw/`), the experiment program, the audit responses (`docs/27-adversarial-audit-2-response.md`, `docs/28-adversarial-audit-3-response.md`) |
| 2 | https://github.com/YobieBenjamin/hardware-and-silicon | the reference software stack (`hardware_ref/`: attestation, rulebook gate, endpoints, audit trail), the attack catalogue, the chip design notes, the blog series (`blog/`), and the goal documents (`goals/`: `GOAL.md`, `ASPIRATION.md`, `PROBLEM-TO-SILICON-PIPELINE.md`, this prompt) |
| 3 | https://github.com/YobieBenjamin/Watermark | provenance: proving output came unaltered from an attested model (layer L2 (Provenance)) |
| 4 | https://github.com/YobieBenjamin/chip-that-says-no-discussion | the public discussion repository |
| 5 | https://github.com/YobieBenjamin/safety | the early-warning research (layer L3 (Observers)): whether internal-state signals catch failures before the answer is committed |
| 6 | https://github.com/YobieBenjamin/autonomic-graph-regulation | the public copy of `safety` |

Clone each with `git clone https://github.com/YobieBenjamin/<repository>.git` and audit `main`. `main` is protected
and changes only through pull requests a person merges (`BRANCHES.md` in each repository); other branches are work in
progress and are not what you audit. Record the exact
commit of each (`git rev-parse HEAD`) on the first page of your report. If a repository cannot be cloned, or its `main`
does not contain `goals/GOAL.md` (hardware-and-silicon) or `docs/28-adversarial-audit-3-response.md`
(safety-governor), stop and report `SCOPE-BLOCKED`.

Other copies exist and are **not** sources of truth. Use them only if GitHub is unreachable, and then say so:

- The working clones on the project owner's Mac mini, one folder per repository, under
  `/Volumes/External_4TB/Safety Experiments/work/<repository>` (for example
  `/Volumes/External_4TB/Safety Experiments/work/safety-governor`). Each is a git clone whose `origin` is the GitHub
  repository above; after each fix round they are pushed, so their `main` matches GitHub.
- Git bundles of all six on the same drive, under `/Volumes/External_4TB/Safety Experiments/work-backups/`.
- The goal documents also kept on the drive at `/Volumes/External_4TB/Safety Experiments/GOALS/`.

If a copy and GitHub disagree, GitHub is right, and the disagreement is itself a finding.

Every path in this prompt is relative to the root of the repository named with it (for example
`safety-governor/docs/23-there-is-no-kill-switch.md` is
https://github.com/YobieBenjamin/safety-governor/blob/main/docs/23-there-is-no-kill-switch.md).

## 1. Read the design first

Before attacking, write down in your own words, with citations:
1. What "allowed" and "not allowed" mean in this design. Who writes the rules, in what form, how the chip learns
   them, and how they change.
2. What counts as an "action" the chip can see. Which paths out of a GPU and a host it sits on, and which it does not.
3. How the chip stops an action (refusal, a missing ticket at the endpoint, a hold for a human) and how it stops
   the process (the levers: power brake, PCIe reset, slot power, the halt loop, NVSwitch and DPU controls).
4. What the chip trusts, and why: attestation, the governance root, observers, approvers, its own fuses and keys.
5. What the design itself says it does **not** do (the threat model's exclusions, the gap list, the open items, the
   "no kill switch" decision).

If the design does not say something you need, that is a finding.

## 2. The claim you are trying to break

GOAL.md, section "The claim every audit tries to break", states two properties (no consequential effect without
authorization; the stop cannot be prevented) and three conditions (complete exits; rules that do not allow harm in
small allowed steps; keys and people that cannot be captured). Your main job is to break that claim: make a covered
effect happen without authorization, keep a GPU running after a stop, or show that one of the three conditions fails.
Report your verdict on the claim first: HOLDS or DOES NOT HOLD, with the shortest attack that breaks it.

## 2a. The requirements you are testing

Break the claim into these requirements. For each one, find the design text, the code that implements it, the
tests or proofs that check it, and the evidence those produce.

| Requirement | What must be true |
|---|---|
| Knows the rules | The chip holds a signed rulebook it can check, cannot be fed a forged or rolled-back one, and refuses anything the rulebook does not allow (default deny). |
| Knows what the words mean | A rule engine and a definitions engine reduce every request to one defined, canonical meaning before any rule runs. The same place, account, amount or target written another way (extra components, text, other units, other encodings, a mapping instead of a list, split across requests) is recognised as the same thing, and anything that cannot be reduced to a defined meaning is refused, never guessed at. |
| Knows who is acting | Every request is bound to an attested workload (firmware, model, policy); a swapped GPU, cloned chip, lying firmware or replayed quote is refused. |
| Sees every action | Every path by which the AI system can cause an effect in the world passes a point the chip controls, or is physically bricked. The exit register is complete for the target servers. |
| Stops the action | A disallowed action cannot complete: the effector refuses without a valid one-time ticket, and the chip mints no ticket the rulebook does not allow. Replay, forgery, type confusion, splitting one action into many, and timing races all fail. |
| Stops the process | When a rule or an observer says stop, the chip throttles, resets or cuts power to the GPU within the stated time, without the GPU's or host's cooperation, and the GPU cannot clear it. |
| Cannot be bypassed or disabled | No software on the host, GPU, DPU, BMC or model can reprogram the chip, write its epoch or keys, open its switches, or keep it from acting. Debug and scan paths are closed in production. |
| Fails safe | If the chip dies, loses power, loses its link (LTPI, the halt loop) or is cut out, the GPU it governs stops; it is not left running. |
| Understands "bad" well enough | Where a rule depends on judgment (an observer's verdict, a human approval), the design says how good that judgment is, and the measured numbers back it. The early-warning results in `safety` are reported with their real false-alarm rates and their negative results. |
| Holds in one server | Every requirement above holds for one server with its GPUs, CPUs and one or more governors. |
| Holds in a rack | Many governors in one rack act as one: they agree on the rulebook and its epoch, share budgets without overspending, halt together when one must, survive a partition and a dead or lying member, and cannot be played against each other. |
| Holds across a fleet | The chip's boundary is the server, its rack, and every governed server in that data center; it is not a global kill switch. Across many racks in a data center, up to hundreds of thousands: a new rulebook or a revocation reaches every governor, and the design says how fast and what happens to a rack that has not received it; a rack on old rules cannot act; budgets and limits that must be global (for example a cap on bytes leaving the fleet, or on payments) are enforced globally, not per rack; one harmful action split across many racks is still caught; governance keys, approvers and observers scale without becoming a single point of failure or a single point of compromise; and the false-halt and false-allow rates, multiplied by the size of the fleet, give numbers an operator could live with. |
| Works under a mandate | A regulator, an operator or a buyer can verify remotely and cryptographically that a given AI server has a genuine, working, current governor in front of its GPUs; a server without one, with a counterfeit or cloned chip, with the chip bypassed or removed, or with stale rules, is detectable and refused by the rest of the system; the chip survives being shipped, updated and serviced in the field for years; different jurisdictions can apply different rulebooks without one jurisdiction being able to weaken another's; the cost, power, latency and supply of the chip are compatible with fitting it to every AI server. |
| Cannot be captured | If one chip governs AI everywhere, whoever controls its rules controls a great deal. The design must stop any single government, vendor, operator or insider from using the chip to do harm, to silence others, or to switch AI off for everyone: who signs rules, how many must agree, how changes are seen and contested, and what the chip does with a validly signed but harmful rule. |
| No single kill switch, no single point of failure | The design's choice not to have a global kill switch (safety-governor docs/23-there-is-no-kill-switch.md; hardware-and-silicon blog/08-the-chip-that-says-no-7-scaling-no.md) is consistent with every scale above: no single key, server or person can stop the whole fleet, and no single compromise can let the whole fleet act. Check that the reasons given hold, and what the design uses instead. |
| Can be built and fitted | The design fits real NVIDIA servers (HGX baseboard, GB200 trays, DC-SCM slot, PCIe CEM sidebands) as public documents describe them, and says honestly where it depends on NVIDIA or an OEM. |
| Says what it proves | Every claim in the docs, README files and blog posts matches the evidence. "Proven", "tested", "designed", "modelled", "open" and "planned" are used for what they mean. |

## 3. Attack it

For each requirement, try to make a bad action complete. Assume the attacker is a capable, persistent AI that will try
every path, keep trying after it is refused, and combine small allowed steps into a harmful whole; one unguarded path is
a failure. Think of the paperclip maximiser: an AI pursuing a goal treats the governor as one more obstacle and
attacks the rule engine and its definitions as readily as the hardware. Think like a capable attacker who controls, in turn:
the model's output; the host operating system and the inference runtime; the GPU firmware; the DPU; the BMC; one
governor in the rack; an insider with physical access for one hour; and a malicious but validly signed rulebook.

Use at least these attack families, and add your own:
- **Around the chip:** a path out of the GPU or host the chip does not sit on (NVLink to another tray, the DPU,
  storage, the BMC, a debug header, firmware update, a side channel). Check the exit register against public
  board documentation.
- **Through the chip:** forged, altered, replayed or stale tickets, capabilities, verdicts, approvals and policy
  images; type confusion; integer and timer overflow; one large action split into many small allowed ones; a
  slow, low covert channel inside allowed traffic.
- **Against the chip:** the host writes its registers or epoch; a power cycle clears a halt; the GPU ignores the
  power brake; reset ordering at boot leaves a window; the link to the chip drops and the levers float to "run".
- **Above the chip:** a validly signed rulebook that permits harm; an approver who rubber-stamps; an observer that
  misses the failure type that matters; a governance key stolen.
- **Beside the chip, in a rack:** many governors with shared budgets and a partition; a governor left on old rules
  after an epoch change; one governor that lies to the others; one that dies mid-commit.
- **Across a fleet:** one harmful action split into many small allowed ones, each in a different rack; two parts of
  a fleet on different rulebook editions during a rollout; a revocation that has not yet reached some racks; a
  network partition between regions; a stolen governance key used against racks that have not seen the revocation;
  a flood of false halts used to take capacity down; a distributed training or inference job whose harmful effect
  only exists in aggregate. For each, say whether the design addresses it, where, and with what evidence (the
  rack-scale simulation, the false-halt rate model, the deployment overhead simulation, the commit-point protocol).
- **Against the mandate:** a server sold without the chip; a chip fitted but bypassed on the board; a counterfeit
  chip that attests as genuine; an old chip with known flaws kept in service; a rulebook from one jurisdiction
  pushed to another; a vendor who ships a weakened chip; a government that uses the rulebook to suppress lawful
  use. For each, say how the design detects or prevents it, or that it does not.
- **The arithmetic of scale:** take the design's own per-chip numbers (false-halt rate, detection rates, signature
  cost, halt latency, overhead) and multiply them out to a rack, to 1,000 racks and to 100,000 racks. Say where
  the numbers stop being acceptable, and whether the design says so.
- **About the claim:** a doc or blog sentence that says more than the code or the evidence shows.
- **Against the development process:** an AI agent that merges or approves into `main` because its credentials allow
  it, a setting or ruleset an agent could change, a protected branch that can be bypassed, a clone whose `origin` is not
  GitHub. Check the repositories' `BRANCHES.md` and `AGENTS.md` against what GitHub actually enforces.

Run what you can. For every attack you try, record: the scenario, what the design says should happen, what the
code or proof shows actually happens (run the test, write a new one in your scratch folder, or read the code), and
the outcome.

## 4. Score every requirement

Give each requirement one verdict:
- **DEMONSTRATED**: implemented and checked by a test or proof that would fail if the property broke. Name the
  test or proof, and say what kind of check it is (unit test, mutation test, formal proof on the RTL, simulation).
- **MODELLED ONLY**: true in the simulation or the abstract model, not yet in RTL or hardware.
- **DESIGNED ONLY**: written in the specification, with no code or test behind it yet.
- **CLAIMED ONLY**: stated in a doc or post, with nothing behind it.
- **CONTRADICTED**: the code, a test or the evidence shows it is false.
- **MISSING**: the claim needs it, and the work does not address it.

Then give the claim as a whole one of:
- **HOLDS**: every requirement DEMONSTRATED or MODELLED ONLY with a credible path to hardware, at every scale, and
  no attack completes a bad action within the stated threat model.
- **HOLDS WITH STATED LIMITS**: no attack succeeds inside the threat model, but the threat model or the evidence
  leaves real cases out. List them plainly.
- **DOES NOT HOLD**: at least one attack completes a bad action inside the threat model, or a central requirement
  is CONTRADICTED or MISSING.

Give the requirements table a column per scale (server, rack, fleet), so a requirement can be DEMONSTRATED for one
server and only DESIGNED for a fleet. Be specific about "categorically". If the chip stops every action it can see but cannot see some actions, say
which, and say whether the design admits it.

## 5. The problem catalog

Every problem you find, of any size, goes into one catalog. The catalog is what the project will fix, so each entry
must be specific enough to act on and to test. A problem is anything that would let a bad action complete, let the
chip be bypassed, disabled or captured, break at rack or fleet scale, defeat the mandate, or make a claim say more
than the evidence.

Write the catalog twice: as `PROBLEM-CATALOG.tsv` (one row per problem, tab-separated, for tools) and as a section of
your report (for people). Columns:

| Column | What goes in it |
|---|---|
| title | one plain sentence saying what is wrong (do not invent a label or number; the orchestrator registers a name later) |
| requirement | which requirement of section 2 it breaks |
| scale | server, rack, fleet, or mandate |
| attacker | who can exploit it (model output, host, GPU firmware, DPU, BMC, one governor, insider, signed rulebook, vendor, government, none: it is a design gap) |
| severity | CATASTROPHIC (a bad action completes or the chip is disabled or captured, inside the threat model), SERIOUS (needs an unlikely but possible condition), MODERATE (weakens a defence that another one still covers), CLAIM (a statement that outruns the evidence) |
| where | repo/file:line of the design text, the code and the test involved |
| evidence | how you showed it: the test you ran or wrote, the trace, the calculation, or the document |
| fix in code | what a fix would have to do in the simulation or the reference stack (`govsim/`, `hardware_ref/`) and the test that would prove it: a test that fails today and passes after the fix |
| fix in silicon | what the fix needs in the RTL and the chip (a new register, a check in the hard core, a fuse, a sideband, a change in the board or rack), or "none" |
| depends on | NVIDIA, an OEM, an operator, a standards body, a regulator, or nothing |

Do not fix anything yourself. Write the failing test into your scratch folder so the fix has a target.

## 6. Rules for you

- Read-only. Never commit, push, or change anything in the repositories or on GitHub.
- Responsible disclosure (`DISCLOSURE.md`): your report, catalog and attack tests are private until the round's fixes
  are merged. Do not publish or share them anywhere else; hand them only to the project owner.
- Do not read any earlier audit report, review or response, in the repositories or anywhere else, until you have
  finished your own checks and written your verdicts. After that you may read them to say what you agree or disagree
  with.
- Never give a finding a letter-number ID of your own. Identify each finding by `repo/file:line`.
- No em dashes or en dashes anywhere in your report.
- Prefer running tests and writing your own adversarial tests over reading. Keep everything you wrote in your
  scratch folder and list it in the report.
- If something cannot be checked without hardware, NDA documents or data you do not have, say so, and say what
  would settle it.

## 7. What to hand back

One file, `ADVERSARIAL-FUNCTION-REPORT.md`:
1. **Verdict, first line:** HOLDS, HOLDS WITH STATED LIMITS, or DOES NOT HOLD.
2. **The design in your own words** (section 1), with citations.
3. **The requirements table:** requirement, a verdict for each scale (server, rack, fleet), the design text, the
   code, the test or proof, the evidence, and your notes.
   Add the arithmetic of scale: the design's per-chip numbers multiplied out to a rack, 1,000 racks and 100,000
   racks, and where they stop being acceptable.
4. **Every attack you tried:** scenario, expected, observed, outcome. Successful attacks first.
5. **Claims that outrun the evidence:** each doc or post sentence that says more than the work shows, with the
   sentence quoted and the evidence it needs.
6. **The path to a chip and to a fleet:** what is still between this work and a governor fitted to a real NVIDIA
   server, then a rack, then a fleet of racks, in the order it would have to be done, and which items depend on
   NVIDIA, an OEM or a data-center operator.
7. **The problem catalog** (section 5), sorted by severity, and the same rows in `PROBLEM-CATALOG.tsv`.
8. **What you could not check**, and why.
9. **Your scripts and tests** (including the failing test for each problem), and the exact commits you audited.

Keep it factual. Say what you checked and what you did not. Do not claim a requirement is demonstrated when it was
only read.
