"""prepare.py — FROZEN evaluator for the music-abc example.

Owns: corpus, tokenizer, dataloader, evaluate_bpb (ground truth), TIME_BUDGET.
The agent NEVER edits this file (template contract: import evaluate_bpb,
never redefine it — enforced by an object-identity test).
"""
import math
import random

TIME_BUDGET = 60  # seconds, wall clock, per candidate run

# ---------------------------------------------------------------- corpus ----
# Deterministic, seeded procedural ABC notation generator. Labeled in README.md
# as an honest stand-in for a real ABC corpus (self-contained reproducibility).

_ABC_HEAD = "X:{n}\nT:Tune {n}\nM:4/4\nL:1/8\nK:{key}\n"
_KEYS = ["C", "G", "D", "A", "F"]
_NOTES = "CDEFGAB"

def _bar(rng):
    """One 4/4 bar: 8 eighth-slot tokens, '|' at the end."""
    toks = []
    for _ in range(8):
        r = rng.random()
        if r < 0.10:
            toks.append("z")
        else:
            toks.append(rng.choice(_NOTES) + ("" if r < 0.85 else "2"))
    return "|".join(toks) + "|"

def _tune(n, rng):
    lines = _ABC_HEAD.format(n=n, key=rng.choice(_KEYS))
    for _ in range(rng.randint(4, 8)):
        lines += _bar(rng) + "\n"
    return lines

def generate_corpus(n_tunes, seed):
    rng = random.Random(seed)
    return "".join(_tune(i, rng) for i in range(1, n_tunes + 1))

TRAIN_TEXT = generate_corpus(280, seed=1234)
VAL_TEXT = generate_corpus(20, seed=99999)   # disjoint seed = held-out

# ------------------------------------------------------------- tokenizer ----
_VOCAB = sorted(set(TRAIN_TEXT))
STOI = {ch: i for i, ch in enumerate(_VOCAB)}
ITOS = {i: ch for ch, i in STOI.items()}
VOCAB_SIZE = len(_VOCAB)

def tokenizer(text):
    """Character-level; unseen chars are dropped (val uses the same alphabet)."""
    return [STOI[c] for c in text if c in STOI]

def dataloader(ids):
    return ids

# ------------------------------------------------------------------ eval ----
def evaluate_bpb(val_ids, prob_fn):
    """Ground-truth metric: bits-per-byte of VAL_TEXT under the model.

    prob_fn(prev_id) -> list[float] of VOCAB_SIZE next-token probabilities.
    FROZEN: import this; never redefine it (contract).
    """
    total_bits = 0.0
    for i in range(1, len(val_ids)):
        probs = prob_fn(val_ids[i - 1])
        p = max(probs[val_ids[i]], 1e-12)
        total_bits += -math.log2(p)
    total_bytes = len(VAL_TEXT.encode("utf-8"))
    return total_bits / total_bytes

if __name__ == "__main__":
    print(f"TIME_BUDGET={TIME_BUDGET}s")
    print(f"train_chars={len(TRAIN_TEXT)} val_chars={len(VAL_TEXT)}")
    print(f"vocab={VOCAB_SIZE} val_tokens={len(tokenizer(VAL_TEXT))}")
