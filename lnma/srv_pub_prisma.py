'''
Services of PRISMA for publication site
'''
import os
import json
import copy
import pandas as pd

from flask import current_app

from lnma import dora
from lnma import util
from lnma import ss_state
from lnma import settings
from lnma import srv_extract
from lnma import db

from lnma import srv_paper
from lnma import srv_project

def get_prisma_json(keystr, cq_abbr):
    '''
    Make PRISMA.json
    '''
    output_fn = 'PRISMA.json'
    full_output_fn = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        keystr, 
        cq_abbr,
        output_fn
    )

    # make the cache
    util.mk_graphdata_path(current_app.instance_path, keystr, cq_abbr)

    # get the result for database
    ret = get_pub_prisma_from_db(
        keystr, 
        cq_abbr
    )
    latest = srv_project.get_project_latest_stat_by_keystr(keystr)
    ret['latest'] = latest

    # catch the result
    json.dump(ret, open(full_output_fn, 'w'), default=util.json_encoder)
    print('* generated PRISMA.json at %s' % (full_output_fn))

    return ret


def get_pub_prisma_from_db(keystr, cq_abbr='default'):
    '''
    Get the PRISMA from db for public site

    This will combine the information from project meta and DB
    '''
    # get this project
    project = dora.get_project_by_keystr(keystr)

    if project is None:
        return None

    # get the ID for this func
    project_id = project.project_id

    # get the living part
    living_prisma = get_prisma_by_cq(
        project_id,
        cq_abbr,
        True
    )

    # check if exists
    past_prisma = None
    if 'prisma' not in project.settings:
        # if no history is provided, use empty
        past_prisma = copy.deepcopy(settings.PRISMA_PAST_TEMPLATE)

    elif cq_abbr not in project.settings['prisma']:
        # if no history is provided, use empty
        past_prisma = copy.deepcopy(settings.PRISMA_PAST_TEMPLATE)

    else:
        # great, you have user input information
        # just use this for the past_prisma
        past_prisma = copy.deepcopy(
            project.settings['prisma'][cq_abbr]
        )

    # start to merge?
    # we just need the following from living
    # a1: the records in living
    # e2: ex by title in living 
    # e22: ex by abs in living
    # e3: ex by fulltext
    # e3_by_reason: e3
    # f1: the final number in SR
    # f3: the final number in MA
    # we need to calculate the a2 and a3.
    # And also the u1 and u2
    prisma = {}

    # first, the living
    for s in ['s0', 'a1', 'a2x', 'e2', 'e22', 'e3', 'f1', 'f3', 'a3x', 'f2']:
        tmp = copy.deepcopy(living_prisma['stat'][s])
        tmp['paper_list'] = tmp['pids']
        tmp['study_list'] = tmp['rcts']
        tmp['n_pmids'] = tmp['n']
        tmp['n_ctids'] = len(tmp['rcts'])

        prisma[s] = tmp

    # then, the living details for the e3 reasons
    prisma['e3_by_reason'] = copy.deepcopy(
        living_prisma['stat']['e3_by_reason']
    )
    prisma['e3i_by_reason'] = copy.deepcopy(
        living_prisma['stat']['e3i_by_reason']
    )

    # second, copy the past directly
    for s in ['b1', 'b2', 'b3', 'b4', 'b5', 'b6', 'b7']:
        prisma[s] = past_prisma[s]

    # backup the e2
    prisma['e21'] = copy.deepcopy(prisma['e2'])
    # start to merge e2, pub.e2 is the sum of ex by title and abs
    prisma['e2']['n_pmids'] += prisma['e22']['n_pmids']
    prisma['e2']['n_pmids'] += past_prisma['e2']['n_pmids']
    prisma['e2']['text'] += ' and abstract'

    # merge e3
    prisma['e3']['n_pmids'] += past_prisma['e3']['n_pmids']
    
    # calc a2 and u1
    # the a2 is the difference between b6 and f1
    # first, get all new studies
    # but these studies could be categorized into 2 types:
    # 1. pure new study and new paper
    # 2. existing study but new follow-up paper
    # So, we need to check each new paper and decide which belong to which
    a2_study_list = [] # for pure new study
    a2_paper_list = [] # for pure new study's paper
    u1_study_list = [] # for follow-up study
    u1_paper_list = [] # for follow-up study's paper
    a2_study_list, a2_paper_list, u1_study_list, u1_paper_list = _get_prisma_updated(
        prisma['b6'], prisma['f1'], living_prisma['paper_dict']
    )

    prisma['a2'] = {
        "study_list": a2_study_list,
        "paper_list": a2_paper_list,
        "stage": "a1",
        "text": "New studies included in SR"
    }
    # then calculate the n_pmids and n_ctids
    prisma['a2']['n_pmids'] = len(prisma['a2']['paper_list'])
    prisma['a2']['n_ctids'] = len(prisma['a2']['study_list'])

    # calc a3
    # the a3 is the difference between b7 and f3
    # the calculation follows the same process
    a3_study_list = [] # for pure new study
    a3_paper_list = [] # for pure new study's paper
    u2_study_list = [] # for follow-up study
    u2_paper_list = [] # for follow-up study's paper
    a3_study_list, a3_paper_list, u2_study_list, u2_paper_list = _get_prisma_updated(
        prisma['b7'], prisma['f3'], living_prisma['paper_dict']
    )
    prisma['a3'] = {
        "study_list": a3_study_list,
        "paper_list": a3_paper_list,
        "stage": "a3",
        "text": "New studies included in MA"
    }
    # then calculate the n_pmids and n_ctids
    prisma['a3']['n_pmids'] = len(prisma['a3']['paper_list'])
    prisma['a3']['n_ctids'] = len(prisma['a3']['study_list'])

    # u1 is those pmid with 
    prisma['u1'] = {
        "n_ctids": len(u1_study_list),
        "n_pmids": len(u1_paper_list),
        "study_list": u1_study_list,
        "paper_list": u1_paper_list,
        "stage": "u1",
        "text": "Updated studies in SR"
    }

    # calc u2 
    prisma['u2'] = {
        "n_ctids": len(u2_study_list),
        "n_pmids": len(u2_paper_list),
        "study_list": u2_study_list,
        "paper_list": u2_paper_list,
        "stage": "u2",
        "text": "Updated studies in MA"
    }

    # calc f3n
    # f3n_study_list = [ i for i in prisma['f1']['study_list'] if i not in prisma['f3']['study_list'] ]
    # f3n_paper_list = [ i for i in prisma['f1']['paper_list'] if i not in prisma['f3']['paper_list'] ]
    # prisma['f3n'] = {
    #     "n_ctids": len(f3n_study_list),
    #     "n_pmids": len(f3n_paper_list),
    #     "study_list": f3n_study_list,
    #     "paper_list": f3n_paper_list,
    #     "stage": "f3n",
    #     "text": "Studies not in MA"
    # }
    # get a simple f3n
    prisma['f3n'] = {
        "n_ctids": 0,
        "n_pmids": prisma['f1']['n_pmids'] - prisma['f3']['n_pmids'],
        "study_list": [],
        "paper_list": [],
        "stage": "f3n",
        "text": "Studies not in MA"
    }

    # build final ret
    ret = {
        'prisma': prisma,
        "paper_dict": living_prisma['paper_dict'],
        "study_dict": living_prisma['study_dict'],
        "monthly_prisma": living_prisma['monthly_stat'],
    }
    return ret


