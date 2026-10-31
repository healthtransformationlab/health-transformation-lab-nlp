"""Profile tables for the data-dictionary ERD (dictionary_erd.py, #379): per table its row count, per column its
nulls, distinct values and, when there are few, every value's count (else the three most common);
for dates, the first and last year. One fact per line, as the dictionary shows them.
Counts are of the data given, synthetic in this repo. Nothing row-level is kept, only the counts."""
import pandas as pd

TOP = 8      # list every value's count when a column has at most this many distinct values


def _pct(n, total):
    return f"{round(100 * n / total) if total else 0}%"


def column_profile(s: pd.Series) -> str:
    total, nulls = len(s), int(s.isna().sum())
    present = s.dropna()
    distinct = int(present.nunique())
    out = [f"null={nulls:,} ({_pct(nulls, total)})", f"n_distinct={distinct:,}"]
    if pd.api.types.is_datetime64_any_dtype(s):
        if len(present):
            out += [f"first={present.min().year}", f"last={present.max().year}"]
    elif distinct <= TOP:
        counts = present.value_counts().sort_index()
        out += [f"{_fmt(v)}={n:,} ({_pct(n, total)})" for v, n in counts.items()]
    else:
        counts = present.value_counts()
        if len(counts) and counts.iloc[0] > 1:            # a value that repeats: show the three most common
            top = sorted(counts.items(), key=lambda vn: (-vn[1], vn[0]))[:3]
            return ";\n".join(out) + ";\ntop results:\n" + ";\n".join(
                f"  {_fmt(v)}={n:,} ({_pct(n, total)})" for v, n in top)
    return ";\n".join(out)


def _fmt(v):
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)


def profile(frames: dict) -> dict:
    """{table: DataFrame} -> {table: {'rows': n, 'columns': {column: profile line}}}"""
    return {name: {"rows": len(df), "columns": {c: column_profile(df[c]) for c in df.columns}}
            for name, df in frames.items()}
