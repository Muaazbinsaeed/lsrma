import os
import json
from functools import wraps

from flask import request
from flask import flash
from flask import render_template
from flask import Blueprint
from flask import jsonify
from flask import url_for
from flask import current_app

from werkzeug.utils import secure_filename

from lnma.settings import *

from lnma import settings
from lnma import dora
# from lnma.analyzer import rplt_analyzer
from lnma.analyzer import rpy2_pwma_analyzer as rplt_analyzer
from lnma.analyzer import bayes_analyzer

from lnma import srv_analyzer

PATH_PUBDATA = 'pubdata'

bp = Blueprint("rplt", __name__, url_prefix="/rplt")


def apikey_required(f):
    '''
    Check the APIKEY 
    '''
    @wraps(f)
    def wrap(*args, **kwargs):
        if request.method=='GET':
            return f(*args, **kwargs)

        # check the API Keys here
        # apikey_set = set([
        #     '7323590e-577b-4f46-b19f-3ec401829bd6',
        #     '9bebaa87-983d-42e4-ad70-4430c99aa886',
        #     'a8c0c749-7263-4072-a313-99ccc76569d3'
        # ])
        apikey = request.form.get('apikey', '').strip()
        if apikey not in settings.API_SYSTEM_APIKEYS:
            ret = {
                'success': False,
                'msg': 'Unauthorized request'
            }
            return jsonify(ret)

        return f(*args, **kwargs)

    return wrap



def apikey_required_as_header(f):
    '''
    Check the APIKEY 
    '''
    @wraps(f)
    def wrap(*args, **kwargs):

        if request.method=='GET':
            return f(*args, **kwargs)

        # check the API Keys here
        # apikey_set = set([
        #     '7323590e-577b-4f46-b19f-3ec401829bd6',
        #     '9bebaa87-983d-42e4-ad70-4430c99aa886',
        #     'a8c0c749-7263-4072-a313-99ccc76569d3'
        # ])
        
        if 'x-token' in request.headers:
            apikey = request.headers['x-token']
            if apikey in settings.API_SYSTEM_APIKEYS:
                return f(*args, **kwargs)

        ret = {
            'success': False,
            'msg': 'Unauthorized request'
        }
        return jsonify(ret)

    return wrap



@bp.route('/')
def index():
    return 'RPLT Service'


@bp.route('/NMA_BAYES', methods=['GET', 'POST'])
@apikey_required
def nma_bayes():
    '''
    NMA Bayesian Analyzer
    '''
    if request.method=='GET':
        return render_template('rplt/NMA_BAYES.html')
    
    # prepare the return object
    ret = {
        'success': False,
        'msg': '',
        'analysis_method': 'nma_bayes'
    }

    # measure_of_effect
    sm = request.form.get('sm', '').strip()
    # reference_treatment
    rt = request.form.get('rt', '').strip()

    input_format = request.form.get('input_format', '').strip()
    
    # check rs
    if sm not in set(['HR', 'RR', 'OR']):
        ret['msg'] = 'Unsupported measure of effect'
        return jsonify(ret)
    
    # check hk
    if input_format not in set(['HRLU']):
        ret['msg'] = 'Unsupported value for input format'
        return jsonify(ret)

    # extract data
    try:
        rs = request.form.get('rs')
        rs = json.loads(rs)
    except Exception as err:
        print('wrong rs:', err)
        ret['msg'] = 'Input data is missing or not valid JSON format.'
        return jsonify(ret) 

    # get all treats
    trts = []
    for r in rs:
        if r['t1'] not in trts: trts.append(r['t1'])
        if r['t2'] not in trts: trts.append(r['t2'])
    if rt not in trts:
        rt = trts[0]
    
    cfg = {
        'analysis_method': 'bayes',
        'measure_of_effect': sm,
        'fixed_or_random': 'random',
        'which_is_better': 'small',
        'input_format': input_format,
        'reference_treatment': rt
    }

    _ret = bayes_analyzer.analyze(rs, cfg)
    # change the result name
    _ret['rsts'] = _ret['data']
    del _ret['data']

    ret['data'] = _ret

    return ret


