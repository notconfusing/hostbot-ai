from hostbotai.utils import load_con_from_config, load_session_from_con
from hostbotai.utils import get_candidate_users

import pandas as pd
import logging
from IPython import embed
from hostbotai.orm_models import candidates

from datetime import datetime as dt
from datetime import timedelta as td

from hostbotai.logger import get_logger
log = get_logger()


class HostBot():
    def __init__(self, daily_limit=150, threshhold=None, test=False, tracking_days=1):
        '''
        Class to store bot state and methods
        :param daily_limit: number of users to invite per UTC day
        :param threshhold: thressholds to use for inviting, float or dict
        :param test: run quickly for testing purposes
        :param tracking_days: number of days to consider newcomers after their user_registration tamp
        '''
        self.daily_limit = daily_limit
        self.threshhold = threshhold if threshhold else 0.9
        self.wmfcon = load_con_from_config('replica.my.cnf')
        self.internalcon = load_con_from_config('internalbot.my.cnf')
        self.internalsession = load_session_from_con(self.internalcon)
        self.limit_interval_days = 1
        self.test = test
        self.tracking_days = tracking_days
        self.min_dt = dt.utcnow() - td(days=self.tracking_days) - td(hours=1) #also subtract a bit of buffer time

    def add_update_candidate_users(self, knowns, candidates_df):
        candidates_inserts = []
        candidates_updates = []

        # wanted to use database style joins, but i'll just use looping algos for now.
        # knowns_user_ids = [c.user_id for c in knowns]
        knowns_objs_dict= {c.user_id: c for c in knowns}

        for row in candidates_df.iterrows():
            cand = row[1].to_dict()
            cand_user_id = cand['user_id']
            # if the new candidates user id isn't in the knowns, we need to insert it
            if not cand_user_id in knowns_objs_dict.keys():
                candidates_inserts.append(candidates(**cand))
            # if the candidate is known, they might have a new edit count
            else:
                known = knowns_objs_dict[cand_user_id]
                # if the new edit count is higher
                if cand['user_editcount'] > known.user_editcount:
                    known.user_editcount = cand['user_editcount']
                    known.candidate_status = 'unpredicted'
                    candidates_updates.append(known)

        return candidates_inserts, candidates_updates

    def update_candidates(self):
        '''refresh the candidates table by getting latest and comparing'''
        knowns = self.internalsession.query(candidates) \
            .filter(candidates.user_registration > self.min_dt).all()
        candidates_df = get_candidate_users(self.wmfcon, min_dt=self.min_dt, test=self.test)
        candidates_inserts, candidates_updates = self.add_update_candidate_users(knowns, candidates_df)

        self.internalsession.add_all(candidates_inserts)
        self.internalsession.add_all(candidates_updates)

        self.internalsession.commit()

    def predict_new_candidates(self):
        '''make predictions using newcomer predictions module'''
        # assume the network is down.
        cands_to_predict = self.internalsession.query(candidates) \
            .filter(candidates.user_registration > self.min_dt) \
            .filter(candidates.candidate_status == 'unpredicted')

        for cand in cands_to_predict:
            try:
                pass
            except Exception as e:
                log.error(e)
            finally:
                cand.candidate_status = 'unpredicted'
                self.internalsession.commit()

    def send_invites(self):
        '''send invitations to successful newcomers and user the overflow intelligently'''
        pass

    def run(self):
        self.update_candidates()
        self.predict_new_candidates()
        self.send_invites()


if __name__ == "__main__":
    hb = HostBot(test=True)
    hb.update_candidates()
    hb.predict_new_candidates()
