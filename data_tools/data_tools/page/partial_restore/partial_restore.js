frappe.pages['partial_restore'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Partial Restore',
		single_column: true
	});

	new PartialRestorePage(page);
}

class PartialRestorePage {
	constructor(page) {
		this.page = page;
		this.backup_data = null;
		this.file_data = null;
		this.filename = null;
		this.make_page();
	}

	make_page() {
		this.page.main.html(`
			<div class="partial-restore-container">
				<div class="frappe-card">
					<div class="frappe-card-head">
						<h4>Upload Backup File</h4>
					</div>
					<div class="frappe-card-body">
						<div class="form-group">
							<label>Select Backup File (.zip)</label>
							<div id="file-upload"></div>
						</div>
					</div>
				</div>

				<div class="frappe-card" id="preview-card" style="display: none; margin-top: 20px;">
					<div class="frappe-card-head">
						<h4>Backup Preview</h4>
					</div>
					<div class="frappe-card-body">
						<div id="backup-info"></div>
						<div id="doctype-list"></div>
						<div class="form-group" style="margin-top: 20px;">
							<button class="btn btn-primary btn-sm" id="restore-btn">
								<span class="fa fa-upload"></span> Restore Backup
							</button>
							<button class="btn btn-default btn-sm" id="cancel-btn">
								Cancel
							</button>
							<span id="restore-status" class="text-muted" style="margin-left: 15px;"></span>
						</div>
					</div>
				</div>

				<div class="frappe-card" id="log-card" style="display: none; margin-top: 20px;">
					<div class="frappe-card-head">
						<h4>Restore Log</h4>
					</div>
					<div class="frappe-card-body">
						<div id="restore-log"></div>
					</div>
				</div>
			</div>
		`);

		this.setup_file_upload();
		this.setup_handlers();
	}

	setup_file_upload() {
		const container = this.page.main.find('#file-upload');

		this.file_upload = frappe.ui.form.make_control({
			parent: container,
			df: {
				fieldtype: 'Attach',
				fieldname: 'backup_file',
				label: 'Backup File',
				onchange: () => {
					const file = this.file_upload.get_value();
					if (file) {
						this.handle_file_upload(file);
					}
				}
			},
			render_input: true
		});
	}

	handle_file_upload(file_url) {
		// Get file from the URL
		fetch(file_url)
			.then(response => response.blob())
			.then(blob => {
				const reader = new FileReader();
				reader.onload = (e) => {
					this.file_data = e.target.result;
					this.filename = file_url.split('/').pop();
					this.parse_backup_file();
				};
				reader.readAsDataURL(blob);
			})
			.catch(err => {
				frappe.msgprint(__('Error reading file: ' + err.message));
			});
	}

	parse_backup_file() {
		frappe.call({
			method: 'data_tools.data_tools.page.partial_restore.partial_restore.parse_backup_file',
			args: {
				file_data: this.file_data,
				filename: this.filename
			},
			freeze: true,
			freeze_message: __('Parsing backup file...'),
			callback: (r) => {
				if (r.message && r.message.success) {
					this.backup_data = r.message;
					this.show_preview();
				} else {
					frappe.msgprint(__('Error parsing backup file: ' + (r.message.error || 'Unknown error')));
				}
			}
		});
	}

