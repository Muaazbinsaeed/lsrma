#%% define packages and methods
import copy
import os
import re
import json
import time
import random
import hashlib
import datetime
import requests
from bs4 import BeautifulSoup

import uuid 

from werkzeug.utils import secure_filename

from tqdm import tqdm

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from sqlalchemy.ext.declarative import DeclarativeMeta

import logging
from pprint import pprint
logger = logging.getLogger("lnma.util")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s')

from . import settings

# PubMed related functions
PUBMED_URL = {
    'base': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/',
    'esearch': 'esearch.fcgi?db={db}&term={term}&retmode=json&retmax={retmax}',
    'esummary': 'esummary.fcgi?db={db}&id={ids}&retmode=json',
    'efetch': "efetch.fcgi?db={db}&id={uid}&retmode={retmode}",
}


class AlchemyEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            # an SQLAlchemy class
            fields = {}
            for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
                data = obj.__getattribute__(field)
                try:
                    json.dumps(data) # this will fail on non-encodable values, like other classes
                    fields[field] = data
                except TypeError:
                    fields[field] = None
            # a json-encodable dict
            return fields

        return json.JSONEncoder.default(self, obj)


def mk_abbr(length=8):
    return ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for i in range(length))


def mk_oc_abbr():
    return ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for i in range(8))


def mk_abbr_12():
    '''
    Make a random string of length = 12
    '''
    return mk_abbr(12)


def mk_hash_12(t):
    '''
    Make hash per given t in 12 chars
    '''
    return hashlib.md5(t.encode(encoding='utf8')).hexdigest()[:12].upper()


def mk_number_str(length=6):
    '''
    Make a random str of numbers
    '''
    return ''.join(random.choice('0123456789') for i in range(length))


def mk_fake_pid():
    '''
    Make a fake pid for saving those studies without id
    '''
    return 'F%s' % mk_number_str(16)


def mk_md5_by_title(title):
    '''
    Using hash to make a new pid
    '''
    _title = title.lower()
    md5 = hashlib.md5()
    md5.update(_title.encode('utf8'))
    return md5.hexdigest()


def mk_piece_data(
    is_selected=False, 
    is_checked=False,
    n_arms=2,
    init_main_arm_by_cate_attrs=None):
    '''
    Make an empty extract paper data (piece)
    '''
    return mk_empty_extract_paper_data(
        is_selected,
        is_checked,
        n_arms,
        init_main_arm_by_cate_attrs
    )


def mk_empty_extract_paper_data(
    is_selected=False, 
    is_checked=False,
    n_arms=2,
    init_main_arm_by_cate_attrs=None):
    '''
    Make an empty extract paper data
    '''
    pc = {
        'is_selected': is_selected,
        'is_checked': is_checked,
        'n_arms': n_arms,
        'attrs': {
            'main': {},
            'other': []
        }
    }

    if init_main_arm_by_cate_attrs is not None:
        pc['attrs']['main'] = \
            fill_extract_data_arm(
                pc['attrs']['main'],
                init_main_arm_by_cate_attrs
            )

    return pc


def fill_extract_data_arm(arm, cate_attrs, g_idx=0):
    '''
    Fill the extract data arm with empty values
    The arm could be main (arm 1) or other arm
    '''
    # sub group
    sg = 'g%s' % g_idx
    for cate in cate_attrs:
        for attr in cate['attrs']:
            attr_abbr = attr['abbr']
            if attr['subs'] is None:
                if sg not in arm:
                    arm[sg] = {}
                if attr_abbr not in arm[sg]:
                    arm[sg][attr_abbr] = ''
                else:
                    # which means this attr exsits
                    pass
            else:
                # have multiple subs
                for sub in attr['subs']:
                    sub_abbr = sub['abbr']
                    if sg not in arm:
                        arm[sg] = {}
                    # 2021-09-15: fix the sub value missing
                    if sub_abbr not in arm[sg]:
                        arm[sg][sub_abbr] = ''

    return arm


def is_same_extraction(ea, eb, flag_skip_is_selected=False):
    '''
    Compare two extractions attr by attr
    '''
    if flag_skip_is_selected:
        pass
    else:
        if 'is_selected' in ea and 'is_selected' in eb:
            if ea['is_selected'] != eb['is_selected']:
                return False

    if 'is_checked' in ea and 'is_checked' in eb:
        if ea['is_checked'] != eb['is_checked']:
            return False
    
    if 'n_arms' in ea and 'n_arms' in eb:
        if ea['n_arms'] != eb['n_arms']:
            return False

    # check the main arm from ea side
    # 2021-07-12: add subgroup in the comparison
    # the following comparison is also updated
    for g in ea['attrs']['main']:
        if g not in eb['attrs']['main']:
            # which means this subgroup not in eb
            return False
        for attr in ea['attrs']['main'][g]:
            if attr not in eb['attrs']['main'][g]:
                # which means eb use different meta???
                return False
        
            if ea['attrs']['main'][g][attr] != eb['attrs']['main'][g][attr]:
                # which means the value is different
                return False

    # 2021-06-04: two side check update
    # we found that when updating the itable design
    # one side check couldn't figure out the changes
    # check the main arm from eb side
    for g in eb['attrs']['main']:
        if g not in ea['attrs']['main']:
            # which means this subg group not in ea
            return False
        for attr in eb['attrs']['main'][g]:
            if attr not in ea['attrs']['main'][g]:
                # which means ea use different meta???
                return False
            
            if eb['attrs']['main'][g][attr] != ea['attrs']['main'][g][attr]:
                # which means ea have different 
                return False

    # check other arms
    if len(ea['attrs']['other']) != len(eb['attrs']['other']):
        # which means the number of arms is different
        return False

    # check each arm in other
    for arm_idx, _ in enumerate(ea['attrs']['other']):
        ea_arm = ea['attrs']['other'][arm_idx]
        eb_arm = eb['attrs']['other'][arm_idx]

        # check from ea side
        for g in ea_arm:
            if g not in eb_arm:
                # which means this sub group g not in eb_arm
                return False
            for attr in ea_arm[g]:
                if attr not in eb_arm[g]:
                    # which means eb use different meta???
                    return False
                
                if ea_arm[g][attr] != eb_arm[g][attr]:
                    # which means ea has different value
                    return False

        # 2021-06-04: two side check
        for g in eb_arm:
            if g not in ea_arm:
                # which means this sub group g not in ea_arm
                return False
            for attr in eb_arm[g]:
                if attr not in ea_arm[g]:
                    # which means eb use different meta???
                    return False
                
                if eb_arm[g][attr] != ea_arm[g][attr]:
                    # which means eb has different value
                    return False
            
    # wow, they are the same
    return True
    

