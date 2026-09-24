/*
 * Setup view for ITSI Maintenance Window Management.
 * Reads and writes itsi_maintenance.conf [safety] via the splunkd web proxy
 * (works in Splunk Web, including Splunk Cloud - no :8089 access needed).
 * Loaded by default/data/ui/views/setup.xml via the dashboard "script" attribute.
 */
require([
    'jquery',
    'splunkjs/mvc',
    'splunkjs/mvc/simplexml/ready!'
], function ($, mvc) {
    'use strict';

    var APP = 'itsi_maintenance_window_management';
    var PATH = '/servicesNS/nobody/' + APP +
        '/configs/conf-itsi_maintenance/safety';

    var BOOL_FIELDS = [
        'default_dry_run', 'enable_delete', 'allow_cancel_active',
        'require_change_id', 'auto_split_mixed'
    ];
    var TEXT_FIELDS = [
        'allowed_operations', 'required_title_prefix',
        'max_duration_seconds', 'max_future_horizon_seconds',
        'max_objects_per_window', 'max_rows_per_invocation'
    ];

    var service = mvc.createService({ owner: 'nobody', app: APP });

    function status(msg, isError) {
        $('#imw-status')
            .text(msg)
            .css('color', isError ? '#a41515' : '#2b7a2b');
    }

    function isTrue(v) {
        return v === '1' || v === 'true' || v === true;
    }

    function load() {
        service.get(PATH, { output_mode: 'json' }, function (err, resp) {
            if (err) {
                status('Could not load settings (' +
                    (err.status || 'error') + ').', true);
                return;
            }
            var content = {};
            try {
                content = resp.data.entry[0].content || {};
            } catch (e) {
                content = {};
            }
            BOOL_FIELDS.forEach(function (f) {
                $('#' + f).prop('checked', isTrue(content[f]));
            });
            TEXT_FIELDS.forEach(function (f) {
                $('#' + f).val(content[f] == null ? '' : content[f]);
            });
        });
    }

    function save() {
        var data = {};
        BOOL_FIELDS.forEach(function (f) {
            data[f] = $('#' + f).is(':checked') ? '1' : '0';
        });
        TEXT_FIELDS.forEach(function (f) {
            data[f] = $.trim($('#' + f).val());
        });
        status('Saving...', false);
        service.post(PATH, data, function (err) {
            if (err) {
                status('Save failed (' + (err.status || 'error') +
                    '). You may lack write access to the app config.', true);
                return;
            }
            // Mark the app configured so setup is not forced again (best-effort).
            service.post('/services/apps/local/' + APP,
                { configured: '1' }, function () {});
            status('Saved. New settings apply to the next command run.', false);
        });
    }

    $('#imw-save').on('click', save);
    load();
});
