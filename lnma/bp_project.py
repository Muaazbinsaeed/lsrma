from flask import json, request
from flask import flash
from flask import render_template
from flask import Blueprint
from flask import jsonify
from flask import current_app
from flask import redirect
from flask import url_for

from flask_login import login_required
from flask_login import current_user
from werkzeug.utils import escape

from . import db

from lnma import dora, settings, srv_project, srv_extract, create_app
from lnma.settings import TOXIXITY_ABBR_GROUP

bp = Blueprint("project", __name__, url_prefix="/project")
app = create_app()
logger = app.logger

@bp.route('/')
@login_required
def index():
    return render_template('index.html')

@bp.route('/project_assignment/', methods=['GET', 'POST'])
def project_assignment():
    if request.method == 'GET':
        keystr = request.args.get('project_keystr')
        projects = dora.get_project_by_keystr(keystr)
        all_users = dora.list_all_users()
        assigned_users = []
        project_owner_id =  projects.owner_uid
        for record in projects.related_users:
            if project_owner_id != record.uid:
                assigned_users.append(record.uid)
        unassigned_users = []
        for record in all_users:
            if record.uid not in assigned_users and project_owner_id != record.uid:
                unassigned_users.append(record.uid)
                
        papers = dora.get_papers_by_stage(projects.project_id, "unscreened")
        unscreened_papers = len(papers)

        return render_template('project/project_assignment.html', assigned_users=assigned_users, 
        unassigned_users=unassigned_users, project_obj=projects, clinica_questions=projects.settings['clinical_questions'],
        unscreened_papers=unscreened_papers)

    
    assigned_users = request.form.getlist('assigne_users[]')
    keystr = request.form.get('project_keystr')
    status  = dora.assign_bulk_users_to_users(assigned_users, keystr)
    
    ret = {'success': status,}

    return jsonify(ret)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'GET':
        return render_template('project/create.html')

    query = request.form.get('query')

    project, msg = dora.create_project(
        owner_uid = current_user.uid,
        title = request.form.get('title'),
        keystr = request.form.get('keystr'),
        abstract = request.form.get('abstract'),
        p_settings=None
    )
    if project is None:
        flash('Failed. This project Identifier already exists, please use other Identifier and try again', 'error')
        return redirect(url_for('project.create'))
    else:
        flash('Project is created!')
        return redirect(url_for('project.mylist'))



@bp.route('/mylist', methods=['GET', 'POST'])
@login_required
def mylist():
    logger.info("We are enterting into the logging")
    if request.method == 'GET':
        return render_template(
            'project/list.html'
        )
    projects = dora.list_projects_by_uid(current_user.uid)


@bp.route('/editor')
@login_required
def editor():
    project_id = request.cookies.get('project_id')
    if project_id is None or project_id == '':
        flash('Set working project first')
        return redirect(url_for('project.mylist'))

    project = dora.get_project(project_id)

    # preprocessing the tags
    form_textarea_tags = project.get_tags_text()

    # preprocessing the ie criterias
    form_textarea_inclusion_criterias = project.get_inclusion_criterias_text()

    # preprocessing the ie criterias
    form_textarea_exclusion_criterias = project.get_exclusion_criterias_text()

    # preprocessing the exclusion reasons
    form_textarea_exclusion_reasons = project.get_exclusion_reasons_text()

    # preprocessing the ie keywords
    form_textarea_inclusion_keywords = project.get_inclusion_keywords_text()

    # preprocessing the exclusion keywords
    form_textarea_exclusion_keywords = project.get_exclusion_keywords_text()

    # the pdf keywords
    form_textarea_pdf_keywords = project.get_pdf_keywords_text()

    # the all settings JSON string
    form_textarea_settings = project.get_settings_text()

    return render_template('project/editor.html', 
        project=project,
        form_textarea_tags=form_textarea_tags,
        form_textarea_inclusion_criterias=form_textarea_inclusion_criterias,
        form_textarea_exclusion_criterias=form_textarea_exclusion_criterias,
        form_textarea_exclusion_reasons=form_textarea_exclusion_reasons,
        form_textarea_inclusion_keywords=form_textarea_inclusion_keywords,
        form_textarea_exclusion_keywords=form_textarea_exclusion_keywords,
        form_textarea_pdf_keywords=form_textarea_pdf_keywords,
        form_textarea_settings=form_textarea_settings,
        form_textarea_settings_cqs = project.get_cqs()
    )