def is_valid_rct_id(rct_id):
    '''
    Check if a RCT ID is valid

    currently, there is not a good way to know
    '''
    # 2023-05-29: fix nan or none rct_id
    _rct_id = '%s' % rct_id
    if len(_rct_id)>5:
        return True

    return False


def is_valid_embase_id(pid):
    '''
    Check if a pid is valid Embase ID

    Just a basic check
    '''
    valid_pids = re.findall('^\d{9,10}$', pid, re.MULTILINE)

    if valid_pids == []:
        return False
    else:
        return True


def is_valid_doi(pid):
    '''
    Check if a pid is valid DOI

    Just a basic check
    '''
    valid_pids = re.findall('^10.\d{4,9}/[-._;()/:a-zA-Z0-9]+$', pid, re.MULTILINE)

    if valid_pids == []:
        return False
    else:
        return True


def is_valid_pmid(pmid):
    '''
    Check if a pmid is valid PMID

    Just a basic check
    '''
    valid_pmids = re.findall('^\d{6,8}$', pmid, re.MULTILINE)

    if valid_pmids == []:
        return False
    else:
        return True


def get_valid_pmid(pmid):
    '''
    Get the valid PMID from a pmid string (candidate)
    '''
    valid_pmids = re.findall('\d{8}', pmid, re.MULTILINE)

    if valid_pmids == []:
        return None
    else:
        return valid_pmids[0]


def allowed_file_format(fn, exts=['csv', 'xls', 'xlsx', 'xml']):
    return '.' in fn and \
        fn.rsplit('.', 1)[1].lower() in exts


def _get_e_search_url(term, db='pubmed', retmax=300):
    url = PUBMED_URL['base'] + PUBMED_URL['esearch'].format(db=db, term=term, retmax=retmax)
    return url


def _get_e_summary_url(ids, db='pubmed'):
    url = PUBMED_URL['base'] + PUBMED_URL['esummary'].format(db=db, ids=ids)
    return url


def _get_e_fetch_url(uid, db='pubmed', retmode='xml'):
    url = PUBMED_URL['base'] + PUBMED_URL['efetch'].format(db=db, uid=uid, retmode=retmode)
    return url


def e_search(term, db='pubmed'):
    '''
    Search for term in pubmed
    '''
    try_times = 0

    while True:
        url = _get_e_search_url(term)
        print('* e_search %s' % url)
        r = requests.get(url)

        if r.status_code == 200:
            return r.json()

        # something wrong?
        try_times += 1
        print('* Something wrong, HTTP Status Code: {0}'.format(r.status_code))
        if r.status_code == 429:
            print('* Reached MAX request limit of PubMed')

        if try_times < 3:
            dur = 7 * try_times
            print('* Wait for %s seconds and try again ...' % dur)
            time.sleep(dur)
        else:
            break
    
    print('* Tried e_search %s times but still failed ...' % try_times)
    return None


def e_summary(ids, db='pubmed'):
    '''
    Get summary of pmid list
    '''
    try_times = 0

    while True:
        url = _get_e_summary_url(','.join(ids))
        print('* e_summary %s' % url)
        r = requests.get(url)

        if r.status_code == 200:
            return r.json()

        # something wrong?
        try_times += 1
        print('* Something wrong, HTTP Status Code: {0}'.format(r.status_code))
        if r.status_code == 429:
            print('* Reached MAX request limit of PubMed')

        if try_times < 3:
            dur = 7 * try_times
            print('* Wait for %s seconds and try again ...' % dur)
            time.sleep(dur)
        else:
            break
    
    print('* Tried e_summary %s times but still failed ...' % try_times)
    return None

    
def _e_fetch(ids, db='pubmed'):
    '''
    Get the raw xml data from pubmed
    '''
    try_times = 0

    while True:
        url = _get_e_fetch_url(','.join(ids))
        print('* e_fetch %s' % url)
        r = requests.get(url)

        if r.status_code == 200:
            return r.text

        # something wrong?
        try_times += 1
        print('* Something wrong, HTTP Status Code: {0}'.format(r.status_code))
        if r.status_code == 429:
            print('* Reached MAX request limit of PubMed')

        if try_times < 3:
            dur = 7 * try_times
            print('* Wait for %s seconds and try again ...' % dur)
            time.sleep(dur)
        else:
            break
    
    print('* Tried e_fetch %s times but still failed ...' % try_times)
    return None


