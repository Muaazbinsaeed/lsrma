from operator import contains
import re
import uuid
import datetime
from sqlalchemy.sql.expression import extract

from werkzeug.security import generate_password_hash

from sqlalchemy import and_, or_, not_
from sqlalchemy import func
from sqlalchemy import text
from sqlalchemy import update as sqlalchemy_update
from sqlalchemy.orm.attributes import flag_modified

from lnma import ss_state
from .models import Project
from .models import User
from .models import Paper
from .models import Piece
from .models import DataSource
from .models import Extract
from .models import Note

from . import db

from lnma import util
from lnma.util import get_year, pred_rct
from lnma.util import get_nct_number
from lnma import settings

REL_PROJECT_USER_CREATOR = 'creator'

def create_project(owner_uid, title, keystr=None, abstract="", p_settings=None):
    """
    Create a project based on given parameter
    """
    # create a project
    project_id = str(uuid.uuid1())
    if keystr is None or keystr.strip() == '':
        keystr = str(uuid.uuid1()).split('-')[0].upper()
    else:
        pass

    # detect if the keystr exists
    _p = get_project_by_keystr(keystr)
    if _p is not None:
        # existed???
        return None, 'existed project'

    date_created = datetime.datetime.now()
    date_updated = datetime.datetime.now()
    is_deleted = settings.PAPER_IS_DELETED_NO

    # settings is very very very important!
    # 2021-08-13: the `settings` is the module name ...
    import copy
    if p_settings is None:
        p_settings = copy.deepcopy(settings.PROJECT_DEFAULT_SETTINGS)

    # update the cq name
    p_settings["clinical_questions"][0]['name'] = title

    project = Project(
        project_id = project_id,
        keystr = keystr,
        owner_uid = owner_uid,
        title = title,
        abstract = abstract,
        date_created = date_created,
        date_updated = date_updated,
        settings = p_settings,
        is_deleted = is_deleted
    )
    owner = User.query.get(owner_uid)
    project.related_users.append(owner)
    db.session.add(project)
    db.session.commit()

    return project, 'ok'


def get_project(project_id):
    project = Project.query.filter(and_(
        Project.project_id == project_id
    )).first()

    return project


def get_project_by_keystr(keystr):
    project = Project.query.filter(and_(
        Project.keystr == keystr
    )).first()

    return project


def get_all_projects():
    '''
    Get all projects
    '''
    return list_all_projects()


def list_all_projects():
    '''
    Get all projects for test
    '''
    projects = Project.query.all()
    return projects


def create_user(uid, first_name, last_name, password, role='user'):
    '''
    Create a user in this database
    '''
    user = User(
        uid = uid,
        password = generate_password_hash(password),
        first_name = first_name,
        last_name = last_name,
        role = role,
        is_deleted = settings.PAPER_IS_DELETED_NO
    )
    db.session.add(user)
    db.session.commit()

    return user


def reset_user_password(uid, password):
    '''
    Reset user password
    '''
    user = User.query.get(uid)

    if user is None:
        return False, None
    else:
        user.password = generate_password_hash(password)
        db.session.commit()
        return True, user
        

def is_existed_user(uid):
    '''
    Check whether the specified user exists
    '''
    user = get_user(uid)

    if user is None:
        return False, None
    else:
        return True, user


def create_user_if_not_exist(uid, first_name, last_name, password, role='user'):
    '''
    Create a user in this database if not existed
    '''
    is_existed, user = is_existed_user(uid)

    if is_existed:
        return is_existed, user
    else:
        user = create_user(
            uid = uid, 
            first_name = first_name,
            last_name = last_name,
            password = password,
            role = role
        )
        return is_existed, user


def add_user_to_project_by_keystr_if_not_in(uid, keystr):
    '''
    Add user to a project by the keystr
    '''
    project = get_project_by_keystr(keystr)
    if project is None:
        return None, None, None

    return add_user_to_project_if_not_in(uid, project.project_id)



def assign_bulk_users_to_users(users_list , keystr):
    project = get_project_by_keystr(keystr)
    if project is None:
        return False
    owner_obj = User.query.get(project.owner_uid)
    project.related_users = [owner_obj]

    db.session.commit()

    for user in users_list:
        obj = User.query.get(user)
        project.related_users.append(obj)
        db.session.commit()
    return True


def add_user_to_project_if_not_in(uid, project_id):
    project = get_project(project_id)
    if project is None:
        return None, None, None

    is_in, user = project.is_user_in(uid)
    if is_in:
        pass
    else:
        user = User.query.get(uid)
        if user is None:
            return None, None, project

        project.related_users.append(user)
        db.session.commit()

    return (is_in, user, project)


def remove_user_from_project_by_keystr_if_in(uid, keystr):
    '''
    Remove user from a project
    '''
    project = get_project_by_keystr(keystr)
    if project is None:
        return None, None, None

    is_in, user = project.is_user_in(uid)

    if is_in:
        user = User.query.get(uid)
        if user is None:
            return None, None, project
        project.related_users.remove(user)
        db.session.commit()

    return (is_in, user, project)


def get_user(uid):
    user = User.query.filter(User.uid == uid).first()
    return user


def list_all_users():
    users = User.query.all()
    return users


def count_projects(uid=None):
    '''
    Count how many projects a user has
    '''

    if uid is None:
        cnt = Project.query.count()
    else:
        cnt = Project.query.filter_by(
            Project.related_users.any(
                uid=uid
            )
        ).count()

    return cnt
    

def list_projects_by_uid(owner_uid):
    projects = Project.query.filter(Project.related_users.any(uid=owner_uid)).all()
    return projects

def get_paper_by_pid(pid):
    return  Paper.query.filter_by(
        pid=pid,
    ).first()


def delete_paper(paper_id):
    '''
    Delete a paper
    '''
    p = Paper.query.filter_by(
        paper_id=paper_id
    ).first()

    if p is None:
        return False

    db.session.delete(p)
    db.session.commit()

    return True


def delete_project(project_id):
    '''
    Delete a project (and related relations with users)
    '''
    p = Project.query.filter_by(
        project_id=project_id
    ).first()

    if p is None:
        return False

    db.session.delete(p)
    db.session.commit()

    return True


def delete_project_and_papers(project_id):
    '''
    Delete a project and related papers
    '''
    prj = Project.query.filter_by(
        project_id=project_id
    ).first()

    if prj is None:
        return False

    # first, delete those papers
    Paper.query.filter_by(
        project_id=project_id
    ).delete()

    # second, delete the project
    db.session.delete(prj)

    # commit
    db.session.commit()

    return True


def is_existed_project(project_id):
    '''
    Check if a project exists
    '''
    project = Project.query.filter(Project.project_id==project_id).first()

    if project is None:
        return False
    else:
        return True


def set_project_criterias(project_id, inclusion_criterias, exclusion_criterias):
    '''
    Set the inclusion/exclusion criterias list for a project
    '''
    project = get_project(project_id)
    if project is None:
        return False, None

    if 'criterias' not in project.settings:
        project.settings['criterias'] = {
            "inclusion": '',
            "exclusion": ''
        }

    project.settings['criterias']['inclusion'] = inclusion_criterias
    project.settings['criterias']['exclusion'] = exclusion_criterias
    
    flag_modified(project, "settings")

    # commit this
    db.session.add(project)
    db.session.commit()

    return True, project


def set_project_exclusion_reasons(project_id, exclusion_reasons):
    '''
    Set the exclusion_reasons for a project
    '''
    project = get_project(project_id)
    if project is None:
        return False, None

    if 'exclusion_reasons' not in project.settings:
        project.settings['exclusion_reasons'] = []

    project.settings['exclusion_reasons'] = exclusion_reasons
    flag_modified(project, "settings")

    # commit this
    db.session.add(project)
    db.session.commit()

    return True, project


def set_project_highlight_keywords(project_id, highlight_keywords):
    '''
    Set the highlight_keywords list for a project
    '''
    project = get_project(project_id)
    if project is None:
        return False, None

    if 'highlight_keywords' not in project.settings:
        project.settings['highlight_keywords'] = {
            "inclusion": [],
            "exclusion": []
        }

    project.settings['highlight_keywords'] = highlight_keywords
    flag_modified(project, "settings")

    # commit this
    db.session.add(project)
    db.session.commit()

    return True, project


def set_project_tags(project_id, tags):
    '''
    Set the tag list for a project
    '''
    project = get_project(project_id)
    if project is None:
        return False, None

    if 'tags' not in project.settings:
        project.settings['tags'] = []

    project.settings['tags'] = tags
    flag_modified(project, "settings")

    # commit this
    db.session.add(project)
    db.session.commit()

    return True, project


def set_project_pdf_keywords(project_id, keywords, other_keywords=None):
    '''
    Set the pdf keywords list for a project
    '''
    project = get_project(project_id)
    if project is None:
        return False, None

    if 'pdf_keywords' not in project.settings:
        project.settings['pdf_keywords'] = {
            "main": []
        }

    if 'main' not in project.settings['pdf_keywords']:
        project.settings['pdf_keywords']['main'] = []

    project.settings['pdf_keywords']['main'] = keywords
    flag_modified(project, "settings")

    # commit this
    db.session.add(project)
    db.session.commit()

    return True, project


