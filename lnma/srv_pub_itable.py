import os
import json
import pandas as pd

from flask import current_app

from lnma import dora
from lnma import srv_extract
from lnma import util
from lnma import settings

from lnma import srv_project

def get_itable_json(keystr, cq_abbr):
    '''
    Make ITABLE.json
    '''
    # get the cache path
    output_fn = 'ITABLE.json'
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
    ret = get_itable_attr_rs_cfg_from_db(
        keystr, 
        cq_abbr,
        True
    )
    latest = srv_project.get_project_latest_stat_by_keystr(keystr)
    ret['latest'] = latest

    # catch the result
    json.dump(ret, open(full_output_fn, 'w'), default=util.json_encoder)
    print('* generated ITABLE.json at %s' % (full_output_fn))

    return ret


def get_itable_attr_rs_cfg_from_db(keystr, cq_abbr="default", with_extract=False):
    '''
    Get everything related to itable from db
    '''
     # get the paper data as well
    # the itable is a special extract for this project

    project = dora.get_project_by_keystr(keystr)
    if project is None:
        return None

    project_id = project.project_id

    # get the extract
    extract = srv_extract.get_itable_by_project_id_and_cq_abbr(
        project_id, cq_abbr
    )
    if extract is None:
        return None
    

    # Muneeb cpmmenting this line when uploading itable should given the priority 
    # 2023-03-30: add data
    # extract = dora.attach_extract_data(extract)

    # get the papers for this project
    papers = dora.get_papers_of_included_sr(project_id)
    print('* found %s papers included in SR' % (
        len(papers)
    ))
    paper_dict = {}
    for p in papers:
        paper_dict[p.pid] = p
    print('* created paper_dict based on %s papers' % (
        len(papers)
    ))

    cq_papers = dora.get_papers_of_included_sr_and_cq(
        project_id,
        cq_abbr
    )
    print('* found %s papers included in cq[%s]' % (
        len(cq_papers),
        cq_abbr
    ))

    # create a original/followup
    cq_rcts = util.sort_rct_seq(cq_papers)

    # this is for output as some papers are not selected for output
    selected_paper_dict = {}

    # get the stat selected for itable
    # stat = {
    #     'f3': {
    #         'pids': [],
    #         'rcts': [],
    #         'n': 0
    #     }
    # }
    stat_f3 = srv_extract.get_studies_included_in_ma(
        keystr, 
        cq_abbr,
        paper_dict
    )
    if stat_f3 is None:
        stat_f3 = []
    else:
        stat_f3 = stat_f3['f3']['pids']

    # get the extract meta and data
    meta = extract.meta
    data = extract.data

    # the data needed for the itable frontend
    rs = []
    cfg = {}
    attrs = []
    index=0
    abbr2attr_name = {}
    trial_name = {}
    # convert the format for attrs
    for cate in meta['cate_attrs']:
        for attr in cate['attrs']:
            index = index +1
            if attr['subs'] is None or attr['subs'] == []:
                attr_name = "%s" % attr['name']
                attr_id = ("_%s|%s" % (attr['name'], attr['name'])).upper()
                abbr2attr_name[attr['abbr']] = attr_name
                
                if(attr['name'].split() == 'Trial Name'.split()):
                    trial_name = {
                        "attr_id": attr_id, 
                        "branch": "%s" % attr['name'], 
                        "cate": "%s" % cate['name'], 
                        "name": attr_name, 
                        "trunk": "_%s" % attr['name'], 
                        "vtype": "text",
                    }
                    print(f'attr name is being printed {attr["name"]}')
                else:
                    attrs.append({
                        "attr_id": attr_id, 
                        "branch": "%s" % attr['name'], 
                        "cate": "%s" % cate['name'], 
                        "name": attr_name, 
                        "trunk": "_%s" % attr['name'], 
                        "vtype": "text",
                    })

            else:
                for sub in attr['subs']:
                    attr_name = "%s | %s" % (attr['name'], sub['name'])
                    attr_id = ("%s|%s" % (attr['name'], sub['name'])).upper()
                    abbr2attr_name[sub['abbr']] = attr_name
                    sub_categories_length = 0 
                    sub_length = 0
                    sub_branches = []
                    sub_sub_branches = []
                    if sub.get('sub_categories') is None :
                        sub_categories_length = 1
                    else:
                       sub_categories_length = len(sub.get('sub_categories')) or 1
                    if attr.get('subs') is None:
                        sub_length = 1
                    else:
                        sub_length = len(attr.get('subs')) 

                           # Add Sub Category for further nested Level update August 2023 Update (by Muneeb)
                    if sub.get('sub_categories') is None or sub.get('sub_categories') == []:
                        sub_branches = [] 
                    else:
                        sub_b = []
                        for sub_c in sub['sub_categories']:
                            attr_name = " %s | %s | %s" % ( attr['name'], sub['name'], sub_c['name'])
                            attr_id = ("%s|%s|%s" % (attr['name'], sub['name'], sub_c['name'])).upper()
                            abbr2attr_name[sub_c['abbr']] = attr_name
                            
                            if sub_c.get('sub_sub_categories') is None or sub_c.get('sub_sub_categories') == []:
                                sub_sub_branches = [] 
                            else:
                                sub_sub_b = []
                                for sub_sub_c in sub_c['sub_sub_categories']:
                                    attr_name = " %s | %s | %s | %s" % ( attr['name'], sub['name'], sub_c['name'],
                                    sub_sub_c['name'])
                                    attr_id = ("%s|%s|%s|%s" % (attr['name'], sub['name'], sub_c['name'], 
                                    sub_sub_c['name'])).upper()
                                    abbr2attr_name[sub_sub_c['abbr']] = attr_name
                                    sub_sub_b.append({"attr_id": attr_id, 
                                        "branch": "%s" % sub_sub_c['name'], 
                                        "cate": "%s" % cate['name'], 
                                        "name": attr_name, 
                                        "trunk": "%s" % attr['name'], 
                                        "vtype": "text",
                                        "sub_category": True,
                                        "sub__sub_category": True,
                                        "sub_parent": sub_c['name'],
                                        "index_attr": index
                                        })
                                sub_sub_branches = sub_sub_b
                                
                            # attr_name = " %s | %s | %s" % ( attr['name'], sub['name'], sub_c['name'])
                            # attr_id = ("%s|%s|%s" % (attr['name'], sub['name'], sub_c['name'])).upper()
                            # abbr2attr_name[sub_c['abbr']] = attr_name

                            sub_b.append({
                                "attr_id": attr_id, 
                                "branch": "%s" % sub_c['name'], 
                                "cate": "%s" % cate['name'], 
                                "name": attr_name, 
                                "trunk": "%s" % attr['name'], 
                                "vtype": "text",
                                "sub_category": True,
                                "sub_parent": sub['name'],
                                "index_attr": index,
                                "sub_sub_branches": sub_sub_branches
                            })
                        sub_branches = sub_b


                    attrs.append({
                        "attr_id": attr_id, 
                        "branch": "%s" % sub['name'], 
                        "cate": "%s" % cate['name'], 
                        "name": attr_name, 
                        "trunk": "%s" % attr['name'], 
                        "vtype": "text",
                        "sub_categories_length": sub_categories_length,
                        "sub_length": sub_length,
                        "sub_branches": sub_branches
                    })

                    for sub in sub_branches:
                        print("@@@@@@@@@@@@@@@@@@")
                        print(sub)
                        attrs.append(sub)
                        for sub_c in sub['sub_sub_branches']:
                            attrs.append(sub_c)

                        
             
    # after the attributes in the `extract.meta`, which are customized for itable,
    # need to add those "basic" attributes, which just some information for paper.
    basic_attrs = [
    { 'abbr': 'ba_included_in_ma', 'name': 'Included in MA', },
    # { 'abbr': 'ba_ofu', 'name': 'Original/Follow Up',        },
    { 'abbr': 'ba_year', 'name': 'Year',                     },
    { 'abbr': 'ba_authors', 'name': 'Authors',               },
    { 'abbr': 'ba_pmid', 'name': 'PMID',                     },
    { 'abbr': 'ba_nct', 'name': 'NCT',                       },
]

       

    first_cate = attrs[0]['cate']
    for attr in basic_attrs:
        attr_name = "%s" % attr['name']
        attr_id = ("_%s|%s" % (attr['name'], attr['name'])).upper()
        abbr2attr_name[attr['abbr']] = attr_name
        attrs.insert(0, {
            "attr_id": attr_id, 
            "branch": "%s" % attr['name'], 
            "cate": first_cate, 
            "name": attr_name, 
            "trunk": "_%s" % attr['name'], 
            "vtype": "text"
        })
    # for trail name  insert at 3rd position
    if trial_name:
        attrs.insert(2, trial_name)
        
    
    # 2021-08-08: to insert the data from other arms
    # we abstract the function for getting `r`
    def _make_r(paper_data, abbr_dict, arm_idx=0):
        '''
        arm_idx is 0 means it's the main
        otherwise it means it's multi arm
        '''
        # `r` use name as key to retrive data, 
        # which is used in the itable.html.
        # but the case here is quite complex, the multi-arm issue
        # let's append the main track
        # the paper_ext is a dictionary:
        # 2021-08-08: the data structure in extracted data have been updated
        # for itable, there is only one group `g0` in all arms
        #
        # {
        #    'attrs': {
        #         'main': {
        #              g0: {
        #                   abbr: value
        #              }
        #         },
        #         'other': [{
        #              g0: {
        #                   abbr: value
        #              }
        #         }]
        #    }
        #    'n_arms':
        #    'is_checked':
        #    'is_selected':
        # }
        #
        # So, please check the data carefully.
        # 2023-03-30: for multi-arm study
        # we also need to add some information about the arm
        r = {
            '_arm_idx': arm_idx
        }

        for abbr in abbr_dict:
            attr_name = abbr_dict[abbr]
            if abbr in paper_data:
                r[attr_name] = paper_data[abbr]
            else:
                # in most case, the value should be there
                # but ... you know ... I don't know what happens
                # just give an empty value to avoid any issue in rendering
                r[attr_name] = ''

        # add the basic features
        for attr in basic_attrs:
            attr_name = "%s" % attr['name']
            if attr['abbr'] == 'ba_year':
                val = paper.get_year()
            elif attr['abbr'] == 'ba_authors':
                # the author name maybe different format, use paper instead of `r`
                auetal = util.get_author_etal_from_paper(paper)

                # add some information of other arms
                if arm_idx > 0:
                    val = auetal + ' (Comp %s)' % (arm_idx + 1)
                else:
                    val = auetal

            elif attr['abbr'] == 'ba_ofu':
                # 2022-02-27: use the cq level pid and nct
                # val = paper.get_study_type()
                val = settings.PAPER_STUDY_TYPE_ORIGINAL
                _rct = paper.meta['rct_id']
                if _rct in cq_rcts:
                    if paper.pid in cq_rcts[_rct]['rct_seq']:
                        if cq_rcts[_rct]['rct_seq'][paper.pid] > 0:
                            val = settings.PAPER_STUDY_TYPE_FOLLOWUP

            elif attr['abbr'] == 'ba_pmid':
                # val = paper.pid
                # 2023-01-18 after added the ds_id in meta
                # the pid may not be the PMID
                # so need to get the PMID from meta.ds_id
                val = util.get_paper_pmid_if_exists(paper)['id']

            elif attr['abbr'] == 'ba_nct':
                val = paper.meta['rct_id']

            elif attr['abbr'] == 'ba_included_in_ma':
                val = 'yes' if paper.pid in stat_f3 else 'no'

            else:
                val = 'NA'

            r[attr_name] = val

        return r

    # now convert the records
    # first, we need to understand that, maybe not all of the f1, f2, and f3
    # are used in the itable, the only way to decide that is the `is_selected`
    # flag in the `extract.data`.
    # so, when getting the `rs`, the main loop is to get the studies
    if keystr == 'LPR':
        if data.get('37142371'):
            data['37142371']['attrs']['main']['g0']['FD62EFD5662E'] = 'E+AAP+ADT'
            data['37142371']['attrs']['main']['g0']['D497B247EF62'] = 'ARPI'
            data['37142371']['attrs']['main']['g0']['7AB539ED4DCA'] = 'ARPI'
            
            

    for pid in data:
        paper_ext = data[pid]
        print("if this paper is selected or not ", pid, paper_ext['is_selected'])
        
        if paper_ext['is_selected'] == False: continue

        # now, let's parse this paper
        # paper = dora.get_paper_by_project_id_and_pid(project_id, pid)
        if pid not in paper_dict:
            # what???
            print('* MISSING %s when building ITABLE.json' % pid)
            continue

        # get this paper from dict instead of SQL
        paper = paper_dict[pid]

        # add this paper to dict for output
        selected_paper_dict[pid] = paper.as_extreme_simple_dict()
        
        # the `r` is for the output
        # first, let's get the main arm
        r = _make_r(
            paper_ext['attrs']['main']['g0'], 
            abbr2attr_name, 
            0
        )
        rs.append(r)

        # check other arms
        if paper_ext['n_arms'] > 2:
            # ok, multi-arms!
            for arm_idx in range(paper_ext['n_arms'] - 2):
                r = _make_r(
                    paper_ext['attrs']['other'][arm_idx]['g0'], 
                    abbr2attr_name,
                    # arm_idx starts with 0, so need to add 1
                    arm_idx + 1
                )
                rs.append(r)
        
    # cols for display
    cfg['cols'] = {
        'default': ['Authors'],
        'fixed': ['Authors']
    }
    # add the default attrs
    if 'default_attrs' in meta:
        cfg['cols']['default'] += meta['default_attrs']
    
    # last thing is the filter
    # filter is in the meta
    # add the filters
    if 'filters' in meta:
        cfg['filters'] = meta['filters']
    else:
        cfg['filters'] = []

    # add the default filter All 
    for filter in cfg['filters']:
        if 'ALL' not in filter['values'][0]['display_name'].upper():
            filter['values'].insert(0, {
                'default': True,
                'display_name': 'All',
                'sql_cond': '1=1',
                'value': 0
            })

    # add the raw extract if needed
    if with_extract:
        ext_dict = extract.as_dict()
    else:
        ext_dict = {}

    # finally, finished!
    ret = {
        'rs': rs,
        'cfg': cfg,
        'attrs': attrs,
        'paper_dict': selected_paper_dict,
        'itable': ext_dict
    }

    return ret


