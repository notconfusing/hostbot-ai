from unittest.mock import patch

import mwapi
import pytest
from requests_oauthlib import OAuth1

from hostbotai.utils import send_invite_text, load_oauth_credentials

import logging

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def mwapi_session():
    import mwapi
    session = mwapi.Session(
        host="https://en.wikipedia.org",
        user_agent="mwoauth demo script -- ahalfaker@wikimedia.org")
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


def skipped_user_test(user_name, invitee, mwapi_session, auth, test=True):
    invitee.user_name = user_name
    result = send_invite_text(invitee, mwapi_session, auth, test)
    assert result == 'already-invited-or-blocked'


def test_skip_banned_unblock_templ(invitee, mwapi_session, auth):
    return skipped_user_test('Hjrohin', invitee, mwapi_session, auth)


def test_skip_banned_tmboc_templ(invitee, mwapi_session, auth):
    return skipped_user_test('VEMBERDOM', invitee, mwapi_session, auth)


def test_skip_banned_live_api(invitee, mwapi_session, auth):
    return skipped_user_test('Komadoe', invitee, mwapi_session, auth)

def test_skip_banned_live_api_with_no_page(invitee, mwapi_session, auth):
    return skipped_user_test('Patrice Starr', invitee, mwapi_session, auth)

def test_skip_already_invited(invitee, mwapi_session, auth):
    return skipped_user_test('Premapandiri', invitee, mwapi_session, auth)

@patch('mwapi.Session.post')
def test_blacklist_error(mock_mwapi_session, invitee, mwapi_session, auth):
    mock_mwapi_session.side_effect = mwapi.errors.APIError('blacklisted', 'for sockpuppetry', 'a')
    invitee.user_name = "Harshuboy0"
    result = send_invite_text(invitee, mock_mwapi_session, auth, test=True)
    assert result == 'already-invited-or-blocked'