def set_project_settings(project_id, settings):
    '''
    Set the project settings directly.

    CAUTION! this function is VERY VERY dangerous.
    Don't use unless you are 120% sure what you are doing.
    '''
    project = get_project(project_id)
    if project is None:
        return False, None

    project.settings = settings
    flag_modified(project, "settings")

    # commit this
    db.session.add(project)
    db.session.commit()

    return True, project
    

def sort_paper_rct_seq_in_project(project_id):
    '''
    Sort the paper's rct seq

    Based on 
    '''
    # papers = get_papers(project_id)
    papers = get_papers_by_stage(
        project_id, 
        ss_state.SS_STAGE_INCLUDED_SR
    )

    # get all nct
    ncts = {}

    n_papers = 0
    for paper in papers:
        if paper.meta['rct_id'] == '': continue

        # update the rct
        nct = paper.meta['rct_id']
        if nct not in ncts:
            ncts[nct] = {
                'rct_seq': {},
                'papers': []
            }

        ncts[nct]['papers'].append({
            'pid': paper.pid,
            'pub_date': get_year(paper.pub_date)
        })

        n_papers += 1

    print('* found %d papers of %d RCT_ID' % (
        n_papers, len(ncts)
    ))
    
    # sort the nct's paper
    for nct in ncts:
        ncts[nct]['papers'] = sorted(
            ncts[nct]['papers'],
            key=lambda p: p['pub_date']
        )
        for i, p in enumerate(ncts[nct]['papers']):
            ncts[nct]['rct_seq'][p['pid']] = i

    print('* sorted all nct and papers')

    # update the paper
    n_updates = 0
    for paper in papers:
        if paper.meta['rct_id'] == '':
            paper.meta['rct_seq'] = None
            paper.meta['study_type'] = None
            flag_modified(paper, 'meta')

        else:
            nct = paper.meta['rct_id']
            
            rct_seq = ncts[nct]['rct_seq'][paper.pid]
            if rct_seq == 0:
                study_type = settings.PAPER_STUDY_TYPE_ORIGINAL
            else:
                study_type = settings.PAPER_STUDY_TYPE_FOLLOWUP
            
            paper.meta['rct_seq'] = rct_seq
            paper.meta['study_type'] = study_type
            flag_modified(paper, 'meta')

            db.session.add(paper)
            n_updates += 1

    # commit!
    db.session.commit()
    print('* updated %s paper study_type' % (n_updates))

    return papers


def set_paper_rct_id(paper_id, rct_id):
    '''
    Set the main rct_id for study
    '''
    paper = get_paper_by_id(paper_id)

    paper.meta['rct_id'] = rct_id
    flag_modified(paper, "meta")

    # automatic update the date_updated
    paper.date_updated = datetime.datetime.now()
    
    db.session.add(paper)
    db.session.commit()

    return True, paper


def set_paper_meta_ds_id(paper_id, ds_name, ds_id):
    '''
    Set the data source id for a paper
    '''
    # just call the set pid
    paper = get_paper_by_id(paper_id)
    project_id = paper.project_id

    # 2023-01-16: just set the pmid in place
    # in case this study doesn't have ds_id yet
    # just give set it
    has_updated_meta_ds_id = paper.update_meta_ds_id_by_self()

    # just set it
    paper.meta['ds_id'][ds_name] = ds_id

    # automatic update the date_updated
    paper.date_updated = datetime.datetime.now()
    
    flag_modified(paper, 'meta')
    db.session.add(paper)
    db.session.commit()

    return True, paper


def set_paper_pmid(paper_id, pmid):
    '''
    Set the PMID for a paper
    '''
    # just call the set pid
    paper = get_paper_by_id(paper_id)
    project_id = paper.project_id

    # 2023-01-16: just set the pmid in place
    # in case this study doesn't have ds_id yet
    # just give set it
    has_updated_meta_ds_id = paper.update_meta_ds_id_by_self()

    # just set it
    paper.meta['ds_id']['pmid'] = pmid

    # second, try to update the pid if possible
    # 1. try to find all possible extracts
    selected_abbrs = get_paper_selections(project_id, paper.pid)
    existed_papers = get_papers_by_pids(project_id, [pmid])

    if len(selected_abbrs) == 0:
        # great! this paper is not used in any extraction yet
        # just go modify the name
        if len(existed_papers) == 0:
            # which means it is not exists
            # we can update the pid for this paper
            paper.pid = pmid
            paper.pid_type = 'PMID'

        else:
            # oh... too bad, it's better to reset the existed one
            # but the issue is ... these paper may be used by extracts!
            # so need to check each one and modify
            # it's better not to touch this part
            # but need to let user know.
            pass
    else:
        # this paper is used in some extracts ...
        # so ... any way, just leave as it is
        pass

    # automatic update the date_updated
    paper.date_updated = datetime.datetime.now()
    
    flag_modified(paper, 'meta')
    db.session.add(paper)
    db.session.commit()

    return True, paper


def set_paper_pid(paper_id, pid, pid_type=None):
    '''
    Set the pid for a paper

    Please make sure this pid is not used by other paper!!!
    '''
    paper = get_paper_by_id(paper_id)
    project_id = paper.project_id

    existed_papers = get_papers_by_pids(project_id, [pid])
    if existed_papers == []:
        # which means it is not exists
        pass
    else:
        # this pmid exists!!!
        return False, existed_papers[0]

    # need to check if this pmid exists
    old_pid = paper.pid
    old_pid_type = paper.pid_type

    # now, set new pid
    paper.pid = pid

    if pid_type is None:
        pid_type = util.guess_pid_type_by_pid(pid)
    paper.pid_type = pid_type

    # 2023-06-03: just set the pmid in place
    # in case this study doesn't have ds_id yet
    # just give set it
    has_updated_meta_ds_id = paper.update_meta_ds_id_by_self(
        force_update=True
    )

    # and update the ds_id
    ds_id_type = util.get_ds_name_by_pid_and_type(
        pid, pid_type
    )
    paper.meta['ds_id'][ds_id_type] = pid
    # as JSON format meta is changed, need to flag
    flag_modified(paper, 'meta')

    # then, try to update pid in extraction if possible
    pieces = get_pieces_by_project_id_and_pid(
        project_id,
        old_pid
    ).all()

    if len(pieces) == 0:
        # great!!! but in most cases, it's not possible
        print("* Not found any pieces for paper[%s] in project[%s]" % ( 
            old_pid,
            project_id
        ))
    else:
        # ok ... let's update these pieces
        stmt = sqlalchemy_update(Piece).where(
            and_(
                Piece.project_id == project_id,
                Piece.pid == old_pid
            )
        ).values(
            pid=pid
        )
        db.session.execute(stmt)
        print(" Found and added %s pieces to be updated for paper[%s] in project[%s]" % (
            len(pieces),
            old_pid,
            project_id
        ))

    # automatic update the date_updated
    paper.date_updated = datetime.datetime.now()
    
    db.session.add(paper)
    db.session.commit()
    print('* set paper[%s] pid %s(%s)->%s(%s)' % (
        paper_id,
        old_pid, old_pid_type,
        pid, pid_type
    ))

    return True, paper


def set_paper_pub_date(paper_id, pub_date):
    '''
    Set the pub_date for a paper
    '''
    paper = get_paper_by_id(paper_id)

    paper.pub_date = pub_date

    # automatic update the date_updated
    paper.date_updated = datetime.datetime.now()
    
    db.session.add(paper)
    db.session.commit()

    return True, paper


def add_paper_tag(paper_id, tag):
    '''
    Add a tag to a paper
    '''
    paper = get_paper_by_id(paper_id)
    
    # add tags key if not exist
    if 'tags' not in paper.meta:
        paper.meta['tags'] = []

    # add tag
    if tag not in paper.meta['tags']:
        paper.meta['tags'].append(tag)
        flag_modified(paper, 'meta')
        db.session.add(paper)
        db.session.commit()
    else:
        pass

    return True, paper


def toggle_paper_tag(paper_id, tag):
    '''
    Toggle a tag on a paper.
    '''
    paper = get_paper_by_id(paper_id)
    
    # add tags key if not exist
    if 'tags' not in paper.meta:
        paper.meta['tags'] = []

    # toggle tag
    if tag not in paper.meta['tags']:
        paper.meta['tags'].append(tag)
    else:
        paper.meta['tags'].remove(tag)

    flag_modified(paper, 'meta')
    db.session.add(paper)
    db.session.commit()
    
    return True, paper


def is_existed_paper(project_id, pid, title=None):
    '''
    Check if a pid exists and title (optional)

    By default check the pmid
    '''
    paper = Paper.query.filter(and_(
        Paper.project_id == project_id,
        Paper.pid == pid
    )).first()

    if paper is None:
        if title is not None:
            # try to use the title
            paper = Paper.query.filter(and_(
                Paper.project_id == project_id,
                Paper.title == title
            )).first()

            if paper is not None:
                return True, paper

        # which means not matter title is None or not,
        # this paper doesn't exist
        return False, None

    else:
        return True, paper


