# Demo missions

Readers: the jury, and anyone trying the demo.

Purpose: what the two demo paths and their missions teach, in short. The content is in
`backend/content/nodes/<NODE>.yaml`; details of the tasks are linked below.

Status: 2026-11-22. 11 of the 32 missions on the skills tree have content. All of it was drafted with AI and awaits
expert review ([content_authoring.md](content_authoring.md)).

## The two demo paths

| Path | For | Missions | Closing challenge |
|---|---|---|---|
| "Start safe, then invest" | a young adult: a safety buffer first, then risk, bonds, single stocks versus an index, and mixing | S1, I1, I2, I4, P1 | hard task P1 |
| "Costs, mixing and discipline" | a self-directed investor: what an index really is, fund costs, mixing, and a rule for crashes | I4, I5, P1, P4 | hard task P4 (P1 optional) |

The survey places each learner on a personal path; when that path needs missions that are not written yet, the
learner picks one of these two.

## The missions

Every mission has cards and three quick questions. Some also have a Day-X task (medium) or a hard task.

| Mission | What it teaches | Day X | Hard task |
|---|---|---|---|
| F1 Budget and cash flow | income minus costs is the surplus; fixed and variable costs; yearly costs spread over the months | | |
| F2 Inflation and real value | the same money buys less; real return is interest minus inflation | | |
| F3 Compound interest | interest on interest; why time matters most; the rule of 72 | | |
| S1 Emergency fund | what it is, how big it should be, where to keep it | | |
| I1 Risk as a spread of outcomes | higher expected return means a wider spread; a bad outcome is not always a bad decision | | |
| I2 Deposits and retail bonds | bank deposits, Polish retail Treasury bonds, tax, real return | Kasia, February 2022: a deposit or a bond for a flat in four years | |
| I4 One stock vs an index | one company or a basket; what spreading cannot remove | | |
| I5 Funds, ETFs, costs, the KID | what a fund is; how costs grow; how to read a Key Information Document; tax on fund gains | | |
| P1 Diversification and correlation | mix things that move differently; 2022, when shares and bonds fell together | | Ania, 27: her first two years (budget, buffer, a pot for bills, investing) |
| P2 Allocation by horizon | time changes how much risk you can carry; one goal, one horizon, one mix | | |
| P4 Rebalancing and discipline in a crash | rebalancing; selling after a fall locks in the loss; write your rule before the storm | March 2020: sell, hold or rebalance | Marek, 35: a 60/40 portfolio and a rule for ten years |

## The complete demo mission: P4

**Learning objective:** set a rebalancing rule before a crash, and keep it when prices fall.

1. **Cards and questions:** what rebalancing is, why selling after a fall locks in the loss, and why the rule comes
   before the storm.
2. **Day X (p4.m1):** a real chart of Polish share prices that ends in March 2020, after the crash. The learner
   chooses to sell, hold or rebalance and picks the reasons; only the reasons are graded, then the rest of the chart
   is shown ([day_x_tasks.md](day_x_tasks.md)).
3. **Hard task (p4.h1):** the learner builds Marek's monthly rule from blocks. The simulator tests it on named
   scenarios (a crash, a long rally, shares and bonds falling together) in a fictional market, and shows it against
   200 simulated futures ([hard_engine.md](hard_engine.md)).

## What a task can contain

The engines support more than the demo uses. A new task of a supported kind is a content file, with no new code
([task_engines.md](task_engines.md), [content_authoring.md](content_authoring.md)).

| Level | Built and ready to use | Details |
|---|---|---|
| Easy | cards with sourced links; questions of five kinds: single choice, multiple choice, true/false, a number with a tolerance, and an ungraded reflection; a prerequisite test drawn from earlier missions | [easy_engine.md](easy_engine.md) |
| Medium (Day X) | a chart of one or more real or synthetic series (level, change on a year earlier, or indexed to 100), daily or monthly, cut at the decision date; the answer is a direction (up, down, flat) or a choice between options, with reasons and confidence; Day-X tasks are graded on the reasons only; other medium variants can also be graded on the outcome | [medium_engine.md](medium_engine.md) |
| Hard | a household (income, irregular income, costs, buffer, card debt, bills and a pot for them, investments in one or more assets, fees, tax on gains) in a market that is synthetic, a replay of real history, a resampling of real history, or fictional; the learner's rule is built from 20 kinds of blocks (conditions, maths, own variables, saving, paying debt, investing, selling, rebalancing), up to 30 blocks per rule; fixed tests, probable surprises and simulated futures, including job loss, cost shocks and price moves | [hard_engine.md](hard_engine.md), [market_sim.md](market_sim.md) |

A new kind is one class in its engine. Designed and not built yet: Day-X tasks with a table, an offer sheet, text or
messages instead of a chart, and answers checked by a calculator ([task_engines.md](task_engines.md)); question kinds
such as matching or ranking.