@bp.route('/PWMA_INCD', methods=['GET', 'POST'])
@apikey_required
def pwma_incd():
    if request.method=='GET':
        return render_template('rplt/PWMA_INCD.html')

    # prepare the return object
    ret = {
        'success': False,
        'msg': '',
        'analysis_method': 'pwma_incd',
        'img': {
            'outplt1': { 'url': '' },
            'cumuplt': { 'url': '' }
        }
    }

    # measure_of_effect
    sm = request.form.get('sm', '').strip()
    # is_hakn
    hk = request.form.get('hk', '').strip()
    # is_create_figure
    cf = request.form.get('cf', '').strip()

    # check rs
    if sm not in set(['PLOGIT', 'PAS', "PFT", "PLN", "PRAW", "IR"]):
        ret['msg'] = 'Unsupported measure of effect'
        return jsonify(ret)
    
    # check hk
    if hk not in set(['TRUE', 'FALSE']):
        ret['msg'] = 'Unsupported value for Hartung-Knapp adjustment'
        return jsonify(ret)
    
    # check cf
    if cf not in set(['YES', 'NO']):
        ret['msg'] = 'Unsupported value for figure creation'
        return jsonify(ret)

    # extract data
    try:
        rs = request.form.get('rs')
        rs = json.loads(rs)
    except Exception as err:
        print('wrong rs:', err)
        ret['msg'] = 'Input data is missing or not valid JSON format.'
        return jsonify(ret) 

    # create a config
    cfg = {
        'analyzer_model': 'PWMA_INCD',
        'measure_of_effect': sm,
        'input_format': 'CAT_RAW',
        'fixed_or_random': 'random',
        'is_fixed': 'FALSE',
        'is_random': 'TRUE',
        'pooling_method': 'Inverse',
        'tau_estimation_method': 'DL',
        'is_hakn': hk,
        'hakn_adjustment': hk,
        'adhoc_hakn': '' if hk == 'FALSE' else 'se',
        'is_create_figure': cf,
        'sort_by': 'year',
        'assumed_baseline': 100
    }
    print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
    print("I am being called !!!!!!!!!!!!!!!!!1")
    # set the params for callback usage
    ret['params'] = {
        'sm': sm,
        'hk': hk
    }
    ret['params'].update(cfg)
    non_io = request.form.get('non_io', '').strip()
    analysis_type =request.form.get('analysis_type', '').strip() 
    person_time =request.form.get('person_time', '').strip() 
    ir_scale = request.form.get('ir_scale', 10)
    p_scale = request.form.get('p_scale', 10)
    try:

        print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print(analysis_type)
        print(ir_scale)

        if analysis_type and analysis_type == 'meta_rate':
            result=rplt_analyzer.analyze_pwma_incd_metarate(rs, cfg, person_time, int(ir_scale))
        elif non_io and  analysis_type =="meta_prop":
            result = rplt_analyzer.analyze_pwma_incd_pft(rs,int(p_scale), cfg)
        
        else:
            result = rplt_analyzer.analyze_pwma_incd(rs, cfg)
        # TODO the return should be checked here
        # but most of time, the figure will be generated.
        if result['success']:
            ret['success'] = True
            if cf == 'YES':
                ret['img']['outplt1']['url'] = url_for('index.f', fn=result['params']['fn_outplt1'])
                ret['img']['cumuplt']['url'] = url_for('index.f', fn=result['params']['fn_cumuplt'])
                ret['data'] = result['data']
            else:
                ret['data'] = result['data']

            # merge the rs value
            for i, r in enumerate(rs):
                for k in r:
                    ret['data']['incdma']['stus'][i][k] = r[k]
                
            # the cumulative may NOT be in the results if there is only one record
            if 'cumuma' in ret['data'] and ret['data']['cumuma'] is not None:
                for i, r in enumerate(rs):
                    for k in r:
                        ret['data']['cumuma']['stus'][i][k] = r[k]
        else:
            ret['msg'] = result['msg']

    except Exception as err:
        print('Handling run-time error:', err)

        if current_app.config['DEBUG']:
            raise err

        ret['msg'] = 'System error, please check input data.'

    # print(ret)

    return jsonify(ret)


