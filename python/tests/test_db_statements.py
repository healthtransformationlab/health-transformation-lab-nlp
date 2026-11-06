"""#624: db._statements splits SQL into statements on `;` only outside quotes and comments."""

from health_transformation_lab_nlp.db import _statements


def test_a_comment_holding_dashes_and_a_semicolon_stays_one_statement():
    # the bug class that broke a CREATE TABLE ... COMMENT '...' elsewhere: the comment text held -- and ;
    sql = ("CREATE TABLE @cdmDatabaseSchema.t (a int);\n"
           "COMMENT ON TABLE @cdmDatabaseSchema.t IS 'one row per visit -- the grain; never per tooth';\n")
    assert _statements(sql, "cdm") == [
        "CREATE TABLE cdm.t (a int)",
        "COMMENT ON TABLE cdm.t IS 'one row per visit -- the grain; never per tooth'",
    ]


def test_a_line_inside_a_multiline_literal_that_starts_with_dashes_is_kept():
    sql = "COMMENT ON TABLE t IS 'first line\n-- second line, not a comment';"
    assert _statements(sql, "cdm") == ["COMMENT ON TABLE t IS 'first line\n-- second line, not a comment'"]


def test_escaped_quotes_and_quoted_identifiers():
    sql = """INSERT INTO t VALUES ('it''s; fine');\nSELECT "odd;name" FROM t;"""
    assert _statements(sql, "cdm") == ["INSERT INTO t VALUES ('it''s; fine')", 'SELECT "odd;name" FROM t']


def test_comments_outside_quotes_are_dropped_even_with_a_semicolon():
    sql = ("-- header; not a statement\n"
           "CREATE TABLE t (\n  a int, -- trailing note; still one statement\n  b int\n);\n"
           "/* block; comment */ DROP TABLE u;")
    assert _statements(sql, "cdm") == ["CREATE TABLE t (\n  a int, \n  b int\n)", "DROP TABLE u"]


def test_blank_statements_are_left_out():
    assert _statements(";\n;  ;\n-- only a comment\n", "cdm") == []