def e_fetch(ids, db='pubmed'):
    '''
    get JSONfied data
    '''
    text = _e_fetch(ids, db)

    if text is None:
        return None

    # parse the xml tree
    root = ET.fromstring(text)

    ret = {
        'result': {
            'uids': []
        }
    }
    for item in root.findall('PubmedArticle'):
        # check each item
        paper = {
            'uid': '',
            'sortpubdate': [],
            'date_pub': [],
            'date_epub': [],
            'date_revised': [],
            'date_completed': [],
            'source': '',
            'title': '',
            'authors': [],
            'abstract': [],
            'raw_type': 'pubmed_xml',
            'xml': ET.tostring(item, encoding='utf8', method='xml')
        }

        # check each xml node
        for node in item.iter():
            if node.tag == 'PMID': 
                if paper['uid'] == '':
                    paper['uid'] = node.text
                else:
                    # other PMIDs will also appear in result
                    pass

            elif node.tag == 'ArticleTitle':
                paper['title'] = node.text

            elif node.tag == 'Abstract':
                for c in node:
                    if c is None or c.text is None:
                        pass
                    else:
                        paper['abstract'].append(c.text)

            elif node.tag == 'ISOAbbreviation':
                paper['source'] = node.text

            # 2021-03-24: there are four types of date
            # take this for example: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=27717298&retmode=xml
            # I guess
            # - ArticleDate is the ePub date
            # - PubDate is the journal physical publication date
            # - DateCompleted is ... I don't know
            # - DateRevised is the online revision date
            # in the last, if ArticleDate is available, just use ArticleDate
            # if not, follow the order above

            elif node.tag == 'ArticleDate':
                for c in node:
                    paper['date_epub'].append(c.text)

            elif node.tag == 'PubDate':
                for c in node:
                    paper['date_pub'].append(c.text)

            elif node.tag == 'DateCompleted':
                for c in node:
                    paper['date_completed'].append(c.text)

            elif node.tag == 'DateRevised':
                for c in node:
                    paper['date_revised'].append(c.text)
                
            elif node.tag == 'AuthorList':
                for c in node:
                    fore_name = c.find('ForeName')
                    last_name = c.find('LastName')
                    name = ('' if fore_name is None else fore_name.text) + ' ' + \
                           ('' if last_name is None else last_name.text)

                    paper['authors'].append({
                        'name': name,
                        'authtype': 'Author'
                    })
        # merge abstract
        paper['abstract'] = ' '.join(paper['abstract'])

        # try to find the good date
        paper['date_epub'] = '-'.join(paper['date_epub'])
        paper['date_pub'] = '-'.join(paper['date_pub'])
        paper['date_completed'] = '-'.join(paper['date_completed'])
        paper['date_revised'] = '-'.join(paper['date_revised'])

        if paper['date_epub'] != '':
            paper['sortpubdate'] = paper['date_epub']
        elif paper['date_pub'] != '':
            paper['sortpubdate'] = paper['date_pub']
        elif paper['date_pub'] != '':
            paper['sortpubdate'] = paper['date_completed']
        elif paper['date_pub'] != '':
            paper['sortpubdate'] = paper['date_revised']
        else:
            paper['sortpubdate'] = ''

        # append to return
        if paper['uid'] != '':
            ret['result']['uids'].append(paper['uid'])
            ret['result'][paper['uid']] = paper

    return ret


def doi_fetch(doi):
    '''
    Get paper metadata by DOI

    Returns

    1. Parsed result
    2. Raw JSON result
    '''
    url = f"https://api.crossref.org/works/{doi}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        paper_info = parse_doi_ws_json(data)

        if paper_info is None:
            return None, None, 'None Information'

        return paper_info, data, 'OK'

    else:
        return None, None, 'DOI Service Error %s' % response.status_code


###########################################################
# parse functions
###########################################################

def parse_doi_ws_json(data):
    '''
    Parse the JSON returns from DOI webservice
    https://api.crossref.org/works/
    '''
    paper_info = {
        'title': '',
        'abstract': '',
        'pub_date': '',
        'authors': '',
        'journal': '',
    }
        
    # Retrieve title
    if data is None or 'message' not in data:
        # what???
        return None

    if 'title' not in data['message']:
        # no need to parse if title is not there
        return None
    
    title = data['message']['title'][0]
    paper_info['title'] = title
    
    # Retrieve abstract
    if 'abstract' in data['message']:
        abstract_html = data['message']['abstract']
        abstract_text = BeautifulSoup(abstract_html, 'html.parser').get_text()
        paper_info['abstract'] = abstract_text
    else:
        paper_info['abstract'] = ""
    
    # Retrieve publication date
    if 'published-print' in data['message']:
        publication_date_parts = data['message']['published-print']['date-parts'][0]
        publication_date = '-'.join(str(part) for part in publication_date_parts)
        paper_info['pub_date'] = publication_date
    else:
        paper_info['pub_date'] = ""
    
    # Retrieve authors
    authors = []
    if 'author' in data['message']:
        for author in data['message']['author']:
            an = ''
            if 'given' in author:
                an = author['given']
            if 'family' in author:
                if an == '':
                    an = author['family']
                else:
                    an = an + ' ' + author['family']
            
            if an != '':
                authors.append(an)
        
        paper_info['authors'] = '; '.join(authors)
    
    # Retrieve journal information
    if 'container-title' in data['message']:
        journal_info = data['message']['container-title'][0]
        paper_info['journal'] = journal_info
    
    return paper_info


def parse_ovid_exported_xml(full_fn):
    '''
    Parse the file from ovid export
    '''
    try:
        tree = ET.parse(full_fn)
        root = tree.getroot()
    except Exception as err:
        logger.error('ERROR when parsing %s, %s' % (full_fn, err))
        return None

    return _parse_ovid_exported_xml_root(root)


def parse_ovid_exported_xml_text(text):
    '''
    Parse the XML text from ovid export
    '''
    try:
        tree = ET.fromstring(text)
        try:
            root = tree.getroot()
        except:
            root = tree

    except Exception as err:
        logger.error('ERROR when parsing xml text, %s' % (err))
        return None

    return _parse_ovid_exported_xml_root(root)
    
    
