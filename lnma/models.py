import copy
import enum
import json
import logging
from xml.sax.saxutils import escape

from matplotlib.pyplot import title

from . import db
from . import settings
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

from sqlalchemy.dialects.mysql import LONGTEXT

from lnma import ss_state
from lnma import util
from lnma import settings

# for the relationship between project and user
rel_project_users = db.Table(
    'rel_project_users',
    db.Column('project_id', db.String(48), db.ForeignKey('projects.project_id'), primary_key=True),
    db.Column('uid', db.String(48), db.ForeignKey('users.uid'), primary_key=True)
)


class User(db.Model):
    """
    Data model for users
    """
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}

    uid = db.Column(db.String(64), primary_key=True, nullable=False)
    password = db.Column(db.String(128), index=False)
    first_name = db.Column(db.String(45), index=False)
    last_name = db.Column(db.String(45), index=False)
    role = db.Column(db.String(16), index=False)
    is_deleted = db.Column(db.String(8), index=False)


    # for Flask-login
    def is_authenticated(self):
        return True


    def is_active(self):
        return self.is_deleted == 'no'


    def is_anonymous(self):
        return False


    def get_id(self):
        return self.uid


    # for data API
    def as_dict(self):
        return {
            'uid': self.uid,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'role': self.role
        }


    def get_abbr(self):
        return "%s. %s" % (
            self.first_name[0].upper(), 
            self.last_name.upper()
        )


    def set_password(self, raw_pass):
        self.password = generate_password_hash(raw_pass)


    def __repr__(self):
        return '<User {}>'.format(self.uid)


class Project(db.Model):
    """Data model for projects
    """
    __tablename__ = 'projects'
    __table_args__ = {'extend_existing': True}

    project_id = db.Column(db.String(48), primary_key=True, nullable=False)
    keystr = db.Column(db.String(64), unique=True)
    owner_uid = db.Column(db.String(64), index=False)
    title = db.Column(db.Text, index=False)
    abstract = db.Column(db.Text, index=False)
    date_created = db.Column(db.DateTime, index=False)
    date_updated = db.Column(db.DateTime, index=False)
    settings = db.Column(db.JSON, index=False)
    is_deleted = db.Column(db.String(8), index=False)
    
    # for the users
    related_users = db.relationship('User', secondary=rel_project_users, lazy='subquery',
        backref=db.backref('related_projects', lazy=True))

    # for JSON
    def as_dict(self):
        return {
            'project_id': self.project_id,
            'keystr': self.keystr,
            'owner_uid': self.owner_uid,
            'title': self.title,
            'abstract': self.abstract,
            'date_created': self.date_created.strftime('%Y-%m-%d'),
            'date_updated': self.date_updated.strftime('%Y-%m-%d'),
            'settings': self.settings,
            'related_users': [ u.as_dict() for u in self.related_users ]
        }


    def is_user_in(self, uid):
        for u in self.related_users:
            if u.uid == uid:
                return (True, u)
        return (False, None)


    def get_tags_text(self):
        '''
        Get the tags in plain text format
        '''
        if 'tags' in self.settings:
            txt = '\n'.join(self.settings['tags'])
        else:
            txt = ''

        return txt


    def get_inclusion_criterias_text(self):
        '''
        Get the inclusion criterias in plain text format
        '''
        txt = ''
        if 'criterias' in self.settings:
            if 'inclusion' in self.settings['criterias']:
                txt = self.settings['criterias']['inclusion']
        return txt
        

    def get_exclusion_criterias_text(self):
        '''
        Get the exclusion criterias in plain text format
        '''
        txt = ''
        if 'criterias' in self.settings:
            if 'exclusion' in self.settings['criterias']:
                txt = self.settings['criterias']['exclusion']
        return txt
        

    def get_exclusion_reasons_text(self):
        '''
        Get the exclusion reasons in plain text format
        '''
        txt = ''
        if 'exclusion_reasons' in self.settings:
            txt = '\n'.join(self.settings['exclusion_reasons'])
        return txt


    def get_inclusion_keywords_text(self):
        '''
        Get the inclusion keywords in plain text format
        '''
        txt = ''
        if 'highlight_keywords' in self.settings:
            if 'inclusion' in self.settings['highlight_keywords']:
                txt = '\n'.join(self.settings['highlight_keywords']['inclusion'])
        return txt


    def get_exclusion_keywords_text(self):
        '''
        Get the exclusion keywords in plain text format
        '''
        txt = ''
        if 'highlight_keywords' in self.settings:
            if 'exclusion' in self.settings['highlight_keywords']:
                txt = '\n'.join(self.settings['highlight_keywords']['exclusion'])
        return txt


    def get_pdf_keywords_text(self):
        '''
        Get the PDF keywords in plain text format
        '''
        txt = ''
        if 'pdf_keywords' in self.settings:
            if 'main' in self.settings['pdf_keywords']:
                txt = '\n'.join(self.settings['pdf_keywords']['main'])
        return txt


    def get_settings_text(self):
        '''
        Get all settings as a JSON string
        '''
        txt = json.dumps(self.settings, sort_keys=True, indent=4)
        return txt


    def get_cqs(self):
        '''
        Get clinical questions
        '''
        if 'clinical_questions' not in self.settings:
            return []

        else:
            return self.settings['clinical_questions']

    def get_cq_name(self, cq_abbr):
        '''
        Get the clinical question name by given abbr
        '''
        if 'clinical_questions' not in self.settings:
            return ''

        for cq in self.settings['clinical_questions']:
            if cq['abbr'] == cq_abbr:
                return cq['name']

        return ''


    def __repr__(self):
        return '<Project {0}: {1}>'.format(self.project_id, self.title)


