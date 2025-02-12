from lnma.models import Paper
import logging
import os
import sys
import io
import json
import uuid
from collections import OrderedDict
from pprint import pprint
import traceback

from flask import request
from flask import flash
from flask import render_template
from flask import Blueprint
from flask import send_file
from flask import send_from_directory
from flask import current_app
from flask import jsonify

from flask_login import login_required
from flask_login import current_user
from matplotlib.pyplot import broken_barh

import pandas as pd
import numpy as np

from .analyzer import rplt_analyzer
from .analyzer import pwma_analyzer_v2 as pwma_analyzer
from .analyzer import nma_analyzer

from lnma import settings, ss_state
from lnma import util
from lnma import dora

from lnma import srv_extract
from lnma import srv_project
from lnma import srv_paper
from lnma import srv_pub_itable
from lnma import srv_pub_prisma
from lnma import srv_pub_pwma
from lnma import srv_pub_nma
from lnma import srv_deduplicate


import PythonMeta as PWMA

DEFAULT_EXTERNAL_VAL = 0

bp = Blueprint("pub", __name__, url_prefix="/pub")


@bp.route('/')
def index():
    return render_template('pub/index.html')


@bp.route('/blankindex')
def blankindex():
    return render_template('pub/blankindex.html')


@bp.route('/jsdebug.html')
def jsdebug():
    return render_template('pub/jsdebug.html')


@bp.route('/subindex/<prj>')
def subindex(prj):
    prj_data = {
        'CAT': { 'prj': 'CAT', 'title': 'Cancer Associated Thrombosis'},
        'RCC': { 'prj': 'RCC', 'title': 'Metastatic Renal Cell Cancer'},
        'IO': { 'prj': 'IO', 'title': 'Toxicity of Immune'},
        'ADJRCC': { 'prj': 'ADJRCC', 'title': 'Adjuvant Renal Cell Carcinoma'},
    }[prj]
    return render_template('pub/subindex.html', prj_data=prj_data)


@bp.route('/php.html')
def php():
    '''
    The project homepage for a cq
    '''
    # first, check this prj and cq exist or not
    keystr = request.args.get('k')
    cq_abbr = request.args.get('c')
    tpl_name = request.args.get('t')
    web_version = request.args.get('web_v')

    if tpl_name is None or tpl_name == '':
        tpl_name = 'index'
    else:
        pass
    # get this project
    project = dora.get_project_by_keystr(keystr)

    if project is None:
        return 'No such project %s' % keystr

    path_to_homepage = 'pub/%s/%s/%s.html' % (
        keystr, cq_abbr, tpl_name
    )
    # TODO need to check the file availability here
    # this template name may not exist
    
    # last, check this path exists or not
    # if not os.path.exists(os.path.join()):
    year = util.get_current_year_str()

    # for the sorting 
    # full_fn_sorted_texts = os.path.join(
    #     current_app.instance_path, 
    #     settings.PUBLIC_PATH_PUBDATA, 
    #     keystr, 
    #     cq_abbr,
    #     'SORTED_TEXTS.json'
    # )
    
    # if os.path.exists(full_fn_sorted_texts):
    #     pass
    #     sorted_texts = json.load(
    #         open(full_fn_sorted_texts, encoding='utf8')
    #     )
    # else:
    #     sorted_texts = {}
    if 'sorted_texts' in project.settings:
        sorted_texts = project.settings['sorted_texts']
    else:
        sorted_texts = {}
    list_ = []
    if 'website_version' in project.settings:
        if project.settings['website_version'].get(cq_abbr):
            list_ = project.settings['website_version'][cq_abbr]
    else:
        list_ =[]

    return render_template(
        path_to_homepage,
        keystr=keystr,
        cq_abbr=cq_abbr,
        project=project,
        year=year,
        web_version=web_version,
        sorted_texts=sorted_texts,
        version_list = json.dumps(list_)
    )

@bp.route('/sp.html')
def sp():
    '''
    Static page
    '''
    keystr = request.args.get('prj')
    cq_abbr = request.args.get('cq')
    fn = request.args.get('fn')

    path_to_static_page = 'pub/%s/%s/%s' % (
        keystr,
        cq_abbr,
        fn
    )

    # TODO ensure the file exists

    return render_template(
        path_to_static_page
    )


@bp.route('/decision_aid.html')
def decision_aid():
    '''
    The decision_aid page for a cq
    '''
    # first, check this prj and cq exist or not
    keystr = request.args.get('k')
    cq_abbr = request.args.get('c')
    
    # get this project
    project = dora.get_project_by_keystr(keystr)

    if project is None:
        return 'No such project %s' % keystr

    path_to_webpage = 'pub/%s/%s/decision_aid.html' % (
        keystr, cq_abbr
    )
    # last, check this path exists or not
    # if not os.path.exists(os.path.join(, path_to_webpage)):
        # return 'No such webpage for %s.%s' % (keystr, cq_abbr)

    year = util.get_current_year_str()

    return render_template(
        path_to_webpage,
        keystr=keystr,
        cq_abbr=cq_abbr,
        project=project,
        year=year
    )


@bp.route('/methods.html')
def lnma_methods():

    year = util.get_current_year_str()

    return render_template(
        'pub/methods.html',
        year=year
    )


@bp.route('/hub.html')
def lnma_hub():

    year = util.get_current_year_str()

    return render_template(
        'pub/hub.html',
        year=year
    )


###############################################################################
# For IO project
# Every thing is special designed
###############################################################################

# @bp.route('/IO.html')
# def static_IO():
#     prj = 'IO'
#     return render_template('pub/IO/pub.IO.html')


# @bp.route('/IOTOX.html')
# def IOTOX():
#     prj = 'IOTOX'
#     return render_template('pub/pub.IOTOX.html')


# @bp.route('/IO/default/index.html')
# def pub_IO_default_index():
#     '''
#     The index page for IO default project
#     '''
#     return render_template('pub/IO/default/index.html')


@bp.route('/prisma_IO.html')
def prisma_IO():
    '''
    A special PRISMA for IOTOX project
    The looking is different from others
    '''
    return render_template('pub/IO/prisma_IO.html')


@bp.route('/rtpma_IO.html')
def rtpma_IO():
    return render_template('pub/IO/rtpma_IO.html')


@bp.route('/rtpma.html')
def rtpma():
    return render_template('pub/IO/rtpma_IO.html')


@bp.route('/graph_pma_IO.html')
def graph_pma_IO():
    return render_template('pub/IO/graph_pma_IO.html')


@bp.route('/va_pma_IO.html')
def va_pma_IO():
    return render_template('pub/IO/va_pma_IO.html')


# a demo page for poster
@bp.route('/pwma_va_demo.html')
def pwma_va_demo():
    return render_template('pub/IO/pwma_va_demo.html')


@bp.route('/softable_pma_IO.html')
def softable_pma_IO():
    # return render_template('pub/IO/softable_pma_IO_by_metajs.html')
    return render_template('pub/IO/softable_pma_IO.html')


###########################################################
# Modules for public page
###########################################################

@bp.route('/prisma.html')
@bp.route('/prisma_hybrid.html')
def prisma():
    return render_template('pub/prisma_hybrid.html')


@bp.route('/prisma_living.html')
def prisma_living():
    return render_template('pub/prisma_living.html')


@bp.route('/itable')
@bp.route('/itable.html')
def itable():
    return render_template('pub/itable.html')

@bp.route('/itable_v2')
@bp.route('/itable_v2.html')
def itable_v2():
    return render_template('pub/itable_v2.html')

@bp.route('/graph_pma_v2')
@bp.route('/graph_pma_v2.html')
def graph_pma_v2():
    return render_template('pub/graph_pma_v2.html')


@bp.route('/result_table_pub_check')
@bp.route('/result_table_pub_check.html')
def result_table_pub_check():
    keystr = request.args.get('prj')
    cq_abbr = request.args.get('cq')


    project =  dora.get_project_by_keystr(keystr)

    keys_list = project.settings.get('clinical_question_result_table')
    list_ = []

    if project.settings.get('clinical_question_result_table'):
        if project.settings.get('clinical_question_result_table').get(cq_abbr):
            if project.settings.get('clinical_question_result_table').get(cq_abbr).get('cate_attrs_relations'):
                keys_list = project.settings.get('clinical_question_result_table').get(cq_abbr).get('cate_attrs_relations')
                for key in keys_list:
                    for i, j in key.items():
                        list_.append(i)
    

    if project.settings.get('clinical_question_result_table'):

        if project.settings.get('clinical_question_result_table').get(cq_abbr):
            return render_template(
            'extractor/result_table_pub_check.html',
            project_json_str=list_,
            cq_abbr=cq_abbr,
            project=project,
            comaparator_name=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('comaparator_name')),
            varaiable_name=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('varaiable_name')), 
            abbr_list_updated=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('abbr_list_updated')),
            headers_result=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('cate_attrs_relations')),
            rows_result=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('result_table_records')),
            rows_result_seq=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('result_table_records_seq')),
            rows_headers_mapping=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('parent_nested_realtion'))
            )
        else:
            return render_template(
            'extractor/result_table_pub_check.html',
            cq_abbr=cq_abbr,
            project=project,
            headers_result={},
            rows_result={},
            rows_headers_mapping={}
            )

    
    else:

        return render_template(
            'extractor/result_table_pub_check.html',
            cq_abbr=cq_abbr,
            project=project,
            headers_result={},
            rows_result={},
            rows_headers_mapping={}
        )

    



@bp.route('/result_table_pub')
@bp.route('/result_table_pub.html')
def result_table_pub():
    keystr = request.args.get('prj')
    cq_abbr = request.args.get('cq')


    project =  dora.get_project_by_keystr(keystr)

    keys_list = project.settings.get('clinical_question_result_table')
    list_ = []

    if project.settings.get('clinical_question_result_table'):
        if project.settings.get('clinical_question_result_table').get(cq_abbr):
            if project.settings.get('clinical_question_result_table').get(cq_abbr).get('cate_attrs_relations'):
                keys_list = project.settings.get('clinical_question_result_table').get(cq_abbr).get('cate_attrs_relations')
                for key in keys_list:
                    for i, j in key.items():
                        list_.append(i)
    

    if project.settings.get('clinical_question_result_table'):

        if project.settings.get('clinical_question_result_table').get(cq_abbr):
            return render_template(
            'extractor/result_table_pub.html',
            project_json_str=list_,
            cq_abbr=cq_abbr,
            project=project,
            comaparator_name=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('comaparator_name')),
            varaiable_name=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('varaiable_name')), 
            abbr_list_updated=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('abbr_list_updated')),
            headers_result=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('cate_attrs_relations')),
            rows_result=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('result_table_records')),
            rows_result_seq=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('result_table_records_seq')),
            rows_headers_mapping=json.dumps(project.settings.get('clinical_question_result_table').get(cq_abbr).get('parent_nested_realtion'))
            )
        else:
            return render_template(
            'extractor/result_table_pub.html',
            cq_abbr=cq_abbr,
            project=project,
            headers_result={},
            rows_result={},
            rows_headers_mapping={}
            )

    
    else:

        return render_template(
            'extractor/result_table_pub.html',
            cq_abbr=cq_abbr,
            project=project,
            headers_result={},
            rows_result={},
            rows_headers_mapping={}
        )


@bp.route('/graph_nma.html')
def graph_nma():
    return render_template('pub/graph_nma.html')


@bp.route('/graph_pma.html')
def graph_pma():
    return render_template('pub/graph_pma.html')

@bp.route('/graph_incidences.html')
def graph_incidences():
    return render_template('pub/graph_incidences.html')

@bp.route('/softable_nma.html')
def softable_nma():
    return render_template('pub/softable_nma.html')


@bp.route('/softable_pma.html')
def softable_pma():
    fn = 'pub/softable_pma.html'
    return render_template(fn)


@bp.route('/evmap.html')
def evmap():
    return render_template('pub/evmap.html')


###########################################################
# Archived modules for public page
###########################################################


###############################################################################
# For RCC project
# Special designed pages
###############################################################################

@bp.route('/RCC.html')
def RCC():
    prj = 'RCC'
    # load the graph data
    full_fn = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        prj, 
        'NMA_LIST.json'
    )
    nma = json.load(open(full_fn))
    
    # load the dma data
    full_fn = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        prj, 
        'PWMA_DATA.xlsx'
    )

    df = pd.read_excel(full_fn)
    pwma = OrderedDict()
    for idx, row in df.iterrows():
        pwma_type = row['type']
        option_text = row['option_text']
        legend_text = row['legend_text']
        filename = row['filename']
        if pwma_type not in pwma: 
            pwma[pwma_type] = {
                '_default_option': option_text
            }
        if option_text not in pwma[pwma_type]: 
            pwma[pwma_type][option_text] = {
                'text': option_text,
                'slides': [],
                'fns': []
            }
        # add this img
        pwma[pwma_type][option_text]['fns'].append({
            'fn': filename,
            'txt': legend_text
        })
        pwma[pwma_type][option_text]['slides'].append(filename + '$' + legend_text)

    # load the evmap data
    full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, 'EVMAP.json')
    evmap = json.load(open(full_fn))

    return render_template('pub/RCC/pub.RCC.html', nma=nma, pwma=pwma, evmap=evmap)


@bp.route('/mRCC.html')
def mRCC():
    prj = 'RCC'
    # load the graph data
    full_fn = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        prj, 
        'NMA_LIST.json'
    )
    nma = json.load(open(full_fn))
    
    # load the dma data
    full_fn = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        prj, 
        'PWMA_DATA.xlsx'
    )
    df = pd.read_excel(full_fn)
    pwma = OrderedDict()
    for idx, row in df.iterrows():
        pwma_type = row['type']
        option_text = row['option_text']
        legend_text = row['legend_text']
        filename = row['filename']
        if pwma_type not in pwma: 
            pwma[pwma_type] = {
                '_default_option': option_text
            }
        if option_text not in pwma[pwma_type]: 
            pwma[pwma_type][option_text] = {
                'text': option_text,
                'slides': [],
                'fns': []
            }
        # add this img
        pwma[pwma_type][option_text]['fns'].append({
            'fn': filename,
            'txt': legend_text
        })
        pwma[pwma_type][option_text]['slides'].append(filename + '$' + legend_text)

    # load the evmap data
    full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, 'EVMAP.json')
    evmap = json.load(open(full_fn))

    return render_template('pub/RCC/mRCC.html', nma=nma, pwma=pwma, evmap=evmap)


@bp.route('/graph_nma_RCC.html')
def graph_nma_RCC():
    return render_template('pub/RCC/graph_nma.html')


@bp.route('/graph_RCC.html')
def graph_RCC():
    return render_template('pub/RCC/graph_nma.html')


@bp.route('/ida_RCC.html')
def ida_RCC():
    '''
    A special module for the RCC
    '''
    return render_template('pub/RCC/ida.html')

###############################################################################
# For CAT project
# Special designed pages
###############################################################################

@bp.route('/CAT.html')
def CAT():
    prj = 'CAT'
    # load the graph data
    full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, 'NMA_LIST.json')
    nma = json.load(open(full_fn))

    # load the dma data
    full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, 'DMA_DATA.xlsx')
    df = pd.read_excel(full_fn)
    dma = OrderedDict()
    for idx, row in df.iterrows():
        dma_type = row['type']
        option_text = row['option_text']
        legend_text = row['legend_text']
        filename = row['filename']
        if dma_type not in dma: dma[dma_type] = {
            '_default_option': option_text
        }
        if option_text not in dma[dma_type]: dma[dma_type][option_text] = {
            'text': option_text,
            'slides': [],
            'fns': []
        }
        # add this img
        dma[dma_type][option_text]['fns'].append({
            'fn': filename,
            'txt': legend_text
        })
        dma[dma_type][option_text]['slides'].append(filename + '$' + legend_text)
    
    return render_template('pub/CAT/default/index.html', dma=dma, nma=nma)


