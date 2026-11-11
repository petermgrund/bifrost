from bifrost.core import ids


def test_taken_ids_unions_every_source_normalized():
    taken = ids.taken_ids({"LIVE22"}, [" ppr222 ", None, ""], {"WDRN22": {"withdrawn": "t"}})
    assert taken == {"LIVE22", "PPR222", "WDRN22"}


def test_generator_never_reissues_a_taken_id(script_ids):
    script_ids("LIVE22", "WDRN22", "FRESH2")
    assert ids.generate_gramps_id(ids.taken_ids({"LIVE22"}, {"WDRN22"})) == "FRESH2"


def test_generator_skips_guarded_candidates(script_ids):
    script_ids("234567", "README", "FRESH2")
    assert ids.generate_gramps_id(set()) == "FRESH2"


def test_next_sequential_id():
    assert ids.next_sequential_id("C", {"C0001", "C0036", "C0068"}) == "C0069"
    assert ids.next_sequential_id("N", {"N0134", "N_XNH8SH", "N_RX4ZRR"}) == "N0135"
    assert ids.next_sequential_id("R", set()) == "R0001"
    assert ids.next_sequential_id("C", {"C9999"}) == "C10000"
