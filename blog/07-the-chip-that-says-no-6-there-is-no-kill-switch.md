# The Chip That Says No

By Yobie Benjamin · yobie AT ieee DOT org · linkedin.com/in/yobie · October 21, 2026 · Part 6: there is no kill switch

> Every few weeks somebody important says the answer to AI safety is a kill switch. A big red button. If the AI misbehaves, we turn it off. I do not believe a word of it, and I am going to show you why with a few drawings and a piece of mathematics from 1927 that you can follow with a pencil. Then I am going to show you where a switch can actually go, because there is a place, and it is the whole reason I am building a chip.

## The picture in your head

When people say kill switch, here is the picture they have: one AI, one machine, one wire, one button. Pull the wire and it stops.

That picture was true for the computer in the movie, and it has never been true for the thing we have now.

![The picture in your head, and the picture that is true](figures/fig_ks_picture.png)

Here is the picture that is true. There is not one AI. There are copies. Every big lab has a model that can write the same scam email and plan the same fraud. Open models, the ones with their weights published, are sitting right now on hundreds of thousands of private machines, from server farms to a gaming PC in somebody's bedroom. None of these copies needs any of the others to run. People like to say the models are all connected because they were all trained on the same Internet. That is not connected. That is *copied*. It is worse for the kill-switch crowd than connected would be, because it means there is no one you can call, no one wire, and no owner of the list. Pull any one plug and nothing changes.

Between those copies and the world sits the network. The network was designed, on purpose, to have no middle. Paul Baran drew it that way at RAND in 1964: a distributed web with no centre to hit, so that a message could always find another road. The Internet grew up in that shape. It is the one piece of infrastructure humanity built specifically so that there would be no switch.

And at the far edge of the network sit the things that actually matter: the bank's payment switch, the drone's release line, the robot's motor, the relay in the power station, the storage box that holds a model's weights. Those are the places where an AI's words turn into something you cannot take back.

So when someone says kill switch, ask them: where exactly is the wire?

## A hundred-year-old theorem about guards

I promised mathematics, and here it is. It is called Menger's theorem, Karl Menger proved it in 1927, and it is about roads and guards.

