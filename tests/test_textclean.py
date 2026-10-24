from tickerquill.textclean import clean_repeats, collapse_runs


def test_repeated_words_are_collapsed_to_two():
    assert collapse_runs("iya iya iya iya iya baik") == "iya iya baik"


def test_repeated_phrases_are_collapsed():
    assert collapse_runs("ya kan, ya kan, ya kan, ya kan.") == "ya kan ya kan."  # the trailing period after the run is kept


def test_short_repeats_are_kept():
    assert collapse_runs("iya iya iya") == "iya iya iya"


def test_identical_consecutive_lines_are_dropped_and_timestamps_kept():
    text = "[00:00:01] halo\n[00:00:02] halo\n[00:00:03] dunia\n\n[00:00:04] iya iya iya iya iya"
    assert clean_repeats(text).splitlines() == ["[00:00:01] halo", "[00:00:03] dunia", "[00:00:04] iya iya"]
