import os
import time
import json
from datetime import datetime

from flask import request
from flask import flash
from flask import render_template
from flask import Blueprint
from flask import current_app
from flask import jsonify
from flask import redirect
from flask import url_for

from flask_login import login_required
from flask_login import current_user

from lnma import dora
from lnma import srv_paper
from lnma import srv_pub_prisma
from lnma import srv_project
from lnma import srv_deduplicate
from lnma.models import *
from lnma import ss_state
from lnma import util
from lnma import settings

bp = Blueprint("screener", __name__, url_prefix="/screener")

@bp.context_processor
def inject_enumerate():
    return dict(enumerate=enumerate)


@bp.route('/')
@login_required
def index():
    return render_template('screener.index_v3.html')


@bp.route('/deduplicate')
@login_required
def deduplicate():
    '''
    De-duplicate records
    '''
    project_id = request.cookies.get('project_id')

    if project_id is None:
        return redirect(url_for('project.mylist'))
    project = dora.get_project(project_id)

    # get the job and result file names
    # full_fn_job = os.path.join(
    #     current_app.instance_path, 
    #     settings.PATH_DEDUPLICATE, 
    #     project.keystr,
    #     'job.json'
    # )

    # # get the job
    # dd_job = None

    # if os.path.exists(full_fn_job):
    #     dd_job = json.load(open(full_fn_job))

    return render_template(
        'screener/deduplicate.html',
        project=project,
        project_json_str=json.dumps(project.as_dict()),
    )


@bp.route('/overview')
@login_required
def overview():
    '''
    The overview of the
    '''
    project_id = request.cookies.get('project_id')

    if project_id is None:
        return redirect(url_for('project.mylist'))

    project = dora.get_project(project_id)

    return render_template(
        'screener/overview.html',
        project=project,
        project_json_str=json.dumps(project.as_dict())
    )


@bp.route('/pcq_selector')
@login_required
def pcq_selector():
    '''
    Show project cq - selection match
    '''
    project_id = request.cookies.get('project_id')

    if project_id is None:
        return redirect(url_for('project.mylist'))

    project = dora.get_project(project_id)

    return render_template(
        'screener/pcq_selector.html',
        project=project,
        project_json_str=json.dumps(project.as_dict())
    )


@bp.route('/timeline')
@login_required
def timeline():
    '''
    Show the timeline
    '''
    project_id = request.cookies.get('project_id')

    if project_id is None:
        return redirect(url_for('project.mylist'))

    project = dora.get_project(project_id)

    # timeline = srv_project.get_project_timeline_by_keystr(project.keystr)

    return render_template(
        'screener/timeline.html',
        # timeline=timeline,
        project=project,
        project_json_str=json.dumps(project.as_dict())
    )


###############################################################################
# AJAX API functions for screener
###############################################################################

# @bp.route('/delete_paper_from_project')
# @login_required
# def delete_paper_from_project():
#     '''
#     Delete a paper from a project
#     '''
#     project_id = request.cookies.get('project_id')
#     paper_id = request.args.get('paper_id')

#     if project_id is None:
#         return redirect(url_for('project.mylist'))

#     paper = dora.get_paper_by_id(paper_id)

#     # now need to check if this paper is really deletable

@bp.route('/keep_and_exclude', methods=['POST'])
@login_required
def keep_and_exclude():
    '''
    Keep paper and exclude others and merge!
    '''
    project_id = request.form.get('project_id')
    pid_to_keep = request.form.get('pid_to_keep')
    dup_pids = request.form.get('dup_pids').split(',')

    project = dora.get_project(project_id)

    print('* project %s' % (project.keystr))
    print('* pid_to_keep = %s' % (pid_to_keep))
    print("* dup_pids = %s" % (dup_pids))

    _, excluded_papers = srv_deduplicate.merge_and_exclude_dups(
        project,
        pid_to_keep,
        dup_pids
    )

    ret = {
        'success': True,
        'excluded_papers': [ _.as_very_simple_dict() for _ in excluded_papers ]
    }

    return jsonify(ret)


