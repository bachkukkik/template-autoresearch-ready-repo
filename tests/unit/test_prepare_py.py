"""SC2 — prepare.py is the immutable anti-cheat evaluator. IDs: AC-TPL-01N."""
import hashlib
import math
import os

import prepare

# Byte pin on the frozen evaluator (AC-TPL-014). This is the CI gate that makes
# "nobody edits prepare.py" real: an intentional evaluator change MUST update
# this constant in the same commit, so a silent edit cannot ride along with a
# candidate change. Recompute with:
#   python3 -c "import hashlib;print(hashlib.sha256(open('contract/prepare.py','rb').read()).hexdigest())"
PREPARE_PY_SHA256 = "744993ebfea0afcfbcdeaae8802d7a9a3af36eca23c17159d91004ed14728ff2"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def test_prepare_time_budget():
    """AC-TPL-011: fixed time budget is 300 seconds."""
    assert prepare.TIME_BUDGET == 300


def test_prepare_py_is_byte_pinned():
    """AC-TPL-014: prepare.py's sha256 equals the pin — an edit must move it.

    The pin is the enforcement half of SC2: prepare.py's immutability is stated
    here and checked by CI, not left to convention.
    """
    path = os.path.join(REPO_ROOT, "contract", "prepare.py")
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    assert digest == PREPARE_PY_SHA256, (
        "contract/prepare.py changed but the AC-TPL-014 pin did not — if the "
        "evaluator change is intentional, update PREPARE_PY_SHA256 in the same "
        "commit; otherwise revert prepare.py (it is frozen; see program.md)."
    )


def test_prepare_data_hooks_exist():
    """AC-TPL-012: tokenizer + dataloader + data side are exposed."""
    assert callable(prepare.tokenizer)
    assert callable(prepare.dataloader)
    assert isinstance(prepare.TRAIN_TEXT, str) and prepare.TRAIN_TEXT
    assert isinstance(prepare.VAL_TEXT, str) and prepare.VAL_TEXT
    vocab, tokenize = prepare.tokenizer()
    assert isinstance(vocab, list) and len(vocab) > 1
    assert callable(tokenize)
    ids = tokenize(prepare.VAL_TEXT)
    assert isinstance(ids, list) and len(ids) > 1
    assert all(isinstance(i, int) for i in ids)
    # dataloader yields real (x, y) batches
    batches = list(prepare.dataloader(prepare.VAL_TEXT, batch_size=4,
                                      seq_len=8))
    assert batches and all(len(b) <= 4 for b in batches)
    for x, y in batches[0]:
        assert len(x) == len(y) == 8


def test_evaluate_bpb_callable_and_hand_built():
    """AC-TPL-013: evaluate_bpb is callable, returns float, handles a tiny case."""
    assert callable(prepare.evaluate_bpb)
    V, N = 3, 2
    logits = [[0.0] * V for _ in range(N)]  # uniform over vocab
    targets = [0, 1]
    token_bytes = {0: 1, 1: 2}  # 3 bytes total
    bpb = prepare.evaluate_bpb(logits, targets, token_bytes,
                               mask_ids=frozenset())
    assert isinstance(bpb, float)
    expected = N * math.log(V) / (math.log(2.0) * 3)
    assert math.isclose(bpb, expected, rel_tol=1e-12)


def test_evaluate_bpb_masks_special_tokens():
    """AC-TPL-013b: special tokens are excluded from numerator and denominator."""
    V = 2
    logits = [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
    targets = [0, 1, 1]  # id 0 (<pad>) is special and masked by default
    token_bytes = {0: 10, 1: 1}  # 10 bytes but masked -> not counted
    bpb = prepare.evaluate_bpb(logits, targets, token_bytes)  # default mask
    expected = 2 * math.log(2.0) / (math.log(2.0) * 2)  # 2 tokens, 2 bytes
    assert math.isclose(bpb, expected, rel_tol=1e-12)