@bp.route('/CAT_v1.html')
def CAT_v1():
    '''
    Deprecated
    '''
    prj = 'CAT'
    # load the graph data
    full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, 'NMA_LIST.json')
    nma = json.load(open(full_fn))

    # load the dma data
    full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, 'DMA_DATA.xlsx')
    df = pd.read_excel(full_fn)
    dma = OrderedDict()
    for idx, row in df.iterrows():
        dma_type = row['type']
        option_text = row['option_text']
        legend_text = row['legend_text']
        filename = row['filename']
        if dma_type not in dma: dma[dma_type] = {
            '_default_option': option_text
        }
        if option_text not in dma[dma_type]: dma[dma_type][option_text] = {
            'text': option_text,
            'slides': [],
            'fns': []
        }
        # add this img
        dma[dma_type][option_text]['fns'].append({
            'fn': filename,
            'txt': legend_text
        })
        dma[dma_type][option_text]['slides'].append(filename + '$' + legend_text)
    
    return render_template('pub/pub.CAT.html', dma=dma, nma=nma)


@bp.route('/ADJRCC.html')
def ADJRCC():
    prj = 'ADJRCC'

    # load the pwma data
    full_fn = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        prj, 
        'PWMA_DATA.xlsx'
    )
    pwma = get_pwma_data(full_fn)

    return render_template('pub/ADJRCC/pub.ADJRCC.html', pwma=pwma)


@bp.route('/slide.html')
def slide():
    return render_template('pub/slide.html')


@bp.route('/prisma_v2.html')
def prisma_v2():
    return render_template('pub/pub.prisma_v2.html')


@bp.route('/prisma_v3.html')
def prisma_v3():
    return render_template('pub/pub.prisma_v3.html')


@bp.route('/graph_v1.html')
def graph_v1():
    return render_template('pub/pub.graph_v1.html')


@bp.route('/graph_v2.html')
def graph_v2():
    return render_template('pub/pub.graph_v2.html')


@bp.route('/graph_v2_1.html')
def graph_v2_1():
    return render_template('pub/pub.graph_v2_1.html')


@bp.route('/graph_v2_2.html')
def graph_v2_2():
    return render_template('pub/pub.graph_v2_2.html')


@bp.route('/graph_v3.html')
def graph_v3():
    return render_template('pub/pub.graph_v3.html')


@bp.route('/oplot.html')
def oplot():
    return render_template('pub/pub.oplot.html')


@bp.route('/oplot_v2.html')
def oplot_v2():
    return render_template('pub/pub.oplot_v2.html')


@bp.route('/softable_pma_v2.html')
def softable_pma_v2():
    return render_template('pub/pub.softable_pma_v2.html')


@bp.route('/softable_nma_v2.html')
def softable_nma_v2():
    return render_template('archive/pub/pub.softable_nma_v2.html')


@bp.route('/evmap_tr.html')
def evmap_tr():
    return render_template('pub/pub.evmap_tr.html')


@bp.route('/evmap_tr_v2.html')
def evmap_tr_v2():
    return render_template('archive/pub/pub.evmap_tr_v2.html')


###########################################################
# Data services
###########################################################

@bp.route('/graphdata/<keystr>/file/<path:rest>')
def graphdata_file(keystr, rest):
    '''
    Special rule for other file in grpah data under file/

    The cq is required to determine sub-folder
    '''
    # get the cq for sub folder
    cq_abbr = request.args.get('cq')
    if cq_abbr is None or cq_abbr == '':
        cq_abbr = 'default'

    # get the full path to the file
    full_path = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        keystr, 
        cq_abbr,
        'file',
        rest
    )

    if os.path.exists(full_path):
        print('* requesting project file: %s' % full_path)
        return send_file(
            full_path
        )

    else:
        # this file not exists???
        print('* not found project file: %s' % full_path)
        return '', 404


@bp.route('/graphdata/<keystr>/<fn>')
def graphdata(keystr, fn):
    '''
    General rule for accessing project data files

    The cq is required to determine sub-folder
    '''
    # get the cq for sub folder
    cq_abbr = request.args.get('cq')
    if cq_abbr is None or cq_abbr == '':
        cq_abbr = 'default'

    # get the full path to the file
    full_path = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        keystr, 
        cq_abbr
    )
    # get the full name for display
    full_fn = os.path.join(
        full_path, 
        fn
    )
    if os.path.exists(full_fn):
        print('* requesting project file: %s' % full_fn)
        return send_from_directory(
            full_path,
            fn
        )
    else:
        # this file not exists???
        print('* not found project file: %s' % full_fn)
        return '', 404


@bp.route('/graphdata/<keystr>/PRISMA.json')
def graphdata_prisma_json(keystr):
    '''
    Special rule for the PRISMA.json

    This JSON file is for the PRISMA plot
    '''
    # get the itable from database directly
    src = request.args.get('src')
    version = request.args.get('version')
    if src is None or src == '':
        # set the default to get things from db
        src = 'cache'

    # get the cq_abbr
    cq_abbr = request.args.get('cq')
    if cq_abbr is None or cq_abbr == '':
        cq_abbr = 'default'

    fn_json = 'PRISMA.json'
    if version:
         full_fn_json = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr, 
            cq_abbr,
            f'version_{version}',
            fn_json
        )

    else:
        full_fn_json = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr, 
            cq_abbr,
            fn_json
        )

    # make the cache
    util.mk_graphdata_path(current_app.instance_path, keystr, cq_abbr)
    
    if src == 'cache':
        print('* using cache for %s.%s %s' % (
            keystr, cq_abbr, fn_json
        ))
        ret = json.load(open(full_fn_json))
        return jsonify(ret)

    if src == 'db':
        ret = srv_pub_prisma.get_pub_prisma_from_db(keystr, cq_abbr)
        latest = srv_project.get_project_latest_stat_by_keystr(keystr)
        project = dora.get_project_by_keystr(keystr)
        rst = dora.get_screener_stat_by_project_id(project.project_id)
        ret['prisma']['u4'] ={'n': rst['unscreened'], 'text': 'Currently Screening',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids':rst['unscreened'], 'n_ctids': 0}

        # ret_ = srv_deduplicate.find_duplicates(keystr)
        # duplicate_records = len(ret_.keys())
        # records_dup = []
        # for key , values in ret_.items():
        #     records_dup.append(len(values))
        
       
        # duplicate_records = sum(records_dup) - len(ret_.keys()) 
        total_records = (ret['prisma']['s0']['n'] + ret['prisma']['a1']['n'] + ret['prisma']['a3x']['n'])
        duplicate_records = total_records - (rst['unscreened'] + rst['decided'])
        total_records = total_records  - duplicate_records
        

        # Currently Screening   
        ret['prisma']['u5'] ={'n': duplicate_records, 'text': 'Currently Screening',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids':duplicate_records, 'n_ctids': 0}

        # Records Screened 
        ret['prisma']['u6'] ={'n': rst['decided'], 'text': 'Records Screened',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids':rst['decided'], 'n_ctids': 0} 

        # Records after Removing Duplicates  
        included = rst['included_sr']
        excluded_by_full_text_review = (rst['included_sr'] - ret['prisma']['f1']['n_pmids']) + rst['excluded_by_fulltext']
       
        print("*" * 60)
        print('* start calculating uX ...')

        records_after_removing_dup = total_records - (rst['unscreened'] + rst['decided'])

        ret['prisma']['u7'] ={'n': total_records, 'text': 'Records after removing duplicates',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids':total_records, 'n_ctids': 0}


        ret['prisma']['u8'] ={'n': rst['excluded_by_title'], 'text': 'Excluded by Title',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids':rst['excluded_by_title'], 'n_ctids': 0}

        ret['prisma']['u9'] ={'n': rst['excluded_by_abstract'], 'text': 'Excluded by Abstract',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids':rst['excluded_by_abstract'], 'n_ctids': 0}

        ret['prisma']['u10'] ={'n': rst['excluded_by_fulltext'], 'text': 'Excluded by Full Text Review',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids':rst['excluded_by_fulltext'], 'n_ctids': 0} 

        ret['prisma']['u11'] ={'n': rst['excluded_by_fulltext'], 'text': 'Total Records Identified',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids':rst['excluded_by_fulltext'], 'n_ctids': 0}

        ret['prisma']['u12'] ={'n': excluded_by_full_text_review, 'text': 'Excluded by Full Text Review',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids':excluded_by_full_text_review, 'n_ctids': 0}
        
        # update the e3 by reason
        n_reasons = 0
        for r in ret['prisma']['e3_by_reason']:
            n_reasons += ret['prisma']['e3_by_reason'][r]['n']

        if excluded_by_full_text_review != n_reasons:
            patch = excluded_by_full_text_review - n_reasons
            if ss_state.SS_REASON_OTHER not in ret['prisma']['e3_by_reason']:
                ret['prisma']['e3_by_reason'][ss_state.SS_REASON_OTHER] = {
                    'n': 0
                }
            ret['prisma']['e3_by_reason'][ss_state.SS_REASON_OTHER]['n'] += patch
            print('* added %s patch to the e3_by_reason.Other, Other=%s' % (
                patch,
                ret['prisma']['e3_by_reason'][ss_state.SS_REASON_OTHER]['n']
            ))
        
        else:
            print('* no need to patch e3_by_reason %s' % (n_reasons))
            

        inital_dup_records = ret['prisma']['s0']['n']- (ret['prisma']['a2x']['n'] )
        ret['prisma']['u13'] ={'n': inital_dup_records , 'text': 'Total Records Inital indentified',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids':inital_dup_records, 'n_ctids': 0}

        ret['prisma']['u14'] ={'n': ret['prisma']['a2x']['n'] , 'text': 'Records after removing duplicates inital',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids':ret['prisma']['a2x']['n'] , 'n_ctids': 0}

        ret['prisma']['u15'] ={'n':   rst['excluded_by_title_inital'] , 'text': 'Excluded by Title inital',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids': rst['excluded_by_title_inital'], 'n_ctids': 0}

        ret['prisma']['u16'] ={'n': rst['excluded_by_abstract_inital'] , 'text': 'Excluded by Abstract inital',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids': rst['excluded_by_abstract_inital'], 'n_ctids': 0}

        ret['prisma']['u17'] ={'n':  rst['excluded_by_full_text_inital'] , 'text': 'Excluded by Full text inital',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids': rst['excluded_by_full_text_inital'], 'n_ctids': 0}

        full_text_access_eligibility = ret['prisma']['a2x']['n']  - ( rst['excluded_by_title_inital'] + rst['excluded_by_abstract_inital'])
        ret['prisma']['u18'] ={'n':  full_text_access_eligibility , 'text': 'Excluded by Full text inital',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids': full_text_access_eligibility, 'n_ctids': 0}

        excluded_by_full_text_review_inital  = full_text_access_eligibility - ret['prisma']['f2']['n_pmids']
        ret['prisma']['u19'] ={'n':  excluded_by_full_text_review_inital , 'text': 'Excluded by Full text inital',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids': excluded_by_full_text_review_inital, 'n_ctids': 0}
        
        
        # update the e3i by reason
        n_ireasons = 0
        for r in ret['prisma']['e3i_by_reason']:
            n_ireasons += ret['prisma']['e3i_by_reason'][r]['n']

        if excluded_by_full_text_review_inital != n_ireasons:
            patch = excluded_by_full_text_review_inital - n_ireasons
            if ss_state.SS_REASON_OTHER not in ret['prisma']['e3i_by_reason']:
                ret['prisma']['e3i_by_reason'][ss_state.SS_REASON_OTHER] = {
                    'n': 0
                }
            ret['prisma']['e3i_by_reason'][ss_state.SS_REASON_OTHER]['n'] += patch
            print('* added %s patch to the e3i_by_reason.Other, Other=%s' % (
                patch,
                ret['prisma']['e3i_by_reason'][ss_state.SS_REASON_OTHER]['n']
            ))
        
        else:
            print('* no need to patch e3i_by_reason %s' % (n_ireasons))

        ret['prisma']['u20'] ={'n':  ret['prisma']['a2x']['n'], 'text': 'Records Screened initial',
         'pids': [], 'rcts': [], 'paper_list': [], 'study_list': [], 'n_pmids': ret['prisma']['a2x']['n'], 'n_ctids': 0}


        print(total_records)
        if ret is None:
            ret = {
                'success': False,
                'msg': 'ITABLE DATA NOT EXISTS FOR THIS PROJECT'
            }

        ret['latest'] = latest

        # catch the result
        json.dump(ret, open(full_fn_json, 'w'), default=util.json_encoder)

        return jsonify(ret)


    # read from xls?
    ret = srv_pub_prisma.get_prisma_from_xls(keystr)

    return jsonify(ret)


@bp.route('/graphdata/<keystr>/ITABLE.json')
def graphdata_itable_json(keystr):
    '''
    Special rule for the ITABLE.json which does not exist
    '''

    # get the itable from database directly
    src = request.args.get('src')
    # get the cq_abbr
    cq_abbr = request.args.get('cq')
    if cq_abbr is None or cq_abbr == '':
        cq_abbr = 'default'
    version = request.args.get('version')
    # get the cache path
    output_fn = 'ITABLE.json'
    if version:
         full_output_fn = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr, 
            cq_abbr,
            f'version_{version}',
            output_fn
        )

    else:
        full_output_fn = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr, 
            cq_abbr,
            output_fn
        )

    # make the cache
    util.mk_graphdata_path(current_app.instance_path, keystr, cq_abbr)

    if src == 'cache':
        print('* using cache for %s.%s %s' % (
            keystr, cq_abbr, output_fn
        ))
        ret = json.load(open(full_output_fn))
        return jsonify(ret)

    if src == 'db':
        ret = srv_pub_itable.get_itable_attr_rs_cfg_from_db(
            keystr,
            cq_abbr,
            True
        )
        latest = srv_project.get_project_latest_stat_by_keystr(keystr)
        ret['latest'] = latest
        

        if ret is None:
            ret = {
                'success': False,
                'msg': 'ITABLE DATA NOT EXISTS FOR THIS PROJECT'
            }

        # catch the result
        json.dump(ret, open(full_output_fn, 'w'), default=util.json_encoder)

        return jsonify(ret)

    # OK, get the itable data from XLS
    fn = 'ITABLE_ATTR_DATA.xlsx'
    full_fn = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        keystr, 
        fn
    )

    # get the cols from the xls
    attr_pack = srv_pub_itable.get_attr_pack_from_itable(full_fn)
    attrs = list(attr_pack['attr_dict'].values())

    # load the data from file 
    df = pd.read_excel(full_fn, skiprows=[0])
    rs = json.loads(df.to_json(orient='records'))

    # create the return obj
    ret = {
        'rs': rs,
        'attrs': attrs
    }

    # make a cache of this json
    json.dump(ret, open(full_output_fn, 'w'))

    return jsonify(ret)


@bp.route('/graphdata/<keystr>/ALL_OUTCOMES.json')
def graphdata_all_outcomes_json(keystr):
    '''
    Special rule for the ALL_OUTCOMES.json
    '''
    src = request.args.get('src')
    if src is None or src == '':
        # set the default to get things from db
        src = 'cache'

    cq_abbr = request.args.get('cq')
    if cq_abbr is None or cq_abbr == '':
        cq_abbr = 'default'

    project = dora.get_project_by_keystr(keystr)
    output_fn = 'ALL_OUTCOMES.json'
    full_output_fn = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        keystr, 
        cq_abbr,
        output_fn
    )
    util.mk_graphdata_path(current_app.instance_path, keystr, cq_abbr)

    if src == 'cache':
        print('* using cache for %s.%s %s' % (
            keystr, cq_abbr, output_fn
        ))
        ret = json.load(open(full_output_fn))
        return jsonify(ret)

    # get the result for database
    _extracts = dora.get_extracts_by_project_id_and_cq(
        project.project_id,
        cq_abbr
    )
    papers = srv_paper.get_included_papers_by_cq(
        project.project_id, 
        cq_abbr
    )
    paper_dict = {}
    for paper in papers:
        paper_dict[paper.pid] = paper.as_extreme_simple_dict()

    extracts = []
    for ext_idx, extract in enumerate(_extracts):
        # first, add data
        extract = dora.attach_extract_data(extract)

        # add this extract
        extracts.append(extract.as_dict())

    ret = {
        "paper_dict": paper_dict,
        "extracts": extracts
    }
    
    latest = srv_project.get_project_latest_stat_by_keystr(keystr)
    ret['latest'] = latest

    # catch the result
    json.dump(ret, open(full_output_fn, 'w'), default=util.json_encoder)

    return jsonify(ret)


@bp.route('/graphdata/<keystr>/GRAPH_PMA.json')
def graphdata_graph_pwma_json(keystr):
    '''
    Special rule for the GRAPH_PMA.json which does not exist

    This JSON is designed for the PWMA results.
    It is the first pure DB-based export, no XLS file required.
    '''
    src = request.args.get('src')
    if src is None or src == '':
        # set the default to get things from db
        src = 'cache'

    cq_abbr = request.args.get('cq')
    if cq_abbr is None or cq_abbr == '':
        cq_abbr = 'default'
    version = request.args.get('version')
    calc = request.args.get('calc')
    if calc is None or calc == '':
        calc = 'no'

    # get the cache path
    project = dora.get_project_by_keystr(keystr)
    cq_plot_relation = {}
    if project.settings.get('cq_plots_statisification'):
        if  project.settings.get('cq_plots_statisification').get(cq_abbr):
            cq_plot_relation = project.settings.get('cq_plots_statisification').get(cq_abbr)

    output_fn = 'GRAPH_PMA.json'
    if version:
        full_output_fn = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr, 
            cq_abbr,
            f'version_{version}',
            output_fn
        )
    else:
            full_output_fn = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr, 
            cq_abbr,
            output_fn
        )

    # make the cache
    util.mk_graphdata_path(current_app.instance_path, keystr, cq_abbr)

    if src == 'cache':
        print('* using cache for %s.%s %s' % (
            keystr, cq_abbr, output_fn
        ))
        ret = json.load(open(full_output_fn))
        return jsonify(ret)

    # get the result for database
    ret = srv_pub_pwma.get_graph_pwma_data_from_db(
        keystr, 
        cq_abbr
    )
    latest = srv_project.get_project_latest_stat_by_keystr(keystr)
    ret['latest'] = latest
    ret['cq_plot_relation'] = cq_plot_relation
    # if cq_abbr== "parp_mcrpc":
    #     ret['parp_flag'] = True

    # catch the result
    json.dump(ret, open(full_output_fn, 'w'), default=util.json_encoder)

    return jsonify(ret)


@bp.route('/graphdata/<keystr>/GRAPH_PMA_INCIDENCE.json')
def graphdata_graph_pwma_incidence_json(keystr):
    '''
    Special rule for the GRAPH_PMA.json which does not exist

    This JSON is designed for the PWMA results.
    It is the first pure DB-based export, no XLS file required.
    '''
    src = request.args.get('src')
    if src is None or src == '':
        # set the default to get things from db
        src = 'cache'

    cq_abbr = request.args.get('cq')
    if cq_abbr is None or cq_abbr == '':
        cq_abbr = 'default'
    version = request.args.get('version')
    calc = request.args.get('calc')
    if calc is None or calc == '':
        calc = 'no'

    project = dora.get_project_by_keystr(keystr)
    cq_plot_relation = {}
    if project.settings.get('cq_plots_statisification'):
        if  project.settings.get('cq_plots_statisification').get(cq_abbr):
            cq_plot_relation = project.settings.get('cq_plots_statisification').get(cq_abbr)

    # get the cache path
    output_fn = 'GRAPH_PMA_INCIDENCE.json'
    if version:
        full_output_fn = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr, 
            cq_abbr,
            f'version_{version}',
            output_fn
        )
    else:
            full_output_fn = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr, 
            cq_abbr,
            output_fn
        )

    # make the cache
    util.mk_graphdata_path(current_app.instance_path, keystr, cq_abbr)

    if src == 'cache':
        print('* using cache for %s.%s %s' % (
            keystr, cq_abbr, output_fn
        ))
        ret = json.load(open(full_output_fn))
        return jsonify(ret)

    # get the result for database
    ret = srv_pub_pwma.get_graph_pwma_data_incidence_from_db(
        keystr, 
        cq_abbr,
        False
    )
    latest = srv_project.get_project_latest_stat_by_keystr(keystr)
    ret['latest'] = latest
    ret['cq_plot_relation'] = cq_plot_relation
    # if cq_abbr== "parp_mcrpc":
    #     ret['parp_flag'] = True

    # catch the result
    json.dump(ret, open(full_output_fn, 'w'), default=util.json_encoder)

    return jsonify(ret)


@bp.route('/graphdata/<keystr>/GRAPH_NMA.json')
def graphdata_graph_nma_json(keystr):
    '''
    Special rule for the grpah data of NMA
    '''
    src = request.args.get('src')
    version = request.args.get('version')
    if src is None or src == '':
        # set the default to get things from db
        src = 'cache'

    cq_abbr = request.args.get('cq')
    if cq_abbr is None or cq_abbr == '':
        cq_abbr = 'default'

    # get the cache path
    output_fn = 'GRAPH_NMA.json'
    if version:
        full_output_fn = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr, 
            cq_abbr,
            f'version_{version}',
            output_fn
        )
    else:
            full_output_fn = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr, 
            cq_abbr,
            output_fn
        )

    # make the cache
    util.mk_graphdata_path(current_app.instance_path, keystr, cq_abbr)

    if src == 'cache':
        print('* using cache for %s.%s %s' % (
            keystr, cq_abbr, output_fn
        ))
        ret = json.load(open(full_output_fn))
        return jsonify(ret)

    # get the result for database
    ret = srv_pub_nma.get_graph_nma_json(
        keystr, 
        cq_abbr
    )

    return jsonify(ret)


@bp.route('/graphdata/<keystr>/SOFTABLE_PMA.json')
def graphdata_softable_pwma_json(keystr):
    '''
    Special rule for the SoF Table PWMA which does not exist
    In this function, all the data are stored in ALL_DATA.xlsx
    The first tab is Study characteristics
    The second tab is Adverse events
    From third tab all the events
    '''
    src = request.args.get('src')
    if src is None or src == '':
        # set the default to get things from db
        src = 'cache'

    # get the cq_abbr
    cq_abbr = request.args.get('cq')
    if cq_abbr is None or cq_abbr == '':
        cq_abbr = 'default'

    fn_json = 'SOFTABLE_PMA.json'
    full_fn_json = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        keystr, 
        cq_abbr,
        fn_json
    )

    # make the cache
    util.mk_graphdata_path(current_app.instance_path, keystr, cq_abbr)
    
    if src == 'cache':
        print('* using cache for %s.%s %s' % (
            keystr, cq_abbr, fn_json
        ))
        ret = json.load(open(full_fn_json))
        return jsonify(ret)

    if src == 'db':
        print('* reading database for %s.%s %s' % (
            keystr, cq_abbr, fn_json
        ))
        ret = srv_pub_pwma.get_sof_pwma_data_from_db(
            keystr, 
            cq_abbr, 
            is_calc_pwma=True
        )

        if ret is None:
            ret = {
                'success': False,
                'msg': 'SOFTABLE_PMA DATA NOT EXISTS FOR THIS PROJECT'
            }

        latest = srv_project.get_project_latest_stat_by_keystr(keystr)
        ret['latest'] = latest

        # catch the result
        json.dump(ret, open(full_fn_json, 'w'), default=util.json_encoder)

        return jsonify(ret)

    # get the version of this file
    # v1 is for IOTOX, v2 for others
    v = request.args.get('v')
    ret = {}

    if v is None or v == '' or v == '1':
        if keystr == 'IO':
            fn = 'ALL_DATA.xlsx'
            full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, keystr, fn)
            ret = get_sof_pma_data_IO(full_fn, is_calc_pwma=True)
        else:
            fn = 'SOFTABLE_PMA_DATA.xlsx'
            full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, keystr, fn)
            ret = get_ae_pma_data_simple(full_fn)

    elif v == '2':
        fn = 'SOFTABLE_PMA_DATA.xlsx'
        full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, keystr, fn)
        ret = get_sof_pma_data(full_fn)

    # cache the data
    json.dump(ret, open(full_fn_json, 'w'))

    return jsonify(ret)


@bp.route('/graphdata/<keystr>/SOFTABLE_NMA.json')
def graphdata_softable_nma_json(keystr):
    '''
    Special rule for the SoF Table NMA which does not exist
    
    If get the result from Excel file, all the data are stored in ALL_DATA.xlsx
    The first tab is Study characteristics
    The second tab is Adverse events
    From third tab all the events
    '''
    src = request.args.get('src')
    if src is None or src == '':
        # set the default to get things from db
        src = 'cache'

    # get the cq_abbr
    cq_abbr = request.args.get('cq')
    if cq_abbr is None or cq_abbr == '':
        cq_abbr = 'default'

    # 
    fn_json = 'SOFTABLE_NMA.json'
    full_fn_json = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        keystr,
        cq_abbr,
        fn_json
    )

    # make the cache
    util.mk_graphdata_path(current_app.instance_path, keystr, cq_abbr)

    if src == 'cache':
        print('* using cache for %s.%s %s' % (
            keystr, cq_abbr, fn_json
        ))
        ret = json.load(open(full_fn_json))
        return jsonify(ret)

    if src == 'db':
        print('* reading database for %s.%s %s' % (
            keystr, cq_abbr, fn_json
        ))

        ret = srv_pub_nma.get_sof_nma_data_from_db(
            keystr, cq_abbr
        )

        if ret is None:
            ret = {
                'success': False,
                'msg': 'SOFTABLE NMA DATA NOT EXISTS FOR THIS PROJECT'
            }

        latest = srv_project.get_project_latest_stat_by_keystr(keystr)
        ret['latest'] = latest

        # catch the result
        json.dump(ret, open(full_fn_json, 'w'), default=util.json_encoder)

        return jsonify(ret)

    # ok ... read file
    # read file
    if src == 'xls':
            
        backend = 'freq'
        if keystr == 'RCC':
            backend = 'freq'
        elif keystr == 'CAT':
            backend = 'bayes'

        # get parameters
        v = request.args.get('v')

        ret = {}
        fn = 'SOFTABLE_NMA_DATA.xlsx'
        full_fn = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr, 
            fn
        )
        if v is None or v == '' or v == '1':
            ret = get_ae_nma_data(full_fn, backend=backend)
            # cache the result
            json.dump(ret, open(full_fn_json, 'w'))
        elif v == '2':
            ret = get_sof_nma_data(full_fn)
            # cache the result
            json.dump(ret, open(full_fn_json, 'w'))

    # 
    ret = {
        'success': False,
        'msg': 'SOFTABLE_PMA DATA NOT EXISTS FOR THIS PROJECT'
    }
    return jsonify(ret)