@bp.route('/find_duplicates')
@login_required
def find_duplicates():
    '''
    Find duplicates
    '''
    project_id = request.args.get('project_id')
    src = request.args.get('src')

    project = dora.get_project(project_id)

    if src != 'db':
        src = 'cache'

    # find
    if src == 'db':
        rst = srv_deduplicate.find_duplicates(
            project.keystr
        )
    else:
        full_fn_json = srv_deduplicate.get_fn_rst(project.keystr)
        try:
            rst = json.load(open(full_fn_json))
        except Exception as err:
            rst = {}

    return jsonify(rst)



@bp.route('/start_deduplicate_search')
@login_required
def start_deduplicate_search():
    '''
    Start a deduplicate search
    '''
    project_id = request.cookies.get('project_id')
    project = dora.get_project(project_id)

    # set up this task
    n_papers = dora.get_n_papers_by_project_id(project.project_id)

    # define a job
    job = srv_deduplicate.make_job(
        project.keystr, 
        n_papers
    )

    # start!
    # all_dups = srv_paper.get_duplicated_papers('IO')

    return jsonify(job)


@bp.route('/get_deduplicate_search_result')
@login_required
def get_deduplicate_search_result():
    '''
    Get the deduplicate search result
    '''
    project_id = request.cookies.get('project_id')
    project = dora.get_project(project_id)
    full_fn_rst = os.path.join(
        current_app.instance_path, 
        settings.PATH_DEDUPLICATE, 
        project.keystr,
        'DUPLICATES.json'
    )

    dd_rst = None
    if not os.path.exists(full_fn_rst):
        return jsonify({
            'success': False,
            'msg': 'Result not found'
        })
    
    try:
        # get basic results
        dd_rst = json.load(open(full_fn_rst))

        # then update other information for user
        # 1. get all pids
        all_pids = []
        for title in dd_rst['dup_dict']:
            all_pids += dd_rst['dup_dict'][title]
        
        papers = dora.get_papers_by_pids(project_id, all_pids)
        paper_dict = dict([ (p.pid, p.as_simple_dict()) for p in papers ])
        print('* got %s papers in project [%s]' % (
            len(papers),
            project.keystr
        ))

        # 2. get the selections
        extracts = dora.get_extracts_by_project_id(project_id)
        extract_dict = dict([ (_.extract_id, _.as_very_simple_dict()) for _ in extracts ])
        print('* got %s extracts in project [%s]' % (
            len(extracts),
            project.keystr
        ))

        # 3. get all pieces (after using piece, the logic is different now)
        pieces = dora.get_pieces_by_extracts_and_papers(extracts, papers)
        print('* got %s pieces in project [%s]' % (
            len(pieces),
            project.keystr
        ))

        for pid in paper_dict:
            ext_abbrs = dora.get_paper_selections_in_extracts_by_pieces(
                pid, 
                pieces,
                extract_dict
            )
            paper_dict[pid]['ext_abbrs'] = ext_abbrs

        print('* matched all relations between papers and extracts by pieces')
        
        # ok, add this paper_dict to dd_rst
        dd_rst['paper_dict'] = paper_dict

        return jsonify({
            'success': True,
            'msg': 'OK',
            'rst': dd_rst
        })

    except Exception as err:
        logging.error("* loading deduplicate result %s error" % full_fn_rst)
        logging.error(err)

        return jsonify({
            'success': False,
            'msg': 'Parsing error %s' % err
        })


@bp.route('/get_timeline')
@login_required
def get_timeline():
    '''
    Get the timeline JSON
    '''
    project_id = request.cookies.get('project_id')
    project = dora.get_project(project_id)
    timeline = srv_project.get_project_timeline_by_keystr(project.keystr)

    return jsonify(timeline)


