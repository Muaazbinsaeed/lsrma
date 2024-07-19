from enum import unique
import os
import time
import math

import numpy as np
from collections import OrderedDict
import pandas as pd
from tqdm import tqdm 

from sqlalchemy import and_, or_, not_
from sqlalchemy.orm.attributes import flag_modified

from lnma import settings
from lnma import util
from lnma import dora
from lnma import ss_state
from lnma import srv_paper
from lnma.models import *

from lnma import db


def validate_or_update_piece_by_outcome(
    piece, 
    extract
):
    '''
    Check whether a piece data structure meet the definition of an outcome

    If yes, it's ok. Otherwise, update this piece.
    '''
    flag_updated = False
    for subg_idx, subg in enumerate(extract.meta['sub_groups']):
        # the group key in extracted piece
        gx = 'g%s' % subg_idx

        for arm in [piece.data['attrs']['main']] + piece.data['attrs']['other']:
            # check whether this group exists
            # g0, g1, etc.
            if gx in arm:
                # ok, this arm exists
                pass
            else:
                # oh, no, this group doesn't exist
                # let's add this group with empty information
                # by filling the group with information
                arm = util.fill_extract_data_arm(
                    arm, 
                    extract.meta['cate_attrs'], 
                    subg_idx
                )
                flag_updated = True
    
    return flag_updated, piece


def copy_extracts(
    keystr_a,
    cq_abbr_a,
    group_a,

    keystr_b,
    cq_abbr_b,
    group_b,

    oc_type,
    skip_exists=False,
    skip_data=False
):
    '''
    Copy extracts from one group to another of same oc_type

    Please make sure the data
    '''
    project_a = dora.get_project_by_keystr(keystr_a)
    project_b = dora.get_project_by_keystr(keystr_b)

    if project_a is None:
        return None

    if project_b is None:
        return None

    # TODO, check the groups

    # Get all the extracts
    extracts_a = dora.get_extracts_by_keystr_and_cq_and_oc_type_and_group(
        keystr_a,
        cq_abbr_a,
        'pwma',
        group_a
    )

    # Copy to new projects
    extracts_b = []

    for ext_a in tqdm(extracts_a):
        # check if the abbr exists
        _ext_b = dora.get_extract_by_keystr_and_cq_and_abbr(
            keystr_b, 
            cq_abbr_b,
            ext_a.abbr
        )

        # update the meta
        new_meta = copy.deepcopy(ext_a.meta)
        new_meta['cq_abbr'] = cq_abbr_b
        new_meta['group'] = group_b

        if _ext_b is None:
            # great, there is no ext in this cq yet

            ext_b = dora.create_extract(
                project_b.project_id,
                oc_type,
                ext_a.abbr,
                new_meta,
                {} if skip_data else ext_a.data
            )
            extracts_b.append(ext_b)
            print('* copied extract %s' % ext_b.get_repr_str())

        else:
            # what??? this exists??
            if skip_exists:
                print('* skip duplicated extract %s' % ext_a.get_repr_str())

            else:
                # create a new abbr for this 
                new_abbr = util.mk_oc_abbr()
                new_meta['abbr'] = new_abbr
                ext_b = dora.create_extract(
                    project_b.project_id,
                    oc_type,
                    new_abbr,
                    new_meta,
                    {} if skip_data else ext_a.data
                )
                extracts_b.append(ext_b)
                print('* copied extract %s' % ext_b.get_repr_str())

    return extracts_b


def get_extracts_by_cate_and_name(keystr, cq_abbr, oc_type, group, category, category_outcome, full_name):
    '''
    Get extract by cate and name for detect duplicate purpose
    '''
    # first, get this paper
    project = dora.get_project_by_keystr(keystr)

    # second, check this
    sql = """
    select extract_id
    from extracts
    where project_id = '{project_id}'
        and oc_type = '{oc_type}'
        and JSON_EXTRACT(meta, '$.cq_abbr') = '{cq_abbr}'
        and JSON_EXTRACT(meta, '$.group') = '{group}'
        and JSON_EXTRACT(meta, '$.category') = '{category}'
        and JSON_EXTRACT(meta, '$.category_outcome') = '{category_outcome}'
        and JSON_EXTRACT(meta, '$.full_name') = '{full_name}'
    """.format(
        project_id=project.project_id,
        cq_abbr=cq_abbr,
        oc_type=oc_type,
        group=group,
        category=category,
        category_outcome=category_outcome,
        full_name=full_name
    )
    # print('* execute sql: %s' % sql)
    rs = db.session.execute(sql).fetchall()

    exts = []
    for r in rs:
        exts.append(
            dora.get_extract(r['extract_id'])
        )

    return exts
    

def create_empty_extract(project_id, cq_abbr, oc_type, group, category, full_name, other_meta={}):
    '''
    Create an extract with some infos
    '''
    oc_abbr = util.mk_oc_abbr()
    default_meta = copy.deepcopy(settings.OC_TYPE_TPL[oc_type]['default'])

    # set some value to meta
    default_meta['abbr'] = oc_abbr
    default_meta['cq_abbr'] = cq_abbr
    default_meta['oc_type'] = oc_type
    default_meta['group'] = group
    default_meta['category'] = category
    default_meta['full_name'] = full_name

    # need to fix the cate
    default_meta['cate_attrs'] = copy.deepcopy(
        settings.INPUT_FORMAT_TPL[oc_type][default_meta['input_format']]
    )

    # 2024-05-27: update the cate_attr after copy, otherwise it will be overwritten
    # copy other values
    for key in other_meta:
        default_meta[key] = other_meta[key]

    ext = dora.create_extract(
        project_id=project_id,
        oc_type=oc_type,
        abbr=oc_abbr,
        meta=default_meta,
        data={}
    )

    return ext


def  check__extract_nma_pre_data( df, papers,data_type, is_subg=False):
     # only one group when nma
    g_idx = 0

    # empty data
    data = {}

    # prepare the pids for detection
    pids = [ p.pid for p in papers ]
    pid2paper = {}
    for p in papers:
        pid2paper[p.pid] = p
    missing_pids = []

    # check each row
    for idx, row in df.iterrows():
        # no matter what, get the pid first
        pid = __get_pid(__get_val(row['pid']))

       

        # check this pid in pids or not
        if pid not in pids:
            if pid not in missing_pids:
                missing_pids.append(pid)

            # now it is the difficult part
            # how to deal with this missing?
            # I think we need to skip these records first
            continue
        error_exist = []
        # if data_type == 'raw':
        #     # try to get Et, Nt, Ec, Nc
        #    if 'Ec_t1' in row.keys():
        #         # assume Ec_t1, Et_t1, Ec_t2, Et_t2 format
        #         Et = __get_val(row['Ec_t1'])
        #         Nt = __get_val(row['Et_t1'])
        #         Ec = __get_val(row['Ec_t2'])
        #         Nc = __get_val(row['Et_t2'])

        #    else:
        #         # assume Et, Nt, Ec, Nc format
        #         Et = __get_val(row['Et'])
        #         Nt = __get_val(row['Nt'])
        #         Ec = __get_val(row['Ec'])
        #         Nc = __get_val(row['Nc'])

        #    if Et == '' and Nt =='' and Ec == "" and Nc == "":
        #         error_exist.append(pid)
        # if data_type == 'pre':
        #     lowerci = __get_val(row['lowerci'])
        #     upperci = __get_val(row['upperci'])
        #     if 'TE' in row.keys():     TE = __get_val(row['TE'])
        #     elif 'sm' in row.keys():   TE = __get_val(row['sm'])
        #     else:                      TE = 'NA'
        #     if TE == "NA" and lowerci == '' and upperci == '':
        #         error_exist.append(pid)
        
    return missing_pids, error_exist

def  check__extract_pwma_pre_data( df, papers,data_type, is_subg=False):
     # only one group when nma
    g_idx = 0

    # empty data
    data = {}

    # prepare the pids for detection
    pids = [ p.pid for p in papers ]
    pid2paper = {}
    for p in papers:
        pid2paper[p.pid] = p
    missing_pids = []
    error_exist = []
    # check each row
    for idx, row in df.iterrows():
        # no matter what, get the pid first
        pid = __get_pid(__get_val(row['pid']))

       

        # check this pid in pids or not
        if pid not in pids:
            if pid not in missing_pids:
                missing_pids.append(pid)

            # now it is the difficult part
            # how to deal with this missing?
            # I think we need to skip these records first
            continue
        
        if data_type == 'raw':
            # try to get Et, Nt, Ec, Nc
           if 'Ec_t1' in row.keys():
                # assume Ec_t1, Et_t1, Ec_t2, Et_t2 format
                Et = __get_val(row['Ec_t1'])
                Nt = __get_val(row['Et_t1'])
                Ec = __get_val(row['Ec_t2'])
                Nc = __get_val(row['Et_t2'])

           else:
                # assume Et, Nt, Ec, Nc format
                Et = __get_val(row['Et'])
                Nt = __get_val(row['Nt'])
                Ec = __get_val(row['Ec'])
                Nc = __get_val(row['Nc'])

           if Et == '' and Nt =='' and Ec == "" and Nc == "":
                error_exist.append(pid)
        if data_type == 'pre':
            lowerci = __get_val(row['lowerci'])
            upperci = __get_val(row['upperci'])
            if 'TE' in row.keys():     TE = __get_val(row['TE'])
            elif 'sm' in row.keys():   TE = __get_val(row['sm'])
            else:                      TE = 'NA'
            if TE == "" and lowerci == '' and upperci == '':
                error_exist.append(pid)

            print(f'PID:{pid} TE:{TE} lower_ci:{lowerci} upper_ci{upperci}')
    print("Error Exists ")

    return missing_pids, error_exist