class Paper(db.Model):
    """
    Data model for papers

    The `meta` could contain a lot of things:
    {
        all_rct_ids: Array(1)
        paper: Object
        pdfs: [{
            display_name: '',
            file_id: ''
            folder: ''
        }]
        pred: [{
            is_rct: true
            model: "svm_cnn_ptyp"
            preds: Object
            ptyp_rct: 0
            score: 3.472353767624721
            threshold_type: "balanced"
            threshold_value: 2.1057231048584675
        }]
        rct_id: "NCT01668784"
        rct_seq: 1
        study_type: "followup"
        tags: ['tag',]
        ds_id: {
            pmid: '32145678',
            embase: '201012345678',
            doi: 'abc.om/test/24',
            other: 'ddxxa-234',
            md5: 'xxxx-swww-xxxx-2111'
        }
    }

    The `ss_ex` could also contain a lot:
    {
        label: {
            CKL: { name: 'CKL' }
        },
        date_decided: "2021-03-27",
        decision: "included_sr",
        reason: "Through Abstract",
        ss_cq: {
            default: 'no'
        }
    }
    """
    __tablename__ = 'papers'
    __table_args__ = {'extend_existing': True}

    paper_id = db.Column(db.String(48), primary_key=True, nullable=False)
    pid = db.Column(db.String(settings.PAPER_PID_MAX_LENGTH), index=False)
    pid_type = db.Column(db.Text, index=False)
    seq_num = db.Column(db.Integer, index=False)
    project_id = db.Column(db.String(48), index=False)
    title = db.Column(db.Text, index=False)
    abstract = db.Column(LONGTEXT, index=False)
    pub_date = db.Column(db.String(settings.PAPER_PUB_DATE_MAX_LENGTH), index=False)
    authors = db.Column(db.Text, index=False)
    journal = db.Column(db.Text, index=False)
    meta = db.Column(db.JSON, index=False)
    ss_st = db.Column(db.String(8), index=False)
    ss_pr = db.Column(db.String(8), index=False)
    ss_rs = db.Column(db.String(8), index=False)
    ss_ex = db.Column(db.JSON, index=False)
    date_created = db.Column(db.DateTime, index=False)
    date_updated = db.Column(db.DateTime, index=False)
    is_deleted = db.Column(db.String(8), index=False)


    def get_ss_stages(self):
        '''
        Get the screen status stages of this paper
        '''
        stages = []

        if self.ss_pr == ss_state.SS_PR_NA and \
            self.ss_rs == ss_state.SS_RS_NA:
            stages.append(ss_state.SS_STAGE_UNSCREENED)

        if self.ss_pr != ss_state.SS_PR_NA or \
            self.ss_rs != ss_state.SS_RS_NA:
            stages.append(ss_state.SS_STAGE_DECIDED)

        if self.ss_rs == ss_state.SS_RS_EXCLUDED_TITLE:
            stages.append(ss_state.SS_STAGE_EXCLUDED_BY_TITLE)

        if self.ss_rs == ss_state.SS_RS_EXCLUDED_ABSTRACT:
            stages.append(ss_state.SS_STAGE_EXCLUDED_BY_ABSTRACT)

        if self.ss_rs == ss_state.SS_RS_EXCLUDED_FULLTEXT:
            stages.append(ss_state.SS_STAGE_EXCLUDED_BY_FULLTEXT)

        if self.ss_rs == ss_state.SS_RS_INCLUDED_ONLY_SR:
            stages.append(ss_state.SS_STAGE_INCLUDED_ONLY_SR)
            stages.append(ss_state.SS_STAGE_INCLUDED_SR)

        if self.ss_rs == ss_state.SS_RS_INCLUDED_SRMA:
            stages.append(ss_state.SS_STAGE_INCLUDED_SRMA)
            stages.append(ss_state.SS_STAGE_INCLUDED_SR)

        return stages


    def is_ss_included_in_project(self):
        '''
        Check whether this paper is included in project
        '''
        if self.ss_rs in [
            ss_state.SS_RS_INCLUDED_ONLY_SR,
            ss_state.SS_RS_INCLUDED_ONLY_MA,
            ss_state.SS_RS_INCLUDED_SRMA
        ]:
            return True

        else:
            return False


    def is_ss_included_in_cq(self, cq_abbr):
        '''
        Check whether this paper is included in a cq
        '''
        if 'ss_cq' not in self.ss_ex:
            return False
        
        if cq_abbr not in self.ss_ex['ss_cq']:
            return False
        
        if self.ss_ex['ss_cq'][cq_abbr]['d'] != 'yes':
            return False

        return True


    def is_ss_included_in_project_and_cq(self, cq_abbr):
        '''
        Check whether this paper is included in a project and a cq
        '''
        if self.is_ss_included_in_project() and self.is_ss_included_in_cq(cq_abbr):
            return True
        else:
            return False


    def get_rct_id(self):
        '''
        Get the RCT ID (NCT) or other number
        '''
        if 'rct_id' in self.meta:
            return self.meta['rct_id']
        else:
            return ''


    def get_study_type(self):
        '''
        Get the study type (original / follow-up)
        '''
        if 'study_type' in self.meta:
            return self.meta['study_type']
        else:
            return ''


    def get_short_name(self, style=None):
        '''
        Get a short name for this study

        For example,

        He et al 2021
        Huan He et al 2021

        '''
        year = util.get_year(self.pub_date)
        fau_etal = util.get_author_etal_from_authors(self.authors)

        return '%s %s' % (fau_etal, year)


    def get_year(self):
        '''
        Get the year from this record
        '''
        return util.get_year(self.pub_date)


    def update_ss_cq_ds(self, cqs):
        '''
        Update the ss_cq data structure in the ss_ex without changing decision
        
        This attiribute is used only for those included studies.

        cqs: [{
            abbr: 'default',
            name: 'Long name'
        }, ...]
        '''
        if self.is_ss_included_in_project():
            # ok, let's check the cq
            if 'ss_cq' in self.ss_ex:
                pass
            else:
                self.ss_ex['ss_cq'] = {}

            # set a flag for this changing
            is_changed = False

            for cq in cqs:
                if cq['abbr'] in self.ss_ex['ss_cq']:
                    # update the format
                    if (type(self.ss_ex['ss_cq'][cq['abbr']]) == str):
                        # oh, it's not the format we need now
                        # str format yes/no is the old format for cq
                        # we need a dict format to put more information
                        self.ss_ex['ss_cq'][cq['abbr']] = util.make_ss_cq_decision(
                            self.ss_ex['ss_cq'][cq['abbr']],
                            settings.SCREENER_DEFAULT_REASON_FOR_CQ_INCLUSION,
                            'no'
                        )
                        is_changed = True
                        
                    else:
                        # great! we already have this cq set in dict format
                        # 2022-02-04: just update the decision
                        pass

                else:
                    # nice! just add this lovely new cq
                    self.ss_ex['ss_cq'][cq['abbr']] = util.make_ss_cq_decision(
                        settings.SCREENER_DEFAULT_DECISION_FOR_CQ_INCLUSION,
                        settings.SCREENER_DEFAULT_REASON_FOR_CQ_INCLUSION,
                        'yes'
                    )
                    is_changed = True

            return is_changed, 'Updated'

        else:
            # ok, this study is not included in SR
            # so ... no need to add this ss_cq
            return False, 'Not included in this project'

    
    def update_ss_cq_by_cqs(self, cqs, 
        decision=settings.SCREENER_DEFAULT_DECISION_FOR_CQ_INCLUSION,
        reason=settings.SCREENER_DEFAULT_REASON_FOR_CQ_INCLUSION):
        '''
        Update the ss_cq in the ss_ex

        This attiribute is used only for those included studies.

        cqs: [{
            abbr: 'default',
            name: 'Long name'
        }, ...]
        '''
        if self.is_ss_included_in_project():
            # ok, let's check the cq
            if 'ss_cq' in self.ss_ex:
                pass
            else:
                self.ss_ex['ss_cq'] = {}
            
            # check each cq
            # if len(cqs) == 1:
            #     # if there is only one cq, just set to yes
            #     ss_cq_decision = util.make_ss_cq_decision(
            #         decision,
            #         reason,
            #         'yes'
            #     )

            for cq in cqs:
                if cq['abbr'] in self.ss_ex['ss_cq']:
                    # update the format
                    if (type(self.ss_ex['ss_cq'][cq['abbr']]) == str):
                        # oh, it's not the format we need now
                        # str format yes/no is the old format for cq
                        # we need a dict format to put more information
                        self.ss_ex['ss_cq'][cq['abbr']] = util.make_ss_cq_decision(
                            self.ss_ex['ss_cq'][cq['abbr']],
                            reason,
                            'no'
                        )
                    else:
                        # great! we already have this cq set in dict format
                        # 2022-01-05: just update the decision
                        self.ss_ex['ss_cq'][cq['abbr']] = util.make_ss_cq_decision(
                            decision,
                            reason,
                            'yes'
                        )

                        # if 'c' in self.ss_ex['ss_cq'][cq['abbr']]:
                        # else:
                            # self.ss_ex['ss_cq'][cq['abbr']]['c'] = 'no'
                else:
                    # nice! just add this lovely new cq
                    self.ss_ex['ss_cq'][cq['abbr']] = util.make_ss_cq_decision(
                        decision,
                        reason,
                        'yes'
                    )

            return True, 'Updated'

        else:
            # ok, this study is not included in SR
            # so ... no need to add this ss_cq
            return False, 'Not included in this project'

        # ok, that's all

    
    def update_meta_ds_id_by_self(self, force_update=False):
        '''
        Update the meta's ds_id
        '''
        ds_name = util.get_ds_name_by_pid_and_type(self.pid, self.pid_type)

        if 'ds_id' in self.meta:
            if ds_name in self.meta['ds_id']:
                if force_update:
                    # which means current pid is not added as ds_id???
                    self.meta['ds_id'][ds_name] = self.pid
                    return True
                else:
                    return False
            else:
                self.meta['ds_id'][ds_name] = self.pid
                return True
        else:
            # which means this paper needs to be updated!
            self.meta['ds_id'] = {
                ds_name: self.pid
            }
            return True
            

    def get_simple_pid_type(self):
        '''
        Get the simple pid type
        '''
        pid_type = self.pid_type.upper()

        if 'MEDLINE' in pid_type or \
            'PMID' in pid_type or \
            'NLM' in pid_type or \
            'PUBMED' in pid_type:
            return 'PUBMED'

        if 'EMBASE' in pid_type:
            return 'EMBASE'

        return pid_type

    
    def is_pmid(self):
        '''
        Get the flag of is pmid

        We could use pmid for a lot of things
        '''
        pid_type = self.pid_type.upper()

        if 'MEDLINE' in pid_type or \
            'PMID' in pid_type or \
            'NLM' in pid_type or \
            'PUBMED' in pid_type:

            return True
            
        elif 'EMBASE' in pid_type:
            return False
        
        elif 'ABSTRACT' in pid_type:
            return False
        
        else:
            # sometimes, we don't know ...
            if util.is_valid_pmid(self.pid):
                return True
            else:
                return False
        

    def as_dict(self):
        # convert all basic attributes
        ret = {c.name: getattr(self, c.name) for c in self.__table__.columns}

        # add other values that not directly converted
        ret['is_pmid'] = self.is_pmid()
        ret['year'] = self.get_year()
        ret['rct_id'] = self.get_rct_id()
        ret['short_name'] = self.get_short_name()
        ret['study_type'] = self.get_study_type()

        return ret

    
    def as_simple_dict(self):
        '''
        Return the simple data of this paper

        Reduce the object size
        '''
        full_dict = self.as_dict()
        if 'paper' in full_dict['meta']:
            del full_dict['meta']['paper']

        if 'pred' in full_dict['meta']:
            is_rct = full_dict['meta']['pred'][0]['is_rct']
            usr_fb = full_dict['meta']['pred'][0].get('usr_fb', '')
            
            # remove other values, just keep the is_rct
            full_dict['meta']['pred'][0] = {
                'is_rct': is_rct,
                'usr_fb': usr_fb
            }

        # remove the abstract to reduce file size
        # this require the frontend to reload this paper information
        # full_dict['abstract'] = ''

        return full_dict

    
    def as_quite_simple_dict(self):
        '''
        Return the very very simple data of this paper
        '''
        d = self.as_simple_dict()
        del d['paper_id']
        del d['pid_type']
        del d['date_updated']

        # delete those for import information
        if 'xml' in d['meta']: del d['meta']['xml']
        if 'raw_type' in d['meta']: del d['meta']['raw_type']

        return d


    def as_very_simple_dict(self):
        '''
        Return the simple data of this paper

        Reduce the object size by remove the abstract
        '''
        simple_dict = self.as_simple_dict()
        simple_dict['abstract'] = ''
        simple_dict['authors'] = ''
        simple_dict['date_created'] = self.date_created.strftime('%Y-%m-%d')
        simple_dict['pid_type'] = self.get_simple_pid_type()

        # delete those for import information
        if 'xml' in simple_dict['meta']: del simple_dict['meta']['xml']
        if 'raw_type' in simple_dict['meta']: del simple_dict['meta']['raw_type']
        
        del simple_dict['is_deleted']
        del simple_dict['project_id']

        return simple_dict

    def as_extreme_simple_dict(self):
        '''
        Return an extreme simple dict for small file size
        '''
        d = dict(
            pid = self.pid,
            pid_type = self.pid_type,
            title = self.title,
            is_pmid = self.is_pmid(),
            year = self.get_year(),
            rct_id = self.get_rct_id(),
            short_name = self.get_short_name(),
            study_type = self.get_study_type(),
            journal = self.journal,
            pub_date = self.pub_date
        )
        return d


    def as_endnote_xml(self):
        '''
        Return the EndNote XML format fragment
        '''
        if 'raw_type' in self.meta and self.meta['raw_type'] == 'endnote_xml':
            # this paper is imported by endnote
            return self.meta['xml']
            
        author_list = self.authors.split(',')
        xml = """
<record>
    <database name="EndNote_Export.enl">EndNote_Export.enl</database>
    <source-app name="EndNote" version="19.3">EndNote</source-app>
    <contributors>
        <authors>
        {contributors}
        </authors>
    </contributors>
    <dates>
        <year>
            <style face="normal" font="default" size="100%">{year}</style>
        </year>
    </dates>
    <periodical>
        <full-title>
            <style face="normal" font="default" size="100%">{journal}</style>
        </full-title>
    </periodical>
    <accession-num>
        <style face="normal" font="default" size="100%">{accession_num}</style>
    </accession-num>
    <titles>
        <title>
            <style face="normal" font="default" size="100%">{title}</style>
        </title>
    </titles>
    <abstract>
        <style face="normal" font="default" size="100%">{abstract}</style>
    </abstract>
</record>
        """.format(
            contributors= "\n".join([ '<author>%s</author>' % escape(au) for au in author_list ]),
            accession_num=self.pid,
            title=escape(self.title),
            abstract=escape(self.abstract),
            year=escape(self.pub_date),
            journal=escape(self.journal)
        )
        return xml


    def as_ovid_xml(self):
        '''
        Return the OVID XML format fragment
        '''
        author_list = self.authors.split(',')
        xml = """
<record>
    <F C="UI" L="Unique Identifier">
        <D type="c">{UI}</D>
    </F>
    <F C="TI" L="Title">
        <D type="c">{TI}</D>
    </F>
    <F C="SO" L="Source">
        <D type="c">{SO}</D>
    </F>
    <F C="VI" L="Version ID">
        <D type="c">{VI}</D>
    </F>
    <F C="ST" L="Status">
        <D type="c">{ST}</D>
    </F>
    <F C="AU" L="Authors">
        {AU}
    </F>
    <F C="AB" L="Abstract">
        <D type="c">{AB}</D>
    </F>
    <F C="YR" L="Year of Publication">
        <D type="c">{YR}</D>
    </F>
</record>
        """.format(
            UI=self.pid,
            TI=escape(self.title),
            SO=escape(self.journal),
            VI=1,
            ST=escape(self.pid_type),
            AU="\n".join([ '<D type="s">%s</D>' % escape(au) for au in author_list ]),
            AB=escape(self.abstract),
            YR=escape(self.pub_date)
        )

        return xml


    def from_pubmed_record(self, pubmed_record):
        '''
        Update this item from a pubmed record
        '''
        self.title = pubmed_record['title']
        self.abstract = pubmed_record['abstract']
        self.pub_date = pubmed_record['sortpubdate']
        self.authors = ', '.join([ a['name'] for a in pubmed_record['authors'] ])
        self.journal = pubmed_record['source']


    def from_doi_record(self, doi_record):
        '''
        Update this item from a DOI parsing result
        '''
        self.title = doi_record['title']
        self.abstract = doi_record['abstract']
        self.pub_date = doi_record['pub_date']
        self.authors = doi_record['authors']
        self.journal = doi_record['journal']


    def get_date_created_in_date(self):
        '''
        Get the YYYY-MM-DD format date_created
        '''
        return self.date_created.strftime('%Y-%m-%d')


    def get_date_updated_in_date(self):
        '''
        Get the YYYY-MM-DD format date_updated
        '''
        return self.date_updated.strftime('%Y-%m-%d')


    def __repr__(self):
        return '<Paper {0}: {1} {2}>'.format(self.paper_id, self.pub_date, self.title)


