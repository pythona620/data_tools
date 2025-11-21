frappe.pages['doctype_export'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'DocType Export',
		single_column: true
	});

	new DocTypeExportPage(page);
}

class DocTypeExportPage {
	constructor(page) {
		this.page = page;
		this.doctypes = [];
		this.selected_doctypes = [];
		this.make_page();
	}

	make_page() {
		this.page.main.html(`
			<div class="doctype-export-container">
				<div class="frappe-card">
					<div class="frappe-card-head">
						<h4>Export DocType Schemas</h4>
						<p class="text-muted small" style="margin: 5px 0 0 0;">
							Export only DocType definitions (schemas) without data. Use this to migrate DocType structures between sites.
						</p>
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
							<button class="btn btn-primary btn-sm" id="export-btn">
								<span class="fa fa-download"></span> Export DocTypes
							</button>
							<span id="export-status" class="text-muted" style="margin-left: 15px;"></span>
						</div>
					</div>
				</div>

				<div class="frappe-card" style="margin-top: 20px;">
					<div class="frappe-card-head">
						<h4>What is DocType Export?</h4>
					</div>
					<div class="frappe-card-body">
						<p>This tool exports <strong>only the DocType schemas/definitions</strong> without any data records. Use it when you need to:</p>
						<ul>
							<li>Migrate DocType structures from development to production</li>
							<li>Share custom DocType definitions with other Frappe installations</li>
							<li>Create templates of your data models</li>
							<li>Backup your custom DocType configurations</li>
						</ul>
						<p class="text-warning"><strong>Note:</strong> This does NOT export data records. Use "Partial Backup" if you need both schemas and data.</p>
					</div>
				</div>
			</div>
		`);

		this.load_apps();
		this.load_modules();
		this.load_doctypes();
		this.setup_handlers();
	}

	load_apps() {
		frappe.call({
			method: 'data_tools.data_tools.page.doctype_export.doctype_export.get_apps',
			callback: (r) => {
				if (r.message) {
					this.setup_app_filter(r.message);
				}
			}
		});
	}

	load_modules() {
		frappe.call({
			method: 'data_tools.data_tools.page.doctype_export.doctype_export.get_modules',
			callback: (r) => {
				if (r.message) {
					this.setup_module_filter(r.message);
				}
			}
		});
	}

	load_doctypes(app_filter = null, module_filter = null) {
		if (app_filter) {
			frappe.call({
				method: 'data_tools.data_tools.page.doctype_export.doctype_export.get_doctypes_by_app',
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
			frappe.call({
				method: 'data_tools.data_tools.page.doctype_export.doctype_export.get_all_doctypes',
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
		const wrapper = $('<div class="multiselect-wrapper"></div>');
		container.append(wrapper);

		this.create_manual_multiselect(wrapper, apps);
	}

	create_manual_multiselect(container, apps) {
		this.selected_apps = [];

		const html = `
			<div class="app-multiselect">
				<div class="form-control multiselect-input" style="height: auto; min-height: 38px; cursor: pointer;" id="app-multiselect-trigger">
					<span class="text-muted">Select Apps (click to open)</span>
				</div>
				<div class="multiselect-dropdown" id="app-multiselect-dropdown" style="display: none; position: absolute; z-index: 1000; background: white; border: 1px solid #d1d8dd; border-radius: 4px; max-height: 300px; overflow-y: auto; width: 100%; margin-top: 2px;">
					${apps.map(app => `
						<div class="checkbox" style="padding: 5px 10px; margin: 0;">
							<label style="font-weight: normal; margin: 0;">
								<input type="checkbox" class="app-checkbox" value="${app}">
								${app}
							</label>
						</div>
					`).join('')}
				</div>
			</div>
		`;

		container.html(html);

		container.find('#app-multiselect-trigger').on('click', () => {
			container.find('#app-multiselect-dropdown').toggle();
		});

		container.find('.app-checkbox').on('change', (e) => {
			const checkbox = $(e.target);
			const app = checkbox.val();

			if (checkbox.is(':checked')) {
				if (!this.selected_apps.includes(app)) {
					this.selected_apps.push(app);
				}
			} else {
				this.selected_apps = this.selected_apps.filter(a => a !== app);
			}

			this.update_multiselect_display(container);
			this.handle_app_filter_change();
		});

		$(document).on('click', (e) => {
			if (!$(e.target).closest('.app-multiselect').length) {
				container.find('#app-multiselect-dropdown').hide();
			}
		});
	}

	update_multiselect_display(container) {
		const trigger = container.find('#app-multiselect-trigger');
		if (this.selected_apps.length === 0) {
			trigger.html('<span class="text-muted">Select Apps (click to open)</span>');
		} else {
			const pills = this.selected_apps.map(app =>
				`<span class="badge" style="margin: 2px; background-color: #2490ef; color: white;">${app}</span>`
			).join('');
			trigger.html(pills);
		}
	}

	handle_app_filter_change() {
		const selected_apps = this.selected_apps || [];
		const app_filter = selected_apps && selected_apps.length > 0 ? selected_apps : null;
		const module = this.module_filter ? this.module_filter.get_value() : null;
		const module_filter = module === 'All Modules' ? null : module;
		this.load_doctypes(app_filter, module_filter);
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
					const selected_apps = this.selected_apps || [];
					const app_filter = selected_apps && selected_apps.length > 0 ? selected_apps : null;
					this.load_doctypes(app_filter, module);
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

			// Parent DocType
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

			// Child tables (indented under parent)
			if (d.has_child_tables && d.child_tables && d.child_tables.length > 0) {
				d.child_tables.forEach(child => {
					const child_html = `
						<div class="child-table-item" style="margin: 3px 0 3px 35px; padding-left: 10px; border-left: 2px solid #d1d8dd;">
							<span class="text-muted" style="font-size: 0.85em;">
								<i class="fa fa-table" style="margin-right: 5px;"></i>
								${child}
							</span>
						</div>
					`;
					container.append(child_html);
				});
			}
		});

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
		this.page.main.find('#export-btn').on('click', () => {
			this.export_doctypes();
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

	export_doctypes() {
		if (!this.selected_doctypes || this.selected_doctypes.length === 0) {
			frappe.msgprint(__('Please select at least one DocType'));
			return;
		}

		const status_elem = this.page.main.find('#export-status');
		status_elem.html('<span class="text-primary"><span class="fa fa-spinner fa-spin"></span> Exporting...</span>');

		frappe.call({
			method: 'data_tools.data_tools.page.doctype_export.doctype_export.export_doctypes',
			args: {
				doctypes: this.selected_doctypes
			},
			callback: (r) => {
				if (r.message && r.message.success) {
					const result = r.message;

					// Download the file
					const binary_data = atob(result.file_data);
					const array = new Uint8Array(binary_data.length);
					for (let i = 0; i < binary_data.length; i++) {
						array[i] = binary_data.charCodeAt(i);
					}

					const blob = new Blob([array], { type: 'application/zip' });
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
							Exported ${result.total_doctypes} DocType schemas successfully
						</span>`
					);

					frappe.show_alert({
						message: __('DocTypes exported successfully'),
						indicator: 'green'
					});
				} else {
					status_elem.html('<span class="text-danger">Export failed</span>');
				}
			},
			error: () => {
				status_elem.html('<span class="text-danger">Export failed</span>');
				frappe.msgprint(__('Error exporting DocTypes. Please check the error log.'));
			}
		});
	}
}