def _parse_ovid_exported_xml_root(root):
    '''
    Parse a XML root which is an exported XML
    '''
    papers = []
    records = root.find('records').findall('record')
    # logger.info('found %s records in XML root' % (len(records)))
    for record in records:
        paper = {
            'pid': '',
            'pid_type': '',
            'title': '',
            'authors': '',
            'abstract': '',
            'pub_date': '',
            'pub_type': '',
            'journal': '',
            'rct_id': '',
            'raw_type': 'ovid_xml',
            'xml': ET.tostring(record, encoding='utf8', method='xml').decode('utf-8'),
            'other': {}
        }

        for node in record.iter():
            if node.tag == 'F':
                c = node.attrib['C']

                if c == 'UI':
                    # update the pid
                    paper['pid'] = __get_node_text(paper['pid'], node)
                    # make sure the lowercase
                    paper['pid'] = paper['pid'].lower()
                elif c == 'ST':
                    # update the pid type by ST
                    paper['pid_type'] = __get_node_text(paper['pid_type'], node)
                elif c == 'DB':
                    # update the pid type by DB
                    paper['pid_type'] = __get_node_text(paper['pid_type'], node)
                elif c == 'TI':
                    # update the title
                    paper['title'] = __get_node_text(paper['title'], node)
                elif c == 'AU':
                    # update the authors
                    paper['authors'] = '; '.join([ _.text for _ in node.findall('D') ])
                elif c == 'AB':
                    # update the abstract
                    paper['abstract'] = __get_node_text(paper['abstract'], node)
                elif c == 'AS':
                    # update the journal by AS Abbreviated Source
                    paper['journal'] = __get_node_text(paper['journal'], node)
                elif c == 'SO':
                    # update the journal by SO
                    paper['journal'] = __get_node_text(paper['journal'], node)
                elif c == 'JA':
                    # update the journal by JA
                    paper['journal'] = __get_node_text(paper['journal'], node)
                elif c == 'YR':
                    # update the pub_date
                    paper['pub_date'] = __get_node_text(paper['pub_date'], node)
                elif c == 'DP':
                    # update the pub date by other info
                    paper['pub_date'] = __get_node_text(paper['pub_date'], node)
                elif c == 'PT':
                    # update the pub_type
                    paper['pub_type'] = __get_node_text(paper['pub_type'], node)
                elif c == 'CN':
                    # update the RCT id
                    paper['rct_id'] = __get_node_text(paper['rct_id'], node)
                else:
                    # unknow keywords
                    if c not in paper['other']:
                        paper['other'][c] = []
                    # extend this
                    paper['other'][c] += [ d.text for d in node.findall('D') ]
        
        papers.append(paper)

    return papers


def __get_node_text(old_text, node):
    '''
    Get the node text and return the option
    '''
    if node.find('D') is None:
        # if node is none, nothing to do
        return old_text

    # otherwise, get the text
    new_text = node.find('D').text.strip()

    if new_text == '':
        # if text is empty, just use the old text
        return old_text

    if old_text == '':
        # great! old text is empty, just use the new text
        return new_text

    # now is the hardest situation, both are not empty
    # TODO should decide the value by node type
    c = node.attrib['C']
    return new_text


def parse_exported_ris(full_fn):
    '''
    Parse the file from endnote export
    '''
    import rispy

    f = open(full_fn)
    ents = rispy.load(f)
    f.close()

    # let's check each paper
    papers = []
    cnt = {
        'has_pid': 0,
        'no_pid_has_doi': 0,
        'no_id': 0
    }

    for ent in ents:
        # create an empty paper object
        paper = {
            'pid': '',
            'pid_type': [],
            'doi': '',
            'title': '',
            'authors': [],
            'abstract': '',
            'pub_date': [],
            'pub_type': '',
            'journal': [],
            'raw_type': 'ris',
            'other': copy.deepcopy(ent)
        }
        # print(paper)
        if 'authors' in ent:
            paper['authors'] = ent['authors']

        if 'primary_title' in ent:
            paper['title'] = ent['primary_title']

        if 'abstract' in ent:
            paper['abstract'] = ent['abstract']

        for key in ['date', 'publication_year', 'year']:
            try:
                paper['pub_date'] = ent[key]
                break
            except:
                pass

        for key in ['journal_name', 'secondary_title', 'alternate_title1', 'alternate_title2', 'alternate_title3']:
            try:
                paper['journal'] = ent[key]
                break
            except:
                pass
        
        if 'doi' in ent:
            paper['doi'] = ent['doi']

        # update the authors
        paper['authors'] = check_paper_authors('; '.join(paper['authors']))

        # if the pid is empty, 
        paper['pid'] = check_paper_pid(paper['pid'])
        paper['doi'] = check_paper_doi(paper['doi'])
        
        if paper['pid'] == '':
            # what a ... anyway, check doi
            if paper['doi'] == '':
                # I don't have anything to say, just make a fake pid for this
                paper['pid'] = mk_md5_by_title(
                    paper['title']
                )
                paper['pid_type'] = 'MD5'

                cnt['no_id'] += 1
            else:
                paper['pid'] = paper['doi']
                paper['pid_type'] = 'DOI'
                cnt['no_pid_has_doi'] += 1
                
        else:
            cnt['has_pid'] += 1
        
        papers.append(paper)

    print('* found %s has pid, %s paper using doi, %s no id' % (
        cnt['has_pid'], cnt['no_pid_has_doi'],
        cnt['no_id'],
    ))

    return papers, cnt


def parse_endnote_exported_xml(full_fn):
    '''
    Parse the file from endnote export
    '''
    try:
        tree = ET.parse(full_fn)
        root = tree.getroot()
    except Exception as err:
        logger.error('ERROR when parsing %s, %s' % (full_fn, err))
        return None

    papers = []
    cnt = {
        'has_pid': 0,
        'no_pid_has_doi': 0,
        'no_id': 0
    }
    for record in tqdm(root.find('records').findall('record')):
        paper = {
            'pid': '',
            'pid_type': [],
            'doi': '',
            'title': '',
            'authors': [],
            'abstract': '',
            'pub_date': [],
            'pub_type': '',
            'journal': [],
            'raw_type': 'endnote_xml',
            # 'xml': ""
            'xml': ET.tostring(record, encoding='utf8', method='xml').decode('utf-8'),
            'other': {}
        }
        # print(paper)

        for node in record.iter():
            # print(node.tag)
            if node.tag == 'accession-num':
                paper['pid'] = ''.join(node.itertext())
            elif node.tag == 'remote-database-name':
                paper['pid_type'].append(''.join(node.itertext()))
            elif node.tag == 'remote-database-provider':
                paper['pid_type'].append(''.join(node.itertext()))
            
            elif node.tag == 'title':
                paper['title'] = ''.join(node.itertext())
            elif node.tag == 'author':
                paper['authors'].append(''.join(node.itertext()))
            elif node.tag == 'electronic-resource-num':
                paper['doi'] = ''.join(node.itertext())

            # the journal information
            elif node.tag == 'full-title':
                paper['journal'].append(''.join(node.itertext()))
            elif node.tag == 'pages':
                paper['journal'].append('p. ' + ''.join(node.itertext()))
            elif node.tag == 'volume':
                paper['journal'].append('vol. ' + ''.join(node.itertext()))
            elif node.tag == 'number':
                paper['journal'].append('(%s)' % ''.join(node.itertext()))

            # the abstract
            elif node.tag == 'abstract':
                paper['abstract'] = ''.join(node.itertext())
                # print('* found abstract: %s' % paper['abstract'])
                
            elif node.tag == 'pub-dates':
                paper['pub_date'].append( ' '.join(node.itertext()) )
            elif node.tag == 'dates':
                year = node.find('year')
                if year:
                    paper['pub_date'].append( ' '.join(node.find('year').itertext()) )
            elif node.tag == 'work-type':
                paper['pub_type'] = ''.join(node.itertext())
            else:
                if node.tag not in paper['other']:
                    paper['other'][node.tag] = []
                paper['other'][node.tag] += list(node.itertext())

        # update the authors
        paper['authors'] = check_paper_authors('; '.join(paper['authors']))
        paper['pub_date'] = check_paper_pub_date(' '.join(paper['pub_date']))
        paper['journal'] = check_paper_journal('; '.join(paper['journal']))
        paper['pid_type'] = check_paper_pid_type(', '.join(paper['pid_type']))

        # if the pid is empty, 
        paper['pid'] = check_paper_pid(paper['pid'])
        paper['doi'] = check_paper_doi(paper['doi'])
        
        if paper['pid'] == '':
            # what a ... anyway, check doi
            if paper['doi'] == '':
                # I don't have anything to say, just make a fake pid for this
                paper['pid'] = mk_md5_by_title(
                    paper['title']
                )
                paper['pid_type'] = 'MD5'

                cnt['no_id'] += 1
            else:
                paper['pid'] = paper['doi']
                paper['pid_type'] = 'DOI'
                cnt['no_pid_has_doi'] += 1
                
        else:
            cnt['has_pid'] += 1
        
        papers.append(paper)

    print('* found %s has pid, %s paper using doi, %s no id' % (
        cnt['has_pid'], cnt['no_pid_has_doi'],
        cnt['no_id'],
    ))

    return papers, cnt


