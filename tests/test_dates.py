import pytest

from bifrost.core import dates
from bifrost.core.dates import EMPTY_DATE, SPAN_MAX, plain_date, range_date


def gdate(day, month, year, modifier=0, quality=0, **extra):
    return {**plain_date(day, month, year, modifier, quality), **extra}


def form(value, precision="exact", modifier="regular", quality="regular", **extra):
    return {"value": value, "precision": precision, "modifier": modifier, "quality": quality, **extra}


class TestParsing:
    @pytest.mark.parametrize("text,expected", [
        ("1923", ("1923-01-01", "year")),
        ("1923-6", ("1923-06-01", "month")),
        ("1923-06-15", ("1923-06-15", "exact")),
        (" 1923-06-15 ", ("1923-06-15", "exact")),
    ])
    def test_parse_date_value(self, text, expected):
        assert dates.parse_date_value(text) == expected

    @pytest.mark.parametrize("text", ["", "June 1923", "1923-13", "1923-02-30", "23", None])
    def test_unreadable_dates(self, text):
        assert dates.parse_date_value(text) is None

    @pytest.mark.parametrize("f,expected", [
        (form("1923-06-15"), "exact"),
        (form("1923-06-15", "month"), "month"),
        (form("1923-06-15", "year", "before"), "year"),
        (form("1923-06-15", "exact", "about"), "month"),
        (form("1923-06-15", "year", "about"), "year"),
        (form("1945-06-15", "exact", "decade"), "year"),
        (form("1945-06-15", "month", "span"), "year"),
        ({"value": "1923-06-15"}, "exact"),
    ])
    def test_effective_precision(self, f, expected):
        assert dates.effective_precision(f) == expected


class TestGrampsDate:
    def test_exact_month_and_year(self):
        assert dates.gramps_date(form("1923-06-15")) == gdate(15, 6, 1923)
        assert dates.gramps_date(form("1923-06-15", "month")) == gdate(0, 6, 1923)
        assert dates.gramps_date(form("1923-06-15", "year")) == gdate(0, 0, 1923)

    def test_modifiers_and_qualities(self):
        assert dates.gramps_date(form("1923-06-15", "year", "before")) == gdate(0, 0, 1923, modifier=1)
        assert dates.gramps_date(form("1923-06-15", modifier="after", quality="calculated")) == \
            gdate(15, 6, 1923, modifier=2, quality=2)
        assert dates.gramps_date({"value": "1923-06-15"}) == gdate(15, 6, 1923)

    def test_about_falls_back_to_the_month(self):
        assert dates.gramps_date(form("1923-06-15", "exact", "about", "estimated")) == \
            gdate(0, 6, 1923, modifier=3, quality=1)

    @pytest.mark.parametrize("extra,first,last", [
        ({"modifier": "decade"}, 1940, 1949),
        ({"modifier": "span", "minus": 10, "plus": 5}, 1935, 1950),
        ({"modifier": "span", "minus": 0, "plus": 0}, 1945, 1945),
        ({"modifier": "span"}, 1945, 1945),
    ])
    def test_decades_and_spans_become_ranges(self, extra, first, last):
        assert dates.gramps_date({"value": "1945-06-15", "precision": "exact", **extra}) == \
            {"_class": "Date", "dateval": [0, 0, first, False, 0, 0, last, False],
             "modifier": 4, "quality": 0, "text": ""}

    def test_year_range(self):
        assert dates.year_range("decade", 1945, None) == (1940, 1949)
        assert dates.year_range("span", 1945, (10, 5)) == (1935, 1950)
        assert dates.year_range("span", 1945, None) == (1945, 1945)


class TestFormatting:
    @pytest.mark.parametrize("d,text", [
        (gdate(15, 6, 1923), "1923-06-15"),
        (gdate(0, 6, 1923), "1923-06"),
        (gdate(0, 0, 1923), "1923"),
        (gdate(0, 0, 1923, modifier=1), "Before 1923"),
        (gdate(15, 6, 1923, modifier=2), "After 1923-06-15"),
        (gdate(0, 6, 1923, modifier=3, quality=1), "Est. About 1923-06"),
        (range_date(1940, 1949), "Between 1940 and 1949"),
        ({"dateval": [0, 6, 1940, False, 0, 0, 1949, False], "modifier": 4}, "Between 1940-06 and 1949"),
        ({"dateval": [0, 0, 1940, False, 0, 0, 1949, False], "modifier": 5, "quality": 2},
         "Calc. From 1940 to 1949"),
    ])
    def test_format_gramps_date(self, d, text):
        assert dates.format_gramps_date(d) == text

    @pytest.mark.parametrize("d", [None, {}, EMPTY_DATE, {"dateval": [1, 2]}, {"dateval": None}])
    def test_empty_dates_are_none(self, d):
        assert dates.format_gramps_date(d) == "(none)"

    def test_text_only_dates_show_their_text(self):
        assert dates.gramps_date_text({**EMPTY_DATE, "modifier": 6, "text": " the summer Ed left "}) == \
            "the summer Ed left"
        assert dates.gramps_date_text({**EMPTY_DATE, "text": "sometime"}) == "sometime"
        assert dates.gramps_date_text(gdate(15, 6, 1923, text="ignored")) == "1923-06-15"
        assert dates.gramps_date_text(EMPTY_DATE) == ""
        assert dates.gramps_date_text(None) == ""

    def test_date_display(self):
        assert dates.date_display(form("1923-06-15", "exact", "about", "estimated")) == "Est. About 1923-06"
        assert dates.date_display({"value": "1945-01-01", "modifier": "decade"}) == "Between 1940 and 1949"
        assert dates.date_display(None) == ""


