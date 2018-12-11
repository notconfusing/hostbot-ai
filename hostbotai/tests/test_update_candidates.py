import pandas as pd
from hostbotai.hostbot_ai import HostBot
from hostbotai.orm_models import candidates, predictions
from hostbotai.utils import utf_8_decode
all_tables = [candidates, predictions]
from IPython import embed


def load_knowns_from_df(fname):
    knowns_df = pd.read_csv(f'test_data/{fname}', parse_dates=[3], index_col=0, encoding='utf-8')
    # knowns_df['user_name'] = knowns_df['user_name'].apply(lambda un: un.encode('unicode_escape'))
    cand_columns = ['user_id', 'user_name', 'user_registration', 'user_editcount']
    knowns_df['cand_obj'] = knowns_df[cand_columns].apply(lambda row: candidates(**row.to_dict()), axis=1)
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


def clear_tables(internalsession):
    for table in all_tables:
        internalsession.query(table).delete()
        internalsession.commit()


def test_prediction_predicts():
    hb = HostBot(test=True)
    knowns = load_knowns_from_df('candidates_1.csv')
    clear_tables(hb.internalsession)
    # embed()
    hb.internalsession.add_all(knowns)
    hb.internalsession.commit()
    for cand in hb.internalsession.query(candidates):
        assert cand.candidate_status == 'unpredicted'
    hb.predict_new_candidates()
    # for cand in hb.internalsession.query(candidates):
    #     assert cand.candidate_status != 'unpredicted'

if __name__=="__main__":
    test_prediction_predicts()