def parse_ovid_exported_text_content(txt):
    '''
    Parse the email content from OVID 

    This is for the text format
    '''
    # open('tmp.txt', 'w').write(txt)

    lines = txt.split('\n')
    ptn_attr = r'^\s*([A-Z]{2})\s+-\s(.*)'
    ptn_attr_ext = r'^\s+(.*)'
    ptn_new_art = r'^\s*\<(\d+)\>'

    arts = []

    # temporal variable
    art = {}
    attr = ''
    buff = []

    for line in lines:
        buff.append(line)
        # try articl pattern
        m = re.findall(ptn_new_art, line)
        if len(m) > 0:
            # this means this line starts a new article
            # for example
            # re.findall(ptn_new_art, '<13>')
            # the 13rd article is found
            if art == {}:
                # it means this is the first article
                pass
            else:
                # not the first, save previous first, then reset
                art['text'] = '\n'.join(buff)
                arts.append(art)
                art = {}
                buff = []
            
            # once match a pattern, no need to check other patterns
            continue

        # try attr pattern first, it's the most common pattern
        m = re.findall(ptn_attr, line)
        if len(m) > 0:
            # which means it's a new attribute
            # for example
            # > re.findall(ptn_attr, 'DB  - Ovid MEDLINE(R) Revisions')
            # > [('DB', 'Ovid MEDLINE(R) Revisions')]
            attr = m[0][0]
            val = m[0][1].strip()

            # auto seg by UI
            if attr == 'UI' and 'UI' in art:
                art['text'] = '\n'.join(buff)
                arts.append(art)
                art = {}
                buff = []

            # append this attr
            if attr not in art: art[attr] = []

            # put this value into art object
            art[attr].append(val)

            # once match a pattern, no need to check other patterns
            continue

        # try next pattern
        m = re.findall(ptn_attr_ext, line)
        if len(m) > 0:
            # this means this line is an extension of previous attr
            val = m[0]
            # use previous attr, the attr should exist
            if attr == '':
                pass
            else:
                if attr not in art: art[attr] = []
                art[attr].append(val)

                # once match a pattern, no need to check other patterns
                continue

    
    # usually, the last art need to be appended manually
    if art != {}:
        art['text'] = '\n'.join(buff)
        arts.append(art)
        buff = []

    # now need to merge the attributes 
    for art in arts:
        for k in art:
            if len(art[k]) == 1:
                art[k] = art[k][0]
            else:
                if k in ('AU', 'FA', 'ID'): continue
                elif k == 'AB': art[k] = '\n'.join(art[k])
                else: art[k] = ' '.join(art[k])

    # convert the articles to paper format
    papers = []

    for art in arts:
        if 'UI' not in art:
            continue

        pid = art['UI'].lower()
        title = art['TI'] if 'TI' in art else ''
        abstract = art['AB'] if 'AB' in art else ''
        authors = ', '.join(art['AU']) if 'AU' in art else ''
        pid_type = art['DB'].upper() if 'DB' in art else 'OVID'
        pub_type = art['PT'] if 'PT' in art else ''
        rct_id = art['CN'] if 'CN' in art else ''

        if pid_type.startswith('EMBASE'):
            pub_date = art['DP'] if 'DP' in art else ''
            journal = art['JA'] if 'JA' in art else ''
        elif pid_type.startswith('OVID MEDLINE'):
            pub_date = art['EP'] if 'EP' in art else ''
            journal = art['AS'] if 'AS' in art else ''
        else:
            pub_date = art['EP'] if 'EP' in art else ''
            journal = art['AS'] if 'AS' in art else ''

        paper = {
            'pid': pid,
            'pid_type': pid_type,
            'title': title,
            'authors': authors,
            'abstract': abstract,
            'pub_date': pub_date,
            'pub_type': pub_type,
            'journal': journal,
            'rct_id': rct_id,
            'raw_type': 'text',
            'xml': '',
            'other': art
        }

        papers.append(paper)

    return papers


def pred_rct(ti, ab):
    '''
    Predict if a study is RCT
    '''
    url = 'http://localhost:12580/'
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    data = {'ti': ti, 'ab': ab}
    data_str = json.dumps(data)
    r = requests.post(url, data=data_str, headers=headers)
    j = r.json()
    return j


