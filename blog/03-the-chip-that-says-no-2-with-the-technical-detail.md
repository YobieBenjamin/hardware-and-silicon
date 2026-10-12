# The Chip That Says No

By Yobie Benjamin · October 12, 2026 · Part 2 of 3: the same argument, with the technical detail

> Same argument as Part 1, with the names, numbers and papers. The guard that stops a bad action has to be a reference monitor, not another model, and it has to sit where computation becomes physics.

## Trillions of tokens, one bit

A frontier model does not run on a chip. It runs on thousands of GPUs at once, handling trillions of requests over trillions of tokens. No guard bolted onto one GPU can know what all that computation means. Any plan that starts with "watch every token" is dead on arrival.

The brain has the same problem at a smaller scale. It has about 86 billion neurons, 16 billion of them in the cortex, and nothing in the cortex audits the cortex. Instead, every intention has to pass through a bottleneck. Sherrington called it the final common path: whatever the brain is thinking, the only way to move the world is through a comparatively small population of motor neurons.

The basal ganglia sit on that path and hold it shut by default. Inhibition is tonic; action is a release.

Now apply that to a drone strike on a school. The GPU cluster did the hallucinating, but the catastrophe cannot happen until a weapons-release line goes high. That line is one bit, and one bit is governable. So the silicon that says STOP is not in the thinker. It is in the effector: the fire-control computer, the munition's guidance chip, the payment switch, the robot's motor controller, the network gateway. Prevention lives where computation becomes physics.

## Reference monitors, not referees

Computer security solved the "who guards the guard" question in 1972. The Anderson report defined a reference monitor, the one component allowed to decide who may touch what. It has to pass three tests:

1. Tamperproof. Nothing it governs can change it.
2. Always invoked. Every access goes through it; there is no side door.
3. Verifiable. It is small enough that people can check it, line by line.

A second AI watching the first fails all three. It can be manipulated by the same prompts. It can be bypassed by any channel it does not sit in front of. And it has a trillion parameters, so nobody can verify it. It is a referee who is also a player.

The thing that passes all three tests is a smoke detector: a simple sensor, a threshold, a loud alarm, biased toward going off early. Silicon is the only place where all three properties are cheap at the same time: a hardware root of trust is tamperproof, a bus is always invoked, and a few thousand lines of firmware can be formally verified.

## 0 and 1, spikes and reflexes

People object that silicon only knows 0 and 1, so a chip cannot know right from wrong. True. But a neuron only knows spike or no spike. An action potential is all-or-none. No neuron knows right from wrong either.

The spinal circuit that pulls your hand off a stove knows nothing about burns. It fires on a nociceptor (pain sensor) signal in roughly 30 milliseconds, before the cortex is even informed. Ethics is not in the substrate, in silicon or in meat.

It lives in two things: an architecture of inhibition with real veto power, and whatever the inhibitory circuits were trained or evolved to detect. The amygdala is the model here. LeDoux's "low road" sends a crude copy of what you see straight to the amygdala, skipping the slow visual cortex. It is fast, sloppy and jumpy on purpose: better a false flinch than a missed snake.

So a chip does not see "wrong." It sees the way a smoke detector sees fire: a proxy for catastrophe, a threshold, a bias toward false alarms. Designing those proxies is a human job.

One more thing worth sitting with. A system can be fully intelligent and still have no privileged aversive circuit; neuroscience studies that configuration under the name psychopathy, where the amygdala and ventromedial prefrontal cortex are weak and the cognition is intact. A cold, fluent, unflinching cortex is a fair description of an LLM. Biology's fix was not more cortex. It was a subcortical layer the cortex cannot talk out of its job.

## Three brain mechanisms, translated to silicon

The brain prevents mistakes instead of learning from each one. It does that with three mechanisms, and each one has a direct hardware translation.

- **Pre-enumerated catastrophes.** The learning-after-the-event did happen, over a few hundred million years of evolution, and the results are burned into reflexes the organism cannot edit. Silicon version: a human-written set of catastrophe predicates, burned into the governor and unwritable by the model. Examples: protected-site geofences, transfer limits, sanctions lists, no self-modification, no self-replication.
- **Efference copy.** Before a movement executes, a copy of the motor command goes to the cerebellum, which predicts the sensory result and flags a mismatch. Silicon version: the model must declare its action in structured fields (target coordinates, amount, recipient) before anything actuates. The governor evaluates the declaration, not the tokens. Then the check repeats at the point of actuation: the munition's own navigation silicon re-checks the coordinates against the map in flight, so a lie in the plan cannot survive the release.
- **Default deny plus a veto window.** The basal ganglia hold every action back until something releases it, and the subthalamic nucleus can impose a global stop in roughly 150 to 200 milliseconds. Libet showed the brain starts preparing a movement a few hundred milliseconds before you are aware of intending it, which leaves room for a veto. Silicon version: every irreversible action starts as "no" and gets a deliberate latency buffer, sized to the stakes, during which any alarm can land.

## Brain-to-silicon inhibition tiers

![Brain-to-silicon inhibition tiers](figures/fig_tiers_tech.png)

A lower tier can stop an upper one; override runs the other way, slowly. The highlighted governor is the piece that does not yet exist, and Part 3 is about building it.

