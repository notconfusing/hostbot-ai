import configparser
import os

import pandas as pd
from datetime import datetime as dt
from datetime import timedelta as td

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import hostbotai
from hostbotai.orm_models import Base, candidates

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
                 'catalog': cnf.get('client','catalog', fallback='enwiki_p').replace("'",""),
                 'port': cnf.get('client','port', fallback='3306'),
                 'pymysql': cnf.get('client','pymysql', fallback='+pymysql').replace("'",""),
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


def get_cands_needing_prediction(internalsession, days_ago):
    now = dt.utcnow()
    days_ago = now - td(days=days)
    days_ago_buffered = days_ago - td(hours=1)
    min_time = days_ago_buffered.strftime(wmfdate_fmt)
    known_users = internalsession.query(candidates).filter(candidates.user_registration > min_time).all()
    return known_users
