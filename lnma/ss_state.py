# for study screening import
SS_ST_BATCH_SEARCH       = 'b10'
SS_ST_BATCH_OTHER        = 'b12'
SS_ST_AUTO_SEARCH        = 'a10'
SS_ST_AUTO_EMAIL         = 'a11'
SS_ST_AUTO_OTHER         = 'a12'
SS_ST_IMPORT_ENDNOTE_XML = 'a21'
SS_ST_IMPORT_OVID_XML    = 'a22'
SS_ST_IMPORT_SIMPLE_CSV  = 'a23'
SS_ST_IMPORT_MANUAL      = 'a24'
SS_ST_NA                 = 'na'

# for study screening process
SS_PR_LOADED_META       = 'p10'
SS_PR_PASSED_TITLE      = 'p20'
SS_PR_CHECKED_FULLTEXT  = 'p30'
SS_PR_UPDATE_EXIST      = 'p40'
# SS_PR_CHECKED_UNIQUE    = 'p50'
SS_PR_CHECKED_SR        = 'p70'
# SS_PR_CHECKED_MA        = 'p80'
SS_PR_CHECKED_SRMA      = 'p90'
SS_PR_CHECKED_BY_ADMIN  = 'p99'
SS_PR_NA                = 'na'

# for study screening result of excluded
SS_RS_EXCLUDED_NOTFOUND = 'e00'
SS_RS_EXCLUDED_DUP      = 'e1'
SS_RS_EXCLUDED_TITLE    = 'e2'
SS_RS_EXCLUDED_RCT      = 'e21'
SS_RS_EXCLUDED_ABSTRACT = 'e22'
SS_RS_EXCLUDED_FULLTEXT = 'e3'
SS_RS_EXCLUDED_UPDATE   = 'e4'

# for study screening result of included
SS_RS_INCLUDED_ONLY_SR  = 'f1'
SS_RS_INCLUDED_ONLY_MA  = 'f2'
SS_RS_INCLUDED_SRMA     = 'f3'
SS_RS_NA                = 'na'

# ss types
SS_STAGE_ALL_OF_THEM = 'all_of_them'
SS_STAGE_UNSCREENED = 'unscreened'
SS_STATE_PASSED_TITLE_NOT_FULLTEXT = 'passed_title_not_fulltext'
SS_STAGE_EXCLUDED_BY_TITLE = 'excluded_by_title'
SS_STAGE_EXCLUDED_BY_ABSTRACT = 'excluded_by_abstract'
SS_STAGE_EXCLUDED_BY_TITLE_ABSTRACT = 'excluded_by_title_abstract'
SS_STAGE_EXCLUDED_BY_RCT_CLASSIFIER = 'excluded_by_rct_classifier'
SS_STAGE_EXCLUDED_BY_FULLTEXT = 'excluded_by_fulltext'
SS_STAGE_EXCLUDED_BY_FULLTEXT_INITIAL = 'excluded_by_fulltext_initial'
SS_STAGE_INCLUDED_ONLY_SR = 'included_only_sr'
SS_STAGE_INCLUDED_SR = 'included_sr'
SS_STAGE_INCLUDED_SR_INITIAL = 'included_sr_initial'
SS_STAGE_INCLUDED_SRMA = 'included_srma'
SS_STAGE_DECIDED = 'decided'
SS_STAGE_MANUAL = 'manual'

# RS -> Stage
SS_RS2STAGE = {
    SS_RS_EXCLUDED_TITLE: SS_STAGE_EXCLUDED_BY_TITLE,
    SS_RS_EXCLUDED_ABSTRACT: SS_STAGE_EXCLUDED_BY_ABSTRACT,
    SS_RS_INCLUDED_ONLY_SR: SS_STAGE_INCLUDED_SR,
    SS_RS_INCLUDED_SRMA: SS_STAGE_INCLUDED_SRMA,
}

# ss reason
SS_REASON_CHECKED_BY_ADMIN = "checked by admin"

# ss reason for unknown
SS_REASON_OTHER = 'Other'

# for screener
SS_STAGE_CONDITIONS = {
    'unscreened': "ss_pr = 'na' and ss_rs = 'na'"
}

# for stage -> pr + rs
SS_STAGE_TO_PR_AND_RS = {
    SS_STAGE_UNSCREENED: (SS_PR_NA, SS_RS_NA),
    
    SS_STATE_PASSED_TITLE_NOT_FULLTEXT: (SS_PR_PASSED_TITLE, SS_RS_NA),

    SS_STAGE_EXCLUDED_BY_TITLE: (SS_PR_NA, SS_RS_EXCLUDED_TITLE),
    SS_STAGE_EXCLUDED_BY_ABSTRACT: (SS_PR_NA, SS_RS_EXCLUDED_ABSTRACT),
    SS_STAGE_EXCLUDED_BY_FULLTEXT: (SS_PR_NA, SS_RS_EXCLUDED_FULLTEXT),

    SS_STAGE_INCLUDED_SR: (SS_PR_CHECKED_FULLTEXT, SS_RS_INCLUDED_ONLY_SR),
    SS_STAGE_INCLUDED_SRMA: (SS_PR_CHECKED_FULLTEXT, SS_RS_INCLUDED_SRMA)
}

# for labels
# label check later
SS_LABEL_CKL = 'CKL'
# label reviwer-confirmed decision
SS_LABEL_RFC = 'RFC'
# label reviwer disagree
SS_LABEL_DIS = 'DIS'