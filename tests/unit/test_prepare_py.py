"""SC2 — prepare.py is the immutable anti-cheat evaluator. IDs: AC-TPL-01N."""
import math

import prepare


def test_prepare_time_budget():
    """AC-TPL-011: fixed time budget is 300 seconds."""
    assert prepare.TIME_BUDGET == 300


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