@bp.route('/public_website', methods=['GET'])
@login_required
def public_website():
    project_id = request.cookies.get('project_id')
    cq_abbr = request.cookies.get('cq_abbr')

    if project_id is None:
        return redirect(url_for('project.mylist'))

    if cq_abbr is None:
        cq_abbr = 'default'

    project = dora.get_project(project_id)

    return render_template(
        'project/public_website.html',
        cq_abbr=cq_abbr,
        project=project,
        project_json_str=json.dumps(project.as_dict())
    )


@bp.route('/webiste_versioning', methods=['GET', 'POST'])
@login_required
def webiste_versioning():
    if request.method == 'GET':
        project_id = request.cookies.get('project_id')
        cq_abbr = request.cookies.get('cq_abbr')

        if project_id is None:
            return redirect(url_for('project.mylist'))

        if cq_abbr is None:
            cq_abbr = 'default'

        project = dora.get_project(project_id)
        import os
        key_str = project.keystr

        versions_list =[]
        if project.settings.get('website_version'):
            versions = project.settings.get('website_version')
            if versions.get(cq_abbr):
                versions_list = versions.get(cq_abbr)



        return render_template(
            'project/public_site_versions.html',
            cq_abbr=cq_abbr,
            project=project,
            project_json_str=json.dumps(project.as_dict()),

            versions_list= json.dumps(versions_list)

        )


    # Deletion
    if request.method == 'POST' and 'delete_version' in request.form:
        version_to_delete = request.form.get('delete_version')
        project_id = request.cookies.get('project_id')
        cq_abbr = request.cookies.get('cq_abbr') 


        project = dora.get_project(project_id)
        project_settings = project.settings 

        if project_settings.get('website_version'):
            if project_settings.get('website_version').get(cq_abbr):
                list_ = project_settings.get('website_version').get(cq_abbr)
                list_.remove(version_to_delete)

                is_success, project = dora.set_project_settings(
                    project_id, project_settings
                )

                return jsonify({'success': is_success})
       

    
    version_name = request.form.get('versionName')
    project_id = request.cookies.get('project_id')
    cq_abbr = request.cookies.get('cq_abbr')


    if project_id is None:
        return redirect(url_for('project.mylist'))

    if cq_abbr is None:
         ret = {'success': False,}
         return jsonify(ret)

    project = dora.get_project(project_id)
    project_settings = project.settings 
    if project_settings.get('website_version'):
        if project_settings.get('website_version').get(cq_abbr):
            list_ =project_settings.get('website_version').get(cq_abbr)
            list_.append(version_name)
            
            
        else:
            project_settings.get('website_version')[cq_abbr] = [version_name]
            
    else:
        project_settings['website_version'] = {
            cq_abbr: [version_name]
        }
    is_success, project = dora.set_project_settings(
        project_id, project_settings
    )


    import os
    full_path = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        project.keystr, 
        cq_abbr,
    )
    import os
    path = os.path.join(full_path, version_name)
    os.mkdir(path)

    import shutil
    full_destination_path = os.path.join(
        current_app.instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        project.keystr, 
        cq_abbr,
        version_name
    )
    # Get a list of all files in the source directory
    files = [f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))]
    # Copy each file to the destination directory
    for file in files:
        source_path = os.path.join(full_path, file)
        destination_path = os.path.join(full_destination_path, file)
        shutil.copy2(source_path, destination_path)  # Use shutil.copy2 to preserve metadata if needed

    ret = {'success': True,}
    return jsonify(ret)
    
    


    

   

###############################################################
# APIs for project
###############################################################

@bp.route('/api/list')
@login_required
def api_list():
    projects = dora.list_projects_by_uid(current_user.uid)
    print("About to call logs @@@@@@@@@@@@@@@@@@@@@@@@@@@@ ")
    print(logger)
    logger.debug("We are enterting into the logging")

    ret = {
        'success': True,
        'projects': [ project.as_dict() for project in projects ]
    }

    return jsonify(ret)


@bp.route('/api/get_project')
@login_required
def api_get_project():
    projects = dora.list_projects_by_uid(current_user.uid)

    ret = {
        'success': True,
        'projects': [ project.as_dict() for project in projects ]
    }

    return jsonify(ret)