def get_prisma_by_cq(project_id, cq_abbr="default", do_include_papers=True):
    '''
    Get the PRISMA numbers from database
    '''
    project = dora.get_project(project_id)

    if project is None:
        return None

    # project_id = project.project_id

    # get the living prisma from database
    stat, monthly_stat = get_stat_aef(project_id)

    # get the paper information from database
    # the paper dict is PMID based
    paper_dict = {}

    # the study dict is NCT based
    study_dict = {}

    # update the e3 reasons
    papers = dora.get_papers_by_stage(
        project_id, 
        ss_state.SS_STAGE_EXCLUDED_BY_FULLTEXT
    )
    print('* found %s papers excluded by fulltext (by screener)' % (
        len(papers)
    ))

    stat['e3_by_reason'] = {}
    for paper in papers:
        
        reason = paper.ss_ex['reason']
        if reason not in stat['e3_by_reason']:
            stat['e3_by_reason'][reason] = {
                'n': 0
            }
        
        stat['e3_by_reason'][reason]['n'] += 1

        # update monthly stat
        dict_ = monthly_stat[paper.date_created.year][paper.date_created.month]
        if not dict_.get('e3_by_reason'):
            monthly_stat[paper.date_created.year][paper.date_created.month]['e3_by_reason'] = {}
            monthly_stat[paper.date_created.year][paper.date_created.month]['e3_by_reason'] = {
                reason : {'n': 0}
            }
        else:
             if reason not in monthly_stat[paper.date_created.year][paper.date_created.month]['e3_by_reason']:
                 monthly_stat[paper.date_created.year][paper.date_created.month]['e3_by_reason'] = {
                reason : {'n': 0}
            }
             else:
                existing_records = monthly_stat[paper.date_created.year][paper.date_created.month]['e3_by_reason'][reason]['n']
                monthly_stat[paper.date_created.year][paper.date_created.month]['e3_by_reason'][reason] = {'n': existing_records}

        # print("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
        # print(monthly_stat[paper.date_created.year][paper.date_created.month]['e3_by_reason'])
        monthly_stat[paper.date_created.year][paper.date_created.month]['e3_by_reason'][reason]['n'] += 1

    ##########################################################################
    # for the basic f1
    ##########################################################################
    # update the f1 decisions
    papers = dora.get_papers_by_stage(
        project_id,
        ss_state.SS_STAGE_INCLUDED_SR
    )
    print('* found %s papers included in SR in all CQs of project %s' % (
        len(papers),
        project.keystr
    ))

    # create a dict for later checking pid existence
    for p in papers:
        paper_dict[p.pid] = p

    # using this to check whether a study is used in SR
    f1_pids = []
    small_paper_dict = {}
    for paper in papers:
        rct_id = paper.get_rct_id()
        year_ = paper.date_created.year
        month_ = paper.date_created.month
        # decide the cq level decision
        if paper.ss_ex['ss_cq'].get(cq_abbr):
            if paper.ss_ex['ss_cq'][cq_abbr]['d'] == 'yes':
                # nothing, just add this study
                # if paper.ss_st in ['a10', 'a11', 'a12']:
                #     monthly_stat[year_][month_]['f1']['pids'].append(paper.pid)
                stat['f1']['pids'].append(paper.pid)

                # update the rct id if not exists
                if rct_id not in stat['f1']['rcts']:
                    # if paper.ss_st in ['a10', 'a11', 'a12']:
                    #     monthly_stat[year_][month_]['f1']['rcts'].append(rct_id)
                    stat['f1']['rcts'].append(rct_id)

                f1_pids.append(paper.pid)
            else:
                # this study is not included in this cq
                stat['f1']['n'] -= 1
                # if paper.ss_st in ['a10', 'a11', 'a12']:
                #     monthly_stat[year_][month_]['f1']['n'] -=1
                # this study should be counted in the excluded by full-text
                stat['e3']['n'] += 1

                if paper.ss_st in ['a10', 'a11', 'a12']:
                    monthly_stat[year_][month_]['e3']['n'] +=1

                # update the reason
                reason = paper.ss_ex['ss_cq'][cq_abbr]['r']
                if reason in stat['e3_by_reason']:
                    stat['e3_by_reason'][reason]['n'] += 1

                    # monthly_stat[year_][month_]['e3_by_reason'][reason] -=1
                else:
                    # this reason is NOT in existing reasons
                    if ss_state.SS_REASON_OTHER not in stat['e3_by_reason']:
                        stat['e3_by_reason'][ss_state.SS_REASON_OTHER] = {
                            'n': 0
                        }
                    stat['e3_by_reason'][ss_state.SS_REASON_OTHER]['n'] += 1

        # add this paper to the paper dict
        if do_include_papers:
            small_paper_dict[paper.pid] = {
                "authors": paper.authors,
                "ctid": rct_id,
                "date": paper.pub_date,
                "journal": paper.journal,
                "pid": paper.pid,
                "pid_type": paper.pid_type,
                "is_pmid": paper.is_pmid(),
                "title": paper.title,
            }

            # add this RCT to the study dict
            if rct_id not in study_dict:
                study_dict[rct_id] = {
                    "authors": paper.authors,
                    "ctid": rct_id,
                    "date": paper.pub_date,
                    "journal": paper.journal,
                    "pid": paper.pid,
                    "title": paper.title,

                    # the followings are for RCT
                    "study_id": rct_id,
                    "latest_pid": '',
                    "pids": [],
                }
        
            # then add this paper to the study list
            study_dict[rct_id]['latest_pid'] = paper.pid
            study_dict[rct_id]['pids'].append(paper.pid)
        
    papers_manaual = dora.get_papers_by_stage(
        project_id,
        ss_state.SS_STAGE_MANUAL
    )
    print('* found %s papers SS_STAGE_MANUAL in all CQs of project %s' % (
        len(papers),
        project.keystr
    ))

    for paper in papers_manaual:
        small_paper_dict[paper.pid] = {
            "authors": paper.authors,
            "ctid": rct_id,
            "date": paper.pub_date,
            "journal": paper.journal,
            "pid": paper.pid,
            "pid_type": paper.pid_type,
            "is_pmid": paper.is_pmid(),
            "title": paper.title,
        }

        # add this RCT to the study dict
        if rct_id not in study_dict:
            study_dict[rct_id] = {
                "authors": paper.authors,
                "ctid": rct_id,
                "date": paper.pub_date,
                "journal": paper.journal,
                "pid": paper.pid,
                "title": paper.title,

                # the followings are for RCT
                "study_id": rct_id,
                "latest_pid": '',
                "pids": [],
            }
    
        # then add this paper to the study list
        study_dict[rct_id]['latest_pid'] = paper.pid
        study_dict[rct_id]['pids'].append(paper.pid)

    print('* found %s papers %s trials included in SR (by screener, not the final number)' % (
        len(stat['f1']['pids']),
        len(stat['f1']['rcts']),
    ))
    print("* found %s papers excluded by full text (by screener + not selected)" % (
        stat['e3']['n']
    ))
    for r in stat['e3_by_reason']:
        n = stat['e3_by_reason'][r]['n']
        print('* - e3 by %s: %s' % (r, n))
    print('*' * 60)

    ##########################################################################
    # for the final f1
    ##########################################################################
    print('* start counting papers for final f1')

    # 2023-06-39: check the itable extraction
    itable = srv_extract.get_itable_by_project_id_and_cq_abbr(
        project_id, 
        cq_abbr
    )

    # this tmp will be used the final f1!
    # the tmp.pids are decided by itable and screener
    tmp = {
        'pids': [],
        'rcts': []
    }
    if itable is None:
        print('* not found itable for %s|%s' % (
            project.keystr,
            cq_abbr
        ))

    else:
        # Muneeb Its is becuase we are prioritizing the xls uploaded file 
        # 2023-06-20: fix data
        # itable = dora.attach_extract_data(itable)
        print('* found the itable for %s|%s' % (
            project.keystr,
            cq_abbr
        ))

        for pid in itable.data:
            # Commenting it for testing purpsoe 
            if pid not in stat['f1']['pids']:
                # 2024-04-14: what???
                # this may happen when importing xls to system (just maybe)
                # and it's also possible that paper X is excluded in screener,
                # but xls file includes paper X. 
                # then, still need to figure out what to do with it.
                continue

            # get the nct from paper_dict
            rct_id = paper_dict[pid].get_rct_id()
            d = itable.data[pid]

            if d['is_selected']:
                # which means this paper is selected in SR
                # that's the most important decision
                if pid in stat['f1']['pids']:
                    # ok, this is also included
                    tmp['pids'].append(pid)
                else:
                    # what??? this papaer is in itable but not included in SR
                    print('* CONFLICT %s paper in iTable but not included, maybe removed?')
                    continue

                if rct_id not in tmp['rcts']:
                    tmp['rcts'].append(rct_id)
                else:
                    pass
            else:
                pass
        # update the stat f1 with itable result
        # updated_list = list(itable.data.keys()) + tmp['pids']
        # updated_list = list(set(updated_list))
        # tmp['pids'] = updated_list
        tmp['n'] = len(tmp['pids'])
        tmp['text'] = stat['f1']['text']
        stat['f1'] = tmp

        print('* updated stat.f1 (%s papers, %s trials) with iTable data' % (
            len(stat['f1']['pids']),
            len(stat['f1']['rcts']),
        ))

    print('* found %s papers %s trials included in iTable for SR' % (
        len(stat['f1']['pids']),
        len(stat['f1']['rcts']),
    )) 
    print('*' * 60)

    ##########################################################################
    # for the statistics of initial
    ##########################################################################
    print('* start counting papers for initial search')

    # e3i_by_reason is for inital search stats
    e3i_by_reason = {}
    papers_e3i = dora.get_papers_by_stage(
        project_id,
        ss_state.SS_STAGE_EXCLUDED_BY_FULLTEXT_INITIAL
    )

    for paper in papers_e3i:
        reason = paper.ss_ex['reason']
        if reason not in e3i_by_reason:
            e3i_by_reason[reason] = {
                'n': 0
            }
        
        e3i_by_reason[reason]['n'] += 1

    print('* found %s papers excluded by fulltext in initial (by screener)' % (
        len(papers_e3i)
    ))


    papers2 = dora.get_papers_by_stage(
        project_id,
        ss_state.SS_STAGE_INCLUDED_SR_INITIAL
    )
    print('* found %s papers included in INITAL SR in all CQs of project %s' % (
        len(papers2),
        project.keystr
    ))

    # rename to avoid conflicts
    paper_dict2 = {}
    study_dict2 = {}
    # create a dict for later checking pid existence
    for p in papers2:
        paper_dict2[p.pid] = p

    # using this to check whether a study is used in SR
    f1_pids = []
    small_paper_dict_inital = {}

    for paper in papers2:
        rct_id = paper.get_rct_id()
        year_ = paper.date_created.year
        month_ = paper.date_created.month

        # decide the cq level decision
        if paper.ss_ex['ss_cq'].get(cq_abbr):
            if paper.ss_ex['ss_cq'][cq_abbr]['d'] == 'yes':
                # nothing, just add this study
                # monthly_stat[year_][month_]['f2']['pids'].append(paper.pid)
                stat['f2']['pids'].append(paper.pid)

                # update the rct id if not exists
                if rct_id not in stat['f2']['rcts']:
                    # monthly_stat[year_][month_]['f2']['rcts'].append(rct_id)
                    stat['f2']['rcts'].append(rct_id)

                f1_pids.append(paper.pid)
            else:
                # this study is not included in this cq
                stat['f2']['n'] -= 1

                # update e3i
                reason = paper.ss_ex['ss_cq'][cq_abbr]['r']
                if reason in e3i_by_reason:
                    e3i_by_reason[reason]['n'] += 1

                else:
                    # this reason is NOT in existing reasons
                    if ss_state.SS_REASON_OTHER not in e3i_by_reason:
                        e3i_by_reason[ss_state.SS_REASON_OTHER] = {
                            'n': 0
                        }
                    e3i_by_reason[ss_state.SS_REASON_OTHER]['n'] += 1

        # add this paper to the paper dict
        if do_include_papers:
            small_paper_dict_inital[paper.pid] = {
                "authors": paper.authors,
                "ctid": rct_id,
                "date": paper.pub_date,
                "journal": paper.journal,
                "pid": paper.pid,
                "pid_type": paper.pid_type,
                "is_pmid": paper.is_pmid(),
                "title": paper.title,
            }

            # add this RCT to the study dict
            if rct_id not in study_dict2:
                study_dict2[rct_id] = {
                    "authors": paper.authors,
                    "ctid": rct_id,
                    "date": paper.pub_date,
                    "journal": paper.journal,
                    "pid": paper.pid,
                    "title": paper.title,

                    # the followings are for RCT
                    "study_id": rct_id,
                    "latest_pid": '',
                    "pids": [],
                }
        
            # then add this paper to the study list
            study_dict2[rct_id]['latest_pid'] = paper.pid
            study_dict2[rct_id]['pids'].append(paper.pid)

    print('* found %s papers %s trials included in INITIAL SR (f2, by screener, not the final number)' % (
        len(stat['f2']['pids']),
        len(stat['f2']['rcts']),
    ))

    # 2024-04-14: itable is already got
    # itable = srv_extract.get_itable_by_project_id_and_cq_abbr(
    #     project_id, 
    #     cq_abbr
    # )

    # this is the final f2
    tmp = {
        'pids': [],
        'rcts': []
    }
    if itable is None:
        print('* not found itable for %s|%s' % (
            project.keystr,
            cq_abbr
        ))

    else:
        # 2024-04-14: itable is already updated
        # itable = dora.attach_extract_data(itable)
        # print('* found the itable for %s|%s' % (
            # project.keystr,
            # cq_abbr
        # ))

        for pid in itable.data:
            if pid not in stat['f2']['pids']:
                # what????
                continue

            # get the nct
            rct_id = paper_dict2[pid].get_rct_id()
            d = itable.data[pid]

            if d['is_selected']:
                # which means this paper is selected in SR
                if pid in stat['f2']['pids']:
                    # ok, this is also included
                    tmp['pids'].append(pid)
                else:
                    # what??? this papaer is in itable but not included in SR
                    print('* CONFLICT %s paper in iTable but not included, maybe removed?')
                    continue

                if rct_id not in tmp['rcts']:
                    tmp['rcts'].append(rct_id)
                else:
                    pass
            else:
                pass
        # update the stat f1 with itable result
        tmp['n'] = len(tmp['pids'])
        tmp['text'] = stat['f2']['text']
        stat['f2'] = tmp

    print('* updated stat.f2 (%s papers, %s trials) with iTable data' % (
        len(stat['f2']['pids']),
        len(stat['f2']['rcts']),
    ))
    flag_is_f2_a_subset_of_f1 = set(stat['f2']['pids']).issubset(stat['f1']['pids'])
    print('* Is f2 a subset of f1? %s' % (flag_is_f2_a_subset_of_f1))

    print("* found papers excluded by full text in initial (by screener + not selected)")
    for r in e3i_by_reason:
        n = e3i_by_reason[r]['n']
        print('* - e3i by %s: %s' % (r, n))

    # bind to the final
    stat['e3i_by_reason'] = e3i_by_reason

    print("*" * 60)

    ##########################################################################
    # update the f3 decisions
    ##########################################################################
    print('* start counting papers for final f3')
    ocs = dora.get_extracts_by_keystr_and_cq(
        project.keystr,
        cq_abbr
    )
    print('* found %s outcomes in %s|%s' % (
        len(ocs),
        project.keystr,
        cq_abbr
    ))

    # check each outcome
    missing_itable_f3_pids = []
    for oc_idx, oc in enumerate(ocs):
        # 2022-01-19: fix the number issue
        # the itable should be excluded from the counting
        if oc.oc_type == 'itable':
            continue

        # month_ = oc.date_created.month
        # year_ = oc.date_created.year

        # print('********** check outcome %s/%s %s' % (
        #     (oc_idx + 1),
        #     len(ocs),
        #     oc.get_repr_str()
        # ))

        # 2023-06-30: fix the data
        oc = dora.attach_extract_data(oc)

        # check papaer extracted in this outcome
        cnt_selected = 0
        for pid in oc.data:
            # 2022-01-17 fix the MA>SR issue
            # need to check whether this pid exists in papers
            if pid not in small_paper_dict:
                # which means this extraction is not linked with a paper,
                # maybe due to import issue or pid update.
                # so, just skip this
                continue

            # 2024-04-14 fix not-included in SR issue
            # a paper is possible selected into an outcome but not in itable
            # in this case, need to remove this paper from f3
            if pid not in stat['f1']['pids']:
                # which means this paper is not selected in the itable
                if pid not in missing_itable_f3_pids:
                    missing_itable_f3_pids.append(pid)
                continue

            # get the data
            p = oc.data[pid]

            if p['is_selected']:
                cnt_selected += 1
                if pid in stat['f3']['pids']:
                    # this pid has been counted
                    pass
                else:
                    stat['f3']['pids'].append(pid)
                    stat['f3']['n'] += 1
                    paper = dora.get_paper_by_pid(
                        pid
                    )

                    year_ = paper.date_created.year
                    month_ = paper.date_created.month
                    # Monthly data update for prisma 16 Jan 2024 update  
                    
                    monthly_stat[year_][month_]['f3']['n'] +=1
                    monthly_stat[year_][month_]['f3']['pids'].append(pid)

                    # print("(((((((((((((((((((((((((((((((((((")
                    # print(  monthly_stat[year_][month_]['f3']['n'])

                    # check the ctid
                    if pid in paper_dict:
                        rct_id = paper_dict[pid].get_rct_id()

                        if rct_id not in stat['f3']['rcts']:
                            monthly_stat[year_][month_]['f3']['rcts'].append(rct_id)
                            stat['f3']['rcts'].append(rct_id)
                    else:
                        # what???
                        # if this pid not in paper dict
                        # which means the rct info is missing
                        print('* ERROR missing %s in the included paper dict' % (
                            pid
                        ))
                        rct_id = None
                    
                    # print('* found %s papers %s trials included in MA, added %s|%s' % (
                    #     len(stat['f3']['pids']),
                    #     len(stat['f3']['rcts']),
                    #     rct_id,
                    #     pid,
                    # ))

            else:
                # this paper is extracted but not selected yet.
                pass
        # print('* found %s selected papers' % (
        #     cnt_selected
        # ))

    print('* found %s papers %s trials included in MA (f3, final number)' % (
        len(stat['f3']['pids']),
        len(stat['f3']['rcts']),
    ))
    flag_is_f3_a_subset_of_f1 = set(stat['f3']['pids']).issubset(stat['f1']['pids'])
    print('* Is f3 a subset of f1? %s' % (flag_is_f3_a_subset_of_f1))
    print("* f3.difference(f1): %s" % (
        set(stat['f3']['pids']).difference(stat['f1']['pids'])
    ))

    print('* found %s missing itable extraction papers in f3' % (
        len(missing_itable_f3_pids)
    ))
    if len(missing_itable_f3_pids) > 0:
        [ print('! missing extraction/selection in itable: %s' % pid) for pid in missing_itable_f3_pids ]

    print('*' * 60)

    ##########################################################################
    # update the monthly statistics based on final f1, f2, and f3
    ##########################################################################
    print('* start counting living updates based on final f1, f2, f3')

    living_f1 = list(set(stat['f1']['pids']).difference(stat['f2']['pids']))
    print('* found %s difference between f1 and f2: (which are living f1)' % (
        len(living_f1)
    ))
    [ print('* living f1 %s' % _pid) for _pid in living_f1 ]

    # living papers are those 
    living_papers = dora.get_living_papers_based_on_pids(project_id, living_f1)

    # reset the f1 and f3
    for _year in monthly_stat:
        for _month in monthly_stat[_year]:
            monthly_stat[_year][_month]['f1']['pids'] = []
            monthly_stat[_year][_month]['f1']['rcts'] = []
            monthly_stat[_year][_month]['f1']['n'] = 0

            monthly_stat[_year][_month]['f3']['pids'] = []
            monthly_stat[_year][_month]['f3']['rcts'] = []
            monthly_stat[_year][_month]['f3']['n'] = 0

    # update stats
    for paper in living_papers:
        _year = paper.date_created.year
        _month = paper.date_created.month
        rct_id = paper.get_rct_id()
        
        # update living f1
        monthly_stat[_year][_month]['f1']['pids'].append(paper.pid)
        if rct_id not in monthly_stat[_year][_month]['f1']['rcts']: 
             monthly_stat[_year][_month]['f1']['rcts'].append(rct_id)
        monthly_stat[_year][_month]['f1']['n'] = len(
            monthly_stat[_year][_month]['f1']['pids']
        )
        
        # update living f3
        if paper.pid in stat['f3']['pids']:
            monthly_stat[_year][_month]['f3']['pids'].append(paper.pid)
            if rct_id not in monthly_stat[_year][_month]['f3']['rcts']: 
                monthly_stat[_year][_month]['f3']['rcts'].append(rct_id)
            monthly_stat[_year][_month]['f3']['n'] = len(
                monthly_stat[_year][_month]['f3']['pids']
            )

        print("* update %s/%s living f1:%s f3:%s, by paper %s" % (
            _year, _month,
            monthly_stat[_year][_month]['f1']['n'],
            monthly_stat[_year][_month]['f3']['n'],
            paper.pid
        ))

    #######################################################
    # add other stages
    #######################################################
    # the s0
    stat['s0'] = {
        'n': stat['a1']['n'] + stat['a2x']['n'],
        'text': 'Search',
        'pids': [],
        'rcts': []
    }
    # use the given s0 as the number
    if 'prisma' in project.settings and 's0' in project.settings['prisma']:
        stat['s0']['n'] = project.settings['prisma']['s0']['n']

    # use the cq-specific s0 as the number
    if 'prisma' in project.settings and \
        cq_abbr in project.settings['prisma'] and \
        's0' in project.settings['prisma'][cq_abbr]:
        stat['s0']['n'] = project.settings['prisma'][cq_abbr]['s0']['n_pmids']

    stat['e1'] = {
        'n': stat['s0']['n'] - stat['a1']['n'],
        'text': 'Excluded by duplicates',
        'pids': []
    }
    stat['all'] = {
        'n': stat['a1']['n'] + 
             stat['a2x']['n'],
        'text': 'Records for screening',
        'pids': []
    }
    stat['uns'] = {
        'n': stat['ax_na_na']['n'],
        'text': 'Unscreened',
        'pids': []
    }
    stat['fte'] = {
        'n': stat['a1']['n'] + 
                 stat['a2x']['n'] -
                 stat['e2']['n'] - 
                 stat['e22']['n'] - 
                 stat['uns']['n'],
        'text': 'Eligible for full-text review',
        'pids': []
    }
    stat['unr'] = {
        'n': stat['ax_p2_na']['n'],
        'text': 'Reviewing full text',
        'pids': []
    }
    stat['f3n'] = {
        'n': stat['f1']['n'] -
                 stat['f3']['n'],
        'text': 'Not in MA',
        'pids': []
    }

    # remove the stages
    del stat['stages']
    
    # finally, we present this object
    ret = {
        "stat": stat,
        "paper_dict": small_paper_dict,
        "monthly_stat": monthly_stat,
        "study_dict": study_dict,
    }

    return ret


