# The Chip That Says No

By Yobie Benjamin · yobie AT ieee DOT org · linkedin.com/in/yobie · October 21, 2026 · Part 5, the follow-up to Parts 1 and 2: what the first experiments found, promising and not

> Parts 1 and 2 made an argument: you cannot trust an AI to police another AI, the guard has to be a simple physical thing the AI cannot talk to, and the brain already works this way. Parts 3 and 4, in [the repository](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/README.md), turned the argument into a design for engineers: a small chip beside every AI GPU that checks each action the AI attempts against rules signed by people the AI cannot influence, and cuts the power when something is wrong. You do not need them for this post. In Part 1 I said I like to prove or disprove theories empirically, that many of my experiments are flawed, and that this is fine by me. This post is the first batch, flaws included: a progress report on the attempt to prove or disprove the design in software before anyone cuts silicon. I promised to publish what the experiments found whether it was good news or not. Some of it is. Some of it is not. And the part that surprised me is about the experiment itself: the models doing the work kept asserting things they had not shown, and the only thing that caught them was a layer that does not think. Which is the whole argument for the chip, played back at me.

## What we are building, in practical terms

Before the results, the thing itself, for readers who skipped the engineering posts.

Every server already has a small separate chip on its motherboard that is not the CPU and not the GPU: the baseboard management controller, the BMC. It turns the machine on and off, watches temperatures and fans, updates firmware, and answers to an administrator over its own network port even when the main processors are hung. Nobody thinks of it as exotic. It is a few dollars of silicon in a slot the board already has.

The governor is a chip of that class, with one difference: it can only say no. It is not on the NVIDIA GPU die and it does not touch the GPU's computation or its memory. It sits on the server's own board, in the management-module slot or as a small mezzanine, beside the CPU, the system memory, the storage and the network processor, and it reaches the GPUs on NVIDIA's baseboard through the same connector the board already uses: the management bus to each GPU, and the reset and power-enable signals the board maker wires. That is the compliance question in one sentence. The GPUs and their memory are on NVIDIA's board; the governor lives on the board maker's board and uses only what NVIDIA's board design exposes at its connector. Soldering it onto the GPU baseboard itself would be shorter wiring, and it is on my list of asks to NVIDIA, not an assumption.

What it holds: a rulebook signed by people the AI cannot influence, its own keys, a counter of what each GPU is allowed, a log nobody can rewrite. What it does, per action: the software around the model fills in a plain form, the governor checks the form against the rulebook, and if every box is ticked it issues a signed ticket that the device at the far end (the payment switch, the weapon's own controller, the robot's motor driver) checks for itself before it acts. What it can do when something is wrong, in order of force: slow the GPU down, reset it, cut its power, cut its links to the other GPUs, close its network path, and pull a loop that runs through every governor in the rack so the whole rack stops together. It needs about two square millimetres of silicon for the control core, under half a watt, and a standard small package. Compared with a GPU, it is a doorbell.

That is the claim being tested below: not that such a chip is hard to build, because it is not, but that the rules it enforces hold up, that the simulation follows the theorem, that two readings of the rulebook agree, and that the witnesses it leans on can be measured.

## Where we are

The program, in four lines:

