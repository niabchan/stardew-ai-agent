"""Only tests a deterministic toy proposal policy. No game, HTTP or Luna."""
from dataclasses import fields, replace

from reference.sunny_daytime_intents import FakeDaytimePlanner, FakeScene


def test_three_daytime_choices_without_fixed_clock_or_one_action_quota():
    planner = FakeDaytimePlanner()
    scene = FakeScene(weather="rainy", revision=1)
    first = planner.choose(scene, "WATCH_WEATHER_TV")
    assert (first.status, first.action) == ("SELECTED_FAKE", "WATCH_WEATHER_TV")
    # A fresh synthetic observation with explicit previous completion allows
    # another independently chosen activity on the same simulated farm day.
    second = planner.choose(replace(scene, revision=2, recently_completed=("WATCH_WEATHER_TV",)), "MOVE_TO_CHAIR")
    assert (second.status, second.action) == ("SELECTED_FAKE", "MOVE_TO_CHAIR")
    third = planner.choose(replace(scene, revision=3, p2_seated=True,
                                   recently_completed=("WATCH_WEATHER_TV", "MOVE_TO_CHAIR")), "STAY")
    assert (third.status, third.action) == ("SELECTED_FAKE", "STAY")


def test_repeated_snapshot_never_requests_new_choice_round():
    planner = FakeDaytimePlanner()
    scene = FakeScene()
    assert planner.choose(scene, "STAY").status == "SELECTED_FAKE"
    assert planner.choose(scene, "MOVE_TO_CHAIR").status == "WAIT_NEW_OBSERVATION"
    assert planner.choose(replace(scene, revision=0), "STAY").status == "WAIT_NEW_OBSERVATION"


def test_stay_is_always_eligible_and_not_forced_to_chatter():
    scene = FakeScene(p1_awake=False, social_cooldown=True, chair_reachable=False,
                      tv_reachable=False)
    result = FakeDaytimePlanner().choose(scene, "STAY")
    assert result.action == "STAY"
    assert [c.action for c in result.candidates] == ["STAY"]


def test_never_offer_speech_to_sleeping_far_or_cooldown_p1():
    for override in ({"p1_awake": False}, {"p1_distance_tiles": 6},
                     {"p1_distance_tiles": None}, {"social_cooldown": True}):
        candidates = FakeDaytimePlanner().propose(replace(FakeScene(), **override)).candidates
        assert "SPEAK_TO_P1" not in {c.action for c in candidates}


def test_do_not_retoggle_chair_after_seated_or_recently_completed():
    for override in ({"p2_seated": True}, {"chair_reachable": False},
                     {"recently_completed": ("MOVE_TO_CHAIR",)}):
        candidates = FakeDaytimePlanner().propose(replace(FakeScene(), **override)).candidates
        assert "MOVE_TO_CHAIR" not in {c.action for c in candidates}


def test_fancy_or_unoffered_action_never_smuggled_in():
    planner = FakeDaytimePlanner()
    scene = FakeScene(offered_actions=("STAY", "FIREPLACE_TOGGLE", "MARRY_NPC"))
    result = planner.choose(scene, "MARRY_NPC")
    assert result.status == "DENIED_NOT_GROUNDED"
    assert [c.action for c in result.candidates] == ["STAY"]
    assert "FIREPLACE_TOGGLE" not in {c.action for c in result.candidates}


def test_no_p1_raw_messages_or_diary_in_scene_contract():
    names = {f.name for f in fields(FakeScene)}
    assert not any(key in name for name in names for key in ("diary", "chat", "feed", "secret", "inventory"))


def test_wrong_owner_seat_epoch_and_unknown_result_block():
    scenarios = [
        (replace(FakeScene(), epoch="different-load"), "BLOCKED_EPOCH"),
        (replace(FakeScene(), owner="other-owner"), "BLOCKED_ROLE_OR_OWNER"),
        (replace(FakeScene(), p1_is_human=False), "BLOCKED_ROLE_OR_OWNER"),
        (replace(FakeScene(), p2_is_ai=False), "BLOCKED_ROLE_OR_OWNER"),
        (replace(FakeScene(), p2_ready=False), "BLOCKED_ROLE_OR_OWNER"),
        (replace(FakeScene(), unresolved_attempt=True), "BLOCKED_UNRESOLVED"),
    ]
    for scene, expected in scenarios:
        assert FakeDaytimePlanner().choose(scene, "STAY").status == expected


def test_never_guess_interest_not_in_offered_choices():
    result = FakeDaytimePlanner().choose(FakeScene(), "WATCH_FORTUNE_TV")
    assert result.status == "DENIED_NOT_GROUNDED"
    assert result.action is None


def test_no_stay_in_observation_blocks_candidates():
    result = FakeDaytimePlanner().choose(FakeScene(offered_actions=("MOVE_TO_CHAIR",)), "MOVE_TO_CHAIR")
    assert result.status == "BLOCKED_NO_STAY"