class TestDatesEqual:
    def test_ignores_api_decoration(self):
        stored = {"_class": "Date", "dateval": [0, 7, 1955, False], "modifier": 3,
                  "quality": 0, "text": "", "sortval": 2422325, "calendar": 0}
        assert dates.dates_equal(stored, gdate(0, 7, 1955, modifier=3))
        assert dates.dates_equal(gdate(0, 7, 1955, text="a"), gdate(0, 7, 1955, text="b"))

    def test_missing_fields_count_as_regular(self):
        assert dates.dates_equal({"dateval": [0, 7, 1955, False]}, gdate(0, 7, 1955))

    def test_differs_on_the_fields_bifrost_writes(self):
        base = {"dateval": [0, 0, 1920, False], "modifier": 3, "quality": 1}
        assert not dates.dates_equal(base, {**base, "dateval": [0, 0, 1921, False]})
        assert not dates.dates_equal(base, {**base, "modifier": 0})
        assert not dates.dates_equal(base, {**base, "quality": 0})

    def test_none_against_a_date(self):
        assert not dates.dates_equal(None, {"dateval": [0, 0, 1920, False]})
        assert not dates.dates_equal({"dateval": [0, 0, 1920, False]}, None)
        assert dates.dates_equal(None, None)
        assert dates.dates_equal(None, {})


class TestDateFromGramps:
    @pytest.mark.parametrize("d,expected", [
        (gdate(15, 6, 1923), {"value": "1923-06-15", "precision": "exact", "modifier": "regular",
                              "quality": "regular", "display": "1923-06-15"}),
        (gdate(0, 6, 1923, modifier=3, quality=1), {"value": "1923-06-01", "precision": "month",
                                                    "modifier": "about", "quality": "estimated",
                                                    "display": "Est. About 1923-06"}),
        (gdate(0, 0, 1923, modifier=1), {"value": "1923-01-01", "precision": "year", "modifier": "before"}),
        (gdate(15, 6, 1923, modifier=2, quality=2), {"modifier": "after", "quality": "calculated"}),
        (range_date(1940, 1949, 2), {"value": "1940-01-01", "precision": "year", "modifier": "decade",
                                     "quality": "calculated", "display": "Calc. Between 1940 and 1949"}),
        (range_date(1935, 1950), {"value": "1935-01-01", "precision": "year", "modifier": "span",
                                  "minus": 0, "plus": 15, "display": "Between 1935 and 1950"}),
        (range_date(1945, 1945), {"modifier": "span", "minus": 0, "plus": 0}),
        (range_date(1941, 1950), {"modifier": "span", "minus": 0, "plus": 9}),
        (range_date(1000, 1000 + SPAN_MAX), {"modifier": "span", "plus": SPAN_MAX}),
    ])
    def test_round_trips_through_the_form(self, d, expected):
        f, readonly = dates.date_from_gramps(d)
        assert readonly is None
        assert {k: f[k] for k in expected} == expected
        assert dates.dates_equal(dates.gramps_date(f), d)

    def test_round_trip_ignores_api_decoration(self):
        f, readonly = dates.date_from_gramps(gdate(15, 6, 1923, sortval=2423571, calendar=0, newyear=0))
        assert readonly is None and f["value"] == "1923-06-15"

    @pytest.mark.parametrize("d,text", [
        ({**EMPTY_DATE, "modifier": 6, "text": "the summer Ed left"}, "the summer Ed left"),
        ({**EMPTY_DATE, "text": "sometime"}, "sometime"),
        (gdate(1, 3, 1750, dateval=[1, 3, 1750, True]), "1750-03-01"),
        (gdate(15, 6, 1923, calendar=1), "1923-06-15"),
        (gdate(15, 6, 1923, newyear=1), "1923-06-15"),
        (gdate(15, 6, 1923, modifier=3), "About 1923-06-15"),
        (gdate(0, 13, 1923), "1923-13"),
        (gdate(15, 6, 1923, quality=7), "1923-06-15"),
        ({"dateval": [0, 6, 1940, False, 0, 0, 1949, False], "modifier": 4, "quality": 0, "text": ""},
         "Between 1940-06 and 1949"),
        ({"dateval": [0, 0, 1940, False, 0, 0, 1949, True], "modifier": 4, "quality": 0, "text": ""},
         "Between 1940 and 1949"),
        ({"dateval": [0, 0, 1940, False, 0, 0, 1949, False], "modifier": 5, "quality": 0, "text": ""},
         "From 1940 to 1949"),
        (range_date(1950, 1940), "Between 1950 and 1940"),
        (range_date(1000, 1000 + SPAN_MAX + 1), f"Between 1000 and {1000 + SPAN_MAX + 1}"),
        ({"dateval": [0, 0, 1940, False], "modifier": 4, "quality": 0, "text": ""}, "1940"),
    ])
    def test_dates_the_form_cannot_hold_are_read_only(self, d, text):
        assert dates.date_from_gramps(d) == (None, text)

    def test_no_date(self):
        assert dates.date_from_gramps(None) == (None, None)
        assert dates.date_from_gramps({}) == (None, None)
        assert dates.date_from_gramps(EMPTY_DATE) == (None, None)
