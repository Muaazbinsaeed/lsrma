var fm_loader = {
    box: null,
    box_id: '#fm_loader',
    vpp: null,
    vpp_id: '#fm_loader',
    data: null,

    init: function() {
        this.vpp = new Vue({
            el: this.vpp_id,
            data: {
                btn_upload: {
                    disabled: false,
                    txt_normal: 'Upload',
                    txt_working: 'Uploading ...'
                },

                dataset_summary: '',
                multiple_subsheet:'' ,

                datasets: []
            },
            methods: {
                upload: function() {
                    fm_loader.upload_data_file();
                }
            }
        });
    },

    toggle_btn_upload: function() {
        this.vpp.btn_upload.disabled = !this.vpp.btn_upload.disabled;
    },

    set_dataset_summary: function(s) {
        this.vpp.dataset_summary = s;
    },

    set_multiple_subsheet: function(s) {
        this.vpp.multiple_subsheet = s;
    },

    upload_data_file: function() {
        // check file
        if ($('#ipt-csv-file').val() == '' && !(Cookies.get('analyzer_content'))) {
            return;
        }


        const searchParams = new URLSearchParams(window.location.search);
        standalone_page = searchParams.has('standalone');
        if (!(standalone_page)){
            var csvFile;
            var downloadLink;

            // CSV FILE
            form_data = new Blob([analyzer_content], {type: "text/csv"});
            const blob = new Blob([analyzer_content], { type: 'text/csv' });

            form_data = new FormData();
            form_data.append('file', blob, 'data.csv');
            // Cookies.set('analyzer_content', '')
    
        }
        else{
            var form_data = new FormData($('#upload-file')[0]);
        }

        // update UI
        this.vpp.btn_upload.disabled = true;
        sub_sheet = $('#multiple_sub_sheets').val();
        if ((sub_sheet)){
            form_data.append('sheet_selected', sub_sheet)
        }
        jarvis.clear_all();

        // send request
        $.ajax({
            type: 'POST',
            url: './read_file',
            data: form_data,
            contentType: false,
            cache: false,
            processData: false,
            success: function(data) {
                console.log(data);
                fm_loader.toggle_btn_upload();
                jarvis.on_read_data_file(data);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                console.error(textStatus, errorThrown);
            }
        });
    },
}