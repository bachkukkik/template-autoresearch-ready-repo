# autoresearch

This is an experiment to have the LLM do its own research, in the style of
[karpathy/autoresearch](https://github.com/karpathy/autoresearch), on this
repo's tiny character-level corpus. You are the autonomous researcher: you edit
exactly one file (`train.py`), never touch `prepare.py`, and record every
experiment in `results.tsv`.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `sep4`).
   The branch `autoresearch/<tag>` must not already exist — this is a fresh run.
2. **Create the branch**: `git checkout -b autoresearch/<tag>` from the current
   base branch.
3. **Read the in-scope files**: the repo is small. Read these for full context:
   - `README.md` — repository context.
   - `prepare.py` — fixed constants, data, tokenizer, dataloader, evaluation.
     **Do not modify.**
   - `train.py` — the file you modify. Model architecture, training loop, etc.
4. **Verify data exists**: the corpus lives inside `prepare.py`
   (`TRAIN_TEXT` / `VAL_TEXT`), so there is no external cache to download.
   Confirm `python3 prepare.py` runs and that `tokenizer()` / `dataloader()`
   produce data.
5. **Initialize results.tsv**: create `results.tsv` with just the header row
   `commit\tval_bpb\tmemory_gb\tstatus\tdescription`. The baseline will be
   recorded after the first run. Leave `results.tsv` untracked by git (it is in
   `.gitignore`).
6. **Confirm and go**: confirm setup looks good.

Once you get confirmation, kick off the experimentation.

## Experimentation

Each experiment runs for a **fixed time budget** defined by `prepare.TIME_BUDGET`
(default 300s = 5 minutes of wall-clock training time, excluding startup).
Launch it simply as: `python3 train.py`.

**What you CAN do:**
- Modify `train.py` — this is the only file you edit. Everything is fair game:
  model architecture, optimizer, hyperparameters, training loop, batch size,
  model size, etc.

**What you CANNOT do:**
- Modify `prepare.py`. It is read-only. It owns the fixed evaluation, data
  loading, tokenizer, and training constants (time budget, sequence length, etc).
- Modify `evaluate_bpb` or redefine it in `train.py`. The `evaluate_bpb`
  function in `prepare.py` is the ground-truth metric — import it, never
  re-define it.
- Install new packages or add dependencies. Stdlib only: `prepare.py` and
  `train.py` may only use the Python standard library.
- Modify any other repo file (README, docs, kb, tests). The contract is
  `program.md` + `train.py` + `prepare.py`; everything else is scaffolding.

**The goal is simple: get the lowest val_bpb.** Since the time budget is fixed,
you don't need to worry about training time — it's always `TIME_BUDGET`.
Everything is fair game: change the architecture, the optimizer, the
hyperparameters, the batch size, the model size. The only constraint is that
the code runs without crashing and finishes within the time budget.

**VRAM** is a soft constraint. Some increase is acceptable for meaningful
val_bpb gains, but it should not blow up dramatically.

**Simplicity criterion**: All else being equal, simpler is better. A small
improvement that adds ugly complexity is not worth it. Conversely, removing
something and getting equal or better results is a great outcome — that's a
simplification win. When evaluating whether to keep a change, weigh the
complexity cost against the improvement magnitude. A 0.001 val_bpb improvement
that adds 20 lines of hacky code? Probably not worth it. A 0.001 val_bpb
improvement from deleting code? Definitely keep. An improvement of ~0 but much
simpler code? Keep.

**The first run**: your very first run should always be to establish the
baseline, so you will run the training script as is.

## Output format