def get_attr_pack_from_itable(full_fn):
    # read data, hope it is xlsx format ...
    if full_fn.endswith('csv'):
        df = pd.read_csv(full_fn, header=None, nrows=2)
    else:
        df = pd.read_excel(full_fn, header=None, nrows=2)
    # convert to other shape
    dft = df.T
    df_attrs = dft.rename(columns={0: 'cate', 1: 'name'})

    # not conver to tree format
    attr_dict = {}
    attr_tree = {}

    for idx, row in df_attrs.iterrows():
        vtype = 'text'
        name = row['name'].strip()
        cate = row['cate'].strip()

        # split the name into different parts
        name_parts = name.split('|')
        if len(name_parts) > 1:
            trunk = name_parts[0].strip()
            branch = name_parts[1].strip()
        else:
            trunk = '_' + name
            branch = name
        attr_id = trunk.upper() + '|' + branch.upper()

        if cate not in attr_tree: attr_tree[cate] = {}
        if trunk not in attr_tree[cate]: attr_tree[cate][trunk] = []

        attr = {
            'name': name,
            'cate': cate,
            'vtype': vtype,
            'trunk': trunk,
            'branch': branch,
            'attr_id': attr_id,
        }
        # pprint(attr)

        # put this item into dict
        attr_tree[cate][trunk].append(attr)
        attr_dict[attr_id] = attr

    return { 'attr_dict': attr_dict, 'attr_tree': attr_tree }