@bp.route('/graphdata/<keystr>/EVMAP.json')
def graphdata_evmap_json(keystr):
    '''
    Special rule for the EVMAP.json

    This JSON file is for the evidence map plot
    '''
    src = request.args.get('src')
    version = request.args.get('version')
    if src is None or src == '':
        # set the default to get things from db
        src = 'cache'

    # get the cq_abbr
    cq_abbr = request.args.get('cq')
    if cq_abbr is None or cq_abbr == '':
        cq_abbr = 'default'

    fn_json = 'EVMAP.json'
    if version:
        full_path = os.path.join(
            current_app.instance_path, 
            settings.PUBLIC_PATH_PUBDATA, 
            keystr,
            cq_abbr,
            f'version_{version}'
        )
    else:
        full_path = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        keystr,
        cq_abbr
    )
    full_fn_json = os.path.join(
        full_path,
        fn_json
    )

    # make the cache
    util.mk_graphdata_path(current_app.instance_path, keystr, cq_abbr)
    
    if src == 'cache':
        print('* using cache for %s.%s %s' % (
            keystr, cq_abbr, fn_json
        ))
        ret = json.load(open(full_fn_json))
        return jsonify(ret)

    if src == 'sofnma_cache' or src == 'db':
        full_fn_sofnama = os.path.join(
            full_path,
            'SOFTABLE_NMA.json'
        )
        print('* using sof name cache for %s.%s %s by %s' % (
            keystr, cq_abbr, fn_json, full_fn_sofnama
        ))
        j = json.load(open(full_fn_sofnama))
        ret = srv_pub_nma.parse_evmap_data_from_json(j)
        latest = srv_project.get_project_latest_stat_by_keystr(keystr)
        ret['latest'] = latest

        # catch the result
        json.dump(ret, open(full_fn_json, 'w'), default=util.json_encoder)

        return jsonify(ret)

    # what????
    # reading the file?
    # fn = 'EVMAP_DATA.xlsx'
    fn = 'SOFTABLE_NMA_DATA.xlsx'
    full_fn = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        keystr, 
        fn
    )

    # no cache
    ret = get_evmap_data(full_fn)

    # cache the latest data
    json.dump(ret, open(full_fn_json, 'w'))

    return jsonify(ret)


@bp.route('/graphdata/<prj>/LATEST.json')
def graphdata_latest_json(prj):
    '''
    Special rule for the LATEST.json

    which is used for displaying some latest information
    '''
    result = srv_project.get_project_latest_stat_by_keystr(prj)

    return jsonify(result)


@bp.route('/mkjson/PRISMA.json')
def mkjson_prisma_json():
    '''
    Make JSON data for PRISMA
    '''
    keystr = request.args.get('k')
    cq_abbr = request.args.get('c')

    print('* collecting sys stdout ...')
    stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        data = srv_pub_prisma.get_prisma_json(
            keystr, 
            cq_abbr
        )
    except Exception as ex:
        data = None
        print('* Runtime Exception!')
        print('* ErrorName:', ex, ex.__traceback__)
        traceback.print_exc(file=buffer)
        print('* Please check output or contact administrator')

    sys.stdout = stdout
    sys_output = buffer.getvalue()
    print('* collected sys stdout')
    print(sys_output)

    ret = {
        'success': True,
        'data': data,
        'sys_output': sys_output
    }

    return jsonify(ret)


@bp.route('/mkjson/ITABLE.json')
def mkjson_itable_json():
    '''
    Make JSON data for ITABLE
    '''
    keystr = request.args.get('k')
    cq_abbr = request.args.get('c')

    print('* collecting sys stdout ...')
    stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        data = srv_pub_itable.get_itable_json(
            keystr, 
            cq_abbr
        )
    except Exception as ex:
        data = None
        print('* Runtime Exception!')
        print('* ErrorName:', ex, ex.__traceback__)
        traceback.print_exc(file=buffer)
        print('* Please check output or contact administrator')

    sys.stdout = stdout
    sys_output = buffer.getvalue()
    print('* collected sys stdout')
    print(sys_output)

    ret = {
        'success': True,
        'data': data,
        'sys_output': sys_output
    }

    return jsonify(ret)


@bp.route('/mkjson/SOFTABLE_PMA.json')
def mkjson_softable_pwma_json():
    '''
    Make JSON data file by backend 
    '''
    keystr = request.args.get('k')
    cq_abbr = request.args.get('c')

    print('* collecting sys stdout ...')
    stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        data = srv_pub_pwma.get_softable_pwma_json(
            keystr, 
            cq_abbr
        )
    except Exception as ex:
        data = None
        print('* Runtime Exception!')
        print('* ErrorName:', ex, ex.__traceback__)
        traceback.print_exc(file=buffer)
        print('* Please check output or contact administrator')

    sys.stdout = stdout
    sys_output = buffer.getvalue()
    print('* collected sys stdout')
    print(sys_output)

    ret = {
        'success': True,
        'data': data,
        'sys_output': sys_output
    }

    return jsonify(ret)
    