def test_malformed_scene_fields_fail_closed_without_consuming_revision():
    malformed = {
        'offered_actions': [None, 'STAY', ([],), ('STAY', 1), {'STAY': True}],
        'recently_completed': [None, 'MOVE_TO_CHAIR', ([],), (1,)],
        'revision': [None, True, False, -1, 1.5, '2'],
        'p1_distance_tiles': [True, False, -1, 2.5, '3', float('nan'), float('inf')],
        'epoch': [None, 1], 'owner': [None, 1],
    }
    for name in ('p1_is_human', 'p2_is_ai', 'p2_ready', 'chair_reachable',
                 'p2_seated', 'tv_reachable', 'p1_awake', 'social_cooldown',
                 'unresolved_attempt'):
        malformed[name] = [None, 0, 1, 'false', [], {}]
    for name, values in malformed.items():
        for value in values:
            planner = FakeDaytimePlanner()
            result = planner.choose(replace(FakeScene(), **{name: value}), 'STAY')
            assert (result.status, result.action, result.candidates) == ('BLOCKED_MALFORMED_SCENE', None, ()), (name, value)
            assert planner.choose(FakeScene(), 'STAY').status == 'SELECTED_FAKE'
    assert FakeDaytimePlanner().choose(None, 'STAY').status == 'BLOCKED_MALFORMED_SCENE'


def test_hostile_interest_never_raises_or_invents_offer():
    class Hostile:
        def __hash__(self):
            raise AssertionError('must not hash untrusted candidate')
        def __eq__(self, other):
            raise AssertionError('must not compare untrusted candidate')
    for interest in (None, [], {}, ['STAY'], 1, True, Hostile()):
        result = FakeDaytimePlanner().choose(FakeScene(), interest)
        assert result.status == 'DENIED_NOT_GROUNDED'
        assert result.action is None
    result = FakeDaytimePlanner().choose(FakeScene(offered_actions=('STAY', 'MARRY_NPC')), 'MARRY_NPC')
    assert result.status == 'DENIED_NOT_GROUNDED'
    assert [c.action for c in result.candidates] == ['STAY']


def test_unresolved_attempt_latches_even_before_first_choice_and_after_refresh():
    for choose_first in (False, True):
        planner = FakeDaytimePlanner()
        if choose_first:
            assert planner.choose(FakeScene(), 'WATCH_WEATHER_TV').status == 'SELECTED_FAKE'
        assert planner.choose(FakeScene(revision=2, unresolved_attempt=True), 'STAY').status == 'BLOCKED_UNRESOLVED'
        result = planner.choose(FakeScene(revision=3, recently_completed=('WATCH_WEATHER_TV',)), 'MOVE_TO_CHAIR')
        assert (result.status, result.action, result.candidates) == ('BLOCKED_UNRESOLVED', None, ())


def test_identity_readiness_checks_are_not_masked_by_stale_revision():
    for changes, status in (({'owner': 'other'}, 'BLOCKED_ROLE_OR_OWNER'),
                            ({'epoch': 'other'}, 'BLOCKED_EPOCH'),
                            ({'p1_is_human': False}, 'BLOCKED_ROLE_OR_OWNER'),
                            ({'p2_is_ai': False}, 'BLOCKED_ROLE_OR_OWNER'),
                            ({'p2_ready': False}, 'BLOCKED_ROLE_OR_OWNER')):
        for revision in (1, 2):
            planner = FakeDaytimePlanner()
            assert planner.choose(FakeScene(), 'STAY').status == 'SELECTED_FAKE'
            assert planner.choose(replace(FakeScene(revision=revision), **changes), 'STAY').status == status


def test_changed_scene_same_revision_still_waits_and_boundary_speech_is_optional():
    planner = FakeDaytimePlanner()
    assert planner.choose(FakeScene(), 'STAY').status == 'SELECTED_FAKE'
    result = planner.choose(FakeScene(weather='rainy', p2_seated=True), 'WATCH_WEATHER_TV')
    assert (result.status, result.action) == ('WAIT_NEW_OBSERVATION', None)
    for distance in (0, 5):
        assert FakeDaytimePlanner().choose(FakeScene(p1_distance_tiles=distance), 'SPEAK_TO_P1').status == 'SELECTED_FAKE'
    for distance in (6, 1000000, None):
        result = FakeDaytimePlanner().propose(FakeScene(p1_distance_tiles=distance))
        assert result.status == 'PROPOSED_FAKE'
        assert 'SPEAK_TO_P1' not in {c.action for c in result.candidates}
    result = FakeDaytimePlanner().choose(FakeScene(recently_completed=('STAY',)), 'STAY')
    assert result.status == 'SELECTED_FAKE'
    assert next(c for c in result.candidates if c.action == 'STAY').expected_observation == 'no dispatched activity'