	show_preview() {
		const backup_info = this.backup_data.backup_info;
		const doctypes = this.backup_data.doctypes;

		// Show backup info
		const info_html = `
			<div class="row">
				<div class="col-md-6">
					<p><strong>Created By:</strong> ${backup_info.created_by || 'Unknown'}</p>
					<p><strong>Creation Date:</strong> ${backup_info.creation_date || 'Unknown'}</p>
				</div>
				<div class="col-md-6">
					<p><strong>Frappe Version:</strong> ${backup_info.frappe_version || 'Unknown'}</p>
					<p><strong>Total Records:</strong> ${backup_info.total_records || 0}</p>
				</div>
			</div>
		`;
		this.page.main.find('#backup-info').html(info_html);

		// Show DocTypes table
		const table_html = `
			<table class="table table-bordered" style="margin-top: 15px;">
				<thead>
					<tr>
						<th>DocType</th>
						<th>Records</th>
					</tr>
				</thead>
				<tbody>
					${doctypes.map(dt => `
						<tr>
							<td>${dt.doctype}</td>
							<td>${dt.record_count}</td>
						</tr>
					`).join('')}
				</tbody>
				<tfoot>
					<tr>
						<th>Total: ${doctypes.length} DocTypes</th>
						<th>${doctypes.reduce((sum, dt) => sum + dt.record_count, 0)} Records</th>
					</tr>
				</tfoot>
			</table>
		`;
		this.page.main.find('#doctype-list').html(table_html);

		// Show preview card
		this.page.main.find('#preview-card').show();
	}

	setup_handlers() {
		this.page.main.find('#restore-btn').on('click', () => {
			this.restore_backup();
		});

		this.page.main.find('#cancel-btn').on('click', () => {
			this.reset();
		});
	}

	restore_backup() {
		frappe.confirm(
			__('Are you sure you want to restore this backup? This will import all records from the backup file.'),
			() => {
				const status_elem = this.page.main.find('#restore-status');
				status_elem.html('<span class="text-primary">Restoring backup...</span>');

				frappe.call({
					method: 'data_tools.data_tools.page.partial_restore.partial_restore.restore_backup',
					args: {
						file_data: this.file_data,
						filename: this.filename
					},
					freeze: true,
					freeze_message: __('Restoring backup... This may take a while.'),
					callback: (r) => {
						if (r.message && r.message.success) {
							const result = r.message;
							this.show_restore_log(result);

							status_elem.html(
								`<span class="text-success">
									<span class="fa fa-check"></span>
									Restore completed: ${result.summary.success} successful, ${result.summary.errors} errors
								</span>`
							);

							frappe.show_alert({
								message: __('Backup restored successfully'),
								indicator: 'green'
							});
						} else {
							status_elem.html('<span class="text-danger">Restore failed</span>');
							frappe.msgprint(__('Error restoring backup: ' + (r.message.error || 'Unknown error')));
						}
					},
					error: (r) => {
						status_elem.html('<span class="text-danger">Restore failed</span>');
						frappe.msgprint(__('Error restoring backup. Please check the error log.'));
					}
				});
			}
		);
	}

	show_restore_log(result) {
		const log_html = `
			<div class="restore-summary" style="margin-bottom: 20px;">
				<h5>Summary</h5>
				<p>
					<span class="badge" style="background-color: #28a745;">${result.summary.success} Successful</span>
					<span class="badge" style="background-color: #dc3545;">${result.summary.errors} Errors</span>
				</p>
			</div>
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>DocType</th>
						<th>Status</th>
						<th>Message</th>
					</tr>
				</thead>
				<tbody>
					${result.restore_log.map(log => `
						<tr>
							<td>${log.doctype}</td>
							<td>
								<span class="badge" style="background-color: ${this.get_status_color(log.status)};">
									${log.status}
								</span>
							</td>
							<td>${log.message}</td>
						</tr>
					`).join('')}
				</tbody>
			</table>
		`;

		this.page.main.find('#restore-log').html(log_html);
		this.page.main.find('#log-card').show();
	}

	get_status_color(status) {
		const colors = {
			'success': '#28a745',
			'error': '#dc3545',
			'warning': '#ffc107',
			'partial': '#fd7e14'
		};
		return colors[status] || '#6c757d';
	}

	reset() {
		this.backup_data = null;
		this.file_data = null;
		this.filename = null;
		this.page.main.find('#preview-card').hide();
		this.page.main.find('#log-card').hide();
		this.file_upload.set_value('');
	}
}