@bp.route('/api/add_user_to_project', methods=['GET', 'POST'])
@login_required
def api_add_user_to_project():
    if request.method == 'GET':
        return redirect(url_for('project.mylist'))

    to_add_uid = request.form.get('uid', None)
    project_id = request.form.get('project_id', None)
    current_user_uid = current_user.uid

    # TODO validate the project is belong to current user

    # add the to_add_uid
    to_add_user, project = dora.add_user_to_project(to_add_uid, project_id)

    # TODO check the result
    
    flash("Added %s to Project [%s]" % (to_add_user.uid, project.title))

    return redirect(url_for('project.mylist'))


@bp.route('/api/api_set_criterias', methods=['GET', 'POST'])
@login_required
def api_set_criterias():
    if request.method == 'GET':
        return redirect(url_for('project_editor'))
        
    project_id = request.cookies.get('project_id')
    if project_id is None or project_id == '':
        flash('Set working project first')
        return redirect(url_for('project.mylist'))

    raw_inclusion_criterias = request.form.get('form_textarea_inclusion_criterias')
    raw_exclusion_criterias = request.form.get('form_textarea_exclusion_criterias')

    # remove blank
    raw_inclusion_criterias = raw_inclusion_criterias.strip()
    raw_exclusion_criterias = raw_exclusion_criterias.strip()

    # update
    is_success, project = dora.set_project_criterias(
        project_id, raw_inclusion_criterias, raw_exclusion_criterias
    )

    flash('Saved inclusion/exclusion criterias!')
    return redirect(url_for('project.editor', _anchor="ie_criteria_info"))


@bp.route('/api/set_exclusion_reasons', methods=['GET', 'POST'])
@login_required
def api_set_exclusion_reasons():
    if request.method == 'GET':
        return redirect(url_for('project_editor'))
        
    project_id = request.cookies.get('project_id')
    if project_id is None or project_id == '':
        flash('Set working project first')
        return redirect(url_for('project.mylist'))

    raw_exclusion_reasons = request.form.get('form_textarea_exclusion_reasons')

    # remove blank
    raw_exclusion_reasons = raw_exclusion_reasons.strip()

    # split
    exclusion_reasons = raw_exclusion_reasons.split('\n')
    
    # remove empty
    exclusion_reasons_cleaned = []
    for t in exclusion_reasons:
        t = t.strip()
        if t == '':
            pass
        else:
            exclusion_reasons_cleaned.append(t)

    # update
    is_success, project = dora.set_project_exclusion_reasons(
        project_id, exclusion_reasons_cleaned
    )

    flash('Saved %s exclusion_reasons!' % (
        len(exclusion_reasons_cleaned),
    ))
    return redirect(url_for('project.editor', _anchor="ex_reason_info"))


@bp.route('/api/set_highlight_keywords', methods=['GET', 'POST'])
@login_required
def api_set_highlight_keywords():
    if request.method == 'GET':
        return redirect(url_for('project_editor'))
        
    project_id = request.cookies.get('project_id')
    if project_id is None or project_id == '':
        flash('Set working project first')
        return redirect(url_for('project.mylist'))

    raw_hk_inc = request.form.get('form_textarea_inclusion_keywords')
    raw_hk_exc = request.form.get('form_textarea_exclusion_keywords')

    # remove blank
    raw_hk_inc = raw_hk_inc.strip()
    raw_hk_exc = raw_hk_exc.strip()

    # split
    hk_incs = raw_hk_inc.split('\n')
    hk_excs = raw_hk_exc.split('\n')

    # remove empty
    hk_incs_cleaned = []
    for hk_inc in hk_incs:
        hk_inc = hk_inc.strip()
        if hk_inc == '':
            pass
        else:
            hk_incs_cleaned.append(hk_inc)
    
    hk_excs_cleaned = []
    for hk_exc in hk_excs:
        hk_exc = hk_exc.strip()
        if hk_exc == '':
            pass
        else:
            hk_excs_cleaned.append(hk_exc)

    highlight_keywords = {
        "inclusion": hk_incs_cleaned,
        "exclusion": hk_excs_cleaned
    }
    # update
    is_success, project = dora.set_project_highlight_keywords(
        project_id, highlight_keywords
    )

    flash('Saved %s + %s highlight_keywords!' % (
        len(highlight_keywords['inclusion']), 
        len(highlight_keywords['exclusion']), 
    ))
    return redirect(url_for('project.editor', _anchor="ie_keywords_info"))