def update_extract_pwma_pre_data(extract, df, papers, is_subg=False):
    '''
    Update extract data with a df of pre PWMA foramt

    study, year, TE/sm, lowerci, upperci, treatment, control, survival in control, Ec, Et, pid

    The `TE/sm, lowerci, upperci, survival in control, Ec, Et, pid` are required.

    But the `survival in control`, `Ec`, `Et` may not be available.

    `rob` maybe provided for risk of bias

    If this extract is about subgroup analysis, there should be an `subgroup` column.

    2024-05-27: add a new requirement

    study, year, TE/sm, lowerci, upperci, 
    survival in treatment, Ec_t1/Et, Et_t1/Nt,
    survival in control, Ec_t2/Ec, Et_t2/Nc

    '''
    # only one group when nma
    g_idx = 0

    # empty data
    data = {}

    # prepare the pids for detection
    pids = [ p.pid for p in papers ]
    pid2paper = {}
    for p in papers:
        pid2paper[p.pid] = p
    missing_pids = []

    # special for subg analysis
    subgroup_dict = {}

    # need to update the extract meta
    new_meta = copy.deepcopy(extract.meta)

    # check each row
    for idx, row in df.iterrows():
        # no matter what, get the pid first
        pid = __get_pid(__get_val(row['pid']))

        if idx == 0:
            # use the first record to update the treatment
            treatment = __get_val(row['treatment'])
            control = __get_val(row['control'])
            new_meta['treatments'] = [
                treatment, control
            ]

        # check this pid in pids or not
        if pid not in pids:
            print('* MISSING %s - pid: %s' % (
                extract.meta['full_name'],
                pid
            ))
            if pid not in missing_pids:
                missing_pids.append(pid)

            # now it is the difficult part
            # how to deal with this missing?
            # I think we need to skip these records first
            continue
        
        # get the related paper
        paper = pid2paper[pid]

        # next need to include this paper to this ext if not
        if paper.is_ss_included_in_project_and_cq(extract.meta['cq_abbr']):
            # OK, it's included, no need to further check
            pass
        else:
            dora.update_paper_ss_cq_decision(
                paper,
                [{ 'abbr': extract.meta['cq_abbr'] }],
                'yes', 
                'Import'
            )
            print('* updated %s cq selection to %s' % (
                pid,
                extract.meta['cq_abbr']
            ))
        
        # build the data object for this paper
        # the format is from the settings
        # this has to be a manually mapping
        if 'TE' in row.keys():     TE = __get_val(row['TE'])
        elif 'sm' in row.keys():   TE = __get_val(row['sm'])
        else:                      TE = 'NA'

        # try to get Et, Nt, Ec, Nc
        if 'Et' in row.keys():          Et = __get_int_val(__get_col(row, 'Et'))
        elif 'Ec_t1' in row.keys():     Et = __get_int_val(__get_col(row, 'Ec_t1'))
        else:                           Et = 'NA'

        if 'Nt' in row.keys():          Nt = __get_int_val(__get_col(row, 'Nt'))
        elif 'Et_t1' in row.keys():     Nt = __get_int_val(__get_col(row, 'Et_t1'))
        else:                           Nt = 'NA'

        if 'Ec' in row.keys():          Ec = __get_int_val(__get_col(row, 'Ec'))
        elif 'Ec_t2' in row.keys():     Ec = __get_int_val(__get_col(row, 'Ec_t2'))
        else:                           Ec = 'NA'

        if 'Nc' in row.keys():          Nc = __get_int_val(__get_col(row, 'Nc'))
        elif 'Et_t2' in row.keys():     Nc = __get_int_val(__get_col(row, 'Et_t2'))
        else:                           Nc = 'NA'

        if 'survival in treatment' in row.keys():   survival_in_treatment = __get_val(__get_col(row, 'survival in treatment'))
        elif 'survival in t1' in row.keys():        survival_in_treatment = __get_val(__get_col(row, 'survival in t1'))
        else:                                       survival_in_treatment = 'NA'

        if 'survival in control' in row.keys():   survival_in_control = __get_val(__get_col(row, 'survival in control'))
        elif 'survival in t2' in row.keys():      survival_in_control = __get_val(__get_col(row, 'survival in t2'))
        else:                                     survival_in_control = 'NA'

        # 2024-05-30: add rob column
        if 'rob' in row.keys():         rob = __get_val(__get_col(row, 'rob'), 'NA')
        else:                           rob = 'NA'

        # get all information
        arm = dict(
            treatment = __get_val(__get_col(row, 'treatment'), 'Treatment'),
            control = __get_val(__get_col(row, 'control'), 'Control'),

            TE = TE,
            lowerci = __get_val(row['lowerci']),
            upperci = __get_val(row['upperci']),

            survival_in_treatment = survival_in_treatment,
            Et = Et,
            Nt = Nt,

            survival_in_control = survival_in_control,
            Ec = Ec,
            Nc = Nc,

            rob = rob
        )

        # now, need to check if this is a subg analysis
        # by default, the subg_code is always g0
        # which means there is only one group for this analysis
        subg_code = 'g0'
        if is_subg:
            if 'subgroup' in row.keys():
                # it should be called as subgroup column
                subg = __get_val(row['subgroup'], 'NA')
            else:
                # sometimes it's just called group
                subg = __get_val(row['group'], 'NA')

            # if this a new subgroup?
            if subg not in subgroup_dict:
                # this is a new subgroup, assign a group id for this
                subgroup_dict[subg] = 'g%s' % (len(subgroup_dict))

            # get the subg_code for this subgroup
            subg_code = subgroup_dict[subg]

        # ok, let's add this record
        if pid not in data:
            # nice! first time add
            data[pid] = copy.deepcopy(settings.DEFAULT_EXTRACT_DATA_PID_TPL)

            # add this to the main arm
            data[pid]['attrs']['main'][subg_code] = arm

            # update the status
            data[pid]['is_selected'] = True
            data[pid]['is_checked'] = True

        else:
            # then need to check subg
            if is_subg:
                # as long as this paper has been added
                # we just need to add this subgroup
                data[pid]['attrs']['main'][subg_code] = arm

            else:
                # so this is not for subgroup analysis
                # the duplicated pid means 
                # wow! it's multi arm study??
                data[pid]['attrs']['other'].append(
                    {subg_code: arm}
                )

                # and increase the n_arms
                data[pid]['n_arms'] += 1

    # update the subg settings if is subgroup analysis
    if is_subg:
        # get the sub_groups
        sub_groups = []

        # create a dict for reverse search
        g2subg_dict = {}
        for k in subgroup_dict:
            v = subgroup_dict[k]
            g2subg_dict[v] = k

        # loop on the values and convert to the ordered list
        for i in range(len(g2subg_dict)):
            sub_groups.append(
                g2subg_dict['g%s'%i]
            )

        # set the subgs
        new_meta['sub_groups'] = sub_groups
        print('* found subgroups: %s' % (sub_groups))

        extract = Extract.query.filter(and_(
        Extract.project_id == extract.project_id,
        Extract.abbr == extract.abbr
        )).first()

        # TODO check if not exists

        # update
        extract.meta['sub_groups'] = sub_groups
        import datetime
        extract.date_updated = datetime.datetime.now()

        flag_modified(extract, "meta")

        # commit this
        db.session.add(extract)
        db.session.commit()
        print("* updated subgroups: %s" % (
            sub_groups
        ))

    # update the extract
    # ext = dora.update_extract_meta_and_data(
    #     extract.project_id,
    #     extract.oc_type,
    #     extract.abbr,
    #     new_meta,
    #     data
    # )

    # 2023-06-12: update using new method
    dora.create_or_update_pieces_by_extract_data(
        extract.project_id,
        extract.extract_id,
        data
    )

    return extract, missing_pids


def update_extract_pwma_raw_data(extract, df, papers, incidence_flag, is_subg=False):
    '''
    Update extract data with a df of raw PWMA foramt

    study, year, Et, Nt, Ec, Nc, treatment, control, pid

    The Et, Nt, Ec, Nc, pid are required.

    `rob` is added for coe
    '''
    # only one group when nma
    g_idx = 0

    # empty data
    data = {}

    # prepare the pids for detection
    pids = [ p.pid for p in papers ]
    pid2paper = {}
    for p in papers:
        pid2paper[p.pid] = p
    missing_pids = []

    # special for subg analysis
    subgroup_dict = {}

    # need to update the extract meta accordingly
    new_meta = copy.deepcopy(extract.meta)

    # check each row
    for idx, row in df.iterrows():
        pid = __get_pid(__get_val(row['pid']))

        if idx == 0:
            # use the first record to update the treatment
            if not incidence_flag:
                treatment = __get_val(row['treatment'])
                # breakpoint()
                control = __get_val(row['control'])
                new_meta['treatments'] = [
                    treatment, control
                ]

        # check this pid in pids or not
        if pid not in pids:
            print('* MISSING %s - pid: %s' % (
                extract.meta['full_name'],
                pid
            ))
            if pid not in missing_pids:
                missing_pids.append(pid)

            # now it is the difficult part
            # how to deal with this missing?
            # I think we need to skip these records first
            continue
        
        # get the related paper
        paper = pid2paper[pid]
        # next need to include this paper to this ext if not
        if p.is_ss_included_in_project_and_cq(extract.meta['cq_abbr']):
            # OK, it's included, no need to further check
            pass
        else:
            dora.update_paper_ss_cq_decision(
                paper,
                [{ 'abbr': extract.meta['cq_abbr'] }],
                'yes', 
                'Import'
            )
            print('* updated %s cq selection to %s' % (
                pid,
                extract.meta['cq_abbr']
            ))
        
        
        # 2024-05-30: add rob column
        if 'rob' in row.keys():         rob = __get_val(__get_col(row, 'rob'), 'NA')
        else:                           rob = 'NA'

        # build the data object for this paper
        # the format is from the settings
        # this has to be a manually mapping
        if incidence_flag:
            arm = dict(
                Et = __get_val(row['Et']),
                Nt = __get_val(row['Nt']),
                TimeUnit = __get_val(row.get('time-unit')),
                Pt = __get_val(row.get('Pt')),
                Fu = __get_val(row.get('Fu')),
                rob = rob,
            )
        else:

            if 'Ec_t1' in row.keys():
                # assume Ec_t1, Et_t1, Ec_t2, Et_t2 format
                Et = __get_val(row['Ec_t1'])
                Nt = __get_val(row['Et_t1'])
                Ec = __get_val(row['Ec_t2'])
                Nc = __get_val(row['Et_t2'])

            else:
                # assume Et, Nt, Ec, Nc format
                Et = __get_val(row['Et'])
                Nt = __get_val(row['Nt'])
                Ec = __get_val(row['Ec'])
                Nc = __get_val(row['Nc'])

            arm = dict(
                Et = Et,
                Nt = Nt,
                Ec = Ec,
                Nc = Nc,

                rob = rob,
                
                treatment = __get_val(__get_col(row, 'treatment'), 'Treatment'),
                control = __get_val(__get_col(row, 'control'), 'Control'),
            )

        # now, need to check if this is a subg analysis
        # by default, the subg_code is always g0
        # which means there is only one group for this analysis
        subg_code = 'g0'
        if is_subg:
            subg = row['subgroup']

            # if this a new subgroup?
            if subg not in subgroup_dict:
                # this is a new subgroup, assign a group id for this
                subgroup_dict[subg] = 'g%s' % (len(subgroup_dict))

            # get the subg_code for this subgroup
            subg_code = subgroup_dict[subg]

        # ok, let's add this record
        if pid not in data:
            # nice! first time add
            data[pid] = copy.deepcopy(settings.DEFAULT_EXTRACT_DATA_PID_TPL)

            # add this to the main arm
            data[pid]['attrs']['main'][subg_code] = arm

            # update the status
            data[pid]['is_selected'] = True
            data[pid]['is_checked'] = True

        else:
            # then need to check subg
            if is_subg:
                # as long as this paper has been added
                # we just need to add this subgroup
                data[pid]['attrs']['main'][subg_code] = arm

            else:
                # so this is not for subgroup analysis
                # the duplicated pid means 
                # wow! it's multi arm study??
                data[pid]['attrs']['other'].append(
                    {subg_code: arm}
                )

                # and increase the n_arms
                data[pid]['n_arms'] += 1

    # update the subg settings if is subgroup analysis
    if is_subg:
        # get the sub_groups
        sub_groups = []

        # create a dict for reverse search
        g2subg_dict = {}
        for k in subgroup_dict:
            v = subgroup_dict[k]
            g2subg_dict[v] = k

        # loop on the values and convert to the ordered list
        for i in range(len(g2subg_dict)):
            sub_groups.append(
                g2subg_dict['g%s'%i]
            )

        # set the subgs
        new_meta['sub_groups'] = sub_groups

        extract = Extract.query.filter(and_(
        Extract.project_id == extract.project_id,
        Extract.abbr == extract.abbr
        )).first()

        # TODO check if not exists

        # update
        extract.meta['sub_groups'] = sub_groups
        import datetime
        extract.date_updated = datetime.datetime.now()

        flag_modified(extract, "meta")

        # commit this
        db.session.add(extract)
        db.session.commit()
        
        print("* updated subgroups: %s" % (
            sub_groups
        ))

    # update
    # ext = dora.update_extract_meta_and_data(
    #     extract.project_id,
    #     extract.oc_type,
    #     extract.abbr,
    #     new_meta,
    #     data
    # )

    # 2023-06-12: update using new method
    dora.create_or_update_pieces_by_extract_data(
        extract.project_id,
        extract.extract_id,
        data
    )

    return extract, missing_pids


