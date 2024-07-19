import os
import json
import random
import requests
import argparse

import logging

from lnma.analyzer import rpy2_nma_analyzer, rpy2_pwma_analyzer
logger = logging.getLogger("watcher")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s')

from sqlalchemy import and_, or_, not_
from tqdm import tqdm
from pprint import pprint

# for looping the watcher
from timeloop import Timeloop
from datetime import timedelta

# for checking email updates
from imbox import Imbox

import pandas as pd

# app settings
from lnma import db, create_app, srv_extract, srv_paper, srv_project
from lnma.models import *
from lnma import dora
from lnma import util
from lnma import ss_state
from lnma.analyzer import rpy2_nma_analyzer

# app for using LNMA functions and tables
app = create_app()
db.init_app(app)
app.app_context().push()

def test():
    test21()


def test21():
    '''
    Import mCSPC itable
    '''
    srv_extract.import_itable_from_xls(
        'LPR',
        'mcrpc',
        '/home/m210842/sites/dev_lnma/tmp/LPR/mCRPC/ITABLE_SAMPLE_COE.xlsx',
        None, # no filter update this time

        # flags
        flag_overwrite_decision=True,
        flag_overwrite_piece=True
    )
    print('* done')


def test20():
    srv_extract.import_extracts_from_xls(
        'LPR',
        'mcrpc',
        'pwma',
        # '/home/m210842/sites/dev_lnma/tmp/LPR/mCRPC/SOFTABLE_PMA_SAMPLE.xlsx',
        '/home/m210842/sites/dev_lnma/tmp/LPR/mCRPC/SOFTABLE_PMA_DATA_FINALIZED_V4.xlsx',
        True,
        True,
        flag_has_nma_coe=False,
    )
    print('* done')


def test19():
    '''
    Import mCSPC itable
    '''
    srv_extract.import_itable_from_xls(
        'LPR',
        'mcspc',
        '/tmp/mCSPC/ITABLE_ATTR_DATA_FINALIZED.xlsx',
        None, # no filter update this time

        # flags
        flag_overwrite_decision=False,
        flag_overwrite_piece=True
    )
    print('* done')


def test18():
    '''
    Update the pid to lowercase
    '''
    papers = Paper.query.filter(
        Paper.pid_type == 'DOI'
    ).all()

    print("* found %s papers using DOI as pid" % (
        len(papers)
    ))

    cnt_need_to_update = 0
    for p in papers:
        if p.pid.lower() != p.pid:
            cnt_need_to_update += 1

    print('* found %s papers needs to be lowercased' % (
        cnt_need_to_update
    ))

    for p_idx, p in enumerate(papers):
        if p.pid.lower() == p.pid: continue
        print('****** processing %s/%s' % (p_idx + 1, len(papers)))
        old_pid = p.pid
        new_pid = p.pid.lower()

        pieces = Piece.query.filter(
            Piece.pid == p.pid
        ).all()

        print("* found %s pieces for %s" % (
            len(pieces), p.pid
        ))

        # update paper and pieces
        p.pid = new_pid
        db.session.add(p)

        for pi in pieces:
            pi.pid = new_pid
            db.session.add(pi)

        db.session.commit()
        print('* processed %s->%s and its %s pieces' % (old_pid, new_pid, len(pieces)))

    print('* done!')


def test17():
    '''
    Import CRPC itable
    '''
    srv_extract.import_itable_from_xls(
        'LPR',
        'mcrpc',
        '/tmp/CRPC/V1/V8_DES.xlsx',
        '/tmp/CRPC/V1/ITABLE_FILTERS.xlsx',

        # flags
        flag_overwrite_decision=False,
        flag_overwrite_piece=True
    )
    print('* done')


def test16():
    all_dups = srv_paper.get_duplicated_papers('IO')


def test15():
    print('* in test now')


def test14():
    exts = srv_extract.copy_extracts(
        'IO', 
        'default',
        'treatment',

        'LPR',
        'tox_pca',
        'treatment',

        'pwma'
    )

    print('* done')


def test13():
    srv_extract.import_itable_from_xls(
        'LPR',
        'mcspc',
        '/tmp/LPR/ITABLE_ATTR_DATA_FINALIZED.xlsx',
        '/tmp/LPR/filters.xlsx'
    )
    print('* done')




def test10():
    itable = srv_extract.import_itable_from_xls(
        'LPR', 
        'default',
        '/tmp/LPR/ITABLE.xlsx',
        '/tmp/LPR/ITABLE_FILTERS.xlsx'
    )
    print('* done')


def test9():
    ret = rpy2_pwma_analyzer.test_subg_cat_raw()
    json.dump(ret, open('/tmp/jrst.json', 'w'), indent=2)



def test7():
    ret = rpy2_nma_analyzer.test_nma_bayes_pre_2()
    json.dump(ret, open('/tmp/jrst.json', 'w'), indent=2)


def test6():
    itable = srv_extract.import_itable_from_xls(
        'LPR', 
        'default',
        '/tmp/LPR/ITABLE_ATTR_DATA.xlsx',
        '/tmp/LPR/ITABLE_FILTERS.xlsx'
    )


def test_pred():
    project_id = '119bdd6a-2ae9-11eb-8100-bf78cc92e08e'
    pids = ['32966830']

    for pid in pids:
        pred = dora.update_paper_rct_result(project_id, pid)
        pprint(pred)    


def test5():
    rs = json.loads(pd.DataFrame([
        ['CHK 9ER', 0.42, 0.23, 0.74, 'Sarc'],
        ['CHK 9ER', 0.56, 0.45, 0.69, 'Non-Sarc'],
        ['IMM 151', 0.46, 0.28, 0.78, 'Sarc'],
        ['IMM 151', 0.87, 0.64, 1.17, 'Non-Sarc'],
    ], columns=['study', 'TE', 'lowerci', 'upperci', 'subgroup']).to_json(orient='records'))
    # print(rs)

    cfg = {
        'measure_of_effect': 'HR',
        'fixed_or_random': 'random',
        'tau_estimation_method': 'DL',
        'hakn_adjustment': 'FALSE'
    }

    ret = rpy2_pwma_analyzer.analyze_subg_cat_pre(
        rs,
        cfg
    )

    pprint(ret)


def test4():
    itable = srv_extract.import_itable_from_xls(
        'RCC', 
        'default',
        '/tmp/mrcc-itable.xlsx',
        '/tmp/mrcc-filters.xlsx'
    )


def test2():
    ret = srv_paper.check_existed_paper_by_file(
        'IO',
        'ovid',
        # '/tmp/IO-0110-149.xml'
        '/tmp/IO-0107-1336.xml'
    )
    print(ret['cnt'])
    # print('is_valid_pmid:', util.is_valid_pmid('12345678'))
    # print('is_valid_pmid:', util.is_valid_pmid('223456783212323212'))


def test2():
    ext_ids = srv_extract.get_extracts_by_cate_and_name(
        'RCC',
        'default',
        'nma',
        'default',
        'PFS'
    )
    print(ext_ids)

    ext = srv_extract.create_extract(
        'RCC',
        'default',
        'nma',
        'primary',
        'default',
        'Big Name Here %s' % random.randint(0, 1000),
        other_meta={

        }
    )

    print(ext.as_very_simple_dict())


if __name__ == "__main__":
    print("* Now you have the app and db to access the env")
    test()