class Note(db.Model):
    """Data model for notes
    """
    __tablename__ = 'notes'
    __table_args__ = {'extend_existing': True}

    note_id = db.Column(db.String(48), primary_key=True, nullable=False)
    paper_id = db.Column(db.String(48), index=False)
    project_id = db.Column(db.String(48), index=False)
    data = db.Column(db.JSON, index=False)
    date_created = db.Column(db.DateTime, index=False)
    date_updated = db.Column(db.DateTime, index=False)
    is_deleted = db.Column(db.String(8), index=False)

    def __repr__(self):
        return '<Note {0}: {1}>'.format(self.note_id, self.date_created)


class DataSource(db.Model):
    """
    Data source for the studies, such as email, xml, and pmid list
    """
    __tablename__ = 'datasources'
    __table_args__ = {'extend_existing': True}

    datasource_id = db.Column(db.String(48), primary_key=True, nullable=False)
    ds_type = db.Column(db.String(48), index=False)
    title = db.Column(db.Text, index=False)
    content = db.Column(LONGTEXT, index=False)
    date_created = db.Column(db.DateTime, index=False)

    def __repr__(self):
        return '<DataSource {0}: {1}>'.format(self.ds_type, self.title)


class Extract(db.Model):
    """
    The product details extracted by user

    The extraction contains the information related to an outcome (or AE).
    The oc_type currently have the following:

    - pwma
    - subg
    - nma
    - itable

    For each oc_type, the meta content would be different accordingly.

    For the `pwma` type, the `meta` includes:
    {
        "abbr": '',

        # The five level
        "cq_abbr": 'default',
        "oc_type": 'pwma',
        "group": 'primary',
        "category": 'default',
        "full_name": 'pwma outcome full name',

        # for two arms
        "treatments": ["A", "B"],

        # for subg
        "is_subg_analysis": 'no',
        "sub_groups": ['A'],

        # for the display
        "included_in_plots": 'no',
        "included_in_sof": 'no',

        # for the MA
        "input_format": 'PRIM_CAT_RAW',
        "measure_of_effect": 'RR',
        "fixed_or_random": 'random',
        "which_is_better": 'lower',

        "pooling_method": "Inverse",
        "tau_estimation_method": "DL",
        "hakn_adjustment": "FALSE",
        "smd_estimation_method": "Hedges",
        "prediction_interval": "FALSE",
        "sensitivity_analysis": "no",
        "cumulative_meta_analysis": "no",
        "cumulative_meta_analysis_sortby": "year",

        # for the extraction
        "attrs": None,
        "cate_attrs": None

        # for NMA only
        "cetable": {}
    }

    Some attributes are designed for the public site only.
    More information would be added in the future.


    As the extraction is becoming more complex, 
    it is very possible that N users is working on a same extraction.
    So the extracted data may be overwrite
    As a result, the following will be deprecated due to significant conflict.

    The `data` attribute contains all the extraction results.
    It's a pid based (e.g., PMID) dictionary.
    {
        pid: {
            is_selected: true / false,
            is_checked: true / false,
            n_arms: 2 / 3 / 4 / 5,
            attrs: {
                main: {
                    g0: {  # the 0 is the default group
                        attr_sub_abbr: value
                    },
                    g1: {  # the 1 and others are other sub groups

                    }
                },
                other: [{
                    g0: {
                        attr_sub_abbr: value
                    },
                    g1: {

                    }
                }, ...]
            }
        }
    }
    """
    
    __tablename__ = 'extracts'
    __table_args__ = {'extend_existing': True}

    extract_id = db.Column(db.String(48), primary_key=True, nullable=False)
    project_id = db.Column(db.String(48), index=False)
    oc_type = db.Column(db.String(48), index=False)
    abbr = db.Column(db.String(48), index=False)
    meta = db.Column(db.JSON, index=False)
    data = db.Column(db.JSON, index=False)
    date_created = db.Column(db.DateTime, index=False)
    date_updated = db.Column(db.DateTime, index=False)


    def update_meta(self):
        '''
        Update / validate the meta according to default template by oc_type

        Fix the missing attributes in desing
        '''
        meta_template = settings.OC_TYPE_TPL[self.oc_type]['default']

        for attr_name in meta_template:
            if attr_name not in self.meta:
                self.meta[attr_name] = meta_template[attr_name]
                print(f'* fixed missing attr[{attr_name}] in meta')
        
        # 2021-12-22: fix the cate_attr missing in meta
        if self.meta['cate_attrs'] is None:
            self.meta['cate_attrs'] = copy.deepcopy(
                settings.INPUT_FORMAT_TPL[self.oc_type][self.meta['input_format']]
            )

        # 2023-01-10: fix the coe bug


    def update_meta_by_other_meta(self, other_meta):
        '''
        Update meta by other meta
        '''
        for key in other_meta:
            self.meta[key] = other_meta[key]


    def update_data(self):
        '''
        Double check the current extract with its meta data
        '''
        pids = set([])

        # for pid in self.data:

    
    def update_data_by_pieces(self, pieces):
        '''
        Update the current extract with extracted pieces
        '''
        for pc in pieces:
            self.data[pc.pid] = pc.data


    def update_data_by_papers(self, papers):
        '''
        Deprecated ... I think
        Extend the current extract with more papers
        according to the given papers.
        And also update existing papers according the extract meta
        '''
        # merge the return obj
        # make a ref in the extract for frontend display
        # make sure every selected paper is listed in extract.data
        pids = set([])
        for paper in papers:
            pid = paper.pid
            # record this pid for next step
            pids.add(pid)

            # check if this pid exists in extract
            if pid in self.data:
                # nothing to do if has added
                # 2021-07-12: fix the sub group update
                # for those already existsed, the subgroup may updated
                for g_idx, g in enumerate(self.meta['sub_groups']):
                    # check the main
                    self.data[pid]['attrs']['main'] = util.fill_extract_data_arm(
                        self.data[pid]['attrs']['main'],
                        self.meta['cate_attrs'],
                        g_idx
                    )
                    # check the other arms
                    for idx in range(len(self.data[pid]['attrs']['other'])):
                        self.data[pid]['attrs']['other'][idx] = util.fill_extract_data_arm(
                            self.data[pid]['attrs']['other'][idx],
                            self.meta['cate_attrs'],
                            g_idx
                        )
                # after update the meta, we could skip this paper
                continue

            print('* NOT FOUND pid[%s] in this extract[%s]' % (
                pid,
                self.abbr
            ))
            # if not exist, add this paper
            self.data[pid] = copy.deepcopy(settings.DEFAULT_EXTRACT_DATA_PID_TPL)

            # fill the main track with empty values
            for g_idx, g in enumerate(self.meta['sub_groups']):
                self.data[pid]['attrs']['main'] = util.fill_extract_data_arm(
                    self.data[pid]['attrs']['main'],
                    self.meta['cate_attrs'],
                    g_idx
                )

        # reverse search, unselect those are not in papers
        for pid in self.data:
            if pid in pids:
                # which means this pid is in the SR stage
                continue

            # if not, just unselect this paper
            # don't delete
            self.data[pid]['selected'] = False

        # in fact, we don't need to return much things
        return pids


    def get_n_selected(self):
        '''
        Get the number of selected papers
        '''
        n = 0
        for pid in self.data:
            if self.data[pid]['is_selected']:
                n += 1

        if 'updated_selected_papers' in self.meta:
            n = len(self.meta['updated_selected_papers'])

        return n

    
    def get_pids_selected(self):
        '''
        Get the pids of the selected papers
        '''
        pids = []
        for pid in self.data:
            if self.data[pid]['is_selected']:
                pids.append(pid)

        return pids

    
    def get_short_title(self):
        '''
        Get a short title for this extract
        '''
        return self.meta['full_name']


    def as_dict(self):
        '''
        Return the dict format of this extract
        '''
        ret = {c.name: getattr(self, c.name) for c in self.__table__.columns}

        # add how many selected
        ret['n_selected'] = self.get_n_selected()

        # add the survival_in_control
        ret['survival_in_control'] = self.get_survival_in_control()

        # add the internal_val
        ret['internal_val'] = self.get_internal_val()
        ret['has_internal_val'] = ret['internal_val'] != 0

        # add the data_type
        ret['data_type'] = self.get_data_type()

        # add the certainty
        ret['certainty'] = self.get_certainty()

        # patch the certainty
        if 'certainty' not in self.meta:
            self.meta['certainty'] = self.get_certainty()

        # add/set the coe
        ret['coe'] = self.get_coe()

        return ret


    def as_simple_dict(self):
        '''
        Return the simple data of this extract

        Reduce the object size
        '''
        full_dict = self.as_dict()

        for attr in ['data']:
            if attr in full_dict:
                del full_dict[attr]

        return full_dict


    def as_very_simple_dict(self):
        '''
        Return the very simple format
        '''
        simple_dict = self.as_simple_dict()

        if 'cate_attrs' in simple_dict['meta']:
            del simple_dict['meta']['cate_attrs']

        return simple_dict

    
    #######################################################
    # For analyzer purpose
    #######################################################

    def get_survival_in_control(self):
        '''
        Get the survival_in_control for this extract.
        
        The survival_in_control depends on the input format.
        For different type (e.g., raw, pre), the calculation is different
        '''

        if self.get_data_type() == 'raw':
            return 0

        # for pre data
        survival_in_control = 0
        if self.oc_type == 'pwma':

            # there must be a column 'survival_in_control'
            survival_in_controls = []
            for pid in self.data:
                ext = self.data[pid]

                if not ext['is_selected']:
                    continue

                # now check the main arm
                try:
                    _srvc = float(ext['attrs']['main']['g0']['survival_in_control'])
                except:
                    _srvc = None

                if _srvc is None:
                    # some thing wrong with the value
                    pass
                else:
                    survival_in_controls.append(_srvc)

                # now check other arms

            if len(survival_in_controls) > 0:
                survival_in_control = sum(survival_in_controls) / len(survival_in_controls)
            else:
                pass

        elif self.oc_type == 'nma':
            pass

        return survival_in_control


    def get_internal_val(self):
        '''
        Get the internal_val for this extract
        '''
        internal_val = None

        if self.oc_type == 'pwma':
            if self.get_data_type() == 'pre':
                Ec = 0
                Et = 0

                for pid in self.data:
                    ext = self.data[pid]
                    if not ext['is_selected']:
                        continue

                  

                    # check all arms
                    for arm in [ext['attrs']['main']] + ext['attrs']['other']:
                        try:
                            # Ec += util.val2int(arm['g0']['Ec']) * 1000 / util.val2int(arm['g0']['Et'])
                            # Et += 1000
                            Ec += util.val2int(arm['g0']['Ec'])  
                            Et += util.val2int(arm['g0']['Et'])

                        except:
                            pass

                if Ec != 0:
                    internal_val = int(
                        1000 * Ec / Et
                    )

            elif self.get_data_type() == 'raw':
                # check each study
                for pid in self.data:
                    ext = self.data[pid]
                    if not ext['is_selected']:
                        continue

                    Ec = 0
                    Et = 0

                    # check all arms
                    for arm in [ext['attrs']['main']] + ext['attrs']['other']:
                        try:
                            Ec += util.val2int(arm['g0']['Ec']) * 1000 / util.val2int(arm['g0']['Et'])
                            Et += 1000
                        except:
                            pass

                    if Ec != 0:
                        internal_val = int(
                            1000 * Ec / Et
                        )

        return internal_val

    
    def get_data_type(self):
        '''
        Get the data type

        This is a simple flag for input_format
        Usually we don't need to have a complete input_format
        '''
        if 'RAW' in self.meta['input_format']:
            return 'raw'

        if 'PRE' in self.meta['input_format']:
            return 'pre'

        return 'raw'


    def get_certainty(self):
        '''
        Get certainty of evidence 

        This could be done automatically
        But if not available, this will return a default value
        '''
        if 'certainty' in self.meta:
            return self.meta['certainty']

        if self.oc_type == 'pwma':
            ret = copy.deepcopy(settings.OC_TYPE_TPL['pwma']['default']['certainty'])

        elif self.oc_type == 'nma':
            ret = copy.deepcopy(settings.OC_TYPE_TPL['pwma']['default']['certainty'])

        else:
            # not need for itable in fact
            ret = copy.deepcopy(settings.OC_TYPE_TPL['pwma']['default']['certainty'])
            
        return ret


    def get_coe(self):
        '''
        Get certainty of evidence for evaluation
        '''
        # first, check if coe is added to meta
        if 'coe' not in self.meta:
            # just copy the default coe to 
            self.meta['coe'] = copy.deepcopy(settings.OC_TYPE_TPL[self.oc_type]['default']['coe'])

        if self.oc_type == 'pwma':
            # for IO data type, need to update the coe
            if self.meta['input_format'] == "PRIM_CAT_RAW_G5":
                # check the coe cate
                for coe_cate_key in settings.COE_CATE_KEYS_BY_INPUT_FORMAT[self.meta['input_format']]:
                    if coe_cate_key in self.meta['coe']:
                        # ok, this cate has been added or updated
                        pass
                    else:
                        # oh, this coe cate is not there, need to be updated
                        # just copy the information for setting's default coe
                        # but a potential issue is, it's not a good practice
                        # to update the meta info here.
                        self.meta['coe'][coe_cate_key] = copy.deepcopy(settings.OC_TYPE_TPL['pwma']['default']['coe']['main'])
                        # print('* added the cate_key [%s] in meta.coe for oc [%s]' % (
                        #     coe_cate_key,
                        #     self.abbr
                        # ))

        elif self.oc_type == 'nma':
            # at present, no further update on the NMA
            pass

        else:
            # not need for itable in fact
            pass
            
        # finally, just set this coe as the return obj
        ret = self.meta['coe']

        return ret
        

    def get_treatments_in_data(self):
        '''
        Get available treatments
        '''
        if self.oc_type != 'nma':
            return None

        treatments = []
        for pid in self.data:
            ext = self.data[pid]
            if not ext['is_selected']:
                continue

            # check all arms
            for arm in [ext['attrs']['main']] + ext['attrs']['other']:
                try:
                    # no matter pre or raw format
                    # there always be t1 and t2
                    t1 = arm['g0']['t1'].strip()
                    t2 = arm['g0']['t2'].strip()

                    if t1 not in treatments: treatments.append(t1)
                    if t2 not in treatments: treatments.append(t2)

                except:
                    pass

        treatments.sort()

        return treatments


    def get_nma_trtable(self):
        '''
        Get treat table for details in this extract
        '''
        treatments = self.get_treatments_in_data()
        data_type = self.get_data_type()

        # build treatment table
        trtable = {}

        for pid in self.data:
            ext = self.data[pid]
            if not ext['is_selected']:
                continue

            # check all arms
            for record in [ext['attrs']['main']] + ext['attrs']['other']:
                arm = record['g0']
                # no matter pre or raw format
                # there always be t1 and t2
                for tx in ['t1', 't2']:
                    treat_name = arm[tx].strip()

                    if data_type == 'raw':
                
                        if treat_name not in trtable:
                            trtable[treat_name] = {
                                "n_stus": 0,
                                "event": 0,
                                "total": 0,
                                'internal_val_ec': 0,
                                'internal_val_et': 0,
                                'has_internal_val': True,
                                'has_survival_data': False,
                                'survival_in_control': 0
                            }
                        
                        # update the numbers of this treatment
                        trtable[treat_name]['n_stus'] += 1
                        try:
                            trtable[treat_name]['event'] += int(arm['event_'+tx])
                            trtable[treat_name]['total'] += int(arm['total_'+tx])
                        except Exception as err:
                            logging.warning(err)

                        trtable[treat_name]['internal_val_ec'] += trtable[treat_name]['event']
                        trtable[treat_name]['internal_val_et'] += trtable[treat_name]['total']

                    elif data_type == 'pre':
                        if treat_name not in trtable:
                            # ok, this treatment doesn't exist yet
                            trtable[treat_name] = {
                                'n_stus': 0,
                                'internal_val_ec': 0,
                                'internal_val_et': 0,
                                'has_internal_val': False,
                                'has_survival_data': False,
                                'survival_in_control': 0,
                            }

                        # update the numbers of this treatment
                        trtable[treat_name]['n_stus'] += 1

                        # try to add survival
                        try:
                            _srvc = float(arm['survival_'+tx])
                        except Exception as err:
                            _srvc = None
                            # logging.warning(err)

                        if _srvc is None:
                            pass
                        else:
                            trtable[treat_name]['survival_in_control'] += _srvc
                            trtable[treat_name]['has_survival_data'] = True
                    
                        # try to add internal
                        try: 
                            trtable[treat_name]['internal_val_ec'] += \
                                float(arm['Ec_'+tx]) * 1000 / float(arm['Et_'+tx])
                            trtable[treat_name]['internal_val_et'] += 1000
                        except Exception as err:
                            logging.warning(err)

                    else:
                        # what???
                        pass

        # ok, get the survival_in_control
        for treat_name in trtable:
            # final check the has_survival_data flag
            trtable[treat_name]['has_survival_data'] = trtable[treat_name]['survival_in_control'] != 0

            # update the survival in control
            trtable[treat_name]['survival_in_control'] = trtable[treat_name]['survival_in_control'] / trtable[treat_name]['n_stus']

            # update the external base data
            trtable[treat_name]['has_internal_val'] = trtable[treat_name]['internal_val_et'] != 0
            if trtable[treat_name]['has_internal_val']:
                trtable[treat_name]['internal_val'] = int(1000 * trtable[treat_name]['internal_val_ec'] / trtable[treat_name]['internal_val_et'])
            else:
                trtable[treat_name]['internal_val'] = 100

        return trtable


    def get_raw_rs_cfg(self, paper_dict, is_skip_unselected=True):
        '''
        Get the raw result set (rs) and configuration (cfg)
        from this extract.

        Due the incomplete data in the extract, 
        the `study` and `year` information for each record 
        is not available. 

        So for the analyzer, it
        '''
        if self.oc_type == 'itable':
            # itable is not prepared for this purpose
            return None

        elif self.oc_type == 'pwma':
            if self.meta['group'] == 'subgroup':
                rs = self._get_rs_subg(paper_dict, is_skip_unselected)
            else:
                rs = self._get_rs_pwma(paper_dict, is_skip_unselected)
                
            cfg = self._get_cfg_pwma()
            return {
                'rs': rs,
                'cfg': cfg
            }

        elif self.oc_type == 'nma':
            rs = self._get_rs_nma(paper_dict, is_skip_unselected)
            cfg = self._get_cfg_nma()
            return {
                'rs': rs,
                'cfg': cfg
            }

        else:
            # what???
            return None


    def _get_cfg_pwma(self):
        '''
        Get the PWMA cfg for analyzer
        '''
        cfg = {}

        for item in settings.META_ANALYSIS_CONFIG['pwma']:
            if item in settings.META_ANALYSIS_CONFIG['pwma']:
                cfg[item] = self.meta[item]
            else:
                pass

        # more information about the config
        cfg['external_val'] = 0
        cfg['has_internal_val'] = self.meta['input_format'] == 'PRIM_CAT_RAW'
        cfg['survival_in_control'] = 0
        cfg['internal_val_ec'] = 0
        cfg['internal_val_et'] = 0

        return cfg


    def _get_cfg_nma(self):
        '''
        Get the NMA cfg for analyzer
        '''
        cfg = {}

        for item in settings.META_ANALYSIS_CONFIG['nma']:
            if item in settings.META_ANALYSIS_CONFIG['nma']:
                cfg[item] = self.meta[item]
            else:
                pass

        # more information about the config
        cfg['external_val'] = 0
        cfg['has_internal_val'] = self.meta['input_format'] == 'PRIM_CAT_RAW'
        cfg['survival_in_control'] = 0
        cfg['internal_val_ec'] = 0
        cfg['internal_val_et'] = 0

        return cfg

    
    def _get_rs_pwma(self, paper_dict, is_skip_unselected=True):
        '''
        Get the PWMA rs and cfg for analyzer

        The `paper_dict` is a pid-based dictionary of Paper objects
        '''
        # the value will for each record
        r_treatment = self.meta['treatments'][0]
        r_control = self.meta['treatments'][1]

        rs = []
        for pid in self.data:
            ext = self.data[pid]
           
            if pid in paper_dict:
                study = paper_dict[pid].get_short_name()
                year = paper_dict[pid].get_year()
            else:
                study = '%s' % pid
                year = 'NA'

            if not ext['is_selected'] and is_skip_unselected:
                continue
            
            for arm_idx, arm in enumerate([ext['attrs']['main']] + ext['attrs']['other']):
                r = copy.deepcopy(arm['g0'])

                # convert the data type
                r = util.convert_extract_r_to_number(
                    r,
                    self.meta['input_format']
                )

                # add other information?
                r['pid'] = pid
                r['study'] = study
                r['year'] = year
                r['treatment'] = r_treatment
                r['control'] = r_control

                # ok ...
                rs.append(r)

            # # copy values of main arm to rs
            # r = copy.deepcopy(ext['attrs']['main']['g0'])

            # # for subgroup analysis
            # # if self.meta['group'] == 'subgroup':
                

            # # convert the data type
            # r = util.convert_extract_r_to_number(
            #     r,
            #     self.meta['input_format']
            # )

            # # add other information?
            # r['pid'] = pid
            # r['study'] = study
            # r['year'] = year
            # r['treatment'] = r_treatment
            # r['control'] = r_control

            # # ok ...
            # rs.append(r)

            # # copy other arms if exists
            # if len(ext['attrs']['other']) > 0:
            #     for arm_idx, arm in enumerate(ext['attrs']['other']):
            #         r = copy.deepcopy(arm['g0'])

            #         # convert the data type
            #         r = util.convert_extract_r_to_number(
            #             r,
            #             self.meta['input_format']
            #         )

            #         # add other information?
            #         r['pid'] = pid
            #         r['study'] = study + " (%s)" % (arm_idx+1)
            #         r['year'] = year
            #         r['treatment'] = r_treatment
            #         r['control'] = r_control

            #         # ok, finally
            #         rs.append(r)
        
        return rs
        
    
    def _get_rs_subg(self, paper_dict, is_skip_unselected=True):
        '''
        Get the Subgroup rs for analyzer

        The `paper_dict` is a pid-based dictionary of Paper objects
        '''
        # the value will for each record
        r_treatment = self.meta['treatments'][0]
        r_control = self.meta['treatments'][1]
        subgroups = self.meta['sub_groups']

        rs = []
        for pid in self.data:
            ext = self.data[pid]

            if pid in paper_dict:
                study = paper_dict[pid].get_short_name()
                year = paper_dict[pid].get_year()
            else:
                study = '%s' % pid
                year = 'NA'

            if not ext['is_selected'] and is_skip_unselected:
                continue
            
            for arm_idx, arm in enumerate([ext['attrs']['main']] + ext['attrs']['other']):
                for subg_idx, subg in enumerate(subgroups):
                    subg_key = 'g%s' % subg_idx
                    # 2022-02-11: fix for
                    if subg_key not in arm:
                        # that's also possible, some study have single subgroup
                        continue

                    # copy values of main arm to rs
                    r = copy.deepcopy(arm[subg_key])

                    # convert the data type
                    try:
                        r = util.convert_extract_r_to_number(
                            r,
                            self.meta['input_format']
                        )
                    except Exception as err:
                        # something wrong with the this record
                        print("* cannot convert this record", err)
                        continue

                    # add other information?
                    r['pid'] = pid
                    
                    if arm_idx > 0:
                        r['study'] = study + " (%s)" % (arm_idx+1)
                    else:
                        r['study'] = study

                    r['year'] = year
                    r['treatment'] = r_treatment
                    r['control'] = r_control

                    # the subg
                    r['subgroup'] = subg

                    # ok ...
                    rs.append(r)
        
        return rs

    def _get_nma_treat_list(self, is_skip_unselected=True):
        '''
        Get the NMA treat list
        '''
        # treat_list = []
        # for pid in self.data:
        #     ext = self.data[pid]

        #     if not ext['is_selected'] and is_skip_unselected:
        #         continue

        #     for arm in [ext['attrs']['main']] + ext['attrs']['other']:
        #         t1 = arm['g0']['t1'].strip()
        #         t2 = arm['g0']['t2'].strip()
        #         # add the t1 if not exists
        #         if t1 not in treat_list:
        #             treat_list.append(t1)

        #         # add the t2 if not exists
        #         if t2 not in treat_list:
        #             treat_list.append(t2)

        # return treat_list
        return self.get_treatments_in_data()


    def _get_rs_nma(self, paper_dict, is_skip_unselected=True):
        '''
        Get the NMA rs from this outcome for analyzer
        '''
        rs = []
        study_dict = {}
        for pid in self.data:
            ext = self.data[pid]

            if pid in paper_dict:
                study = paper_dict[pid].get_short_name()
                year = paper_dict[pid].get_year()
            else:
                study = '%s' % pid
                year = 'NA'

            # 2021-12-08: fix duplicate study name
            # Some studies have same first author, 
            # so need to rename
            if study in study_dict:
                # put this study in list again for 
                study_dict[study] += 1
                # put the pid 
                study = '%s (%s)' % (study, pid)
            else:
                study_dict[study] = 1

            if not ext['is_selected'] and is_skip_unselected:
                continue
            
            # there may be other arms, so just join all
            for arm_idx, record in enumerate([ext['attrs']['main']] + ext['attrs']['other']):
                # copy values of main arm to rs
                r = copy.deepcopy(record['g0'])

                # convert the data type
                try:
                    r = util.convert_extract_r_to_number(
                        r,
                        self.meta['input_format']
                    )
                except Exception as err:
                    # something wrong?
                    print("* cannot convert this record", err)
                    continue

                # add other information?
                r['pid'] = pid
                r['study'] = study

                # for multi arm study, need to have different name
                if arm_idx > 0:
                    r['study'] = '%s (Comp %s)' % (study, arm_idx)

                r['year'] = year

                # add alia names if the data type is raw
                if self.meta['input_format'] == 'NMA_PRE_SMLU':
                    # for the pre format, it's very simple, one r is one r
                    rs.append(r)

                elif self.meta['input_format'] == 'NMA_RAW_ET':
                    # the raw format is different by the method
                    if self.meta['analysis_method'] == 'bayes':
                        # if use bayes, need to use two row format
                        # two rows form a record
                        #     study, treat1, event, total
                        #     study, treat2, event, total
                        # so need to convert
                        for i in [1, 2]:
                            # create two rows
                            _r = dict(
                                study = r['study'],
                                treat = r['t%s' % i],
                                event = r['event_t%s' % i],
                                total = r['total_t%s' % i]
                            )
                            rs.append(_r)

                    else:
                        # if use freq, just need to use one row format
                        _r = {}
                        _r['study'] = r['study']
                        _r['treat1'] = r['t1']
                        _r['treat2'] = r['t2']
                        _r['event1'] = r['event_t1']
                        _r['event2'] = r['event_t2']
                        _r['n1'] = r['total_t1']
                        _r['n2'] = r['total_t2']
                        rs.append(_r)

                # ok ...
                # rs.append(r)

            # copy other arms if exists
            # if len(ext['attrs']['other']) > 0:
            #     for arm_idx, arm in enumerate(ext['attrs']['other']):
            #         r = copy.deepcopy(arm['g0'])

            #         # convert the data type
            #         r = util.convert_extract_r_to_number(
            #             r,
            #             self.meta['input_format']
            #         )

            #         # add other information?
            #         r['pid'] = pid
            #         r['study'] = study + " (%s)" % (arm_idx+1)
            #         r['year'] = year

            #         # add alia names if the data type is raw
            #         if self.meta['input_format'] == 'NMA_PRE_SMLU':
            #             pass

            #         elif self.meta['input_format'] == 'NMA_RAW_ET':
            #             r['treat1'] = r['t1']
            #             r['treat2'] = r['t2']
            #             r['event1'] = r['event_t1']
            #             r['event2'] = r['event_t2']
            #             r['n1'] = r['total_t1']
            #             r['n2'] = r['total_t2']

            #         # ok, finally
            #         rs.append(r)
        
        return rs


    def get_repr_str(self):
        '''
        Get a representation string
        '''
        return '%s|%s|%s|%s|%s' % (
            self.meta['cq_abbr'],
            self.meta['oc_type'],
            self.meta['group'],
            self.meta['category'],
            self.meta['full_name']
        )
        

    def __repr__(self):
        return '<Extract {0} {1}: {2}>'.format(
            self.oc_type, self.abbr, self.extract_id)


