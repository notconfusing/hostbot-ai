import configparser
import os
import json

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
                 'host': 'localhost',  # yes you have to be on wikitech tool-labs or ssh-tunneled
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
    new_user_query = f'''select user_id, user_name, user_registration, user_editcount 
                        from user where user_registration > {min_time} 
                        and user_editcount >= 3'''
    if test:
        new_user_query += ' limit 10'
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


def send_invite_text(invitee, mwapi_session, test):
    # make the page name
    page_title = f'User_talk:{invitee.user_name.replace(" ","_")}'
    if test:
        page_title = f'User_talk:Maximilianklein/draft/{invitee.user_name.replace(" ","_")}'

    # get the curr page info and edittoken
    curr_page_info = mwapi_session.get(action='query', prop='info', meta='tokens', titles=page_title)
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
                                          rvslots='*')
        page_doc = curr_page_revisions['query']['pages']
        [(page_id, page_doc_data)] = page_doc.items()
        page_wikitext = page_doc_data['revisions'][0]['slots']['main']['*']
        page_wikitext_lower = page_wikitext.lower()
        # print(page_wikitext_lower)
        # check if teahouse is mentioned in revision text
        teahouse_in = 'teahouse' in page_wikitext_lower
        tea_house_in = 'tea house' in page_wikitext_lower
        # if yes log and return already invited return 'already invited'
        if teahouse_in or tea_house_in:
            return 'already-invited'
        # if not post text, confirm success, return 'invited'

    # if we get to this point its because the page is uncreated or teahouse isn't mentioned in there
    post_text = f"{{{{subst:Wikipedia:Teahouse/HostBot_Invitation|personal=The Teahouse is a friendly space where new " \
                f"editors can ask questions about contributing to Wikipedia and get help from experienced editors. " \
                f"|bot={{{{noping|HostBot}}}}|timestamp=~~~~~}}}} "
    log.info(f"About to invite on {page_title} host:{mwapi_session.host}")
    mwapi_session.post(action='edit', title=page_title, section='new', text=post_text, token=csrftoken, )
    return 'invited'
