frappe.pages['partial_backup'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Partial Backup',
		single_column: true
	});

	new PartialBackupPage(page);
}

class PartialBackupPage {
	constructor(page) {
		this.page = page;
		this.doctypes = [];
		this.selected_doctypes = [];
		this.export_format = 'json'; // Default format
		this.make_page();
	}

	make_page() {
		this.page.main.html(`
			<div class="partial-backup-container">
				<div class="frappe-card">
					<div class="frappe-card-head">
						<h4>Select DocTypes for Backup</h4>
					</div>
					<div class="frappe-card-body">
						<div class="row">
							<div class="col-sm-6">
								<div class="form-group">
									<label>Filter by Apps (Multi-select)</label>
									<div id="app-filter"></div>
									<p class="help-box small text-muted">Select one or more apps to filter DocTypes</p>
								</div>
							</div>
							<div class="col-sm-6">
								<div class="form-group">
									<label>Filter by Module</label>
									<div id="module-filter"></div>
								</div>
							</div>
						</div>
						<div class="form-group">
							<label>Search DocTypes</label>
							<input type="text" class="form-control" id="doctype-search" placeholder="Type to search DocTypes...">
						</div>
						<div class="form-group">
							<label>
								Select DocTypes
								<span class="text-muted" id="selected-count">(0 selected)</span>
								<button class="btn btn-xs btn-default" id="select-all-btn" style="margin-left: 10px;">Select All</button>
								<button class="btn btn-xs btn-default" id="deselect-all-btn">Deselect All</button>
							</label>
							<div id="doctype-list" style="max-height: 400px; overflow-y: auto; border: 1px solid #d1d8dd; padding: 10px; border-radius: 4px; background: white;"></div>
						</div>
						<div class="form-group">
							<label>Export Format</label>
							<div id="export-format"></div>
						</div>
						<div class="form-group">
							<button class="btn btn-primary btn-sm" id="create-backup-btn">
								<span class="fa fa-download"></span> Create Backup
							</button>
							<span id="backup-status" class="text-muted" style="margin-left: 15px;"></span>
						</div>
					</div>
				</div>
			</div>
		`);

		this.load_apps();
		this.load_modules();
		this.load_doctypes();
		this.setup_export_format();
		this.setup_handlers();
	}

	load_apps() {
		frappe.call({
			method: 'data_tools.data_tools.page.partial_backup.partial_backup.get_apps',
			callback: (r) => {
				if (r.message) {
					this.setup_app_filter(r.message);
				}
			}
		});
	}

	load_modules() {
		frappe.call({
			method: 'data_tools.data_tools.page.partial_backup.partial_backup.get_modules',
			callback: (r) => {
				if (r.message) {
					this.setup_module_filter(r.message);
				}
			}
		});
	}

	load_doctypes(app_filter = null, module_filter = null) {
		if (app_filter) {
			// Load DocTypes by app(s)
			// app_filter can be an array of apps or a single app string
			frappe.call({
				method: 'data_tools.data_tools.page.partial_backup.partial_backup.get_doctypes_by_app',
				args: {
					app_names: Array.isArray(app_filter) ? JSON.stringify(app_filter) : app_filter
				},
				callback: (r) => {
					if (r.message) {
						this.doctypes = r.message;
						this.filtered_doctypes = module_filter
							? this.doctypes.filter(d => d.module === module_filter)
							: this.doctypes;
						this.setup_doctype_list();
					}
				}
			});
		} else {
			// Load all DocTypes
			frappe.call({
				method: 'data_tools.data_tools.page.partial_backup.partial_backup.get_all_doctypes',
				callback: (r) => {
					if (r.message) {
						this.doctypes = r.message;
						this.filtered_doctypes = module_filter
							? this.doctypes.filter(d => d.module === module_filter)
							: this.doctypes;
						this.setup_doctype_list();
					}
				}
			});
		}
	}

	setup_app_filter(apps) {
		const container = this.page.main.find('#app-filter');

		this.app_filter = frappe.ui.form.make_control({
			parent: container,
			df: {
				fieldtype: 'MultiSelect',
				fieldname: 'app',
				options: apps.map(app => ({label: app, value: app})),
				placeholder: 'Select Apps (All if empty)',
				onchange: () => {
					const selected_apps = this.app_filter.get_value();
					// If no apps selected, pass null to load all
					const app_filter = selected_apps && selected_apps.length > 0 ? selected_apps : null;
					const module = this.module_filter ? this.module_filter.get_value() : null;
					const module_filter = module === 'All Modules' ? null : module;
					this.load_doctypes(app_filter, module_filter);
				}
			},
			render_input: true
		});
	}

	setup_module_filter(modules) {
		const container = this.page.main.find('#module-filter');

		this.module_filter = frappe.ui.form.make_control({
			parent: container,
			df: {
				fieldtype: 'Select',
				fieldname: 'module',
				options: ['All Modules', ...modules],
				default: 'All Modules',
				onchange: () => {
					const selected_module = this.module_filter.get_value();
					const module = selected_module === 'All Modules' ? null : selected_module;
					const selected_apps = this.app_filter ? this.app_filter.get_value() : null;
					// If no apps selected or empty array, pass null to load all
					const app_filter = selected_apps && selected_apps.length > 0 ? selected_apps : null;
					this.load_doctypes(app_filter, module);
				}
			},
			render_input: true
		});
	}

