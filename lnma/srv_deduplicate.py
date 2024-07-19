"""
Deduplicate related functions
"""
import os
import json
from datetime import datetime
from tqdm import tqdm

from lnma import settings
from lnma import srv_paper
from lnma import dora
from lnma import util
from lnma import ss_state
from . import db

from flask import current_app
from lnma import celery_app

def get_fn_job(keystr):
    '''
    Get the file name for job description
    '''
    full_fn_job = os.path.join(
        current_app.instance_path, 
        settings.PATH_DEDUPLICATE, 
        keystr,
        'job.json'
    )

    return full_fn_job


def get_fn_rst(keystr):
    '''
    Get the file name for results
    '''
    full_fn_job = os.path.join(
        current_app.instance_path, 
        settings.PATH_DEDUPLICATE, 
        keystr,
        'DUPLICATES.json'
    )

    return full_fn_job


def update_job(keystr, n_papers, n_completed, status='RUNNING'):
    '''
    Update the job status and numbers
    '''
    # load the job
    full_fn_job = get_fn_job(keystr)

    if os.path.exists(full_fn_job):
        pass
    else:
        job = _create_job(keystr, n_papers, status)
        save_job_file(keystr, job)
        
    job = json.load(open(full_fn_job))

    # update number
    job['n_papers'] = n_papers
    job['n_completed'] = n_completed
    job['status'] = status
    job['date_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if status == 'COMPLETED':
        job['date_completed'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # save it
    save_job_file(keystr, job)


def save_job_file(keystr, job):
    '''
    Save the job file
    '''
    # make the folder
    job_path = os.path.join(
        current_app.instance_path, 
        settings.PATH_DEDUPLICATE, 
        keystr
    )
    if os.path.exists(job_path):
        pass
    else:
        os.makedirs(job_path)
        print('* created directory %s' % job_path)

    full_fn_job = get_fn_job(keystr)

    # save it!
    with open(full_fn_job, 'w') as f:
        json.dump(job, f)
    
    return full_fn_job


def save_rst_file(keystr, rst):
    '''
    Save the result file
    '''
    # make the folder
    job_path = os.path.join(
        current_app.instance_path, 
        settings.PATH_DEDUPLICATE, 
        keystr
    )
    if os.path.exists(job_path):
        pass
    else:
        os.makedirs(job_path)
        print('* created directory %s' % job_path)

    full_fn_rst = get_fn_rst(keystr)

    # save it!
    with open(full_fn_rst, 'w') as f:
        json.dump(rst, f, default=str)
    
    return full_fn_rst


def _create_job(keystr, n_papers, status='RUNNING'):
    '''
    Create a job object
    '''
    job = {
        'n_papers': n_papers,
        'n_completed': 0,
        'keystr': keystr,
        'status': status,
        'date_created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'date_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'date_completed': 'TBD',
    }
    return job


def make_job(keystr, n_papers, status='RUNNING'):
    '''
    Make the job
    '''
    # create the job json
    job = _create_job(keystr, n_papers, status)

    # just run the deduplicate task in background
    async_start_deduplicate.delay(keystr)

    # save it
    save_job_file(keystr, job)
    print('* made the deduplicate search job %s' % keystr)
    return job


@celery_app.task()
def async_start_deduplicate(keystr):
    '''
    Get deduplicated papers as a celery task
    '''
    return find_duplicates(keystr)


def find_duplicates(keystr):
    '''
    Get deduplicated papers
    '''
    project = dora.get_project_by_keystr(keystr)
    print('* got the [%s] project information' % keystr)

    papers = dora.get_papers_by_keystr(keystr)
    print('* got %s papers for project [%s]' % (
        len(papers), keystr
    ))

    title_dict = {}
    # for saving duplicates
    for p1_idx, p1 in enumerate(tqdm(papers)):
        p1_title = p1.title.strip().lower()

        if p1_title in title_dict:
            # this title has been duplicated with existing record
            title_dict[p1_title].append(p1)
        else:
            # this title is a new record
            title_dict[p1_title] = [p1]
        
        # update progress
        # if p1_idx % 10 == 0:
            # update_job(keystr, len(papers), p1_idx+1)
    
    print('* parsed %s titles in %s papers for deduplication' % (
        len(title_dict),
        len(papers)
    ))

    # update_job(keystr, len(papers), p1_idx+1, 'COMPLETED')

    # extract the duplicates only
    dup_dict = {}
    stat = {
        "n_both_excluded": 0,
    }
    for title in title_dict:
        if len(title_dict[title]) == 1:
            # which means this is not a duplicate
            pass
        else:
            dup_dict[title] = []
            # update the selection
            for p in title_dict[title]:
                dup_dict[title].append(p.pid)
                
            # and do some quick statistics

    # save the results
    save_rst_file(keystr, {
        'stat': stat,
        'dup_dict': dup_dict
    })

    return dup_dict


def merge_and_exclude_dups(project, pid_to_keep, dup_pids):
    '''
    Keep a single paper and exclude other dups

    dup_pids is a group/list of pids, 
    which is identified by find_duplicates
    '''
    # get all pieces of the pid_to_keep
    pieces_to_keep = dora.get_pieces_by_project_id_and_pid(
        project.project_id,
        pid_to_keep
    )
    # collect all extracts
    p2k_extract_ids = [ _.extract_id for _ in pieces_to_keep ]

    # count
    cnt_copied = 0
    excluded_papers = []

    for pid in dup_pids:
        # skip pid_to_keep itself
        if pid == pid_to_keep: continue

        # get all pieces of this pid
        pieces = dora.get_pieces_by_project_id_and_pid(
            project.project_id,
            pid
        )

        # compare
        for p in pieces:
            if p.extract_id in p2k_extract_ids:
                # ok, this is a conflict, let's just ignore
                pass
            else:
                # ok, this is a new extraction, we need to merge
                new_piece = dora.copy_piece(p, auto_add=False, auto_commit=False)
                # update the pid to the one to be kept
                new_piece.pid = pid_to_keep
                # let's add it here instead of auto-adding
                db.session.add(new_piece)
                print('* copied extraction [%s] for merging %s->%s' % (
                    p.extract_id,
                    p.pid,
                    pid_to_keep
                ))
                cnt_copied += 1

        # commit all added pieces
        db.session.commit()

        # now exclude this paper
        paper = dora.get_paper_by_project_id_and_pid(
            project.project_id,
            pid
        )
        detail_dict = {
            'date_decided': util.get_today_date_str(),
            'reason': 'By deduplication',
            'decision': ss_state.SS_STAGE_EXCLUDED_BY_TITLE
        }

        # update the screening
        paper = dora.set_paper_pr_rs_with_details(
            paper.paper_id, 
            pr=ss_state.SS_PR_PASSED_TITLE, 
            rs=ss_state.SS_RS_EXCLUDED_TITLE,
            detail_dict=detail_dict
        )
        excluded_papers.append(paper)
        print('* excluded paper %s' % (pid))

    print("* copied %s extracted pieces" % (cnt_copied))

    return pid_to_keep, excluded_papers