![Menger's theorem, with roads and guards](figures/fig_ks_menger.png)

Suppose two towns are joined by three roads that never cross each other. You want to stop all traffic between them. How many guards do you need? Three. Not two. Put guards on two roads and the traffic takes the third. Menger's theorem says this is always true, for any map: the smallest number of guards that stops all traffic between two places is exactly the number of separate roads between them. Separate meaning they share no crossing. Computers can calculate that number for any map in a fraction of a second.

Now look at a house. Roads come from everywhere, and they all funnel into one driveway. One guard at the door stops everything. Same theorem, different place. The number of guards you need is smallest where the roads come together, and the roads come together at the ends. In the middle of a well-built network they fan out, which is the whole point of a well-built network.

Hold on to that. The smallest cut is at the ends. Everything else in this post is that sentence applied to AI.

## The whole thing as a graph

Let me draw the real situation as a map of roads and guard posts. Mathematicians call it a graph. It is just dots and lines.

![The whole thing as a graph](figures/fig_ks_graph.png)

On the left, the model copies, and the chip each one runs on. In the middle, the network. On the right, the devices that act, each with a controller that every command passes through, and the deed on the other side of it. Top and bottom, everyone else: the billions of people and services using the same network who have nothing to do with AI.

A kill switch, in this picture, is a set of dots you remove so that no road is left from any copy to any device. The question is: where are the smallest sets, what do they cost, and who else do they take down?

## Where could the switch go?

I built exactly this graph in code and had the computer find the smallest cuts, using the max-flow method that turns Menger's theorem into arithmetic. Sixty network nodes with six separate roads to every point, twelve model copies, ten devices, forty bystanders, and one laptop wired straight to a motor with no network in between. The file is in the repository and it checks itself against brute force. The numbers are the model's, not the Internet's, and the shape is what matters.

![Where could the switch go? Five places, measured on the model](figures/fig_ks_cuts.png)

Deep in the network: **there is no cut at all.** Not a big one. None. Once you stay away from the links right next to the machines, the middle is so connected that no set of nodes separates the copies from the devices. That is Baran's design doing its job sixty years later.

At the edge, one hop from every machine: a cut exists. It takes 43 guards in a network of 60, it removes 72 percent of the core, and it severs 19 percent of the connections between ordinary people and ordinary services who were just trying to check their email. And notice what it needs: a list of every machine, because every guard stands next to one. If you have the list of every machine, you did not need the network switch. You could have put the gate in the machine.

At the devices: 11 guards, one per device, nobody else touched. At the chips: 13 guards, one per copy, nobody else touched. And if you only guard the devices whose deed cannot be undone, the ones where "can you undo it?" gets a no, it is 6.

That is Menger's theorem with numbers on it. The only small, clean cuts are at the ends.

## "But Iran switched off the Internet"

I hear this one a lot. Yes. Iran has switched off its Internet more than once, for days. So did others. Look at what that actually was, because it is not a counterexample. It is the theorem demonstrated.

![But Iran switched off the Internet. Yes. Look at what that was.](figures/fig_ks_country.png)

A country's shutdown is an edge cut on one region. The government owns or controls every access link inside the border, so it has the list. It cuts them. Four things follow, and all four are on the drawing.

It did not kill the Internet. It killed Iran's corner of it. The rest of the world did not notice except in the news. The copies of every model outside the border kept running and the devices outside kept acting.

It took everyone in the country down with it. Hospitals, banks, kids doing homework. That is the collateral bar in the chart, except at 100 percent.

It needed the list. A government that owns every ISP in its territory is the one actor in the world that has the list of every machine in one region. Nobody has the list for the planet.

And it had a hole. The government kept its own lines. The elite kept theirs. North Korea runs this way permanently: a national intranet for the many and the real Internet for the few. A cut with a hole in it is not a cut, by definition, and an AI kill switch built the same way would switch off the public's models and leave the state's running. That is the opposite of safety. It is the only kind of kill switch a government can build, and it is the one you would least want.

## Too little, as well as too much

One more drawing, and it is the one that embarrasses the whole idea.

![Too little as well as too much: the laptop and the motor](figures/fig_ks_local.png)

A model on a laptop, wired by one cable to the motor it drives. No network anywhere. Switch off every router on Earth and nothing happens here. The only cut is the cable, or a gate in the motor's controller. The network switch, if you could build it, which you cannot, would miss the case that matters most: a machine that acts on the world right in front of it.

## So where does the switch go?

At the ends. That is what the theorem says, and the measured cuts say the same thing. Two ends, and you should know which one to prefer.

![So the switch goes at the ends, and it is a gate, not a switch](figures/fig_ks_exits.png)

The source end is the chip the model runs on. A gate there catches an action before it ever reaches the network, and it has the levers behind it: slow the GPU down, reset it, cut its power, cut its links. That is the governor from Parts 3, 4 and 5. But there are a great many sources, the number grows every time someone uploads a weight file, and nobody owns the list. You will never finish gating that end.

The device end is the controller inside the thing that acts. There are far fewer of those than there are model copies. The world has a countable number of wire-transfer switches, weapon release lines and motor drivers, they change slowly, and they do not multiply when a model gets copied. Menger says the smallest cut is at the smaller end, and this is the smaller end. Gate the exits.

And here is the part that makes it a chip project rather than a slogan. A switch stops everything, which nobody will accept, because the same wire that could fire a missile also delivers insulin. A *gate* is different. A gate lets through exactly what a signed rulebook allows and nothing else. The software around the model fills in a plain form: what, to whom, how much. The gate checks the form against rules signed by people the model cannot talk to. If every box is ticked, it issues a signed ticket, and the device at the far end checks the ticket for itself before it moves. No ticket, nothing moves. That is the reference monitor, the oldest idea in computer security, and the proofs in the repository show the governor's gate has exactly that property in every state the machine can reach. Part 5 has the details and the first results.

Everything else people propose, the classifiers, the watchers, the second AI that judges the first, the sandboxes, lives in the middle of the graph. The middle is where there is no cut. That is why I keep saying those things are witnesses. They can yell STOP. They cannot be the lock. The lock is at the ends, where one guard covers one door.

## What this does not do

Two things, and I would rather say them than have you find them.

A gate only covers the doors you put it on. A device nobody wired through a gate is not in the cut. That is the coverage problem, and it is the real work: getting the gate into the payment switch, the release line, the motor driver. It is also why the device end is the one you can actually finish, and why the design asks nothing of NVIDIA that would stop a server maker from shipping the module tomorrow.

And a person is a door no chip gates. A model that talks a human into wiring the money has walked around every cut on every drawing in this post. The log will show that no ticket was ever issued for it, and the watchers can flag the attempt. That is all the hardware can do, and I am not going to pretend otherwise.

## The sentence

Next time someone says kill switch, here is the sentence. There is no button, because the capability is in a thousand places and the network between them and the world has no middle to cut. The only places a cut is small and complete are the chip that runs the model and the device that does the deed. We can build gates there. We are building them. Everything else is a classifier with a press release.

## Sources

Everything claimed above is public. The addresses are written out so they survive a copy and paste.

- The argument with the mathematics spelled out, and the part of the popular kill-switch argument that is wrong, is docs/23-there-is-no-kill-switch.md in the chip's repository, https://github.com/YobieBenjamin/safety-governor (the safety-governor repository). The graph model and the minimum cuts, computed by max-flow and cross-checked by brute force, are proofs/no_global_kill_switch.py in the same repository; `make proof` runs it with the other two proofs.
- Menger's theorem: Karl Menger, *Zur allgemeinen Kurventheorie*, Fundamenta Mathematicae 10, 1927. The max-flow min-cut theorem that turns it into arithmetic: L. R. Ford and D. R. Fulkerson, *Maximal Flow Through a Network*, Canadian Journal of Mathematics, 1956, and, independently, Elias, Feinstein and Shannon the same year.
- The network with no middle: Paul Baran, *On Distributed Communications*, RAND Corporation, 1964.
- The reference monitor: James P. Anderson, *Computer Security Technology Planning Study*, 1972.
- The gate, the ticket and the proofs: Parts 1 to 5 of this series, in https://github.com/YobieBenjamin/hardware-and-silicon (the hardware-and-silicon repository), blog/README.md; the route through the whole program for anyone who wants to check it is https://github.com/YobieBenjamin/safety-governor/blob/main/START-HERE.md in the chip's repository.
- Country-level shutdowns are documented year by year by Access Now's #KeepItOn project; North Korea's national intranet is Kwangmyong.

## Run it yourself

```
git clone https://github.com/YobieBenjamin/safety-governor
cd safety-governor && make proof      # the two Z3 proofs and the kill-switch cuts, under five seconds
```

If anyone wants in on any phase of this, I am here: yobie AT ieee DOT org.
