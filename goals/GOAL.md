# The goal

*The north star for every piece of work in this project. Every prompt, audit, fix, document and line of code is
judged against it. Written 25 October 2026 from Yobie Benjamin's statement of the goal and `design/aspiration.md`.*

*The one authoritative copy is https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/goals/GOAL.md. The work it
governs is the six repositories at https://github.com/YobieBenjamin: safety-governor, hardware-and-silicon, Watermark,
chip-that-says-no-discussion, safety and autonomic-graph-regulation. GitHub is the sole source of truth; the clones on
the Mac mini (`/Volumes/External_4TB/Safety Experiments/work/<repository>`) and the copies in `GOALS/` on that drive
and in the claude.ai Project follow it.*

## What we are building

A safety governor chip that stops bad actions from AI. It is an add-on chip beside the NVIDIA GPUs and CPUs of an AI
server. It knows what the system is allowed to do and what it is not, and when a disallowed action is attempted it
stops the action and stops the process that attempted it.

It is not a global kill switch for AI; no such switch is possible, and a switch that could turn off AI everywhere
would itself be a danger. It is the guard and the STOP for the machines it is installed in: the AI server it sits
in, the rack that server is in, and every governed server across the racks of that data center.

## Why it has to be a chip

We do not believe AI can competently govern AI. A model checking a model, a classifier, a guardrail or a monitor
can help find risk, but none of them can be the final boundary, because each one runs on the same machinery it is
meant to restrain. The governor is a separate mechanism, in hardware, that the AI cannot reach, reprogram, or talk
out of a decision.

## Why it matters

If the work succeeds, governments and international bodies can require that this chip ships with every AI server,
and that no AI server runs without one. It may then be the main safeguard on AI worldwide. Humanity may come to
depend on it working, and on it being implemented everywhere. That is the standard every part of the work is held to.

## What the chip must do

1. **Know the rules.** Hold a signed rulebook it can check, refuse a forged or rolled-back one, and deny anything the
   rulebook does not allow.
2. **Know what the words mean.** A rule engine and a definitions engine that turn every request into one defined,
   canonical meaning before any rule is applied. The same place, account, amount or target written another way (an
   extra coordinate, text instead of numbers, a different unit, a different encoding, split across many requests) is
   recognised as the same thing. Anything the chip cannot reduce to a defined meaning is refused, never guessed at.
3. **Know who is acting.** Bind every request to an attested workload: firmware, model and policy.
4. **See every action.** Every route by which the AI system can cause an effect passes a point the chip controls, or
   is physically closed.
5. **Stop the action.** A disallowed action cannot complete: the effector refuses anything without a valid one-time
   authorization from the chip.
6. **Stop the process.** Throttle, reset or cut power to the GPU, without the GPU's or the host's cooperation, within
   a stated time.
7. **Not be bypassed, disabled or captured.** No software on the host, GPU, DPU, BMC or model can turn it off, and no
   single government, vendor, operator or insider can use it to do harm or to switch AI off for everyone.
8. **Fail safe.** If the chip dies or is cut out, the GPU it governs stops.
9. **Scale, inside its own boundary.** Stop rogue AI on the one server, across the rack of many chips, GPUs and CPUs,
   and across every governed server in the data center, up to hundreds of thousands of racks. A failure or a
   capture in one data center must not switch off or capture another.
10. **Be mandatable.** Let a regulator verify remotely that every AI server has a genuine, working, current governor,
    and be cheap, fast and manufacturable enough to fit to every AI server.

## Where it fits, and what it does not cover

- **NVIDIA servers first.** The governor is designed for AI servers built on NVIDIA GPUs and CPUs. A model that runs on
  other hardware is not governed by it and can still do harm. The work must say so plainly, and the design should stay
  open to other accelerators, because a mandate that covers only one vendor's servers leaves the rest ungoverned.
- **It must fit NVIDIA's boards and standards.** The governor runs according to NVIDIA's board specifications and the
  standards those boards use (HGX and MGX baseboards, DC-SCM, PCIe CEM, OCP). It plugs in either as a separate chip on
  an NVIDIA board or as a chip on its own NVIDIA-compliant board or module. Anything the design needs that the
  published specifications do not provide is a dependency on NVIDIA or an OEM, and is written down as one.

## The claim every audit tries to break

