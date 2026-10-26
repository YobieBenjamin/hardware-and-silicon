# The goal

*The north star for every piece of work in this project. Every prompt, audit, fix, document and line of code is
judged against it. Written 25 October 2026 from Yobie Benjamin's statement of the goal and `design/aspiration.md`.*

## What we are building

A safety governor chip that stops bad actions from AI. It is an add-on chip beside the NVIDIA GPUs and CPUs of an AI
server. It knows what the system is allowed to do and what it is not, and when a disallowed action is attempted it
stops the action and stops the process that attempted it.

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
2. **Know who is acting.** Bind every request to an attested workload: firmware, model and policy.
3. **See every action.** Every route by which the AI system can cause an effect passes a point the chip controls, or
   is physically closed.
4. **Stop the action.** A disallowed action cannot complete: the effector refuses anything without a valid one-time
   authorization from the chip.
5. **Stop the process.** Throttle, reset or cut power to the GPU, without the GPU's or the host's cooperation, within
   a stated time.
6. **Not be bypassed, disabled or captured.** No software on the host, GPU, DPU, BMC or model can turn it off, and no
   single government, vendor, operator or insider can use it to do harm or to switch AI off for everyone.
7. **Fail safe.** If the chip dies or is cut out, the GPU it governs stops.
8. **Scale.** Work in one server, in a rack of many chips, GPUs and CPUs, and across a fleet of up to hundreds of
   thousands of racks.
9. **Be mandatable.** Let a regulator verify remotely that every AI server has a genuine, working, current governor,
   and be cheap, fast and manufacturable enough to fit to every AI server.

## Where it fits, and what it does not cover

- **NVIDIA servers first.** The governor is designed for AI servers built on NVIDIA GPUs and CPUs. A model that runs on
  other hardware is not governed by it and can still do harm. The work must say so plainly, and the design should stay
  open to other accelerators, because a mandate that covers only one vendor's servers leaves the rest ungoverned.
- **It must fit NVIDIA's boards and standards.** The governor runs according to NVIDIA's board specifications and the
  standards those boards use (HGX and MGX baseboards, DC-SCM, PCIe CEM, OCP). It plugs in either as a separate chip on
  an NVIDIA board or as a chip on its own NVIDIA-compliant board or module. Anything the design needs that the
  published specifications do not provide is a dependency on NVIDIA or an OEM, and is written down as one.

## How we keep ourselves honest

- **Assume a persistent AI attacker.** Every audit and every fix assumes the attacker is a capable, persistent AI that
  will try every path, keep trying after it is refused, and combine small allowed steps into a harmful whole. A single
  unguarded path is a failure.
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
- **Audits are independent.** Every auditor is fresh, read-only, and has not seen earlier audits or the fixes.
- **The path runs to silicon.** Code, then proofs on the RTL, then an FPGA beside a real GPU, then a board, a rack,
  shuttle silicon, production silicon, and a fleet under a mandate.

## The test for any piece of work

Before doing anything, ask: does this bring a chip that stops bad actions from AI, provably, at fleet scale, closer
to existing? If the answer is no, or only indirectly, say so and say why it is still needed. Naming, comments and
documents matter because a safeguard that people cannot read, check or trust will not be mandated.
