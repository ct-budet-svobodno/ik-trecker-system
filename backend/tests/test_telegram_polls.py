import hashlib
import hmac
import json
import time

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User
from app.models.telegram_poll import TelegramPollRecipient
from app.services import broadcast_service, telegram_poll_service, telegram_service
from tests.conftest import TestingSessionLocal


def auth(client, credentials):
    token = client.post('/api/auth/login', data=credentials).json()['access_token']
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def scenario(client, admin_credentials, employee_credentials, monkeypatch):
    monkeypatch.setattr(settings, 'telegram_bot_token', 'test-token')
    monkeypatch.setattr(telegram_poll_service, 'SessionLocal', TestingSessionLocal)
    monkeypatch.setattr(broadcast_service, '_spawn', lambda target, *args: target(*args))
    monkeypatch.setattr(broadcast_service, 'SEND_INTERVAL', 0)
    messages = []
    monkeypatch.setattr(telegram_service, 'call', lambda method, payload, **kw: messages.append(payload) or {})
    with TestingSessionLocal() as db:
        employee = db.scalar(select(User).where(User.username == 'employee'))
        employee.telegram_id = 123456789012
        db.commit()
        employee_id = employee.id
        admin_id = db.scalar(select(User.id).where(User.username == 'admin'))
    admin = auth(client, admin_credentials)
    member = auth(client, employee_credentials)
    data = dict(text='**Собрание** завтра?', options=['Приду', 'Не приду'], user_ids=[employee_id, admin_id])
    return admin, member, data, messages