	setup_export_format() {
		const container = this.page.main.find('#export-format');

		this.export_format_control = frappe.ui.form.make_control({
			parent: container,
			df: {
				fieldtype: 'Select',
				fieldname: 'export_format',
				options: [
					{label: 'JSON (Metadata with records)', value: 'json'},
					{label: 'SQL (Database dump)', value: 'sql'}
				],
				default: 'json',
				onchange: () => {
					this.export_format = this.export_format_control.get_value();
				}
			},
			render_input: true
		});
	}

	setup_doctype_list() {
		const container = this.page.main.find('#doctype-list');
		container.empty();

		const search_input = this.page.main.find('#doctype-search');
		const search_term = search_input.length ? search_input.val().toLowerCase() : '';

		const filtered = this.filtered_doctypes.filter(d =>
			!search_term || d.name.toLowerCase().includes(search_term)
		);

		if (filtered.length === 0) {
			container.html('<p class="text-muted">No DocTypes found</p>');
			return;
		}

		filtered.forEach(d => {
			const is_checked = this.selected_doctypes.includes(d.name);
			const checkbox_html = `
				<div class="checkbox" style="margin: 5px 0;">
					<label style="display: flex; align-items: center;">
						<input type="checkbox"
							class="doctype-checkbox"
							data-doctype="${d.name}"
							${is_checked ? 'checked' : ''}>
						<span style="margin-left: 8px;">
							<strong>${d.name}</strong>
							<span class="text-muted" style="margin-left: 8px; font-size: 0.9em;">
								${d.module}${d.is_custom ? ' (Custom)' : ''}${d.is_single ? ' [Single]' : ''}
							</span>
						</span>
					</label>
				</div>
			`;
			container.append(checkbox_html);
		});

		// Update selected doctypes when checkboxes change
		container.find('.doctype-checkbox').on('change', (e) => {
			const doctype = $(e.target).data('doctype');
			if (e.target.checked) {
				if (!this.selected_doctypes.includes(doctype)) {
					this.selected_doctypes.push(doctype);
				}
			} else {
				this.selected_doctypes = this.selected_doctypes.filter(dt => dt !== doctype);
			}
			this.update_selected_count();
		});

		this.update_selected_count();
	}

	update_selected_count() {
		this.page.main.find('#selected-count').text(`(${this.selected_doctypes.length} selected)`);
	}

	setup_handlers() {
		this.page.main.find('#create-backup-btn').on('click', () => {
			this.create_backup();
		});

		this.page.main.find('#select-all-btn').on('click', () => {
			this.selected_doctypes = this.filtered_doctypes.map(d => d.name);
			this.setup_doctype_list();
		});

		this.page.main.find('#deselect-all-btn').on('click', () => {
			this.selected_doctypes = [];
			this.setup_doctype_list();
		});

		this.page.main.find('#doctype-search').on('input', () => {
			this.setup_doctype_list();
		});
	}

	create_backup() {
		if (!this.selected_doctypes || this.selected_doctypes.length === 0) {
			frappe.msgprint(__('Please select at least one DocType'));
			return;
		}

		const status_elem = this.page.main.find('#backup-status');
		status_elem.html('<span class="text-primary">Creating backup...</span>');

		frappe.call({
			method: 'data_tools.data_tools.page.partial_backup.partial_backup.create_partial_backup',
			args: {
				doctypes: this.selected_doctypes,
				export_format: this.export_format
			},
			freeze: true,
			freeze_message: __('Creating backup...'),
			callback: (r) => {
				if (r.message && r.message.success) {
					const result = r.message;

					// Download the file
					const binary_data = atob(result.file_data);
					const array = new Uint8Array(binary_data.length);
					for (let i = 0; i < binary_data.length; i++) {
						array[i] = binary_data.charCodeAt(i);
					}

					// Set correct MIME type based on export format
					const mime_type = this.export_format === 'sql'
						? 'application/sql'
						: 'application/zip';
					const blob = new Blob([array], { type: mime_type });
					const url = window.URL.createObjectURL(blob);
					const a = document.createElement('a');
					a.href = url;
					a.download = result.filename;
					document.body.appendChild(a);
					a.click();
					document.body.removeChild(a);
					window.URL.revokeObjectURL(url);

					status_elem.html(
						`<span class="text-success">
							<span class="fa fa-check"></span>
							Backup created: ${result.total_doctypes} DocTypes, ${result.total_records} records
						</span>`
					);

					frappe.show_alert({
						message: __('Backup downloaded successfully'),
						indicator: 'green'
					});
				}
			},
			error: () => {
				status_elem.html('<span class="text-danger">Backup failed</span>');
				frappe.msgprint(__('Error creating backup. Please check the error log.'));
			}
		});
	}
}