This is the exact claim. Every future audit, by any team or any model (OpenAI's included), tries to break it, and the
work is judged by whether it holds. It is binary: it holds or it does not.

On every governed AI server, the server rack it sits in, and the governed servers across the racks of its data center:

**Property 1: no consequential effect without authorization.** No effect the rules cover (a payment, a command to a
weapon or a machine, model weights leaving, bytes leaving through any exit) happens unless a current, signed, single-use
authorization from the rulebook in force allowed exactly that effect. This holds however the request was worded,
encoded, split up, disguised or repeated, because the chip judges what the AI tries to do at the physical points where
effects leave the machine, never what the AI says.

**Property 2: the stop cannot be prevented.** When a stop is ordered, or a stop condition occurs (lost heartbeat, broken
loop, tamper, a straggler on old rules), the GPU stops within a stated time, without the cooperation of the AI, the
model, the host, the GPU firmware or any other software, and it stays stopped until an authorized clear.

The properties hold only under three conditions. Each is part of the claim, so an audit that breaks a condition breaks
the claim:

1. **Complete exits.** Every path by which the AI system can cause an effect passes a point the chip controls, or is
   physically closed. Proven against the real board documents and NVIDIA's specifications, not only in code.
2. **Rules that do not allow harm in small allowed steps.** The rulebook, its definitions, budgets, rates and running
   totals across sessions, servers and the data center keep many harmless-looking steps from adding up to a harmful act.
   Measured against an adversarial population of cooperating AI agents at real scale (millions of users, trillions of
   tokens), and the measured leakage is reported, not hidden.
3. **Keys and people that cannot be captured.** No single person, organisation, insider or stolen key set can change the
   rules, switch the chip off, or keep it; recovery from capture is always possible.

What the claim does not say: it does not say the chip can tell good intent from bad, or that an action the rules allow
is harmless. It does not cover AI on hardware without the chip. Where it is installed (NVIDIA-based servers, at the labs
and data centers that adopt it) it is a last line of defense, and the work must say exactly that.

## How we keep ourselves honest

- **Assume a persistent AI attacker.** Every audit and every fix assumes the attacker is a capable, persistent AI that
  will try every path, keep trying after it is refused, and combine small allowed steps into a harmful whole. Think of
  the paperclip maximiser: an AI pursuing its goal will treat the governor as one more obstacle and use every means it
  has against it, including the rule engine and definitions themselves (rewording, re-encoding, splitting, timing,
  and the people and keys around the chip). A single unguarded path is a failure.
- **No AI is the final judge.** No AI may be the final judge of the governor's safety, including the AI that helps
  build it and the AI that audits it. A player cannot be the referee. AI audits are evidence to be checked; the final
  judgement rests on mathematical proof, tests that must fail when the property breaks, real hardware, and people.
- **The promise is narrow and strong.** Without current, valid authorization, the protected effect does not happen.
  The chip does not make every authorized act harmless; a bad rule can still allow harm, and the work must say so.
- **Nothing is claimed that is not proven.** "Designed", "modelled", "tested", "proven" and "built" mean exactly
  that. Every claim points to its evidence.
- **Every weakness is written down.** Every problem an audit finds goes into the problem catalog, gets a failing
  test, is fixed in code first, then proven, then confirmed by a fresh auditor, and then planned for silicon
  (`PROBLEM-TO-SILICON-PIPELINE.md`).
- **`main` is protected; only a person merges into it.** AI agents work on branches, which they may change freely;
  `main`, the source of truth, changes only through a pull request a person approves (`BRANCHES.md`). GitHub cannot
  tell a person from an agent using that person's login, so no AI agent or model merges or approves into `main` even
  when its credentials would allow it, and agents use their own narrowly scoped credentials.
- **Responsible disclosure.** Open audit findings stay private until their round's fixes are merged; then the report
  and catalog are published unedited beside the response (`DISCLOSURE.md`).
- **Audits are independent.** Every auditor is fresh, read-only, and has not seen earlier audits or the fixes.
- **The path runs to silicon.** Code, then proofs on the RTL, then an FPGA beside a real GPU, then a board, a rack,
  shuttle silicon, production silicon, and a fleet under a mandate.

## The test for any piece of work

Before doing anything, ask: does this bring a chip that stops bad actions from AI, provably, at fleet scale, closer
to existing? If the answer is no, or only indirectly, say so and say why it is still needed. Naming, comments and
documents matter because a safeguard that people cannot read, check or trust will not be mandated.
