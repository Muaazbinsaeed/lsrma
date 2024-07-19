
from flask import flash
from flask import render_template
from flask import Blueprint
from flask import json, request
from flask import current_app
from flask import redirect
from flask import url_for

from flask_login import login_required
from flask_login import current_user

from lnma import dora, settings, srv_project

bp = Blueprint("usermanagement", __name__, url_prefix="/usermanagement")


@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    return render_template('user_management/user_management.html')

@bp.route('/users', methods=['GET', 'POST'])
@login_required
def users():
     users = dora.list_all_users()
     return render_template('user_management/list.html', users=users)



@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'GET':
        return render_template('user_management/user_management.html')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    password = request.form.get('password')
    is_existed, user = dora.create_user_if_not_exist(
        email, first_name, last_name, password
    )
    users = dora.list_all_users()
    if is_existed:
        flash('User already exsited')
        return render_template('user_management/list.html', users=users)
        
    flash('User Created Successfully')
    return render_template('user_management/list.html', users=users)