@bp.route('/mkjson/GRAPH_PMA.json')
def mkjson_graph_pwma_json():
    '''
    Make GRAPH_PMA.json by backend
    '''
    keystr = request.args.get('k')
    cq_abbr = request.args.get('c')

    print('* collecting sys stdout ...')
    stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        data = srv_pub_pwma.get_graph_pwma_json(
            keystr, 
            cq_abbr
        )
    except Exception as ex:
        data = None
        print('* Runtime Exception!')
        print('* ErrorName:', ex, ex.__traceback__)
        traceback.print_exc(file=buffer)
        print('* Please check input XLS file or contact administrator')

    sys.stdout = stdout
    sys_output = buffer.getvalue()
    print('* collected sys stdout')
    print(sys_output)

    ret = {
        'success': True,
        'data': data,
        'sys_output': sys_output
    }

    return jsonify(ret)


@bp.route('/mkjson/SOFTABLE_NMA.json')
def mkjson_softable_nma_json():
    '''
    Make JSON data file by backend
    '''
    keystr = request.args.get('k')
    cq_abbr = request.args.get('c')

    print('* collecting sys stdout ...')
    stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        data = srv_pub_nma.get_softable_nma_json(
            keystr, 
            cq_abbr
        )
    except Exception as ex:
        data = None
        print('* Runtime Exception!')
        print('* ErrorName:', ex, ex.__traceback__)
        traceback.print_exc(file=buffer)
        print('* Please check input XLS file or contact administrator')

    sys.stdout = stdout
    sys_output = buffer.getvalue()
    print('* collected sys stdout')
    print(sys_output)

    ret = {
        'success': True,
        'data': data,
        'sys_output': sys_output
    }

    return jsonify(ret)


@bp.route('/mkjson/GRAPH_NMA.json')
def mkjson_graph_nma_json():
    '''
    Make JSON data file for backend 
    '''
    keystr = request.args.get('k')
    cq_abbr = request.args.get('c')

    print('* collecting sys stdout ...')
    stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        data = srv_pub_nma.get_graph_nma_json(
            keystr, 
            cq_abbr
        )
    except Exception as ex:
        data = None
        print('* Runtime Exception!')
        print('* ErrorName:', ex, ex.__traceback__)
        traceback.print_exc(file=buffer)
        print('* Please check input XLS file or contact administrator')

    sys.stdout = stdout
    sys_output = buffer.getvalue()
    print('* collected sys stdout')
    print(sys_output)

    ret = {
        'success': True,
        'data': data,
        'sys_output': sys_output
    }

    return jsonify(ret)
    

@bp.route('/mkjson/EVMAP.json')
def mkjson_evmap_json():
    '''
    Make EVMAP.json by backend
    '''
    keystr = request.args.get('k')
    cq_abbr = request.args.get('c')

    print('* collecting sys stdout ...')
    stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    try:
        data = srv_pub_nma.get_evmap_json(
            keystr, 
            cq_abbr
        )
    except Exception as ex:
        data = None
        print('* Runtime Exception!')
        print('* ErrorName:', ex, ex.__traceback__)
        traceback.print_exc(file=buffer)
        print('* Please check NMA data or contact administrator')

    sys.stdout = stdout
    sys_output = buffer.getvalue()
    print('* collected sys stdout')
    print(sys_output)

    ret = {
        'success': True,
        'data': data,
        'sys_output': sys_output
    }

    return jsonify(ret)


###########################################################
# Archieved Data services
###########################################################

@bp.route('/graphdata/<prj>/img/<fn>')
def graphdata_img(prj, fn):
    '''
    get image files of specific project
    '''
    full_path = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        prj, 
        'img'
    )
    return send_from_directory(full_path, fn)


@bp.route('/graphdata/<prj>/decision_aid/<cmp>/<fn>')
def graphdata_da_cmp(prj, cmp, fn):
    '''
    Get decision aid image files of specific project
    '''
    full_path = os.path.join(
        current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, 
        'decision_aid',
        cmp
    )
    return send_from_directory(full_path, fn)


@bp.route('/graphdata/<prj>/ITABLE_CFG.json')
def graphdata_itable_cfg_json(prj):
    full_fn_itable_cfg_json = os.path.join(
        current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, 'ITABLE_CFG.json')

    # just send the ITABLE_CFG.json if exists
    # if os.path.exists(full_fn_itable_cfg_json):
    #     return send_from_directory(
    #         os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj),
    #         'ITABLE_CFG.json'
    #     )

    # just load the existing filters
    fn = 'ITABLE_FILTERS.json'
    full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, fn)
    if os.path.exists(full_fn):
        filters = json.load(open(full_fn))['filters']
    else:
        # get the filters from the excel file
        fn = 'ITABLE_FILTERS.xlsx'
        full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, fn)
        filters = get_filters_from_itable(full_fn)

    ret = {
        "cols": {
            "fixed": [],
            "default": []
        },
        "filters": filters
    }

    # make a cache
    json.dump(ret, open(full_fn_itable_cfg_json, 'w'))

    return jsonify(ret)


@bp.route('/graphdata/<prj>/GRAPH.json')
def graphdata_graph_json(prj):
    '''
    Special rule for the graphs.
    Generate a GRAPH.json for this project.
    And, it will also generate a set of outcome seperate file
    '''

    fn = 'SOFTABLE_NMA_DATA.xlsx'
    full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, fn)

    # hold all the outcomes
    fn_json = 'GRAPH.json'
    full_fn_json = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, fn_json)

    # hold one outcome
    fn_oc_json = 'GRAPH_%s.json'
    full_oc_fn_json = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, fn_oc_json)

    # hold the outcome list 
    fn_nma_list_json = 'NMA_LIST.json'
    full_nma_list_json = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, fn_nma_list_json)

    # use cache to haste the loading
    use_cache = request.args.get('use_cache')
    if use_cache == 'yes':
        return send_from_directory(
            os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj),
            fn_json
        )
    
    # generate the NMA List data
    nma = get_nma_list_data(full_fn)

    # cache the NMA list
    json.dump(nma, open(full_nma_list_json, 'w'))

    # get the graph json data
    ret = get_oc_graph_data(full_fn)

    # save the GRAPH.json
    json.dump(ret, open(full_fn_json, 'w'))

    return jsonify(ret)


@bp.route('/graphdata/<prj>/OPLOTS.json')
def graphdata_oplots(prj):
    '''
    Deprecated
    Special rule for the OPLOTS.json which does not exist
    
    The input file is OPLOTS.xls with multiple sheets

    S.1: Adverse events
    S.2: ?
    S.3: All SEs
    S.4: AE_NAME_1 
    S.n: AE_NAME_2

    '''
    fn = 'ALL_DATA.xlsx'
    full_fn = os.path.join(current_app.instance_path, settings.PUBLIC_PATH_PUBDATA, prj, fn)
    ret = get_ae_pma_data(full_fn, is_getting_sms=False)

    return jsonify(ret)


###########################################################
# Other utils
###########################################################

def get_evmap_data(full_fn):
    # return get_evmap_data_v1(full_fn)
    return get_evmap_data_v2(full_fn)

    
def get_evmap_data_v2(full_fn):
    '''
    fn = 'SOFTABLE_NMA_DATA.xlsx
    '''
    # first, load all the treatment names
    tab_name_outcomes = 'Outcomes'
    tab_name_certainty = 'Certainty'
    tab_name_treatments = 'Treatments'

    # load the xls
    xls = pd.ExcelFile(full_fn)

    # read the outcomes for evmap
    dft = xls.parse(tab_name_outcomes)

    # select those included in es
    dft = dft[dft['included in em']=='yes']

    # build oc category
    oc_dict = {}
    oc_names = []
    for idx, row in dft.iterrows():
        oc = {
            "oc_method": row['method'],
            "oc_name": row['name'],
            "oc_fullname": row['full name'],
            "oc_measures": row['measure'].split(','),
            "oc_datatype": row['data type'],
            "param": {
                "analysis_method": row["method"],
                "fixed_or_random": row["fixed_or_random"],
                "which_is_better": row["which_is_better"]
            },
            # certainy and effect table
            "cetable": {},
            "lgtable": {}
        }
        oc_dict[oc['oc_name']] = oc
        oc_names.append(oc['oc_name'])

    # build treats list
    dft = xls.parse(tab_name_treatments)

    # build treat dictionary
    treat_list = []
    treat_dict = {}
    for idx, row in dft.iterrows():
        tr_name = row['treats'].strip()
        tr_fullname = row['full name']

        # add this treat
        treat_list.append(tr_name)
        treat_dict[tr_name] = {
            'tr_name': tr_name,
            'tr_fullname': tr_fullname
        }

    # build certainty dict
    cols_range = 'A:K'
    cols_certs = [
        'oc_cate', 'oc_name', 'comparator', 'treatment', 
        'cie_rob', 'cie_inc', 'cie_ind', 'cie_imp', 'pub_bia',
        'cie_coh', 'cie_trs'
    ]
    cols_calc_cert = [
        'cie_rob', 'cie_inc', 'cie_ind', 'cie_imp', 'cie_coh', 'cie_trs'
    ]
    dft = xls.parse(tab_name_certainty, usecols=cols_range, names=cols_certs)
    # there maybe nan 
    dft = dft[~dft['oc_name'].isna()]

    # parse the data build cert dict
    for idx, row in dft.iterrows():
        oc_cate = row['oc_cate']
        oc_name = row['oc_name']
        comparator = row['comparator']
        treatment = row['treatment']

        # 2021-03-08: skip the oc when it is set to no
        if oc_name not in oc_dict:
            continue 
        
        if comparator not in oc_dict[oc_name]['cetable']:
            oc_dict[oc_name]['cetable'][comparator] = { comparator: {} }

        # put the comparator vs treatment {} in 
        oc_dict[oc_name]['cetable'][comparator][treatment] = {}

        # put the values of each column
        for col in cols_certs[4:]:
            try:
                oc_dict[oc_name]['cetable'][comparator][treatment][col] = int(row[col])
            except:
                oc_dict[oc_name]['cetable'][comparator][treatment][col] = 0

        # calc the cie of this row
        oc_dict[oc_name]['cetable'][comparator][treatment]['cie'] = \
            calc_cie(row[cols_calc_cert].tolist())

    # now get the NMA results
    cols_dict = settings.SOFTABLE_NMA_COLS
    
    for oc_name in oc_names:
        oc = oc_dict[oc_name]
        sheet_name = oc_name

        # get the data
        usecols = cols_dict[oc['oc_datatype']][0]
        namecols = cols_dict[oc['oc_datatype']][1]
        dft = xls.parse(sheet_name, usecols=usecols, names=namecols)

        # remove those empty lines based on study name
        # the study name MUST be different
        dft = dft[~dft.study.isna()]
        # get the records
        rs = json.loads(dft.to_json(orient='table', index=False))['data']

        # summary of mesure, only use the first?
        sm = oc['oc_measures'][0]
        cfg = {
            # for init analyzer
            "backend": oc['param']['analysis_method'],
            "input_format": {
                'pre': settings.INPUT_FORMATS_HRLU, 
                'raw': settings.INPUT_FORMATS_ET,
                'raw_time': settings.INPUT_FORMATS_FTET
            }[oc['oc_datatype']],
            "measure_of_effect": sm,
            "fixed_or_random": oc['param']['fixed_or_random'],
            # just use the first one as 
            "reference_treatment": treat_list[0],
            "which_is_better": 'big' if oc['param']["which_is_better"] in ['higher', 'bigger'] else 'small'
        }
        # invoke analyzer
        ret_nma = nma_analyzer.analyze(rs, cfg)

        # get formatted lgtable data
        lgtable_sm = _conv_nmarst_league_to_lgtable(ret_nma)
        oc_dict[oc_name]['lgtable'][sm] = lgtable_sm


    # init the evmap data
    data = {}
    effects = {
        3: 'significant benefit',
        2: 'no significant effect',
        1: 'significant harm',
        0: 'na'
    }
    for comparator in treat_list:
        data[comparator] = []
        for treatment in treat_list:
            # nothing to comparator with self
            if treatment == comparator: continue

            for oc_name in oc_names:
                oc = oc_dict[oc_name]
                sm = oc['oc_measures'][0]
                # get the certainty
                if comparator in oc['cetable'] and \
                    treatment in oc['cetable'][comparator] and \
                    'cie' in oc['cetable'][comparator][treatment]:
                    c = oc['cetable'][comparator][treatment]['cie']
                    e_txt = "no significant effect"
                else:
                    c = 0
                    e_txt = 'na'

                # get the effect
                if comparator in oc['lgtable'][sm] and \
                    treatment in oc['lgtable'][sm][comparator]:
                    if oc['lgtable'][sm][comparator][treatment]['sm'] == 1:
                        e = 2
                    elif oc['lgtable'][sm][comparator][treatment]['lw'] < 1 \
                        and oc['lgtable'][sm][comparator][treatment]['up'] > 1:
                        e = 2
                    elif oc['lgtable'][sm][comparator][treatment]['sm'] > 1:
                        if oc['param']["which_is_better"] == 'higher':
                            e = 3
                        else:
                            e = 1
                    elif oc['lgtable'][sm][comparator][treatment]['sm'] < 1:
                        if oc['param']["which_is_better"] == 'higher':
                            e = 1
                        else:
                            e = 3
                    else:
                        e = 0
                else:
                    e = 0

                e_txt = effects[e]

                # update the table data
                data[comparator].append({
                    "c": c, 
                    "e": e, 
                    "e_txt": e_txt, 
                    "oc": oc_name, 
                    "t": treatment
                })

    ret = {
        "treat_list": treat_list,
        "treat_dict": treat_dict,
        "oc_dict": oc_dict,
        "data": data
    }

    return ret


def get_evmap_data_v1(full_fn):
    '''
    fn = 'EVMAP_DATA.xlsx'
    '''
    # first, load all the treatment names
    tab_name_treatments = 'Treatments'

    # load the xls
    xls = pd.ExcelFile(full_fn)

    # read the treatments
    dft = xls.parse(tab_name_treatments)
    tmp = dft['treats'].tolist()

    # load each treat
    cols = ['treatment', 'comparator', 'outcome', 'certainty', 'effect']
    treat_list = []
    data = {}
    for treat in tmp:
        treat = treat.strip()
        tab_name = treat

        # add this treat
        treat_list.append(treat)

        # load the data of this comparator
        dft = xls.parse(tab_name, usecols='A:E', names=cols)
        rs = []
        for idx, row in dft.iterrows():
            t = row['treatment'].strip()
            oc = row['outcome'].strip()
            cert = row['certainty']
            effect = row['effect']

            if np.isnan(cert):
                c = 0
                e = 0
                effect = None
            else:
                c = int(cert)
                e = {
                    'significant benefit': 3,
                    'no significant effect': 2,
                    'significant harm': 1
                }.get(effect.strip().lower(), 0)
            
            r = {
                't': t,
                'oc': oc,
                'c': c,
                'e': e,
                'e_txt': effect
            }
            rs.append(r)

        # bind this rs to data
        data[treat] = rs

    ret = {
        "treat_list": treat_list,
        "data": data
    }

    return ret


def get_filters_from_itable(full_fn):
    '''Get the filters from ITABLE_FILTERS.xlsx
    In this file, there should be only one tab: Filters
    
    The format of this file should follow:

    label1,    label2,     ...
    col_name1, col_name2,  ...
    flt_type1, flt_type2,  ...
    def_opt_1, def_opt_2,  ...
    option1_1, option_2_1, ...
    option1_2, option_2_2, ...

    Each column represents one filter.
    The first row is the label displayed on the UI.
    The second row is the column name.
    The third row is the filter type: radio, select.
    The 4th row is the default label name
    From this row, all rows are the options for this filter.

    All of the options must be the text in the column in the itable.
    '''
    # load the data file
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
        ft_attr = tmp[0]
        # the second line of dft is the filter type: radio or select
        ft_type = tmp[1].strip().lower()
        # get those rows not NaN, which means containing option
        ft_opts = dft[col][~dft[col].isna()].tolist()[3:]
        # get the default label
        ft_def_opt_label = tmp[2].strip()

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