@bp.route('/get_paper_by_id')
@login_required
def get_paper_by_id():
    paper_id = request.args.get('paper_id')
    project_id = request.cookies.get('project_id')

    if project_id is None:
        return redirect(url_for('project.mylist'))

    # time.sleep(1)

    paper = dora.get_paper_by_id(paper_id)
    project = dora.get_project(project_id)

    # check this paper
    if paper is None:
        json_paper = None
    else:
        if paper.is_ss_included_in_project():
            paper.update_ss_cq_ds(
                project.settings['clinical_questions']
            )
        json_paper = paper.as_dict()

    ret = {
        'success': True,
        'paper': json_paper
    }
    return jsonify(ret)


@bp.route('/get_papers')
@login_required
def get_papers():
    project_id = request.args.get('project_id')
    papers = dora.get_papers(project_id)

    json_papers = [ p.as_very_simple_dict() for p in papers ]

    ret = {
        'success': True,
        'papers': json_papers
    }
    return jsonify(ret)


@bp.route('/get_papers_by_stage')
@login_required
def get_papers_by_stage():
    project_id = request.args.get('project_id')
    stage = request.args.get('stage')
    cq_abbr = request.args.get('cq_abbr')
    cq_dval = request.args.get('cq_dval') # for yes / no
    print('* stage:%s, cq_abbr:%s, cq_dval:%s' % (
        stage, cq_abbr, cq_dval
    ))

    papers = dora.get_papers_by_stage(project_id, stage)
    json_papers = [  ]
    for p in papers:

        if stage == ss_state.SS_STAGE_INCLUDED_SR and cq_abbr!='':
            if cq_abbr not in p.ss_ex['ss_cq']:
                continue
                
            if p.ss_ex['ss_cq'][cq_abbr]['d'] != cq_dval:
                continue

        d = p.as_very_simple_dict()
        # remove some unused information in first look
        del d['date_updated']
        del d['year']
        if 'pred_dict' in d['meta']: del d['meta']['pred_dict']
        if 'all_rct_ids' in d['meta']: del d['meta']['all_rct_ids']

        json_papers.append(d)

    ret = {
        'success': True,
        'papers': json_papers
    }
    return jsonify(ret)


@bp.route('/get_stat')
@login_required
def get_stat():
    project_id = request.args.get('project_id')
    rst = dora.get_screener_stat_by_project_id(project_id)

    # 2021-08-17: extend the rst with cq-level result
    project = dora.get_project(project_id)
    cq_rst = dora.get_screener_cq_stat_by_project(project)

    rst['cq'] = cq_rst

    ret = {
        'success': True,
        'stat': rst
    }
    return jsonify(ret)


@bp.route('/get_prisma')
@login_required
def get_prisma():
    project_id = request.args.get('project_id')
    prisma = dora.get_prisma(project_id)
    ret = {
        'success': True,
        'prisma': prisma
    }
    return jsonify(ret)


@bp.route('/get_prisma_by_cq_abbr')
@login_required
def get_prisma_by_cq_abbr():
    project_id = request.args.get('project_id')
    cq_abbr = request.args.get('cq_abbr')
    prisma = srv_pub_prisma.get_prisma_by_cq(project_id, cq_abbr)
    ret = {
        'success': True,
        'project_id': project_id,
        'cq_abbr': cq_abbr,
        'prisma': prisma
    }
    return jsonify(ret)


@bp.route('/set_rct_id', methods=['GET', 'POST'])
@login_required
def set_rct_id():
    paper_id = request.form.get('paper_id')
    rct_id = request.form.get('rct_id')
    is_success, paper = dora.set_paper_rct_id(paper_id, rct_id)

    ret = {
        'success': True,
        'paper': paper.as_very_simple_dict()
    }
    return jsonify(ret)


