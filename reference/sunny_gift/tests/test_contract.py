"""Contract examples, not assertions about Stardew or the installed pilot."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sunny_gift.contract import ContractError, Record, Reference


@pytest.fixture
def trace():
    fixture = json.loads((Path(__file__).parent / 'fixtures/gift.json').read_text())
    records = {d['record_id']: Record.read(d) for d in fixture['records']}
    model = Reference(records['O1'].data['world'])
    for r in records.values():
        model.add(r)
    return model, records, fixture['reload_world']


def changed(record, **payload):
    d = record.data
    d['payload'].update(payload)
    return Record.read(d)


def unknown(records, identity='VU'):
    d = records['V1'].data
    d['record_id'] = identity
    d['payload'].update(verdict='unknown', disposition='unknown', causal_evidence=None)
    d['refs'] = {k:v for k,v in d['refs'].items() if k in {'offer', 'attempt'}}
    return Record.read(d)


def test_accepted_ack_is_not_receipt_or_execution_end(trace):
    m, r, _ = trace
    m.dispatch(r['A1'], r['O1'])
    status = m.observe_reply(r['A1'], ack='Dialogue closed', observed_choice='accepted', evidence='simulated choice capture')
    assert status == dict(execution='running', dispatch='dispatched', reply_completed=True,
                          observed_choice='accepted', ack='Dialogue closed')
    event = m.publish(unknown(r))
    assert event.data['payload']['vocabulary'] == 'gift_outcome_unresolved'
    context = m.context('C1').data['payload']
    assert context['verified_facts'] == []
    assert context['unresolved'] == [event.ref]
    assert len(m.dispatches) == 1


def test_verified_receipt_reaches_frozen_next_context_with_optional_silence(trace):
    m, r, _ = trace
    before = m.context('before')
    m.dispatch(r['A1'], r['O1'])
    event = m.publish(r['V1'])
    context = m.context('after')
    assert before.data['payload']['event_revisions'] == []
    assert context.data['payload']['verified_facts'] == [event.ref]
    assert event.data['payload']['save_state'] == 'unconfirmed'
    assert context.data['payload']['current_possession'] == 'unknown'
    assert r['D1'].data['payload']['social'] == 'silence'
    assert len(m.dispatches) == 1  # Context delivery creates neither speech nor acceptance.


@pytest.mark.parametrize('replacement', ['canceled', 'identical-new-prompt', 'unrelated', 'missing'])
def test_stale_or_canceled_offer_dispatches_zero(trace, replacement):
    m, r, _ = trace
    current = None
    if replacement == 'canceled':
        current = changed(r['O1'], status='canceled', cancellation_evidence='simulated positive notice')
    elif replacement == 'identical-new-prompt':
        current = changed(r['O1'], token='new-instance-same-text')
    elif replacement == 'unrelated':
        current = changed(r['O1'], family='sleep')
    status = m.dispatch(r['A1'], current)
    assert status['dispatch'] == 'not_dispatched'
    assert status['observed_choice'] == 'unknown'  # Disappearance does not prove cancellation.
    assert m.dispatches == []


def test_duplicate_poll_request_and_event_vs_two_identical_real_gifts(trace):
    m, r, _ = trace
    first = m.dispatch(r['A1'], r['O1'])
    assert m.dispatch(r['A1'], None) == first  # Lost reply never triggers another dispatch.
    event1 = m.publish(r['V1'])
    assert m.publish(r['V1']) == event1
    assert m.add(r['O1']) == r['O1']
    second = {}
    for name, record in r.items():
        d = record.data
        d['record_id'] = name+'-2'
        for ref in d['refs'].values():
            ref['record_id'] += '-2'
        if d['kind'] == 'offer':
            d['payload']['token'] = 'new-instance-same-text'
        if d['kind'] == 'decision':
            d['payload']['expected_token'] = 'new-instance-same-text'
        if d['kind'] == 'verification':
            d['payload']['transition_id'] = 'T2'
        second[name] = m.add(Record.read(d))
    assert second['O1'].data['payload']['question'] == r['O1'].data['payload']['question']
    m.dispatch(second['A1'], second['O1'])
    event2 = m.publish(second['V1'])
    assert event1.ref != event2.ref
    assert len(m.dispatches) == len(m.publications) == 2
    assert m.context('C').data['payload']['verified_facts'] == [event1.ref, event2.ref]


def test_unsaved_same_day_reload_keeps_history_out_of_current_memory(trace):
    m, r, reload_world = trace
    m.dispatch(r['A1'], r['O1'])
    old = m.publish(r['V1'])
    old_context = m.context('old')
    m.reload(reload_world)
    assert m.context('new').data['payload']['event_revisions'] == []
    assert not m.context_is_current(old_context)
    assert old in m.publications  # Historical evidence retained.
    assert m.dispatch(r['A1'], r['O1'])['dispatch'] == 'dispatched'  # Historical status only.
    assert len(m.dispatches) == 1
    # A new attempt carrying the old epoch also cannot mutate.
    d = r['A1'].data
    d['record_id'] = 'late-old-attempt'
    assert m.dispatch(Record.read(d), r['O1'])['dispatch'] == 'not_dispatched'


def test_unknown_then_verified_then_correction_revises_same_event(trace):
    m, r, _ = trace
    unresolved = unknown(r)
    e1 = m.publish(unresolved)
    d = r['V1'].data
    d['revision'] = 2
    v = changed(Record.read(d), corrects=unresolved.ref)
    e2 = m.publish(v)
    frozen = m.context('frozen')
    correction = unknown(r, 'VC')
    correction = changed(correction, verdict='contradicted', corrects=v.ref)
    e3 = m.publish(correction)
    assert [e.data['record_id'] for e in [e1,e2,e3]] == ['E1']*3
    assert [e.data['revision'] for e in [e1,e2,e3]] == [1,2,3]
    assert e3.data['payload']['corrects'] == e2.ref
    assert frozen.data['payload']['verified_facts'] == [e2.ref]
    assert not m.context_is_current(frozen)
    assert m.context('new').data['payload']['verified_facts'] == []
    assert m.context('new').data['payload']['unresolved'] == [e3.ref]
    assert m.dispatches == []


@pytest.mark.parametrize('change', [dict(causal_evidence=None), dict(intervening_mutations=['other']),
                                  dict(quantity=0), dict(source='P2')])
def test_weak_evidence_cannot_certify_receipt(trace, change):
    m, r, _ = trace
    with pytest.raises(ContractError):
        m.publish(changed(r['V1'], **change))
    assert m.publications == []


def test_conflicts_require_explicit_correction_and_attempt_args_cannot_change(trace):
    m, r, _ = trace
    m.dispatch(r['A1'], r['O1'])
    with pytest.raises(ContractError):
        m.dispatch(changed(r['A1'], args={'option':1}), r['O1'])
    m.publish(r['V1'])
    with pytest.raises(ContractError):
        m.publish(unknown(r))
    assert len(m.dispatches) == len(m.publications) == 1


@pytest.mark.parametrize('field,value', [('schema','sunny.gift/2.0.0'), ('revision',0)])
def test_bad_envelope_rejected(trace, field, value):
    _, r, _ = trace
    d = r['A1'].data
    d[field] = value
    with pytest.raises(ContractError):
        Record.read(d)


@pytest.mark.parametrize('activity', ['defer', 'stay', 'other'])
def test_voluntary_non_mutation_has_no_default_decline(trace, activity):
    m, r, _ = trace
    d = r['D1'].data
    d['record_id'] = 'D-non-action'
    d['payload']['activity'] = activity
    decision = m.add(Record.read(d))
    a = r['A1'].data
    a['record_id'] = 'A-non-action'
    a['refs']['decision'] = decision.ref
    assert m.dispatch(Record.read(a), r['O1'])['dispatch'] == 'not_dispatched'
    assert m.dispatches == []


@pytest.mark.parametrize('fault', ['missing-source', 'wrong-quantity', 'variant-mismatch', 'stale', 'out-of-order'])
def test_incomplete_or_uncorrelated_captures_reject_receipt(trace, fault):
    m, r, _ = trace
    d = r['V1'].data
    if fault == 'missing-source':
        d['refs']['source_before']['record_id'] = 'absent'
    elif fault == 'wrong-quantity':
        d['payload']['quantity'] = 2
    elif fault == 'variant-mismatch':
        d['payload']['variant']['quality'] = 4
    else:
        c = r['P2after'].data
        c['record_id'] = 'bad-capture'
        c['payload'].update({'fresh':False} if fault == 'stale' else {'sequence':0})
        d['refs']['destination_after'] = m.add(Record.read(c)).ref
    with pytest.raises(ContractError):
        m.publish(Record.read(d))
    assert m.context('C').data['payload']['verified_facts'] == []


def test_correction_invalidates_dependent_decision_before_dispatch(trace):
    m, r, _ = trace
    m.publish(r['V1'])
    context = m.add(m.context('C1'))
    d = r['D1'].data
    d['record_id'] = 'D-dependent'
    d['refs']['context'] = context.ref
    decision = m.add(Record.read(d))
    correction = changed(unknown(r), corrects=r['V1'].ref)
    m.publish(correction)
    a = r['A1'].data
    a['record_id'] = 'A-dependent'
    a['refs']['decision'] = decision.ref
    assert m.dispatch(Record.read(a), r['O1'])['dispatch'] == 'not_dispatched'
    assert m.dispatches == []


@pytest.mark.parametrize('field,value', [('seat','P1'), ('fence',0)])
def test_wrong_seat_or_fence_cannot_dispatch(trace, field, value):
    m, r, _ = trace
    a = r['A1'].data
    a['record_id'] = 'A-invalid'
    a['payload'][field] = value
    assert m.dispatch(Record.read(a), r['O1'])['dispatch'] == 'not_dispatched'
    assert m.dispatches == []


def test_real_new_gift_after_reload_is_not_deduped_against_abandoned_gift(trace):
    m, r, reload_world = trace
    abandoned = m.publish(r['V1'])
    m.reload(reload_world)
    fresh = {}
    for name, record in r.items():
        d = record.data
        d['world'] = reload_world
        d['record_id'] += '-reload'
        for ref in d['refs'].values():
            ref['record_id'] += '-reload'
        if d['kind'] in {'attempt','decision'}:
            d['payload']['fence'] = 2
        if d['kind'] == 'offer':
            d['payload']['token'] = 'reload-instance'
        if d['kind'] == 'decision':
            d['payload']['expected_token'] = 'reload-instance'
        fresh[name] = m.add(Record.read(d))
    m.dispatch(fresh['A1'], fresh['O1'])
    new = m.publish(fresh['V1'])  # Same transition label, different world lineage.
    assert new.ref != abandoned.ref
    assert m.context('C-new').data['payload']['verified_facts'] == [new.ref]
    assert len(m.dispatches) == 1


def test_unknown_mutation_choice_fails_closed(trace):
    m, r, _ = trace
    d = r['D1'].data
    d['record_id'] = 'D-unknown'
    d['payload']['activity'] = 'accept-and-close-any-menu'
    decision = m.add(Record.read(d))
    a = r['A1'].data
    a['record_id'] = 'A-unknown'
    a['refs']['decision'] = decision.ref
    with pytest.raises(ContractError):
        m.dispatch(Record.read(a), r['O1'])
    assert m.dispatches == []