def get_pwma_by_py(dataset, datatype='CAT_RAW', 
    sm='RR', method='MH', fixed_or_random='random'):
    '''
    Get the PWMA results
    The input dataset should follow:

    [Et, Nt, Ec, Nc, Name 1],
    [Et, Nt, Ec, Nc, Name 2], ...

    for example:

    dataset = [
        [41, 522, 59, 524, 'A'], 
        [8, 203, 18, 203, 'B']
    ]
    '''
    meta = PWMA.Meta()
    meta.datatype = 'CATE' if datatype == 'CAT_RAW' else 'CATE'
    meta.models = fixed_or_random.capitalize()
    meta.algorithm = method
    meta.effect = sm
    rs = meta.meta(dataset)

    ret = {
        "model": {
            'measure': rs[0][0],
            'sm': rs[0][1],
            'lower': rs[0][3],
            'upper': rs[0][4],
            'total': rs[0][5],
            'i2': rs[0][9],
            'tau2': rs[0][12],
            'q_tval': rs[0][7],
            'q_pval': rs[0][8],
            'z_tval': rs[0][10],
            'z_pval': rs[0][11]
        },
        'stus': []
    }

    # put results of other studies
    for i in range(1, len(rs)):
        r = rs[i]
        ret['stus'].append({
            'name': r[0],
            'sm': r[1],
            'lower': r[3],
            'upper': r[4],
            'total': r[5],
            'w': r[2] / rs[0][2],
        })
    
    return ret


def get_pwma_by_r_CAT_PRE(dataset, 
    sm='HR', fixed_or_random='random'):
    '''
    Get the PWMA results by R script (PRIM_CAT_RPE)
    The input dataset should follow:

    [TE, lowerci, upperci, Name 1],
    [TE, lowerci, upperci, Name 2], ...

    for example:

    dataset = [
        [0.5, 0.4, 0.9, 'A'], 
        [0.3, 0.2, 0.4, 'B']
    ]
    '''
    rs = []
    for d in dataset:
        rs.append({
            'study': d[3],
            'TE': d[0],
            'lowerci': d[1],
            'upperci': d[2]
        })
    cfg = {
        'prj': 'ALL',
        'analyzer_model': 'PRIM_CAT_PRE',
        'fixed_or_random': fixed_or_random,
        'measure_of_effect': sm,
        'is_hakn': 'FALSE'
    }
    # use R to get the results
    rst = pwma_analyzer.analyze(rs, cfg)

    ret = {
        "model": {
            'measure': sm,
            'sm': rst['data']['primma']['model'][fixed_or_random]['sm'],
            'lower': rst['data']['primma']['model'][fixed_or_random]['lower'],
            'upper': rst['data']['primma']['model'][fixed_or_random]['upper'],
            'total': 0,
            # 'i2': rst['data']['primma']['heterogeneity']['i2'],
            # 'tau2': rst['data']['primma']['heterogeneity']['tau2'],
            # 'q_tval': 0,
            # 'q_pval': rst['data']['primma']['heterogeneity']['p'],
            # 'z_tval': 0,
            # 'z_pval': 0
        },
        'stus': []
    }

    for i in range(len(rst['data']['primma']['stus'])):
        r = rst['data']['primma']['stus'][i]
        ret['stus'].append({
            'name': r['name'],
            'sm': r['sm'],
            'lower': r['lower'],
            'upper': r['upper'],
            'total': 0,
            'w': r['w.%s' % fixed_or_random],
        })

    return ret


def get_pwma_by_r_CAT_RAW(dataset,
    sm='OR', method='MH', fixed_or_random='random'):
    '''
    Get the PWMA results by R script (PRIM_CAT_RAW)
    The input dataset should follow:

    [Et, Nt, Ec, Nc, Name 1],
    [Et, Nt, Ec, Nc, Name 2], ...

    for example:

    dataset = [
        [41, 522, 59, 524, 'A'], 
        [8, 203, 18, 203, 'B']
    ]
    '''
    rs = []
    for d in dataset:
        rs.append({
            'study': d[4],
            'year': 2020,
            'Et': d[0],
            'Nt': d[1],
            'Ec': d[2],
            'Nc': d[3]
        })
    cfg = {
        'prj': 'ALL',
        'analyzer_model': 'PRIM_CAT_RAW',
        'fixed_or_random': fixed_or_random,
        'measure_of_effect': sm,
        'is_hakn': 'FALSE'
    }
    # use R to get the results
    rst = rplt_analyzer.analyze(rs, cfg)

    ret = {
        "model": {
            'measure': sm,
            'sm': rst['data']['primma']['model'][fixed_or_random]['sm'],
            'lower': rst['data']['primma']['model'][fixed_or_random]['lower'],
            'upper': rst['data']['primma']['model'][fixed_or_random]['lower'],
            'total': 0,
            'i2': rst['data']['primma']['heterogeneity']['i2'],
            'tau2': rst['data']['primma']['heterogeneity']['tau2'],
            'q_tval': 0,
            'q_pval': rst['data']['primma']['heterogeneity']['p'],
            'z_tval': 0,
            'z_pval': 0
        },
        'stus': []
    }

    for i in range(len(rst['data']['primma']['stus'])):
        r = rst['data']['primma']['stus'][i]
        ret['stus'].append({
            'name': r['name'],
            'sm': r['sm'],
            'lower': r['lower'],
            'upper': r['upper'],
            'total': r['Nt'],
            'w': r['w.%s' % fixed_or_random],
        })

    return ret


def get_ae_pma_data(full_fn, is_getting_sms=False):
    # load data
    xls = pd.ExcelFile(full_fn)

    # build AE Category data
    first_sheet_name = 'Adverse events'
    dft = xls.parse(first_sheet_name)
    ae_dict = {}
    ae_list = []

    for col in dft.columns:
        ae_cate = col
        # get those rows not NaN, which means containing adverse event name
        ae_names = dft[col][~dft[col].isna()]
        ae_item = {
            'ae_cate': ae_cate,
            'ae_names': []
        }
        # build ae_name dict
        for ae_name in ae_names:
            # remove the white space
            ae_name = ae_name.strip()
            if ae_name in ae_dict:
                cate1 = ae_dict[ae_name]
                print('! duplicate %s in [%s] and [%s]' % (ae_name, cate1, ae_cate))
                continue
            ae_dict[ae_name] = ae_cate
            ae_item['ae_names'].append(ae_name)

        ae_list.append(ae_item)
            
        print('* parsed ae_cate %s with %s names' % (col, len(ae_names)))
    print('* created ae_dict %s terms' % (len(ae_dict)))

    # build AE details
    cols = ['author', 'year', 'GA_Et', 'GA_Nt', 'GA_Ec', 'GA_Nc', 
            'G34_Et', 'G34_Ec', 'G3H_Et', 'G3H_Ec', 'G5N_Et', 'G5N_Ec', 
            'treatment', 'control']
    # sms = ['OR', 'RR', 'RD']
    sms = ['OR', 'RR']
    # grades = ['GA', 'G34', 'G3H', 'G5N']
    grades = ['GA', 'G3H', 'G5N']
    ae_dfts = []
    ae_rsts = {}

    # add detailed AE
    # the detailed AE starts from 3rd sheet
    # each sheet_name is an AE
    for sheet_name in xls.sheet_names[2:]:
        ae_name = sheet_name
        # the first row is no use
        # the second row is used as column name, but replaced with `cols` from A to N
        dft = xls.parse(sheet_name, skiprows=1, usecols='A:N', names=cols)
        
        # remove those empty lines based on author
        dft = dft[~dft.author.isna()]

        if len(dft) == 0: 
            print('* %s: [%s]' % (
                'EMPTY AE Tab'.ljust(25, ' '),
                ae_name.rjust(35, ' ')
            ))
            continue
        
        # add ae name here
        ae_name = ae_name.strip()
        ae_cate = ae_dict[ae_name]
        dft.loc[:, 'ae_cate'] = ae_cate
        dft.loc[:, 'ae_name'] = ae_name
        
        # add flag for each one, but need to be modified later
        dft.loc[:, 'has_GA'] = dft.GA_Et.notna()
        dft.loc[:, 'has_G34'] = dft.G34_Et.notna()
        dft.loc[:, 'has_G3H'] = dft.G3H_Et.notna()
        dft.loc[:, 'has_G5N'] = dft.G5N_Et.notna()

        # re-mark some flags to remove some studies
        for idx, r in dft.iterrows():
            # first, check the total number
            Nt = r['GA_Nt']
            Nc = r['GA_Nc']
            author = r['author']
            if np.isnan(Nt) or np.isnan(Nc):
                print('* %s: [%s] [%s] [%s] ' % (
                    'NaN Value Nt or Nc'.ljust(25, ' '),
                    ae_name.rjust(35, ' '), 
                    grade.rjust(3, ' '),
                    author
                ))
                # when Nt or Nc is NaN, the whole shouldn't appear
                for grade in grades:
                    dft.loc[idx, 'has_%s' % grade] = False
                continue

            for grade in grades:
                Et = r['%s_Et' % grade]
                Ec = r['%s_Ec' % grade]

                # second, check the Et, Ec NaN
                if np.isnan(Et) or np.isnan(Ec):
                    # print('* %s: [%s] [%s] [%s] ' % (
                    #     'Et or Ec is NaN'.ljust(25, ' '),
                    #     ae_name.rjust(35, ' '), 
                    #     grade.rjust(3, ' '), 
                    #     author
                    # ))
                    dft.loc[idx, 'has_%s' % grade] = False

                # third, check the Et Ec is 0
                if Et == 0 and Ec == 0:
                    # print('* %s: [%s] [%s] [%s]' % (
                    #     'ZERO Et and Ec'.ljust(25, ' '),
                    #     ae_name.rjust(35, ' '), 
                    #     grade.rjust(3, ' '), 
                    #     author
                    # ))
                    dft.loc[idx, 'has_%s' % grade] = False

        # add the AE model result
        # for each grade of each AE, the structure of rsts is as follows:
        # {
        #    'grade': grade,
        #    'stus': ['Name 1', 'Name 2'],
        #    'result': {
        #       'OR': {
        #          'random': pma_result,
        #          'fixed': pma_result
        #       } 
        #    }
        # }
        ae_rsts[ae_name] = {}
        for grade in grades:
            ae_rsts[ae_name][grade] = {
                'grade': grade,
                'stus': [],
                'Et': 0,
                'Nt': 0,
                'Ec': 0,
                'Nc': 0,
                'result': {}
            }
            # get records of this grade
            dftt = dft[dft['has_%s' % grade]==True]
            
            if len(dftt) < 2:
                # print('* %s: [%s] [%s]' % (
                #     'LESS than 2 studies'.ljust(25, ' '),
                #     ae_name.rjust(35, ' '), 
                #     grade.rjust(3, ' ')
                # ))
                continue 
            
            # ok, use the existing data to calcuate the 
            ae_rsts[ae_name][grade]['Et'] = int(dftt['%s_Et' % grade].sum())
            ae_rsts[ae_name][grade]['Nt'] = int(dftt['GA_Nt'].sum())
            ae_rsts[ae_name][grade]['Ec'] = int(dftt['%s_Ec' % grade].sum())
            ae_rsts[ae_name][grade]['Nc'] = int(dftt['GA_Nc'].sum())
            # fill the effective number of studies
            ae_rsts[ae_name][grade]['stus'] = dftt['author'].values.tolist()

            # get the dataset of this grade
            # from here, getting the OR/RR values of each AE of each grade
            if is_getting_sms:
                pass
            else: 
                continue

            # prepare the dataset for Pairwise MA
            ds = []
            for idx, r in dftt.iterrows():
                Et = r['%s_Et' % grade]
                Nt = r['GA_Nt']
                Ec = r['%s_Ec' % grade]
                Nc = r['GA_Nc']
                author = r['author']

                # a data fix for PythonMeta
                if Et == 0: Et = 0.4
                if Ec == 0: Ec = 0.4

                # convert data to PythonMeta Format
                ds.append([
                    Et,
                    Nt,
                    Ec, 
                    Nc,
                    author
                ])

            # for each sm, get the PWMA result
            for sm in sms:
                # get the pwma result
                try:
                    pma_r = get_pwma_by_py(ds, datatype="CAT_RAW", sm=sm, fixed_or_random='random')
                    # validate the result, if isNaN, just set None
                    if np.isnan(pma_r['model']['sm']):
                        pma_r = None
                    
                except:
                    print('* %s: [%s] [%s] [%s]' % (
                        'ISSUE Data cause error'.ljust(25, ' '),
                        ae_name.rjust(35, ' '), 
                        grade.rjust(3, ' '),
                        ds
                    ))
                    pma_r = None

                # use R script to calculate the OR/RR
                # pma_r = get_pwma_by_rplt(ds, datetype="CAT_RAW", sm=sm, fixed_or_random='random')

                ae_rsts[ae_name][grade]['result'][sm] = {
                    'random': pma_r,
                    # 'fixed': pma_f
                }
        
        # add to aes list
        ae_dfts.append(dft)

    # convert all small AE dft to a big one df_aes
    df_aes = pd.concat(ae_dfts)

    # fix data type
    df_aes['year'] = df_aes['year'].astype('int')
    def _asint(v):
        # if v is NaN
        if v!=v: return v
        # convert value to int
        try:
            v1 = int(v)
            return v1
        except:
            # convert other string to 0
            return 0
    for col in cols[2: -3]:
        df_aes[col] = df_aes[col].apply(_asint)
        df_aes[col] = df_aes[col].astype('Int64')

    # set index as a column
    df_aes = df_aes.reset_index()
    df_aes.rename(columns={'index': 'pid'}, inplace=True)
    rs = json.loads(df_aes.to_json(orient='records'))

    # build the return object
    ret = {
        'rs': rs,
        'ae_list': ae_list
    }

    if is_getting_sms:
        ret['ae_rsts'] = ae_rsts

    return ret


