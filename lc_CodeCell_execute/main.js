define([
	'base/js/namespace',
	'jquery',
	'notebook/js/codecell'
], function(IPython, $, codecell) {
	"use strict";

	var CodeCell = codecell.CodeCell;

	var lc_CodeCell_execute = function() {
		/**
		 * Execute current code cell to the kernel
		 * @method execute
		 */
		CodeCell.prototype.execute = function (stop_on_error) {
			if (!this.kernel) {
				console.log("Can't execute cell since kernel is not set.");
				return;
			}

			if (!(this.metadata.run_control === undefined) && this.metadata.run_control.frozen) {
				console.log("Can't execute cell since cell is frozen.");
				return;
			}

			if (stop_on_error === undefined) {
				stop_on_error = true;
			}

			this.output_area.clear_output(false, true);
			var old_msg_id = this.last_msg_id;
			if (old_msg_id) {
				this.kernel.clear_callbacks_for_msg(old_msg_id);
				delete CodeCell.msg_cells[old_msg_id];
				this.last_msg_id = null;
			}
			if (this.get_text().trim().length === 0) {
				// nothing to do
				this.set_input_prompt(null);
				return;
			}
			this.set_input_prompt('*');
			this.element.addClass("running");
			var callbacks = this.get_callbacks();
			
			var options = {silent: false, store_history: true, stop_on_error : stop_on_error};
			var data = {
				"lc_cell_data" : {
					"lc_cell_meme" : this.metadata.lc_cell_meme
				}
			};
			$.extend(true, options, data);

			this.last_msg_id = this.kernel.execute(this.get_text(), callbacks, options);
			CodeCell.msg_cells[this.last_msg_id] = this;
			this.render();
			this.events.trigger('execute.CodeCell', {cell: this});
		};
	};
	return {
		load_jupyter_extension : lc_CodeCell_execute,
		load_ipython_extension : lc_CodeCell_execute
	};
});