def create_paper(project_id, pid, 
    pid_type='pmid', title=None, abstract=None,
    pub_date=None, authors=None, journal=None, meta=None,
    ss_st=None, ss_pr=None, ss_rs=None, ss_ex=None, seq_num=None):
    """
    Create a paper object, 

    By default, the pmid. 
    Please make sure the input pmid is NOT exist
    """
    paper_id = str(uuid.uuid1())
    pid = pid
    pid_type = pid_type
    title = '' if title is None else title
    abstract = '' if abstract is None else abstract
    pub_date = '' if pub_date is None else pub_date
    authors = '' if authors is None else authors
    journal = '' if journal is None else journal
    
    # the meta will contain more information
    all_rct_ids = get_nct_number(abstract)
    rct_id = '' if len(all_rct_ids) == 0 else all_rct_ids[0]
    
    # get ds_id
    ds_name = util.get_ds_name_by_pid_and_type(pid, pid_type)

    _meta = {
        'tags': [],
        'pdfs': [],
        'rct_id': rct_id,
        'all_rct_ids': all_rct_ids,
        # 2023-01-16: for de-duplication
        # just use this to store the correct ID information
        # we don't want to lose any records in the db
        # so, even for a duplicated records, we still need to save it
        'ds_id': {
            ds_name: pid
        }
    }
    if meta is None:
        pass
    else:
        # copy the data in the meta to overwrite the default one
        for k in meta:
            _meta[k] = meta[k]

    ss_st = ss_state.SS_ST_AUTO_OTHER if ss_st is None else ss_st
    ss_pr = ss_state.SS_PR_NA if ss_pr is None else ss_pr
    ss_rs = ss_state.SS_RS_NA if ss_rs is None else ss_rs

    # ss_ex is an extend attribute for each record
    ss_ex = {
        'label': {},
    } if ss_ex is None else ss_ex

    date_created = datetime.datetime.now()
    date_updated = datetime.datetime.now()
    is_deleted = settings.PAPER_IS_DELETED_NO
    if seq_num is None:
        # need to get the current max number
        max_cur_seq = get_current_max_seq_num(project_id)
        # increase one bit
        seq_num = max_cur_seq + 1

    paper = Paper(
        paper_id = paper_id,
        pid = pid,
        pid_type = pid_type,
        project_id = project_id,
        title = title,
        abstract = abstract,
        pub_date = pub_date,
        authors = authors,
        journal = journal,
        meta = _meta,
        ss_st = ss_st,
        ss_pr = ss_pr,
        ss_rs = ss_rs,
        ss_ex = ss_ex,
        date_created = date_created,
        date_updated = date_updated,
        is_deleted = is_deleted,
        seq_num = seq_num
    )

    db.session.add(paper)
    db.session.commit()

    return paper


def update_paper_pub_date(paper_id, pub_date):
    '''
    Update the paper pub_date
    '''
    paper = get_paper_by_id(paper_id)
    paper.pub_date = pub_date

    db.session.add(paper)
    db.session.commit()

    return paper


def update_paper_rct_result_by_keystr_and_seq_num(keystr, seq_num):
    '''
    Update the RCT detection result
    '''
    paper = get_paper_by_keystr_and_seq(keystr, seq_num)
    paper = update_paper_rct_result(paper)

    return paper


def update_paper_rct_result(project_id, pid):
    '''Update the RCT detection result
    '''
    paper = get_paper_by_project_id_and_pid(project_id, pid)
    paper = update_paper_rct_result(paper)

    return paper


def update_paper_rct_result(paper):
    '''
    The function of updating RCT result
    '''
    # TODO catch exception
    pred = pred_rct(paper.title, paper.abstract)
    paper.meta['pred'] = pred['pred']

    # and add to pred_dict
    if 'pred_dict' not in paper.meta:
        # ok, this is a new record
        paper.meta['pred_dict'] = {}

    paper.meta['pred_dict'][settings.AI_MODEL_ROBOTSEARCH_RCT] = pred['pred'][0]
    
    flag_modified(paper, "meta")
    
    # commit this
    db.session.add(paper)
    db.session.commit()

    return paper


def update_paper_ss_cq_decision(
    paper, 
    cqs,
    decision=settings.SCREENER_DEFAULT_DECISION_FOR_CQ_INCLUSION, 
    reason=settings.SCREENER_DEFAULT_REASON_FOR_CQ_INCLUSION):
    '''
    Update paper ss_cq decision

    cqs: [{
            abbr: 'default',
            name: 'Long name'
        }, ...]

    '''
    # now update the ss cq for just this 
    is_success, msg = paper.update_ss_cq_by_cqs(
        cqs,
        decision,
        reason
    )

    if is_success:
        flag_modified(paper, "ss_ex")
        
        # commit this
        db.session.add(paper)
        db.session.commit()
        # print('* updated %s ss_cq:' % (paper_id), cqs, decision, reason)

    else:
        print('* failed update_paper_ss_cq_decision! %s' % (
            msg
        ))

    return paper


def update_paper_ss_cq_decision_by_paper_id(paper_id, 
    cqs,
    decision=settings.SCREENER_DEFAULT_DECISION_FOR_CQ_INCLUSION, 
    reason=settings.SCREENER_DEFAULT_REASON_FOR_CQ_INCLUSION):
    '''
    Update paper ss_cq decision

    cqs: [{
            abbr: 'default',
            name: 'Long name'
        }, ...]

    '''
    paper = get_paper_by_id(paper_id)

    return update_paper_ss_cq_decision(
        paper,
        cqs,
        decision,
        reason
    )


def update_paper_ss_cq_decision_by_keystr_and_pid(
    keystr, pid,
    cqs,
    decision=settings.SCREENER_DEFAULT_DECISION_FOR_CQ_INCLUSION, 
    reason=settings.SCREENER_DEFAULT_REASON_FOR_CQ_INCLUSION
):
    '''
    Update paper ss_cq decision by keystr and pid
    
    '''
    paper = get_paper_by_keystr_and_pid(keystr, pid)

    # now update the ss cq for just this 
    paper.update_ss_cq_by_cqs(
        cqs,
        decision,
        reason
    )

    flag_modified(paper, "ss_ex")
    
    # commit this
    db.session.add(paper)
    db.session.commit()

    return paper


def _update_paper_meta(paper, auto_add=True, auto_commit=True):
    '''
    The internal function of updating meta 
    '''
    flag_modified(paper, "meta")
    
    # commit this
    if auto_add: db.session.add(paper)
    if auto_commit: db.session.commit()

    return paper


def set_paper_is_deleted_by_keystr_and_seq_num(keystr, seq_num, is_deleted):
    '''
    Update the is_deleted
    '''
    paper = get_paper_by_keystr_and_seq(keystr, seq_num)

    if is_deleted:
        paper.is_deleted = settings.PAPER_IS_DELETED_YES
    else:
        paper.is_deleted = settings.PAPER_IS_DELETED_NO

    db.session.add(paper)
    db.session.commit()

    return paper


def create_paper_if_not_exist(project_id, pid, 
    pid_type=None, title=None, abstract=None,
    pub_date=None, authors=None, journal=None, meta=None,
    ss_st=None, ss_pr=None, ss_rs=None, ss_ex=None, seq_num=None,
    skip_check_title=False):
    '''
    A wrapper function for create_paper and is_existed_paper
    '''
    is_existed, paper = is_existed_paper(
        project_id, 
        pid, 
        None if skip_check_title else title
    )
    if is_existed:
        return is_existed, paper
    else:
        p = create_paper(project_id, pid, 
            pid_type=pid_type, title=title, abstract=abstract,
            pub_date=pub_date, authors=authors, journal=journal, meta=meta,
            ss_st=ss_st, ss_pr=ss_pr, ss_rs=ss_rs, ss_ex=ss_ex, seq_num=seq_num)
        return is_existed, p


def create_paper_if_not_exist_and_predict_rct(project_id, pid, 
    pid_type=None, title=None, abstract=None,
    pub_date=None, authors=None, journal=None, meta=None,
    ss_st=None, ss_pr=None, ss_rs=None, ss_ex=None, seq_num=None,
    skip_check_title=False):
    '''
    A wrapper function for create_paper and is_existed_paper
    '''
    is_existed, paper = create_paper_if_not_exist(project_id, pid,
            pid_type=pid_type, title=title, abstract=abstract,
            pub_date=pub_date, authors=authors, journal=journal, meta=meta,
            ss_st=ss_st, ss_pr=ss_pr, ss_rs=ss_rs, ss_ex=ss_ex, seq_num=seq_num,
            skip_check_title=skip_check_title
    )

    if is_existed:
        # nothing to do for a existing paper
        return is_existed, paper
    else:
        # update the RCT for this paper by the internal function
        paper = update_paper_rct_result(paper)
        return is_existed, paper


# def get_paper(project_id, pid):
#     '''
#     Get a paper by the project_id and pid(pmid/embaseid)
#     '''
#     paper = Paper.query.filter(and_(
#         Paper.project_id == project_id,
#         Paper.pid == pid
#     )).first()

#     return paper


def get_paper_by_project_id_and_pid(project_id, pid):
    '''
    Get a paper by the project_id and pid(pmid/embaseid)
    '''
    paper = Paper.query.filter(and_(
        Paper.project_id == project_id,
        Paper.pid == pid
    )).first()

    return paper


def get_paper_by_id(paper_id):
    '''
    Get a paper by its unique paper_id
    '''
    paper = Paper.query.filter(and_(
        Paper.paper_id == paper_id
    )).first()

    return paper


