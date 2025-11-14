frappe.pages['doctype_import'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'DocType Import',
		single_column: true
	});

	new DocTypeImportPage(page);
}

class DocTypeImportPage {
	constructor(page) {
		this.page = page;
		this.file_data = null;
		this.filename = null;
		this.preview_data = null;
		this.selected_doctypes = [];
		this.make_page();
	}

	make_page() {
		this.page.main.html(`
			<div class="doctype-import-container">
				<div class="frappe-card">
					<div class="frappe-card-head">
						<h4>Import DocType Schemas</h4>
						<p class="text-muted small" style="margin: 5px 0 0 0;">
							Import DocType definitions (schemas) from an export file. This will create or update DocTypes without importing data.
						</p>
					</div>
					<div class="frappe-card-body">
						<div class="form-group">
							<label>Upload Export File</label>
							<div id="file-upload-area"></div>
							<p class="help-box small text-muted">Upload a DocType export ZIP file created using the DocType Export page</p>
						</div>
						<div id="preview-section" style="display: none; margin-top: 20px;">
							<h5>Export File Preview</h5>
							<div id="export-info"></div>
							<div id="doctype-list-preview" style="margin-top: 15px;"></div>
							<div class="form-group" style="margin-top: 20px;">
								<button class="btn btn-primary btn-sm" id="import-btn">
									<span class="fa fa-upload"></span> Import Selected DocTypes
								</button>
								<span id="import-status" class="text-muted" style="margin-left: 15px;"></span>
							</div>
						</div>
						<div id="import-log-section" style="display: none; margin-top: 20px;">
							<h5>Import Log</h5>
							<div id="import-log"></div>
						</div>
					</div>
				</div>

				<div class="frappe-card" style="margin-top: 20px;">
					<div class="frappe-card-head">
						<h4>What is DocType Import?</h4>
					</div>
					<div class="frappe-card-body">
						<p>This tool imports <strong>only the DocType schemas/definitions</strong> without any data records. Use it when you need to:</p>
						<ul>
							<li>Import DocType structures from another Frappe installation</li>
							<li>Create new custom DocTypes from exported templates</li>
							<li>Update existing custom DocType definitions</li>
							<li>Restore DocType configurations from backups</li>
						</ul>
						<div class="alert alert-warning">
							<strong>Important Notes:</strong>
							<ul>
								<li>Standard (non-custom) DocTypes will be skipped to prevent system issues</li>
								<li>Custom DocTypes will be created if they don't exist, or updated if they do</li>
								<li>This does NOT import data records - only DocType structures</li>
								<li>Always test imports on a development site first</li>
							</ul>
						</div>
					</div>
				</div>
			</div>
		`);

		this.setup_file_upload();
	}

	setup_file_upload() {
		const container = this.page.main.find('#file-upload-area');

		this.file_upload = frappe.ui.form.make_control({
			parent: container,
			df: {
				fieldtype: 'Attach',
				fieldname: 'export_file',
				label: 'Upload Export File',
				onchange: () => {
					this.handle_file_upload();
				}
			},
			render_input: true
		});
	}

	handle_file_upload() {
		const file_url = this.file_upload.get_value();

		if (!file_url) {
			return;
		}

		// Get filename from URL
		this.filename = file_url.split('/').pop();

		// Read file content
		frappe.call({
			method: 'frappe.client.get_file',
			args: {
				file_url: file_url
			},
			callback: (r) => {
				if (r.message) {
					// Store the base64 file data
					this.file_data = r.message;

					// Parse and preview the file
					this.parse_file();
				}
			}
		});
	}

	parse_file() {
		frappe.call({
			method: 'data_tools.data_tools.page.doctype_import.doctype_import.parse_export_file',
			args: {
				file_data: this.file_data,
				filename: this.filename
			},
			callback: (r) => {
				if (r.message && r.message.success) {
					this.preview_data = r.message.preview;
					this.show_preview();
				} else {
					frappe.msgprint(__('Error parsing export file'));
				}
			},
			error: (r) => {
				frappe.msgprint(__('Error parsing export file: {0}', [r.message || 'Unknown error']));
			}
		});
	}

