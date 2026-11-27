# ex1-music-abc-cs — scripted replay

Economy `PORTABLE`, 4 rounds. Trunk 3.765056 -> 2.178568.

| round | opener | strategies A/B | payoff A/B | banks A/B | landed A/B | void | verdict |
|---|---|---|---|---|---|---|---|
| 1 | A | context/smoothing | 42.137169/0.000717 | 46.137169/4.000717 | yes/no | — | A landed |
| 2 | B | context/context | 0.000000/0.000000 | 46.137169/2.000717 | no/no | — | B kept nothing |
| 3 | A | smoothing/smoothing | 0.000000/0.000000 | 46.137169/2.000717 | — | B not served | void: B not served |
| 4 | B | smoothing/smoothing | 0.000000/0.000000 | 46.137169/2.000717 | no/no | — | B kept nothing |

Equilibrium reached: **False** (threshold 2.5, unexplored cells: A=0, B=0).

A void row pays nobody and is skipped by the equilibrium;
seat directories are scratch and never vendored.
