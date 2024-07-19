import os

from . import make_page
from . import make_folders
from . import copy_static_files
from . import copy_graphdata_files
from . import copy_all_graphdata_files

# app settings
from lnma import db, create_app
from lnma.models import *


def kacha(keystr, cq_abbr, output_path, prefix=''):
    '''
    Take a snapshot for general project
    '''

    # app for using LNMA functions and tables
    app = create_app()

    if prefix != '':
        app.config['APPLICATION_ROOT'] = prefix
        print('* set app.config["APPLICATION_ROOT"]=%s' % (
            app.config['APPLICATION_ROOT']
        ))
    else:
        print('* using default APPLICATION_ROOT=%s' % (
            app.config['APPLICATION_ROOT']
        ))

    db.init_app(app)
    app.app_context().push()
    print('* inited the app env')

    # first, make the folders
    make_folders(
        keystr, 
        cq_abbr, 
        output_path,
        prefix
    )

    pcq_output_path = os.path.join(
        output_path, 
        keystr, 
        cq_abbr,
        prefix
    )

    # second, copy static files
    copy_static_files(keystr, cq_abbr, pcq_output_path, [
        'lib/d3',
        'lib/file-saver'
    ])
    
    # third, copy the graph data
    # copy_graphdata_files(
    #     keystr, 
    #     cq_abbr,
    #     pcq_output_path, 
    #     [
    #         'CONCEPT_IMAGE.svg',
    #         'CONCEPT_IMAGE_UPDATED.svg',
    #         'file', # a folder for other files
    #     ]
    # )
    
    # third, copy the graph data
    copy_all_graphdata_files(
        keystr, 
        cq_abbr,
        pcq_output_path, 
    )
    
    # special pages
    rules = [
        # the basic home page
        ['HOMEPAGE [%s.%s]' % (keystr, cq_abbr), '/pub/php.html?k=%s&c=%s' % (keystr, cq_abbr), 'index.html'],

        # for the PRISMA
        ['PRISMA PAGE', '/pub/prisma_hybrid.html?prj=%s&cq=%s' % (keystr, cq_abbr), 'pub/prisma_hybrid.html'],
        ['PRISMA PAGE', '/pub/prisma_living.html?prj=%s&cq=%s' % (keystr, cq_abbr), 'pub/prisma_living.html'],
        ['PRISMA.json', '/pub/graphdata/%s/PRISMA.json?src=cache&cq=%s' % (keystr, cq_abbr), 'pub/graphdata/%s/PRISMA.json' % (keystr)],

        # for the itable
        ['ITABLE PAGE', '/pub/itable.html?prj=%s&src=cache' % (keystr), 'pub/itable.html'],
        ['ITABLE.json', '/pub/graphdata/%s/ITABLE.json?src=cache&cq=%s' % (keystr, cq_abbr), 'pub/graphdata/%s/ITABLE.json' % (keystr)],

        # for the pwma plots
        ['PWMA PLOTS PAGE', '/pub/graph_pma.html?src=cache&prj=%s&cq=%s' % (keystr, cq_abbr), 'pub/graph_pma.html'],
        ['PWMA PLOTS DATA', '/pub/graphdata/%s/GRAPH_PMA.json?src=cache&cq=%s' % (keystr, cq_abbr), 'pub/graphdata/%s/GRAPH_PMA.json' % (keystr)],

        # for the pwma softable
        ['PWMA SOFTABLE PAGE', '/pub/softable_pma.html?src=cache&prj=%s&cq=%s' % (keystr, cq_abbr), 'pub/softable_pma.html'],
        ['PWMA SOFTABLE DATA', '/pub/graphdata/%s/SOFTABLE_PMA.json?src=cache&cq=%s' % (keystr, cq_abbr), 'pub/graphdata/%s/SOFTABLE_PMA.json' % (keystr)],

        # for the nma plots
        ['NMA PLOTS PAGE', '/pub/graph_nma.html?src=cache&prj=%s&cq=%s' % (keystr, cq_abbr), 'pub/graph_nma.html'],
        ['NMA PLOTS DATA', '/pub/graphdata/%s/GRAPH_NMA.json?src=cache&cq=%s' % (keystr, cq_abbr), 'pub/graphdata/%s/GRAPH_NMA.json' % (keystr)],

        # for the nma softable
        ['NMA SOFTABLE PAGE', '/pub/softable_nma.html?src=cache&prj=%s&cq=%s' % (keystr, cq_abbr), 'pub/softable_nma.html'],
        ['NMA SOFTABLE DATA', '/pub/graphdata/%s/SOFTABLE_NMA.json?src=cache&cq=%s' % (keystr, cq_abbr), 'pub/graphdata/%s/SOFTABLE_NMA.json' % (keystr)],

        # for the evmap
        ['EVMAP PAGE', '/pub/evmap.html?src=cache&prj=%s&cq=%s' % (keystr, cq_abbr), 'pub/evmap.html'],
        ['EVMAP DATA', '/pub/graphdata/%s/EVMAP.json?src=cache&cq=%s' % (keystr, cq_abbr), 'pub/graphdata/%s/EVMAP.json' % (keystr)],

        # for the latest update
        ['LATEST DATE', '/pub/graphdata/%s/LATEST.json' % (keystr), 'pub/graphdata/%s/LATEST.json' % (keystr)],

        # for the decision aid
        ['DECISION AID', '/pub/decision_aid.html?k=%s&c=%s' % (keystr, cq_abbr), 'pub/decision_aid.html'],

        # other static pages
        ['METHODS', '/pub/methods.html', 'pub/methods.html']
    ]

    # the root path for output
    # pathlib.Path(__file__).parent.absolute()

    # download each page / data
    with app.test_client() as client:
        with app.app_context():
            for rule in rules:
                print('*'*80)
                print('* MAKING - %s' % rule[0])
                # create the file name for this rule
                full_fn = os.path.join(
                    pcq_output_path,
                    rule[2]
                )

                # make page or download the data for this rule
                make_page(client, rule[1], full_fn)

    print('* done building static pages')