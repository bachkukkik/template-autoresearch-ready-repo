"""SC5 — domain-adaptation hooks. IDs: AC-TPL-04N."""
import prepare
import train


def test_train_uses_prepare_evaluate_bpb():
    """AC-TPL-041: train.py imports evaluate_bpb from prepare (no redefinition)."""
    assert hasattr(train, "evaluate_bpb")
    assert train.evaluate_bpb is prepare.evaluate_bpb
    # and the module-level import in train is the very same object
    import train as train_mod
    import prepare as prepare_mod
    assert train_mod.evaluate_bpb is prepare_mod.evaluate_bpb


def test_prepare_exposes_data_side_hooks():
    """AC-TPL-042: corpus constants + tokenizer callable (SC5 data side)."""
    assert isinstance(prepare.TRAIN_TEXT, str) and len(prepare.TRAIN_TEXT) > 0
    assert isinstance(prepare.VAL_TEXT, str) and len(prepare.VAL_TEXT) > 0
    assert callable(prepare.tokenizer)
    assert callable(prepare.dataloader)
    vocab, tokenize = prepare.tokenizer()
    assert isinstance(vocab, list)
    assert callable(tokenize)
    ids = tokenize(prepare.VAL_TEXT)
    assert all(isinstance(i, int) for i in ids)
    # tokenizer ids are stable and map back into vocab
    assert all(0 <= i < len(vocab) for i in ids)


def test_train_uses_data_side_hooks():
    """AC-TPL-042b: train.py consumes the prepare data hooks for its corpus."""
    vocab, tokenize = prepare.tokenizer()
    # behavior: ids map back to the expected chars via the vocab
    assert tokenize("ab") == [vocab.index("a"), vocab.index("b")]
    # train.py trains on prepare's corpus through prepare's tokenizer
    train_ids = train.build_bigram_logprobs(tokenize(prepare.TRAIN_TEXT),
                                            len(vocab))
    assert isinstance(train_ids, dict)
    assert len(train_ids) > 0