class Piece(db.Model):
    """
    The extracted data piece details

    It uses three IDs to locate:

    1. project_id: decide which project
    2. extract_id: decide which extract
    3. pid: decide which paper

    The piece contains the information related to an outcome (or AE).
    The `data` attribute contains all the extraction results.
    {
        is_selected: true / false,
        is_checked: true / false,
        n_arms: 2 / 3 / 4 / 5,
        attrs: {
            main: { 
                g0: {
                    attr_sub_abbr: value
                }
            },
            other: [{
                g0: {
                    attr_sub_abbr: value
                }
            }, ...]
        }
    }
    """
    
    __tablename__ = 'pieces'
    __table_args__ = {'extend_existing': True}

    piece_id = db.Column(db.String(48), primary_key=True, nullable=False)
    project_id = db.Column(db.String(48), index=False)
    extract_id = db.Column(db.String(48), index=False)
    pid = db.Column(db.String(settings.PAPER_PID_MAX_LENGTH), index=False)
    data = db.Column(db.JSON, index=False)
    date_created = db.Column(db.DateTime, index=False)
    date_updated = db.Column(db.DateTime, index=False)


    def __repr__(self):
        return '<Piece {0}: {1} in {2}/{3}>'.format(
            self.piece_id, 
            self.pid, 
            self.project_id,
            self.extract_id
        )

    
    def set_is_selected(self, selection):
        '''
        Unselect this piece
        '''
        self.data['is_selected'] = selection


    def as_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