@bp.route('/set_pmid', methods=['GET', 'POST'])
@login_required
def set_pmid():
    paper_id = request.form.get('paper_id')
    pmid = request.form.get('pmid')

    if util.is_valid_pmid(pmid):
        is_success, paper = dora.set_paper_pmid(paper_id, pmid)
        ret = {
            'success': is_success,
            'msg': 'updated',
            'paper': paper.as_very_simple_dict()
        }
    else:
        paper = dora.get_paper_by_id(paper_id)
        ret = {
            'success': False,
            'msg': 'PMID [%s] is invalid',
            'paper': paper.as_very_simple_dict()
        } 

    return jsonify(ret)


@bp.route('/set_pid', methods=['GET', 'POST'])
@login_required
def set_pid():
    paper_id = request.form.get('paper_id')
    new_pid = request.form.get('pid')

    # 2023-06-13: lowercase pid is needed
    new_pid = new_pid.strip().lower()

    # get this paper
    paper = dora.get_paper_by_id(paper_id)

    # TODO ensure paper exists

    # first, check if there is duplicate?
    paper = dora.get_paper_by_project_id_and_pid(
        paper.project_id,
        new_pid
    )

    if paper is None:
        # great! just set it!
        is_success, paper = dora.set_paper_pid(
            paper_id,
            new_pid
        )
        ret = {
            'success': True,
            'msg': 'Given PID [%s] is updated to paper#%s' % (
                new_pid,
                paper.seq_num
            ),
            'paper': paper.as_very_simple_dict()
        } 
    else:
        # oh ... this means it's duplicate!
        # what to do?
        ret = {
            'success': False,
            'msg': 'Given PID [%s] is already used by another paper#%s' % (
                new_pid,
                paper.seq_num
            ),
            'paper': paper.as_very_simple_dict()
        } 

    return jsonify(ret)


@bp.route('/set_meta_ds_id', methods=['GET', 'POST'])
@login_required
def set_meta_ds_id():
    paper_id = request.form.get('paper_id')
    ds_name = request.form.get('ds_name')
    ds_id = request.form.get('ds_id')

    is_success, paper = dora.set_paper_meta_ds_id(
        paper_id, 
        ds_name,
        ds_id
    )
    ret = {
        'success': is_success,
        'msg': 'updated',
        'paper': paper.as_very_simple_dict()
    }

    return jsonify(ret)


@bp.route('/set_pub_date', methods=['GET', 'POST'])
@login_required
def set_pub_date():
    paper_id = request.form.get('paper_id')
    pub_date = request.form.get('pub_date')
    # TODO check the pub_date

    is_success, paper = dora.set_paper_pub_date(paper_id, pub_date)

    ret = {
        'success': is_success,
        'paper': paper.as_very_simple_dict()
    }
    
    return jsonify(ret)

    

@bp.route('/set_ss_cq', methods=['GET', 'POST'])
@login_required
def set_ss_cq():
    paper_id = request.form.get('paper_id')
    cq_abbr = request.form.get('cq_abbr')
    ss_cq = request.form.get('ss_cq')

    is_success, paper = srv_paper.set_paper_ss_cq(paper_id, cq_abbr, ss_cq)

    ret = {
        'success': is_success,
        'paper': paper.as_very_simple_dict() if is_success else None
    }
    return jsonify(ret)


@bp.route('/set_ss_cq_exclude_reason', methods=['GET', 'POST'])
@login_required
def set_ss_cq_exclude_reason():
    paper_id = request.form.get('paper_id')
    cq_abbr = request.form.get('cq_abbr')
    ss_cq = request.form.get('ss_cq')
    exclude_reason = request.form.get('reason')

    is_success, paper = srv_paper.set_paper_ss_cq(
        paper_id, cq_abbr, settings.PAPER_SS_EX_SS_CQ_DECISION_NO,
        exclude_reason
    )

    ret = {
        'success': is_success,
        'paper': paper.as_very_simple_dict() if is_success else None
    }
    return jsonify(ret)


@bp.route('/add_tag', methods=['GET', 'POST'])
@login_required
def add_tag():
    paper_id = request.form.get('paper_id')
    tag = request.form.get('tag')
    is_success, paper = dora.add_paper_tag(paper_id, tag)

    ret = {
        'success': True,
        'paper': paper.as_very_simple_dict()
    }
    return jsonify(ret)