def update_extract_nma_pre_data(extract, df, papers):
    '''
    Update extract data with a df of pre data format
    '''
    # only one group when nma
    g_idx = 0

    # empty data
    data = {}

    def __get_sm(row):
        if 'sm' in row: return row['sm']
        if 'hr' in row: return row['hr']
        return ''

    # prepare the pids for detection
    pids = [ p.pid for p in papers ]
    pid2paper = {}
    for p in papers:
        pid2paper[p.pid] = p
    missing_pids = []

    # check each row
    for idx, row in df.iterrows():
        pid = __get_pid(__get_val(row['pid']))

        # check this pid in pids or not
        if pid not in pids:
            print('* MISSING %s - pid: %s' % (
                extract.meta['full_name'],
                pid
            ))
            if pid not in missing_pids:
                missing_pids.append(pid)

            # now it is the difficult part
            # how to deal with this missing?
            # I think we need to skip these records first
            continue
        
        # get the related paper
        paper = pid2paper[pid]

        # next need to include this paper to this ext if not
        if paper.is_ss_included_in_project_and_cq(extract.meta['cq_abbr']):
            # OK, it's included, no need to further check
            pass
        else:
            # Update
            dora.update_paper_ss_cq_decision(
                paper,
                [{ 'abbr': extract.meta['cq_abbr'] }],
                'yes', 
                'Import'
            )
            print('* updated %s cq selection to %s' % (
                pid,
                extract.meta['cq_abbr']
            ))

        # build the data object for this paper
        # the format is from the settings
        # this has to be a manually mapping
        arm = dict(
            t1 = str(row['t1']),
            t2 = str(row['t2']),
            sm = str(__get_sm(row)),
            lowerci = str(row['lowerci']),
            upperci = str(row['upperci']),
            survival_t1 = str(__get_val(__get_col(row, 'survival in t1'))),
            survival_t2 = str(__get_val(__get_col(row, 'survival in t2'))),
            Ec_t1 = __get_int_val(row['Ec_t1']),
            Et_t1 = __get_int_val(row['Et_t1']),
            Ec_t2 = __get_int_val(row['Ec_t2']),
            Et_t2 = __get_int_val(row['Et_t2']),
        )

        # ok, let's add this record
        if pid not in data:
            # nice! first time add
            data[pid] = copy.deepcopy(settings.DEFAULT_EXTRACT_DATA_PID_TPL)

            # add this to the main arm
            data[pid]['attrs']['main']['g0'] = arm

            # update the status
            data[pid]['is_selected'] = True
            data[pid]['is_checked'] = True

        else:
            # wow! it's multi arm study??
            data[pid]['attrs']['other'].append(
                {'g0': arm}
            )

            # and increase the n_arms
            data[pid]['n_arms'] += 1
    
    # update the extract
    # ext = dora.update_extract_data(
    #     extract.project_id,
    #     extract.oc_type,
    #     extract.abbr,
    #     data
    # )

    # 2023-06-12: update using new method
    dora.create_or_update_pieces_by_extract_data(
        extract.project_id,
        extract.extract_id,
        data
    )

    return extract, missing_pids