def get_paper_by_seq(project_id, seq_num):
    '''
    Get a paper by the project_id and its seq_num
    '''
    paper = Paper.query.filter(and_(
        Paper.project_id == project_id,
        Paper.seq_num == seq_num
    )).first()

    return paper


def get_paper_by_keystr_and_seq(keystr, seq_num):
    '''
    Get a paper detail by the keystr and its seq_num
    '''
    project = get_project_by_keystr(keystr)
    if project is None:
        return None
    paper = get_paper_by_seq(project.project_id, seq_num)

    return paper


def get_paper_by_keystr_and_pid(keystr, pid):
    '''
    Get a paper detail by the keystr and its pid
    '''
    project = get_project_by_keystr(keystr)
    if project is None:
        return None
    paper = get_paper_by_project_id_and_pid(
        project.project_id, 
        pid
    )

    return paper


def get_all_papers():
    '''
    Get ALL papers in the database

    Please don't use this function if you are not sure
    '''
    papers = Paper.query.all()
    return papers


def get_n_papers_by_project_id(project_id):
    '''
    Get the number of papers by project_id
    '''
    n = db.session.query(
        func.count(Paper.paper_id)
    ).filter(
        Paper.project_id == project_id
    ).scalar()

    return n


def get_papers(project_id):
    papers = Paper.query.filter(and_(
        Paper.project_id == project_id,
        Paper.is_deleted == settings.PAPER_IS_DELETED_NO
    )).order_by(Paper.date_created.desc()).all()

    return papers


def get_papers_by_keystr(keystr):
    '''
    Get papers by the project keystr
    '''
    project = get_project_by_keystr(keystr)
    papers = Paper.query.filter(and_(
        Paper.project_id == project.project_id
    )).order_by(Paper.date_created.desc()).all()

    return papers


def get_papers_by_seq_nums(project_id, seq_nums):
    '''
    Get papers by the seq_num list
    '''
    papers = Paper.query.filter(and_(
        Paper.project_id == project_id,
        Paper.seq_num.in_(seq_nums)
    )).all()
    return papers


def get_papers_by_pids(project_id, pids):
    '''
    Get all the papers according to pmid list
    '''
    papers = Paper.query.filter(and_(
        Paper.project_id == project_id,
        Paper.pid.in_(pids)
    )).all()
    return papers


def get_papers_of_included_sr(project_id):
    '''
    Get all papers of included sr stage
    '''
    papers = Paper.query.filter(and_(
        Paper.project_id == project_id,
        Paper.ss_rs.in_([
            ss_state.SS_RS_INCLUDED_ONLY_SR,
            ss_state.SS_RS_INCLUDED_SRMA
        ]),
        Paper.is_deleted == settings.PAPER_IS_DELETED_NO
    )).order_by(Paper.date_updated.desc()).all()

    return papers


def get_papers_of_included_sr_and_cq(project_id, cq_abbr):
    '''
    Get all papers of included sr stage and in a cq
    '''
    _papers = get_papers_of_included_sr(project_id)

    # select those selected in this cq
    papers = []
    for p in _papers:
        if 'ss_cq' in p.ss_ex:
            if cq_abbr in p.ss_ex['ss_cq']:
                if p.ss_ex['ss_cq'][cq_abbr]['d'] == settings.PAPER_SS_EX_SS_CQ_DECISION_YES:
                    papers.append(p)
                else:
                    pass
            else:
                pass
        else:
            continue

    return papers


def get_papers_by_stage(project_id, stage, cq_abbr="default"):
    '''
    Get all papers of specified stage
    '''
    print('* get papers by stage [%s]' % stage)
    if stage == ss_state.SS_STAGE_ALL_OF_THEM:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()
    
    elif stage == ss_state.SS_STAGE_MANUAL:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_st.in_([
                'a24'
            ])
        )).order_by(Paper.date_updated.desc()).all()

    elif stage == ss_state.SS_STAGE_UNSCREENED:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            # 2020-12-10 how the study is imported doesn't matter for unscreened
            # Paper.ss_st.in_([
            #     ss_state.SS_ST_AUTO_EMAIL,
            #     ss_state.SS_ST_AUTO_SEARCH,
            #     ss_state.SS_ST_AUTO_OTHER,
            #     ss_state.SS_ST_IMPORT_ENDNOTE_XML,
            #     ss_state.SS_ST_IMPORT_OVID_XML,
            #     ss_state.SS_ST_IMPORT_SIMPLE_CSV
            # ]),
            Paper.ss_pr == ss_state.SS_PR_NA,
            Paper.ss_rs == ss_state.SS_RS_NA,
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    elif stage == ss_state.SS_STAGE_DECIDED:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_rs != ss_state.SS_RS_NA,
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    elif stage == ss_state.SS_STATE_PASSED_TITLE_NOT_FULLTEXT:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_pr == ss_state.SS_PR_PASSED_TITLE,
            Paper.ss_rs == ss_state.SS_RS_NA,
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    elif stage == ss_state.SS_STAGE_INCLUDED_SR:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_rs.in_([
                ss_state.SS_RS_INCLUDED_ONLY_SR,
                ss_state.SS_RS_INCLUDED_SRMA
            ]),
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    elif stage == ss_state.SS_STAGE_INCLUDED_SR_INITIAL:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_rs.in_([
                ss_state.SS_RS_INCLUDED_ONLY_SR,
                ss_state.SS_RS_INCLUDED_SRMA
            ]),
            Paper.ss_st.in_([
                'a21', 'a22', 'a23'
            ]),
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    

    elif stage == ss_state.SS_RS_INCLUDED_ONLY_SR:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_rs.in_([
                ss_state.SS_RS_INCLUDED_ONLY_SR
            ]),
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    elif stage == ss_state.SS_STAGE_INCLUDED_SRMA:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_rs == ss_state.SS_RS_INCLUDED_SRMA,
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    elif stage == ss_state.SS_STAGE_EXCLUDED_BY_TITLE_ABSTRACT:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_rs.in_([
                ss_state.SS_RS_EXCLUDED_TITLE,
                ss_state.SS_RS_EXCLUDED_ABSTRACT
            ]),
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    elif stage == ss_state.SS_STAGE_EXCLUDED_BY_TITLE:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_rs == ss_state.SS_RS_EXCLUDED_TITLE,
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    elif stage == ss_state.SS_STAGE_EXCLUDED_BY_ABSTRACT:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_rs == ss_state.SS_RS_EXCLUDED_ABSTRACT,
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    elif stage == ss_state.SS_STAGE_EXCLUDED_BY_FULLTEXT:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_rs == ss_state.SS_RS_EXCLUDED_FULLTEXT,
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    elif stage == ss_state.SS_STAGE_EXCLUDED_BY_FULLTEXT_INITIAL:
        papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.ss_rs == ss_state.SS_RS_EXCLUDED_FULLTEXT,
            Paper.ss_st.in_([
                'a21', 'a22', 'a23'
            ]),
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()

    else:
        print('* NOT found specified stage [%s]' % stage)
        papers = []
        
    return papers


def get_living_papers_based_on_pids(project_id, pids):
    papers = Paper.query.filter(and_(
            Paper.project_id == project_id,
            Paper.pid.in_(pids),
            Paper.is_deleted == settings.PAPER_IS_DELETED_NO
        )).order_by(Paper.date_updated.desc()).all()
    return papers


def set_paper_pr_rs(paper_id, pr=None, rs=None):
    '''
    Set the pr_rs for a paper
    '''
    paper = Paper.query.filter_by(
        paper_id=paper_id
    ).first()
    
    if pr is not None: paper.ss_pr = pr
    if rs is not None: paper.ss_rs = rs

    # automatic update the date_updated
    paper.date_updated = datetime.datetime.now()

    db.session.add(paper)
    db.session.commit()

    return paper


def set_paper_pr_rs_with_details(paper_id, pr=None, rs=None, detail_dict=None):
    '''
    Set the pr and rs state with more detail

    The detail is a dict that will be added/overwrite the paper.
    '''
    paper = Paper.query.filter_by(
        paper_id=paper_id
    ).first()
    
    if pr is not None: paper.ss_pr = pr
    if rs is not None: paper.ss_rs = rs
    if detail_dict is not None:
        for key in detail_dict:
            if detail_dict[key] is None:
                # which means remove this key
                if key in paper.ss_ex:
                    del paper.ss_ex[key]
                else:
                    pass
            else:
                paper.ss_ex[key] = detail_dict[key]
        flag_modified(paper, "ss_ex")

    # automatic update the date_updated
    paper.date_updated = datetime.datetime.now()

    db.session.add(paper)
    db.session.commit()
    return paper


def set_rct_user_feedback(paper_id, usr_fb):
    '''Set the user feedback for RCT result
    '''
    paper = Paper.query.filter_by(
        paper_id=paper_id
    ).first()

    if 'usr_fb' not in paper.meta['pred'][0]:
        paper.meta['pred'][0]['usr_fb'] = ''

    paper.meta['pred'][0]['usr_fb'] = usr_fb
    flag_modified(paper, "meta")

    db.session.add(paper)
    db.session.commit()
    
    return paper


def add_pdfs_to_paper(paper_id, pdf_metas):
    '''
    Add PDF meta to a paper
    '''
    paper = get_paper_by_id(paper_id)
    if paper is None:
        raise Exception('no such paper???')

    if 'pdfs' not in paper.meta:
        paper.meta['pdfs'] = []

    paper.meta['pdfs'] += pdf_metas
    flag_modified(paper, "meta")

    db.session.add(paper)
    db.session.commit()
    
    return paper


