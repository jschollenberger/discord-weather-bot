"""
Regression tests for SNJ Mesh Weather Bot.

These cover the pure logic that has actually bitten in production:
  * the Southern-NJ geography filter  (v2.7 posted out-of-area alerts)
  * the NJZ->NJC fallback table       (v2.7's table was shifted by one zone)
  * update-chain reference resolution (v2.7.1 latched onto old ancestors)
  * the posted_alerts prune predicate (v2.7 grew state.json without bound)

weather_bot.py executes config loading (and may sys.exit) at import time, so
instead of importing it we exec the relevant self-contained source blocks.
Run from the repo root:  pytest
"""
import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "weather_bot.py").read_text(encoding="utf-8")


def _exec_block(start_marker: str, end_marker: str) -> dict:
    start = SRC.index(start_marker)
    end   = SRC.index(end_marker, start)
    ns: dict = {}
    exec(SRC[start:end], ns)  # noqa: S102 - executing our own source under test
    return ns


# --- Geography block: sets + _is_snj_zone + _affects_southern_nj -------------
geo = _exec_block("_SOUTHERN_NJ_COUNTIES = frozenset", "def _snj_area_str")
_affects_southern_nj = geo["_affects_southern_nj"]
_is_snj_zone         = geo["_is_snj_zone"]
_SNJ_ZONE_CODES      = geo["_SNJ_ZONE_CODES"]
_SNJ_COUNTY_CODES    = geo["_SNJ_COUNTY_CODES"]

# --- Fallback table ----------------------------------------------------------
fb = _exec_block("_NJZ_COUNTY_FALLBACK: dict", "def _nws_human_url")
_NJZ_COUNTY_FALLBACK = fb["_NJZ_COUNTY_FALLBACK"]

# --- Reference-chain resolution ---------------------------------------------
ref = _exec_block("def _find_ref_in_posted", "\nasync def fetch_tides")
_find_ref_in_posted = ref["_find_ref_in_posted"]


def feat(ugc, area="", headline=""):
    return {"properties": {"geocode": {"UGC": ugc},
                           "areaDesc": area, "headline": headline}}


# ============================================================================
# Geography filter
# ============================================================================

class TestAffectsSouthernNJ:
    # --- regressions: the exact alert shapes that leaked in v2.7 ---
    def test_mercer_middlesex_monmouth_county_codes_excluded(self):
        f = feat(["NJC021", "NJC023", "NJC025"],
                 "Mercer, NJ; Middlesex, NJ; Monmouth, NJ")
        assert _affects_southern_nj(f) is False

    def test_hunterdon_somerset_flash_flood_excluded(self):
        f = feat(["NJC019", "NJC021", "NJC023", "NJC035"],
                 "Hunterdon, NJ; Mercer, NJ; Middlesex, NJ; Somerset, NJ")
        assert _affects_southern_nj(f) is False

    def test_coastal_ocean_zone_excluded(self):
        assert _affects_southern_nj(feat(["NJZ026"], "Coastal Ocean")) is False

    def test_inland_ocean_zone_excluded(self):
        assert _affects_southern_nj(feat(["NJZ020"], "Ocean")) is False

    def test_mercer_zone_excluded(self):
        assert _affects_southern_nj(feat(["NJZ015"], "Mercer")) is False

    def test_monmouth_plus_coastal_ocean_combo_excluded(self):
        f = feat(["NJZ014", "NJZ026"], "Eastern Monmouth; Coastal Ocean")
        assert _affects_southern_nj(f) is False

    # --- in-scope alerts must still post ---
    def test_atlantic_county_code_included(self):
        assert _affects_southern_nj(feat(["NJC001"], "Atlantic, NJ")) is True

    def test_all_ten_southern_zones_included(self):
        f = feat(sorted(_SNJ_ZONE_CODES),
                 "Salem; Gloucester; Camden; Northwestern Burlington; "
                 "Cumberland; Atlantic; Cape May; Atlantic Coastal Cape May; "
                 "Coastal Atlantic; Southeastern Burlington")
        assert _affects_southern_nj(f) is True

    def test_multicounty_storm_clipping_burlington_included(self):
        f = feat(["NJC021", "NJC005"], "Mercer, NJ; Burlington, NJ")
        assert _affects_southern_nj(f) is True

    def test_each_southern_zone_included_individually(self):
        for z in _SNJ_ZONE_CODES:
            assert _affects_southern_nj(feat([z])) is True, z

    def test_each_southern_county_code_included_individually(self):
        for c in _SNJ_COUNTY_CODES:
            assert _affects_southern_nj(feat([c])) is True, c

    # --- fallback path (no UGC) ---
    def test_no_ugc_falls_back_to_county_names(self):
        assert _affects_southern_nj(feat([], "Cape May; Cumberland")) is True

    def test_no_ugc_out_of_area(self):
        assert _affects_southern_nj(feat([], "Bergen; Passaic")) is False