def update_extract_nma_raw_data(extract, df, papers):
    '''
    Update extract data with a df of raw data format

    The df format looks like the following:

    study	treat	event	total	pid
    name_x	LenPem	244  	355	    33616314
    name_x	Suni	122	    357	    33616314
    name_y	LenPem	244	    355	    33616312
    name_y	Suni	122	    357	    33616312

    there should be 5 columns and each study will have two rows.

    '''
    # only one group when nma
    g_idx = 0

    # empty data
    data = {}

    pids = [ p.pid for p in papers ]
    pid2paper = {}
    for p in papers:
        pid2paper[p.pid] = p
    missing_pids = []

    # check records two by two
    for i in range(len(df)//2):
        # get the first and second row of current idx 
        idx = i * 2
        rows = [
            df.iloc[idx],
            df.iloc[idx+1]
        ]

        # first, need to check these two pids
        pid1 = __get_pid(__get_val(rows[0]['pid']))
        pid2 = __get_pid(__get_val(rows[0]['pid']))

        if pid1 != pid2:
            # what????
            # this must be some kind of mismatch error
            print('* MISMATCH row %s: %s - %s' % (
                idx, pid1, pid2
            ))
            continue

        # ok, now just use one pid
        pid = pid1

        # check this pid in pids or not
        # due to the 2-row format design
        if pid not in pids:
            print('* MISSING %s - pid: %s' % (
                extract.meta['full_name'],
                pid
            ))
            if pid not in missing_pids:
                missing_pids.append(pid)
            
            # now it is the difficult part
            # how to deal with this missing?
            # I think we need to skip these records first
            continue
        
        # get the related paper
        paper = pid2paper[pid]

        # next need to include this paper to this ext if not
        if paper.is_ss_included_in_project_and_cq(extract.meta['cq_abbr']):
            # OK, it's included, no need to further check
            pass
        else:
            dora.update_paper_ss_cq_decision(
                paper,
                [{ 'abbr': extract.meta['cq_abbr'] }],
                'yes', 
                'Import'
            )
            print('* updated %s cq selection to %s' % (
                pid,
                extract.meta['cq_abbr']
            ))

        # build the arm
        arm = dict(
            t1 = __get_int_val(rows[0]['treat']),
            t2 = __get_int_val(rows[1]['treat']),

            event_t1 = __get_int_val(rows[0]['event']),
            total_t1 = __get_int_val(rows[0]['total']),

            event_t2 = __get_int_val(rows[1]['event']),
            total_t2 = __get_int_val(rows[1]['total']),
        )

        # check this data
        if pid not in data:
            # ok, create this record
            # nice! first time add
            data[pid] = copy.deepcopy(settings.DEFAULT_EXTRACT_DATA_PID_TPL)

            # add this to the main arm
            # it's the first row here, so the t2 is empty
            data[pid]['attrs']['main']['g0'] = arm

            # update the status
            data[pid]['is_selected'] = True
            data[pid]['is_checked'] = True

        else:
            # ok, it's a multi arm study!
            # wow! it's multi arm study??
            data[pid]['attrs']['other'].append(
                {'g0': arm}
            )

            # and increase the n_arms
            data[pid]['n_arms'] += 1

    # update the extract
    # ext = dora.update_extract_data(
    #     extract.project_id,
    #     extract.oc_type,
    #     extract.abbr,
    #     data
    # )

    # 2023-06-12: update using new method
    dora.create_or_update_pieces_by_extract_data(
        extract.project_id,
        extract.extract_id,
        data
    )

    return extract, missing_pids


def check_nma_files(keystr,
    cq_abbr, 
    oc_type,
    full_path):
    xls = pd.ExcelFile(full_path)

    # build AE Category data
    # must have a sheet called Outcomes
    dft = xls.parse('Outcomes')
    dft = dft[~dft['full_name'].isna()]
    missing_tabs = []
    missing_pids = []
    categories_realtion ={}
    categories_realtion_incidence = {}
    pid2tabs = {}
    project = dora.get_project_by_keystr(keystr)
    missing_pids_dict = {}
    wrong_data = {}
    coe_based_files = []
    missing_coe_files = []

    # get all included papers for decision
    papers = dora.get_papers_of_included_sr(
        project.project_id
    )
    total_files_ =0
    sof_files_ =0
    plot_files_ =0
    files_in_coe = 0
    for idx, row in dft.iterrows():
        tab_name = row['name'].strip()
        data_type = row['data_type'].strip()
        incidence_check = row.get('incidence', 'no') 
        analysis_group = row['analysis_title'].strip()

        category_outcome = __get_val(__get_col(row, 'category_outcome'), 'default')
        index_ = 1
        if row['included_in_sof'] == 'yes':
            sof_files_ = sof_files_ +1
        if row['included_in_plots'] == 'yes':
            plot_files_ =plot_files_ +1
        if row['included_in_em'] == 'yes':
            files_in_coe = files_in_coe +1
            coe_based_files.append(tab_name)
        
        total_files_ = total_files_ +1

        if analysis_group in categories_realtion:
            """
            To ensure thata the incidence use actually name column so we need 'name' here 
            """
            if incidence_check == 'yes':
                
                _key = f'{row["analysis_title"].strip()}|{category_outcome}|{row["full_name"].strip()}'
                    
                if category_outcome in categories_realtion[analysis_group].keys():
                    categories_realtion[analysis_group][_key].append(row['full_name'])
                else:
                    categories_realtion[analysis_group][_key]= [f'{index_}*{row["full_name"]}']
                index_  = index_ +1
            else:
                if category_outcome in categories_realtion[analysis_group].keys():
                    categories_realtion[analysis_group][category_outcome].append(row['full_name'])
                else:
                    categories_realtion[analysis_group][category_outcome]= [row['full_name']]

        else:
            categories_realtion[analysis_group] = {}
        if tab_name not in xls.sheet_names:
            missing_tabs.append(f'{tab_name}|{row["full_name"].strip()}')
            continue
        df_oc = xls.parse(tab_name)
        group = row['analysis_title'].strip()

        # need to exclude those with empty study name
        df_oc = df_oc[~df_oc['study'].isna()]

        pids = list(set(df_oc[~df_oc['pid'].isna()]['pid'].tolist()))
        for _pid in pids:
            _pid = __get_pid(__get_val(_pid))
            if _pid not in pid2tabs: pid2tabs[_pid] = []
            pid2tabs[_pid].append(tab_name)

        # if data_type == 'pre':
        #     is_subg = False
        #     if group == "subgroup":
        #         is_subg = True
        # missing_pids = list(set(missing_pids + ms_pids))
        ms_pids, error_exits = check__extract_nma_pre_data(df_oc,papers, data_type)
        missing_pids = list(set(missing_pids + ms_pids))
        if error_exits:
            wrong_data[row['full_name']] = error_exits
            
        # elif data_type == 'raw': 
        #     ext, ms_pids = update_extract_pwma_raw_data(ext, df_oc, papers, incidence_flag, is_subg)
        #     missing_pids = list(set(missing_pids + ms_pids))
        #     print('* updated ext raw data %s' % ext.abbr)
        for pid in missing_pids:
            if pid in pid2tabs:
                missing_pids_dict[pid] = pid2tabs[pid]
                print(pid, ':', pid2tabs[pid])
            else:
                print("??pid:%s" % pid)
        
    dft = xls.parse('Certainty')

    for idx, row in dft.iterrows():
            
            if row['name'] in coe_based_files:
                continue
            missing_coe_files.append(tab_name)

            
    return categories_realtion , missing_tabs, missing_pids_dict, wrong_data, total_files_, sof_files_, plot_files_, files_in_coe, missing_coe_files


def check_pwma_files( keystr, 
    cq_abbr, 
    oc_type,
    full_path, 
    flag_unselect_existing_pieces=False,
    flag_exclude_existing_outcomes_from_public=False,
    flag_has_nma_coe=False
    ):
    xls = pd.ExcelFile(full_path)

    # build AE Category data
    # must have a sheet called Outcomes
    dft = xls.parse('Outcomes')
    dft = dft[~dft['full_name'].isna()]
    missing_tabs = []
    missing_pids = []
    categories_realtion ={}
    categories_realtion_incidence = {}
    pid2tabs = {}
    project = dora.get_project_by_keystr(keystr)
    missing_pids_dict = {}
    wrong_data = {}

    # get all included papers for decision
    papers = dora.get_papers_of_included_sr(
        project.project_id
    )
    total_files_ =0
    sof_files_ =0
    plot_files_ =0
    for idx, row in dft.iterrows():
        tab_name = row['name'].strip()
        data_type = row['data_type'].strip()
        incidence_check = row.get('incidence', 'no') 
        analysis_group = row['analysis_title'].strip()

        category_outcome = __get_val(__get_col(row, 'category_outcome'), 'default')
        index_ = 1
        if row['included_in_sof'] == 'yes':
            sof_files_ = sof_files_ +1
        if row['included_in_plots'] == 'yes':
            plot_files_ =plot_files_ +1
        
        total_files_ = total_files_ +1

        if analysis_group in categories_realtion:
            """
            To ensure thata the incidence use actually name column so we need 'name' here 
            """
            if incidence_check == 'yes':
                
                _key = f'{row["analysis_title"].strip()}|{category_outcome}|{row["full_name"].strip()}'
                    
                if category_outcome in categories_realtion[analysis_group].keys():
                    categories_realtion[analysis_group][_key].append(row['full_name'])
                else:
                    categories_realtion[analysis_group][_key]= [f'{index_}*{row["full_name"]}']
                index_  = index_ +1
            else:
                if category_outcome in categories_realtion[analysis_group].keys():
                    categories_realtion[analysis_group][category_outcome].append(row['full_name'])
                else:
                    categories_realtion[analysis_group][category_outcome]= [row['full_name']]

        else:
            categories_realtion[analysis_group] = {}
        if tab_name not in xls.sheet_names:
            missing_tabs.append(f'{tab_name}|{row["full_name"].strip()}')
            continue
        df_oc = xls.parse(tab_name)
        group = row['analysis_title'].strip()

        # need to exclude those with empty study name
        df_oc = df_oc[~df_oc['study'].isna()]

        pids = list(set(df_oc[~df_oc['pid'].isna()]['pid'].tolist()))
        for _pid in pids:
            _pid = __get_pid(__get_val(_pid))
            if _pid not in pid2tabs: pid2tabs[_pid] = []
            pid2tabs[_pid].append(tab_name)

        # if data_type == 'pre':
        #     is_subg = False
        #     if group == "subgroup":
        #         is_subg = True
        # missing_pids = list(set(missing_pids + ms_pids))
        ms_pids, error_exits = check__extract_pwma_pre_data(df_oc,papers, data_type)
        missing_pids = list(set(missing_pids + ms_pids))
        if error_exits:
            wrong_data[f'Group:{analysis_group}|Category Outcome:{category_outcome}|Outcome:{row["full_name"]}'] = error_exits
            
        # elif data_type == 'raw': 
        #     ext, ms_pids = update_extract_pwma_raw_data(ext, df_oc, papers, incidence_flag, is_subg)
        #     missing_pids = list(set(missing_pids + ms_pids))
        #     print('* updated ext raw data %s' % ext.abbr)
        for pid in missing_pids:
            if pid in pid2tabs:
                missing_pids_dict[pid] = pid2tabs[pid]
                print(pid, ':', pid2tabs[pid])
            else:
                print("??pid:%s" % pid)
            
    return categories_realtion , missing_tabs, missing_pids_dict, wrong_data, total_files_, sof_files_, plot_files_
            

def import_extracts_from_xls(
    keystr, 
    cq_abbr, 
    oc_type,
    full_path, 
    flag_unselect_existing_pieces=False,
    flag_exclude_existing_outcomes_from_public=False,
    flag_has_nma_coe=False
):
    '''
    Import extracts to database
    '''
    project = dora.get_project_by_keystr(keystr)

    # load data
    xls = pd.ExcelFile(full_path)

    # build AE Category data
    # must have a sheet called Outcomes
    dft = xls.parse('Outcomes')
    dft = dft[~dft['full_name'].isna()]
    
    print(dft.head())

    # get all included papers for decision
    papers = dora.get_papers_of_included_sr(
        project.project_id
    )

    missing_pids = []
    missing_tabs = []
    pid2tabs = {}

    # 2023-06-19 add CoE 
    # this is a tab_name based dict
    # {
    #     tab_name: {
    #         cetable: {}
    #     }
    # }
    coe_dict = {}
    if flag_has_nma_coe:
        # define a func for parse value
        def _int_cie(v):
            '''
            A helper for cie int value, default is 0
            '''
            _v = util.val2int(v)
            if type(_v) == int:
                return _v
            else:
                # default just give 0
                return 0

        if oc_type == 'nma':
            # must have a Certainty tab
            dft_coe = xls.parse('Certainty')
            dft_coe = dft_coe[~dft_coe['name'].isna()]

            # check each row
            for row_idx, row in dft_coe.iterrows():
                c = row['comparator'].strip()
                t = row['treatment'].strip()
                tab_name = row['name']

                if tab_name not in coe_dict:
                    coe_dict[tab_name] = {
                        'cetable': {}
                    }

                if c not in coe_dict[tab_name]['cetable']:
                    coe_dict[tab_name]['cetable'][c] = {}

                # check treatment
                if t not in coe_dict[tab_name]['cetable'][c]:
                    coe_dict[tab_name]['cetable'][c][t] = {}

                # put the values
                for k in settings.CIE_NMA_COLUMNS:
                    # make sure the value type is int
                    coe_dict[tab_name]['cetable'][c][t][k] = _int_cie('%s'%row[k])

                # no matter cie is there or not
                # update cie
                # then get the final cie
                coe_dict[tab_name]['cetable'][c][t]['cie'] = util.calc_nma_cie(
                    coe_dict[tab_name]['cetable'][c][t],
                    settings.CIE_NMA_COLUMNS
                )
            # summary extracted
            n_coe_ocs = len(coe_dict.keys())
            
            print('* found %s CoE(s) for NMA outcomes' % (
                n_coe_ocs
            ))
        
        if oc_type == 'pwma':
            pass

    else:
        print("* skip parsing NMA coe as flag_has_nma_coe=%s" % (flag_has_nma_coe))

    # before adding, just exclude all
    if flag_exclude_existing_outcomes_from_public:
        extracts = dora.get_extracts_by_keystr_and_cq_and_oc_type(
            project.keystr,
            cq_abbr,
            oc_type
        )
        for extract in extracts:
            extract.meta['included_in_plots'] = 'no'
            extract.meta['included_in_sof'] = 'no'

            # just for NMA
            if oc_type == 'nma': extract.meta['included_in_em'] = 'no'

            flag_modified(extract, 'meta')
            db.session.add(extract)
            print('* excluded from plots+sof+em to outcome %s' % (
                extract.get_repr_str()
            ))
        db.session.commit()
    
    else:
        print('* skip excluding all outcomes from plots+sof')

    # columns we could use 
    categories_realtion ={}
    categories_realtion_incidence = {}
    for idx, row in dft.iterrows():
        tab_name = row['name'].strip()
        data_type = row['data_type'].strip()
        incidence_check = row.get('incidence', 'no') 
        analysis_group = row['analysis_title'].strip()

        category_outcome = __get_val(__get_col(row, 'category_outcome'), 'default')
        index_ = 1

        if analysis_group in categories_realtion:
            """
            To ensure thata the incidence use actually name column so we need 'name' here 
            """
            if incidence_check == 'yes':
                
                _key = f'{row["analysis_title"].strip()}|{category_outcome}|{row["full_name"].strip()}'
                    
                if category_outcome in categories_realtion[analysis_group].keys():
                    categories_realtion[analysis_group][_key].append(row['full_name'])
                else:
                    categories_realtion[analysis_group][_key]= [f'{index_}*{row["full_name"]}']
                index_  = index_ +1
            else:
                if category_outcome in categories_realtion[analysis_group].keys():
                    categories_realtion[analysis_group][category_outcome].append(row['full_name'])
                else:
                    categories_realtion[analysis_group][category_outcome]= [row['full_name']]

        else:
            categories_realtion[analysis_group] = {}
    
    project = dora.get_project_by_keystr(keystr)

    project_settings = project.settings
    if project.settings.get('cq_plots_statisification'):
        project.settings['cq_plots_statisification'][cq_abbr] = categories_realtion
        
    else:
        project.settings['cq_plots_statisification'] ={
            cq_abbr: categories_realtion
        }
    is_success, project = dora.set_project_settings(
            project.project_id, project_settings
        )
    for idx, row in dft.iterrows():
        tab_name = row['name'].strip()
        data_type = row['data_type'].strip()
        analysis_group = row['analysis_title'].strip()
        print(
            '*'*40, 
            (idx+1), '/', len(dft),
            keystr, 
            cq_abbr, oc_type, analysis_group, '[%s]' % tab_name, '|', data_type
        )
        
        # search this tab first
        if tab_name not in xls.sheet_names:
            print('* NOT FOUND SHEET [%s]' % tab_name)
            missing_tabs.append(tab_name)
            continue

        # the general meta information for an outcome
        category_outcome = __get_val(__get_col(row, 'category_outcome'), 'default')
        incidence_rate = __get_val(__get_col(row, 'incidence_rate'), 'NA')

        meta = dict(
            cq_abbr = cq_abbr,
            oc_type = oc_type,
            group = row['analysis_title'].strip(),
            category = row['category'].strip(),
            full_name = row['full_name'].strip(),
            which_is_better = row['which_is_better'].strip(),
            fixed_or_random = row['fixed_or_random'].strip(),
            measure_of_effect = row['measure'].strip(),
            included_in_plots = row['included_in_plots'].strip(),
            included_in_sof = row['included_in_sof'].strip(),
            is_subg_analysis = 'no',
            sub_groups = ['A'],
            category_outcome = category_outcome,
            incidence_rate = incidence_rate
        )
        print('* created meta %s|%s|%s' % (
            meta['group'], meta['category'], meta['full_name']
        ))

        # special rule for NMA
        if oc_type == 'nma':
            # include this extract in evidence map or not
            meta['included_in_em'] = row['included_in_em'].strip().lower()

            # for NMA, freq or bayes?
            meta['analysis_method'] = row['method'].strip()

            # the current data type
            meta['input_format'] = {
                'pre':'NMA_PRE_SMLU', 
                'raw':'NMA_RAW_ET'
            }[data_type]

            # 2023-06-30: update coe by the coe_dict
            if tab_name in coe_dict:
                meta['cetable'] = coe_dict[tab_name]['cetable']
                print('* attached XLS CoE data to %s meta.cetable' % (
                    tab_name
                ))
                util.print_cetable(meta['cetable'])
            else:
                print('* NOT found %s in Certainty of Evidence sheet' % (tab_name))

        # special rule for PWMA
        if oc_type == 'pwma':
            # the certainty for this outcome
            # the values could be NaN, so need to check
            meta['certainty'] = {
                'cie': '0',
                'risk_of_bias': "%s"%__get_int_val(__get_col(row, 'risk_of_bias'), '0'),
                'inconsistency': "%s"%__get_int_val(__get_col(row, 'inconsistency'), '0'),
                'indirectness': "%s"%__get_int_val(__get_col(row, 'indirectness'), '0'),
                'imprecision': "%s"%__get_int_val(__get_col(row, 'imprecision'), '0'),
                'publication_bias': "%s"%__get_int_val(__get_col(row, 'publication_bias'), '0'),
                'importance': __cie_imp2val(__get_val(__get_col(row, 'importance'), '0')),
            }

            # the treatment and control
            # but the value can be empty
            # need to double check in the data sheet

            # check the Incdence base data here 
            incidence_flag = False
            if (row.get('incidence') and row.get('incidence') == "yes"):
                #  breakpoint()
                 meta['input_format'] = 'PRIM_INC_RAW'
                 incidence_flag = True
                 val_t = __get_val(row.get('treatment'), 'Treatment')
                 val_c = __get_val(row.get('control'), 'Control')
                 meta['treatments'] = [
                    val_t,
                    val_c
                ]
                 meta['full_name'] = f'{row["analysis_title"].strip()}|{category_outcome}|{row["full_name"].strip()}'
                 meta['incidence_gene_name'] = row['name']
            
            else:
                val_t = __get_val(row.get('treatment'), 'Treatment')
                val_c = __get_val(row.get('control'), "Control")
                meta['treatments'] = [
                    val_t,
                    val_c
                ]
                 # the data type
                meta['input_format'] = {
                    'pre': 'PRIM_CAT_PRE', 
                    'raw': 'PRIM_CAT_RAW'
                }[data_type]
            # now need to check subg analysis
            if meta['group'] == 'subgroup':
                meta['is_subg_analysis'] = 'yes'

        # 2024-05-27: while importing the new xlsx, the def may change
        # update the cate_attrs
        meta['cate_attrs'] = settings.INPUT_FORMAT_TPL[oc_type][meta['input_format']]

        # check exist
        exts = get_extracts_by_cate_and_name(
            keystr, 
            cq_abbr,
            oc_type,
            meta['group'],
            meta['category'],
            meta['category_outcome'],
            meta['full_name']
        )

        if len(exts)==0:
            ext = create_empty_extract(
                project.project_id, 
                cq_abbr,
                oc_type,
                meta['group'],
                meta['category'],
                meta['full_name'],
                meta
            )
            print('* created extract from sheet[%s] -> %s' % (
                tab_name,
                ext.get_repr_str()
            ))

        else:
            ext = exts[0]
            ext.update_meta_by_other_meta(meta)
            ext = dora.update_extract(
                ext,
                flag_has_meta_modified=True
            )
            print('* updated extract from sheet[%s] -> %s' % (
                tab_name,
                ext.get_repr_str()
            ))

        if flag_unselect_existing_pieces:
            # now need to find all related pieces
            pieces = dora.get_pieces_by_project_id_and_extract_id(
                project.project_id,
                ext.extract_id
            )
            if len(pieces) > 0:
                # unselect all
                for p in pieces:
                    p.set_is_selected(False)
                    db.session.add(p)
                    flag_modified(p, "data")

                db.session.commit()
                print('* found and unselected %s existing pieces for this outcome %s' % (
                    len(pieces),
                    tab_name
                ))
            else:
                print('* not found any pieces for this outcome %s' % (
                    tab_name
                ))
        else:
            print("* skipped unselect existing pieces as flag_unselect_existing_pieces=%s" % (
                flag_unselect_existing_pieces
            ))

        # now let's update data
        df_oc = xls.parse(tab_name)

        # need to exclude those with empty study name
        df_oc = df_oc[~df_oc['study'].isna()]
        print('* found %s records for this oc in the XLS sheet %s' % (
            len(df_oc),
            tab_name
        ))
        
        # update the pid used by oc
        pids = list(set(df_oc[~df_oc['pid'].isna()]['pid'].tolist()))
        for _pid in pids:
            _pid = __get_pid(__get_val(_pid))
            if _pid not in pid2tabs: pid2tabs[_pid] = []
            pid2tabs[_pid].append(tab_name)

        if oc_type == 'nma':
            if data_type == 'pre':
                ext, ms_pids = update_extract_nma_pre_data(ext, df_oc, papers)
                missing_pids = list(set(missing_pids + ms_pids))
                print('* updated ext pre data %s' % ext.abbr)

            elif data_type == 'raw':
                ext, ms_pids = update_extract_nma_raw_data(ext, df_oc, papers)
                missing_pids = list(set(missing_pids + ms_pids))
                print('* updated ext raw data %s' % ext.abbr)

        elif oc_type == 'pwma':
            # one more thing for pwma is that is this a subg analysis
            is_subg = meta['is_subg_analysis'] == 'yes'
            if data_type == 'pre':
                ext, ms_pids = update_extract_pwma_pre_data(ext, df_oc, papers, is_subg)
                missing_pids = list(set(missing_pids + ms_pids))
                print('* updated ext pre data %s' % ext.abbr)

            elif data_type == 'raw': 
                ext, ms_pids = update_extract_pwma_raw_data(ext, df_oc, papers, incidence_flag, is_subg)
                missing_pids = list(set(missing_pids + ms_pids))
                print('* updated ext raw data %s' % ext.abbr)
    
             
    print('\n\n\n* MISSING pids:')
    for pid in missing_pids:
        if pid in pid2tabs:
            print(pid, ':', pid2tabs[pid])
        else:
            print("??pid:%s" % pid)
            
    print('\n\n\n* MISSING tabs:')
    for tab in missing_tabs:
        print(tab)
    
    if len(missing_pids) == 0 and \
       len(missing_tabs) == 0:
        print('\n\n\n* GREAT! It seems NO missing found while importing papers!\n')

    else:
        print('\n\n\n* TOO BAD! Something is missing!\n')


    return dft


###############################################################################
# Utils for the itable
###############################################################################

def get_itable_by_keystr_and_cq_abbr(keystr, cq_abbr):
    '''
    Get the specific CQ itable in a project
    '''
    project = dora.get_project_by_keystr(keystr)

    if project is None:
        return None

    extract = Extract.query.filter(and_(
        Extract.project_id == project.project_id,
        Extract.meta['cq_abbr'] == cq_abbr,
        Extract.oc_type == 'itable'
    )).first()

    return extract


def get_itable_by_project_id_and_cq_abbr(project_id, cq_abbr):
    '''
    Get the specific CQ itable in a project
    '''
    extract = Extract.query.filter(and_(
        Extract.project_id == project_id,
        Extract.meta['cq_abbr'] == cq_abbr,
        Extract.oc_type == 'itable'
    )).first()

    return extract


def import_itable_from_xls(
    keystr, 
    cq_abbr, 
    full_fn_itable, 
    full_fn_filter,
    flag_overwrite_decision=True,
    flag_overwrite_piece=True
):
    '''
    Import itable all data from xls file

    Including:

    1. meta data for attributes
    2. data of extraction
    3. filters

    the itable file name is 'ITABLE_ATTR_DATA.xlsx' or other
    the filters name is ITABLE_FILTERS.xlsx or other
    '''
    project = dora.get_project_by_keystr(keystr)

    # if project is None:
    #     project_id = request.cookies.get('project_id')
    #     project = dora.get_project(project_id)

    if project is None:
        return None
    
    project_id = project.project_id
    oc_type = 'itable'

    # in fact, due to the update the cq, this is also needed to be updated
    # cq_abbr = 'default'

    # get the exisiting extracts
    # extract = dora.get_extract_by_project_id_and_abbr(
    #     project.project_id, abbr
    # )
    extract = dora.get_itable_by_project_id_and_cq(
        project_id, 
        cq_abbr
    )

    # if not exist, create a new one which is empty
    if extract is None:
        abbr = util.mk_abbr()
        meta = copy.deepcopy(settings.OC_TYPE_TPL['itable']['default'])
        meta['cq_abbr'] = cq_abbr
        extract = dora.create_extract(
            project_id, 
            oc_type, 
            abbr, 
            settings.OC_TYPE_TPL['itable']['default'],
            {}
        )
        print('* created an extract %s for itable' % (extract.extract_id))

    else:
        print('* found an existing extract %s for itable' % (extract.extract_id))

    # 2022-02-19: fix the order
    abbr = extract.abbr

    # 2024-05-28: overwrite the is_selected decision for all existing
    if flag_overwrite_decision:
        dora.unselect_extract_data(extract)

    # get the itable data
    cad, cate_attrs, i2a, data, not_found_pids, found_pmids_xls = get_itable_from_itable_data_xls(
        project.keystr, 
        cq_abbr,
        full_fn_itable,
        extract.data,
        flag_overwrite_decision,
    )
    if cate_attrs is None:
        # something wrong???
        return None

    print('* not found the following %s pid(s)' % (
        len(not_found_pids)
    ))
    for _ in not_found_pids:
        print('*   %s' % (_))

    # update the meta's cate_attrs only
    meta = extract.meta
    meta['cate_attrs'] = cate_attrs

    # get the filters
    if full_fn_filter is None or full_fn_filter == '':
        # no need to update the filters
        pass
    else:
        # oh, we get a new filter file
        filters = get_itable_filters_from_xls(
            project.keystr, 
            full_fn_filter
        )
        if filters == []:
            print('* not found filters')

        meta['filters'] = filters

    # update the extract
    # pprint(filters)
    # 2023-05-29: just update meta first
    itable = dora.update_extract_meta(
        project_id, 
        oc_type, 
        abbr, 
        meta
    )

    itable_data = dora.update_extract_data(
        project_id, 
        abbr, 
        cq_abbr, 
        data
    )

    # get papers for import
    papers = srv_paper.get_included_papers_by_cq(
        project_id, 
        cq_abbr
    )
    paper_dict = {}
    for paper in papers:
        paper_dict[paper.pid] = paper
    print('* found %s papers included in SR[%s/%s]' % (
        len(papers),
        project.keystr,
        cq_abbr
    ))

    # save all data
    stat_data = {
        'no_paper': [],
        'no_piece': [],
        'has_piece': []
    }
    for pid in data:
        print('***** working on %s' % (pid))
        # convert to lower case
        if pid not in paper_dict:
            stat_data['no_paper'].append(pid)
            print('!! not found %s in INCLUDED_SR to [%s], maybe excluded or included in other cq' % (
                pid, cq_abbr
            ))
            continue
        
        # try to search this picec
        piece = dora.get_piece_by_project_id_and_extract_id_and_pid(
            project_id,
            extract.extract_id,
            pid
        )

        if piece is None:
            stat_data['no_piece'].append(pid)
            # create piece
            _piece = dora.create_piece(
                project_id,
                extract.extract_id,
                pid,
                data[pid]
            )

        else:
            stat_data['has_piece'].append(pid)

            if flag_overwrite_piece:
                dora.update_piece_data_by_id(
                    piece.piece_id,
                    data[pid],
                    # 2024-05-28: we also need to overwrite the selection
                    flag_skip_is_selected=False
                )
        
    print('* skipped missing included_in_SR %s paper(s): %s' % (
        len(stat_data['no_paper']),
        ' | '.join(stat_data['no_paper'])
    ))
    print('* added no extracted piece %s' % (
        len(stat_data['no_piece'])
    ))
    print('* %s piece %s' % (
        'updated' if flag_overwrite_piece else 'found(no update)',
        len(stat_data['has_piece'])
    ))

    return itable


def get_itable_from_itable_data_xls(
    keystr, 
    cq_abbr,
    full_fn,
    extract_orginial_data,
    flag_overwrite_decision=True
    ):
    '''
    Get the itable extract from ITABLE_ATTR_DATA.xlsx
    '''
    if not os.path.exists(full_fn):
        # try the xls file
        # full_fn = full_fn[:-1]
        # what's wrong???
        return None, None, None, None, None

    # get this project
    project = dora.get_project_by_keystr(keystr)
    if project is None:
        return None, None, None, None, None
    original_pmids = []
    for key , value in extract_orginial_data.items():
        original_pmids.append(key)

    # get the ca list first
    ca_dict, ca_list, i2a, n2i, i2n = get_cate_attr_subs_from_itable_data_xls(
        full_fn
    )

    # read the first sheet, but skip the first row
    xls = pd.ExcelFile(full_fn)
    first_sheet_name = xls.sheet_names[0]

    # 2024-05-17: some columns have same name, so shouldn't use header as default
    df = xls.parse(first_sheet_name, header=None, skiprows=1)

    # 2021-06-27: weird bug, read so many NaN columns
    df = df.dropna(axis=1, how='all')

    # get the num of total columns
    n_cols = len(df.columns)
    print("* found %s columns in df" % n_cols)

    # a pmid/pid based dictionary
    data = {}

    # use this to locate those not found pid
    not_found_pids = []
    found_pids_xls_file = []

    # By default deselect all studies in the original itable data 
    for pmid in data:
        data[pmid]['is_selected'] = False
        data[pmid]['is_checked'] = False

    # begin loop 
    for row_idx, row in df.iterrows():
        # the first row is the header but we don't use
        if row_idx == 0: continue

        # find the pmid first
        if 'PMID' in n2i:
            pmid = row[n2i['PMID']]
        elif 'PubMed ID' in n2i:
            pmid = row[n2i['PubMed ID']]
        else:
            pmid = None

        # try to make sure it's NOT something like 12345678.0
        if pd.isna(pmid):
            # this is a NaN value for pmid
            # can not parse this kind of value
            print('* skipped Row[%s] duo to NaN pmid' % ( _ ))
            continue

        try:
            pmid = int(pmid)

            # must make sure the pmid is a string
            pmid = '%s' % pmid

            # the pmid may contain blank
            pmid = pmid.strip()
            pmid = '%s' % int(pmid)
            
        except:
            pmid = pmid.strip()
            # print('* non-PMID pid[%s]' % ( pmid ))
            # 2022-02-04: now we support DOI as pid
            # just remove the blanks
            # last try, just

        # 2023-06-12: need to have lowercase pmid/doi for processing
        pmid = pmid.lower()
        found_pids_xls_file.append(pmid)

        print('*********************** processing %s / %s: %s' % (
            row_idx,
            len(df),
            pmid
        ))
        

        # get the NCT
        if 'Trial registration #' in n2i:
            nct8 = __get_val(row[n2i['Trial registration #']])
        elif 'NCT' in n2i:
            # 2022-02-04: sometimes the nct is from Col NCT
            nct8 = __get_val(row[n2i['NCT']], 'NA')
        else:
            nct8 = ''

        # get the decision
        if 'Included in MA' in n2i:
            included_in_ma = ('%s'%row[n2i['Included in MA']]).strip().upper()
        else:
            included_in_ma = 'NO'

        # check if this pmid exists
        is_main = False

        if pmid in data:
            # which means this row is an multi arm
            # add a new object in `other`
            # that's all we need to do
            data[pmid]['n_arms'] += 1
            data[pmid]['attrs']['other'].append({'g0':{}}) # subg 0 (in fact no subg)

        else:
            # ok, this is a new study
            # by default not selected and not checked
            # 
            # `main` is for the main records
            # `other` is for other arms, by default, other is empty
            data[pmid] = {
                'is_selected': True,
                'is_checked': True,
                'n_arms': 2,
                'attrs': {
                    'main': {'g0': {}}, # follow the pattern shared by subg
                    'other': []
                }
            }
            is_main = True

            # it's better to update the nct information
            is_success, p = srv_paper.set_paper_rct_id(
                keystr, pmid, nct8
            )

            if is_success:
                # ok, updated the nct for this paper
                pass
            else:
                print('* skipped setting rct_id [%s] to %s' % (
                    nct8, pmid
                ))

            # next, if a study is in itable.xls,
            # it must be included sr at least
            p = dora.get_paper_by_project_id_and_pid(
                project.project_id, pmid
            )

            if p is None:
                # BUT, it is possible that this pmid is not found
                print('* NOT found pid[%s] in the current project' % (
                    pmid
                ))
                not_found_pids.append(
                    pmid
                )

            else:
                # OK, we found this paper!
                sss = p.get_ss_stages()
                # if ss_state.SS_STAGE_INCLUDED_SR in sss:
                #     # OK, this study is included in SR at least
                #     pass

                # else:

                # set the stage for this paper
                # change stage!
                if flag_overwrite_decision:
                    _, p = srv_paper.set_paper_ss_decision(
                        project, 
                        cq_abbr,
                        pmid, 
                        ss_state.SS_PR_CHECKED_BY_ADMIN,
                        ss_state.SS_RS_INCLUDED_ONLY_SR,
                        ss_state.SS_REASON_CHECKED_BY_ADMIN,
                        ss_state.SS_STAGE_INCLUDED_ONLY_SR
                    )

                    # OK, updated
                    print('* updated decision %s from %s to %s' % (
                        pmid, sss, p.get_ss_stages()
                    ))


        data[pmid]['is_selected'] = True
        data[pmid]['is_checked'] = True        

        
        print("@@@@@@@@@@@@@@@@@ attaching data object to %s" % pmid)


        # now check each column for this study
        for idx in range(n_cols):
            # but th
            col = i2n[idx]
            abbr = i2a[idx]

            # 2024-05-29: just copy everything
            # skip the pmid column
            # since we already use this column as the key
            # if col.upper() in settings.EXTRACTOR_ITABLE_IMPORT_SKIP_COLUMNS:
            #     continue

            # get the value in this column
            val = row[idx]

            # try to clear the blanks
            try: val = val.strip()
            except: pass
            
            # for NaN value
            if pd.isna(val): val = None

            # special rule for COE
            if abbr == 'COE_RCT_ROB_OVERALL_RJ':
                val = __format_itable_coe_rob(val)

            elif abbr == 'COE_RCT_IND_OVERALL_RJ':
                val = __format_itable_coe_ind(val)

            
            if is_main:
                data[pmid]['attrs']['main']['g0'][abbr] = val
                # print("********************************************")
                # print( data[pmid]['attrs']['main']['g0'][abbr])
            else:
                # check if this value is same in the main track
                if val == data[pmid]['attrs']['main']['g0'][abbr]: 
                    # for the same value, also set ...
                    data[pmid]['attrs']['other'][-1]['g0'][abbr] = val
                else:
                    # just save the different values
                    data[pmid]['attrs']['other'][-1]['g0'][abbr] = val
            
            # print('* added col[%s] as abbr[%s] val[%s]' % (col, abbr, val))

        print('* attached %s to data obj %s arms with [%s]' % (
            pmid, data[pmid]['n_arms'], nct8
        ))
        

    # items_not_in_xls_itable = [item for item in original_pmids if item not in found_pids_xls_file]
    # for pid in items_not_in_xls_itable:
    #     if data.get(pid):
    #         print("#################################################")
    #         print(pid)
    #         data[pid]['is_checked'] = False
    #         data[pid]['is_selected'] = False
    # print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
    # modified_data = {}
    # for pid , value in data.items():
    #     if pid in found_pids_xls_file:
    #         modified_data[pid] = value
    # print(items_not_in_xls_itable)
    # print(len(items_not_in_xls_itable))

    return ca_dict, ca_list, i2a, data, not_found_pids, found_pids_xls_file


def get_cate_attr_subs_from_itable_data_xls(full_fn):
    '''
    Get the cate, attr, and subs from the given file
    '''
    if not os.path.exists(full_fn):
        # try the xls file ? wh
        # full_fn = full_fn[:-1]

        # 2022-02-04: no matter what it is, return None
        return None, None, None

    # read the first sheet
    xls = pd.ExcelFile(full_fn)
    first_sheet_name = xls.sheet_names[0]
    df = xls.parse(first_sheet_name, header=None, nrows=2)

    # 2021-06-27: weird bug, read so many NaN columns
    # df = pd.read_excel(full_fn)
    df = df.dropna(axis=1, how='all')

    # convert to other shape
    dft = df.T
    df_attrs = dft.rename(columns={0: 'cate', 1: 'attr'})

    # not conver to tree format
    cate_attr_dict = OrderedDict()
    idx2abbr = {}

    # 2024-05-17: mapping from name to the column
    # ATTENTION: this is not 1:1 mapping
    name2idx = {}
    idx2name = {}

    # check each attr
    for idx, row in df_attrs.iterrows():
        vtype = 'text'

        if type(row['cate']) != str:
            if math.isnan(row['cate']) \
                or math.isnan(row['attr']):
                print('* skip nan cate or attr idx %s' % idx)
                continue


        print("* found %s | %s" % (
            row['cate'], row['attr']
        ))

        # found cate and attr
        cate = row['cate'].strip()
        attr = row['attr'].strip()

        # update attr2idx
        name2idx[attr] = idx
        idx2name[idx] = attr

        # skip some attrs
        # if attr.upper() in settings.EXTRACTOR_ITABLE_IMPORT_SKIP_COLUMNS:
        #     continue

        # special rule for _COE Risk of Bias
        if cate == '_COE_RCT_ROB':  
            cate_attr_dict['COE_RCT_ROB'] = copy.deepcopy(settings.COE_RCT_ROB)

            # just use the column name as abbr
            # in this case, the column name must be abbr:
            # COE_RCT_ROB_OVERALL_RJ
            # or other 
            attr_dict = {
                'abbr': attr,
                'name': attr
            }

            # update the index
            idx2abbr[idx] = attr_dict['abbr']
            print("* mapped %s to attr %s[%s]" % (
                idx,
                attr_dict['name'],
                idx2abbr[idx]
            ))
            continue

        # special rule for _COE Indirectness
        if cate == '_COE_RCT_IND':  
            cate_attr_dict['COE_RCT_IND'] = copy.deepcopy(settings.COE_RCT_IND)

            # just use the column name as abbr
            # in this case, the column name must be abbr:
            # COE_RCT_IND_OVERALL_RJ
            # or other 
            attr_dict = {
                'abbr': attr,
                'name': attr
            }

            # update the index
            idx2abbr[idx] = attr_dict['abbr']
            print("* mapped %s to attr %s[%s]" % (
                idx,
                attr_dict['name'],
                idx2abbr[idx]
            ))
            continue

        # 2024-05-28: fix the empty coe attrs
        # put this cate if not exists
        if cate not in cate_attr_dict:
            cate_attr_dict[cate] = {
                'abbr': util.mk_hash_12(cate),
                'name': cate,
                'attrs': {}
            }

        # special rule for _SYS and _FLOW
        if cate in ['_SYS', '_FLOW']:
            # in _FLOW and _SYS, we assume user just input the abbr manually
            if attr.startswith('abbr='): 
                # get the attr and user-specific abbr from input
                attr_dict = _parse_attr_column_with_abbr(attr)
                
            else:
                # for those defined in old way, just generate this attr_dict
                # create the abbr using the same format as before
                attr_dict = {
                    'abbr': util.mk_hash_12('%s|%s'%(cate, attr)),
                    'name': attr,
                }
            
            # update the whole cate_attr_dict
            cate_attr_dict[cate]['attrs'][attr_dict['name']] = {
                'abbr': attr_dict['abbr'],
                'name': attr_dict['name'],
                'subs': {}
            }

            sub = None
            subsub = None
            subsubsub = None

            print("* found an user-specific abbr: %s -> %s|%s" % (
                cate,
                attr_dict['abbr'],
                attr_dict['name']
            ))

            # update the mapping from idx to this user-specific abbr
            idx2abbr[idx] = attr_dict['abbr']
            print("* mapped %s to attr %s[%s]" % (
                idx,
                attr_dict['name'],
                idx2abbr[idx]
            ))
            
            # then we don't need to run the following codes
            continue
            
    
        # for all other cates, such as TRIAL CHARS, OUTCOMES, etc.
        # split the name into different parts
        attr_subs = attr.split('|')
        if len(attr_subs) == 2:
            # old structure, only attr + sub
            attr = attr_subs[0].strip()
            sub = attr_subs[1].strip()
            subsub = None
            subsubsub = None

        elif len(attr_subs) == 3:
            # e.g., Mode of metastases - N (%) | Synchronous | Treatment
            attr = attr_subs[0].strip()
            sub = attr_subs[1].strip()
            subsub = attr_subs[2].strip()
            subsubsub = None

        elif len(attr_subs) == 4:
            # e.g., Mode of metastases - N (%) | Synchronous | Treatment | Population
            attr = attr_subs[0].strip()
            sub = attr_subs[1].strip()
            subsub = attr_subs[2].strip()
            subsubsub = attr_subs[3].strip()

        else:
            # e.g., Full Pub or Abstract
            attr = attr
            sub = None
            subsub = None
            subsubsub = None


        # now, need to create the structure and generate the abbr for mapping
        # put this attr if not exists
        if attr not in cate_attr_dict[cate]['attrs']:
            cate_attr_dict[cate]['attrs'][attr] = {
                'abbr': util.mk_hash_12('%s|%s'%(cate, attr)),
                'name': attr,
                'subs': {}
            }
            print('* added an attr [%s] to %s' % (
                attr,
                '%s' % (cate)
            ))
        

        # put this sub if not exists
        if sub is not None and \
            sub not in cate_attr_dict[cate]['attrs'][attr]['subs']:
            cate_attr_dict[cate]['attrs'][attr]['subs'][sub] = {
                'abbr': util.mk_hash_12('%s|%s|%s' % (
                    cate, attr, sub
                )),
                'name': sub,
                "sub_categories": {}
            }
            print('* added a sub [%s] to %s' % (
                sub,
                '%s | %s' % (cate, attr)
            ))


        # put this subsub if not exists
        if subsub is not None and \
            subsub not in cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories']:
            cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories'][subsub] = {
                'abbr': util.mk_hash_12('%s|%s|%s|%s' % (
                    cate, attr, sub, subsub
                )),
                'name': subsub,
                'sub_sub_categories': {}
            }
            print('* added a subsub [%s] to %s' % (
                subsub,
                '%s | %s | %s' % (cate, attr, sub)
            ))


        # put this subsubsub if not exists
        if subsubsub is not None and \
            subsubsub not in cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories'][subsub]['sub_sub_categories']:

            cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories'][subsub]['sub_sub_categories'][subsubsub] = {
                'abbr': util.mk_hash_12('%s|%s|%s|%s|%s' % (
                    cate, attr, sub, subsub, subsubsub
                )),
                'name': subsubsub
            }
            print('* added a subsubsub [%s] to %s' % (
                subsubsub,
                '%s | %s | %s | %s' % (cate, attr, sub, subsub)
            ))


        # Now, need to decide the index -> abbr mapping
        if len(attr_subs) == 2:
            # old structure, only attr + sub
            idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['abbr']
            print("* mapped %s to attr + sub %s[%s]" % (
                idx,
                sub,
                idx2abbr[idx]
            ))

        elif len(attr_subs) == 3:
            # attr + sub + subusb
            # e.g., Mode of metastases - N (%) | Synchronous | Treatment
            idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories'][subsub]['abbr']
            print("* mapped %s to attr + sub + subsub %s[%s]" % (
                idx,
                subsub,
                idx2abbr[idx]
            ))

        elif len(attr_subs) == 4:
            # attr + sub + subusb + subsubusb
            # e.g., Mode of metastases - N (%) | Synchronous | Treatment | Population
            idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories'][subsub]['sub_sub_categories'][subsubsub]['abbr']
            print("* mapped %s to attr + sub + subsub + subsubsub %s[%s]" % (
                idx,
                subsubsub,
                idx2abbr[idx]
            ))

        else:
            # just attr
            # e.g., Full Pub or Abstract
            idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['abbr']
            print("* mapped %s to attr %s[%s]" % (
                idx,
                attr,
                idx2abbr[idx]
            ))

        # # get the index mapping of this current row
        # if subsub is not None:
        #     # point the idx to the last subsub in current attr's sub
        #     idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories'][-1]['abbr']
        #     print("indexing!!!!!!!!!!!!!!!!!!!1")
        #     print(idx, cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories'][subsub]['abbr'])

        # #########################
        # # put this subsubsub if not exists
        # if subsubsub is not None:
        #     print( 
        #         cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories']
        #     )
        #     cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories'][subsub]['sub_sub_categories'].append({
        #         'abbr': util.mk_hash_12('%s|%s|%s|%s|%s' % (
        #             cate, attr, sub, subsub, subsubsub
        #         )),
        #         'name': subsubsub,
        #     })

        # # get the index mapping of this current row
        # if subsubsub is not None:
        #     # point the idx to the last subsubsub in current attr's sub
        #     idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories'][subsub]['sub_sub_categories'][-1]['abbr']
        #     print("indexing!!!!!!!!!!!!!!!!!!!1")
        #     print(idx, cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['sub_categories'][subsub]['sub_sub_categories'][-1]['abbr'])

        # #########################

        # elif sub is not None:
        #     # point the idx to the last sub in current attr
        #     idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['abbr']
        #     print("indexing!!!!!!!!!!!!!!!!!!!1")
        #     print(idx, cate_attr_dict[cate]['attrs'][attr]['subs'][sub]['abbr'])
        # else:
        #     # point the idx to the attr
        #     idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['abbr']
            
        #     print("indexing!!!!!!!!!!!!!!!!!!!1")
        #     print(idx, cate_attr_dict[cate]['attrs'][attr]['abbr'])
            

        # put this sub
        # if sub is not None:
        #     if cate_attr_dict[cate]['attrs'][attr]['subs'] is None:
        #         cate_attr_dict[cate]['attrs'][attr]['subs'] = [{
        #             'abbr': util.mk_hash_12('%s|%s|%s' % (
        #                 cate, attr, sub
        #             )),
        #             'name': sub,
        #             "sub_categories": []
        #         }]

        #         if subsub is not None:
        #             cate_attr_dict[cate]['attrs'][attr]['subs'][0]['sub_categories'].append({
        #                 'abbr': util.mk_hash_12('%s|%s|%s|%s' % (
        #                     cate, attr, sub, subsub
        #                 )),
        #                 'name': subsub,
        #             })
        #     else:
        #         flag_found_this_sub = False
        #         for _idx, _sub in enumerate(cate_attr_dict[cate]['attrs'][attr]['subs']):
        #             if _sub['name'] == sub:

        #                 if subsub is not None: 
        #                     cate_attr_dict[cate]['attrs'][attr]['subs'][_idx]['sub_categories'].append({
        #                         'abbr': util.mk_hash_12('%s|%s|%s|%s' % (
        #                             cate, attr, sub, subsub
        #                         )),
        #                         'name': subsub,
        #                     })
        #                     idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['subs'][_idx]['sub_categories'][-1]['abbr']
        #                 else:
        #                     pass

        #                 flag_found_this_sub = True
        #                 break

        #         if flag_found_this_sub:
        #             continue

        #         cate_attr_dict[cate]['attrs'][attr]['subs'].append({
        #             'abbr': util.mk_hash_12('%s|%s|%s' % (
        #                 cate, attr, sub
        #             )),
        #             'name': sub,
        #             "sub_categories": []
        #         })

        #         if subsub is not None:
        #             cate_attr_dict[cate]['attrs'][attr]['subs'][-1]['sub_categories'].append({
        #                 'abbr': util.mk_hash_12('%s|%s|%s|%s' % (
        #                     cate, attr, sub, subsub
        #                 )),
        #                 'name': subsub,
        #             })

        #     if subsub is not None:
        #         idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['subs'][-1]['sub_categories'][-1]['abbr']
        #     else:
        #         # point the idx to the last sub in current attr
        #         idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['subs'][-1]['abbr']
        # else:
        #     # point the idx to the attr
        #     idx2abbr[idx] = cate_attr_dict[cate]['attrs'][attr]['abbr']
    
    # convert the dict to list
    cate_attr_list = []
    for _i in cate_attr_dict:
        cate = cate_attr_dict[_i]

        # special rule for COE risk of bias or indirectness
        # because this cate is just directly copied from settings.py
        # no need to convert again
        if cate['abbr'] == 'COE_RCT_ROB' or \
            cate['abbr'] == 'COE_RCT_IND': 
            cate_attr_list.append(cate)
            continue

        # put this cate
        _cate = {
            'abbr': cate['abbr'],
            'name': cate['name'],
            'attrs': []
        }

        for _j in cate['attrs']:
            attr = cate['attrs'][_j]
            # put this attr
            _attr = {
                'abbr': attr['abbr'],
                'name': attr['name'],
                'subs': []
            }

            for _k in attr['subs']:
                sub = attr['subs'][_k]
                _sub = {
                    'abbr': sub['abbr'],
                    'name': sub['name'],
                    'sub_categories': []
                }

                for _m in sub['sub_categories']:
                    subsub = sub['sub_categories'][_m]
                    _subsub = {
                        'abbr': subsub['abbr'],
                        'name': subsub['name'],
                        'sub_sub_categories': []
                    }

                    for _n in subsub['sub_sub_categories']:
                        subsubsub = subsub['sub_sub_categories'][_n]
                        _subsub['sub_sub_categories'].append(subsubsub)

                    _sub['sub_categories'].append(_subsub)

                _attr['subs'].append(_sub)

            _cate['attrs'].append(_attr)

        cate_attr_list.append(_cate)


    return cate_attr_dict, cate_attr_list, idx2abbr, name2idx, idx2name


