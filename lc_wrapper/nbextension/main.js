define([
    'jquery',
    'require',
    'base/js/namespace',
    'notebook/js/codecell'
], function($, require, Jupyter, codecell) {
    'use strict';

    function patch_CodeCell_get_callbacks() {
        console.log('[LC_wrapper] patching CodeCell.prototype.get_callbacks');
        var previous_get_callbacks = codecell.CodeCell.prototype.get_callbacks;
        codecell.CodeCell.prototype.get_callbacks = function() {
            var that = this;
            var callbacks = previous_get_callbacks.apply(this, arguments);
            var prev_reply_callback = callbacks.shell.reply;
            callbacks.shell.reply = function(msg) {
                if (msg.msg_type === 'execute_reply') {
                    console.log('[LC_wrapper] execute_reply');
                    record_log_path(that, msg);
                }
                return prev_reply_callback(msg);
            };
            return callbacks;
        };
    }

    function record_log_path(cell, msg) {
        var extmsg = msg['content']['lc_wrapper'];
        if(!extmsg) {
            return;
        }
        var logpath = extmsg['log_path']
        if(!logpath) {
            return;
        }
        var extmeta = cell.metadata['lc_wrapper']
        if(!extmeta) {
            extmeta = {};
        }
        var log_history = extmeta['log_history'];
        if (!log_history) {
            log_history = [];
        }
        log_history.push(logpath);
        extmeta['log_history'] = log_history;
        cell.metadata['lc_wrapper'] = extmeta;
    }

    function load_extension() {
        patch_CodeCell_get_callbacks();
    }

    return {
        load_ipython_extension: load_extension,
        load_jupyter_extension: load_extension
    };
});