	show_preview() {
		const preview_section = this.page.main.find('#preview-section');
		preview_section.show();

		// Show export info
		const export_info = this.preview_data.export_info;
		const info_html = `
			<div class="alert alert-info">
				<table class="table table-bordered" style="margin: 0; background: white;">
					<tr>
						<th style="width: 200px;">Created By</th>
						<td>${export_info.created_by}</td>
					</tr>
					<tr>
						<th>Creation Date</th>
						<td>${export_info.creation_date}</td>
					</tr>
					<tr>
						<th>Frappe Version</th>
						<td>${export_info.frappe_version}</td>
					</tr>
					<tr>
						<th>Total DocTypes</th>
						<td>${export_info.total_doctypes}</td>
					</tr>
					<tr>
						<th>Export Type</th>
						<td><span class="badge" style="background-color: #3498db; color: white;">${export_info.export_type}</span></td>
					</tr>
				</table>
			</div>
		`;
		this.page.main.find('#export-info').html(info_html);

		// Show DocType list
		const doctypes = this.preview_data.doctypes;
		let list_html = `
			<div style="border: 1px solid #d1d8dd; border-radius: 4px; padding: 10px; background: white;">
				<div style="margin-bottom: 10px;">
					<button class="btn btn-xs btn-default" id="select-all-import-btn">Select All</button>
					<button class="btn btn-xs btn-default" id="deselect-all-import-btn">Deselect All</button>
					<span class="text-muted" id="import-selected-count" style="margin-left: 10px;">(0 selected)</span>
				</div>
				<div id="import-doctype-list" style="max-height: 400px; overflow-y: auto;">
		`;

		doctypes.forEach(dt => {
			const status_class = dt.exists ? 'text-warning' : 'text-success';
			const status_icon = dt.exists ? 'fa-refresh' : 'fa-plus';

			list_html += `
				<div class="checkbox" style="margin: 5px 0;">
					<label style="display: flex; align-items: center;">
						<input type="checkbox" class="import-doctype-checkbox" data-doctype="${dt.doctype}" checked>
						<span style="margin-left: 8px;">
							<strong>${dt.doctype}</strong>
							<span class="text-muted" style="margin-left: 8px; font-size: 0.9em;">
								${dt.module}${dt.is_custom ? ' (Custom)' : ' (Standard)'}${dt.is_single ? ' [Single]' : ''}
							</span>
							<span class="${status_class}" style="margin-left: 8px;">
								<i class="fa ${status_icon}"></i> ${dt.status}
							</span>
						</span>
					</label>
				</div>
			`;
		});

		list_html += `
				</div>
			</div>
		`;

		this.page.main.find('#doctype-list-preview').html(list_html);

		// Initialize selected doctypes with all
		this.selected_doctypes = doctypes.map(dt => dt.doctype);
		this.update_import_selected_count();

		// Setup handlers
		this.page.main.find('.import-doctype-checkbox').on('change', (e) => {
			const doctype = $(e.target).data('doctype');
			if (e.target.checked) {
				if (!this.selected_doctypes.includes(doctype)) {
					this.selected_doctypes.push(doctype);
				}
			} else {
				this.selected_doctypes = this.selected_doctypes.filter(dt => dt !== doctype);
			}
			this.update_import_selected_count();
		});

		this.page.main.find('#select-all-import-btn').on('click', () => {
			this.selected_doctypes = doctypes.map(dt => dt.doctype);
			this.page.main.find('.import-doctype-checkbox').prop('checked', true);
			this.update_import_selected_count();
		});

		this.page.main.find('#deselect-all-import-btn').on('click', () => {
			this.selected_doctypes = [];
			this.page.main.find('.import-doctype-checkbox').prop('checked', false);
			this.update_import_selected_count();
		});

		this.page.main.find('#import-btn').on('click', () => {
			this.import_doctypes();
		});
	}

	update_import_selected_count() {
		this.page.main.find('#import-selected-count').text(`(${this.selected_doctypes.length} selected)`);
	}

	import_doctypes() {
		if (!this.selected_doctypes || this.selected_doctypes.length === 0) {
			frappe.msgprint(__('Please select at least one DocType to import'));
			return;
		}

		const status_elem = this.page.main.find('#import-status');
		status_elem.html('<span class="text-primary"><span class="fa fa-spinner fa-spin"></span> Importing...</span>');

		frappe.call({
			method: 'data_tools.data_tools.page.doctype_import.doctype_import.import_doctypes',
			args: {
				file_data: this.file_data,
				filename: this.filename,
				selected_doctypes: this.selected_doctypes
			},
			callback: (r) => {
				if (r.message && r.message.success) {
					const result = r.message;

					status_elem.html(
						`<span class="text-success">
							<span class="fa fa-check"></span>
							Import completed: ${result.summary.success} success, ${result.summary.errors} errors, ${result.summary.skipped} skipped
						</span>`
					);

					// Show import log
					this.show_import_log(result.import_log, result.summary);

					frappe.show_alert({
						message: __('DocTypes imported successfully'),
						indicator: 'green'
					});
				} else {
					status_elem.html('<span class="text-danger">Import failed</span>');
				}
			},
			error: (r) => {
				status_elem.html('<span class="text-danger">Import failed</span>');
				frappe.msgprint(__('Error importing DocTypes: {0}', [r.message || 'Unknown error']));
			}
		});
	}

	show_import_log(import_log, summary) {
		const log_section = this.page.main.find('#import-log-section');
		log_section.show();

		let log_html = `
			<div class="alert alert-info">
				<h5>Import Summary</h5>
				<ul>
					<li>Total: ${summary.total}</li>
					<li>Success: <span class="text-success">${summary.success}</span></li>
					<li>Errors: <span class="text-danger">${summary.errors}</span></li>
					<li>Skipped: <span class="text-warning">${summary.skipped}</span></li>
				</ul>
			</div>
			<div style="border: 1px solid #d1d8dd; border-radius: 4px; padding: 10px; background: white; max-height: 400px; overflow-y: auto;">
		`;

		import_log.forEach(log => {
			let status_class = 'text-muted';
			let icon = 'fa-info-circle';

			if (log.status === 'success') {
				status_class = 'text-success';
				icon = 'fa-check';
			} else if (log.status === 'error') {
				status_class = 'text-danger';
				icon = 'fa-times';
			} else if (log.status === 'skipped') {
				status_class = 'text-warning';
				icon = 'fa-exclamation-triangle';
			}

			log_html += `
				<div style="padding: 8px; border-bottom: 1px solid #f0f0f0;">
					<span class="${status_class}">
						<i class="fa ${icon}"></i>
						<strong>${log.doctype}</strong>
						[${log.action}]
					</span>
					<br>
					<span class="text-muted small">${log.message}</span>
				</div>
			`;
		});

		log_html += '</div>';

		this.page.main.find('#import-log').html(log_html);
	}
}