def get_stat_aef(project_id):
    '''
    Get the statistics of the project for the PRISMA
    Including:

    - a auto + import
    - e excluded
    - f final

    '''
    stages = [
        { "stage": "a1",  "text": "Records identified through automatic update" },
        { "stage": "a2x",  "text": "Records identified through batch import" },
        { "stage": "a3x",  "text": "Records identified through Manual import" },

        { "stage": "ax_na_na",  "text": "Unscreened records" },
        { "stage": "ax_p2_na",  "text": "Full-text reviewing" },

        { "stage": "e2",  "text": "Excluded by title" },
        { "stage": "e22", "text": "Excluded by abstract review" },
        { "stage": "e3",  "text": "Excluded by full-text review" },

        { "stage": "f1", "text": "Final number in qualitative synthesis (systematic review)" },
         { "stage": "f2", "text": "Final number in qualitative synthesis (systematic review) Initial" },
        { "stage": "f3", "text": "Final number in quantitative synthesis (meta-analysis)" }
    ]



    sql_monthly = """
    SELECT 
        YEAR(date_created) AS year,
        MONTH(date_created) AS month,
        
        count(case when ss_st in ('a10', 'a11', 'a12') then paper_id else null end) as a1,
        group_concat(case when ss_st in ('a10', 'a11', 'a12') then pid else null end) as a1_pids,
        count(case when ss_st in ('a21', 'a22', 'a23') then paper_id else null end) as a2x,
        count(case when ss_st in ('a24') then paper_id else null end) as a3x,


        count(case when ss_pr = 'na' and ss_rs = 'na' then paper_id else null end) as ax_na_na,
        count(case when ss_pr = 'p20' and ss_rs = 'na' then paper_id else null end) as ax_p2_na,
            
        count(case when ss_rs = 'e2' then paper_id else null end) as e2,
        count(case when ss_rs = 'e22' then paper_id else null end) as e22,
        count(case when ss_rs = 'e3' then paper_id else null end) as e3,
            
        count(case when ss_rs in ('f1', 'f3') then paper_id else null end) as f1,
        0 as f3,
        0 as f2
    FROM 
        papers
    WHERE 
        project_id = '{project_id}'  AND ss_st in ('a10', 'a11', 'a12')
        AND is_deleted = 'no'
    GROUP BY 
        YEAR(date_created), MONTH(date_created)
    Order by year, month
    """.format(project_id=project_id)
    monthly_sql_record = db.session.execute(sql_monthly).fetchall()




    sql = """
    select project_id,
        
        count(case when ss_st in ('a10', 'a11', 'a12') then paper_id else null end) as a1,
        count(case when ss_st in ('a21', 'a22', 'a23') then paper_id else null end) as a2x,
         count(case when ss_st in ('a24') then paper_id else null end) as a3x,

        count(case when ss_pr = 'na' and ss_rs = 'na' then paper_id else null end) as ax_na_na,
        count(case when ss_pr = 'p20' and ss_rs = 'na' then paper_id else null end) as ax_p2_na,
        
        count(case when ss_rs = 'e2' then paper_id else null end) as e2,
        count(case when ss_rs = 'e22' then paper_id else null end) as e22,
        count(case when ss_rs = 'e3' then paper_id else null end) as e3,
        
        count(case when ss_rs in ('f1', 'f3') then paper_id else null end) as f1,
        0 as f3,
        0 as f2
        

    from papers
    where project_id = '{project_id}'
        and is_deleted = 'no'
    group by project_id
    """.format(project_id=project_id)


    sql_manual_import = """
    SELECT  pid FROM papers where project_id='{project_id}' and  ss_st='a24';
    """.format(project_id=project_id)
    r = db.session.execute(sql).fetchone()
    print(r)

    r_manual = db.session.execute(sql_manual_import).fetchall()
    print(r_manual)
    manual_articles = []
    
    for record in r_manual:
            manual_articles.append(record[0])


    if r is None:
        stat = {
            'stages': stages
        }
        for k in stages:
            stat[k['stage']] = {
                'n': 0,
                'text': k['text'],
                'pids': [],
                'rcts': []
            }

        return stat

    # put the values in prisma dict
    stat = {
        'stages': stages
    }

    # attention, f3 is always zero
    # because the value couldn't be decided by the screener
   
    for k in stages:
        stat[k['stage']] = {
            'n': r[k['stage']],
            'text': k['text'],
            'pids': [],
            'rcts': []
        }
        if (k['stage']=="a3x"):
             stat[k['stage']]['pids'] = manual_articles
             stat[k['stage']]['n_pids'] = len(manual_articles)
             stat[k['stage']]['n'] = len(manual_articles)

        
    monthly_stat = [
        { "stage": "a1",  "text": "Records identified through automatic update" },
        { "stage": "a2x",  "text": "Records identified through batch import" },
        { "stage": "a3x",  "text": "Records identified through Manual import" },

        { "stage": "ax_na_na",  "text": "Unscreened records" },
        { "stage": "ax_p2_na",  "text": "Full-text reviewing" },

        { "stage": "e2",  "text": "Excluded by title" },
        { "stage": "e22", "text": "Excluded by abstract review" },
        { "stage": "e3",  "text": "Excluded by full-text review" },

        { "stage": "f1", "text": "Final number in qualitative synthesis (systematic review)" },
        { "stage": "f3", "text": "Final number in quantitative synthesis (meta-analysis)" },

        {"stage": "b2", "text": "Records after removing duplicates" },
        {"stage": "b3", "text": "Full-text articles assessed for eligibility" },
        {"stage": "b5", "text": "Records identified through other sources" },
        {"stage": "e21", "text": "Excluded by title" },
    ]

    monthly_stat_update = {
        'stages': monthly_stat
    }
    monthly_records ={}

    for record in monthly_sql_record:
        record = dict(record)
        
        for k in monthly_stat:
            monthly_stat_update[k['stage']] = {
                'n': record.get(k['stage']) if record.get(k['stage']) else 0 ,
                'text': k['text'],
                'pids': [],
                'rcts': []
            }
        
        # for a1, put all pids of a1 in monthly_stat
        monthly_stat_update['a1']['pids'] = record['a1_pids'].split(',')

        if monthly_records.get(record['year']):
            if monthly_records.get(record['year']).get(record['month']):
                monthly_records[record['year']][record['month']] = monthly_stat_update
            else:
                monthly_records[record['year']][record['month']] = monthly_stat_update

        else:
           monthly_records[record['year']] ={}
           monthly_records[record['year']][record['month']] = monthly_stat_update

        monthly_stat = [

            { "stage": "a1",  "text": "Records identified through automatic update" },
            { "stage": "a2x",  "text": "Records identified through batch import" },
            { "stage": "a3x",  "text": "Records identified through Manual import" },

            { "stage": "ax_na_na",  "text": "Unscreened records" },
            { "stage": "ax_p2_na",  "text": "Full-text reviewing" },

            { "stage": "e2",  "text": "Excluded by title" },
            { "stage": "e22", "text": "Excluded by abstract review" },
            { "stage": "e3",  "text": "Excluded by full-text review" },

            { "stage": "f1", "text": "Final number in qualitative synthesis (systematic review)" },
            { "stage": "f3", "text": "Final number in quantitative synthesis (meta-analysis)" },

            {"stage": "b2", "text": "Records after removing duplicates" },
            {"stage": "b3", "text": "Full-text articles assessed for eligibility" },
            {"stage": "b5", "text": "Records identified through other sources" },
            {"stage": "e21", "text": "Excluded by title" },
        ]
        
        monthly_stat_update = {
            'stages': monthly_stat
        }
 
    return stat , monthly_records
    