def get_ae_pma_data_simple(full_fn):
    # load data
    xls = pd.ExcelFile(full_fn)

    # build AE Category data
    first_sheet_name = xls.sheet_names[0]
    dft = xls.parse(first_sheet_name)
    dft = dft[~dft['name'].isna()]
    ae_dict = {}
    ae_list = []

    cie_cols = [
        'risk of bias',
        'inconsistency',
        'indirectness',
        'imprecision',
    ]

    col_pub_bia = 'publication bias'
    col_importance = 'importance'

    ae_item = {}
    for idx, row in dft.iterrows():
        ae_cate = row['category']
        ae_name = row['name']
        ae_fullname = row['full name']

        # create a new AE item to hold all the data
        if ae_item == {}:
            ae_item = {
                "ae_cate": ae_cate,
                "ae_names": []
            }
        elif ae_cate != ae_item['ae_cate']:
            # append the ae_cate and add a new one
            ae_list.append(ae_item)
            ae_item = {
                "ae_cate": ae_cate,
                "ae_names": []
            }
        
        # put current row in to ae_item
        ae_item['ae_names'].append(ae_name)

        # calc the Certainty in Evidence
        cie = calc_cie(row[cie_cols].tolist())

        # put current row in to ae_dict
        ae_dict[ae_name] = {
            "ae_cate": ae_cate,
            "ae_name": ae_name,
            "ae_fullname": ae_fullname,
            "cie": cie,
            "cie_rob": row[cie_cols[0]],
            "cie_inc": row[cie_cols[1]],
            "cie_ind": row[cie_cols[2]],
            "cie_imp": row[cie_cols[3]],
            "pub_bia": row['publication bias'],
            "importance": row[col_importance]
        }

    # put the last ae_item
    ae_list.append(ae_item)
    print('* created ae_dict %s terms' % (len(ae_dict)))

    # build AE details
    cols = ['study', 'year', 'Et', 'Nt', 'Ec', 'Nc', 'treatment', 'control']
    sms = ['OR', 'RR']
    ae_dfts = []
    ae_rsts = {}

    # add detailed AE
    # the detailed AE starts from 3rd sheet
    # each sheet_name is an AE
    for sheet_name in xls.sheet_names[1:]:
        ae_name = sheet_name
        # the first row is no use
        # the second row is used as column name, but replaced with `cols` from A to N
        dft = xls.parse(sheet_name, usecols='A:H', names=cols)
        
        # remove those empty lines based on author
        dft = dft[~dft.study.isna()]

        if len(dft) == 0: 
            print('* %s: [%s]' % (
                'EMPTY AE Tab'.ljust(25, ' '),
                ae_name.rjust(35, ' ')
            ))
            continue
        
        # add ae name here
        ae_name = ae_name.strip()
        ae_cate = ae_dict[ae_name]['ae_cate']
        ae_fullname = ae_dict[ae_name]['ae_fullname']
        dft.loc[:, 'ae_cate'] = ae_cate
        dft.loc[:, 'ae_name'] = ae_name
        dft.loc[:, 'ae_fullname'] = ae_fullname

        # add ae info
        ae_rsts[ae_name] = {
            'stus': [],
            'Et': 0,
            'Nt': 0,
            'Ec': 0,
            'Nc': 0,
            'result': {}
        }

        # copy ae_dict info to ae_rsts
        for k in ae_dict[ae_name]:
            ae_rsts[ae_name][k] = ae_dict[ae_name][k]
            
        # ok, use the existing data to calcuate the 
        ae_rsts[ae_name]['Et'] = int(dft['Et'].sum())
        ae_rsts[ae_name]['Nt'] = int(dft['Nt'].sum())
        ae_rsts[ae_name]['Ec'] = int(dft['Ec'].sum())
        ae_rsts[ae_name]['Nc'] = int(dft['Nc'].sum())

        # fill the effective number of studies
        ae_rsts[ae_name]['stus'] = dft['study'].values.tolist()

        # prepare the dataset for Pairwise MA
        ds = []
        for idx, r in dft.iterrows():
            Et = r['Et']
            Nt = r['Nt']
            Ec = r['Ec']
            Nc = r['Nc']
            study = r['study']

            # a data fix for PythonMeta
            if Et == 0: Et = 0.4
            if Ec == 0: Ec = 0.4

            # convert data to PythonMeta Format
            ds.append([
                Et,
                Nt,
                Ec, 
                Nc,
                study
            ])

            # for each sm, get the PWMA result
            for sm in sms:
                # get the pwma result
                try:
                    pma_r = get_pwma_by_py(ds, datatype="CAT_RAW", sm=sm, fixed_or_random='random')
                    # pma_r = get_pwma_by_rplt(ds, datatype="CAT_RAW", sm=sm, fixed_or_random='random')
                    # validate the result, if isNaN, just set None
                    if np.isnan(pma_r['model']['sm']):
                        pma_r = None
                    
                except:
                    print('* %s: [%s] [%s]' % (
                        'ISSUE Data cause error'.ljust(25, ' '),
                        ae_name.rjust(35, ' '), 
                        ds
                    ))
                    pma_r = None

                # use R script to calculate the OR/RR
                # pma_r = get_pwma_by_rplt(ds, datetype="CAT_RAW", sm=sm, fixed_or_random='random')

                ae_rsts[ae_name]['result'][sm] = {
                    'random': pma_r,
                    # 'fixed': pma_f
                }
        
        # add to aes list
        ae_dfts.append(dft)

    # convert all small AE dft to a big one df_aes
    df_aes = pd.concat(ae_dfts)

    # fix data type
    df_aes['year'] = df_aes['year'].astype('int')
    def _asint(v):
        # if v is NaN
        if v!=v: return v
        # convert value to int
        try:
            v1 = int(v)
            return v1
        except:
            # convert other string to 0
            return 0
    for col in cols[2: -3]:
        df_aes[col] = df_aes[col].apply(_asint)
        df_aes[col] = df_aes[col].astype('Int64')

    # set index as a column
    df_aes = df_aes.reset_index()
    df_aes.rename(columns={'index': 'pid'}, inplace=True)
    rs = json.loads(df_aes.to_json(orient='records'))

    # build the return object
    ret = {
        'rs': rs,
        'ae_list': ae_list,
        'ae_dict': ae_rsts
    }

    return ret


def get_nma_list_data(full_fn):
    # get all
    xls = pd.ExcelFile(full_fn)
    # build OC Category data
    oc_tab_name = 'Outcomes'

    ######################################
    # Build the NMA_LIST.json
    ######################################
    nma = OrderedDict()
    # read the first tab again
    dft = xls.parse(oc_tab_name)
    dft = dft[~dft['name'].isna()]
    print('* found %s outcome records' % (len(dft)))

    # only use those yes
    dft = dft[dft['included in plots']=='yes']
    print('* kept %s outcome records' % (len(dft)))

    for idx, row in dft.iterrows():
        nma_type = row['analysis title']
        oc_name = row['name']
        oc_fullname = row['full name']
        
        if nma_type not in nma: 
            nma[nma_type] = {
                '_default_oc': oc_name,
                'oc_names': []
            }
        
        # add this img
        nma[nma_type]['oc_names'].append({
            'oc_name': oc_name,
            'oc_fullname': oc_fullname
        })

    return nma


def get_oc_graph_data(full_fn):
    '''
    Get the OC GRAPH.json based on SOFTABLE_NMA_DATA.xlsx

    '''
    # get all
    xls = pd.ExcelFile(full_fn)

    ######################################
    # Build the GRAPH.json
    ######################################

    # build OC Category data
    oc_tab_name = 'Outcomes'
    dft = xls.parse(oc_tab_name)
    dft = dft[~dft['name'].isna()]

    # build oc category
    oc_dict = {}
    oc_names = []
    for idx, row in dft.iterrows():
        oc = {
            "oc_method": row['method'],
            "oc_name": row['name'],
            "oc_fullname": row['full name'],
            "oc_measures": row['measure'].split(','),
            "oc_datatype": row['data type'],
            "param": {
                "analysis_method": row["method"],
                "fixed_or_random": row["fixed_or_random"],
                "which_is_better": row["which_is_better"]
            },
            "treat_list": []
        }
        oc_dict[oc['oc_name']] = oc
        oc_names.append(oc['oc_name'])

    # get all NMA
    ret = {
        'oc_dict': oc_dict,
        'oc_names': oc_names,
        'graph_dict': {}
    }
    for oc_name in oc_names:
        oc = oc_dict[oc_name]
        sheet_name = oc_name

        # get measure
        measure = oc['oc_measures'][0]
        dft = xls.parse(sheet_name)

        # remove those empty lines based on study name
        # the study name MUST be different
        dft = dft[~dft.study.isna()]

        # get treat list
        if oc['oc_datatype'] == 'pre':
            treat_list = list(set(dft['t1'].unique().tolist() + dft['t2'].unique().tolist()))
            input_format = settings.INPUT_FORMATS_HRLU

        elif oc['oc_datatype'] == 'raw':
            treat_list = dft['treat'].unique().tolist()
            input_format = settings.INPUT_FORMATS_ET
            
        else:
            treat_list = dft['treat'].unique().tolist()
            input_format = settings.INPUT_FORMATS_ET

        # update the oc in oc_dict
        oc_dict[oc_name]['treat_list'] = treat_list

        # get config
        analysis_method = oc['param']['analysis_method']
        reference_treatment = treat_list[0]
        fixed_or_random = oc['param']['fixed_or_random']
        which_is_better = "big" if oc['param']['which_is_better'] in ['higher', 'bigger'] else "small"

        cfg = {
            # for init analyzer
            "backend": analysis_method,
            "input_format": input_format,
            "reference_treatment": reference_treatment,
            "measure_of_effect": measure,
            "fixed_or_random": fixed_or_random,
            "which_is_better": which_is_better
        }

        # get the rs for this oc
        rs = json.loads(dft.to_json(orient='table', index=False))['data']

        # calc!
        ret_nma = nma_analyzer.analyze(rs, cfg)

        # put in result
        ret['graph_dict'][oc_name] = ret_nma

    ######################################
    # Build the GRAPH-outcome.json
    ######################################
    # then, dump each oc
    # for oc_name in ret['oc_names']:
    #     # use upper and underscore to convert name to id
    #     oc_name_id = oc_name.upper().replace(' ', '_')
    #     full_oc_fn_json_name = full_oc_fn_json % oc_name_id
    #     # dump!
    #     json.dump(ret['graph_dict'][oc_name], open(full_oc_fn_json_name, 'w'))
        
    # generate a NMA_LIST.json for pub
    # nma_list = { 'nma': [] }
    # for oc_name in ret['oc_names']:
    #     oc = oc_dict[oc_name]
    #     # save to nma list
    #     nma_list['nma'].append({
    #         'name': oc['oc_fullname'],
    #         'sname': oc['oc_name'].upper().replace(' ', '_'),
    #         'treats': oc['treat_list']
    #     })
    # json.dump(nma_list, open(full_nma_list_json, 'w'), indent=4)

    return ret


def get_sof_nma_data(full_fn):
    '''
    Get the SoF Table NMA data

    The backend supports:

    - bayes
    - freq

    '''
    xls = pd.ExcelFile(full_fn)
    
    # build OC Category data
    oc_tab_name = 'Outcomes'
    oc_tab_cert = 'Certainty'
    oc_tab_treats = 'Treatments'

    dft = xls.parse(oc_tab_name)
    dft = dft[~dft['name'].isna()]
    
    # only include those should be included in sof
    dft = dft[dft['included in sof'] == 'yes']

    # build oc category
    oc_dict = {}
    oc_list = []
    oc_item = {}
    oc_names = []
    for idx, row in dft.iterrows():
        oc_cate = row['category']
        oc_name = row['name']
        oc_fullname = row['full name']
        oc_names.append(oc_name)

        # create a new outcome item to hold all the data
        if oc_item == {}:
            oc_item = {
                "oc_cate": oc_cate,
                "oc_names": []
            }
        elif oc_cate != oc_item['oc_cate']:
            # append the oc_cate and add a new one
            oc_list.append(oc_item)
            oc_item = {
                "oc_cate": oc_cate,
                "oc_names": []
            }
        
        # put current row in to oc_item
        oc_item['oc_names'].append(oc_name)

        # put current row in to ae_dict
        oc_dict[oc_name] = {
            "oc_method": row['method'],
            "oc_cate": oc_cate,
            "oc_measures": row['measure'].split(','),
            "oc_datatype": row['data type'],
            "oc_name": oc_name,
            "oc_fullname": oc_fullname,
            "param": {
                "analysis_method": row["method"],
                "fixed_or_random": row["fixed_or_random"],
                "which_is_better": row["which_is_better"]
            },
            "cetable": {},
            "lgtable": {},
            "rktable": {},
            "treats": {}
        }

    # put the last ae_item
    oc_list.append(oc_item)
    print('* created oc_dict %s terms' % (len(oc_dict)))

    # define the columns for basic information of outcome
    cols_range = 'A:K'
    cols_certs = [
        'oc_cate', 'oc_name', 'comparator', 'treatment', 
        'cie_rob', 'cie_inc', 'cie_ind', 'cie_imp', 'pub_bia',
        'cie_coh', 'cie_trs'
    ]

    # build certainty
    if oc_tab_cert in xls.sheet_names:

        dft = xls.parse(oc_tab_cert, usecols=cols_range, names=cols_certs)

        # there maybe nan 
        dft = dft[~dft['oc_name'].isna()]

        for idx, row in dft.iterrows():
            oc_cate = row['oc_cate']
            oc_name = row['oc_name']
            comparator = row['comparator']
            treatment = row['treatment']

            # 2021-02-19: skip those not included in sof
            if oc_name not in oc_names:
                print('* skip oc [%s] due to NOT included-in-sof' % oc_tab_cert)
                continue

            if comparator not in oc_dict[oc_name]['cetable']:
                oc_dict[oc_name]['cetable'][comparator] = { comparator: {} }

            # put the comparator vs treatment {} in 
            oc_dict[oc_name]['cetable'][comparator][treatment] = {}

            # put the values of each column
            for col in cols_certs[4:]:
                try:
                    oc_dict[oc_name]['cetable'][comparator][treatment][col] = int(row[col])
                except:
                    oc_dict[oc_name]['cetable'][comparator][treatment][col] = 0

            # calc the cie of this row
            oc_dict[oc_name]['cetable'][comparator][treatment]['cie'] = \
                calc_cie(row[cols_certs[4:8]].tolist())


    # build OC details by the data type
    cols_dict = settings.SOFTABLE_NMA_COLS
    oc_dfts = []
    oc_rsts = {}

    # add detailed OC
    # create an all_treats for holding the data
    all_treat_list = []
    for oc_name in oc_names:
        oc = oc_dict[oc_name]
        sheet_name = oc_name

        # get the data
        usecols = cols_dict[oc['oc_datatype']][0]
        namecols = cols_dict[oc['oc_datatype']][1]
        dft = xls.parse(sheet_name, usecols=usecols, names=namecols)

        # remove those empty lines based on study name
        # the study name MUST be different
        dft = dft[~dft.study.isna()]

        # empty data???
        if len(dft) == 0: 
            print('* %s: [%s]' % (
                'EMPTY OC Tab'.ljust(25, ' '),
                oc_name.rjust(35, ' ')
            ))
            continue

        # build detail for the treatments of this oc
        treats = {}
        treat_list = []
        if oc['oc_datatype'] == 'raw':
            # treat column contains all the treatments
            treat_list = dft['treat'].unique().tolist()

            # get the total number of each treat
            dftt = dft.groupby('treat')[['event', 'total']].sum()
            for idx, row in dftt.iterrows():
                treat = idx
                treats[treat] = {
                    "event": int(row['event']),
                    "total": int(row['total']),
                    'has_survival_data': False,
                    'has_internal_val': True,
                    'survival_in_control': 0,
                    "n_stus": 0,
                    "rank": 0
                }

            # count how many studies for each treatment
            dftt = dft.groupby('treat')[['study']].count()
            for idx, row in dftt.iterrows():
                treat = idx
                treats[treat]['n_stus'] = int(row['study'])

        elif oc['oc_datatype'] == 'pre':
            # need to get all the treats from t1 and t2
            treat_list = list(set(dft['t1'].unique().tolist() + dft['t2'].unique().tolist()))

            # due to the missing data, we need to count each treatment line by line
            for idx, row in dft.iterrows():
                t1 = row['t1']
                t2 = row['t2']

                # init the t1 and t2 with 0
                if t1 not in treats: 
                    treats[t1] = {
                        'survival_in_control': 0,
                        'n_stus': 0,
                        'rank': 0,
                        'internal_val_et': 0,
                        'internal_val_ec': 0,
                    }
                if t2 not in treats: 
                    treats[t2] = {
                        'survival_in_control': 0,
                        'n_stus': 0,
                        'rank': 0,
                        'internal_val_et': 0,
                        'internal_val_ec': 0,
                    }

                # count the survival when value is float for t1
                treats[t1]['n_stus'] += 1
                try:
                    _srvc = float(row['survival in t1'])
                except:
                    _srvc = None
                if pd.isna(_srvc):
                    pass
                else:
                    treats[t1]['survival_in_control'] += _srvc
            
                # count the survival when value is float for t2
                treats[t2]['n_stus'] += 1
                try:
                    _srvc = float(row['survival in t2'])
                except:
                    _srvc = None
                if pd.isna(_srvc):
                    pass
                else:
                    treats[t2]['survival_in_control'] += _srvc

                # count the Ec and Et of t1
                try: 
                    treats[t1]['internal_val_ec'] += int(row['Ec_t1']) * 1000 / int(row['Et_t1'])
                    treats[t1]['internal_val_et'] += 1000
                except:
                    if row['Ec_t1'] in ['NA', 'NR']:
                        pass
                    
                # count the Ec and Et of t2
                try: 
                    treats[t2]['internal_val_ec'] += int(row['Ec_t2']) * 1000 / int(row['Et_t2'])
                    treats[t2]['internal_val_et'] += 1000
                except:
                    if row['Ec_t2'] in ['NA', 'NR']:
                        pass
            
            # need to update the survival in control
            for t in treats:
                # update the survival data
                treats[t]['has_survival_data'] = treats[t]['survival_in_control'] != 0
                treats[t]['survival_in_control'] = {
                    "avg": treats[t]['survival_in_control'] / treats[t]['n_stus']
                }

                # update the external base data
                treats[t]['has_internal_val'] = treats[t]['internal_val_et'] != 0
                if treats[t]['has_internal_val']:
                    treats[t]['internal_val'] = int(1000 * treats[t]['internal_val_ec'] / treats[t]['internal_val_et'])
                else:
                    treats[t]['internal_val'] = 100

        else:
            pass

        # update treats
        all_treat_list += treat_list

        # after gathering all the treats, bind to oc_dict
        oc_dict[oc_name]['treats'] = treats

        # now get the league table
        oc_dict[oc_name]['lgtable'] = {}

        # get the records
        rs = json.loads(dft.to_json(orient='table', index=False))['data']

        # for each measure, HR, OR, RR ... etc
        for sm in oc['oc_measures']:
            # init this measure with a blank table
            oc_dict[oc_name]['lgtable'][sm] = {}

            # init this measure with a blank table for rank
            oc_dict[oc_name]['rktable'][sm] = {}

            # make a config dict for get the league table
            cfg = {
                # for init analyzer
                "backend": oc['param']['analysis_method'],
                "input_format": {
                    'pre': settings.INPUT_FORMATS_HRLU, 
                    'raw': settings.INPUT_FORMATS_ET,
                    'raw_time': settings.INPUT_FORMATS_FTET
                }[oc['oc_datatype']],
                "measure_of_effect": sm,
                "fixed_or_random": oc['param']['fixed_or_random'],
                # just use the first one as 
                "reference_treatment": treat_list[0],
                "which_is_better": 'big' if oc['param']["which_is_better"] in ['higher', 'bigger'] else 'small'
            }
            
            # invoke analyzer
            ret_nma = nma_analyzer.analyze(rs, cfg)

            # convert nma result to page format
            tmp_lgtable_sm = _conv_nmarst_league_to_lgtable(ret_nma)
            oc_dict[oc_name]['lgtable'][sm] = tmp_lgtable_sm

            # get the rank data
            # 2/16/2021: use the method specified in the input file
            if oc['param']['analysis_method'] == 'freq':
                rank_name = 'psrank'

            elif oc['param']['analysis_method'] == 'bayes':
                rank_name = 'tmrank'

            else:
                rank_name = 'psrank'

            # get the output rank
            # 9/23/2020: add reverse, the higher value, the higher rank
            reverse = True

            # # 10/3/2020: add reverse according to the which_is_better column
            # if oc_dict[oc_name]['param']['which_is_better'] == 'lower':
            #     reverse = False
            # else:
            #     reverse = True
            # if sm in ['HR']:
            #     reverse = False
            print('* for %s, which is better: %s, %s' % (
                oc_name, oc_dict[oc_name]['param']['which_is_better'], 
                reverse
            ))
            
            ranks = sorted(ret_nma['data'][rank_name]['rs'], 
                key=lambda v: v['value'],
                reverse=reverse)

            for i, r in enumerate(ranks):
                oc_dict[oc_name]['treats'][r['treat']]['rank'] = i+1
                oc_dict[oc_name]['treats'][r['treat']]['score'] = r['value']
                # put the ranks in the sm
                oc_dict[oc_name]['rktable'][sm][r['treat']] = {
                    'rank': i + 1,
                    'score': r['value']
                }

    # get the list of all the treatments
    dft = xls.parse(oc_tab_treats)
    dft = dft[~dft['treats'].isna()]
    treat_list = dft['treats'].tolist()

    # return object
    ret = {
        'oc_dict': oc_dict,
        'oc_list': oc_list,
        'treat_list': treat_list
    }

    return ret


