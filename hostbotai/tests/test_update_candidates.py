import pandas as pd
from hostbotai.hostbot_ai import HostBot
from hostbotai.orm_models import candidates, predictions
from hostbotai.utils import load_threshholds
import json
from mock import Mock, patch
from datetime import datetime as dt

all_tables = [candidates, predictions]
from IPython import embed


def clear_tables(internalsession):
    for table in all_tables:
        internalsession.query(table).delete()
        internalsession.commit()


def load_predictions_table(internalsession, pred_f):
    predictions_df = pd.read_csv(f'test_data/{pred_f}')
    predictions_df['user_summary'] = predictions_df['user_summary'].apply(lambda s: json.loads(s))
    predictions_df['newcomer_predictions'] = predictions_df['newcomer_predictions'].apply(lambda s: json.loads(s))
    predictions_df['scores'] = predictions_df['scores'].apply(lambda s: json.loads(s))
    pred_cols = [col for col in predictions_df.columns if col != 'prediction_id']
    predictions_df.fillna("0", inplace=True)
    predictions_df['pred_obj'] = predictions_df[pred_cols].apply(lambda row: predictions(**row.to_dict()), axis=1)
    preds = list(predictions_df['pred_obj'].values)

    # embed()
    for pred in preds:
        internalsession.add(pred)
    internalsession.commit()


def test_invite_checker():
    hb = HostBot(test=True)
    clear_tables(hb.internalsession)
    invite_candidates = load_knowns_from_df('candidates_with_predictions_1.csv')
    load_predictions_table(hb.internalsession, 'predictions_1.csv')
    invitees, overflowees, non_invititees = hb.invite_decider(threshhold=load_threshholds(),
                                                              candidates=invite_candidates,
                                                              daily_limit_remaining=2,
                                                              start_now=dt.utcnow())
    assert len(invitees) == 2
    assert len(overflowees) == 1
    assert len(non_invititees) == 2


def load_knowns_from_df(fname):
    knowns_df = pd.read_csv(f'test_data/{fname}', parse_dates=[2], encoding='utf-8')
    # knowns_df['user_name'] = knowns_df['user_name'].apply(lambda un: un.encode('unicode_escape'))
    # cand_columns = ['user_id', 'user_name', 'user_registration', 'user_editcount']
    knowns_df['cand_obj'] = knowns_df.apply(lambda row: candidates(**row.to_dict()), axis=1)
    knowns = list(knowns_df['cand_obj'].values)
    return knowns


def update_len_check(known_file, candidates_file, inserts_len, updates_len):
    hb = HostBot()
    knowns = load_knowns_from_df(known_file)
    candidates_df = pd.read_csv(f'test_data/{candidates_file}', parse_dates=[3], index_col=0)
    inserts, updates = hb.add_update_candidate_users(knowns, candidates_df)

    assert len(inserts) == inserts_len
    assert len(updates) == updates_len


def test_update_candidates_from_empty():
    update_len_check('knowns_empty.csv', 'candidates_1.csv', inserts_len=461, updates_len=0)


def test_update_candidates_updates_5min():
    update_len_check('candidates_1.csv', 'candidates_2.csv', inserts_len=7, updates_len=6)


@patch('newcomerquality.scorer', autospec=True)
def test_prediction_predicts(mock_newcomer_scorer):
    ns = mock_newcomer_scorer.return_value

    ns.score_newcomer_first_days.__name__ = 'score_newcomer_first_days'
    ns.score_newcomer_first_days.return_value = 0.9

    hb = HostBot(test=True)
    knowns = load_knowns_from_df('candidates_1.csv')
    clear_tables(hb.internalsession)
    embed()
    hb.internalsession.add_all(knowns)
    hb.internalsession.commit()
    for cand in hb.internalsession.query(candidates):
        assert cand.candidate_status == 'unpredicted'
    # TODO still need to figure out how mocking works
    # hb.predict_new_candidates()
    # for cand in hb.internalsession.query(candidates):
    #     assert cand.candidate_status != 'unpredicted'


if __name__ == "__main__":
    test_invite_checker()