#####################################################################
# Deprecated functions
#####################################################################
def get_prisma_from_db(prj, cq_abbr="default"):
    '''
    Deprecated
    Get PRISMA JSON data from database
    '''
    project = dora.get_project_by_keystr(prj)
    project_id = project.project_id

    # get the fixed number from project settings
    # this depends on whether this project 
    past_prisma = {}

    # get the living prisma from database
    prisma, stat = get_prisma_bef(project_id)

    # get the paper information from database
    # the paper dict is PMID based
    paper_dict = {}

    # the study dict is NCT based
    study_dict = {}

    # fill the pmid
    papers = dora.get_papers_by_stage(
        project.project_id,
        ss_state.SS_STAGE_INCLUDED_SR
    )
    for paper in papers:
        rct_id = paper.get_rct_id()

        # add this paper to the paper dict
        paper_dict[paper.pid] = {
            "authors": paper.authors,
            "ctid": rct_id,
            "date": paper.pub_date,
            "journal": paper.journal,
            "pmid": paper.pid,
            "pid_type": paper.pid_type,
            "title": paper.title,
        }

        # 2021-11-15: fix empty rct_id
        if rct_id == '': continue

        # add this RCT to the study dict
        if rct_id not in study_dict:
            study_dict[rct_id] = {
                "authors": paper.authors,
                "ctid": rct_id,
                "date": paper.pub_date,
                "journal": paper.journal,
                "pmid": paper.pid,
                "title": paper.title,

                # the followings are for RCT
                "study_id": rct_id,
                "latest_pmid": '',
                "pmids": [],
            }
        
        # then add this paper to the study list
        study_dict[rct_id]['latest_pmid'] = paper.pid
        study_dict[rct_id]['pmids'].append(paper.pid)

    # finally, we present this object
    ret = {
        "prisma": prisma,
        "stat": stat,
        "paper_dict": paper_dict,
        "study_dict": study_dict,
    }

    return ret


