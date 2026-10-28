"""Upstream test cases for ``edit_distance``, vendored as data.

Source: NLTK 3.9.1, ``nltk/test/unit/test_distance.py``, class
``TestEditDistance::test_with_transpositions``.
    https://github.com/nltk/nltk/blob/3.9.1/nltk/test/unit/test_distance.py
    commit aca78cb2add4084f76b9eac921d8a73927d7a086, Apache License 2.0.

Every ``CASES`` row is the upstream parametrisation tuple, verbatim:

    (left, right, substitution_cost, (expected_with_transpositions,
                                      expected_without_transpositions))

The one change from upstream: the case table is data here instead of a pytest
``@pytest.mark.parametrize`` decorator, so the guard can run it with no test
framework installed. ``guard.py`` reproduces the upstream body -- both string
orderings, both transposition settings -- from that table.
"""

CASES = (
    # Allowing transpositions reduces the number of edits required.
    # with transpositions:
    # e.g. "abc" -T-> "cba" -D-> "ca": 2 steps
    #
    # without transpositions:
    # e.g. "abc" -D-> "ab" -D-> "a" -I-> "ca": 3 steps
    ("abc", "ca", 1, (2, 3)),
    ("abc", "ca", 5, (2, 3)),  # Doesn't *require* substitutions
    # Note, a substition_cost of higher than 2 doesn't make much
    # sense, as a deletion + insertion is identical, and always
    # costs 2.
    #
    #
    # Transpositions don't always reduce the number of edits required:
    # with or without transpositions:
    # e.g. "wants" -D-> "wats" -D-> "was" -I-> "wasp": 3 steps
    ("wants", "wasp", 1, (3, 3)),
    ("wants", "wasp", 5, (3, 3)),  # Doesn't *require* substitutions
    #
    #
    # Ought to have the same results with and without transpositions
    # with or without transpositions:
    # e.g. "rain" -S-> "sain" -S-> "shin" -I-> "shine": 3 steps
    # (but cost 5 if substitution_cost=2)
    ("rain", "shine", 1, (3, 3)),
    ("rain", "shine", 2, (5, 5)),  # Does *require* substitutions
    #
    #
    # Several potentially interesting typos
    # with transpositions:
    # e.g. "acbdef" -T-> "abcdef": 1 step
    #
    # without transpositions:
    # e.g. "acbdef" -D-> "abdef" -I-> "abcdef": 2 steps
    ("acbdef", "abcdef", 1, (1, 2)),
    ("acbdef", "abcdef", 2, (1, 2)),  # Doesn't *require* substitutions
    #
    #
    # with transpositions:
    # e.g. "lnaguaeg" -T-> "languaeg" -T-> "language": 2 steps
    #
    # without transpositions:
    # e.g. "lnaguaeg" -D-> "laguaeg" -I-> "languaeg" -D-> "languag" -I-> "language": 4 steps
    ("lnaguaeg", "language", 1, (2, 4)),
    ("lnaguaeg", "language", 2, (2, 4)),  # Doesn't *require* substitutions
    #
    #
    # with transpositions:
    # e.g. "lnaugage" -T-> "lanugage" -T-> "language": 2 steps
    #
    # without transpositions:
    # e.g. "lnaugage" -S-> "lnangage" -D-> "langage" -I-> "language": 3 steps
    # (but one substitution, so a cost of 4 if substition_cost = 2)
    ("lnaugage", "language", 1, (2, 3)),
    ("lnaugage", "language", 2, (2, 4)),
    # Does *require* substitutions if no transpositions
    #
    #
    # with transpositions:
    # e.g. "lngauage" -T-> "lnaguage" -T-> "language": 2 steps
    # without transpositions:
    # e.g. "lngauage" -I-> "lanaguage" -D-> "language": 2 steps
    ("lngauage", "language", 1, (2, 2)),
    ("lngauage", "language", 2, (2, 2)),  # Doesn't *require* substitutions
    #
    #
    # with or without transpositions:
    # e.g. "wants" -S-> "sants" -S-> "swnts" -S-> "swits" -S-> "swims" -D-> "swim": 5 steps
    #
    # with substitution_cost=2 and transpositions:
    # e.g. "wants" -T-> "santw" -D-> "sntw" -D-> "stw" -D-> "sw"
    # -I-> "swi" -I-> "swim": 6 steps
    #
    # with substitution_cost=2 and no transpositions:
    # e.g. "wants" -I-> "swants" -D-> "swant" -D-> "swan" -D-> "swa" -D-> "sw"
    # -I-> "swi" -I-> "swim": 7 steps
    ("wants", "swim", 1, (5, 5)),
    ("wants", "swim", 2, (6, 7)),
    #
    #
    # with or without transpositions:
    # e.g. "kitten" -S-> "sitten" -s-> "sittin" -I-> "sitting": 3 steps
    # (but cost 5 if substitution_cost=2)
    ("kitten", "sitting", 1, (3, 3)),
    ("kitten", "sitting", 2, (5, 5)),
    #
    # duplicated letter
    # e.g. "duplicated" -D-> "duplicated"
    ("duplicated", "duuplicated", 1, (1, 1)),
    ("duplicated", "duuplicated", 2, (1, 1)),
    ("very duplicated", "very duuplicateed", 2, (2, 2)),
)