@bp.route('/PWMA_PRCM', methods=['GET', 'POST'])
@apikey_required
def pwma_prcm():
    '''
    Pairwise Meta-Analysis for primary and cumulative
    '''
    if request.method=='GET':
        return render_template('rplt/PWMA_PRCM.html')

    # prepare the return object
    ret = {
        'success': False,
        'msg': '',
        'analysis_method': 'pwma_prcm',
        'img': {
            'outplt1': { 'url': '' },
            'cumuplt': { 'url': '' }
        }
    }

    # analyzer model
    am = request.form.get('am', '').strip()
    # measure_of_effect
    sm = request.form.get('sm', '').strip()
    # is_hakn
    hk = request.form.get('hk', '').strip()

    # non IO baaed project 

    non_io = request.form.get('non_io', '').strip()


    # check am
    if am not in set(['FOREST', 'FORESTDATA']):
        ret['msg'] = 'Unsupported analyzer'
        return jsonify(ret)
    
    # check rs
    if sm not in set(['OR', 'RR', 'RD']):
        ret['msg'] = 'Unsupported measure of effect'
        return jsonify(ret)
    
    # check hk
    if hk not in set(['TRUE', 'FALSE']):
        ret['msg'] = 'Unsupported value for Hartung-Knapp adjustment'
        return jsonify(ret)

    # extract data
    try:
        rs = request.form.get('rs')
        rs = json.loads(rs)
    except Exception as err:
        print('wrong rs:', err)
        ret['msg'] = 'Input data is missing or not valid JSON format.'
        return jsonify(ret) 

    # create a config
    cfg = {
        'analyzer_model': 'PWMA_PRCM',
        'measure_of_effect': sm,
        'is_hakn': hk,
        'fixed_or_random': 'random',
        'input_format': 'CAT_RAW',
        'sort_by': 'year',
        'pooling_method': 'MH',
        'tau_estimation_method': 'DL',
        'assumed_baseline': 100
    }

    # set the params for callback usage
    ret['params'] = {
        'am': am,
        'sm': sm,
        'hk': hk
    }
    ret['params'].update(cfg)

    try:
       
        result = rplt_analyzer.analyze_pwma_prcm(rs, cfg, has_cumu=True)
        # TODO the return should be checked here
        # but most of time, the figure will be generated.
        if result['success']:
            ret['success'] = True
            if am == 'FOREST':
                ret['img']['outplt1']['url'] = url_for('index.f', fn=result['params']['fn_outplt1'])
                ret['img']['cumuplt']['url'] = url_for('index.f', fn=result['params']['fn_cumuplt'])
            elif am == 'FORESTDATA': 
                ret['data'] = result['data']

            # merge the rs value
            # in this proecess, add the pid and other information to results
            for i, r in enumerate(rs):
                for k in r:
                    ret['data']['primma']['stus'][i][k] = r[k]

            # the cumulative may NOT be in the results if there is only one record
            if 'cumuma' in ret['data'] and ret['data']['cumuma'] is not None:
                for i, r in enumerate(rs):
                    for k in r:
                        ret['data']['cumuma']['stus'][i][k] = r[k]
                        
        else:
            ret['msg'] = result['msg']

    except Exception as err:
        print('Handling run-time error:', err)

        if current_app.config['DEBUG']:
            raise err

        ret['msg'] = 'System error, please check input data.'

    # print(ret)

    return jsonify(ret)