def get_itable_filters_from_xls(keystr, full_fn):
    '''
    Get the filters from ITABLE_FILTER.xlsx
    '''
    # full_fn = os.path.join(
    #     current_app.instance_path, 
    #     settings.PATH_PUBDATA, 
    #     keystr, fn
    # )
    if not os.path.exists(full_fn):
        # try the xls file
        return []

    # load the data file
    import pandas as pd
    xls = pd.ExcelFile(full_fn)
    # load the Filters tab
    sheet_name = 'Filters'
    dft = xls.parse(sheet_name)

    # build Filters data
    ft_list = []
    for col in dft.columns[1:]:
        display_name = col
        tmp = dft[col].tolist()
        # the first line of dft is the column name / attribute name
        ft_attr = '%s' % tmp[0]

        if ft_attr == 'nan': continue

        # the second line of dft is the filter type: radio or select
        ft_type = ("%s" % tmp[1]).strip().lower()
        # get those rows not NaN, which means containing option
        ft_opts = dft[col][~dft[col].isna()].tolist()[3:]
        # get the default label
        ft_def_opt_label = ("%s" % tmp[2]).strip()

        # set the default option
        ft_item = {
            'display_name': display_name,
            'type': ft_type,
            'attr': ft_attr,
            'value': 0,
            'values': [{
                "display_name": ft_def_opt_label,
                "value": 0,
                "sql_cond": "{$col} is not NULL",
                "default": True
            }]
        }
        # build ae_name dict
        for i, ft_opt in enumerate(ft_opts):
            ft_opt = str(ft_opt)
            # remove the white space
            ft_opt = ft_opt.strip()
            ft_item['values'].append({
                "display_name": ft_opt,
                "value": i+1,
                "sql_cond": "{$col} like '%%%s%%'" % ft_opt,
                "default": False
            })

        ft_list.append(ft_item)
            
        print('* parsed ft_attr %s with %s options' % (ft_attr, len(ft_opts)))
    print('* created ft_list %s filters' % (len(ft_list)))

    return ft_list


