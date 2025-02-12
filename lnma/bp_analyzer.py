import os
import json

from flask import request
from flask import flash
from flask import render_template
from flask import Blueprint
from flask import jsonify
from flask import current_app

from flask_login import login_required
from flask_login import current_user

import pandas as pd

from werkzeug.utils import secure_filename

from lnma.settings import *

from lnma import dora
from lnma import srv_analyzer
from lnma import srv_paper
from lnma.analyzer import freq_analyzer
from lnma.analyzer import bayes_analyzer
from lnma.analyzer import pwma_analyzer
from lnma.analyzer import incd_analyzer
from lnma.analyzer import subg_analyzer
from lnma import ss_state

PATH_PUBDATA = 'pubdata'

bp = Blueprint("analyzer", __name__, url_prefix="/analyzer")

@bp.route('/')
@login_required
def index():
    return render_template('analyzer/index.html')


@bp.route('/azoc')
@login_required
def azoc():
    '''
    Analyze an outcome in a project by the abbr

    According to the oc_type and the input,
    The analyzer UI would be different.

    For example, when analyzing the NMA, it should be network plot, league table.
    When analyzing the pwma - primary or sensitivity, it should be the forest.
    When analyzing the pwma - AEs, it should have more.
    When analyzing the subg, the forest is different.

    So, for different case, we will use different page to show.
    '''
    project_id = request.cookies.get('project_id')
    abbr = request.args.get('abbr')
    project = dora.get_project(project_id)

    cq_abbr = request.cookies.get('cq_abbr')
    if cq_abbr is None:
        cq_abbr = 'default'

    if abbr == '':
        # which means it's a navigation
        return render_template(
            'analyzer/azoc.html',
            cq_abbr=cq_abbr,
            project=project,
            project_json_str=json.dumps(project.as_dict())
        )
    
    # then, get the extract first
    extract = dora.get_extract_by_project_id_and_abbr(
        project_id, abbr
    )

    if extract is None:
        # what??
        pass

    return render_template(
        'analyzer/azoc.html',
        cq_abbr=cq_abbr,
        project=project,
        project_json_str=json.dumps(project.as_dict())
    )


###############################################################################
# Static file analyzers
###############################################################################

@bp.route('/nma')
@login_required
def nma():
    return render_template('analyzer/nma.html')


@bp.route('/pwma')
@login_required
def pwma():
    return render_template('analyzer/pwma.html')
    

@bp.route('/read_file', methods=['GET', 'POST'])
@login_required
def read_data_file():
    '''
    Read data from filename or a uploaded file
    '''
    global sheet_selected 

    if request.method == 'GET':
        fn = request.args.get('fn')
        path = request.args.get('path')
        fmt = fn.split('.')[-1].lower()
        if path is None:
            path = current_app.config['UPLOAD_FOLDER']
        else:
            path = './static/data/'
        full_fn = os.path.join(path, fn)

    elif request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'success': False, 'msg':'No file'})
        file_obj = request.files['file']
        if file_obj.filename == '':
            return jsonify({'success': False, 'msg':'No selected file'})
        # save the upload file
        if file_obj and allowed_file_format(file_obj.filename):
            fn = secure_filename(file_obj.filename)
            full_fn = os.path.join(current_app.config['UPLOAD_FOLDER'], fn)
            file_obj.save(full_fn)
        else:
            return jsonify({'success': False, 'msg': 'Not supported file format'})

    # read csv file
    # breakpoint()
    # if (request.__dict__['form'].get('sheet_selected')):
    #     print()
    sheet_selected = request.__dict__['form'].get('sheet_selected')
    
    ret = _read_file(full_fn)
    return jsonify(ret)


###############################################################################
# Analyzer general endpoint
###############################################################################