def get_prisma_from_xls(prj):
    '''
    Deprecated
    Get PRISMA JSON data from Excel file
    '''
    import numpy as np

    fn = 'PRISMA_DATA.xlsx'
    full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, fn)

    # hold all the outcomes
    fn_json = 'PRISMA.json'
    full_fn_json = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, fn_json)
    
    # there are two tables for this 
    tab_name_prisma = 'PRISMA'
    tab_name_studies = 'studies'

    # load the xls
    xls = pd.ExcelFile(full_fn)

    # read the prisma, we need to read this tab two times
    dft = xls.parse(tab_name_prisma, nrows=4)

    # first, get the basic info
    prisma = {}
    stage_list = dft.columns.tolist()
    for col in dft.columns:
        # col should be b1, b2, b3 ... f1, f2
        stage = col.strip()
        text = dft.loc[0, col]
        n_pmids = dft.loc[1, col]
        if np.isnan(n_pmids):
            n_pmids = None
        detail = dft.loc[2, col]
        if type(detail) != str:
            detail = None
        
        # create the basic 
        prisma[stage] = {
            'stage': stage,
            'n_pmids': n_pmids,
            'n_ctids': 0,
            'text': text,
            'detail': detail,
            'study_list': [],
            'paper_list': []
        }

    # the study dict is NCT based
    study_dict = {}
    # the paper dict is PMID based
    paper_dict = {}
    # then, get the nct and pmids, skip the text, number and detail rows
    dft = xls.parse(tab_name_prisma, skiprows=[1,2,3])
    for col in dft.columns:
        stage = col
        study_ids = dft[col][~dft[col].isna()].tolist()
            
        # update the studies
        for study_id in study_ids:
            # the pmid is a number, but we need it as a string
            study_id = str(study_id)
            # tmp is ctid,PMID format, e.g., NCT12345678,321908734
            tmp = study_id.split(',')

            if len(tmp) == 1:
                # only pmid ???
                ctid = tmp[0]
                pmid = tmp[0]
            elif len(tmp) == 2:
                ctid = tmp[0].strip()
                pmid = tmp[1].strip()
            else:
                continue

            try:
                # some pid are saved as a float number????
                # like 27918762.0???
                pmid = '%s' % int(float(pmid))
            except:
                pass
                
            # append this ctid to this stage
            if ctid not in prisma[stage]['study_list']:
                prisma[stage]['study_list'].append(ctid)

            # create a new in the study_dict for this nct
            if ctid not in study_dict:
                study_dict[ctid] = {
                    'ctid': ctid, 'latest_pmid': None, 'pmids': [],
                }

            # append this pmid to this stage
            if pmid not in prisma[stage]['paper_list']:
                prisma[stage]['paper_list'].append(pmid)
            
            # update the pmid information of this clinical trial
            study_dict[ctid]['latest_pmid'] = pmid
            study_dict[ctid]['pmids'].append(pmid)
            
            # create a new item in paper_dict for this pmid
            if pmid not in paper_dict:
                paper_dict[pmid] = {
                    'ctid': ctid, 'pmid': pmid
                }
            else:
                # what???
                pass
        
        if prisma[stage]['n_pmids'] is None:
            prisma[stage]['n_pmids'] = len(prisma[stage]['paper_list'])

        # update the number of ncts
        prisma[stage]['n_ctids'] = len(prisma[stage]['study_list'])


    # second, read more studies from second tab
    try:
        # the second tab is optional
        cols = ['study_id', 'title', 'date', 'journal', 'authors']
        dft = xls.parse(tab_name_studies, usecols='A:E', names=cols)
        for idx, row in dft.iterrows():
            study_id = ('%s'%row['study_id']).strip()
            is_ctid = False
            if study_id.startswith('NCT'):
                is_ctid = True
            else:
                # sometimes the value is weird ...
                try:
                    study_id = '%s' % int(float(study_id))
                except:
                    pass

            # update the study info
            if is_ctid:
                if study_id in study_dict:
                    for col in cols:
                        study_dict[study_id][col] = str(row[col])
                else:
                    pass
            else:
                if study_id in paper_dict:
                    for col in cols:
                        paper_dict[study_id][col] = str(row[col])
                else:
                    pass
    except Exception as err:
        # nothing, just ignore this error
        print(err)

    # reat the studies
    ret = {
        "prisma": prisma,
        "study_dict": study_dict,
        "paper_dict": paper_dict
    }

    return ret