def get_decision_detail_dict(reason, decision):
    '''
    Get a decision detail dictionary
    '''
    # create a dict for the details
    detail_dict = {
        'date_decided': get_today_date_str(),
        'reason': reason,
        'decision': decision
    }

    return detail_dict


def get_today_date_str():
    '''
    Get the today date string
    '''
    return datetime.datetime.today().strftime('%Y-%m-%d')


def get_nct_number(s):
    '''
    Get the NCT8 number from study
    '''
    return re.findall('NCT\d{8}', s, re.MULTILINE)


def get_year(s):
    '''
    Get the year number from a string
    '''
    rs = re.findall('\d{4}', s, re.MULTILINE)
    if len(rs) == 0:
        return ''
    else:
        return rs[0]


def get_author_etal_from_authors(authors):
    '''
    Get the "First author name et al" format
    '''
    aus = authors.split(';')
    if len(aus) == 1:
        aus = authors.split(',')

    if len(aus[0]) > 20:
        aus = aus[0].split(',')
    
    fau_etal = aus[0] + ' et al'

    return fau_etal


def get_author_etal_from_paper(paper):
    '''
    Get the "First author name et al" format
    '''
    return get_author_etal_from_authors(paper.authors)


def save_pdf(file):
    '''
    Save the Upload file
    '''
    folder = datetime.datetime.now().strftime(settings.PATH_PDF_FOLDER_FORMAT)
    file_id = project_id = str(uuid.uuid1())
    file_name = file_id + '.pdf'

    # TODO make sure the display name is safe
    display_name = file.filename

    # save the file
    full_file_name = os.path.join(
        settings.PATH_PDF_FILES,
        folder,
        file_name
    )
    os.makedirs(os.path.dirname(full_file_name), exist_ok=True)
    file.save(full_file_name)

    # return the obj
    return {
        'folder': folder,
        'file_id': file_id,
        'display_name': display_name
    }


def save_pdfs_from_request_files(files):
    '''
    Save the uploaded files in the request
    and return the pdf_metas for paper.meta['pdfs']

    The `files` is a request form object which contains every file
    '''
    # save the files first
    pdf_metas = []
    for file in files:
        if file and allowed_file(file.filename):
            pdf_meta = save_pdf(file)
            pdf_metas.append(pdf_meta)

    return pdf_metas


def delete_pdf(pdf_meta):
    '''
    Delete the PDF file
    '''
    full_fn = os.path.join(
        settings.PATH_PDF_FILES,
        pdf_meta['folder'],
        pdf_meta['file_id'] + '.pdf'
    )

    if os.path.exists(full_fn):
        os.remove(full_fn)

    return True


def make_temp_pid():
    pid_type = 'TEMP_PID'
    pid = 'TMP' + mk_number_str()

    return pid, pid_type


