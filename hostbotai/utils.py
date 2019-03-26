import configparser
import os
import json
import random

import pandas as pd
from datetime import datetime as dt
from datetime import timedelta as td

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import hostbotai
from hostbotai.orm_models import Base, candidates
from hostbotai.logger import get_logger

log = get_logger()
wmfdate_fmt = '%Y%m%d%H%M%S'


def load_con_from_config(config_fname):
    module_path = os.path.dirname(hostbotai.__file__)
    # print(module_path)
    config_file = os.path.join(module_path, '..', 'config', config_fname)
    cnf = configparser.ConfigParser()
    cnf.read_file(open(config_file, 'r'))

    db_params = {'user': cnf.get('client', 'user').replace("'", ""),
                 'pwd': cnf.get('client', 'password').replace("'", ""),
                 'host': cnf.get('client', 'host', fallback='localhost').replace("'", ""),
                 # yes you have to be on wikitech tool-labs or ssh-tunneled
                 'catalog': cnf.get('client', 'catalog', fallback='enwiki_p').replace("'", ""),
                 'port': cnf.get('client', 'port', fallback='3306'),
                 'pymysql': cnf.get('client', 'pymysql', fallback='+pymysql').replace("'", ""),
                 }

    constr = 'mysql{pymysql}://{user}:{pwd}@{host}:{port}/{catalog}?charset=utf8'.format(**db_params)

    con = create_engine(constr, encoding='utf-8')
    return con


def load_session_from_con(con):
    Base.metadata.bind = con
    DBSession = sessionmaker(bind=con)
    db_session = DBSession()
    return db_session


def utf_8_decode(colstr):
    return colstr.decode('utf-8')


def wmftimestamp(datestr):
    decoded = utf_8_decode(datestr)
    return dt.strptime(decoded, wmfdate_fmt)


def get_candidate_users(con, min_dt, test=False):
    min_time = min_dt.strftime(wmfdate_fmt)
    # notice the user_id constant below. its a shortcut
    # see https://github.com/notconfusing/hostbot-ai/issues/1 for a longer term solution.
    new_user_query = f'''select user_id, user_name, user_registration, user_editcount 
                        from user where user_registration > {min_time} 
                        and user_editcount >= 3
                        and user_id > 35000000
                        and user_id %% 2 = 0;'''
    # if test:
    #     new_user_query += ' limit 10'
    print(new_user_query)
    new_users = pd.read_sql(new_user_query, con)
    new_users['user_name'] = new_users['user_name'].apply(utf_8_decode)
    new_users['user_registration'] = new_users['user_registration'].apply(wmftimestamp)
    return new_users


def load_bot_config(fname=None):
    if fname == None:
        fname = 'default_config.json'
    module_path = os.path.dirname(hostbotai.__file__)
    # print(module_path)
    config_file = os.path.join(module_path, '..', 'config', fname)
    with open(config_file, 'r') as tf:
        config = json.load(tf)
        return config


def load_threshholds(fname=None):
    bot_config = load_bot_config(fname)
    return bot_config['threshholds']


def load_mw_credentials(fname=None):
    bot_config = load_bot_config(fname)
    return bot_config['wm_username'], bot_config['wm_password']


def load_oauth_credentials(fname=None):
    bot_config = load_bot_config(fname)
    return {'client_key': bot_config['client_key'],
            'client_secret': bot_config['client_secret'],
            'resource_owner_key': bot_config['resource_owner_key'],
            'resource_owner_secret': bot_config['resource_owner_secret'], }


def load_inviters(fname=None):
    bot_config = load_bot_config(fname)
    return bot_config['inviters']