def remove_pdfs_from_paper(paper_id, pdf_metas):
    '''
    Remove PDF meta from a paper
    '''
    paper = get_paper_by_id(paper_id)
    if paper is None:
        raise Exception('no such paper???')

    file_ids_to_remove = [ f['file_id'] for f in pdf_metas ]
    new_pdf_metas = []
    for pdf_meta in paper.meta['pdfs']:
        if pdf_meta['file_id'] not in file_ids_to_remove:
            new_pdf_metas.append(pdf_meta)

    paper.meta['pdfs'] = new_pdf_metas
    flag_modified(paper, "meta")

    db.session.add(paper)
    db.session.commit()
    
    return paper


def get_screener_stat_by_stage(project_id, stage):
    '''
    Get the statistics on specified type
    '''
    ss_cond = ''
    if stage not in ss_state.SS_STAGE_CONDITIONS:
        return None

    # get condition for this type, e.g., 
    ss_cond = ss_state.SS_STAGE_CONDITIONS[stage]

    # get the stat on the given type
    sql = """
    select project_id,
        count(case when {ss_cond} then paper_id else null end) as {stage}
    from papers
    where project_id = '{project_id}'
    group by project_id
    """.format(project_id=project_id, ss_cond=ss_cond, stage=stage)
    r = db.session.execute(sql).fetchone()
    
    if r == None: 
        result = {
            stage: None
        }
    else:
        result = {
            stage: r[stage]
        }

    return result


def get_screener_cq_stat_by_project(project):
    '''
    Get the CQ-level statistics
    '''
    sql = """select project_id,"""
    attrs = ['all_of_them']

    for cq in project.settings['clinical_questions']:
        sql += """
        count(case when ss_rs in ('f1', 'f3') 
            and JSON_EXTRACT(ss_ex->'$.ss_cq', '$.{cq_abbr}.d') = 'yes'
            then paper_id else null end
        ) as cnt_included_in_cq_{cq_abbr},
        """.format(cq_abbr = cq['abbr'])

        attrs.append('cnt_included_in_cq_%s' % cq['abbr'])

    sql += """
    count(*) as all_of_them
    from papers
    where project_id = '{project_id}'
        and is_deleted = 'no'
    group by project_id
    """.format(project_id=project.project_id)

    # print(sql)

    r = db.session.execute(sql).fetchone()

    # put the values in result data
    result = {}
    for attr in attrs:
        try:
            result[attr] = r[attr]
        except:
            result[attr] = 0

    return result



def get_screener_stat_by_project_id(project_id):
    '''Get the statistics of the project for the screener
    '''
    sql = """
    select project_id,
        count(*) as all_of_them,
        count(case when ss_pr = 'na' and ss_rs = 'na' then paper_id else null end) as unscreened,
        count(case when ss_pr = 'na' and ss_rs = 'na' and json_contains_path(ss_ex->'$.label', 'one', '$.CKL') then paper_id else null end) as unscreened_ckl,

        count(case when ss_pr = 'p20' and ss_rs = 'na' then paper_id else null end) as passed_title_not_fulltext,
        count(case when ss_pr = 'p20' and ss_rs = 'na' and json_contains_path(ss_ex->'$.label', 'one', '$.CKL') then paper_id else null end) as passed_title_not_fulltext_ckl,
        
        count(case when ss_rs = 'e2' then paper_id else null end) as excluded_by_title,
        count(case when ss_rs = 'e2' and ss_st in ('a21', 'a22', 'a23') then paper_id else null end) as excluded_by_title_inital,
        count(case when ss_rs = 'e2' and json_contains_path(ss_ex->'$.label', 'one', '$.CKL') then paper_id else null end) as excluded_by_title_ckl,
        count(case when ss_rs = 'e2' and json_contains_path(ss_ex->'$.label', 'one', '$.RFC') then paper_id else null end) as excluded_by_title_rfc,

        count(case when ss_rs = 'e22' then paper_id else null end) as excluded_by_abstract,
        count(case when ss_rs = 'e22' and ss_st in ('a21', 'a22', 'a23') then paper_id else null end) as excluded_by_abstract_inital,
        count(case when ss_rs = 'e22' and json_contains_path(ss_ex->'$.label', 'one', '$.CKL') then paper_id else null end) as excluded_by_abstract_ckl,
        count(case when ss_rs = 'e22' and json_contains_path(ss_ex->'$.label', 'one', '$.RFC') then paper_id else null end) as excluded_by_abstract_rfc,

        count(case when ss_rs = 'e3' then paper_id else null end) as excluded_by_fulltext,
        count(case when ss_rs = 'e3' and ss_st in ('a21', 'a22', 'a23') then paper_id else null end) as excluded_by_full_text_inital,
        count(case when ss_rs = 'e3' and json_contains_path(ss_ex->'$.label', 'one', '$.CKL') then paper_id else null end) as excluded_by_fulltext_ckl,
        count(case when ss_rs = 'e3' and json_contains_path(ss_ex->'$.label', 'one', '$.RFC') then paper_id else null end) as excluded_by_fulltext_rfc,

        count(case when ss_rs = 'f1' then paper_id else null end) as included_only_sr,

        count(case when ss_rs in ('f1', 'f3') then paper_id else null end) as included_sr,
        count(case when ss_rs in ('f1', 'f3') and json_contains_path(ss_ex->'$.label', 'one', '$.CKL') then paper_id else null end) as included_sr_ckl,
        count(case when ss_rs in ('f1', 'f3') and json_contains_path(ss_ex->'$.label', 'one', '$.RFC') then paper_id else null end) as included_sr_rfc,

        count(case when ss_rs = 'f3' then paper_id else null end) as included_srma,
        count(case when ss_rs = 'f3' and json_contains_path(ss_ex->'$.label', 'one', '$.CKL') then paper_id else null end) as included_srma_ckl,

        count(case when ss_rs in ('e2', 'e22') then paper_id else null end) as excluded_by_title_abstract,
        count(case when ss_rs = 'e21' then paper_id else null end) as excluded_by_rct_classifier,

        count(case when ss_rs != 'na' then paper_id else null end) as decided,
        count(case when ss_rs != 'na' and json_contains_path(ss_ex->'$.label', 'one', '$.CKL') then paper_id else null end) as decided_ckl,
        count(case when ss_rs != 'na' and json_contains_path(ss_ex->'$.label', 'one', '$.RFC') then paper_id else null end) as decided_rfc
    
    from papers
    where project_id = '{project_id}'
        and is_deleted = 'no'
    group by project_id
    """.format(project_id=project_id)
    r = db.session.execute(sql).fetchone()

    # put the values in result data
    attrs = [
        'unscreened',
        'unscreened_ckl',

        'passed_title_not_fulltext',
        'passed_title_not_fulltext_ckl',

        'excluded_by_title',
        'excluded_by_title_inital',
        'excluded_by_title_ckl',
        'excluded_by_title_rfc',

        'excluded_by_abstract',
        'excluded_by_abstract_inital',
        'excluded_by_abstract_ckl',
        'excluded_by_abstract_rfc',

        'excluded_by_fulltext',
        'excluded_by_full_text_inital',
        'excluded_by_fulltext_ckl',
        'excluded_by_fulltext_rfc',

        'included_sr',
        'included_sr_ckl',
        'included_sr_rfc',

        'included_srma',
        'included_srma_ckl',

        'decided',
        'decided_ckl',
        'decided_rfc',

        # others
        'all_of_them',
        'included_only_sr',
        'excluded_by_title_abstract',
        'excluded_by_rct_classifier',
    ]
    result = {}
    for attr in attrs:
        try:
            result[attr] = r[attr]
        except:
            result[attr] = 0

    return result


def get_screener_stat_only_unscreened_by_project_id(project_id):
    '''Get the statistics of the project for the screener
    '''
    sql = """
    select project_id,
        count(*) as all_of_them,
        count(case when ss_pr = 'na' and ss_rs = 'na' then paper_id else null end) as unscreened,
        count(case when ss_pr = 'na' and ss_rs = 'na' and json_contains_path(ss_ex->'$.label', 'one', '$.CKL') then paper_id else null end) as unscreened_ckl
    
    from papers
    where project_id = '{project_id}'
        and is_deleted = 'no'
    group by project_id
    """.format(project_id=project_id)
    r = db.session.execute(sql).fetchone()

    # put the values in result data
    attrs = [
        'all_of_them',
        'unscreened',
        'unscreened_ckl'
    ]
    result = {}
    for attr in attrs:
        try:
            result[attr] = r[attr]
        except Exception as err:
            
            result[attr] = 0

    return result


def get_portal_stat():
    '''
    Get the statistics for portal
    '''
    sql = """
    select project_id,
        count(*) as all_of_them,
        count(case when ss_pr = 'na' and ss_rs = 'na' then paper_id else null end) as unscreened,
        count(case when ss_pr = 'na' and ss_rs = 'na' and json_contains_path(ss_ex->'$.label', 'one', '$.CKL') then paper_id else null end) as unscreened_ckl
    
    from papers
    where is_deleted = 'no'
    group by project_id
    """
    rs = db.session.execute(sql).fetchall()

    # put the values in result data
    attrs = [
        'all_of_them',
        'unscreened',
        'unscreened_ckl'
    ]
    result = {}
    for r in rs:
        project_id = r['project_id']
        result[project_id] = {}
        for attr in attrs:
            try:
                result[project_id][attr] = r[attr]
            except Exception as err:
                
                result[project_id][attr] = 0

    return result


