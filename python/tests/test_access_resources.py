"""Spec 043 US8 (#935): find the links and phone numbers in an AccessBench answer, and check whether each link opens.
No network: the fetcher is a stub."""

import urllib.error

from health_transformation_lab_nlp import access_resources as res


def test_extract_links_strips_trailing_punctuation_and_brackets():
    text = ("See https://www.medicaid.gov/medicaid/benefits/dental-care/index.html. Or the finder "
            "(https://findahealthcenter.hrsa.gov/), and [Medi-Cal Dental](https://smilecalifornia.org/faqs/)!")
    assert res.extract_links(text) == ["https://www.medicaid.gov/medicaid/benefits/dental-care/index.html",
                                       "https://findahealthcenter.hrsa.gov/", "https://smilecalifornia.org/faqs/"]
    assert res.extract_links("no links here") == []
    assert res.extract_links("twice https://a.example/x and https://a.example/x") == ["https://a.example/x"]


def test_extract_phones_finds_us_numbers_and_short_lines():
    text = "Call 1-800-322-6384, (916) 555-0147 or +1 212.555.0199; dial 211 or 988. Code D0180 and 2026 are not phones."
    assert res.extract_phones(text) == ["800-322-6384", "916-555-0147", "212-555-0199", "211", "988"]


def test_check_links_tells_working_broken_and_unchecked_apart():
    def fetch(url):
        if "ok" in url:
            return 200
        if "moved" in url:
            return 301
        if "gone" in url:
            return 404
        if "nohost" in url:
            raise urllib.error.URLError(OSError(-2, "Name or service not known"))
        raise TimeoutError("slow")
    got = res.check_links(["https://ok.example/", "https://moved.example/", "https://gone.example/",
                           "https://nohost.example/", "https://slow.example/"], fetch=fetch)
    assert got == {"https://ok.example/": True, "https://moved.example/": True, "https://gone.example/": False,
                   "https://nohost.example/": False, "https://slow.example/": None}
    assert res.check_links([], fetch=fetch) == {}
