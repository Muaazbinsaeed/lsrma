var srv_importer = {
    stage: {
        // view stage
        all_of_them: { title: 'All References' },
        decided: { title: 'Decided References' },

        // main stages
        unscreened: { title: 'Unscreened References' },
        passed_title_not_fulltext: { title: 'Full-text review' },
        excluded_by_title: { title: 'Excluded after checking title' },
        excluded_by_abstract: { title: 'Excluded after checking abstract' },
        excluded_by_fulltext: { title: 'Excluded after checking fulltext' },
        included_sr: { title: 'Included in SR' },
        included_srma: { title: 'Included in Both SR and MA' },
        
        // extended stages
        included_only_sr: { title: 'Included only in SR' },
        excluded_by_title_abstract: { title: 'Excluded after checking title and abstract' },
        excluded_by_rct_classifier: { title: 'Excluded by RCT classifier' },
    },

    url: {
        upload_endnote_xml: "[[ url_for('importer.upload_endnote_xml') ]]",
        import_one_pmid: "[[ url_for('importer.import_one_pmid') ]]",
        import_one_doi: "[[ url_for('importer.import_one_doi') ]]",
        save_papers: "[[ url_for('importer.save_papers') ]]",
        upload_user_input_manually: "[[ url_for('importer.upload_user_input_manually') ]]",
    },

    save_papers: function(papers, stage, project_id ,callback, onerror) {
        if (typeof(onerror) == 'undefined') {
            onerror = function(jqXHR, textStatus, errorThrown) {
                console.error(textStatus, errorThrown);
            }
        }
        if (project_id == undefined) {
            alert('Set working project first.');
            return;
        }
    
        // the form for saving papers
        var form_data = {
            project_id: project_id, 
            papers: JSON.stringify(papers), 
            stage: stage
        }

        // send the request
        // $.ajax({
        //     type: 'POST',
        //     url: this.url.save_papers,
        //     data: form_data,
        //     contentType: false,
        //     cache: false,
        //     processData: false,
        //     success: callback,
        //     error: onerror
        // });
        $.post(
            this.url.save_papers,
            {
                project_id:project_id, 
                papers: JSON.stringify(papers), 
                stage:stage
            },
            callback, 
            'json'
        );
    },

    upload_endnote_xml: function(form_data, callback) {
        // send request
        $.ajax({
            type: 'POST',
            url: this.url.upload_endnote_xml,
            data: form_data,
            contentType: false,
            cache: false,
            processData: false,
            success: callback,
            error: function(jqXHR, textStatus, errorThrown) {
                console.error(textStatus, errorThrown);
            }
        });
    },

    import_one_pmid: function(pmid, nct, callback) {
        var project_id = Cookies.get('project_id');
        if (project_id == undefined) {
            alert('Set working project first.');
            return;
        }
        // send request
        $.ajax({
            type: 'POST',
            url: this.url.import_one_pmid,
            dataType: "json",
            data: {
                pmid: pmid,
                nct: nct,
                project_id: project_id
            },
            cache: false,
            success: callback,
            error: function(jqXHR, textStatus, errorThrown) {
                console.error(textStatus, errorThrown);
            }
        });
    },

    import_one_doi: function(doi, nct, callback) {
        var project_id = Cookies.get('project_id');
        if (project_id == undefined) {
            alert('Set working project first.');
            return;
        }
        // send request
        $.ajax({
            type: 'POST',
            url: this.url.import_one_doi,
            dataType: "json",
            data: {
                doi: doi,
                nct: nct,
                project_id: project_id
            },
            cache: false,
            success: callback,
            error: function(jqXHR, textStatus, errorThrown) {
                console.error(textStatus, errorThrown);
            }
        });
    },

    upload_user_input_manually: function(pid, pid_type, title, authors, pub_date, journal, abstract, nct, callback) {
        var project_id = Cookies.get('project_id');
        if (project_id == undefined) {
            alert('Set working project first.');
            return;
        }
        // send request
        $.ajax({
            type: 'POST',
            url: this.url.upload_user_input_manually,
            dataType: "json",
            data: {
                pid: pid,
                pid_type: pid_type,
                title: title,
                authors: authors,
                pub_date: pub_date,
                journal: journal,
                abstract: abstract,
                nct: nct,
                project_id: project_id
            },
            cache: false,
            success: callback,
            error: function(jqXHR, textStatus, errorThrown) {
                console.error(textStatus, errorThrown);
            }
        });
    }
}