def get_current_max_seq_num(project_id):
    '''Get the max seq number
    '''
    sql = """
    select max(seq_num) as max_cur_seq
    from papers
    where project_id = '{project_id}';
    """.format(project_id=project_id)

    r = db.session.execute(sql).fetchone()

    # the max_cur_seq should be an integer
    # but it also can be None
    max_cur_seq = r['max_cur_seq']
    if max_cur_seq is None:
        max_cur_seq = 0

    return max_cur_seq


###############################################################################
# Data Source Related Functions
###############################################################################

def create_datasource(
    ds_type, title, content
):
    '''
    Create a new data source record in db
    '''
    # create a datasource
    datasource_id = str(uuid.uuid1())
    date_created = datetime.datetime.now()

    datasource = DataSource(
        datasource_id = datasource_id,
        ds_type = ds_type,
        title = title,
        content = content,
        date_created = date_created,
    )
    
    db.session.add(datasource)
    db.session.commit()

    return datasource


###############################################################################
# Extract Related Functions
###############################################################################

def create_extract(project_id, oc_type, abbr, meta, data):
    '''
    Create a new extract for a project

    Args:

    oc_type: nma, pwma, itable
    '''
    # create the id
    extract_id = str(uuid.uuid1())
    date_created = datetime.datetime.now()
    date_updated = datetime.datetime.now()

    extract = Extract(
        extract_id = extract_id,
        project_id = project_id,
        oc_type = oc_type,
        abbr = abbr,
        meta = meta,
        data = data,
        date_created = date_created,
        date_updated = date_updated
    )

    db.session.add(extract)
    db.session.commit()

    return extract


def delete_extract(project_id, oc_type, abbr):
    '''
    Delete an extract
    '''
    extract = Extract.query.filter(and_(
        Extract.project_id == project_id,
        Extract.oc_type == oc_type,
        Extract.abbr == abbr
    )).first()

    db.session.delete(extract)
    db.session.commit()

    return True


def update_extract_meta(project_id, oc_type, abbr, meta):
    '''
    Update the existing extract meta only
    '''
    extract = Extract.query.filter(and_(
        Extract.project_id == project_id,
        Extract.abbr == abbr
    )).first()

    # TODO check if not exists

    # update
    extract.meta = meta
    extract.date_updated = datetime.datetime.now()

    flag_modified(extract, "meta")

    # commit this
    db.session.add(extract)
    db.session.commit()

    return extract


def update_extract_data(project_id, abbr, cq_abbr, data):
    '''
    Deprecated.

    The extract data should be updated by piece
    Update the existing extract data only
    '''
    extract = Extract.query.filter(and_(
        Extract.project_id == project_id,
        Extract.abbr == abbr,
        Extract.meta['cq_abbr'] == cq_abbr,
    )).first()

    # TODO check if not exists

    # update
    extract.data = data
    extract.date_updated = datetime.datetime.now()

    flag_modified(extract, "data")

    # commit this
    db.session.add(extract)
    db.session.commit()

    return extract


def update_extract_coe_meta(extract_id, coe):
    '''
    Update the CoE meta data of an existing extract
    '''
    extract = Extract.query.filter(
        Extract.extract_id == extract_id
    ).first()

    # TODO check if not exists

    # update the coe detail
    for ma in coe.keys():
        coe[ma]['date_updated'] = util.get_today_date_str()

    # update
    extract.meta['coe'] = coe
        # extract.meta['coe']['pids'] = extract.get_pids_selected()

    # flag update
    flag_modified(extract, "meta")

    # commit this
    db.session.add(extract)
    db.session.commit()

    return extract


def update_extract_incr_data(
    extract_id, 
    data, 
    flag_skip_is_selected=False
):
    '''
    Update the extract with the given incremental data

    The data have been modified in the frontend,
    so here we just save them.
    '''
    extract = get_extract(extract_id)
    
    pieces = create_or_update_pieces_by_extract_data(
        extract.project_id,
        extract.extract_id,
        data
    )

    return extract, pieces


def update_extract_meta_and_data(project_id, oc_type, abbr, meta, data):
    '''
    Update the existing extract
    '''
    extract = Extract.query.filter(and_(
        Extract.project_id == project_id,
        Extract.abbr == abbr
    )).first()

    # TODO check if not exists

    # update
    extract.meta = meta
    extract.data = data
    extract.date_updated = datetime.datetime.now()

    flag_modified(extract, "meta")
    flag_modified(extract, "data")

    # commit this
    db.session.add(extract)
    db.session.commit()

    return extract
    

def update_extract(
    extract, 
    flag_has_meta_modified=False, 
    flag_has_data_modified=False, 
    auto_add=True,
    auto_commit=True
):
    '''
    Update the given extract
    '''
    extract.date_updated = datetime.datetime.now()

    if flag_has_meta_modified: flag_modified(extract, "meta")
    if flag_has_data_modified: flag_modified(extract, "data")

    # commit this
    if auto_add: db.session.add(extract)
    if auto_commit: db.session.commit()

    return extract


def update_papers_outcome_selections(project, papers, extracts):
    '''
    Update the papers' outcome selections by
    '''
    # create a extract mapping from id to extract
    ext_dict = {}
    ext2seq = {}
    for i, ext in enumerate(extracts):
        extracts[i].meta['updated_selected_papers'] = []
        ext_dict[ext.extract_id] = ext
        ext2seq[ext.extract_id] = i

    # init the paper outcome selections
    pid2seq = {}
    for i, p in enumerate(papers):
        pid2seq[p.pid] = i
        papers[i].meta['outcome_selections'] = []

    # get the selections
    sql_get_paper_selection = """
select pid, extract_id
from pieces
where project_id='{project_id}'
and json_extract(data, "$.is_selected") = TRUE
    """.format(project_id=project.project_id)

    rs = db.session.execute(
        sql_get_paper_selection
    ).fetchall()

    # update the outcome
    for r in rs:
        pid = r['pid']
        extract_id = r['extract_id']

        if pid not in pid2seq:
            # which means this pid is not selected for current CQ
            continue

        if extract_id not in ext_dict:
            # this means this extract does not belong to current CQ
            continue

        # now let's get the abbr for this 
        abbr = ext_dict[extract_id].abbr
        
        # get the idx
        seq_pid = pid2seq[pid]

        # get the idx of extract
        seq_ext = ext2seq[extract_id]

        # update the paper selection
        papers[seq_pid].meta['outcome_selections'].append(abbr)

        # update the extract data
        extracts[seq_ext].meta['updated_selected_papers'].append(pid)

    return papers, extracts


def get_paper_selections(project_id, pid):
    '''
    Get
    '''


# def get_paper_selections(project_id, pid):
#     '''
#     Get the selections of a paper
#     '''
#     extracts = get_extracts_by_project_id(project_id)
#     return get_paper_selections_in_extracts(pid, extracts)
    

# def get_paper_selections_in_extracts(pid, extracts):
#     '''
#     Get the selections of a paper in specific extracts
#     '''
#     # check each extract
#     abbrs = []
#     for extract in extracts:
#         if pid in extract.data:
#             if extract.data[pid]['is_selected']:
#                 abbrs.append(extract.abbr)
#             else:
#                 pass
    
#     return abbrs

def get_paper_selections_in_extracts_by_pieces(pid, pieces, extract_dict):
    '''
    Get the selected abbrs of extracts
    '''
    abbrs = []
    for piece in pieces:
        if piece.pid == pid:
            if piece.data['is_selected']:
                abbrs.append(extract_dict[piece.extract_id]['abbr'])
        else:
            pass

    return abbrs


def update_paper_selection(project_id, cq_abbr, pid, abbr, is_selected):
    '''
    Update the paper outcome selection of single outcome
    '''
    # get the extraction/outcome
    extract = Extract.query.filter(
        Extract.project_id == project_id,
        Extract.abbr == abbr,
        Extract.meta['cq_abbr'] == cq_abbr,
    ).first()

    # get the paper
    paper = get_paper_by_project_id_and_pid(
        project_id, pid
    )

    # get the piece
    piece = get_piece_by_project_id_and_extract_id_and_pid(
        project_id,
        extract.extract_id,
        pid
    )

    if piece is None:
        # no such extraction yet, so just create one
        data = util.mk_empty_extract_paper_data(is_selected)
        # I don't remember what it is, just do it by following other function
        data['attrs']['main'] = util.fill_extract_data_arm(
            data['attrs']['main'],
            extract.meta['cate_attrs']
        )
        piece = create_piece(
            project_id,
            extract.extract_id,
            pid,
            data
        )
        print('* added %s in extract[%s]: %s' % (
            pid, abbr, is_selected
        ))
    else:
        # ok, let's update the piece
        piece.data['is_selected'] = is_selected
        flag_modified(piece, "data")
        db.session.add(piece)
        db.session.commit()
        print('* updated %s in extract[%s]: %s' % (
            pid, abbr, is_selected
        ))
    
    # ok, done!
    return paper, extract, piece