def get_prisma_bef(project_id):
    '''
    Deprecated
    Get the statistics for the PRISMA
    Including:

    - b: batch number
    - e: excluded
    - f: final number

    '''
    # get the basic stats
    stat = dora.get_screener_stat_by_project_id(project_id)

    # get the NCT number states
    papers = dora.get_papers(project_id)
    b1_study_list = []
    b4_study_list = []
    b5_study_list = []
    e1_study_list = []
    e2_study_list = []
    e3_study_list = []
    f1_study_list = []
    f2_study_list = []
    
    f1_paper_list = []
    f2_paper_list = []

    for paper in papers:
        rct_id = ''
        if 'rct_id' in paper.meta:
            rct_id = paper.meta['rct_id']
        
        # use the pid as rct id if it is missing
        if rct_id == '':
            rct_id = paper.pid

        stages = paper.get_ss_stages()
        # print(paper.ss_rs, stages)

        if ss_state.SS_STAGE_INCLUDED_SR in stages:
            f1_study_list.append(rct_id)
            f1_paper_list.append(paper.pid)

        if ss_state.SS_STAGE_INCLUDED_SRMA in stages:
            f2_study_list.append(rct_id)
            f2_paper_list.append(paper.pid)

    prisma = {
        'b1': {
            "n_ctids": len(b1_study_list),
            "n_pmids": stat[ss_state.SS_STAGE_ALL_OF_THEM],
        },
        'b2': {
            "n_ctids": 0,
            "n_pmids": 0,
        },
        'b3': {
            "n_ctids": 0,
            "n_pmids": 0,
        },
        'b4': {
            "n_ctids": len(b4_study_list),
            "n_pmids": stat[ss_state.SS_STAGE_DECIDED]
                - stat[ss_state.SS_STAGE_EXCLUDED_BY_FULLTEXT],
        },
        'b5': {
            "n_ctids": len(b5_study_list),
            "n_pmids": stat[ss_state.SS_STAGE_INCLUDED_SR]
                + stat[ss_state.SS_STAGE_EXCLUDED_BY_ABSTRACT]
        },

        'e1': {
            "n_ctids": len(e1_study_list),
            "n_pmids": stat[ss_state.SS_STAGE_EXCLUDED_BY_TITLE],
        },
        'e2': {
            "n_ctids": len(e2_study_list),
            "n_pmids": stat[ss_state.SS_STAGE_EXCLUDED_BY_ABSTRACT],
        },
        'e3': {
            "n_ctids": len(e3_study_list),
            "n_pmids": stat[ss_state.SS_STAGE_EXCLUDED_BY_FULLTEXT],
        },

        'f1': {
            "n_ctids": len(f1_study_list),
            "n_pmids": stat[ss_state.SS_STAGE_INCLUDED_SR],
            "study_list": f1_study_list,
            "paper_list": f1_paper_list
        },
        'f2': {
            "n_ctids": len(f2_study_list),
            "n_pmids": stat[ss_state.SS_STAGE_INCLUDED_SRMA],
            "study_list": f2_study_list,
            "paper_list": f2_paper_list
        }
    }

    return prisma, stat