def get_studies_included_in_ma(keystr, cq_abbr, paper_dict=None):
    '''
    Get the studies which are included in MA
    '''
    project = dora.get_project_by_keystr(keystr)
    if project is None:
        return None

    if paper_dict is None:
        # create a paper_dict
        papers = dora.get_papers_of_included_sr(project.project_id)
        paper_dict = {}
        for p in papers:
            paper_dict[p.pid] = p

    # get all oc of this project
    ocs = dora.get_extracts_by_keystr_and_cq(
        keystr,
        cq_abbr
    )

    # check each outcome
    # to fill this stat object
    stat = {
        'f3': {
            'pids': [],
            'rcts': [],
            'n': 0
        }
    }
    for oc in ocs:
        # 2022-01-19: fix the number issue
        # the itable should be excluded from the counting
        if oc.oc_type == 'itable':
            continue

        # 2023-06-19: fix the data issues
        oc = dora.attach_extract_data(oc)

        # check papaer extracted in this outcome
        for pid in oc.data:
            # 2022-01-17 fix the MA>SR issue
            # need to check whether this pid exists in papers
            if pid not in paper_dict:
                # which means this extraction is not linked with a paper,
                # maybe due to import issue or pid update.
                # so, just skip this
                continue

            # get the data
            p = oc.data[pid]

            if p['is_selected']:
                if pid in stat['f3']['pids']:
                    # this pid has been counted
                    pass
                else:
                    stat['f3']['n'] += 1
                    stat['f3']['pids'].append(pid)

                    # check the ctid
                    if pid in paper_dict:
                        rct_id = paper_dict[pid].get_rct_id()
                        if rct_id not in stat['f3']['rcts']:
                            stat['f3']['rcts'].append(rct_id)
                    else:
                        # what???
                        # if this pid not in paper_dict
                        # which means the rct info is missing
                        print('* ERROR missing %s in paper_dict' % (
                            pid
                        ))
                        pass

            else:
                # this paper is extracted but not selected yet.
                pass
    try:
        print("* generated stat_f3 %s/%s included in MA" % (
            stat['f3']['n'],
            len(paper_dict)
        ))
    except:
        pass

    return stat