@bp.route('/api/set_tags', methods=['GET', 'POST'])
@login_required
def api_set_tags():
    if request.method == 'GET':
        return redirect(url_for('project_editor'))
        
    project_id = request.cookies.get('project_id')
    if project_id is None or project_id == '':
        flash('Set working project first')
        return redirect(url_for('project.mylist'))

    raw_tags = request.form.get('form_textarea_tags')

    # remove blank
    tags = raw_tags.strip()

    # split
    tags = tags.split('\n')

    # remove empty
    tags_cleaned = []
    for tag in tags:
        tag = tag.strip()
        if tag == '':
            pass
        else:
            tags_cleaned.append(tag)

    # update
    is_success, project = dora.set_project_tags(project_id, tags_cleaned)

    flash('Saved %s tags!' % (len(tags_cleaned)) )
    return redirect(url_for('project.editor', _anchor="tag_info"))



# @bp.route('/api/save_new_cqs', method=['POST'])
# @login_required
# def api_save_new_cqs():

#     project_id = request.cookies.get('project_id')
#     abbr = request.form.get('cq_abbr')
#     name = request.form.get('cq_name')



@bp.route('/api/set_pdf_keywords', methods=['GET', 'POST'])
@login_required
def api_set_pdf_keywords():
    if request.method == 'GET':
        return redirect(url_for('project_editor'))
        
    project_id = request.cookies.get('project_id')
    if project_id is None or project_id == '':
        flash('Set working project first')
        return redirect(url_for('project.mylist'))

    raw_txt = request.form.get('form_textarea_pdf_keywords')

    # remove blank
    lines = raw_txt.strip()

    # split
    keywords = lines.split('\n')

    # remove empty
    keywords_cleaned = []
    for txt in keywords:
        txt = txt.strip()
        if txt == '':
            pass
        else:
            keywords_cleaned.append(txt)

    # update
    is_success, project = dora.set_project_pdf_keywords(project_id, keywords_cleaned)

    flash('Saved %s PDF keywords!' % (len(keywords_cleaned)) )
    return redirect(url_for('project.editor', _anchor="pdf_keywords"))


@bp.route('/api/set_settings', methods=['GET', 'POST'])
@login_required
def api_set_settings():
    '''
    Set the project settings directly

    CAUTION! this function is VERY VERY dangerous.
    Don't use unless you are 120% sure what you are doing.
    '''
    if request.method == 'GET':
        return redirect(url_for('project_editor'))
        
    project_id = request.cookies.get('project_id')
    if project_id is None or project_id == '':
        flash('Set working project first')
        return redirect(url_for('project.mylist'))

    raw_txt = request.form.get('form_textarea_settings')

    # convert to JSON
    try:
        new_prj_settings = json.loads(raw_txt)

    except Exception as err:
        flash('ERROR! Invalid JSON format settings')
        return redirect(url_for('project.editor'))

    # update
    is_success, project = dora.set_project_settings(
        project_id, new_prj_settings
    )

    # then, due to this large update
    # we also need to check and update other things related to setting
    # 1. update the ss_cq based the cq
    # this is based on the decision of 
    srv_project.update_project_papers_ss_cq_by_keystr(
        project.keystr,
        settings.PAPER_SS_EX_SS_CQ_DECISION_NO
    )

    # 2. I'm not sure yet.

    flash('Saved new settings')
    return redirect(url_for('project.editor', _anchor="advanced_mode"))