def get_ae_nma_data(full_fn, backend):
    '''
    Deprecated

    Get the SoF Table NMA data

    the backend supports:

    - bayes
    - freq
    '''
    # load data
    xls = pd.ExcelFile(full_fn)
    
    # build AE Category data
    # The sheets:
    # 1. Adverse events
    # 2. Certainty
    # 3  all the aes
    first_sheet_name = xls.sheet_names[0]
    dft = xls.parse(first_sheet_name)

    # ignore nan rows
    dft = dft[~dft['name'].isna()]
    ae_dict = {}
    ae_list = []

    ae_item = {}
    for idx, row in dft.iterrows():
        ae_cate = row['category']
        ae_name = row['name']
        ae_fullname = row['full name']

        # create a new AE item to hold all the data
        if ae_item == {}:
            ae_item = {
                "ae_cate": ae_cate,
                "ae_names": []
            }
        elif ae_cate != ae_item['ae_cate']:
            # append the ae_cate and add a new one
            ae_list.append(ae_item)
            ae_item = {
                "ae_cate": ae_cate,
                "ae_names": []
            }
        
        # put current row in to ae_item
        ae_item['ae_names'].append(ae_name)

        # put current row in to ae_dict
        ae_dict[ae_name] = {
            "ae_cate": ae_cate,
            "ae_name": ae_name,
            "ae_fullname": ae_fullname,
            "cetable": {}
        }
        
    # put the last ae_item
    ae_list.append(ae_item)

    # get the certainty for each combination of each ae
    sheet_name_2 = xls.sheet_names[1]
    cols_certs = [
        'ae_cate', 'ae_name', 'comparator', 'treatment', 
        'cie_rob', 'cie_inc', 'cie_ind', 'cie_imp', 'pub_bia'
    ]
    dft = xls.parse(sheet_name_2, usecols='A:I', names=cols_certs)
    for idx, row in dft.iterrows():
        ae_cate = row['ae_cate']
        ae_name = row['ae_name']
        comparator = row['comparator']
        treatment = row['treatment']

        if comparator not in ae_dict[ae_name]['cetable']:
            ae_dict[ae_name]['cetable'][comparator] = { comparator: {} }

        # put the CIE values in 
        ae_dict[ae_name]['cetable'][comparator][treatment] = {}

        for col in cols_certs[4:]:
            ae_dict[ae_name]['cetable'][comparator][treatment][col] = row[col]

        # calc the cie of this row
        ae_dict[ae_name]['cetable'][comparator][treatment]['cie'] = calc_cie(row[cols_certs[4:8]].tolist())


    # extract the results
    cols = ['study', 'treat', 'event', 'total']
    sms = ['OR', 'RR']
    ae_dfts = []
    ae_rsts = {}

    for sheet_name in xls.sheet_names[2:]:
        ae_name = sheet_name
        # the first row is used as column name, but replaced with `cols` from A to D
        dft = xls.parse(sheet_name, usecols='A:D', names=cols)

        # remove those empty lines based on first col
        dft = dft[~dft[cols[0]].isna()]
        
        # get the record list like:
        # [
        #    { "col1": val1, "col2": val2 }, ...
        # ]
        rs = json.loads(dft.to_json(orient='table', index=False))['data']

        if len(dft) == 0: 
            print('* %s: [%s]' % (
                'EMPTY OC Tab'.ljust(25, ' '),
                ae_name.rjust(35, ' ')
            ))
            continue

        # count the treats and bind to ae_dict
        treat_list = dft['treat'].unique().tolist()
        ae_dict[ae_name]['treat_list'] = treat_list

        # sum the event and total
        dftt = dft.groupby('treat')[['event', 'total']].sum()
        treats = {}
        for idx, row in dftt.iterrows():
            treat = idx
            treats[treat] = {
                "event": int(row['event']),
                "total": int(row['total']),
                "rank": 0
            }
        # count how many studies for each treatment
        dftt = dft.groupby('treat')[['study']].count()
        for idx, row in dftt.iterrows():
            treat = idx
            treats[treat]['n_stus'] = int(row['study'])
        
        # update the treats list 
        ae_dict[ae_name]['treats'] = treats

        # now get the league table
        ae_dict[ae_name]['lgtable'] = {}
        for sm in sms:
            ae_dict[ae_name]['lgtable'][sm] = {}

            # make a config dictionary for calcuating
            cfg = {
                # for init analyzer
                "backend": backend,
                "input_format": "ET",
                "data_type": 'CAT_RAW',

                # for R script
                "measure_of_effect": sm,
                "fixed_or_random": 'fixed',
                "reference_treatment": treat_list[0],
                "which_is_better": 'big'
            }

            # get the league table
            ret_nma = nma_analyzer.analyze(rs, cfg)

            # convert nma result to page format
            lgt_cols = ret_nma['data']['league']['cols']
            for lgt_rs in ret_nma['data']['league']['tabledata']:
                lgt_r = lgt_rs['row']
                # create a new comparator row
                ae_dict[ae_name]['lgtable'][sm][lgt_r] = {}

                for j, lgt_c in enumerate(lgt_cols):
                    lgt_cell = {
                        "sm": lgt_rs['stat'][j],
                        'lw': lgt_rs['lci'][j],
                        'up': lgt_rs['uci'][j]
                    }
                    # create a new treat col
                    ae_dict[ae_name]['lgtable'][sm][lgt_r][lgt_c] = lgt_cell

            # get the rank data
            if backend == 'freq':
                rank_name = 'psrank'
            elif backend == 'bayes':
                rank_name = 'tmrank'

            # get the output rank
            ranks = sorted(ret_nma['data'][rank_name]['rs'], key=lambda v: v['value'])
            for i, r in enumerate(ranks):
                ae_dict[ae_name]['treats'][r['treat']]['rank'] = i+1
                ae_dict[ae_name]['treats'][r['treat']]['score'] = r['value']

            # bind the raw results
            # ae_dict[ae_name]['lgtable'][sm]['raw_rst'] = ret_nma

    # return object
    rs = []
    ret = {
        'rs': rs,
        'ae_dict': ae_dict,
        'ae_list': ae_list
    }

    return ret


def get_sof_pma_data_IO(full_fn, is_calc_pwma=True):
    '''
    Get the data for SoF / Plots (IO project only)
    '''
    # load data
    xls = pd.ExcelFile(full_fn)

    # build AE Category data
    first_sheet_name = 'Adverse events'
    dft = xls.parse(first_sheet_name)
    oc_dict = {}
    oc_list = []

    for col in dft.columns:
        oc_cate = col
        # get those rows not NaN, which means containing adverse event name
        oc_names = dft[col][~dft[col].isna()]
        oc_item = {
            'oc_cate': oc_cate,
            'oc_names': []
        }
        # build ae_name dict
        for oc_name in oc_names:
            # remove the white space
            oc_name = oc_name.strip()
            if oc_name in oc_dict:
                cate1 = oc_dict[oc_name]
                print('! duplicate oc_name %s in [%s] and [%s]' % (oc_name, cate1, oc_cate))
                continue

            oc_dict[oc_name] = oc_cate
            oc_item['oc_names'].append(oc_name)

        oc_list.append(oc_item)
            
        print('* parsed oc_cate %s with %s names' % (col, len(oc_names)))

    print('* created oc_dict %s terms' % (len(oc_dict)))

    # build AE details
    cols = ['author', 'year', 'GA_Et', 'GA_Nt', 'GA_Ec', 'GA_Nc', 
            'G34_Et', 'G34_Ec', 'G3H_Et', 'G3H_Ec', 'G5N_Et', 'G5N_Ec', 
            'treatment', 'control']
    # sms = ['OR', 'RR', 'RD']
    sms = ['OR', 'RR']
    # grades = ['GA', 'G34', 'G3H', 'G5N']
    grades = ['GA', 'G3H', 'G5N']

    oc_dfts = []
    oc_rsts = {}

    # add detailed AE
    # the detailed AE starts from 3rd sheet
    # each sheet_name is an AE
    for sheet_name in xls.sheet_names[2:]:
        oc_name = sheet_name
        # the first row is no use
        # the second row is used as column name, but replaced with `cols` from A to N
        dft = xls.parse(sheet_name, skiprows=1, usecols='A:N', names=cols)
        
        # remove those empty lines based on author
        dft = dft[~dft.author.isna()]

        if len(dft) == 0: 
            print('* %s: [%s]' % (
                'EMPTY AE Tab'.ljust(25, ' '),
                oc_name.rjust(35, ' ')
            ))
            continue
        
        # add ae name here
        oc_name = oc_name.strip()
        oc_cate = oc_dict[oc_name]
        dft.loc[:, 'oc_cate'] = oc_cate
        dft.loc[:, 'oc_name'] = oc_name
        
        # add flag for each one, but need to be modified later
        dft.loc[:, 'has_GA'] = dft.GA_Et.notna()
        dft.loc[:, 'has_G34'] = dft.G34_Et.notna()
        dft.loc[:, 'has_G3H'] = dft.G3H_Et.notna()
        dft.loc[:, 'has_G5N'] = dft.G5N_Et.notna()

        # re-mark some flags to remove some studies
        for idx, r in dft.iterrows():
            # first, check the total number
            Nt = r['GA_Nt']
            Nc = r['GA_Nc']
            author = r['author']
            if np.isnan(Nt) or np.isnan(Nc):
                print('* %s: [%s] [%s] [%s] ' % (
                    'NaN Value Nt or Nc'.ljust(25, ' '),
                    oc_name.rjust(35, ' '), 
                    grade.rjust(3, ' '),
                    author
                ))
                # when Nt or Nc is NaN, the whole shouldn't appear
                for grade in grades:
                    dft.loc[idx, 'has_%s' % grade] = False
                continue

            for grade in grades:
                Et = r['%s_Et' % grade]
                Ec = r['%s_Ec' % grade]

                # second, check the Et, Ec NaN
                if np.isnan(Et) or np.isnan(Ec):
                    # print('* %s: [%s] [%s] [%s] ' % (
                    #     'Et or Ec is NaN'.ljust(25, ' '),
                    #     ae_name.rjust(35, ' '), 
                    #     grade.rjust(3, ' '), 
                    #     author
                    # ))
                    dft.loc[idx, 'has_%s' % grade] = False

                # third, check the Et Ec is 0
                if Et == 0 and Ec == 0:
                    # print('* %s: [%s] [%s] [%s]' % (
                    #     'ZERO Et and Ec'.ljust(25, ' '),
                    #     ae_name.rjust(35, ' '), 
                    #     grade.rjust(3, ' '), 
                    #     author
                    # ))
                    dft.loc[idx, 'has_%s' % grade] = False

        # add the AE model result
        # for each grade of each AE, the structure of rsts is as follows:
        # {
        #    'grade': grade,
        #    'stus': ['Name 1', 'Name 2'],
        #    'result': {
        #       'OR': {
        #          'random': pma_result,
        #          'fixed': pma_result
        #       } 
        #    }
        # }
        oc_rsts[oc_name] = {}

        # check each grade, GA, G3H, G5N
        for grade in grades:
            # create the result object for this grade
            oc_rsts[oc_name][grade] = {
                'grade': grade,
                'stus': [],
                'Et': 0,
                'Nt': 0,
                'Ec': 0,
                'Nc': 0,
                'result': {}
            }
            # get records of this grade
            dftt = dft[dft['has_%s' % grade]==True]
            
            # for those don't have at least 2 records, skip
            # because couldn't do analysis with less than 2 records
            if len(dftt) < 2:
                # print('* %s: [%s] [%s]' % (
                #     'LESS than 2 studies'.ljust(25, ' '),
                #     ae_name.rjust(35, ' '), 
                #     grade.rjust(3, ' ')
                # ))
                continue 
            
            # ok, use the existing data to calcuate the result
            oc_rsts[oc_name][grade]['Et'] = int(dftt['%s_Et' % grade].sum())
            oc_rsts[oc_name][grade]['Nt'] = int(dftt['GA_Nt'].sum())
            oc_rsts[oc_name][grade]['Ec'] = int(dftt['%s_Ec' % grade].sum())
            oc_rsts[oc_name][grade]['Nc'] = int(dftt['GA_Nc'].sum())

            # fill the studies list with author names
            oc_rsts[oc_name][grade]['stus'] = dftt['author'].values.tolist()

            # get the dataset of this grade
            # from here, getting the OR/RR values of each AE of each grade
            if is_calc_pwma:
                pass
            else: 
                continue

            # prepare the dataset for PWMA
            # the `ds` will looks like a matrix:
            # [
            #    [ Et, Nt, Ec, Nc, author1 ],
            #    [ Et, Nt, Ec, Nc, author2 ],
            #    ...
            # ]
            # this `ds` is prepared the pymeta package
            # the GA_Nt and GA_Nc are shared in all grades
            ds = []

            for idx, r in dftt.iterrows():
                Et = r['%s_Et' % grade]
                Nt = r['GA_Nt']
                Ec = r['%s_Ec' % grade]
                Nc = r['GA_Nc']
                author = r['author']

                # a data fix for PythonMeta
                if Et == 0: Et = 0.4
                if Ec == 0: Ec = 0.4

                # convert data to PythonMeta Format
                ds.append([
                    Et,
                    Nt,
                    Ec, 
                    Nc,
                    author
                ])

            # for each sm, get the PWMA result
            for sm in sms:
                # get the pwma result
                try:
                    # use Python package to calculate the OR/RR
                    pma_r = get_pwma_by_py(ds, datatype="CAT_RAW", sm=sm, fixed_or_random='random')
                    # pma_f = get_pwma_by_py(ds, datatype="CAT_RAW", sm=sm, fixed_or_random='fixed')
 
                    # validate the result, if isNaN, just set None
                    if np.isnan(pma_r['model']['sm']):
                        pma_r = None

                    # if np.isnan(pma_f['model']['sm']):
                    #     pma_f = None

                    # use R package to calculate the OR/RR
                    # pma_r = get_pwma_by_rplt(ds, datetype="CAT_RAW", sm=sm, fixed_or_random='random')
                    # pma_f = get_pwma_by_rplt(ds, datetype="CAT_RAW", sm=sm, fixed_or_random='fixed')
                    
                except:
                    print('* %s: [%s] [%s] [%s]' % (
                        'ISSUE Data cause error'.ljust(25, ' '),
                        oc_name.rjust(35, ' '), 
                        grade.rjust(3, ' '),
                        ds
                    ))
                    pma_r = None
                    # pma_f = None

                oc_rsts[oc_name][grade]['result'][sm] = {
                    'random': pma_r,
                    # 'fixed': pma_f
                }
        
        # add to aes list
        oc_dfts.append(dft)

    # convert all small AE dft to a big one df_aes
    df_aes = pd.concat(oc_dfts)

    # fix data type
    df_aes['year'] = df_aes['year'].astype('int')
    def _asint(v):
        # if v is NaN
        if v!=v: return v
        # convert value to int
        try:
            v1 = int(v)
            return v1
        except:
            # convert other string to 0
            return 0
    for col in cols[2: -3]:
        df_aes[col] = df_aes[col].apply(_asint)
        df_aes[col] = df_aes[col].astype('Int64')

    # set index as a column
    df_aes = df_aes.reset_index()
    df_aes.rename(columns={'index': 'pid'}, inplace=True)
    rs = json.loads(df_aes.to_json(orient='records'))

    # build the return object
    ret = {
        'rs': rs,
        'oc_list': oc_list
    }

    if is_calc_pwma:
        ret['oc_dict'] = oc_rsts

    return ret