def get_selected_pieces(extracts, papers):
    '''
    Get selected pieces according given extracts and selected papers
    '''
    pieces = dora.get_pieces_by_extracts_and_papers(
        extracts,
        papers
    )

    return pieces


def get_stat_outcomes(extracts):
    '''
    Get statistics on outcomes
    '''
    stat = {
        'total': len(extracts)
    }

    return stat


def get_duplicate_outcomes_from_extracts(extracts, concept_dict={}):
    '''
    Find duplicate outcome in the given extract list
    '''
    # save those duplicates (just index)
    dup_oc_idxes = set()

    # save duplicates (relations)
    # {
    #     abbr: [
    #       (abbr_dup_1, msg_1),
    #       (abbr_dup_2, msg_2),
    #       ...
    #     ],
    # }
    dup_ocs = {}

    # check all pairs
    for ext_i in range(len(extracts)):
        if ext_i in dup_oc_idxes:
            # which means this extract has been detected
            continue

        for ext_j in range(ext_i + 1, len(extracts)):
            if ext_j in dup_oc_idxes:
                # which means this extract has been detected
                continue

            # ok, let's compare 
            flag, msg = is_duplicated_outcome(
                extracts[ext_i],
                extracts[ext_j],
                concept_dict
            )

            if flag:
                # just put ext_j
                dup_oc_idxes.add(ext_i)
                dup_oc_idxes.add(ext_j)

                # save this dup ocs
                if extracts[ext_i].abbr not in dup_ocs:
                    dup_ocs[extracts[ext_i].abbr] = []

                dup_ocs[extracts[ext_i].abbr].append(
                    (extracts[ext_j].abbr, msg)
                )
    
    return dup_ocs


def is_duplicated_outcome(ext_a, ext_b, concept_dict={}):
    '''
    Judge whether duplicated

    concept_dict is a mapping from outcome name to a concept
    {
        'fever':            'fever',
        'pyrexia':          'fever',
        'high temperature': 'fever',
        'feverishness':     'fever',
    }
    by using this simple dictionary, we can identify 
    whether a name is duplicated with another simiar name
    '''
    # the easist case, by id
    if ext_a.extract_id == ext_b.extract_id:
        return True, 'same record'
    
    # then by meta info
    # if same oc_type, e.g., nma, pwma, itable
    #    same group, e.g., primary, second
    #    same category, e.g., other
    if ext_a.meta['oc_type'] == ext_b.meta['oc_type'] and \
        ext_a.meta['group'] == ext_b.meta['group'] and \
        ext_a.meta['category'] == ext_b.meta['category']:
        
        # first, get full name in lower case
        _fn_a = ext_a.meta['full_name'].lower().strip()
        _fn_b = ext_b.meta['full_name'].lower().strip()

        if _fn_a == _fn_b:
            return True, 'same name'
        
        else:
            # check same concept
            cpt_a = concept_dict.get(_fn_a, None)
            cpt_b = concept_dict.get(_fn_b, None)

            if cpt_a is not None and \
                cpt_b is not None and \
                cpt_a == cpt_b:
                # which means there 
                return True, 'same concept'

    return False, ''