def get_prisma_abeuf(project_id):
    '''
    Deprecated
    Get the statistics of the project for the PRISMA
    Including:

    - a auto update
    - b batch number
    - e excluded
    - u updated
    - f final

    '''
    stages = [
        { "stage": "b1", "text": "Records retrieved from database search" },
        { "stage": "b2", "text": "Records identified through other sources" },
        { "stage": "b3", "text": "Records after removing dupicates" },
        { "stage": "b4", "text": "Records initialized screened" },
        { "stage": "b5", "text": "Full-text articles assessed for eligibility" },
        { "stage": "b6", "text": "Studies included in systematic review" },
        { "stage": "b7", "text": "Studies included in meta-analysis" },

        { "stage": "e1", "text": "Excluded by title and abstract review" },
        { "stage": "e2", "text": "Excluded by full text review" },
        { "stage": "e3", "text": "Studies not included in meta-analysis" },

        { "stage": "a1", "text": "Records identified through automated search" },
        { "stage": "a1_na_na", "text": "Unscreened records" },
        { "stage": "a1_p2_na", "text": "Records need to check full text" },
        { "stage": "a2", "text": "New studies included in systematic review" },
        { "stage": "a3", "text": "New studies included in meta-analysis" },
        
        { "stage": "u1", "text": "Updated studies in SR" },
        { "stage": "u2", "text": "Updated studies in MA" },

        { "stage": "f1", "text": "Final number in qualitative synthesis (systematic review)" },
        { "stage": "f2", "text": "Final number in quantitative synthesis (meta-analysis)" }
    ]
    sql = """
    select project_id,
        count(*) as cnt,
        count(case when ss_st = 'b10' then paper_id else null end) as b1,
        count(case when ss_st = 'b12' then paper_id else null end) as b2,
        count(case when ss_st in ('b10', 'b12') and ss_rs != 'e1' then paper_id else null end) as b3,
        count(case when ss_st in ('b10', 'b12') and ss_rs != 'e1' then paper_id else null end) as b4,
        count(case when ss_st in ('b10', 'b12') and ss_rs != 'e1' and ss_rs != 'e2' then paper_id else null end) as b5,
        count(case when ss_st in ('b10', 'b12') and ss_rs in ('f1', 'f3') then paper_id else null end) as b6,
        count(case when ss_st in ('b10', 'b12') and ss_rs = 'f3' then paper_id else null end) as b7,
        
        count(case when ss_rs = 'e2' then paper_id else null end) as e1,
        count(case when ss_rs = 'e3' then paper_id else null end) as e2,
        count(case when ss_rs = 'f1' then paper_id else null end) as e3,

        count(case when ss_st in ('a10', 'a11', 'a12') then paper_id else null end) as a1,
        count(case when ss_st in ('a10', 'a11', 'a12') and ss_pr = 'na' and ss_rs = 'na' then paper_id else null end) as a1_na_na,
        count(case when ss_st in ('a10', 'a11', 'a12') and ss_pr = 'p20' and ss_rs = 'na' then paper_id else null end) as a1_p2_na,
        count(case when ss_st in ('a10', 'a11', 'a12') and ss_rs in ('f1', 'f3') then paper_id else null end) as a2,
        count(case when ss_st in ('a10', 'a11', 'a12') and ss_rs = 'f3' then paper_id else null end) as a3,
        
        count(case when ss_st in ('a10', 'a11', 'a12') and ss_pr = 'p40' and ss_rs in ('f1', 'f3') then paper_id else null end) as u1,
        count(case when ss_st in ('a10', 'a11', 'a12') and ss_pr = 'p40' and ss_rs = 'f3' then paper_id else null end) as u2,
        
        count(case when ss_rs in ('f1', 'f3') then paper_id else null end) as f1,
        count(case when ss_rs = 'f3' then paper_id else null end) as f2

    from papers
    where project_id = '{project_id}'
        and is_deleted = 'no'
    group by project_id
    """.format(project_id=project_id)
    r = db.session.execute(sql).fetchone()

    if r is None:
        prisma = {
            'stages': stages
        }
        for k in stages:
            prisma[k['stage']] = 0
        return prisma

    # put the values in prisma dict
    prisma = {
        'stages': stages
    }
    for k in r.keys():
        prisma[k] = r[k]

    return prisma
    

