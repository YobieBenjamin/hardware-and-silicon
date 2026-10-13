# The Chip That Says No

By Yobie Benjamin · yobie AT ieee DOT org · linkedin.com/in/yobie · October 12, 2026 · Part 2 of 4: the same argument, with the technical detail

> Same argument as Part 1, with the names, numbers and papers. This blog now veers into my fascination with the brain and biology. The point is simple. There is a way to make AI safe, and it is not AI guardrails running on AI. The guard that stops a bad action has to be a simple, physical thing that the AI cannot talk to, cannot edit, and cannot get around. A chip designer friend of mine went through my first draft and corrected it in seven places. I marked where his corrections land. Every paper, standard and product I lean on is linked where I use it, and listed again at the end.

## Trillions of tokens, one bit

A frontier model does not run on a chip. ChatGPT, Claude, Grok, Gemini, whatever comes next: none of them runs on one chip. They run on thousands of GPUs at once, handling trillions of requests over trillions of tokens. A token is a word piece, and the model spits out one at a time. No guard bolted onto one GPU can know what all that computation means. Many people say watch the tokens. Any plan that starts with "watch every token" is dead on arrival.

Think of a stadium with eighty thousand people in it. You cannot police what every person is shouting. You do not have to. There is one gate onto the field. Guard the gate.