def signed_vote(client, poll_id, choice=0, telegram_id=123456789012, stamp=None, token='test-token', chat_id=None):
    raw = json.dumps(dict(poll_id=poll_id, choice=choice, telegram_id=telegram_id, chat_id=chat_id)).encode()
    stamp = str(stamp or int(time.time()))
    signature = hmac.new(token.encode(), stamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
    return client.post('/api/telegram-polls/vote', content=raw, headers={
        'Content-Type': 'application/json', 'X-Poll-Time': stamp, 'X-Poll-Signature': signature,
    })


def test_personal_vote_change_waiting_and_close(client, scenario):
    admin, member, data, messages = scenario
    response = client.post('/api/telegram-polls', json=data, headers=admin)
    assert response.status_code == 201, response.text
    poll = response.json(); poll_id = poll['id']
    assert poll['sent'] == 1 and poll['failed'] == 1 and poll['voted'] == 0
    assert len(messages) == 1
    assert messages[0]['reply_markup']['inline_keyboard'][0][0]['callback_data'] == f'ikpoll:{poll_id}:0'
    assert 'виден администратору' in messages[0]['text']
    assert signed_vote(client, poll_id).status_code == 200
    assert signed_vote(client, poll_id).status_code == 200
    assert signed_vote(client, poll_id, choice=1).status_code == 200
    detail = client.get(f'/api/telegram-polls/{poll_id}', headers=admin).json()
    assert detail['counts'] == [0, 1] and detail['voted'] == 1
    waiting = [r for r in detail['recipients'] if r['choice'] is None]
    assert len(waiting) == 1 and waiting[0]['delivery'] == 'no_telegram'
    assert client.put(f'/api/telegram-polls/{poll_id}/closed', headers=admin).status_code == 200
    assert signed_vote(client, poll_id).status_code == 409
    assert client.get(f'/api/telegram-polls/{poll_id}', headers=admin).json()['counts'] == [0, 1]


def test_permissions_and_signed_identity(client, scenario):
    admin, member, data, _ = scenario
    poll_id = client.post('/api/telegram-polls', json=data, headers=admin).json()['id']
    for path in ['/api/telegram-polls', f'/api/telegram-polls/{poll_id}']:
        assert client.get(path, headers=member).status_code == 403
        assert client.get(path).status_code == 401
    assert client.post('/api/telegram-polls', json=data, headers=member).status_code == 403
    assert client.put(f'/api/telegram-polls/{poll_id}/closed', headers=member).status_code == 403
    assert signed_vote(client, poll_id, token='forged').status_code == 401
    assert signed_vote(client, poll_id, stamp=int(time.time())-120).status_code == 401
    assert signed_vote(client, poll_id, telegram_id=999).status_code == 409
    assert signed_vote(client, poll_id, choice=2).status_code == 409
    assert client.post('/api/telegram-polls/vote', json={'telegram_id':123456789012}, headers=member).status_code == 401
    with TestingSessionLocal() as db:
        user = db.scalar(select(User).where(User.username == 'employee'))
        user.is_active = False; db.commit()
    assert signed_vote(client, poll_id).status_code == 409


@pytest.mark.parametrize('options', [['Да'], ['Да', ' Да '], ['', 'Нет'], ['a'*65, 'Нет']])
def test_invalid_options(client, scenario, options):
    admin, _, data, _ = scenario
    data['options'] = options
    assert client.post('/api/telegram-polls', json=data, headers=admin).status_code == 422


def test_bad_recipients_and_disabled_bot(client, scenario, monkeypatch):
    admin, _, data, _ = scenario
    data['user_ids'] = [99999]
    assert client.post('/api/telegram-polls', json=data, headers=admin).status_code == 400
    monkeypatch.setattr(settings, 'telegram_bot_token', '')
    assert client.post('/api/telegram-polls', json=data, headers=admin).status_code == 400
    assert signed_vote(client, 1, token='').status_code == 401


def test_delivery_failure_and_recovery(client, scenario, monkeypatch):
    admin, _, data, _ = scenario
    monkeypatch.setattr(broadcast_service, '_spawn', lambda *args: None)
    poll_id = client.post('/api/telegram-polls', json=data, headers=admin).json()['id']
    monkeypatch.setattr(broadcast_service, '_send', lambda payload: False)
    telegram_poll_service.recover_delivery()
    detail = client.get(f'/api/telegram-polls/{poll_id}', headers=admin).json()
    assert detail['failed'] == 2 and detail['pending'] == 0
    with TestingSessionLocal() as db:
        recipient = db.scalar(select(TelegramPollRecipient).where(TelegramPollRecipient.telegram_id.is_not(None)))
        recipient.delivery = 'sending'; db.commit()
    monkeypatch.setattr(broadcast_service, '_send', lambda payload: pytest.fail('duplicate delivery'))
    telegram_poll_service.recover_delivery()
    assert client.get(f'/api/telegram-polls/{poll_id}', headers=admin).json()['failed'] == 2


def test_group_chat_selection_delivery_and_voting(client, scenario, monkeypatch):
    admin, member, data, messages = scenario
    def fake_call(method, payload, **kw):
        if method == 'getChat':
            return {'id': payload['chat_id'], 'title': 'Чат актива', 'type': 'supergroup'}
        if method == 'getMe':
            return {'id': 77}
        if method == 'getChatMember':
            return {'status': 'administrator'}
        messages.append(payload)
        return {}
    monkeypatch.setattr(telegram_service, 'call', fake_call)
    assert client.post('/api/telegram-polls/chats', json={'chat_id': -100123}, headers=member).status_code == 403
    assert client.post('/api/telegram-polls/chats', json={'chat_id': 123}, headers=admin).status_code == 422
    added = client.post('/api/telegram-polls/chats', json={'chat_id': -100123}, headers=admin)
    assert added.status_code == 200 and added.json()['title'] == 'Чат актива'
    assert len(client.get('/api/telegram-polls', headers=admin).json()['chats']) == 1
    data['chat_id'] = -100123
    response = client.post('/api/telegram-polls', json=data, headers=admin)
    assert response.status_code == 201, response.text
    poll = response.json()
    poll = client.get(f"/api/telegram-polls/{poll['id']}", headers=admin).json()
    assert poll['chat_title'] == 'Чат актива' and poll['chat_delivery'] == 'sent'
    assert len(messages) == 1 and messages[0]['chat_id'] == -100123
    assert signed_vote(client, poll['id']).status_code == 409
    assert signed_vote(client, poll['id'], chat_id=-100999).status_code == 409
    assert signed_vote(client, poll['id'], chat_id=-100123).status_code == 200
    assert signed_vote(client, poll['id'], chat_id=-100123, telegram_id=999).status_code == 409
    assert client.get(f"/api/telegram-polls/{poll['id']}", headers=admin).json()['voted'] == 1
    telegram_poll_service.deliver(poll['id'])
    assert len(messages) == 1


def test_chat_validation_and_unknown_chat(client, scenario, monkeypatch):
    admin, _, data, _ = scenario
    monkeypatch.setattr(telegram_service, 'call', lambda *args, **kw: {'type': 'channel'})
    assert client.post('/api/telegram-polls/chats', json={'chat_id': -100123}, headers=admin).status_code == 400
    data['chat_id'] = -100999
    assert client.post('/api/telegram-polls', json=data, headers=admin).status_code == 400
    def no_permission(method, payload, **kw):
        if method == 'getChat': return {'type': 'supergroup', 'title': 'Чат'}
        if method == 'getMe': return {'id': 77}
        return {'status': 'left'}
    monkeypatch.setattr(telegram_service, 'call', no_permission)
    assert client.post('/api/telegram-polls/chats', json={'chat_id': -100123}, headers=admin).status_code == 400