def _get_prisma_updated(b_stage, f_stage, paper_dict):
    '''
    Get the study and paper list of updated records
    '''
    new_paper_list = [ i for i in f_stage['paper_list'] if i not in b_stage['paper_list'] ]
    a_study_list = [] # for pure new study
    a_paper_list = [] # for pure new study's paper
    u_study_list = [] # for follow-up study
    u_paper_list = [] # for follow-up study's paper
    for pid in new_paper_list:
        # get this paper from the paper dict
        # since this pid is from the same source, it must be in the paper dict
        # but it is possible that due to encoding or other issue
        # the pid is not there
        if pid not in paper_dict:
            print("* NO PID [%s] for PRISMA" % (pid))
            continue

        # get this paper
        paper = paper_dict[pid]

        # get the nct/rct/ctid of this paper
        ctid = paper['ctid']
        if ctid in b_stage['study_list']:
            # which means this new paper is a follow up study
            u_paper_list.append(pid)

            # now, put this ctid in the list if not yet
            # we must do this checking because the Clinical Trail may contain more
            if ctid in u_study_list: pass
            else: u_study_list.append(ctid)
        
        else:
            # which means this is a pure new study
            a_paper_list.append(pid)

            # and put the ctid
            if ctid in a_study_list: pass
            else: a_study_list.append(ctid)

    return a_study_list, a_paper_list, u_study_list, u_paper_list


def _get_rct_ids_from_papers_by_pids(papers, pids):
    '''
    Get RCT IDs of specific pids from a list of papers
    '''
    rct_ids = []
    for p in papers:
        if p.pid in pids:
            rct_ids.append(p.get_rct_id())
    
    return rct_ids