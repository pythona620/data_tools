// Copyright (c) 2025, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on('Backup Schedule', {
	refresh: function(frm) {
		// Add "Run Now" button if the schedule is enabled
		if (frm.doc.enabled && !frm.is_new()) {
			frm.add_custom_button(__('Run Now'), function() {
				frappe.confirm(
					__('Are you sure you want to run this backup now?'),
					function() {
						frappe.call({
							method: 'data_tools.data_tools.doctype.backup_schedule.backup_schedule.run_backup_now',
							args: {
								schedule_name: frm.doc.name
							},
							freeze: true,
							freeze_message: __('Running backup...'),
							callback: function(r) {
								if (r.message) {
									frm.reload_doc();
									frappe.show_alert({
										message: __('Backup completed successfully!'),
										indicator: 'green'
									});
								}
							}
						});
					}
				);
			}, __('Actions'));
		}

		// Show next run info if available
		if (frm.doc.next_run && frm.doc.enabled) {
			frm.dashboard.add_comment(
				__('Next scheduled run: {0}', [frappe.datetime.str_to_user(frm.doc.next_run)]),
				'blue',
				true
			);
		}

		// Show last run info if available
		if (frm.doc.last_run) {
			const indicator = frm.doc.last_status === 'Success' ? 'green' : 'red';
			frm.dashboard.add_comment(
				__('Last run: {0} - Status: {1}', [
					frappe.datetime.str_to_user(frm.doc.last_run),
					frm.doc.last_status || 'Unknown'
				]),
				indicator,
				true
			);
		}
	},

	frequency: function(frm) {
		// Clear dependent fields when frequency changes
		if (frm.doc.frequency !== 'Weekly') {
			frm.set_value('day_of_week', '');
		}
		if (frm.doc.frequency !== 'Monthly') {
			frm.set_value('day_of_month', '');
		}
		if (frm.doc.frequency !== 'Specific Date') {
			frm.set_value('specific_date', '');
		}
	}
});