def get_data_quality(project_id, cq_abbr):
    '''
    Get a report of data quality
    '''
    project = dora.get_project(project_id)

    # get all extracts withOUT data
    extracts = dora.get_extracts_by_project_id_and_cq(
        project_id,
        cq_abbr
    )

    # create a dict for report
    report = {}

    # get all papers included
    papers = srv_paper.get_included_papers_by_cq(
        project_id, 
        cq_abbr
    )
    paper_dict = {}
    for paper in papers:
        paper_dict[paper.pid] = paper

    for ext_idx, extract in enumerate(extracts):
        # first, add data
        extract = dora.attach_extract_data(extract)

        # now let's check
        n_issue_papers = 0
        for pid in extract.data:
            if pid not in paper_dict:
                # which means this paper is not included in SR
                continue

            if pid not in report:
                # add this pid to report and create basic structure
                report[pid] = {
                    # first, we need to know what issues are there
                    # and there are multiply issues. So just check it.
                    'issues': {}
                }

            # ok, now let's check this extraction
            if not extract.data[pid]['is_selected']:
                # ok, this paper is not selected
                continue

            # now let's check issues
            issues = check_extract_piece_quality(extract, extract.data[pid])

            # then update the issues if any
            if len(issues) > 0:
                report[pid]['issues'][extract.abbr] = issues
                n_issue_papers += 1

        print('* parsed %s/%s extract data quality %s' % (
            ext_idx+1,
            len(extracts),
            n_issue_papers
        ))
    
    return report


def check_extract_piece_quality(extract, piece_data):
    '''
    Check the quality of a piece in an extract,

    Returns an issue report if found any.
    Otherwise returns None.
    '''
    # special rule for itable checking
    if extract.oc_type == 'itable':
        return check_extract_piece_quality_for_ITABLE(extract, piece_data)
    
    # for IO-like projects
    if extract.meta['input_format'] == 'PRIM_CAT_RAW_G5':
        return check_extract_piece_quality_for_PRIM_CAT_RAW_G5(extract, piece_data)
    
    # TODO, other data formats
    return []


def check_extract_piece_quality_for_ITABLE(extract, piece_data):
    '''
    A subtype of data quality for iTable extraction

    check missing attributes only
    '''
    # only one subg in itable
    subg = 'g0'
    issues = []
    # need to walk all attrs in extract
    for arm_idx, arm in enumerate([piece_data['attrs']['main']] + \
                                   piece_data['attrs']['other']):
        attrs_empty = []
        for cate in extract.meta['cate_attrs']:
            if cate['abbr'] == 'COE_RCT_ROB':
                # skip the COE Risk of Bias as there should be missing
                continue

            if cate['abbr'] == 'COE_RCT_IND':
                # skip the COE Indirectness as there should be missing
                continue

            if cate['name'] == '_SYS':
                # skip the system search attribute
                continue

            for attr in cate['attrs']:
                if attr['subs'] is None:
                    if attr['abbr'] not in arm[subg]:
                        # which means this value is not there yet
                        attrs_empty.append({
                            'name': attr['name'],
                            'abbr': attr['abbr']
                        })
                        continue

                    # then, just check this attr
                    value = arm[subg][attr['abbr']]
                    if util.is_missing(value):
                        attrs_empty.append({
                            'name': attr['name'],
                            'abbr': attr['abbr']
                        })
                else:
                    # there are multiple subs
                    for sub in attr['subs']:
                        if sub['abbr'] not in arm[subg]:
                            # which means this value is not there yet
                            attrs_empty.append({
                                'name': attr['name'] + '#' + sub['name'],
                                'abbr': sub['abbr']
                            })
                            continue

                        # ok, there is value!
                        value = arm[subg][sub['abbr']]
                        if util.is_missing(value):
                            attrs_empty.append({
                                'name': attr['name'] + '#' + sub['name'],
                                'abbr': sub['abbr']
                            })

        # make a single issue
        if len(attrs_empty) == 0:
            pass
        else:
            issues.append({
                'arm_idx': arm_idx,
                'subg': subg,
                'attr': None,
                'value': None,
                'reason': 'Missing values in %s attributes [%s]' % (
                    len(attrs_empty),
                    ', '.join([ a['name'] for a in attrs_empty ])
                )
            })
    
    return issues


def check_extract_piece_quality_for_PRIM_CAT_RAW_G5(extract, piece_data):
    '''
    A subtype of data quality for PRIM_CAT_RAW_G5 format

    In this format, there are 10 attrs to be checked
    '''
    attrs_emp_or_int = [
        'GA_Et', 'GA_Nt', 'GA_Ec', 'GA_Nc', 
        'G34_Et', 'G34_Ec', 
        'G3H_Et', 'G3H_Ec',
        'G5N_Et', 'G5N_Ec',
    ]

    # those attrs must be greater than 0
    attrs_gtzero = ['GA_Nt', 'GA_Nc']

    # pairs must be match is not empty
    attrs_pwmable = [
        ['GA_Et', 'GA_Nt'],
        ['GA_Ec', 'GA_Nc'],
        ['G34_Et', 'GA_Nt'],
        ['G34_Ec', 'GA_Nc'],
        ['G3H_Et', 'GA_Nt'],
        ['G3H_Ec', 'GA_Nc'],
        ['G5N_Et', 'GA_Nt'],
        ['G5N_Ec', 'GA_Nc'],
    ]

    for arm_idx, arm in enumerate([piece_data['attrs']['main']] + \
                                   piece_data['attrs']['other']):
        # check all arms, and this format only contains g0 for now
        # TODO, add other groups later
        # by default, no issue at all
        issues = []

        # check subg
        subg = 'g0'

        # first, all numbers must be empty or integer
        for attr in attrs_emp_or_int:
            # get the value of this attr
            value = arm[subg][attr]

            # flag 1: is empty?
            f1 = util.is_empty(value)

            # flag 2: is integer?
            f2 = util.is_integer(value)

            if f1 or f2:
                # ok, it works
                pass

            else:
                # oh, no. it's a value that cannot be parsed
                issue = {
                    'arm_idx': arm_idx,
                    'subg': subg,
                    'attr': attr,
                    'value': value,
                    'reason': 'Unparsable non-empty and non-integer value'
                }

                issues.append(issue)

        # second, non-zero value for Nt and Nc
        for attr in attrs_gtzero:
            # get the value of this attr
            value = arm[subg][attr]

            # flag 1: is integer?
            f1 = util.is_integer(value)

            # flag 2: is zero
            f2 = util.is_int_zero(value)

            if f1 and f2:
                # oh ... any of the N is zero
                issue = {
                    'arm_idx': arm_idx,
                    'subg': subg,
                    'attr': attr,
                    'value': value,
                    'reason': 'Total number cannot be zero'
                }

                issues.append(issue)

        # last, pairs
        for attr_pair in attrs_pwmable:
            # get the value of this attr
            value0 = arm[subg][attr_pair[0]]
            value1 = arm[subg][attr_pair[1]]

            # flag: v0 > v1 ?
            f1 = util.is_E_gt_N(value0, value1)

            if f1:
                # what???
                issue = {
                    'arm_idx': arm_idx,
                    'subg': subg,
                    'attr': attr,
                    'value': 'E=%s, N=%s' % (value0, value1),
                    'reason': 'Event cannot be greater than total'
                }

                issues.append(issue)

        return issues


###########################################################
# Utils for management
###########################################################

def delete_all_extracts_and_pieces_by_keystr(keystr, cq_abbr, oc_type='all'):
    '''
    Delete all by keystr
    '''
    project = dora.get_project_by_keystr(keystr)

    if oc_type == 'all':
        extracts = dora.get_extracts_by_keystr_and_cq(keystr, cq_abbr)
    else:
        extracts = dora.get_extracts_by_keystr_and_cq_and_oc_type(keystr, cq_abbr, oc_type)

    for idx, extract in enumerate(extracts):
        print('* deleting %s/%s extracts [%s]' % (
            idx+1,
            len(extracts),
            extract.meta['full_name']
        ))
        delete_extract_and_pieces(project.project_id, extract.extract_id)

    print('* deleted all extracts!')


def delete_all_extracts_and_pieces(project_id, cq_abbr):
    '''
    Delete all extracts and related pieces
    '''
    extracts = dora.get_extracts_by_project_id_and_cq(project_id, cq_abbr)

    for idx, extract in enumerate(extracts):
        print('* deleting %s/%s extracts [%s]' % (
            idx+1,
            len(extracts),
            extract.meta['full_name']
        ))
        delete_extract_and_pieces(project_id, extract.extract_id)

    print('* deleted all extracts!')


def delete_extract_and_pieces(project_id, extract_id):
    '''
    Delete an extract and related pieces
    '''
    # delete all pieces
    _ = Piece.query.filter(
        Piece.project_id == project_id,
        Piece.extract_id == extract_id
    ).delete(synchronize_session=False)

    db.session.commit()

    Extract.query.filter(
        Extract.extract_id == extract_id
    ).delete(synchronize_session=False)

    db.session.commit()

    return 0


def reset_extracts_includes(keystr, cq_abbr, include_in, yes_or_no):
    '''
    Reset all extracts' include in 
    '''
    extracts = dora.get_extracts_by_keystr_and_cq(keystr, cq_abbr)

    for ext in tqdm(extracts):
        if include_in == 'plots':
            ext.meta['included_in_plots'] = yes_or_no            
            flag_modified(ext, 'meta')
            db.session.add(ext)
            db.session.commit()

        elif include_in == 'sof':
            ext.meta['included_in_sof'] = yes_or_no
            flag_modified(ext, 'meta')
            db.session.add(ext)
            db.session.commit()

        else:
            pass

    print('* done reset')


def _parse_attr_column_with_abbr(input_string):
    parts = input_string.split(';')

    # Create an empty dictionary to store the results
    result_dict = {}

    # Loop through the parts
    for part in parts:
        # Split each part at the equals sign to separate keys and values
        key, value = part.split('=')

        # remove any white space
        key = key.strip()
        value = value.strip()

        # Add the key-value pair to the dictionary
        result_dict[key] = value

    return result_dict


def _is_item_in_list(item, rs):
    '''
    Check whether a name in a rs list
    '''
    for idx, r in enumerate(rs):
        if item == r['name']:
            return True, idx
    
    return False, -1
    


def __get_val(v, default_value=''):
    '''
    Helper function for getting values from df cell
    '''
    if pd.isna(v): 
        return default_value
    return str(v).strip()


def __get_int_val(v, default_value=''):
    '''
    Helper function for getting the int value
    '''
    if pd.isna(v): 
        return default_value
    try:
        val = str(int(float(v)))
        return val
    except:
        return v


def __get_col(row, col):
    '''
    Helper function for getting values from df row by column name
    '''
    if col not in row.keys():
        return None
    
    else:
        return row[col]


def __get_pid(v):
    '''
    Helper function for pid
    '''
    try:
        pid = str(int(float(v)))
        return pid
    except:
        return ("%s"%v).strip().lower()


def __cie_imp2val(v):
    '''
    Helper function for the cie importance
    '''
    if v is None: return '0'
    _v = '%s' % v
    _v = _v.lower().strip()

    if _v == 'critical': 
        return '2'

    elif _v == 'important':
        return '1'

    else:
        return v
    

def __format_itable_coe_rob(v):
    if v is None: return 'NA'

    _v = v.lower()
    return {
        'l': 'L',
        'm': 'M',
        'h': 'H',
        'na': 'NA',

        'low risk': 'L',
        'some concerns': 'M',
        'high risk': 'H',
        'not decided': 'NA'
    }.get(_v, 'NA')
    

def __format_itable_coe_ind(v):
    if v is None: return 'NA'

    _v = v.lower()
    return {
        'v': 'V',
        'm': 'M',
        'n': 'N',
        'na': 'NA',

        'very close': 'V',
        'moderately close': 'M',
        'not close': 'N',
        'not decided': 'NA'
    }.get(_v, 'NA')