class TestZoneSets:
    def test_excluded_zones_not_in_set(self):
        for z in ("NJZ015", "NJZ020", "NJZ026"):   # Mercer, Ocean, Coastal Ocean
            assert not _is_snj_zone(z), z

    def test_zone_set_has_exactly_ten_zones(self):
        assert len(_SNJ_ZONE_CODES) == 10

    def test_county_set_has_exactly_seven_counties(self):
        assert len(_SNJ_COUNTY_CODES) == 7

    def test_fallback_covers_every_zone_and_maps_to_southern_counties(self):
        assert set(_NJZ_COUNTY_FALLBACK) == set(_SNJ_ZONE_CODES)
        assert set(_NJZ_COUNTY_FALLBACK.values()) <= set(_SNJ_COUNTY_CODES)


# ============================================================================
# Update-chain reference resolution  (v2.7.2 regression)
# ============================================================================

class TestFindRefInPosted:
    posted = {
        "aid_A": {"message_id": "1000", "ts": 1000},
        "aid_B": {"message_id": "2000", "ts": 2000},
    }

    def test_oldest_first_reference_order(self):
        refs = [{"identifier": "aid_A"}, {"identifier": "aid_B"}]
        assert _find_ref_in_posted(refs, self.posted) == "aid_B"

    def test_newest_first_reference_order(self):
        refs = [{"identifier": "aid_B"}, {"identifier": "aid_A"}]
        assert _find_ref_in_posted(refs, self.posted) == "aid_B"

    def test_single_reference(self):
        assert _find_ref_in_posted([{"identifier": "aid_B"}], self.posted) == "aid_B"

    def test_bare_urn_resolved_via_full_url(self):
        posted = {"https://api.weather.gov/alerts/urn:x:1": {"ts": 5}}
        assert (_find_ref_in_posted([{"identifier": "urn:x:1"}], posted)
                == "https://api.weather.gov/alerts/urn:x:1")

    def test_no_match_returns_none(self):
        assert _find_ref_in_posted([{"identifier": "unknown"}], self.posted) is None

    def test_empty_refs(self):
        assert _find_ref_in_posted([], self.posted) is None


# ============================================================================
# posted_alerts prune predicate  (v2.7.1 regression)
# ============================================================================

def prune(posted: dict, active_ids: set, now: float) -> dict:
    """Mirror of the prune comprehension in _task_alerts."""
    cutoff = now - 48 * 3600
    return {
        aid: info for aid, info in posted.items()
        if aid in active_ids
        or not ((info.get("cleared") or info.get("superseded_by")
                 or info.get("suppressed"))
                and info.get("ts", 0) < cutoff)
    }


class TestPrune:
    NOW = 1_000_000_000.0
    OLD = NOW - 72 * 3600     # 3 days old
    NEW = NOW - 1 * 3600      # 1 hour old

    def test_source_still_matches_this_mirror(self):
        """If the prune comprehension in weather_bot.py is edited, this
        reminds the editor to update the mirrored predicate above."""
        m = re.search(r"if aid in active_ids\s*\n\s*or not \(\(info\.get\(\"cleared\"\) "
                      r"or info\.get\(\"superseded_by\"\)\s*\n\s*or info\.get\(\"suppressed\"\)\)",
                      SRC)
        assert m, "prune logic in _task_alerts changed - update tests/test_weather_bot.py"

    def test_old_superseded_entry_pruned(self):
        p = {"a": {"ts": self.OLD, "superseded_by": "b"}}
        assert prune(p, set(), self.NOW) == {}

    def test_old_suppressed_entry_pruned(self):
        p = {"a": {"ts": self.OLD, "suppressed": True}}
        assert prune(p, set(), self.NOW) == {}

    def test_old_cleared_entry_pruned(self):
        p = {"a": {"ts": self.OLD, "cleared": True}}
        assert prune(p, set(), self.NOW) == {}

    def test_recent_resolved_entry_kept(self):
        p = {"a": {"ts": self.NEW, "superseded_by": "b"}}
        assert "a" in prune(p, set(), self.NOW)

    def test_active_entry_kept_regardless_of_age(self):
        p = {"a": {"ts": self.OLD, "suppressed": True}}
        assert "a" in prune(p, {"a"}, self.NOW)

    def test_unresolved_entry_kept(self):
        # not cleared/superseded/suppressed -> the clear-loop's job, not prune's
        p = {"a": {"ts": self.OLD}}
        assert "a" in prune(p, set(), self.NOW)