def update_paper_selections(project_id, cq_abbr, pid, abbrs):
    '''
    Update the paper outcome selections in a project
    '''
    # first, get all extracts of the specific cq
    extracts = Extract.query.filter(
        Extract.project_id == project_id,
        Extract.meta['cq_abbr'] == cq_abbr
    ).all()

    # get the paper
    paper = get_paper_by_project_id_and_pid(
        project_id, pid
    )

    # then do a loop checking
    for extract in extracts:
        oc_abbr = extract.abbr
        is_selected = oc_abbr in abbrs

        if pid in extract.data:
            db_is_selected = extract.data[pid]['is_selected']
            # print('* %s in %s (%s vs %s)' % (
            #     pid, oc_abbr, is_selected, db_is_selected
            # ))
            if is_selected == db_is_selected:
                # OK, no need to change the value
                pass
            else:
                # user changed the option, ok, update
                extract.data[pid]['is_selected'] = is_selected

                # add to session
                flag_modified(extract, "data")
                db.session.add(extract)
                
                print('* found %s in %s is_selected updated to %s' % (
                    pid, extract.meta['full_name'], is_selected
                ))

        else:
            # print('* %s NOT in %s (%s vs %s)' % (
            #     pid, oc_abbr, is_selected, None
            # ))
            # this is very very very rare, but possible?
            if is_selected:
                # well, have to add this pid to this outcome
                # make an empty extraction
                # {
                #     'is_selected': is_selected,
                #     'is_checked': False,
                #     'n_arms': 2,
                #     'attrs': {
                #         'main': {},
                #         'other': []
                #     }
                # }
                extract.data[pid] = util.mk_empty_extract_paper_data(is_selected)
                extract.data[pid]['attrs']['main'] = util.fill_extract_data_arm(
                    extract.data[pid]['attrs']['main'],
                    extract.meta['cate_attrs']
                )
                flag_modified(extract, "data")
                db.session.add(extract)

                print('* created %s in %s is_selected updated to %s' % (
                    pid, extract.abbr, is_selected
                ))
            else:
                # since it is not selected, just ignore is fine
                pass

    # commit all changes if any
    db.session.commit()

    return paper, abbrs


def get_all_extracts():
    '''
    Get ALL extracts in the database

    Please don't use this function if you are not sure
    '''
    extracts = Extract.query.all()
    return extracts


def get_extracts_by_project_id_and_cq(project_id, cq_abbr):
    '''
    Get all of the extracts by given project and cq
    '''
    extracts = Extract.query.filter(
        Extract.project_id == project_id,
        Extract.meta['cq_abbr'] == cq_abbr
    ).all()

    return extracts


def get_extracts_by_project_id(project_id):
    '''
    Get all of the extract detail of a project
    '''
    extracts = Extract.query.filter(
        Extract.project_id == project_id
    ).all()

    return extracts


def get_extracts_by_keystr(keystr:str):
    '''
    Get all of the extract detail of a project
    '''
    project = get_project_by_keystr(keystr)

    if project is None:
        # what???
        return None

    extracts = Extract.query.filter(
        Extract.project_id == project.project_id
    ).all()

    return extracts

def get_extracts_by_keystr_and_cq(keystr:str, cq_abbr:str):
    '''
    Get all of the extract detail of a project
    '''
    project = get_project_by_keystr(keystr)

    if project is None:
        # what???
        return None

    extracts = Extract.query.filter(
        Extract.project_id == project.project_id,
        Extract.meta['cq_abbr'] == cq_abbr
    ).all()

    return extracts


def get_extracts_by_keystr_and_cq_and_oc_type(keystr:str, cq_abbr:str, oc_type:str):
    '''
    Get all of the extract detail of a project
    '''
    project = get_project_by_keystr(keystr)

    if project is None:
        # what???
        return None

    extracts = Extract.query.filter(
        Extract.project_id == project.project_id,
        Extract.oc_type == oc_type,
        Extract.meta['cq_abbr'] == cq_abbr
    ).all()

    return extracts


def get_extracts_by_keystr_and_cq_and_oc_type_and_group(
    keystr:str, cq_abbr:str, oc_type:str, group:str):
    '''
    Get all of the extract detail of a project
    '''
    project = get_project_by_keystr(keystr)

    if project is None:
        # what???
        return None

    extracts = Extract.query.filter(
        Extract.project_id == project.project_id,
        Extract.oc_type == oc_type,
        Extract.meta['cq_abbr'] == cq_abbr,
        Extract.meta['group'] == group
    ).all()

    return extracts


def get_itable_by_project_id_and_cq(project_id, cq_abbr):
    '''
    Get the itable of a specific cq in a project
    '''
    extract = Extract.query.filter(
        Extract.project_id == project_id,
        Extract.oc_type == 'itable',
        Extract.meta['cq_abbr'] == cq_abbr
    ).first()
  
    if extract is None:
        return None

    # ok, let's add all pieces for itable as data attachment
    extract = attach_extract_data(extract)

    return extract


def attach_all_extracts_data(extracts, flag_skip_not_selected=True):
    '''
    Simply attach all extracts' data

    Do NOT use this function, too slow.
    '''
    for extract in extracts:
        extract = attach_extract_data(extract, flag_skip_not_selected)

    return extracts


def attach_extract_data(extract, flag_skip_not_selected=True):
    '''
    Attach the data to an extract
    '''
    print("I am being calledddddd")
    print(extract.extract_id)
    pieces = get_pieces_by_project_id_and_extract_id(
        extract.project_id,
        extract.extract_id
    )
    data = {}
    for pc in pieces:
        if flag_skip_not_selected:
            if pc.data['is_selected']:
                data[pc.pid] = pc.data
            else:
                pass
        else:
            data[pc.pid] = pc.data

    extract.data = data
    # print('* attached data to extract[%s]' % (
    #     extract.get_repr_str()
    # ))

    print("data as well", data )
    return extract

def get_attached_extract_data(extract, flag_skip_not_selected=True):
    '''
    Attach the data to an extract
    '''
    
    pieces = get_pieces_by_project_id_and_extract_id(
        extract.project_id,
        extract.extract_id
    )
    data = {}
    for pc in pieces:
        if flag_skip_not_selected:
            if pc.data['is_selected']:
                data[pc.pid] = pc.data
            else:
                pass
        else:
            data[pc.pid] = pc.data

    extract.data = data
    # print('* attached data to extract[%s]' % (
    #     extract.get_repr_str()
    # ))

    
    return data


def unselect_extract_data(extract):
    '''
    Unselect all data of an extract
    '''
    pieces = get_pieces_by_project_id_and_extract_id(
        extract.project_id,
        extract.extract_id
    )
    for pc in pieces:
        pc.data['is_selected'] = False
        flag_modified(pc, 'data')
        db.session.add(pc)

    db.session.commit()
    print("* unselected %s pieces in extract[%s]" % (
        len(pieces),
        extract.meta['full_name']
    ))

    return True


def get_extract(extract_id):
    '''
    Get an extract by its primary key
    '''
    extract = Extract.query.filter(
        Extract.extract_id == extract_id
    ).first()

    return extract


def get_extract_by_project_id_and_cq_and_abbr(project_id, cq_abbr, abbr):
    '''
    Get an extract
    '''
    extract = get_extract_by_project_id_and_abbr(project_id, abbr)

    if extract is None:
        return None

    if extract.meta['cq_abbr'] != cq_abbr:
        return None

    return extract


def get_extract_by_keystr_and_cq_and_abbr(keystr, cq_abbr, abbr):
    '''
    Get an extract by keystr, cq, and abbr
    '''
    # return extract
    project = get_project_by_keystr(keystr)

    if project is None:
        # what???
        return None

    extract = Extract.query.filter(
        Extract.project_id == project.project_id,
        Extract.abbr == abbr,
        Extract.meta['cq_abbr'] == cq_abbr
    ).first()

    return extract


def get_extract_by_project_id_and_abbr(project_id, abbr):
    '''
    Get an extract
    '''
    extract = Extract.query.filter(and_(
        Extract.project_id == project_id,
        Extract.abbr == abbr
    )).first()

    return extract


def get_extract_by_keystr_and_abbr(keystr, abbr):
    '''
    Get an extract by keystr and abbr
    '''
    project = get_project_by_keystr(keystr)

    if project is None:
        # what???
        return None

    # extract = Extract.query.filter(and_(
    #     Extract.project_id == project.project_id,
    #     Extract.abbr == abbr
    # )).first()
    extract = get_extract_by_project_id_and_abbr(
        project.project_id,
        abbr
    )

    return extract


###############################################################################
# Piece Related Functions
###############################################################################

def copy_piece(piece, auto_add=True, auto_commit=True):
    '''
    Create a new piece for an extract in a project
    '''
    # create the id
    piece_id = str(uuid.uuid1())
    date_created = datetime.datetime.now()
    date_updated = datetime.datetime.now()

    new_piece = Piece(
        piece_id = piece_id,
        # copy some values from the given piece
        project_id = piece.project_id,
        extract_id = piece.extract_id,
        pid = piece.pid,
        data = piece.data,
        # just set the new dates
        date_created = date_created,
        date_updated = date_updated
    )

    if auto_add: db.session.add(new_piece)
    if auto_commit: db.session.commit()

    return new_piece


