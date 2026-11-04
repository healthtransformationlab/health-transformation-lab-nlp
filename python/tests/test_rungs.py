"""#559: rung names carry their variant suffixes (+cw, +s<seed>)."""


def test_parse_variant_reads_the_class_weight_and_seed_suffixes():
    # #559: the Kaggle encoder notebook runs the seed variants too
    from health_transformation_lab_nlp.rungs import output_tag, parse_variant
    assert parse_variant("modernbert-base") == ("modernbert-base", None, 42)
    assert parse_variant("modernbert-base+cw") == ("modernbert-base", "sqrt", 42)
    assert parse_variant("modernbert-base+cw+s2") == ("modernbert-base", "sqrt", 2)
    assert parse_variant("bert-base+s7") == ("bert-base", None, 7)
    for name in ("bert-base", "bert-base+cw", "modernbert-base+cw+s1"):
        base, cw, seed = parse_variant(name)
        assert base + output_tag(class_weight=cw, seed=seed) == name
