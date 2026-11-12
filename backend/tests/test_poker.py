import pytest

from app.games import poker
from app.models.user import UserRole
from app.schemas.user import UserCreate
from app.services import user_service
from tests.conftest import TestingSessionLocal


def players(client, count=3):
    db = TestingSessionLocal()
    try:
        for i in range(count):
            user_service.create_user(db, UserCreate(
                full_name=f'Poker {i}', username=f'poker{i}', password='pokerpass123', role=UserRole.EMPLOYEE
            ))
    finally:
        db.close()
    return [
        {'Authorization': 'Bearer ' + client.post('/api/auth/login', data={
            'username': f'poker{i}', 'password': 'pokerpass123'
        }).json()['access_token']}
        for i in range(count)
    ]


def test_hand_ranking():
    # Wheel straight loses to a six-high straight; a straight flush beats quads.
    assert poker.score_five((12, 0, 1, 2, 3)) == (8, 5)
    assert poker.score_five((0, 1, 2, 3, 4)) == (8, 6)
    assert poker.score_five((0, 13, 26, 39, 1))[0] == 7
    assert poker.score_seven([0, 1, 2, 3, 4, 13, 26])[0] == 8


def test_betting_and_side_pots():
    state = {'players': [
        {'id': 1, 'stack': 100, 'name': 'A'},
        {'id': 2, 'stack': 1000, 'name': 'B'},
        {'id': 3, 'stack': 1000, 'name': 'C'},
    ], 'dealer': -1, 'phase': None}
    poker.new_hand(state)
    assert len({card for p in state['players'] for card in p['cards']}) == 6
    assert state['turn'] == 0
    poker.move(state, 0, 'all_in')
    poker.move(state, 1, 'call')
    poker.move(state, 2, 'call')
    assert state['phase'] == 'flop' and len(state['board']) == 3
    while state['phase'] != 'showdown':
        poker.move(state, state['turn'], 'check')
    assert len(state['board']) == 5
    assert sum(p['stack'] for p in state['players']) == 2100
    assert state['result']['payouts']


def test_side_pot_goes_to_next_best_hand():
    state = {
        'players': [
            {'cards': [12, 25], 'invested': 100, 'stack': 0, 'folded': False},
            {'cards': [11, 24], 'invested': 200, 'stack': 0, 'folded': False},
            {'cards': [10, 23], 'invested': 200, 'stack': 0, 'folded': False},
        ],
        'board': [2, 16, 30, 44, 9], 'dealer': 0,
    }
    poker._showdown(state)
    assert [p['stack'] for p in state['players']] == [300, 200, 0]


def test_api_lobby_privacy_and_turn(client):
    host, guest, stranger = players(client)
    created = client.post('/api/games/poker', headers=host)
    assert created.status_code == 201
    code = created.json()['code']
    assert created.json()['invite_url'].endswith(f'/games/poker/{code}')
    assert client.get('/api/games/poker/open', headers=guest).json()[0]['code'] == code
    assert client.post(f'/api/games/poker/{code}/start', headers=host).status_code == 400
    assert client.post(f'/api/games/poker/{code}/join', headers=guest).status_code == 200
    assert client.get('/api/games/poker/open', headers=guest).json() == []
    assert client.get('/api/games/poker', headers=guest).json()[0]['code'] == code
    assert client.post(f'/api/games/poker/{code}/start', headers=guest).status_code == 400
    started = client.post(f'/api/games/poker/{code}/start', headers=host).json()
    assert started['phase'] == 'preflop' and started['seat'] == 0
    assert all(isinstance(card, int) for card in started['players'][0]['cards'])
    assert started['players'][1]['cards'] == [None, None]
    assert client.get(f'/api/games/poker/{code}', headers=stranger).status_code == 404
    assert client.post(f'/api/games/poker/{code}/join', headers=stranger).status_code == 404
    assert client.get('/api/games/poker/open', headers=stranger).json() == []
    assert client.post(f'/api/games/poker/{code}/move', headers=host, json={
        'action': 'check', 'version': started['version']
    }).status_code == 400
    moved = client.post(f'/api/games/poker/{code}/move', headers=host, json={
        'action': 'call', 'version': started['version']
    })
    assert moved.status_code == 200
    assert client.post(f'/api/games/poker/{code}/move', headers=host, json={
        'action': 'fold', 'version': started['version']
    }).status_code == 409