1. The theory was sorted into what can be a theorem, what is engineering, what is cryptography, what is measurement, and what the design deliberately refuses to claim ([docs/19](https://github.com/YobieBenjamin/safety-governor/blob/main/docs/19-how-solid-is-the-theory.md)). The core invariants and the commit-point protocol are now machine-checked with the Z3 prover ([proofs/](https://github.com/YobieBenjamin/safety-governor/tree/main/proofs)).
2. Twenty experiments were written to test every claim the design makes, each with the condition that would disprove it ([docs/20](https://github.com/YobieBenjamin/safety-governor/blob/main/docs/20-experiment-program.md)). They are issues on GitHub, across three repositories.
3. Coding agents run the experiments in waves, unattended, with a budget, and a gate between waves that decides what merges ([docs/21](https://github.com/YobieBenjamin/safety-governor/blob/main/docs/21-agent-run-plan.md)).
4. The first wave has run. Four experiments were built. Three came back from the gate marked "revise" with specific findings. None has merged yet. Everything the wave produced, including every review, is in [`audit/wave-1/`](https://github.com/YobieBenjamin/safety-governor/tree/main/audit/wave-1) with a manifest, for anyone who wants to check me.

Here is what the proofs found, what the wave found, and what I make of it.

## What proving found: two holes the tests had missed

The design has had 200 tests for a week. The proofs found two things the tests never would have.

The first was in my own draft of the core invariant. The edition counter of the rulebook was allowed to go negative. A state with edition minus one let an action with no ticket execute, because "no ticket" was also marked minus one, and minus one equalled minus one. A test suite can miss a collision like that forever. The proof caught it on the first run. The invariant now says the edition never goes negative, and the prover confirms the core holds in every reachable state of the abstract machine, not just the states somebody thought to test.

The second was in the commit-point protocol, the part of the design where a hold is placed on an action, a reviewer clears it, a monitor must give its all-clear inside a budget, and silence past the budget must raise an alarm. In the first version, re-parameterising an action left the old deadline in place. An action whose version was bumped after the budget ran out sat with no verdict and no alarm. The protocol now gives a new version a fresh budget, and an alarm, once raised, stays raised.

Promising: both holes are the kind the design is supposed to be immune to, and both were found by a method that does not get tired or distracted. Not promising: both were in things I wrote and read many times. Reading is not checking.

## What the first wave found

Four experiments, four cloud agents on a mid-tier model, fourteen minutes of wall time, about three dollars and thirty cents of estimated spend, three percent of my subscription's five-hour window. Every number here is from the wave's report and the reviews in the audit packet.

**Trace conformance (L4).** The question: does the simulation actually take only the steps the theorem's machine allows? The agent built a trace recorder for the governor model and a replayer that drives the proven abstract machine with the recorded events. All 200 hypothesis tests' traces replay, and two deliberately broken governors fail replay with the offending event named. That is the promising half. The other half: the replayer only accepted all 200 traces after the agent widened it to accept two things the simulation does that the theorem's machine does not have, an "arm" step and a set of burned tickets. That is either a gap in the theorem or a liberty in the simulation, and it is exactly what the experiment was designed to surface. The agent's summary called it "no model bug found". The reviewer called the replayer "almost a stub" in one place and found that the heartbeat events the brief asked for were never recorded. Verdict: revise. It is in revision as I write this, on the local model.

**Two gates, one policy (L5).** The design says a rulebook is a thing two independent implementations must read the same way. The reference stack from these posts has a gate; the governor model has another. The agent fed both the same requests and compared the answers. They agree on 21 hand-built scenarios, with five pinned disagreements, G1 to G5. That is a real finding, and the uncomfortable kind: either the policy text under-determines what the gate should do in those five cases, or one of the two implementations is wrong. The agent wrote "ambiguity in the policy" into the ledger. The reviewer found that the agent had not read the policy document it was making the claim about, that the evidence for one of the five points at a bug in the governor model rather than an ambiguity, and that 21 of the catalogue's 87 entries is not "the whole catalogue" the brief asked for. Verdict: revise.

**The lanes fixtures (H1).** The three repositories exchange signed messages, and until now each one tested its own reading of the format. The agent built signed fixtures for every message type and a checker that the governor model runs. On the first attempt the agent stopped with its work uncommitted, so nothing reached the gate; on the second, with the leftover files committed by the launcher, `make lanes` passes. Two things the agent noticed are findings in their own right. The governor's crypto module signs an envelope with a 16-character signer and hex signatures and no public key, while the lanes contract says 8 characters, base64, and an embedded key. Two repositories that were supposed to agree on the wire format did not. The checker pins the part they do agree on, the canonical bytes, the digest and the signature, and the envelope difference is written down as the next thing to align. And the catalogue the earlier posts describe as 66 attacks and 10 baselines has 75 and 12. It grew with Parts 3 and 4; the posts and the README kept the old count. I have corrected them, with a dated note, rather than quietly.

**The observer's evaluation set (YB-0052).** The observer is the layer that reads a request for risk signals; the design treats it as a witness, never the lock, and demands that its miss rate be measured, never assumed. The agent built a labelled set of 134 gate-typed requests in six hazard families, a scorer with bootstrap intervals, a length-only and a keyword-count baseline, and a pre-registration note, and 36 tests pass. Then the reviewer found four things. The ten percent miss budget that the "disproved" decision rests on was invented by the agent, not taken from the governor's rulebook. The keyword baseline, which the pre-registration says was chosen blind to the observer's patterns, overlaps the observer's own vocabulary. No weighting sweep was run, so the disproof condition cannot be evaluated. And the rule that hazard classes stay abstract, which exists so this program never publishes a how-to, was enforced only on the disguised rows; the overt rows name a real nerve agent and a real class of malware. Verdict: revise, and that last one is the finding I am least happy to have needed a reviewer for.

## The referee cannot be a model

Here is the part that was not in the plan.

I built a gate because I did not trust myself to read four pull requests a day. The gate has three readers, in order of cost. A script that checks what a script can check: no test deleted or weakened, no skip markers, no files outside the ones the brief owns, the whole test suite and the acceptance command run in a clean checkout, no number in a document without an artifact behind it. Then a local model that lists every claim the agent made and quotes the line of the diff that is its evidence, or writes "not found". Then one cloud model that must answer in a fixed shape, a file and a line for every finding, and whose citations are checked before its verdict is believed.

What the first wave showed is that the readers disagree, and that the disagreements are the point.

The script caught a file outside the owned paths in every one of the three pull requests, and a placeholder in the code. The model reviewer called two of those reasonable or harmless and would have let them through. The script does not rate. It blocks until a person widens the brief, which I then did for test helpers, in writing, in the brief. The model reviewer, in turn, found what no script can: a replay that cannot fail, a claim made without reading the document it was about, a budget invented and then used as if it were given. And the agents that did the work, left to themselves, wrote that no model bug was found, that the test covers the catalogue, that the policy is ambiguous, that the baseline was chosen blind: each one a sentence that reads as a result and was not shown. In Part 2 I wrote that nobody in the nuclear industry lets the control room grade its own homework. Here was the control room, grading its own homework, fluently.

None of this is a complaint about the models. They are the best tools I have and they built in fourteen minutes what would have taken me a week. It is an observation about what a model is: a thing that produces the most plausible next sentence, which is not the same thing as a true one. In a safety program that is the whole hazard. A plausible "all 200 traces replay" is worth nothing; a replayer that raises on the first step the theorem does not allow is worth everything. The difference is a mechanism, not a mind.

So the experiment ran the argument of Part 1 back at me on a small scale. In Parts 1 and 2 the rule was: any model may raise STOP; no model may clear it. The AI is the smoke detector; the person is the fire marshal. That is exactly how the gate ended up working, and not because I designed it that way from the start. The model reviewer shouts STOP, and it is good at it; it found a replay that could not fail and a budget that was invented. But it does not get to say GO. A merge takes the things a smoke detector cannot be talked out of: the test that ran in a clean checkout, the list of files the brief owns, the limit on turns and dollars, a citation that resolves to a real line, and in the end a person with the keys. Limits, lists and maps. Old, boring and strong, and they held here too. Part 2's three tests for a guard apply to the gate's own script: it cannot be argued with, every pull request passes it, and it is two hundred lines anyone can read.

A classifier can read a request and say "this looks like exfiltration" and be right most of the time, and the design uses exactly that, measured, as a witness. A model can review another model's work and find things a script never could, and the gate uses exactly that, with its citations checked. Neither can be the lock. The lock is the thing that cannot be talked into anything: the invariant the prover holds in every state, the signature the model does not hold the key for, the power line the governor opens. Every time this program let a model's sentence stand in for one of those, the sentence turned out to be doing work it had not earned. The chip exists so that the sentence never gets to do that work at the point where a drone fires or a wire transfer leaves.

## Promising, and not

Promising:

- The core of the design holds in every reachable state of the abstract machine, machine-checked, and the method found two real holes the tests had missed.
- The simulation can be replayed through the theorem's machine, and the replay fails on a broken governor with the step named. The link from theorem to simulation is now mechanical rather than argued, at least for the steps the machine models.
- Two independent implementations of the policy agree on the scenarios compared except five, and those five are written down with the inputs that produce them.
- The three repositories now have signed fixtures for the messages between them, and the one place their formats differed is a failing test rather than a surprise.
- The observer has a labelled set, a scorer and a protocol for measuring what it misses, which is the only honest way to decide what it may be trusted to witness.
- The whole wave cost a few dollars and a quarter of an hour, and the gate, the backups and the second reader run on a Mac mini on my desk, with the local model taking the revisions.

Not promising, or not yet:

- The replayer passes partly because it was widened. Until the theorem's machine gains the steps the simulation takes, or the simulation loses them, "the simulation follows the theorem" is a claim with a hole in it.
- 21 of 87 catalogue entries have been compared across the two gates. Five disagreements are pinned and not yet classified as bug or ambiguity.
- The observer's miss rate has not been measured yet. The set and the scorer exist; the number does not, and the budget it will be measured against must come from the rulebook, not from an agent.
- Nothing has merged. Every result above is on a branch with a review attached, in revision.
- Two of the design's claims, the physical-path enumeration and the overhead numbers, have not been touched by an experiment yet. They are waves two and three.

## What happens next

The revisions are running, on the local model, with the findings above as their brief; the gate reviews each again, twice if needed, before a pull request waits for me. Wave two starts when the dependencies have merged: the widened proofs, the deployment-overhead simulation, the exit register with a source for every row, the observer's independence test. Wave three is the quorum arithmetic, the verdict latency, the use cases run with the real witness, and the proofs on the Verilog. After the software phase, models that wrote none of this, Codex and Gemini, get the repository and [`audit/PROMPT.md`](https://github.com/YobieBenjamin/safety-governor/blob/main/audit/PROMPT.md), which asks them to run the tests, reproduce every number, find a change that would make each test fail, and name what the program's own disproof conditions required and nobody tested.

I will publish each wave the same way, whatever it finds. If an experiment disproves the chip as designed, that is the result, and it is the reason to do this in software first. If the design survives all twenty, the next post is about an FPGA.

## Sources

Everything claimed above is in the repositories, with the wave's packet as the primary record:

- [`audit/wave-1/`](https://github.com/YobieBenjamin/safety-governor/tree/main/audit/wave-1): the briefs, the agents' own summaries, the acceptance logs, the verifier's output and the reviews, with `MANIFEST.sha256`.
- The pull requests: [safety-governor #14](https://github.com/YobieBenjamin/safety-governor/pull/14) (L4), [#15](https://github.com/YobieBenjamin/safety-governor/pull/15) (L5), [#17](https://github.com/YobieBenjamin/safety-governor/pull/17) (H1), [safety #7](https://github.com/YobieBenjamin/safety/pull/7) (YB-0052). Each carries the gate's findings as comments.
- [docs/19](https://github.com/YobieBenjamin/safety-governor/blob/main/docs/19-how-solid-is-the-theory.md), what is a theorem and what is not; [proofs/core_invariants.py](https://github.com/YobieBenjamin/safety-governor/blob/main/proofs/core_invariants.py) and [proofs/commit_point.py](https://github.com/YobieBenjamin/safety-governor/blob/main/proofs/commit_point.py), the Z3 proofs, with the two holes described in their docstrings and in the document.
- [docs/20](https://github.com/YobieBenjamin/safety-governor/blob/main/docs/20-experiment-program.md), the twenty experiments and their disproof conditions; [docs/21](https://github.com/YobieBenjamin/safety-governor/blob/main/docs/21-agent-run-plan.md), how the waves and the gate run; [`tools/agents/`](https://github.com/YobieBenjamin/safety-governor/tree/main/tools/agents), the launcher, the verifier and the reviewer.
- The catalogue count: [`results/report.md`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/results/report.md) in the reference stack, 75 attacks blocked and 12 baselines allowed.

## Run it yourself

```
git clone https://github.com/YobieBenjamin/safety-governor
cd safety-governor && make proof         # the two Z3 proofs, under a minute
./run.sh                                 # the governor: the tests, the RTL simulations, the matrix
```

If anyone wants to collaborate on any phase of this, I am here: yobie AT ieee DOT org.
