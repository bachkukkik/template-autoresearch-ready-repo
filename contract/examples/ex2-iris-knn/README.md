# Example 2 — iris-knn: Fisher's Iris classifier (accuracy, higher is better)

Template instantiation of the karpathy/autoresearch contract
(`program.md` human policy / `prepare.py` frozen evaluator / `train.py` the one
agent-edited file / `results.tsv` append-only keep-discard ledger) on a
classical supervised-learning problem. Same contract as
[`../ex1-music-abc`](../ex1-music-abc), **direction inverted**: ex1 minimizes
`val_bpb`, this example maximizes accuracy. The loop's comparison, ledger and
keep/reset rule are exercised against `>` instead of `<`.


## Git history (verbatim from the worked run)

```
b756d33 candidate: k=7 kNN
34ed15a candidate: k=3 kNN
8297ae9 ex2-iris-knn: contract (frozen prepare.py + baseline train.py 1-NN raw euclidean)
```