@bp.route('/analyze_oc', methods=['GET'])
@login_required
def analyze_oc():
    '''
    Analyze an oc 

    Args:

    project_id (or keystr)
    cq_abbr
    abbr
    '''
    project_id = request.args.get('project_id')
    keystr = request.args.get('keystr')
    cq_abbr = request.args.get('cq_abbr')
    abbr = request.args.get('abbr')

    # try to get the project first
    project = dora.get_project(project_id)

    if project is None:
        project = dora.get_project_by_keystr(keystr)

        if project is None:
            return jsonify({'success': False, 'msg': 'project not found'})
        else:
            pass
    else:
        pass

    # ok, try to get this oc
    extract = dora.get_extract_by_project_id_and_abbr(
        project.project_id,
        abbr
    )

    if extract is None:
        return jsonify({'success': False, 'msg': 'outcome not found'})

    # now let's try to analyze this oc
    # first, need to get the papers related to this oc
    papers = srv_paper.get_included_papers_by_cq(
        project.project_id, cq_abbr
    )

    # make a dictionary for lookup
    paper_dict = {}
    rs = []
    for paper in papers:
        paper_dict[paper.pid] = paper

    # now get the pwma results
    # there may be a lot of results from one outcome
    results = srv_analyzer.get_pwma(
        extract, 
        paper_dict, 
        is_skip_unselected=True
    )

    # now build the result
    ret = {
        'papers': [ p.as_quite_simple_dict() for p in papers ],
        'oc_dict': {
            abbr: {
                'extract': extract.as_very_simple_dict(),
                'results': results
            }
        }
    }

    return jsonify(ret)


@bp.route('/analyze', methods=['GET', 'POST'])
@login_required
def analyze():
    '''
    Analyze the given dataset

    Args:

    - rs: the records
    - cfg: the configs
    '''
    if request.method == 'GET':
        return 'USE POST'

    # get the input data and configs
    rs = json.loads(request.form.get('rs'))
    cfg = json.loads(request.form.get('cfg'))

    # analyze type is a code for identify which analysis
    # current we support
    # - pwma
    # - incd
    # - nma
    _analyze_type = cfg['_analyze_type']

    if _analyze_type == 'pwma':
        ret = _pwma_analyze(rs, cfg)

    elif _analyze_type == 'nma':
        ret = _nma_analyze(rs, cfg)

    elif _analyze_type == 'incd':
        ret = _incd_analyze(rs, cfg)

    else:
        ret = {

        }

    return jsonify(ret)


@bp.route('/graphdata_maker', methods=['GET', 'POST'])
@login_required
def graphdata_maker():
    if request.method == 'GET':
        return render_template('analyzer/graphdata_maker.html')
    
    # save uploaded file
    if 'file' not in request.files:
        return jsonify({'success': False, 'msg':'No file'})
    file_obj = request.files['file']
    if file_obj.filename == '':
        return jsonify({'success': False, 'msg':'No selected file'})

    if file_obj and allowed_file_format(file_obj.filename):
        fn = secure_filename(file_obj.filename)
        full_fn = os.path.join(current_app.config['UPLOAD_FOLDER'], fn)
        file_obj.save(full_fn)
    
    # prepare the msg for user
    msg = ''
    # read file
    file_data = _read_file(full_fn)

    # analyze
    prj_sname = request.form.get('prj')
    out_sname = request.form.get('out')
    msg += 'Project: %s <br>' % prj_sname
    msg += 'Tag: %s<br>' % out_sname
    
    # cfg = request.form.get('cfg')

    rs = file_data['raw']
    cfg = '{"analysis_method":"freq","input_format":"","treat":"EdoX","measure":"or","model":"fixed","better":"small"}'
    cfg = json.loads(cfg)

    # update file type
    cfg['input_format'] = file_data['coltype']
    
    msg += 'treats: ' + ','.join([ '"%s"' % t for t in file_data['treats'] ]) + '<br>'
    msg += 'cfg.analysis_method: %s <br>' % cfg['analysis_method']
    msg += 'cfg.input_format: %s <br>' % cfg['input_format']
    msg += 'cfg.measure: %s <br>' % cfg['measure']
    msg += 'cfg.model: %s <br>' % cfg['model']
    msg += 'cfg.better: %s <br>' % cfg['better']

    # save the graph data
    for treat in file_data['treats']:
        cfg['treat'] = treat
        graph_data = _nma_analyze(rs, cfg)
        output_fn = 'GRAPH-%s-%s.json' % (out_sname, treat)
        full_output_fn = os.path.join(current_app.instance_path, PATH_PUBDATA, prj_sname, output_fn)
        json.dump(graph_data, open(full_output_fn, 'w'))
        _msg = 'analyzed and saved %s.[%s] on treat [%s] to %s' % (prj_sname, out_sname, treat, output_fn)
        print('* %s' % _msg)
        msg += '%s<br>' % _msg

    ret = {
        'success': True,
        'msg': msg
    }

    return jsonify(ret)


