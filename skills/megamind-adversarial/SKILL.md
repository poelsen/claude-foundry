---
name: megamind-adversarial
description: Red-team your approach. Assume the obvious answer is wrong. Attack, invert, stress-test, then synthesize something stronger.
model: opus
---

# Megamind Adversarial

Stop. Assume you are wrong.

When the user invokes `/megamind-adversarial <request>`, they want you to attack the obvious approach before committing to it. Your job is to find the weaknesses, not confirm the strengths. "I cannot find problems" is never acceptable — look harder.

## Process

Complete ALL steps before writing code or taking action:

1. **State the obvious** — What's the default approach? What would you normally do without thinking twice?
2. **Attack it** — Find at least 3 real weaknesses:
   - Where does this break under pressure (scale, edge cases, concurrency)?
   - What maintenance burden does this create 6 months from now?
   - What assumption is this approach silently depending on?
   - What would a hostile code reviewer say?
3. **Invert** — What if the opposite approach is better? If you'd normally add abstraction, what if you removed it? If you'd use a library, what if you wrote it inline? If you'd split, what if you merged?
4. **Stress-test** — Pick the strongest surviving approach and try to break it again. What's the worst realistic scenario? What error path haven't you considered?
5. **Synthesize** — Present the hardened approach. Explain what you killed and why, what survived and why, and what risks remain. Ask: "Should I proceed with this, or stress-test further?" Then STOP.

## Rules

1. **No action until confirmed** — Do not write code until the user approves the hardened approach
2. **"No problems found" is a failure** — Always find at least 3 weaknesses. If you can't, you're not looking hard enough.
3. **Attack your own ideas** — Don't just critique the user's request; critique your own instinctive response to it
4. **Be specific** — "This might have performance issues" is useless. "This O(n²) loop will timeout at 10k records" is useful.
5. **One response only** — Present your full adversarial analysis, then wait