@bp.route('/toggle_tag', methods=['GET', 'POST'])
@login_required
def toggle_tag():
    paper_id = request.form.get('paper_id')
    tag = request.form.get('tag')
    is_success, paper = dora.toggle_paper_tag(paper_id, tag)

    ret = {
        'success': True,
        'paper': paper.as_very_simple_dict()
    }
    return jsonify(ret)


@bp.route('/sspr/exclude_all', methods=['GET', 'POST'])
@login_required
def sspr_exclude_all():
    project_id = request.form.get('project_id')

    return ''


@bp.route('/sspr/set_papers_unscreened', methods=['GET', 'POST'])
@login_required
def sspr_set_papers_unscreened():
    project_id = request.form.get('project_id')
    paper_ids = request.form.get('paper_ids')
    paper_ids = paper_ids.split(',')

    papers = []
    
    # create a dict for the details
    # this stage is not a decision stage
    detail_dict = {
        'date_decided': None,
        'reason': None,
        'decision': None
    }
    for paper_id in paper_ids:
        p = dora.set_paper_pr_rs_with_details(
            paper_id,
            pr=ss_state.SS_PR_NA, 
            rs=ss_state.SS_RS_NA,
            detail_dict=detail_dict)
        papers.append(p.as_simple_dict())

    ret = {
        'success': True,
        'papers': papers
    }
    return jsonify(ret)


@bp.route('/sspr/set_papers_needchkft', methods=['GET', 'POST'])
@login_required
def sspr_set_papers_needchkft():
    project_id = request.form.get('project_id')
    paper_ids = request.form.get('paper_ids')
    paper_ids = paper_ids.split(',')

    papers = []
    
    # create a dict for the details
    # this stage is not a decision stage
    detail_dict = {
        'date_decided': None,
        'reason': None,
        'decision': None
    }
    for paper_id in paper_ids:
        p = dora.set_paper_pr_rs_with_details(
            paper_id,
            pr=ss_state.SS_PR_PASSED_TITLE, 
            rs=ss_state.SS_RS_NA,
            detail_dict=detail_dict)
        papers.append(p.as_simple_dict())

    ret = {
        'success': True,
        'papers': papers
    }
    return jsonify(ret)


@bp.route('/sspr/exclude_papers_ta', methods=['GET', 'POST'])
@login_required
def sspr_exclude_papers_ta():
    '''Deprecated. Use specified reason instead.
    '''
    project_id = request.form.get('project_id')
    paper_ids = request.form.get('paper_ids')
    paper_ids = paper_ids.split(',')

    papers = []
    for paper_id in paper_ids:
        p = dora.set_paper_pr_rs(paper_id, 
            pr=ss_state.SS_PR_PASSED_TITLE, 
            rs=ss_state.SS_RS_EXCLUDED_TITLE)
        papers.append(p.as_simple_dict())

    ret = {
        'success': True,
        'papers': papers
    }
    return jsonify(ret)


@bp.route('/sspr/exclude_papers_tt', methods=['GET', 'POST'])
@login_required
def sspr_exclude_papers_tt():
    project_id = request.form.get('project_id')
    paper_ids = request.form.get('paper_ids')
    reason = request.form.get('reason')
    paper_ids = paper_ids.split(',')

    # just remove the None
    if reason is None: reason = ''

    papers = []

    # create a dict for the details
    detail_dict = {
        'date_decided': util.get_today_date_str(),
        'reason': reason,
        'decision': ss_state.SS_STAGE_EXCLUDED_BY_TITLE
    }
    for paper_id in paper_ids:
        p = dora.set_paper_pr_rs_with_details(
            paper_id, 
            pr=ss_state.SS_PR_PASSED_TITLE, 
            rs=ss_state.SS_RS_EXCLUDED_TITLE,
            detail_dict=detail_dict)
        papers.append(p.as_simple_dict())

    ret = {
        'success': True,
        'papers': papers
    }
    return jsonify(ret)