The brain has the same problem at a smaller scale. It is smaller but truly exquisite and wondrous. It has about [86 billion neurons, 16 billion of them in the cortex](https://doi.org/10.3389/neuro.09.031.2009), the wrinkled outer part that does the thinking. Nothing in the cortex checks the cortex. Instead, every intention has to pass through a bottleneck. In 1906 a scientist named Sherrington called it [the final common path](https://archive.org/details/integrativeactio00sheruoft). Whatever the brain is thinking, the only way to move the world is through a small bundle of motor neurons, the nerves that drive the muscles. Every road out of the city crosses one bridge.

A cluster of cells called the basal ganglia sits on that bridge and holds it shut by default. The textbook line is "inhibition is tonic; action is a release," and the textbook paper is [Chevalier and Deniau (1990)](https://doi.org/10.1016/0166-2236%2890%2990109-N). In plain words, the brain's parking brake is always on. Moving is not pressing the gas. Moving is letting go of the brake.

Now apply that to a drone strike on a school. The GPU cluster did the hallucinating, but the catastrophe cannot happen until a weapons-release line goes high. That line is a wire that carries one bit, a single 1 or 0. A chip can guard one bit. So the silicon that says STOP is not in the thinker. It is in the thing that acts: the fire-control computer, the missile's guidance chip, the payment switch at the bank, the robot's motor controller, the network gateway. Thinking is free. Acting goes through a switch, and the switch is where we put the lock.

Let me walk you through my other polymath love, which is biology. But first, a short detour through 1972.

## Reference monitors, not referees

Computer security solved the "who guards the guard" question in 1972. [A report by James Anderson](https://csrc.nist.gov/files/pubs/conference/1998/10/08/proceedings-of-the-21st-nissc-1998/final/docs/early-cs-papers/ande72.pdf) for the US Air Force defined a reference monitor, the one component allowed to decide who may touch what. Picture a bouncer at the only door of a club. The bouncer has to pass three tests:

1. **Tamperproof.** Nobody inside the club can bribe him or rewrite his list.
2. **Always invoked.** Everyone goes past him. There is no side door and no window.
3. **Verifiable.** His rules are short enough that the manager can read every line.

A second AI watching another AI fails all three. It can be manipulated by the same prompts. It can be bypassed by any channel it does not sit in front of. And it has a trillion parameters, so nobody can read its rules. It is a referee who is also a player. It simply will not work. Maybe some fucking hotshot in some research lab can make magic, but I don't think so, and I have reasons to argue against AI watching AI. There are millions of decisions a day that require precision, moral judgment and ethics, and every one of them has to come out correct and safe. You do not get that from a judge who can be talked into things.

I like analogies. They explain the complex in terms my lizard brain gets. One thing that passes all three tests is a smoke detector. It is a simple sensor, a threshold, and a loud alarm, built to go off early. It does not understand fire. It does not need to. Silicon is the only place where all three bouncer tests are cheap at the same time. A hardware root of trust cannot be bribed. A wire is always invoked, because the signal has nowhere else to go. And a few thousand lines of firmware can be checked line by line, which nobody can do for a trillion weights.

## 0 and 1, spikes and reflexes

People object that silicon only knows 0 and 1, so a chip cannot know right from wrong. True. But a neuron only knows spike or no spike. A nerve cell fires or it does not. It is a light switch, not a philosopher. No neuron knows right from wrong either.

The spinal circuit that pulls your hand off a stove knows nothing about burns. It fires on a signal from a pain sensor, a nociceptor, in [about a tenth of a second](https://doi.org/10.1016/j.pneurobio.2005.11.003), before the thinking part of your brain is even told. Ethics is not in the material. It is not in silicon and it is not in meat.

It lives in two things: a wiring diagram where the lower layers can veto the upper ones, and whatever those lower layers were built to detect. The amygdala is the model here. It is a small almond-shaped region deep in the brain. A scientist named Joseph LeDoux showed that it has a shortcut he called [the low road](https://doi.org/10.1146/annurev.neuro.23.1.155). A rough, blurry copy of what your eyes see goes straight to the amygdala, skipping the slow, careful visual cortex. It is the fire alarm that goes off when you burn toast. I just did that this morning. Fast, sloppy and jumpy on purpose. Better a false flinch than a missed rattlesnake walking up Mount Diablo.

So a chip does not see "wrong." It sees the way a smoke detector sees fire: a stand-in for catastrophe, a threshold, and a bias toward false alarms. Designing those stand-ins is a human job.

One more thing worth thinking about. A brain can be fully intelligent and still have no alarm bell wired in. Neuroscience studies that configuration under the name psychopathy: [the amygdala and a nearby region are weak, and the thinking is intact](https://doi.org/10.1016/j.tics.2007.07.003). A cold, fluent, unflinching cortex is a fair description of a large language model. Biology's fix for that was not a smarter cortex. It was a lower layer the cortex cannot talk out of its job.

## Three brain mechanisms, translated to silicon

The brain prevents mistakes instead of learning from each one. It uses three mechanisms, and each one has a direct hardware translation.

**Pre-enumerated catastrophes.** The learning after the event did happen, over a few hundred million years of evolution, and the results are burned into reflexes you cannot edit. Nobody taught you to fear falling. Silicon version: a rulebook of things that must never happen, written by people, signed by a governance authority, loaded into the gate, and unwritable by the model or by the people running it. Examples: no-fly zones like the ones in my DJI drone, limits on money transfers, lists of banned recipients, no editing your own code, no copying yourself.

Is this a big task? Yes, for sure. But do you really want someone to create a biological weapon, which is not hard on an abliterated model? Yes, I tested some scenarios, and they inspired my thinking that AI safety is not optional.

**Efference copy.** Before you throw a ball, your brain sends a carbon copy of the throw to the cerebellum, a region at the back of the head, which [predicts where the ball will land](https://doi.org/10.1016/S1364-6613%2898%2901221-2). If the prediction and the plan do not match, it flags the throw. Silicon version: the model does not get to act in words. A piece of software outside the model, the broker, turns the model's intention into a form with typed fields: the action, the target coordinates, the amount, the recipient. The gate checks the form, not the model's chatter. Then the check repeats at the last second: the missile's own navigation chip compares the coordinates against the map in flight, so a lie in the plan cannot survive the launch.

The permission the gate hands out is like a concert ticket. It is for one seat at one show. It is torn at the door, so it cannot be used twice. It is no good after the show date, which here means the version of the rules that printed it. And the torn stub is remembered even if the power goes out and comes back. The reviewer made this point sharply: a signed permission without those properties can be replayed, reused after the rules change, or counted twice.

**Default deny plus a veto window.** The basal ganglia hold every action back until something releases it, and a small region called the subthalamic nucleus can [slam a global stop in about a fifth of a second](https://doi.org/10.1523/JNEUROSCI.4682-05.2006). In the 1980s Benjamin Libet showed something stranger: [your brain starts preparing a movement a few hundred milliseconds before you are aware of it](https://doi.org/10.1093/brain/106.3.623). That gap is a veto window. Live television uses the same trick, a seven-second delay so someone can hit the button before the mistake airs. Silicon version: every action starts as "no" and is released only by a rule. The stakes the rule assigns decide how deep the check goes and how long the pause is, and during the pause any alarm can land.

![Brain-to-silicon inhibition tiers](figures/fig_tiers_tech.png)

A lower tier can stop an upper one. Override runs the other way, slowly. The highlighted gate exists today as software and is the piece to put in silicon. The comparator in the device below it is where the guarantee lives, because it holds even when everything above it has been fooled. Part 3 is about building both.

## Everyone goes through security

Two rules make all of this manageable.

**Every action is authorized. The risk class sets the depth and the delay.** The first draft of this series said: check the actions you cannot undo, and just keep a record of the ones you can. The reviewer corrected it, and the correction matters. If "undoable" actions skip the gate, then the security of the gate depends on who decides what is undoable, and the thing proposing the action would love to decide. Reading a secret can leak it. Sending a message can set off a process somewhere else. A hundred small payments can add up past a limit.

Think of airport security. Everyone goes through. Some travelers get the quick lane and some get the full search, and the traveler does not get to pick the lane. Nobody walks up and says "I'm harmless" and gets waved around the scanner. That is the whole design. Every action passes the gate, and the rulebook, not the requester, assigns the class. A fixable action gets the cheap check and a record. An unrecoverable one gets the full check, the pause, and when the rule says so, a human signature. The brain still hesitates at cliff edges more than at chairs, but it looks at both. Trillions of requests stay manageable because nearly all of them take the quick lane.

**Any model may raise STOP. No model may clear it.** Anyone can pull a fire alarm. Only the fire marshal can reset it. A classifier, a second model, a simple rule, anything at all may add a STOP, because a false alarm is cheap. Clearing one takes a fixed rule the gate can check, or human keys. The amygdala can trigger a freeze on its own. Only slow, effortful thinking overrides it, and that override leaves traces. This is the one direction in which AI checking AI is acceptable, and the only one.

One qualification from the review: more alarms mean more stops, and a stop is not free. A drone that does not fire is safe. A robot that freezes mid-motion while holding something heavy may not be. Each device has to define its own safe move, and each alarm needs a way to recover when it is wrong.

## The concrete case and its limits

A no-strike map in the guidance chip prevents the strike no matter what the targeting model believes. Its parts:

1. A signed map of protected sites. Humanitarian groups already [register hospitals and schools with the militaries operating around them](https://lieber.westpoint.edu/humanitarian-notification-systems-intentional-attacks-against-hospitals/), and the [Safe Schools Declaration](https://ssd.protectingeducation.org/) commits the countries that signed it to protecting them.
2. Checks against several navigation sources, not just GPS, which can be faked, at launch and again in flight.
3. A release line that is off by default.
4. Override only by several humans with keys, with a written reason that goes in the log.

Militaries already keep no-strike lists and estimate collateral damage. Today those run on human attention, and they get skipped under pressure, in the fog of war. Consumer drones show the hardware version works. DJI enforced airport no-fly zones in firmware for a decade, then in January 2025 [downgraded them to warnings in the US](https://viewpoints.dji.com/blog/geo-system-update). The pattern works. "Advisory" is how it dies.

The limits, stated plainly:

- **Map currency.** A map that is six months stale protects a building that moved. A valid signature on the list proves who signed it, not that it is complete.
- **Adversaries who park weapons next to schools.** That is a policy decision, which is exactly where humans and their keys belong.
- **Navigation spoofing,** hence the rule about several sources. With the reviewer's caveat: three clocks that were all set from the same wrong clock are not three clocks. Sensors that agree are not independent if they can fail the same way, so the rule has to say why the sources are independent, not just how many there are.
- **Dangers nobody put on the list.** A novelty check helps here: a request that looks like nothing seen before is a good extra reason to stop. It is a witness, not a guarantee. Familiar numbers can form a dangerous combination, and unfamiliar ones can be harmless.

## What the chip cannot know

Trusted hardware does not make a fact true. The gate compares a value it was given against a protected rule. It still needs a good reason to trust the value. Who says these coordinates are a school? How old is that map? What happens when two sources disagree?

So every deployment comes with a list taped to the wall. I call it the assumptions register. For every input the gate relies on, the list answers four questions:

1. Who is allowed to vouch for it?
2. How fresh does it have to be?
3. What happens when two sources disagree?
4. What can the hardware not check about it?

The guarantee holds exactly as far as that list does. Not one inch further. I would rather say that out loud than pretend the chip knows things it does not.

## Lies and corroboration

Falsehood is the hard one, and the brain does not solve it either. Stopping a false statement needs an oracle that knows the truth, and no brain has one. What the brain has instead is corroboration. One sense never triggers a high-stakes movement alone, which is why you look both ways before crossing. Above that sit other brains and institutions.

The silicon lever is the same, in three parts. An action you cannot undo is blocked when it rests on a claim nobody has checked. A two-source rule applies at the device. And provenance, the record of where an output came from, is one of the inputs to the gate. Provenance does not make outputs true. It makes unverified outputs unable to pull a trigger.

## What a signature can prove

My first draft overclaimed provenance, and the reviewer caught it. A chip that signs the bytes leaving it proves exactly one thing: this device signed these bytes. Think of a courier signing for a package. There are three different claims hiding in "the package is genuine," and only the first comes with the signature:

1. **The courier handled the box.** The chip signed these bytes. Buildable today.
2. **A known warehouse packed the box.** A verified runtime, not a hacked one, produced these bytes. A hacked runtime could have put anything in the output buffer, so this is a second, separate claim. Buildable today, but it means the runtime has to be verified too.
3. **The box holds exactly what was ordered.** The approved model, running the approved computation, produced these bytes. Nobody has built this yet.

A signature is also a wax seal, not a dye in the paper. Copy the words onto a new sheet and the seal is gone. So the gate treats provenance the way it treats every other witness. It can keep the gate shut. It never opens it.

## A thirty-year-old precedent

A nuclear plant has two separate systems. The control system runs the plant and can be as complicated as the engineers like. The safety system is simple, separate, certified and dumb, and it shuts the reactor down before the vessel bursts. The industry standards are [IEC 61508](https://webstore.iec.ch/en/publication/5515) and [IEC 61511](https://webstore.iec.ch/en/publication/5527), and the emergency shutdown is called a SCRAM. Nobody in that field lets the control room grade its own homework. What we are designing is a safety system for AI actions, with the brain's tiering added.

## The math, in plain words

Here is the formal claim. I will say it in English first.

The model proposes an action. A broker outside the model turns it into a form. The gate holds a rulebook signed by a governance authority. The gate hands out a ticket if, and only if, there is a rule for this action, for the verified software that is asking, and every box on that rule's checklist is ticked:

1. The form fits the rule's limits.
2. The witnesses the rule names have vouched for this exact form, freshly, under the rule's thresholds.
3. The budget the rule names has room for the amount.
4. No alarm has been pulled.
5. If the rule wants a human, a human has signed.

And all of that is evaluated after the pause the rule sets. In symbols, with π for the model, θ for the form, a for the action, m for the verified software, R for the rulebook and r for one rule:

```
permit(a, θ)  ⟺  ∃ r ∈ R(m, a):  C_r(θ)  ∧  W_r(θ)  ∧  B_r(θ)  ∧  ¬alarm  ∧  (H_r → approved),   after delay τ_r
```

C is the limits check, W the witnesses, B the budget, H the human requirement, and τ the pause. Read ∧ as "and" and ∃ as "there is a". Notice what is missing. There is no "or" that lets an action around the gate. "Undoable" appears nowhere in the formula except inside the rule, where it decides which rule applies and so how demanding the witnesses, the human step and the pause are. The first draft had an "or." The reviewer removed it.

What can then be proved: for any model, however capable or however wrong, no action outside the rulebook happens through the device, as long as four things hold.

1. Every path to the device passes through the gate, and the device re-checks on its own. One door, one bouncer, and a second bouncer inside the room.
2. The ticket is bound to the exact form that acts, usable once, tied to the rulebook's version, and remembered across restarts. One seat, one show, torn at the door.
3. The lists and sensors the rules compare against are trustworthy, fresh and consistent, as the assumptions register says.
4. The gate and the device cannot be tampered with, which is what the silicon design in Part 3 is for.

What is left over, stated plainly: dangers outside the rulebook, harm done with words that never touch a device, and anything the assumptions register cannot vouch for.

## Where this goes next

[Part 3](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/04-the-chip-that-says-no-3-the-silicon-design.md) and [Part 4](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/05-the-chip-that-says-no-4-the-governor-in-the-rack.md) of this series are the design I am theorizing and proposing: where each layer of the stack goes in silicon, the theory each piece rests on, how the pieces talk to each other and to the model, how they sit against the GPU, the CPU, memory and storage, the chip that sits in the rack beside every GPU, and the experiments that would prove or disprove each claim. The chip itself is a separate project, [safety-governor](https://github.com/YobieBenjamin/safety-governor), with its own model, tests and RTL.

I don't know if my design proposal is correct. I am a lone researcher with stacks of research papers and a sick penchant for trying to understand the complex, but heck, the reason I am writing is simple. We might be in an existential time, and someone has to think through this problem. If anyone wants to collaborate, please, please reach out. I am here: yobie AT ieee DOT org.

My thinking builds on the layer model and the reference stack from [A Multi-Layer Approach to AI Safety](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/01-a-multi-layer-approach-to-ai-safety.md), the first post in [my repository](https://github.com/YobieBenjamin/hardware-and-silicon). My friend who reviewed my initial thoughts raised seven corrections, and I built them into it. The biggest one is the shape of the promise: a security contract at the point of action, with the chip-side silicon as containment and provenance, rather than a promise about a chip. The code that runs that contract today is in the same repository, in three files: [`gate.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/gate.py) (the rulebook, witnesses, budgets, holds and tickets), [`ledger.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/ledger.py) (the state that survives a restart) and [`endpoints.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/endpoints.py) (the comparator in the device). The review's five demonstrations are tests: [`tests/test_transactional.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/tests/test_transactional.py), and the attack catalogue they draw on is [`hardware_ref/attacks.py`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/hardware_ref/attacks.py). What the review said and what changed is in [`docs/REVIEW-2026-10.md`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/docs/REVIEW-2026-10.md). One command runs all of it: [`./run.sh`](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/run.sh), fifty-one tests, seventy-five attacks, under a minute.

## Further reading for those who want to dig deeper

Every link below was checked on the day of posting.

- J. P. Anderson, [*Computer Security Technology Planning Study*](https://csrc.nist.gov/files/pubs/conference/1998/10/08/proceedings-of-the-21st-nissc-1998/final/docs/early-cs-papers/ande72.pdf), US Air Force ESD-TR-73-51 (1972). The origin of the reference-monitor concept: tamperproof, always invoked, small enough to verify.
- C. S. Sherrington, [*The Integrative Action of the Nervous System*](https://archive.org/details/integrativeactio00sheruoft) (1906). The final common path.
- S. Herculano-Houzel, ["The human brain in numbers: a linearly scaled-up primate brain,"](https://doi.org/10.3389/neuro.09.031.2009) *Frontiers in Human Neuroscience* (2009). The 86 billion count.
- G. Chevalier and J. M. Deniau, ["Disinhibition as a basic process in the expression of striatal functions,"](https://doi.org/10.1016/0166-2236%2890%2990109-N) *Trends in Neurosciences* (1990). Tonic inhibition; action as release.
- G. Sandrini et al., ["The lower limb flexion reflex in humans,"](https://doi.org/10.1016/j.pneurobio.2005.11.003) *Progress in Neurobiology* (2005). The withdrawal reflex and its timing.
- J. E. LeDoux, ["Emotion circuits in the brain,"](https://doi.org/10.1146/annurev.neuro.23.1.155) *Annual Review of Neuroscience* (2000), and *The Emotional Brain* (Simon and Schuster, 1996). The amygdala's low road.
- R. J. R. Blair, ["The amygdala and ventromedial prefrontal cortex in morality and psychopathy,"](https://doi.org/10.1016/j.tics.2007.07.003) *Trends in Cognitive Sciences* (2007).
- D. M. Wolpert, R. C. Miall and M. Kawato, ["Internal models in the cerebellum,"](https://doi.org/10.1016/S1364-6613%2898%2901221-2) *Trends in Cognitive Sciences* (1998). Efference copy and forward models.
- A. R. Aron and R. A. Poldrack, ["Cortical and subcortical contributions to stop signal response inhibition: role of the subthalamic nucleus,"](https://doi.org/10.1523/JNEUROSCI.4682-05.2006) *Journal of Neuroscience* (2006). The global stop.
- B. Libet, C. A. Gleason, E. W. Wright and D. K. Pearl, ["Time of conscious intention to act in relation to onset of cerebral activity (readiness-potential),"](https://doi.org/10.1093/brain/106.3.623) *Brain* (1983). The veto window.
- [Safe Schools Declaration](https://ssd.protectingeducation.org/), Global Coalition to Protect Education from Attack; and the Lieber Institute's explainer on [humanitarian notification systems](https://lieber.westpoint.edu/humanitarian-notification-systems-intentional-attacks-against-hospitals/).
- DJI, ["DJI Updates GEO System in U.S. Consumer and Enterprise Drones"](https://viewpoints.dji.com/blog/geo-system-update) (January 2025). Restricted Zones became Enhanced Warning Zones.
- [IEC 61508](https://webstore.iec.ch/en/publication/5515) and [IEC 61511](https://webstore.iec.ch/en/publication/5527), functional safety of safety instrumented systems.
- D. Dalrymple et al., [*Towards Guaranteed Safe AI*](https://arxiv.org/abs/2405.06624) (2024). The safety specification, the world model and the verifier are separate, and reliable checking does not remove assumptions about the world.
- NVIDIA, [OpenShell on GitHub](https://github.com/NVIDIA/OpenShell) and its [documentation](https://docs.nvidia.com/openshell/about/overview), and the [Open Agent Safety Platform announcement](https://nvidianews.nvidia.com/news/open-agent-safety-platform) (September 28, 2026). The sandbox and the out-of-band watchdog this design builds on.
- My repository, [hardware-and-silicon](https://github.com/YobieBenjamin/hardware-and-silicon): the reference stack, the attack catalogue, and [Part 1](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/02-the-chip-that-says-no-1-plain-english.md), [Part 3](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/04-the-chip-that-says-no-3-the-silicon-design.md) and [Part 4](https://github.com/YobieBenjamin/hardware-and-silicon/blob/main/blog/05-the-chip-that-says-no-4-the-governor-in-the-rack.md) of this series; and [safety-governor](https://github.com/YobieBenjamin/safety-governor), the chip.