@bp.route('/PWMA_PRCM_COE', methods=['GET', 'POST'])
@apikey_required
def pwma_prcm_coe():
    '''
    Pairwise Meta-Analysis for primary and cumulative with CoE
    '''
    if request.method=='GET':
        return render_template('rplt/PWMA_PRCM_COE.html')

    # prepare the return object
    ret = {
        'success': False,
        'msg': '',
        'analysis_method': 'pwma_prcm',
        'img': {
            'outplt1': { 'url': '' },
            'cumuplt': { 'url': '' }
        }
    }

    # analyzer model
    am = request.form.get('am', '').strip()
    # measure_of_effect
    sm = request.form.get('sm', '').strip()
    # is_hakn
    hk = request.form.get('hk', '').strip()
    # indirectness threshold
    imp_t = request.form.get('imp_t', '').strip()

    # check am
    if am not in set(['FOREST', 'FORESTDATA']):
        ret['msg'] = 'Unsupported analyzer'
        return jsonify(ret)
    
    # check rs
    if sm not in set(['OR', 'RR', 'RD']):
        ret['msg'] = 'Unsupported measure of effect'
        return jsonify(ret)
    
    # check hk
    if hk not in set(['TRUE', 'FALSE']):
        ret['msg'] = 'Unsupported value for Hartung-Knapp adjustment'
        return jsonify(ret)

    # check imp_t
    if imp_t == '':
        imp_t = 0
        is_t_user_provided = False

    else:
        try:
            imp_t = float(imp_t)
            is_t_user_provided = True
        except:
            ret['msg'] = 'Unsupported value for indirectness threshold T'
            return jsonify(ret)


    # extract data
    try:
        rs = request.form.get('rs')
        rs = json.loads(rs)
    except Exception as err:
        print('wrong rs:', err)
        ret['msg'] = 'Input data is missing or not valid JSON format.'
        return jsonify(ret) 

    # create a config
    cfg = {
        'analyzer_model': 'PWMA_PRCM',
        'measure_of_effect': sm,
        'is_hakn': hk,
        'fixed_or_random': 'random',
        'input_format': 'CAT_RAW',
        'sort_by': 'year',
        'pooling_method': 'MH',
        'tau_estimation_method': 'DL',
        'assumed_baseline': 100,

        # for CoE
        'imp_t': imp_t,
        'is_t_user_provided': is_t_user_provided
    }

    # set the params for callback usage
    ret['params'] = {
        'am': am,
        'sm': sm,
        'hk': hk
    }
    ret['params'].update(cfg)

    try:
        result = rplt_analyzer.analyze_pwma_raw_coe(rs, cfg, has_cumu=True)
        # TODO the return should be checked here
        # but most of time, the figure will be generated.
        if result['success']:
            ret['success'] = True
            if am == 'FOREST':
                ret['img']['outplt1']['url'] = url_for('index.f', fn=result['params']['fn_outplt1'])
                ret['img']['cumuplt']['url'] = url_for('index.f', fn=result['params']['fn_cumuplt'])
            elif am == 'FORESTDATA': 
                ret['data'] = result['data']

            # merge the rs value
            # in this proecess, add the pid and other information to results
            for i, r in enumerate(rs):
                for k in r:
                    ret['data']['primma']['stus'][i][k] = r[k]

            # the cumulative may NOT be in the results if there is only one record
            if 'cumuma' in ret['data'] and ret['data']['cumuma'] is not None:
                for i, r in enumerate(rs):
                    for k in r:
                        ret['data']['cumuma']['stus'][i][k] = r[k]
                        
        else:
            ret['msg'] = result['msg']

    except Exception as err:
        print('Handling run-time error:', err)

        if current_app.config['DEBUG']:
            raise err

        ret['msg'] = 'System error, please check input data.'

    # print(ret)

    return jsonify(ret)
    

@bp.route('/PWMA', methods=['GET', 'POST'])
@apikey_required_as_header
def srv_pwma():
    '''
    General PWMA
    '''
    if request.method=='GET':
        return render_template('rplt/PWMA.html')
    
    data = request.get_json()
    print('* got /PWMA request data:', data)
    # print('* got /PWMA request rs:', rs)
    # print('* got /PWMA request cfg:', cfg)

    results = srv_analyzer.pwma(
        data,
        data['is_subg_analysis']
    )

    ret = {
        "results": results
    }

    return jsonify(ret)


@bp.route('/PWMA_COE', methods=['GET', 'POST'])
@apikey_required_as_header
def srv_pwma_coe():
    '''
    General PWMA with CoE
    '''
    if request.method=='GET':
        return render_template('rplt/PWMA_COE.html')
    
    data = request.get_json()
    print('* got /PWMA request data:', data)

    if data['cfg']['input_format'] == "PRIM_CAT_RAW":
        # binary outcome
        result = rplt_analyzer.analyze_pwma_raw_coe(
            data['rs'],
            data['cfg'],
        )
    else:
        # survival outcome
        result = rplt_analyzer.analyze_pwma_pre_coe(
            data['rs'],
            data['cfg'],
        )

    ret = result

    return jsonify(ret)