@bp.route('/sspr/exclude_papers_ab', methods=['GET', 'POST'])
@login_required
def sspr_exclude_papers_ab():
    project_id = request.form.get('project_id')
    paper_ids = request.form.get('paper_ids')
    reason = ""
    paper_ids = paper_ids.split(',')

    papers = []

    # create a dict for the details
    detail_dict = {
        'date_decided': util.get_today_date_str(),
        'reason': reason,
        'decision': ss_state.SS_STAGE_EXCLUDED_BY_ABSTRACT
    }

    for paper_id in paper_ids:
        p = dora.set_paper_pr_rs_with_details(
            paper_id, 
            pr=ss_state.SS_PR_PASSED_TITLE, 
            rs=ss_state.SS_RS_EXCLUDED_ABSTRACT,
            detail_dict=detail_dict)
        papers.append(p.as_simple_dict())

    ret = {
        'success': True,
        'papers': papers
    }
    return jsonify(ret)


@bp.route('/sspr/exclude_papers_ft', methods=['GET', 'POST'])
@login_required
def sspr_exclude_papers_ft():
    project_id = request.form.get('project_id')
    paper_ids = request.form.get('paper_ids')
    # need to provide reason for ex ft
    reason = request.form.get('reason')
    paper_ids = paper_ids.split(',')
    
    papers = []
    
    # create a dict for the details
    detail_dict = {
        'date_decided': util.get_today_date_str(),
        'reason': reason,
        'decision': ss_state.SS_STAGE_EXCLUDED_BY_FULLTEXT
    }

    for paper_id in paper_ids:
        p = dora.set_paper_pr_rs_with_details(
            paper_id, 
            pr=ss_state.SS_PR_CHECKED_FULLTEXT, 
            rs=ss_state.SS_RS_EXCLUDED_FULLTEXT,
            detail_dict=detail_dict)
        papers.append(p.as_simple_dict())

    ret = {
        'success': True,
        'papers': papers
    }
    return jsonify(ret)


@bp.route('/sspr/include_papers_sr', methods=['GET', 'POST'])
@login_required
def sspr_include_papers_sr():
    project_id = request.form.get('project_id')
    paper_ids = request.form.get('paper_ids')
    reason = request.form.get('reason')
    paper_ids = paper_ids.split(',')

    papers = []
    
    # create a dict for the details
    # detail_dict = {
    #     'date_decided': util.get_today_date_str(),
    #     'reason': reason,
    #     'decision': ss_state.SS_STAGE_INCLUDED_SR
    # }

    detail_dict = util.get_decision_detail_dict(
        reason, ss_state.SS_STAGE_INCLUDED_SR
    )

    project = dora.get_project(project_id)
    # for those included in sr, also included in each sub cq
    detail_dict['ss_cq'] = util.make_ss_cq_dict(project)

    for paper_id in paper_ids:
        p = dora.set_paper_pr_rs_with_details(
            paper_id, 
            pr=ss_state.SS_PR_CHECKED_SR,
            rs=ss_state.SS_RS_INCLUDED_ONLY_SR,
            detail_dict=detail_dict)
        papers.append(p.as_simple_dict())

    ret = {
        'success': True,
        'papers': papers
    }
    return jsonify(ret)


@bp.route('/sspr/include_papers_srma', methods=['GET', 'POST'])
@login_required
def sspr_include_papers_srma():
    project_id = request.form.get('project_id')
    paper_ids = request.form.get('paper_ids')
    reason = ""
    paper_ids = paper_ids.split(',')

    papers = []

    # create a dict for the details
    detail_dict = {
        'date_decided': util.get_today_date_str(),
        'reason': reason,
        'decision': ss_state.SS_STAGE_INCLUDED_SR
    }

    for paper_id in paper_ids:
        p = dora.set_paper_pr_rs_with_details(
            paper_id,
            pr=ss_state.SS_PR_CHECKED_SRMA,
            rs=ss_state.SS_RS_INCLUDED_SRMA,
            detail_dict=detail_dict)
        papers.append(p.as_simple_dict())

    ret = {
        'success': True,
        'papers': papers
    }
    return jsonify(ret)