def create_piece(project_id, extract_id, pid, data, auto_add=True, auto_commit=True):
    '''
    Create a new piece for an extract in a project
    '''
    # create the id
    piece_id = str(uuid.uuid1())
    date_created = datetime.datetime.now()
    date_updated = datetime.datetime.now()

    piece = Piece(
        piece_id = piece_id,
        project_id = project_id,
        extract_id = extract_id,
        pid = pid,
        data = data,
        date_created = date_created,
        date_updated = date_updated
    )

    if auto_add: db.session.add(piece)
    if auto_commit: db.session.commit()

    return piece


def create_or_update_pieces_by_extract_data(project_id, extract_id, ext_data):
    '''
    Create or update many pieces for a extract
    '''
    pieces = []
    for pid in ext_data:
        # get the data of this pid
        data = ext_data[pid]

        # try to find this ext
        piece = Piece.query.filter(
            Piece.project_id == project_id,
            Piece.extract_id == extract_id,
            Piece.pid == pid
        ).first()

        if piece == None:
            # ok, this is a new
            piece = create_piece(
                project_id,
                extract_id,
                pid,
                data,
                auto_add=True,
                auto_commit=False
            )
            print('* created new piece for paper: %s' % (
                pid
            ))
        else:
            piece.data = data
            flag_modified(piece, 'data')
            db.session.add(piece)
            print('* updated existing piece for paper: %s' % (
                pid
            ))
        
        pieces.append(piece)

    # then, commit all
    db.session.commit()

    return pieces


def create_or_update_piece(project_id, extract_id, pid, data):
    '''
    Create or update a single piece
    '''
    piece = update_piece(
        project_id,
        extract_id,
        pid,
        data
    )

    if piece is None:
        # this piece doesn't exists
        piece = create_piece(
            project_id,
            extract_id,
            pid,
            data
        )

    return piece


def get_pieces_as_data_by_project_id_and_extract_id(project_id, extract_id):
    '''
    Get pieces as a pid-data object for extract
    '''
    pieces = get_pieces_by_project_id_and_extract_id(project_id, extract_id)
    data = {}
    for p in pieces:
        data[p.pid] = p.data

    return data


def get_pieces_by_project_id_and_extract_id(project_id, extract_id):
    '''
    Get all pieces in an extract of a project
    '''
    pieces = Piece.query.filter(
        Piece.project_id == project_id,
        Piece.extract_id == extract_id
    ).all()

    return pieces


def get_pieces_by_project_id_and_pid(project_id, pid):
    '''
    Get all pieces in a project by the given pid
    '''
    pieces = Piece.query.filter(
        Piece.project_id == project_id,
        Piece.pid == pid
    )
    return pieces


def get_pieces_by_extracts_and_papers(extracts, papers):
    '''
    Get all pieces by given extracts and papers
    '''
    extract_ids = [ _.extract_id for _ in extracts ]
    pids = [ _.pid for _ in papers ]
    pieces = Piece.query.filter(
        Piece.extract_id.in_(extract_ids),
        Piece.pid.in_(pids)
    ).all()
    return pieces


def get_pieces_by_extracts_and_pids(extracts, pids):
    '''
    Get all pieces by given extracts and pids
    '''
    extract_ids = [ _.extract_id for _ in extracts ]
    pieces = Piece.query.filter(
        Piece.extract_id.in_(extract_ids),
        Piece.pid.in_(pids)
    ).all()
    return pieces


def get_piece_by_project_id_and_extract_id_and_pid(project_id, extract_id, pid):
    '''
    Get one piece in an extract of a project
    '''
    piece = Piece.query.filter(
        Piece.project_id == project_id,
        Piece.extract_id == extract_id,
        Piece.pid == pid
    ).first()

    return piece


def update_piece_data_by_id(
    piece_id, 
    data, 
    flag_skip_is_selected=True, 
    auto_add=True, 
    auto_commit=True
):
    '''
    Update one piece in an extract
    '''
    piece = Piece.query.filter(
        Piece.piece_id == piece_id
    ).first()

    if flag_skip_is_selected:
        is_selected = piece.data['is_selected']
        # just update the data
        piece.data = data
        # overwrite
        piece.data['is_selected'] = is_selected
    else:
        piece.data = data

    flag_modified(piece, 'data')

    if auto_add: db.session.add(piece)
    if auto_commit: db.session.commit()

    return piece


def update_piece(project_id, extract_id, pid, data, auto_add=True, auto_commit=True):
    '''
    Update one piece in an extract
    '''
    piece = Piece.query.filter(
        Piece.project_id == project_id,
        Piece.extract_id == extract_id,
        Piece.pid == pid
    ).first()

    if piece == None:
        return None

    # just update the data
    piece.data = data
    flag_modified(piece, 'data')

    if auto_add: db.session.add(piece)
    if auto_commit: db.session.commit()

    return piece


def force_update_piece(piece):
    '''
    Update the given piece
    '''
    flag_modified(piece, 'data')

    db.session.add(piece)
    db.session.commit()

    return piece

def _make_r_nct_based(paper_data, abbr_dict, basic_attrs, paper):
        r = {
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
            if attr['abbr'] == 'ba_nct':
                val = paper.meta['rct_id']
            else:
                val = 'NA'
            r[attr_name] = val
        return r



###############################################################################
# Deprecated
###############################################################################

# def update_extract_incr_data(
#     extract_id, 
#     data, 
#     flag_skip_is_selected=False
# ):
#     '''
#     Deprecated
#     Update the existing extract data by the increamental data

#     The input data should contains the updated part only.
#     The algorithm will also compare the given data with existing data.
#     '''
#     extract = get_extract(extract_id)

#     # TODO check if not exists

#     # update each paper if it is modified
#     flag_changed = False
#     n_changed = 0
#     pid_changed = {
#         'upd': [], 'new': []
#     }
#     n_compared = 0

#     for pid in data:
#         n_compared += 1
#         pid_ext = data[pid]

#         # search for this pid in this extract first
#         if pid in extract.data:
#             # OK, this is an existing paper
#             # let's check each attribute
#             is_same = util.is_same_extraction(
#                 extract.data[pid],
#                 pid_ext,
#                 flag_skip_is_selected
#             )

#             if is_same:
#                 # nice, no need to update this paper
#                 pass
            
#             else:
#                 # hmmm, this paper is updated
#                 # extract.data[pid] = pid_ext

#                 # 2022-12-12: fix the overwrite selection bug
#                 # copy the pid_ext data to extract.data
#                 for key in pid_ext:
#                     if key == 'is_selected' and flag_skip_is_selected:
#                         # skip the is_selected when flags
#                         pass
#                     else:
#                         extract.data[pid][key] = pid_ext[key]

#                 flag_changed = True
#                 n_changed += 1
#                 pid_changed['upd'].append(pid)
            
#         else:
#             # Great, this is a new paper
#             # It's the simplest case, just add this 
#             extract.data[pid] = pid_ext
#             flag_changed = True
#             n_changed += 1
#             pid_changed['new'].append(pid)
    
#     print("* compared %s extractions, %s changed, %s new (%s), %s update (%s)" % (
#         n_compared, n_changed, 
#         len(pid_changed['new']), pid_changed['new'],
#         len(pid_changed['upd']), pid_changed['upd'],
#     ))

#     if flag_changed:
#         extract.date_updated = datetime.datetime.now()
#         flag_modified(extract, "data")

#         # commit this
#         db.session.add(extract)
#         db.session.commit()
#     else:
#         pass

#     return extract



# def update_paper_selection(project_id, pid, abbr, is_selected):
#     '''
#     Update the paper outcome selection in one extract
#     '''
#     # first, get this selection
#     extract = Extract.query.filter(and_(
#         Extract.project_id == project_id,
#         Extract.abbr == abbr
#     )).first()

#     # TODO if it's NONE???

#     if pid in extract.data:
#         db_is_selected = extract.data[pid]['is_selected']
#         # print('* %s in %s (%s vs %s)' % (
#         #     pid, oc_abbr, is_selected, db_is_selected
#         # ))
#         if is_selected == db_is_selected:
#             # OK, no need to change the value
#             pass
#         else:
#             # user changed the option, ok, update
#             extract.data[pid]['is_selected'] = is_selected

#             # add to session
#             flag_modified(extract, "data")
#             db.session.add(extract)
#             db.session.commit()
            
#             print('* found %s in %s is_selected updated to %s' % (
#                 pid, extract.meta['full_name'], is_selected
#             ))

#     else:
#         if is_selected:
#             # well, have to add this pid to this outcome
#             # make an empty extraction
#             # {
#             #     'is_selected': is_selected,
#             #     'is_checked': False,
#             #     'n_arms': 2,
#             #     'attrs': {
#             #         'main': {},
#             #         'other': []
#             #     }
#             # }
#             extract.data[pid] = util.mk_empty_extract_paper_data(is_selected)
#             extract.data[pid]['attrs']['main'] = util.fill_extract_data_arm(
#                 extract.data[pid]['attrs']['main'],
#                 extract.meta['cate_attrs']
#             )
#             flag_modified(extract, "data")
#             db.session.add(extract)
#             db.session.commit()

#             print('* created %s in %s is_selected updated to %s' % (
#                 pid, extract.abbr, is_selected
#             ))
#         else:
#             # since it is not selected, just ignore is fine
#             pass

#     return extract