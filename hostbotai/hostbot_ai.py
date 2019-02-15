from sqlalchemy import or_, and_

from hostbotai.utils import load_con_from_config, load_session_from_con, send_invite_text, load_mw_credentials
from hostbotai.utils import get_candidate_users, load_threshholds, load_oauth_credentials
from hostbotai.orm_models import candidates, predictions
from datetime import datetime as dt
from datetime import timedelta as td
from newcomerquality.scorer import score_newcomer_first_days, registrationDateError, usercontribError, makeFeaturesError
import mwapi
from requests_oauthlib import OAuth1

import pandas as pd
import logging
from IPython import embed

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
        self.threshhold = threshhold
        self.wmfcon = load_con_from_config('replica.my.cnf')
        self.internalcon = load_con_from_config('internalbot.my.cnf')
        self.internalsession = load_session_from_con(self.internalcon)
        self.limit_interval_days = 1
        self.test = test
        self.tracking_days = tracking_days
        self.start_now = dt.utcnow()
        self.min_dt = self.start_now - td(days=self.tracking_days) - td(hours=1)  # also subtract a bit of buffer time

    def get_mwpai_session(self):
        if hasattr(self, 'mwapi_session'):
            return self.mwapi_session
        else:
            self.mwapi_session = mwapi.Session("https://en.wikipedia.org",
                                               user_agent="HostBot-AI <max@notconfusing.com>")

            mw_username, mw_password = load_mw_credentials(fname=None)
            login_ret = self.mwapi_session.login(mw_username, mw_password)
            assert login_ret['status'] == 'PASS'
            # embed()
            return self.mwapi_session

    def get_oauth_obj(self):
        """Note: This is just a single-consumer OAuth, we don't edit on behalf of anyone."""
        if hasattr(self, 'auth'):
            return self.auth
        else:
            oauth_credentials = load_oauth_credentials(fname=None)
            self.auth = OAuth1(**oauth_credentials)
            return self.auth

    def add_update_candidate_users(self, knowns, candidates_df):
        candidates_inserts = []
        candidates_updates = []

        # wanted to use database style joins, but i'll just use looping algos for now.
        # knowns_user_ids = [c.user_id for c in knowns]
        knowns_objs_dict = {c.user_id: c for c in knowns}

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

        log.info(f'Found {len(candidates_df)} candidates with minimum regisration {self.min_dt}')
        candidates_inserts, candidates_updates = self.add_update_candidate_users(knowns, candidates_df)
        log.info(f'Found {len(candidates_inserts)} new candidates.')
        log.info(f'Found {len(candidates_updates)} existing candidates with higher editcounts')

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
                # embed()
                score = score_newcomer_first_days(user_id=cand.user_id,
                                                  context='enwiki',
                                                  days=self.tracking_days,
                                                  registration_date=cand.user_registration,
                                                  mwapisession=self.get_mwpai_session())

                assert cand.user_id == score['user_id']
                pred = predictions(user_id=cand.user_id,
                                   user_summary=score['user_summary'],
                                   scores=score['scores'],
                                   newcomer_predictions=score['newcomer_predictions'],
                                   pred_min=score['newcomer_predictions']['sessions_goodfaith_proba_min'])

                cand.candidate_status = 'predicted'
                self.internalsession.add(cand)
                self.internalsession.add(pred)
                self.internalsession.commit()
            # there are a variety of reasons for legit errors
            except (registrationDateError, usercontribError, makeFeaturesError) as e:
                log.error(e)
                cand.candidate_status = 'predicition_error'

                pred = predictions(user_id=cand.user_id,
                                   pred_error=e)
                self.internalsession.add(cand)
                self.internalsession.add(pred)
                self.internalsession.commit()
            ## If we have some network errors we don't want to insert anything
            except Exception as e:
                log.error(e)
                cand.candidate_status = 'unpredicted'
                self.internalsession.add(cand)
                self.internalsession.commit()

    def invite_decider(self, threshhold, candidates, daily_limit_remaining, start_now):
        invitees = []
        overflowees = []
        non_invititees = []

        curr_thresh = threshhold[start_now.strftime('%a')]

        log.info(f'DRL: daily limit remaining before deciding {daily_limit_remaining}')

        for cand in candidates:
            cand_pred = self.internalsession.query(predictions). \
                filter(predictions.user_id == cand.user_id). \
                order_by(predictions.predicted_at.desc()). \
                first()

            if cand_pred.pred_min > curr_thresh:
                if daily_limit_remaining > 0:
                    # then we can invite:
                    invitees.append(cand)
                    daily_limit_remaining -= 1
                else:
                    overflowees.append(cand)
            else:
                non_invititees.append(cand)

        log.info(f'DRL: daily limit remaining after deciding {daily_limit_remaining}')

        return invitees, overflowees, non_invititees

    def decide_invitees(self):
        '''send invitations to successful newcomers and user the overflow intelligently'''
        # load threshholds
        if not self.threshhold:
            self.threshhold = load_threshholds()

        today = self.start_now.date()
        beginning_of_today = today
        # TODO maybe invites_sent_today should not include overflow just to not be confusing
        invites_sent_today = self.internalsession.query(candidates). \
            filter(candidates.created_at > today). \
            filter(candidates.invite_sent.in_(['invited', 'test-invited','overflow'])).count()

        log.info(f'DRL: invites & overflows sent today {invites_sent_today}, today to bot is: {today}')
        daily_limit_remaining = self.daily_limit - invites_sent_today

        if daily_limit_remaining < 0:
            log.error('Daily limit exceeded!')
            daily_limit_remaining = 0

        invite_candidates = self.internalsession.query(candidates). \
            filter(and_(candidates.invite_sent.in_(None, 'not-invited'),    # considers re-predicted users (TODO: just repredicted users)
                        candidates.candidate_status == 'predicted')).all()  # UNSENT AND PREDICTED USERS)

        log.info(f'Found {len(invite_candidates)} invite candidates')
        # embed()

        invitees, overflowees, non_invitees = self.invite_decider(threshhold=self.threshhold,
                                                                    candidates=invite_candidates,
                                                                    daily_limit_remaining=daily_limit_remaining,
                                                                    start_now=self.start_now)

        log.info(f'Found {len(invitees)} invitees')
        log.info(f'Found {len(overflowees)} overflowees')
        log.info(f'Found {len(non_invitees)} non_invitees')

        assert len(invitees) + len(overflowees) + len(non_invitees) == len(invite_candidates)

        self.invite_invitees(invitees)
        self.handle_overflowees(overflowees)
        self.handle_non_invitees(non_invitees)

    def invite_invitees(self, invitees):
        """actually send wikipedia messages to invitees"""
        for invitee in invitees:
            invite_status = send_invite_text(invitee, mwapi_session=self.get_mwpai_session(),
                                             auth=self.get_oauth_obj(),
                                             test=self.test)
            self.change_invite_status_of_candidates([invitee], invite_status)

    def handle_overflowees(self, overflowees):
        """choose what to do with candidates who otherwise would have been invited if not for limit"""
        # This is our control group to test against cohort effects. That ORES-favoured would be retained anyway, etc.
        self.change_invite_status_of_candidates(overflowees, 'overflow')

    def handle_non_invitees(self, non_invitees):
        """do something with candidates that don't meet criteria"""
        self.change_invite_status_of_candidates(non_invitees, 'not-invited')

    def change_invite_status_of_candidates(self, change_candidates, new_status):
        for cand in change_candidates:
            cand.invite_sent = new_status
            self.internalsession.add(cand)
        self.internalsession.commit()

    def run(self):
        stage_fns = (self.update_candidates,
                    self.predict_new_candidates,
                     self.decide_invitees)
        for stage_fn in stage_fns:
            fn_name = stage_fn.__name__
            try:
                log.info(f'STARTING stage {fn_name}')
                stage_fn()
                log.info(f'STOPPING stage {fn_name}')
            except Exception as e:
                log.error(e)


if __name__ == "__main__":
    hb = HostBot(test=True)
    hb.run()