@bp.route('/sspr/set_label_rfc', methods=['GET', 'POST'])
@login_required
def sspr_set_label_rfc():
    project_id = request.form.get('project_id')
    paper_id = request.form.get('paper_id')
    cq_abbr = request.form.get('cq_abbr')
    rfc = request.form.get('rfc')

    is_success, paper = srv_paper.set_paper_label_rfc(paper_id, rfc, cq_abbr)

    ret = {
        'success': is_success,
        'paper': paper.as_simple_dict() if is_success else None
    }
    return jsonify(ret)


@bp.route('/sspr/set_label_dis', methods=['GET', 'POST'])
@login_required
def sspr_set_label_dis():
    project_id = request.form.get('project_id')
    paper_id = request.form.get('paper_id')
    cq_abbr = request.form.get('cq_abbr')
    dis = request.form.get('dis')

    is_success, paper = srv_paper.set_paper_label_dis(paper_id, dis, cq_abbr)

    ret = {
        'success': is_success,
        'paper': paper.as_simple_dict() if is_success else None
    }
    return jsonify(ret)


@bp.route('/sspr/set_label_ckl', methods=['GET', 'POST'])
@login_required
def sspr_set_label_ckl():
    project_id = request.form.get('project_id')
    paper_ids = request.form.get('paper_ids')
    paper_ids = paper_ids.split(',')
    
    papers = []

    for paper_id in paper_ids:
        p = srv_paper.set_paper_ss_label(
            paper_id, ss_state.SS_LABEL_CKL,
            current_user
        )
        papers.append(p.as_simple_dict())

    ret = {
        'success': True,
        'papers': papers
    }
    return jsonify(ret)


@bp.route('/sspr/unset_label_ckl', methods=['GET', 'POST'])
@login_required
def sspr_unset_label_ckl():
    project_id = request.form.get('project_id')
    paper_ids = request.form.get('paper_ids')
    paper_ids = paper_ids.split(',')
    
    papers = []

    for paper_id in paper_ids:
        p = srv_paper.unset_paper_ss_label(
            paper_id, 
            ss_state.SS_LABEL_CKL
        )
        papers.append(p.as_simple_dict())

    ret = {
        'success': True,
        'papers': papers
    }
    return jsonify(ret)


@bp.route('/sspr/set_rct_feedback', methods=['GET', 'POST'])
@login_required
def sspr_set_rct_feedback():
    project_id = request.form.get('project_id')
    paper_ids = request.form.get('paper_ids')
    paper_ids = paper_ids.split(',')
    
    feedback = request.form.get('feedback')
    if feedback not in ['0', '1']:
        # reset feedback to empty if not 0 or 1
        feedback = ''
    papers = []

    # need to measure the time
    start_time = time.perf_counter()
    for paper_id in paper_ids:
        paper = dora.set_rct_user_feedback(paper_id, feedback)
        papers.append(paper.as_simple_dict())

    ret = {
        'success': True,
        'papers': papers
    }

    # Stop the timer
    end_time = time.perf_counter()

    # Calculate the time difference
    elapsed_time = end_time - start_time

    # Print the elapsed time
    print("* time elapsed /sspr/set_rct_feedback:", elapsed_time)

    return jsonify(ret)


###############################################################################
# Internal functions for screener
###############################################################################

# def set_label_check_later(paper_id):
#     '''
#     Set the "check later" label for study
#     '''
#     paper = dora.set_paper_ss_label(paper_id, ss_state.SS_LABEL_CKL)
#     return paper


# def unset_label_check_later(paper_id):
#     '''
#     Unset the "check later" label for study
#     '''
#     paper = dora.unset_paper_ss_label(paper_id, ss_state.SS_LABEL_CKL)
#     return paper