def send_invite_text(invitee, mwapi_session, auth, test):
    # make the page name
    page_title = f'User_talk:{invitee.user_name.replace(" ","_")}'
    if test:
        page_title = f'User_talk:Maximilianklein/draft/{invitee.user_name.replace(" ","_")}'

    # get the curr page info and edittoken
    curr_page_info = mwapi_session.get(action='query', prop='info', meta='tokens', titles=page_title, auth=auth)
    # edit token
    csrftoken = curr_page_info['query']['tokens']['csrftoken']
    # lastrevid
    pages = curr_page_info['query']['pages']
    [(page_id, page_data)] = pages.items()
    uncreated_page = page_id == '-1'
    if not uncreated_page:
        # go try and do these things
        lastrevid = page_data['lastrevid']
        # lasttimestamp
        lasttouched = page_data['touched']
        # get the latest revision text
        curr_page_revisions = mwapi_session.get(action='query', prop='revisions', rvprop='content', titles=page_title,
                                                rvslots='*', auth=auth)
        page_doc = curr_page_revisions['query']['pages']
        [(page_id, page_doc_data)] = page_doc.items()
        page_wikitext = page_doc_data['revisions'][0]['slots']['main']['*']
        page_wikitext_lower = page_wikitext.lower()
        # print(page_wikitext_lower)
        # check if teahouse is mentioned in revision text
        skip_templates = ['uw-vandalism4', 'final warning', '{{sock|', 'uw-unsourced4', 'uw-socksuspect',
                          'Socksuspectnotice', 'only warning', 'without further warning', 'Uw-socksuspect',
                          'sockpuppetry', 'Teahouse', 'uw-cluebotwarning4', 'uw-vblock', 'uw-speedy4',
                          '{{bots|deny=HostBot', '{{Bots|deny=HostBot', '{{nobots', '{{Nobots',
                          'tea house', 'teahouse', """You have been '''[[WP:Blocking policy|blocked]]'''""",
                          '{{unblock', """[[Wikipedia:Blocking policy|blocked]]""",
                          'blocking policy']
        skip_templates = [s.lower() for s in skip_templates]
        for skip_template in skip_templates:
            # log.debug(f"Skip template is: {skip_template}. Wikitext on page: {page_wikitext_lower}")
            if skip_template in page_wikitext_lower:
                return 'already-invited-or-blocked'

        # if not post text, confirm success, return 'invited'

    # Try to see if the user is blocked via api seperately.
    block_status = mwapi_session.get(action='query', list='users', ususers=invitee.user_name, usprop='blockinfo')
    log.info(f"{invitee.user_name} has block status {block_status}")
    try:
        blockid = block_status['query']['users'][0]['blockid']
        if blockid:
            log.info(f"User {invitee.user_name} was blocked but had no block templates")
            return 'already-invited-or-blocked'
    except KeyError: #
        pass #if there wasn't a blockid in the response this user is not blocked at the moment
        log.info(f"User {invitee.user_name} does not appear have to have blocked status.")
    # if we get to this point its because the page is uncreated or teahouse isn't mentioned in there
    try:
        inviters = load_inviters()
        inviter = random.choice(inviters)
        post_text = "{{{{subst:Wikipedia:Teahouse/HostBot_Invitation|personal=The Teahouse is a friendly space " \
                    "where new editors can ask questions about contributing to Wikipedia and get help from " \
                    "experienced editors like {{{{noping|{inviter:s}}}}} ([[User_talk:{inviter:s}|talk]]). |bot=" \
                    "{{{{noping|HostBot}}}}|timestamp=~~~~~}}}} ".format(inviter=inviter)
    except KeyError:  # coundn't find inviters
        post_text = f"{{{{subst:Wikipedia:Teahouse/HostBot_Invitation|personal=The Teahouse is a friendly space where new " \
                    f"editors can ask questions about contributing to Wikipedia and get help from experienced editors. " \
                    f"|bot={{{{noping|HostBot}}}}|timestamp=~~~~~}}}} "
    log.info(f"About to invite on {page_title} host:{mwapi_session.host}")
    mwapi_session.post(action='edit', title=page_title, section='new', text=post_text, token=csrftoken, auth=auth)
    return 'invited'