def allowed_file(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in settings.ALLOWED_PDF_UPLOAD_EXTENSIONS


###########################################################
# Shared data functions
###########################################################
def notna(v):
    '''
    Check whether a value `v` is NA or not
    '''
    return not (v is None or v=='' or v=='null' or v=='na' or v=='n/a')


def notzero(v):
    '''
    Check whether a value `v` is 0
    '''
    return v!=0


def is_empty(v):
    '''
    Check whether a value `v` is empty
    '''
    if v is None:
        return True
    
    # convert to string
    v_str = '%s' % v
    v_str = v_str.lower()
    v_str = v_str.strip()
    
    if v_str=='' or v_str=='null' or v_str=='na' or v_str=='n/a':
        return True
    
    # maybe other thing?
    return False


def is_missing(v):
    '''
    Check whether is missing
    '''
    if v is None:
        return True
    
    # convert to string
    v_str = '%s' % v
    v_str = v_str.lower()
    v_str = v_str.strip()
    
    if v_str=='':
        return True
    
    # maybe other thing?
    return False


def is_integer(value):
    '''
    Check whether a value `v` is an integer
    '''
    if isinstance(value, int):
        return True
    elif isinstance(value, float) and value.is_integer():
        return True
    elif isinstance(value, float) and int(value) == value:
        return True
    elif isinstance(value, str):
        _v = value.strip()
        if _v.isdigit():
            return True
        else:
            return False
    else:
        return False


def is_int_zero(value):
    '''
    Check whether a value `v` is an integer zero
    '''
    v_str = '%s' % value
    v_str = v_str.lower()
    v_str = v_str.strip()
    
    if v_str=='0':
        return True
    
    # maybe other thing?
    return False


def is_pwmable(Et, Nt, Ec, Nc):
    '''
    Check whether a study is able to do PWMA
    '''
    # the first condition is all numbers are not null
    f1 = notna(Et) and notna(Nt) and \
         notna(Ec) and notna(Nc)
        
    # the second condition is not both zero
    f2 = (notna(Et) and notzero(Et)) or \
         (notna(Ec) and notzero(Ec))

    # 2023-04-19: Nt and Nc cannot be 0
    f3 = notzero(Nt) and notzero(Nc)

    # final combine two
    return f1 and f2 and f3


def is_E_gt_N(E, N):
    '''
    Check whether two values are ok for pwma
    '''
    if is_integer(E) and is_integer(N):
        val_E = val2int(E)
        val_N = val2int(N)
        if val_E > val_N:
            return True
    
    return False


def get_ds_name_by_pid_and_type(pid, pid_type):
    '''
    Get the data source id (ds_id) by pid / pid_type

    This function is designed for summarizing the pid type to a shorter format
    '''
    _pid_type = pid_type.lower()

    # by default, we don't know what this ds
    ds_name = 'other'

    if 'medline' in _pid_type or \
        'pmid' in _pid_type or \
        'nlm' in _pid_type or \
        'pubmed' in _pid_type:

        ds_name = 'pmid'

    elif is_valid_pmid(pid):
        # sometimes ... yes, just do it.
        ds_name = 'pmid'
    
    elif 'md5' in _pid_type:
        # ok this is just a our customized id
        ds_name = 'md5'

    elif 'embase' in _pid_type or 'ebase' in _pid_type:
        ds_name = 'embase'

    elif 'doi' in _pid_type:
        ds_name = 'doi'
    
    else:
        ds_name = 'other'

    return ds_name


def get_paper_pmid_if_exists(paper):
    '''
    Get the PMID from a paper
    '''
    if 'ds_id' in paper.meta:
        if 'pmid' in paper.meta['ds_id']:
            return {
                'type': 'pmid',
                'id': paper.meta['ds_id']['pmid']
            }
    # oh, no ds_id or not pmid
    return {
        'type': get_ds_name_by_pid_and_type(
            paper.pid,
            paper.pid_type
        ),
        'id': paper.pid
    }


def guess_pid_type_by_pid(pid):
    '''
    Guess the pid_type by the given pid
    '''
    if is_valid_pmid(pid):
        return 'PMID'
    
    elif is_valid_embase_id(pid):
        return 'EMBASE'

    elif is_valid_doi(pid):
        return 'DOI'

    else:
        return 'OTHER'

###############################################################################
# Check the input field to avoid invaild input values
###############################################################################

def check_paper_pid_type(pid_type):
    '''
    make a short pid type for input

    The PID type sometimes is too long for saving, make a shorter version
    from the original text

    Sometimes the pid_type is None, which means no avaiable data is provided
    '''
    if pid_type is None:
        return settings.PID_TYPE_NONE_TYPE

    # clean the leading and last blank space
    pid_type = pid_type.strip()
    if len(pid_type) == 0:
        return settings.PID_TYPE_NONE_TYPE
    else:
        return pid_type[0:settings.PID_TYPE_MAX_LENGTH]


def check_paper_pid(pid):
    '''
    check the paper pid for valid input
    '''
    if pid is None:
        return ''

    # 2023-06-12: make sure the pid is lowercase
    pid = pid.strip().lower()
    if len(pid) == 0:
        return ''
    else:
        return pid[0:settings.PAPER_PID_MAX_LENGTH]


def check_paper_doi(doi):
    '''
    Check the doi content
    '''
    if doi is None:
        return ''

    # 2023-06-12: make sure the doi is lowercase
    doi = doi.strip().lower()

    if len(doi) == 0:
        return ''

    lower_doi = doi.lower()
    _doi = lower_doi

    # 2022-03-30: fix the URL as DOI
    if lower_doi.startswith('http://dx.doi.org/'):
        # 2022-05-13: fix the lower case bug
        _doi = doi[18:]
    
    elif lower_doi.startswith('https://dx.doi.org/'):
        # 2022-05-13: fix the lower case bug
        _doi = doi[19:]
    
    else:
        # 2022-05-13: fix the lower case bug
        _doi = doi

    return _doi[0:settings.PAPER_PID_MAX_LENGTH]
    

def check_paper_pub_date(pub_date):
    '''
    check the paper pub date for valid input
    '''
    if pub_date is None:
        return ''

    pub_date = pub_date.strip()
    if len(pub_date) == 0:
        return ''
    else:
        return pub_date[0:settings.PAPER_PUB_DATE_MAX_LENGTH]
    

def check_paper_authors(authors):
    '''
    check the paper authors for valid input
    '''
    if authors is None:
        return ''

    authors = authors.strip()
    if len(authors) == 0:
        return ''
    else:
        return authors[0:settings.PAPER_AUTHORS_MAX_LENGTH]


def check_paper_journal(journal):
    '''
    check the paper journal for valid input
    '''
    if journal is None:
        return ''

    journal = journal.strip()
    if len(journal) == 0:
        return ''
    else:
        return journal[0:settings.PAPER_JOURNAL_MAX_LENGTH]


def escape_illegal_xml_characters(x):
    '''
    Make a safe XML content
    '''
    return re.sub(u'[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]', '', x)


def json_encoder(o):
    '''
    Encode the object `o` in for JSON
    '''
    if isinstance(o, datetime.datetime):
        return o.__str__()

    return str(o)


def sort_rct_seq(papers):
    '''
    Sort the RCT sequence of the given papers

    Return RCT dict
    {
        'NCT1234567': {
            'rct_seq': {
                '12345678': 0,
                '23456789': 1,
                '34567890': 2
            },
            'papers': [
                {'pid':'12345678', 'pub_date': 2019},
                {'pid':'23456789', 'pub_date': 2020},
                {'pid':'34567890', 'pub_date': 2021}
            ]
        },
        ...
    }
    '''
    # all nct
    rcts = {}

    # check each paper
    for paper in tqdm(papers):
        if paper.meta['rct_id'] == '': continue

        rct = paper.meta['rct_id']
        if rct not in rcts:
            rcts[rct] = {
                'rct_seq': {},
                'papers': []
            }

        rcts[rct]['papers'].append({
            'pid': paper.pid,
            'pub_date': get_year(paper.pub_date)
        })

    # sort the nct's paper
    for rct in rcts:
        rcts[rct]['papers'] = sorted(
            rcts[rct]['papers'],
            key=lambda p: p['pub_date']
        )
        for i, p in enumerate(rcts[rct]['papers']):
            rcts[rct]['rct_seq'][p['pid']] = i

    return rcts
    

def make_ss_cq_dict(project, cq_abbr=None):
    '''
    Make an initial ss_cq based on a project
    '''
    d = {}

    for cq in project.settings['clinical_questions']:
        _cq_abbr = cq['abbr']
        
        if len(project.settings['clinical_questions']) == 1:
            # if just one cq, then yes
            d[_cq_abbr] = make_ss_cq_decision(
                settings.PAPER_SS_EX_SS_CQ_DECISION_YES,
                '',
                settings.PAPER_SS_EX_SS_CQ_CONFIRMED_NO
            )
        
        else:
            # if not, just set the specified one as yes
            if cq_abbr == _cq_abbr:
                d[_cq_abbr] = make_ss_cq_decision(
                    settings.PAPER_SS_EX_SS_CQ_DECISION_YES,
                    '',
                    settings.PAPER_SS_EX_SS_CQ_CONFIRMED_NO
                )
            else:
                d[_cq_abbr] = make_ss_cq_decision(
                    settings.PAPER_SS_EX_SS_CQ_DECISION_NO,
                    '',
                    settings.PAPER_SS_EX_SS_CQ_CONFIRMED_NO
                )

    return d


def make_ss_cq_dict_by_cq_abbr(
    cq_abbr, 
    decision=settings.PAPER_SS_EX_SS_CQ_DECISION_YES,
    reason='',
    confirmed=settings.PAPER_SS_EX_SS_CQ_CONFIRMED_NO):
    '''
    '''
    return {
        cq_abbr: make_ss_cq_decision(
            decision,
            reason,
            confirmed
        )
    }


def make_ss_cq_decision(
    decision,
    reason,
    confirmed
):
    '''
    Decision, Reason, Confirmed
    '''
    return {
        'd': decision,
        'r': reason,
        'c': confirmed
    }


def hash_json(j):
    '''
    Hash a json (Python Dictionary) object
    '''
    # first, convert the json to a string
    s = json.dumps(j, sort_keys=True, indent=2)

    # second, hash it!
    h = hashlib.md5(s.encode("utf-8")).hexdigest()

    return h


def val2int(v):
    ret = v
    if type(v) == str:
        try:
            ret = float(v)
        except:
            pass
        
        try:
            ret = int(ret)
        except:
            pass
        
    elif type(v) == int:
        ret = v

    elif type(v) == float:
        ret = int(v)

    return ret


def val2float(v):
    ret = v
    if type(v) == str:
        ret = float(v)
    elif type(v) == int:
        ret = float(v)
    elif type(v) == float:
        ret = v

    return ret


def calc_nma_cie(r, cols):
    '''
    Calculate the CiE by the given record on the columns
    '''
    cie = 4
    for i in range(len(cols)):
        col = cols[i]

        if col not in r:
            # what??? why???
            continue

        val = r[col]

        # make sure the value type is int
        val = int(float('%s'%val))

        if val == 0:
            # not applicable
            pass

        elif val == 1:
            # not serious
            pass

        elif val == 2:
            # downgrade 1
            cie -= 1

        elif val == 3:
            # downgrade 2
            cie -= 2

        elif val == 4:
            # downgrade 3
            cie -= 3

        else:
            # what???
            pass

    # final check
    if cie <= 0: cie = 1

    return cie


def calc_pma_cie(r, cols):
    '''
    Calculate the CiE for PWMA
    '''
    return calc_nma_cie(r, cols)


def convert_extract_r_to_number(r, input_format):
    '''
    A helper function to change the values
    '''
    print("input format", input_format)
    if input_format == 'PRIM_CAT_RAW':
        for col in ['Et', 'Nt', 'Ec', 'Nc']:
            r[col] = val2int(r[col])

    elif input_format == 'PRIM_CAT_PRE':
        for col in ['TE', 'lowerci', 'upperci']:
            r[col] = val2float(r[col])

    elif input_format == 'NMA_PRE_SMLU':
        for col in ['sm', 'lowerci', 'upperci']:
            r[col] = val2float(r[col])

    elif input_format == 'NMA_RAW_ET':
        for col in ['event_t1', 'total_t1', 'event_t2', 'total_t2']:
            r[col] = val2int(r[col])

    else:
        pass

    # special rules for fixing
    if 'Et' in r:
        r['Et'] = val2int(r['Et'])
    
    if 'Ec' in r:
        r['Ec'] = val2int(r['Ec'])

    return r


def create_pr_rs_details(reason, decision):
    """
    Create detail_dict for the pr_rs for screening
    """
    detail_dict = {
        'date_decided': get_today_date_str(),
        'reason': reason,
        'decision': decision
    }

    return detail_dict


def create_ss_ex(reason, decision):
    '''
    Create empty info
    '''
    d = create_pr_rs_details(reason, decision)
    return d


def get_current_year_str():
    '''
    Get the current year string
    '''
    return datetime.datetime.now().strftime('%Y')


def get_concept_dict_from_concept_synonyms(concept_synonyms):
    '''
    Get the concept_dict from a concept_synonyms def
    The input concept_synonyms is:
    {
        concept_1: [
            concept_1_synonym_1,
            concept_1_synonym_2, 
            ...
        ],
        concept_2: []
    },

    The output concept_dict is:
    {
        concept_1_synonym_1: concept_1,
        concept_1_synonym_2: concept_1,
        ...
    }
    '''
    concept_dict = {}
    for cpt in concept_synonyms:
        for syn in concept_synonyms[cpt]:
            concept_dict[syn] = cpt

    return concept_dict


def print_something():
    '''
    Test functoin
    '''
    print('Something here')



###########################################################
# Printers for MA results in terminal
###########################################################

def print_cetable(cetable):
    '''
    Print CoE Table
    '''
    vs = [ _ for _ in cetable ]
    vs.sort()

    for c in vs:
        print(('* %s:'%c).ljust(32), end='')
        for t in vs:
            if c == t:
                print(' *', end='')
            else:
                if t in cetable[c]:
                    print(' %s'%cetable[c][t]['cie'], end='')
                else:
                    print(' -', end='')
        print('')


def print_rktable(rktable):
    '''
    Print rank table
    '''
    ranks = [ (tr, rktable[tr]) for tr in rktable ]
    ranks = sorted(
        ranks,
        key=lambda v: v[1]['rank'],
    )
    for rank in ranks:
        print(
            ('* %02d %s'%(rank[1]['rank'], rank[0])).ljust(32), 
            '%s' % rank[1]['score']
        )
        

def mk_graphdata_path(instance_path, keystr, cq_abbr):
    '''
    Make the path for saving graphdata
    '''
    full_path = os.path.join(
        instance_path, 
        settings.PUBLIC_PATH_PUBDATA, 
        keystr, 
        cq_abbr,
    )
    if os.path.exists(full_path):
        pass
    else:
        os.makedirs(full_path, exist_ok=True)
        print('* created folder %s' % full_path)

    return True

    
if __name__ == "__main__":
    fn = '/home/hehuan/Downloads/endnote_test.xml'
    fn = '/home/hehuan/Downloads/endnote_test_large.xml'
    fn = '/home/hehuan/Downloads/endnote_test_RCC.xml'
    papers, _ = parse_endnote_exported_xml(fn)
    # pprint(papers)
    json.dump(papers, open('%s.json' % fn, 'w'), indent=2)
    print('* done!')