def allowed_file_format(fn):
    return '.' in fn and \
        fn.rsplit('.', 1)[1].lower() in ['csv', 'xls', 'xlsx']


def _read_file(full_fn):
    '''
    Read data file
    '''
    fmt = full_fn.split('.')[-1].lower()
    fn = full_fn.split('/')[-1]
    sheets_name = []
    # breakpoint()
    if fmt == 'xls' or fmt == 'xlsx':
        sheets = pd.ExcelFile(full_fn)
        for sheet in sheets.sheet_names:
           sheets_name.append(sheet)

        if len(sheets_name) > 1:
            if (sheet_selected):
                df = pd.read_excel(full_fn, sheet_name=None)
                # breakpoint()
                df = df.get(sheet_selected)
            else:
                return {'sheets_name': sheets_name}
        else:
            df = pd.read_excel(full_fn)
    else:
        df = pd.read_csv(full_fn)

    # detect the format
    # df_columns = [ (c.lower()).strip() for c in df.columns.tolist() ]
    # 6/22/2020: column names need to be 100% match case sensitive
    df_columns = [ c.strip() for c in df.columns.tolist() ]
    df_coltype = None
    mapped_cols = []
    for sd_cols in STANDARD_DATA_COLS:
        coltype = sd_cols[0]
        st_cols = sd_cols[1]

        is_this_coltype = True
        for col in st_cols:
            if col in df_columns:
                # ok, found one column
                pass
            else:
                # nope, this doesn't match!
                is_this_coltype = False

        if is_this_coltype:
            df_coltype = coltype
            mapped_cols = st_cols
            break
    
    # get all treat for nma

    if 'treat' in df_columns:
        treats = list(df['treat'].unique())
    elif 't1' in df_columns:
        treats = list(set(df['t1'].unique().tolist() + df['t2'].unique().tolist()))
    else:
        treats = []

    # get treatment and control for pwma
    if 'treatment' in df_columns:
        treatment = df['treatment'].unique().tolist()[0]
    else:
        treatment = ''
    if 'control' in df_columns:
        control = df['control'].unique().tolist()[0]
    else:
        control = ''

    # get the number of studies
    n_studies = int(df['study'].nunique())

    # return
    ret = {
        'raw': json.loads(df.to_json(orient='records')),
        'filename': fn,
        'coltype': df_coltype,
        'cols': ', '.join(mapped_cols),
        'treats': treats,
        'treatment': treatment,
        'control': control,
        'n_studies': n_studies
    }

    return ret


def _nma_analyze(rs, cfg):
    '''
    Run the network meta-analyze the rs with cfg
    '''
    # get the analysis type for make static json
    input_format = cfg['input_format']
    analysis_method = cfg['analysis_method']

    # get all treats
    all_treats = set([])
    for r in rs:
        if 'treat' in r:
            all_treats.add(r['treat'])
        if 't1' in r:
            all_treats.add(r['t1'])
    all_treats = list(all_treats)
    all_treats.sort()

    # analyze!
    if analysis_method == 'freq':
        ret = freq_analyzer.analyze(rs, cfg)
    elif analysis_method == 'bayes':
        ret = bayes_analyzer.analyze(rs, cfg)
    else:
        ret = bayes_analyzer.analyze(rs, cfg)

    return ret


def _pwma_analyze(rs, cfg):
    '''zz
    Run the pairwise meta-analyze the rs with cfg
    '''
    ret = pwma_analyzer.analyze(rs, cfg)

    return ret


def _incd_analyze(rs, cfg):
    '''
    Run the incidence analysis on the rs with cfg
    '''
    ret = incd_analyzer.analyze(rs, cfg)

    return ret


def _subg_analyze(rs, cfg):
    '''
    Run the subgroup analysis on the rs with cfg
    '''
    ret = subg_analyzer.analyze(rs, cfg)

    return ret