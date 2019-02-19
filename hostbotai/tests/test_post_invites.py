import pytest
from requests_oauthlib import OAuth1

from hostbotai.utils import send_invite_text, load_oauth_credentials

import logging

logging.basicConfig(level=logging.DEBUG)

@pytest.fixture
def mwapi_session():
    import mwapi
    session = mwapi.Session(
            host = "https://en.wikipedia.org",
            user_agent = "mwoauth demo script -- ahalfaker@wikimedia.org")
    return session

@pytest.fixture
def invitee():
    class fakeInvitee:
        def __init__(self, user_name):
            self.user_name = user_name
    invi = fakeInvitee('test_user')
    return invi

@pytest.fixture
def auth():
    oauth_credentials = load_oauth_credentials(fname=None)
    return OAuth1(**oauth_credentials)

def test_skip_already_invited(invitee, mwapi_session, auth, test=True):
    result = send_invite_text(invitee, mwapi_session, auth, test)
    assert result == 'already-invited'

def test_skip_banned(invitee, mwapi_session, auth, test=True):
    invitee.user_name = 'Premapandiri'
    result = send_invite_text(invitee, mwapi_session, auth, test)
    assert result == 'already-invited'
