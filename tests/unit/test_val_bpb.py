"""SC4 — val_bpb is the KB metric: nats / (ln2 * bytes). IDs: AC-TPL-031."""
import math

from prepare import evaluate_bpb


def _uniform_case(vocab_size, n_tokens, byte_lengths, mask_ids=frozenset()):
    """Uniform logits over vocab -> each token contributes ln(V) nats."""
    logits = [[0.0] * vocab_size for _ in range(n_tokens)]
    targets = list(range(n_tokens))  # ids inside the vocab, none special
    token_bytes = {t: b for t, b in zip(targets, byte_lengths)}
    return logits, targets, token_bytes, mask_ids


def test_uniform_logits_hand_computed():
    """AC-TPL-031: uniform logits over V with N tokens & B bytes:
    expected = N * ln(V) / (ln 2 * B)."""
    V, N, B = 4, 3, 3
    logits, targets, token_bytes, mask_ids = _uniform_case(
        V, N, [1, 1, 1])  # 3 bytes total
    bpb = evaluate_bpb(logits, targets, token_bytes, mask_ids=mask_ids)
    expected = N * math.log(V) / (math.log(2.0) * B)
    assert math.isclose(bpb, expected, rel_tol=1e-12)

    # same vocab, more tokens, different byte length -> still exact
    V2, N2, B2 = 8, 5, 15
    logits2, targets2, token_bytes2, _ = _uniform_case(
        V2, N2, [3] * N2)
    bpb2 = evaluate_bpb(logits2, targets2, token_bytes2, mask_ids=frozenset())
    expected2 = N2 * math.log(V2) / (math.log(2.0) * B2)
    assert math.isclose(bpb2, expected2, rel_tol=1e-12)

    # both vocab (4 -> 8) and bytes per token (1 -> 3) grow here, so the
    # lower bpb is not isolating byte length alone
    assert bpb2 < bpb


def test_perfect_prediction_is_zero():
    """AC-TPL-031b: p=1 at every position => zero nats => bpb == 0.0."""
    logits = [[0.0, -100.0], [-100.0, 0.0], [0.0, -100.0]]
    targets = [0, 1, 0]
    token_bytes = {0: 1, 1: 2}
    bpb = evaluate_bpb(logits, targets, token_bytes, mask_ids=frozenset())
    assert math.isclose(bpb, 0.0, abs_tol=1e-12)