@bp.route('/add_clinical_question', methods=['POST'])
@login_required
def api_add_clinical_question():


    cq_abbr = request.form.getlist('cq_abbr')[0]
    cq_name = request.form.getlist('cq_name')[0]

    cq_out_group = request.form.getlist('cq_out_group')[0]
    cq_clinical_group = json.loads(request.form.getlist('cq_clinical_group')[0])
    cq_toxicity = request.form.getlist('cq_toxicity')[0]

    project_id = request.cookies.get('project_id')
    project_obj = dora.get_project(project_id)
    outcome_group_exist  = False
    toxicity = 'no'
    for group in cq_clinical_group:
        if cq_toxicity == 'true':
            toxicity = 'yes'
            if project_obj:
                keystr = project_obj.keystr

            ext = srv_extract.copy_extracts(
            'IO', 
            'default',
            'treatment',

            keystr,
            cq_abbr,
            group,

            cq_out_group
        )

    project_id = request.cookies.get('project_id')
    project_obj = dora.get_project(project_id)
    project_settings = project_obj.settings
    cqs = project_settings.get('clinical_questions')
    outcomes = project_settings['outcome'] 
    if (outcomes.get(cq_out_group)):
        outcome_group = outcomes[cq_out_group]['analysis_groups']
        for cq in cq_clinical_group:
            for outcome in outcome_group:
                if outcome['abbr'] == cq:
                    outcome_group_exist = True
            
            if not outcome_group_exist:
                outcome_group.append({'abbr': cq_clinical_group, 'name': TOXIXITY_ABBR_GROUP[cq]})
                project_settings['outcome'][cq_out_group]['analysis_groups'] = outcome_group
    
        cqs.append({'abbr': cq_abbr, 'name': cq_name,'toxicity': toxicity, 'tox_groups': cq_clinical_group, 'parent_group': cq_out_group})
    project_settings['clinical_questions'] = cqs
   
     # update
    is_success, project = dora.set_project_settings(
        project_id, project_settings
    )
    ret = {'success': True,}

    return jsonify(ret)

    # flash('Saved new settings')
    # return redirect(url_for('project.editor', _anchor="clinical_questions"))



@bp.route('/add_cq_rob', methods=['POST'])
@login_required
def api_add_cq_rob():


    project_id = request.form.get('project_id')
    cq_abbr = request.form.get('cq_abbr')

    extract = dora.get_itable_by_project_id_and_cq(
        project_id, 
        cq_abbr
    )
    cq_rob = settings.COE_RCT_ROB
    cq_rob_inc = settings.COE_RCT_IND
    cate_attrs = extract.meta.get('cate_attrs')

    for attr in cate_attrs:
        if (attr.get('abbr')=='COE_RCT_ROB'):
            ret = {'success': True,'msg': 'ROB addded already'}
            return jsonify(ret)
    cate_attrs.append(cq_rob)
    cate_attrs.append(cq_rob_inc)
    extract.meta['cate_attrs'] = cate_attrs

    import datetime
   
    extract.date_updated = datetime.datetime.now()

    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(extract, "meta")

    # commit this
    db.session.add(extract)
    db.session.commit()

    ret = {'success': True,'msg': 'ROB Added Successfully'}
    return jsonify(ret)


@bp.route('/add_cq_toxicity', methods=['POST'])
@login_required
def api_add_cq_toxicity():

    
    project_id = request.form.get('project_id')
    cq_abbr = request.form.get('cq_abbr')
    cq_group = request.form.get('cq_group')
    project_obj = dora.get_project_by_keystr(project_id)
    project_obj = dora.get_project(project_id)
    project_settings = project_obj.settings
    cqs = project_settings['clinical_questions']
    outcomes =project_settings['outcome']
    outcome_group_exist  = False

    if (outcomes.get('pwma')):
        pwma_ = outcomes['pwma']['analysis_groups']
        for outcome in pwma_:
            if outcome['abbr'] == cq_group:
                outcome_group_exist = True
        
        if not outcome_group_exist:
            pwma_.append({'abbr': cq_group, 'name': TOXIXITY_ABBR_GROUP[cq_group]})
            project_settings['outcome']['pwma']['analysis_groups'] = pwma_



    updated_cqs = []
    for cq in cqs:
        if cq['abbr'] == cq_abbr:
            cq['toxicity'] = 'yes'
            if cq.get('tox_groups'):
                cq['tox_groups'].append(cq_group) 
            else:
                cq['tox_groups'] = [cq_group]
        updated_cqs.append(cq)

    project_settings['clinical_questions'] = cqs
   
     # update
    is_success, project = dora.set_project_settings(
        project_id, project_settings
    )
    print(updated_cqs)
        


    
    if project_obj:
        keystr=project_obj.keystr
    ext = srv_extract.copy_extracts(
        'IO', 
        'default',
        'treatment',

        keystr,
        cq_abbr,
        cq_group,

        'pwma'
    )


    ret = {'success': True,'msg': 'Toxicity Added Successfully'}
    return jsonify(ret)

    