def get_sof_pma_data(full_fn):
    '''
    The OC data for PWMA
    Support different types of data and 
    '''
    # load data
    xls = pd.ExcelFile(full_fn)

    # build OC Category data
    oc_tab_name = 'Outcomes'

    # define the columns for basic information of outcome
    cols_outcome = [
        'oc_cate', 'oc_rtitle', 'oc_iisof',
        'oc_measures', 'fixed_or_random', 'which_is_better',
        'oc_datatype', 'oc_name', 'oc_fullname',
        'cie_rob', 'cie_inc', 'cie_ind', 'cie_imp', 'pub_bia', 
        'importance', 'treatment', 'control'
    ]
    dft = xls.parse(oc_tab_name, usecols='A:Q', names=cols_outcome)
    dft = dft[~dft['oc_name'].isna()]

    # 2021-02-19: fix the include in sof not working
    # only include those should be included in sof
    dft = dft[dft['oc_iisof'] == 'yes']

    # build oc category
    oc_dict = {}
    oc_list = []
    oc_item = {}
    oc_names = []
    for idx, row in dft.iterrows():
        oc_cate = row['oc_cate']
        oc_name = row['oc_name']
        oc_fullname = row['oc_fullname']
        oc_names.append(oc_name)

        # create a new outcome item to hold all the data
        if oc_item == {}:
            oc_item = {
                "oc_cate": oc_cate,
                "oc_names": []
            }
        elif oc_cate != oc_item['oc_cate']:
            # append the oc_cate and add a new one
            oc_list.append(oc_item)
            oc_item = {
                "oc_cate": oc_cate,
                "oc_names": []
            }
        
        # put current row in to oc_item
        oc_item['oc_names'].append(oc_name)

        # calc the Certainty in Evidence
        cie = calc_cie(row[['cie_rob', 'cie_inc', 'cie_ind', 'cie_imp']].tolist())

        # put current row in to ae_dict
        oc_dict[oc_name] = {
            "oc_cate": oc_cate,
            "oc_measures": row['oc_measures'].split(','),
            "oc_datatype": row['oc_datatype'],
            "oc_name": oc_name,
            "oc_fullname": oc_fullname,
            "param": {
                "fixed_or_random": row["fixed_or_random"],
                "which_is_better": row["which_is_better"]
            },
            "cie": cie,
        }

        # put the cie columns
        # 'cie_rob', 'cie_inc', 'cie_ind', 'cie_imp', 'pub_bia', 'importance'
        for col in ['cie_rob', 'cie_inc', 'cie_ind', 'cie_imp', 'pub_bia']:
            try:
                oc_dict[oc_name][col] = int(row[col])
            except:
                oc_dict[oc_name][col] = 0
        
        oc_dict[oc_name]['importance'] = row['importance']

    # put the last ae_item
    oc_list.append(oc_item)
    print('* created oc_dict %s terms' % (len(oc_dict)))

    # build OC details by the data type
    cols_dict = {
        'raw': ['A:H', ['study', 'year', 'Et', 'Nt', 'Ec', 'Nc', 'treatment', 'control']],
        'pre': ['A:J', ['study', 'year', 'TE', 'lowerci', 'upperci', 'treatment', 'control', 'survival in control', 'Ec', 'Et']]
    }
    oc_dfts = []
    oc_rsts = {}

    # add detailed OC
    # each sheet_name is an outcome data
    for oc_name in oc_names:
        oc_item = oc_dict[oc_name]
        sheet_name = oc_name

        # get the data depends on the data type
        usecols = cols_dict[oc_item['oc_datatype']][0]
        namecols = cols_dict[oc_item['oc_datatype']][1]
        dft = xls.parse(sheet_name, usecols=usecols, names=namecols)
        
        # remove those empty lines based on study name
        # the study name MUST be different
        dft = dft[~dft.study.isna()]

        # empty data???
        if len(dft) == 0: 
            print('* %s: [%s]' % (
                'EMPTY AE Tab'.ljust(25, ' '),
                oc_name.rjust(35, ' ')
            ))
            continue
        
        # add outcome name on each lines of this data tab
        oc_cate = oc_item['oc_cate']
        oc_fullname = oc_item['oc_fullname']
        oc_datatype = oc_item['oc_datatype']
        dft.loc[:, 'oc_cate'] = oc_cate
        dft.loc[:, 'oc_name'] = oc_name
        dft.loc[:, 'oc_fullname'] = oc_fullname

        # add ae info
        oc_rsts[oc_name] = {
            'stus': [],
            # Et, Nt, Ec, Nc are for raw data
            'Et': 0,
            'Nt': 0,
            'Ec': 0,
            'Nc': 0,
            # TE, lowerci, upperci are for pre data
            'TE': 0,
            'lowerci': 0,
            'upperci': 0,
            # external base for 1000
            'external_val': DEFAULT_EXTERNAL_VAL,
            # survival in control
            'survival_in_control': 0,
            # result is for the model
            'result': {}
        }

        # copy oc_dict info to oc_rsts
        for k in oc_dict[oc_name]:
            oc_rsts[oc_name][k] = oc_dict[oc_name][k]
            
        # fill the effective number of studies
        oc_rsts[oc_name]['stus'] = dft['study'].values.tolist()

        # ok, use the existing data to calcuate number
        # for the total, depends on the data type
        # prepare the dataset for Pairwise MA
        ds = []
        if oc_datatype == 'raw':
            oc_rsts[oc_name]['Et'] = int(dft['Et'].sum())
            oc_rsts[oc_name]['Nt'] = int(dft['Nt'].sum())
            oc_rsts[oc_name]['Ec'] = int(dft['Ec'].sum())
            oc_rsts[oc_name]['Nc'] = int(dft['Nc'].sum())

            for idx, r in dft.iterrows():
                Et = r['Et']
                Nt = r['Nt']
                Ec = r['Ec']
                Nc = r['Nc']
                study = r['study']

                # a data fix for PythonMeta
                if Et == 0: Et = 0.4
                if Ec == 0: Ec = 0.4

                # convert data to PythonMeta Format
                ds.append([ Et, Nt, Ec, Nc, study ])
            oc_rsts[oc_name]['has_internal_val'] = True

        elif oc_datatype == 'pre':
            oc_rsts[oc_name]['TE'] = float(dft['TE'].mean())
            oc_rsts[oc_name]['lowerci'] = float(dft['lowerci'].mean())
            oc_rsts[oc_name]['upperci'] = float(dft['upperci'].mean())
            
            # set the internal value for this outcome
            oc_rsts[oc_name]['internal_val_ec'] = 0
            oc_rsts[oc_name]['internal_val_et'] = 0
            for idx, row in dft.iterrows():
                try: 
                    oc_rsts[oc_name]['internal_val_ec'] += int(row['Ec']) * 1000 / int(row['Et'])
                    oc_rsts[oc_name]['internal_val_et'] += 1000
                except:
                    if row['Ec'] in ['NA', 'NR']:
                        pass

            oc_rsts[oc_name]['has_internal_val'] = oc_rsts[oc_name]['internal_val_et'] != 0
            if oc_rsts[oc_name]['has_internal_val']:
                oc_rsts[oc_name]['internal_val'] = int(1000 * oc_rsts[oc_name]['internal_val_ec'] / oc_rsts[oc_name]['internal_val_et'])
            else:
                oc_rsts[oc_name]['internal_val'] = None

            # oc_rsts[oc_name]['external_val'] = int(dft['Ec'].mean())

            # get survival in control
            survival_in_control = []
            for idx, r in dft.iterrows():
                TE = r['TE']
                lowerci = r['lowerci']
                upperci = r['upperci']
                study = r['study']
                # try:
                # only those with values can be added
                try:
                    _srvc = float(r['survival in control'])
                except:
                    _srvc = None
                if pd.isna(_srvc):
                    # some thing wrong with the value
                    pass
                else:
                    survival_in_control.append(_srvc)
                # except:
                #     pass

                # convert data to PythonMeta Format
                ds.append([ TE, lowerci, upperci, study ])
            
            # update the survival_in_control for this oc
            if len(survival_in_control) > 0:
                oc_rsts[oc_name]['survival_in_control'] = sum(survival_in_control) / len(survival_in_control)
            else:
                oc_rsts[oc_name]['survival_in_control'] = 0
        

        # for each sm, get the PWMA result
        sms = oc_item['oc_measures']
        for sm in sms:
            # get the pwma result
            try:
                pma_r = None
                if sm in ['OR', 'RR', 'RD']:
                    pma_r = get_pwma_by_py(ds, datatype="CAT_RAW", 
                        sm=sm, fixed_or_random='random')
                    # pma_r = get_pwma_by_r_CAT_RAW(ds, 
                    #     sm=sm, fixed_or_random='random')
                    # validate the result, if isNaN, just set None
                    if np.isnan(pma_r['model']['sm']):
                        pma_r = None

                elif sm in ['HR']:
                    pma_r = get_pwma_by_r_CAT_PRE(ds, sm=sm)
                
            except Exception as err:
                print('* %s: [%s] measure [%s], data [%s]' % (
                    'ISSUE Data cause error'.ljust(25, ' '),
                    oc_name.rjust(35, ' '), 
                    sm,
                    ds
                ))
                pma_r = None

            # output the results
            oc_rsts[oc_name]['result'][sm] = {
                'random': pma_r
            }
        
        # add to aes list
        oc_dfts.append(dft)

    # convert all small AE dft to a big one df_aes
    df_ocs = pd.concat(oc_dfts)

    # fix data type
    df_ocs['year'] = df_ocs['year'].fillna(0)
    df_ocs['year'] = df_ocs['year'].astype('int')
    
    # build the return object
    ret = {
        'oc_list': oc_list,
        'oc_dict': oc_rsts
    }

    return ret


def calc_cie(vals):
    '''Calculate the certainty
    '''
    vs = np.array(vals)
    # remove those 0
    vs = vs[vs!=0]

    # use non-zero values
    v = sum(vs)
    l = len(vs)

    # get the result
    if v <= l:
        return 4
    if v == (l+1):
        return 3
    if v == (l+2):
        return 2
    else:
        return 1


def get_effect_val(e_txt):
    return {
        'significant benefit': 3,
        'no significant effect': 2,
        'significant harm': 1,
        'na': 0
    }.get(e_txt.strip().lower(), 0)


def _conv_nmarst_league_to_lgtable(ret_nma):
    '''Convert analyzer result to lgtable format
    '''
    lgt_cols = ret_nma['data']['league']['cols']
    tmp_lgtable_sm = {}
    for lgt_rs in ret_nma['data']['league']['tabledata']:
        lgt_r = lgt_rs['row']
        # create a new comparator row
        tmp_lgtable_sm[lgt_r] = {}

        for j, lgt_c in enumerate(lgt_cols):
            lgt_cell = {
                "sm": lgt_rs['stat'][j],
                'lw': lgt_rs['lci'][j],
                'up': lgt_rs['uci'][j]
            }
            # create a new treat col
            tmp_lgtable_sm[lgt_r][lgt_c] = lgt_cell

    return tmp_lgtable_sm


def get_pwma_data(full_fn):
    '''
    Get the PWMA data for plots
    '''
    df = pd.read_excel(full_fn)
    pwma = OrderedDict()
    for idx, row in df.iterrows():
        pwma_type = row['type']
        option_text = row['option_text']
        legend_text = row['legend_text']
        filename = row['filename']
        if pwma_type not in pwma: 
            pwma[pwma_type] = {
                '_default_option': option_text
            }
        if option_text not in pwma[pwma_type]: 
            pwma[pwma_type][option_text] = {
                'text': option_text,
                'slides': [],
                'fns': []
            }
        # add this img
        pwma[pwma_type][option_text]['fns'].append({
            'fn': filename,
            'txt': legend_text
        })
        pwma[pwma_type][option_text]['slides'].append(filename + '$' + legend_text)

    return pwma