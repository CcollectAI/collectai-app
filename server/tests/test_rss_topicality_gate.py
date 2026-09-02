"""RSS topicality gate — every case here is a real item from a live dry run.

Context: `RSS_EVENTS_ENABLED` has been off since 2026-06-15 because the feeds
polluted the events catalogue with non-collectible articles. The exit condition
written into `event_scraper_scheduler.py` is "once feeds are curated/filtered",
so these tests are that condition, made executable.

The gate they cover is `_is_collector_relevant`, which already existed — the
119 items measured on 2026-09-02 were its SURVIVORS. What changed is (a) four
zero-signal feeds were quarantined at source and (b) topic rules were added
that judge the HEADLINE only.
"""
import pytest

from pipelines.rss_events import _is_collector_relevant, RSS_FEED_TARGETS


# Description deliberately carries food words. SoraNews pages append
# related-article blurbs, and matching topic rules against title+description
# is what dropped the Tamagotchi drop below on the first attempt.
_FOOD_FURNITURE = "Related: Japan convenience store rice ball and Cup Noodle flavour roundup."


@pytest.mark.parametrize("title", [
    "Tamagotchi evolves into a ring for its 30th anniversary, preorders now open",
    "LEGO Ideas 21371 Wallace & Gromit revealed!",
    "Collector preview: Iron Studios opens pre-orders for 30 cm D&D Beholder",
    "New Release: Tudor North Flag Returns As A GMT Watch",
    "Tabletop Scotland 2026 demo floor and playtest schedule revealed",
])
def test_real_collectible_items_survive(title):
    assert _is_collector_relevant(title, "") is True


def test_page_furniture_cannot_veto_a_good_headline():
    """The regression that caught this: topic rules must read the title only."""
    title = "Tamagotchi evolves into a ring for its 30th anniversary, preorders now open"
    assert _is_collector_relevant(title, _FOOD_FURNITURE) is True


@pytest.mark.parametrize("title", [
    # Food & drink — each matches a positive signal (`release`, `announce`)
    "Family Mart releases new Human Made Cup Noodle in Japan",
    "Finally! Japan's big three convenience store chains announce rice ball price reductions",
    "Ghost Face Vodka adds Blood Orange flavour alongside national retail expansion",
    "Disney Eats: First Look at The Diamond Horseshoe Pop-Up Menu",
    # Recurring digests — a weekly roundup is not an event
    "This week's top news articles",
    "What's hot this week",
    "Routinely Itemised: RPG #376",
    # Listicle / retrospective
    "It's Time to Go Back to Hogwarts! Here's Every Return Ranked",
    "The History of Sideshow: Bernie Wrightson's Frankenstein",
])
def test_real_noise_items_are_rejected(title):
    assert _is_collector_relevant(title, "") is False


@pytest.mark.parametrize("dead_feed", [
    "kotaku.com",
    "animenewsnetwork.com",
    "myanimelist.net",
    "japantimes.co.jp",
])
def test_zero_signal_feeds_stay_quarantined(dead_feed):
    """These four produced 33 items and zero collectible events in a real run.

    They are excluded at the FEED level because no title rule can separate
    them: anime industry news uses a product release's exact vocabulary
    ("Main Staff ... Announced" vs "LEGO Ideas ... revealed").
    """
    urls = " ".join(t["feed_url"] for t in RSS_FEED_TARGETS)
    assert dead_feed not in urls
