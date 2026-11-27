# ex2-iris-knn-cs — scripted replay

Economy `PORTABLE`, 4 rounds. Trunk 0.933333 -> 1.000000.

| round | opener | strategies A/B | payoff A/B | banks A/B | landed A/B | void | verdict |
|---|---|---|---|---|---|---|---|
| 1 | A | k/k | 7.142895/7.142895 | 11.142895/11.142895 | yes/no | — | A landed |
| 2 | B | vote/k | 0.000000/0.000000 | 7.142895/11.142895 | no/no | — | B kept nothing |
| 3 | A | distance/vote | 0.000000/0.000000 | 7.142895/11.142895 | no/no | — | A kept nothing |
| 4 | B | k/distance | 0.000000/0.000000 | 7.142895/11.142895 | no/no | — | B kept nothing |

Equilibrium reached: **False** (threshold 2.5, unexplored cells: A=1, B=0).

A void row pays nobody and is skipped by the equilibrium;
seat directories are scratch and never vendored.
