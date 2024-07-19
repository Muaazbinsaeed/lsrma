var srv_pub = {
    url: {
        itable: "[[ url_for('pub.itable') ]]",

        mkjson_prisma_json: "[[ url_for('pub.mkjson_prisma_json') ]]",
        mkjson_itable_json: "[[ url_for('pub.mkjson_itable_json') ]]",

        mkjson_graph_nma_json: "[[ url_for('pub.mkjson_graph_nma_json') ]]",
        mkjson_softable_nma_json: "[[ url_for('pub.mkjson_softable_nma_json') ]]",

        mkjson_graph_pwma_json: "[[ url_for('pub.mkjson_graph_pwma_json') ]]",
        mkjson_softable_pwma_json: "[[ url_for('pub.mkjson_softable_pwma_json') ]]",

        mkjson_evmap_json: "[[ url_for('pub.mkjson_evmap_json') ]]",
    },

    goto_itable: function(prj) {
        location.href = this.url.itable + '?prj=' + prj;
    },

    mkjson_prisma_json: function(keystr, cq_abbr, callback) {
        $.ajax({
            type: 'GET',
            dataType: 'json',
            url: this.url.mkjson_prisma_json,
            data: {
                k: keystr, 
                c: cq_abbr, 
            },
            cache: false,
            success: callback,
            error: function(jqXHR, textStatus, errorThrown) {
                jarvis.toast('Something wrong when making PRISMA.json.', 'alert');
                console.error(textStatus, errorThrown);
            }
        });
    },

    mkjson_itable_json: function(keystr, cq_abbr, callback) {
        $.ajax({
            type: 'GET',
            dataType: 'json',
            url: this.url.mkjson_itable_json,
            data: {
                k: keystr, 
                c: cq_abbr, 
            },
            cache: false,
            success: callback,
            error: function(jqXHR, textStatus, errorThrown) {
                jarvis.toast('Something wrong when making ITABLE.json.', 'alert');
                console.error(textStatus, errorThrown);
            }
        });
    },

    mkjson_graph_nma_json: function(keystr, cq_abbr, callback) {
        $.ajax({
            type: 'GET',
            dataType: 'json',
            url: this.url.mkjson_graph_nma_json,
            data: {
                k: keystr, 
                c: cq_abbr, 
            },
            cache: false,
            success: callback,
            error: function(jqXHR, textStatus, errorThrown) {
                jarvis.toast('Something wrong when making GRAPH_NMA.json.', 'alert');
                console.error(textStatus, errorThrown);
            }
        });
    },

    mkjson_softable_nma_json: function(keystr, cq_abbr, callback) {
        $.ajax({
            type: 'GET',
            dataType: 'json',
            url: this.url.mkjson_softable_nma_json,
            data: {
                k: keystr, 
                c: cq_abbr, 
            },
            cache: false,
            success: callback,
            error: function(jqXHR, textStatus, errorThrown) {
                jarvis.toast('Something wrong when making SOFTABLE_NMA.json.', 'alert');
                console.error(textStatus, errorThrown);
            }
        });
    },

    mkjson_graph_pwma_json: function(keystr, cq_abbr, callback) {
        $.ajax({
            type: 'GET',
            dataType: 'json',
            url: this.url.mkjson_graph_pwma_json,
            data: {
                k: keystr, 
                c: cq_abbr, 
            },
            cache: false,
            success: callback,
            error: function(jqXHR, textStatus, errorThrown) {
                jarvis.toast('Something wrong when making GRAPH_PMA.json.', 'alert');
                console.error(textStatus, errorThrown);
            }
        });
    },

    mkjson_softable_pwma_json: function(keystr, cq_abbr, callback) {
        $.ajax({
            type: 'GET',
            dataType: 'json',
            url: this.url.mkjson_softable_pwma_json,
            data: {
                k: keystr, 
                c: cq_abbr, 
            },
            cache: false,
            success: callback,
            error: function(jqXHR, textStatus, errorThrown) {
                jarvis.toast('Something wrong when making SOFTABLE_PMA.json.', 'alert');
                console.error(textStatus, errorThrown);
            }
        });
    },

    mkjson_evmap_json: function(keystr, cq_abbr, callback) {
        $.ajax({
            type: 'GET',
            dataType: 'json',
            url: this.url.mkjson_evmap_json,
            data: {
                k: keystr, 
                c: cq_abbr, 
            },
            cache: false,
            success: callback,
            error: function(jqXHR, textStatus, errorThrown) {
                jarvis.toast('Something wrong when making EVMAP.json.', 'alert');
                console.error(textStatus, errorThrown);
            }
        });
    },
};