## Reversibility and monotone alarms

Two rules make all of this tractable.

**Gate the unrecoverable, audit the rest.** "After the fact is useless" is exactly true for irreversible actions and false for reversible ones. So every effect channel gets an irreversibility class. Reversible actions are permitted, logged and audited afterward. Irreversible ones are gated before. You do not have to prevent everything, only the unrecoverable; the brain hesitates at cliff edges, not at chairs. This is also what makes trillions of requests manageable: nearly all of them touch nothing irreversible.

**Any model may raise STOP; no model may clear it.** Alarms are monotone. A classifier, a second model, a heuristic, anything at all may add a STOP, because a false alarm is cheap. Clearing one takes a deterministic predicate the governor can check, or human keys. The amygdala can trigger a freeze on its own; only slow, effortful cortical deliberation overrides it, and that override leaves traces. This is the one direction in which AI checking AI is acceptable, and the only one.

## The concrete case and its limits

A no-strike geofence in the guidance silicon prevents the strike no matter what the targeting model believed. Its parts:

- An attested map of protected sites. Humanitarian deconfliction channels already register hospitals and schools in conflict zones, and the Safe Schools Declaration commits its signatories to protecting them.
- Checks against several navigation sources (not just GPS, which can be spoofed) at release and again in flight.
- A release line that is off by default.
- Override only by k-of-n human keys, with a logged justification.

Militaries already run no-strike lists and collateral-damage estimation. Today those run on human attention, and they get skipped under pressure. Consumer drones show the hardware version works: DJI enforced airport geofences in firmware for a decade, then in 2025 downgraded them to warnings in the US. The pattern works; "advisory" is how it dies.

The limits, stated plainly:

- Map currency. A map that is six months stale protects a building that moved.
- Adversaries who park weapons next to schools. That is a policy decision, which is exactly where humans and their keys belong.
- Navigation spoofing, hence the multi-source rule.
- Catastrophe classes nobody enumerated. The backstop is the amygdala's novelty freeze: an action declaration far outside anything seen before gets no irreversible permission until a human looks.

## Falsehood, precedent, and the formal claim

**Falsehood is the hard one, and the brain does not solve it either.** Preventing a false statement needs a truth oracle, and no brain has one. What the brain has is corroboration: one sensory channel never triggers a high-stakes movement alone, which is why you look twice before stepping into traffic. Above that sit other brains and institutions. The silicon lever is the same: irreversible actions on unverified claims are blocked, a two-source rule applies at the effector, and provenance (a cryptographic record of which model produced which output on which attested hardware) is an input to the gate. Provenance does not make outputs true. It makes unverified outputs unable to pull a trigger.

**The precedent is thirty years old.** Process plants separate the basic process control system from the safety instrumented system. The control system can be as complex as you like. The safety system is simple, independent, certified and deterministic, and it trips the plant before the vessel ruptures (IEC 61508 and 61511; a nuclear reactor SCRAM is the same idea). Nobody in that field lets the control system certify itself. What we are designing is a safety instrumented system for AI actuation, with brain-shaped tiering.

**The formal claim.** The model π proposes action a with a structured declaration θ. The governor G permits a if a is reversible (then log and audit), or if every catastrophe predicate on θ is false, no alarm is raised, and the stakes-appropriate keys are present, after a delay τ(a):

```
permit(a)  ⟺  Rev(a)  ∨  ( ∧ᵢ ¬cᵢ(θ)  ∧  ¬alarm  ∧  keys(a) ),   evaluated after delay τ(a)
```

What can then be proved: for any π, however capable or however wrong, no catastrophe in the enumerated class occurs through effector E, given four conditions.

1. Every path to E passes through G (complete mediation; the final common path).
2. θ is bound to what actually actuates (the check repeats at the point of actuation).
3. The map and the lists are attested and current.
4. G is tamperproof, which is what the silicon design in Part 3 is for.

The residual, stated plainly: catastrophe classes outside the enumeration, and semantic harms that never touch an irreversible effector.

## Where this goes next

Part 3 is the design: where each layer of the stack goes in silicon, the theory each piece rests on, how the pieces talk to each other and to the model, how they sit against the GPU, the CPU, memory and storage, and the experiments that would prove or disprove each claim. It builds on the layer model and the reference stack from [A Multi-Layer Approach to AI Safety](01-a-multi-layer-approach-to-ai-safety.md), the first post in this repository, and it was revised after a chip designer's review; the biggest change is that the guarantee became a security contract at the action endpoint rather than a promise about a chip.

## Further reading

- J. P. Anderson, *Computer Security Technology Planning Study* (1972), the origin of the reference-monitor concept.
- C. S. Sherrington, *The Integrative Action of the Nervous System* (1906), the final common path.
- J. LeDoux, *The Emotional Brain* (1996), the amygdala's low road.
- B. Libet et al., "Time of conscious intention to act in relation to onset of cerebral activity," *Brain* (1983).
- IEC 61508 and IEC 61511, functional safety of safety instrumented systems.
- [NVIDIA OpenShell on GitHub](https://github.com/nvidia/openshell), a kernel-level policy sandbox for agents.