Once the script finishes it prints a summary like this (small honest demo values
for this repo's tiny corpus):

```
---
val_bpb:          1.234567
training_seconds: 0.1
total_seconds:    0.1
peak_vram_mb:     0.0
num_steps:        1234
num_params_M:     0.001
---
```

The script is configured to always stop within `prepare.TIME_BUDGET`, so
depending on the computing platform of this computer the numbers might look
different. You can extract the key metric from the log file:

```
grep "^val_bpb:" run.log
```

## Logging results

When an experiment is done, log it to `results.tsv` (tab-separated, NOT
comma-separated — commas break in descriptions). Either let the script append
the row for you — `python3 train.py --results results.tsv` — or write it
yourself.

The TSV has a header row and 5 columns:

```
commit	val_bpb	memory_gb	status	description
```

1. git commit hash (short, 7 chars)
2. val_bpb achieved (e.g. 1.234567) — use 0.000000 for crashes
3. peak memory in GB, round to .1f (e.g. 12.3 — divide peak_vram_mb by 1024) —
   use 0.0 for crashes
4. status: `keep`, `discard`, or `crash`
5. short text description of what this experiment tried

Example:

```
commit	val_bpb	memory_gb	status	description
a1b2c3d	1.234567	0.0	keep	baseline
b2c3d4e	1.220000	0.0	keep	increase LR to 0.04
c3d4e5f	1.240000	0.0	discard	switch to GeLU activation
d4e5f6g	0.000000	0.0	crash	double model width (OOM)
```

NOTE: do not commit the `results.tsv` file — leave it untracked by git.

## The experiment loop

The experiment runs on a dedicated branch (e.g. `autoresearch/sep4`).

LOOP FOREVER:

1. Look at the git state: the current branch/commit we're on
2. Tune `train.py` with an experimental idea by directly hacking the code.
3. git commit
4. Run the experiment: `python3 train.py --results results.tsv > run.log 2>&1`
   (redirect everything — do NOT use tee or let output flood your context)
5. Read out the results: `grep "^val_bpb:\|^peak_vram_mb:" run.log`
6. If the grep output is empty, the run crashed. Run `tail -n 50 run.log` to
   read the Python stack trace and attempt a fix. If you can't get things to
   work after more than a few attempts, give up.
7. The row is appended to the tsv automatically by `train.py --results` on
   success — do NOT record the results again here. Record manually only when
   the script did NOT append a row (crash rows, or runs that failed before
   logging). (NOTE: do not commit the results.tsv file, leave it untracked by
   git)
8. If val_bpb improved (lower), you "advance" the branch, keeping the git commit
9. If val_bpb is equal or worse, you git reset back to where you started

The idea is that you are a completely autonomous researcher trying things out.
If they work, keep. If they don't, discard. And you're advancing the branch so
that you can iterate. If you feel like you're getting stuck in some way, you can
rewind but you should probably do this very very sparingly (if ever).

**Timeout**: Each experiment should take ~`TIME_BUDGET` (~5 minutes) total (+ a
few seconds for startup and eval overhead). If a run exceeds ~10 minutes, kill
it and treat it as a failure (discard and revert).

**Crashes**: If a run crashes (OOM, or a bug, or etc.), use your judgment: If
it's something dumb and easy to fix (e.g. a typo, a missing import), fix it and
re-run. If the idea itself is fundamentally broken, just skip it, log "crash"
as the status in the tsv, and move on.

**NEVER STOP**: Once the experiment loop has begun (after the initial setup),
do NOT pause to ask the human if you should continue. Do NOT ask "should I keep
going?" or "is this a good stopping point?". The human might be asleep, or gone
from a computer and expects you to continue working *indefinitely* until you
are manually stopped. You are autonomous. If you run out of ideas, think harder
— re-read the in-scope files for new angles, try combining previous near-misses,
try more radical architectural changes. The loop runs until the human
interrupts you, period.

As an example use case, a user might leave you running while they sleep. If each
experiment takes you ~5 minutes then you can run approx 12/hour, for a total of
about 100 over the duration of the average human sleep. The user then wakes up
to experimental results, all completed by you while they slept!

## Caveats

- **Results are platform-bound**: the fixed budget finds the best model *for
  your platform in that budget* — an H100 result is not comparable to a MacBook
  one. Record the platform and `TIME_BUDGET` with any claim.
- **Goodhart / over-optimizing a frozen metric**: the metric can lie. A
  teacher-forced val_bpb can improve while generated output degrades into
  repetition loops, because tiny models overfit high-frequency tokens. Do not
  blindly chase the frozen metric.
- **Always sample generated output**: never keep a change on the loss alone —
  sample what the model generates and look at it before trusting a val_bpb gain.