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
		this.include_files = false; // Include file attachments
		this.field_transformations = []; // Field transformations
		this.table_transformations = []; // Table name transformations
		this.selected_apps = []; // Selected apps for filtering
		this.selected_modules = []; // Selected modules for filtering
		this.job_id = null; // Track background job
		this.make_page();
	}

	make_page() {
		// Add "Manage Schedules" button to page header
		this.page.add_inner_button('Manage Backup Schedules', () => {
			frappe.set_route('List', 'Backup Schedule');
		});

		// Add "CLI Help" button
		this.page.add_inner_button('CLI Backup Commands', () => {
			this.show_cli_help();
		});

		this.page.main.html(`
			<div class="partial-backup-container">
				<div class="frappe-card">
					<div class="frappe-card-head">
						<h4>Select DocTypes for Backup</h4>
						<p class="text-muted small" style="margin: 5px 0 0 0;">
							Create an immediate backup or <a href="#List/Backup Schedule">configure scheduled backups</a>
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
							<label>Export Format</label>
							<div id="export-format"></div>
						</div>
						<div class="form-group">
							<label>
								<input type="checkbox" id="include-files-checkbox" style="margin-right: 8px;">
								Include File Attachments
							</label>
							<p class="help-box small text-muted">Export all file attachments associated with the selected DocTypes</p>
						</div>
						<div class="form-group">
							<label>
								<input type="checkbox" id="enable-transformations-checkbox" style="margin-right: 8px;">
								Enable Field Value Transformations
							</label>
							<p class="help-box small text-muted">Transform field values during backup (e.g., change Company from "Test" to "Production")</p>
						</div>
						<div id="transformations-section" style="display: none; border: 1px solid #d1d8dd; padding: 15px; border-radius: 4px; background: #f9f9f9; margin-top: 10px;">
							<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
								<strong>Field Transformations</strong>
								<button class="btn btn-xs btn-success" id="add-transformation-btn">
									<span class="fa fa-plus"></span> Add Transformation
								</button>
							</div>
							<div id="transformations-list" style="max-height: 300px; overflow-y: auto;">
								<p class="text-muted small">No transformations added yet. Click "Add Transformation" to begin.</p>
							</div>
						</div>
						<div class="form-group">
							<label>
								<input type="checkbox" id="enable-table-transformations-checkbox" style="margin-right: 8px;">
								Enable Table Name Transformations
							</label>
							<p class="help-box small text-muted">Rename table names during backup (e.g., change "tabCompeny" to "tabCompany")</p>
						</div>
						<div id="table-transformations-section" style="display: none; border: 1px solid #d1d8dd; padding: 15px; border-radius: 4px; background: #f9f9f9; margin-top: 10px;">
							<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
								<strong>Table Name Transformations</strong>
								<button class="btn btn-xs btn-success" id="add-table-transformation-btn">
									<span class="fa fa-plus"></span> Add Table Transformation
								</button>
							</div>
							<div id="table-transformations-list" style="max-height: 300px; overflow-y: auto;">
								<p class="text-muted small">No table transformations added yet. Click "Add Table Transformation" to begin.</p>
							</div>
						</div>
						<div class="form-group" style="margin-top: 15px;">
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

	load_doctypes_with_filters(app_filter = null, module_filter = null) {
		// Determine which method to call based on app_filter
		const method = app_filter
			? 'data_tools.data_tools.page.partial_backup.partial_backup.get_doctypes_by_app'
			: 'data_tools.data_tools.page.partial_backup.partial_backup.get_all_doctypes';

		const args = app_filter
			? { app_names: Array.isArray(app_filter) ? JSON.stringify(app_filter) : app_filter }
			: {};

		frappe.call({
			method: method,
			args: args,
			callback: (r) => {
				if (r.message) {
					this.doctypes = r.message;

					// Apply module filter if specified (multiple modules)
					if (module_filter && Array.isArray(module_filter) && module_filter.length > 0) {
						this.filtered_doctypes = this.doctypes.filter(d => module_filter.includes(d.module));
					} else {
						this.filtered_doctypes = this.doctypes;
					}

					console.log('Total doctypes:', this.doctypes.length);
					console.log('Filtered doctypes:', this.filtered_doctypes.length);

					this.setup_doctype_list();
				}
			}
		});
	}

	setup_app_filter(apps) {
		const container = this.page.main.find('#app-filter');

		// Create wrapper for multi-select
		const wrapper = $('<div class="multiselect-wrapper"></div>');
		container.append(wrapper);

		// Create manual multi-select for apps (consistent with module filter)
		this.create_app_multiselect(wrapper, apps);
	}

	create_app_multiselect(container, apps) {
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

		// Handle dropdown toggle
		container.find('#app-multiselect-trigger').on('click', () => {
			container.find('#app-multiselect-dropdown').toggle();
		});

		// Handle checkbox changes
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

			this.update_app_multiselect_display(container);
			this.handle_app_filter_change();
		});

		// Close dropdown when clicking outside
		$(document).on('click', (e) => {
			if (!$(e.target).closest('.app-multiselect').length) {
				container.find('#app-multiselect-dropdown').hide();
			}
		});
	}

	update_app_multiselect_display(container) {
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
		// Use manual selection array
		const selected_apps = this.selected_apps || [];

		console.log('Selected apps:', selected_apps);

		// If no apps selected, pass null to load all
		const app_filter = selected_apps && selected_apps.length > 0 ? selected_apps : null;
		const module_filter = this.selected_modules && this.selected_modules.length > 0 ? this.selected_modules : null;

		this.load_doctypes_with_filters(app_filter, module_filter);
	}

	setup_module_filter(modules) {
		const container = this.page.main.find('#module-filter');

		// Create wrapper for multi-select
		const wrapper = $('<div class="multiselect-wrapper"></div>');
		container.append(wrapper);

		// Create manual multi-select for modules
		this.create_module_multiselect(wrapper, modules);
	}

	create_module_multiselect(container, modules) {
		const html = `
			<div class="module-multiselect">
				<div class="form-control multiselect-input" style="height: auto; min-height: 38px; cursor: pointer;" id="module-multiselect-trigger">
					<span class="text-muted">Select Modules (click to open)</span>
				</div>
				<div class="multiselect-dropdown" id="module-multiselect-dropdown" style="display: none; position: absolute; z-index: 1000; background: white; border: 1px solid #d1d8dd; border-radius: 4px; max-height: 300px; overflow-y: auto; width: 100%; margin-top: 2px;">
					${modules.map(module => `
						<div class="checkbox" style="padding: 5px 10px; margin: 0;">
							<label style="font-weight: normal; margin: 0;">
								<input type="checkbox" class="module-checkbox" value="${module}">
								${module}
							</label>
						</div>
					`).join('')}
				</div>
			</div>
		`;

		container.html(html);

		// Handle dropdown toggle
		container.find('#module-multiselect-trigger').on('click', () => {
			container.find('#module-multiselect-dropdown').toggle();
		});

		// Handle checkbox changes
		container.find('.module-checkbox').on('change', (e) => {
			const checkbox = $(e.target);
			const module = checkbox.val();

			if (checkbox.is(':checked')) {
				if (!this.selected_modules.includes(module)) {
					this.selected_modules.push(module);
				}
			} else {
				this.selected_modules = this.selected_modules.filter(m => m !== module);
			}

			this.update_module_multiselect_display(container);
			this.handle_module_filter_change();
		});

		// Close dropdown when clicking outside
		$(document).on('click', (e) => {
			if (!$(e.target).closest('.module-multiselect').length) {
				container.find('#module-multiselect-dropdown').hide();
			}
		});
	}

	update_module_multiselect_display(container) {
		const trigger = container.find('#module-multiselect-trigger');
		if (this.selected_modules.length === 0) {
			trigger.html('<span class="text-muted">Select Modules (click to open)</span>');
		} else {
			const pills = this.selected_modules.map(module =>
				`<span class="badge" style="margin: 2px; background-color: #2490ef; color: white;">${module}</span>`
			).join('');
			trigger.html(pills);
		}
	}

	handle_module_filter_change() {
		// Get selected apps and modules
		const selected_apps = this.selected_apps || [];
		const selected_modules = this.selected_modules || [];

		console.log('Selected apps:', selected_apps);
		console.log('Selected modules:', selected_modules);

		// If no apps selected, pass null to load all
		const app_filter = selected_apps.length > 0 ? selected_apps : null;
		const module_filter = selected_modules.length > 0 ? selected_modules : null;

		this.load_doctypes_with_filters(app_filter, module_filter);
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
					{label: 'SQL (Database dump)', value: 'sql'},
					{label: 'CSV (Records only)', value: 'csv'}
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

		this.page.main.find('#include-files-checkbox').on('change', (e) => {
			this.include_files = e.target.checked;
		});

		this.page.main.find('#enable-transformations-checkbox').on('change', (e) => {
			if (e.target.checked) {
				this.page.main.find('#transformations-section').slideDown();
			} else {
				this.page.main.find('#transformations-section').slideUp();
			}
		});

		this.page.main.find('#add-transformation-btn').on('click', () => {
			this.show_add_transformation_dialog();
		});

		this.page.main.find('#enable-table-transformations-checkbox').on('change', (e) => {
			if (e.target.checked) {
				this.page.main.find('#table-transformations-section').slideDown();
			} else {
				this.page.main.find('#table-transformations-section').slideUp();
			}
		});

		this.page.main.find('#add-table-transformation-btn').on('click', () => {
			this.show_add_table_transformation_dialog();
		});
	}

	show_add_transformation_dialog() {
		const dialog = new frappe.ui.Dialog({
			title: __('Add Field Transformation'),
			fields: [
				{
					fieldname: 'doctype',
					fieldtype: 'Select',
					label: __('DocType'),
					reqd: 1,
					options: this.selected_doctypes,
					description: __('Select the DocType to transform'),
					onchange: function() {
						const selected_doctype = this.get_value();
						if (selected_doctype) {
							// Load fields for the selected doctype
							frappe.call({
								method: 'data_tools.data_tools.page.partial_backup.partial_backup.get_doctype_fields',
								args: {
									doctype: selected_doctype
								},
								callback: (r) => {
									if (r.message) {
										const field_options = r.message.map(f => ({
											label: `${f.label} (${f.fieldname})`,
											value: f.fieldname
										}));

										// Update field dropdown
										const field_control = dialog.get_field('field');
										field_control.df.options = field_options;
										field_control.refresh();
										field_control.set_value('');
									}
								}
							});
						}
					}
				},
				{
					fieldname: 'field',
					fieldtype: 'Select',
					label: __('Field Name'),
					reqd: 1,
					options: [],
					description: __('Select the field to transform')
				},
				{
					fieldname: 'old_value',
					fieldtype: 'Data',
					label: __('Old Value'),
					description: __('Leave empty to replace all values in this field')
				},
				{
					fieldname: 'new_value',
					fieldtype: 'Data',
					label: __('New Value'),
					reqd: 1,
					description: __('The new value to set')
				}
			],
			primary_action_label: __('Add'),
			primary_action: (values) => {
				this.add_transformation(values);
				dialog.hide();
			}
		});

		dialog.show();
	}

	add_transformation(transformation) {
		this.field_transformations.push(transformation);
		this.render_transformations();
	}

	remove_transformation(index) {
		this.field_transformations.splice(index, 1);
		this.render_transformations();
	}

	render_transformations() {
		const container = this.page.main.find('#transformations-list');
		container.empty();

		if (this.field_transformations.length === 0) {
			container.html('<p class="text-muted small">No transformations added yet. Click "Add Transformation" to begin.</p>');
			return;
		}

		this.field_transformations.forEach((transform, index) => {
			const old_val_display = transform.old_value || '<span class="text-muted">(all values)</span>';
			const html = `
				<div class="transformation-item" style="padding: 10px; margin-bottom: 8px; background: white; border: 1px solid #d1d8dd; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;">
					<div>
						<strong>${transform.doctype}</strong>.<code>${transform.field}</code>
						<br>
						<small class="text-muted">
							${old_val_display} → <strong>${transform.new_value}</strong>
						</small>
					</div>
					<button class="btn btn-xs btn-danger remove-transformation-btn" data-index="${index}">
						<span class="fa fa-times"></span> Remove
					</button>
				</div>
			`;
			container.append(html);
		});

		// Add remove handlers
		container.find('.remove-transformation-btn').on('click', (e) => {
			const index = parseInt($(e.currentTarget).data('index'));
			this.remove_transformation(index);
		});
	}

	show_add_table_transformation_dialog() {
		if (!this.selected_doctypes || this.selected_doctypes.length === 0) {
			frappe.msgprint(__('Please select at least one DocType first'));
			return;
		}

		// Create options for old table name dropdown
		const table_options = this.selected_doctypes.map(dt => {
			return {
				label: `tab${dt}`,
				value: `tab${dt}`
			};
		});

		const dialog = new frappe.ui.Dialog({
			title: __('Add Table Name Transformation'),
			fields: [
				{
					fieldname: 'old_table_name',
					fieldtype: 'Select',
					label: __('Old Table Name'),
					reqd: 1,
					options: table_options,
					description: __('Select the current table name from selected DocTypes')
				},
				{
					fieldname: 'new_table_name',
					fieldtype: 'Data',
					label: __('New Table Name'),
					reqd: 1,
					description: __('Enter the new table name (e.g., "tabCompany")')
				}
			],
			primary_action_label: __('Add'),
			primary_action: (values) => {
				this.add_table_transformation(values);
				dialog.hide();
			}
		});

		dialog.show();
	}

	add_table_transformation(transformation) {
		this.table_transformations.push(transformation);
		this.render_table_transformations();
	}

	remove_table_transformation(index) {
		this.table_transformations.splice(index, 1);
		this.render_table_transformations();
	}

	render_table_transformations() {
		const container = this.page.main.find('#table-transformations-list');
		container.empty();

		if (this.table_transformations.length === 0) {
			container.html('<p class="text-muted small">No table transformations added yet. Click "Add Table Transformation" to begin.</p>');
			return;
		}

		this.table_transformations.forEach((transform, index) => {
			const html = `
				<div class="transformation-item" style="padding: 10px; margin-bottom: 8px; background: white; border: 1px solid #d1d8dd; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;">
					<div>
						<code style="font-size: 14px;">${transform.old_table_name}</code>
						<span style="margin: 0 10px;">→</span>
						<code style="font-size: 14px; color: #2490ef;">${transform.new_table_name}</code>
					</div>
					<button class="btn btn-xs btn-danger remove-table-transformation-btn" data-index="${index}">
						<span class="fa fa-times"></span> Remove
					</button>
				</div>
			`;
			container.append(html);
		});

		// Add remove handlers
		container.find('.remove-table-transformation-btn').on('click', (e) => {
			const index = parseInt($(e.currentTarget).data('index'));
			this.remove_table_transformation(index);
		});
	}

	create_backup() {
		if (!this.selected_doctypes || this.selected_doctypes.length === 0) {
			frappe.msgprint(__('Please select at least one DocType'));
			return;
		}

		// First check for dependencies
		frappe.call({
			method: 'data_tools.data_tools.page.partial_backup.partial_backup.get_doctype_dependencies',
			args: {
				doctypes: this.selected_doctypes
			},
			callback: (r) => {
				if (r.message && r.message.has_dependencies) {
					// Show dependency dialog
					this.show_dependency_dialog(r.message);
				} else {
					// No dependencies, proceed directly
					this.show_backup_options_dialog();
				}
			}
		});
	}

	show_dependency_dialog(dependency_data) {
		const dep_list = dependency_data.all_new_dependencies || [];
		const dep_by_doctype = dependency_data.dependencies_by_doctype || {};

		let dep_html = '<div style="margin: 10px 0;">';
		dep_html += '<div style="max-height: 300px; overflow-y: auto; border: 1px solid #d1d8dd; padding: 10px; border-radius: 4px; background: #f9f9f9;">';

		for (let doctype in dep_by_doctype) {
			const deps = dep_by_doctype[doctype];
			if (deps.length > 0) {
				dep_html += `<div style="margin: 8px 0; display: flex; align-items: center; gap: 8px;">`;
				dep_html += `<span class="text-warning" style="font-size: 16px; flex-shrink: 0;" title="Warning: Has dependencies">⚠️</span>`;
				dep_html += `<div><strong>${doctype}</strong> depends on `;
				dep_html += deps.map(d => `<span class="badge" style="background-color: #f39c12; color: white; margin: 2px;">${d}</span>`).join(', ');
				dep_html += '</div></div>';
			}
		}

		dep_html += '</div>';
		dep_html += `<p class="text-muted small" style="margin-top: 10px;">Found ${dep_list.length} dependent DocType(s) not in your selection.</p></div>`;

		// Create HTML for individual dependency checkboxes
		let dep_checkboxes_html = '<div style="margin: 15px 0;"><label><strong>Select Dependencies to Include:</strong></label>';
		dep_checkboxes_html += '<div style="max-height: 250px; overflow-y: auto; border: 1px solid #d1d8dd; padding: 10px; border-radius: 4px; background: white; margin-top: 5px;">';

		if (dep_list.length > 0) {
			dep_checkboxes_html += '<div style="margin-bottom: 10px;"><label style="font-weight: normal;"><input type="checkbox" id="select-all-deps" style="margin-right: 5px;"><strong>Select All</strong></label></div>';
			dep_checkboxes_html += '<hr style="margin: 5px 0;">';

			dep_list.forEach(dep => {
				dep_checkboxes_html += `<div class="checkbox" style="margin: 5px 0;">
					<label style="font-weight: normal; display: flex; align-items: center;">
						<input type="checkbox" class="dep-checkbox" data-doctype="${dep}" checked style="margin-right: 8px;">
						<span>${dep}</span>
					</label>
				</div>`;
			});
		} else {
			dep_checkboxes_html += '<p class="text-muted">No dependencies found.</p>';
		}

		dep_checkboxes_html += '</div></div>';

		const dep_dialog = new frappe.ui.Dialog({
			title: __('Dependencies Detected'),
			fields: [
				{
					fieldtype: 'HTML',
					options: dep_html
				},
				{
					fieldtype: 'HTML',
					options: dep_checkboxes_html
				}
			],
			primary_action_label: __('Continue'),
			primary_action: (values) => {
				// Get selected dependencies from checkboxes
				const selected_deps = [];
				dep_dialog.$wrapper.find('.dep-checkbox:checked').each(function() {
					selected_deps.push($(this).data('doctype'));
				});

				dep_dialog.hide();

				// Add selected dependencies to selection
				if (selected_deps.length > 0) {
					const all_doctypes = [...this.selected_doctypes, ...selected_deps];
					// Remove duplicates
					this.selected_doctypes = [...new Set(all_doctypes)];
					frappe.show_alert({
						message: __(`Added ${selected_deps.length} dependent DocType(s) to backup`),
						indicator: 'green'
					}, 3);
				}

				// Proceed to backup options
				this.show_backup_options_dialog();
			}
		});

		// Add select all functionality after dialog is shown
		dep_dialog.show();

		// Setup select all checkbox handler
		dep_dialog.$wrapper.find('#select-all-deps').on('change', function() {
			const isChecked = $(this).is(':checked');
			dep_dialog.$wrapper.find('.dep-checkbox').prop('checked', isChecked);
		});

		// Update select all checkbox when individual checkboxes change
		dep_dialog.$wrapper.find('.dep-checkbox').on('change', function() {
			const totalCheckboxes = dep_dialog.$wrapper.find('.dep-checkbox').length;
			const checkedCheckboxes = dep_dialog.$wrapper.find('.dep-checkbox:checked').length;
			dep_dialog.$wrapper.find('#select-all-deps').prop('checked', totalCheckboxes === checkedCheckboxes);
		});
	}

	show_backup_options_dialog() {
		// Ask user: Backup Now or Schedule
		const choice_dialog = new frappe.ui.Dialog({
			title: __('Backup Options'),
			fields: [
				{
					fieldtype: 'HTML',
					options: `<p class="text-muted">${__('You have selected')} <strong>${this.selected_doctypes.length}</strong> ${__('DocType(s)')}</p>`
				},
				{
					fieldname: 'backup_type',
					fieldtype: 'Select',
					label: __('Choose Backup Type'),
					options: [
						{label: __('Backup Now (Immediate)'), value: 'now'},
						{label: __('Schedule Backup'), value: 'schedule'}
					],
					default: 'now',
					reqd: 1
				}
			],
			primary_action_label: __('Continue'),
			primary_action: (values) => {
				choice_dialog.hide();
				if (values.backup_type === 'now') {
					this.execute_immediate_backup();
				} else {
					this.show_schedule_dialog();
				}
			}
		});

		choice_dialog.show();
	}

	execute_immediate_backup() {
		const status_elem = this.page.main.find('#backup-status');
		status_elem.html('<span class="text-primary"><span class="fa fa-spinner fa-spin"></span> Starting backup job...</span>');

		// Prepare field transformations
		const transformations = this.field_transformations.length > 0
			? JSON.stringify(this.field_transformations)
			: null;

		// Prepare table transformations
		const table_transformations = this.table_transformations.length > 0
			? JSON.stringify(this.table_transformations)
			: null;

		console.log('Field transformations:', this.field_transformations);
		console.log('Transformations JSON:', transformations);
		console.log('Table transformations:', this.table_transformations);
		console.log('Table transformations JSON:', table_transformations);

		// Start background job
		frappe.call({
			method: 'data_tools.data_tools.page.partial_backup.partial_backup.start_backup_job',
			args: {
				doctypes: this.selected_doctypes,
				export_format: this.export_format,
				include_files: this.include_files,
				field_transformations: transformations,
				table_transformations: table_transformations
			},
			callback: (r) => {
				if (r.message && r.message.job_id) {
					this.job_id = r.message.job_id;
					status_elem.html(
						`<span class="text-primary">
							<span class="fa fa-spinner fa-spin"></span>
							Backup in progress... Please wait.
						</span>`
					);

					// Start polling for job status
					this.poll_job_status();
				} else {
					status_elem.html('<span class="text-danger">Failed to start backup job</span>');
				}
			},
			error: () => {
				status_elem.html('<span class="text-danger">Error starting backup job</span>');
				frappe.msgprint(__('Error starting backup. Please check the error log.'));
			}
		});
	}

	poll_job_status() {
		const status_elem = this.page.main.find('#backup-status');

		const check_status = () => {
			frappe.call({
				method: 'data_tools.data_tools.page.partial_backup.partial_backup.get_job_status',
				args: {
					job_id: this.job_id
				},
				callback: (r) => {
					if (r.message) {
						const status = r.message.status;
						const progress = r.message.progress;

						if (status === 'completed') {
							// Job completed - download the file
							status_elem.html(
								`<span class="text-success">
									<span class="fa fa-check"></span>
									Backup completed! Downloading...
								</span>`
							);
							this.download_backup(this.job_id);
						} else if (status === 'failed') {
							status_elem.html(
								`<span class="text-danger">
									<span class="fa fa-times"></span>
									Backup failed: ${r.message.error || 'Unknown error'}
								</span>`
							);
							frappe.msgprint(__('Backup failed. Please check the error log.'));
						} else if (status === 'running' || status === 'queued') {
							// Update progress message
							let progress_msg = 'Backup in progress...';
							if (progress) {
								progress_msg = progress;
							}
							status_elem.html(
								`<span class="text-primary">
									<span class="fa fa-spinner fa-spin"></span>
									${progress_msg}
								</span>`
							);
							// Continue polling
							setTimeout(check_status, 2000);
						} else {
							// Unknown status, keep polling
							setTimeout(check_status, 2000);
						}
					}
				},
				error: () => {
					status_elem.html('<span class="text-danger">Error checking job status</span>');
				}
			});
		};

		// Start checking status
		check_status();
	}

	download_backup(job_id) {
		const status_elem = this.page.main.find('#backup-status');

		console.log('Downloading backup for job_id:', job_id);

		frappe.call({
			method: 'data_tools.data_tools.page.partial_backup.partial_backup.download_backup',
			args: {
				job_id: job_id
			},
			callback: (r) => {
				console.log('Download response:', r);

				if (r.message && r.message.success) {
					const result = r.message;
					console.log('Result:', result);
					console.log('Filename:', result.filename);
					console.log('Use URL:', result.use_url);
					console.log('File size:', result.file_size);

					try {
						// Check if we should use URL-based download (for large files)
						if (result.use_url) {
							console.log('Using URL-based download for large file');
							console.log('Download URL:', result.download_url);

							// For large files, use direct URL download
							const a = document.createElement('a');
							a.href = result.download_url;
							a.download = result.filename;
							a.style.display = 'none';
							document.body.appendChild(a);
							a.click();
							document.body.removeChild(a);

							status_elem.html(
								`<span class="text-success">
									<span class="fa fa-check"></span>
									Backup download started: ${result.total_doctypes} DocTypes, ${result.total_records} records
									${result.total_files ? `, ${result.total_files} files` : ''}
									(${(result.file_size / 1024 / 1024).toFixed(2)} MB)
								</span>`
							);

							frappe.show_alert({
								message: __('Large backup download started'),
								indicator: 'green'
							}, 5);
						} else {
							console.log('Using base64 download for small file');
							console.log('File data length:', result.file_data ? result.file_data.length : 0);

							// For small files, use base64 decoding
							const binary_data = atob(result.file_data);
							const array = new Uint8Array(binary_data.length);
							for (let i = 0; i < binary_data.length; i++) {
								array[i] = binary_data.charCodeAt(i);
							}

							console.log('Binary data length:', binary_data.length);

							// Set correct MIME type based on export format
							const mime_type = this.export_format === 'sql'
								? 'application/sql'
								: 'application/zip';
							const blob = new Blob([array], { type: mime_type });
							console.log('Blob created, size:', blob.size);

							const url = window.URL.createObjectURL(blob);
							const a = document.createElement('a');
							a.href = url;
							a.download = result.filename;
							document.body.appendChild(a);
							a.click();
							console.log('Download triggered');
							document.body.removeChild(a);
							window.URL.revokeObjectURL(url);

							status_elem.html(
								`<span class="text-success">
									<span class="fa fa-check"></span>
									Backup downloaded: ${result.total_doctypes} DocTypes, ${result.total_records} records
									${result.total_files ? `, ${result.total_files} files` : ''}
								</span>`
							);

							frappe.show_alert({
								message: __('Backup downloaded successfully'),
								indicator: 'green'
							});
						}
					} catch (e) {
						console.error('Error processing download:', e);
						status_elem.html('<span class="text-danger">Error processing download: ' + e.message + '</span>');
					}
				} else {
					console.error('Invalid response:', r);
					status_elem.html('<span class="text-danger">Failed to download backup</span>');
				}
			},
			error: (r) => {
				console.error('Download error:', r);
				status_elem.html('<span class="text-danger">Error downloading backup: ' + (r.message || 'Unknown error') + '</span>');
			}
		});
	}

	show_schedule_dialog() {
		// Create schedule dialog
		const schedule_dialog = new frappe.ui.Dialog({
			title: __('Create Backup Schedule'),
			size: 'large',
			fields: [
				{
					fieldname: 'schedule_name',
					fieldtype: 'Data',
					label: __('Schedule Name'),
					reqd: 1,
					description: __('Give this schedule a unique name')
				},
				{
					fieldname: 'enabled',
					fieldtype: 'Check',
					label: __('Enabled'),
					default: 1
				},
				{
					fieldtype: 'Column Break'
				},
				{
					fieldname: 'export_format',
					fieldtype: 'Select',
					label: __('Export Format'),
					options: 'json\nsql',
					default: this.export_format || 'json',
					reqd: 1
				},
				{
					fieldtype: 'Section Break',
					label: __('Schedule Configuration')
				},
				{
					fieldname: 'frequency',
					fieldtype: 'Select',
					label: __('Frequency'),
					options: 'Daily\nWeekly\nMonthly\nSpecific Date',
					default: 'Daily',
					reqd: 1,
					onchange: function() {
						const freq = this.get_value();
						const dialog = schedule_dialog;

						// Show/hide fields based on frequency
						if (dialog.fields_dict.day_of_week) {
							dialog.fields_dict.day_of_week.df.hidden = (freq !== 'Weekly');
							dialog.fields_dict.day_of_week.refresh();
						}

						if (dialog.fields_dict.day_of_month) {
							dialog.fields_dict.day_of_month.df.hidden = (freq !== 'Monthly');
							dialog.fields_dict.day_of_month.refresh();
						}

						if (dialog.fields_dict.specific_date) {
							dialog.fields_dict.specific_date.df.hidden = (freq !== 'Specific Date');
							dialog.fields_dict.specific_date.refresh();
						}
					}
				},
				{
					fieldname: 'time_of_day',
					fieldtype: 'Time',
					label: __('Time'),
					default: '02:00:00',
					reqd: 1
				},
				{
					fieldtype: 'Column Break'
				},
				{
					fieldname: 'day_of_week',
					fieldtype: 'Select',
					label: __('Day of Week'),
					options: 'Monday\nTuesday\nWednesday\nThursday\nFriday\nSaturday\nSunday',
					default: 'Monday',
					hidden: 1
				},
				{
					fieldname: 'day_of_month',
					fieldtype: 'Int',
					label: __('Day of Month'),
					description: __('Enter day number (1-31)'),
					default: 1,
					hidden: 1
				},
				{
					fieldname: 'specific_date',
					fieldtype: 'Date',
					label: __('Specific Date'),
					hidden: 1
				},
				{
					fieldtype: 'Section Break',
					label: __('Selected DocTypes')
				},
				{
					fieldname: 'doctypes_info',
					fieldtype: 'HTML',
					options: `<div class="text-muted">
						<p>${__('The following DocTypes will be included in this schedule:')}</p>
						<ul>
							${this.selected_doctypes.map(dt => `<li>${dt}</li>`).join('')}
						</ul>
						<p><strong>${__('Total:')} ${this.selected_doctypes.length} ${__('DocType(s)')}</strong></p>
					</div>`
				}
			],
			primary_action_label: __('Create Schedule'),
			primary_action: (values) => {
				this.create_schedule(values);
				schedule_dialog.hide();
			}
		});

		schedule_dialog.show();
	}

	create_schedule(values) {
		const status_elem = this.page.main.find('#backup-status');
		status_elem.html('<span class="text-primary">Creating schedule...</span>');

		// Prepare doctypes_to_backup child table data
		const doctypes_to_backup = this.selected_doctypes.map(dt => {
			return {
				doctype_name: dt
			};
		});

		// Validate frequency-specific fields
		if (values.frequency === 'Weekly' && !values.day_of_week) {
			frappe.msgprint(__('Please select a day of week for weekly schedules'));
			status_elem.html('');
			return;
		}

		if (values.frequency === 'Monthly' && !values.day_of_month) {
			frappe.msgprint(__('Please enter a day of month for monthly schedules'));
			status_elem.html('');
			return;
		}

		if (values.frequency === 'Specific Date' && !values.specific_date) {
			frappe.msgprint(__('Please select a specific date'));
			status_elem.html('');
			return;
		}

		// Create the Backup Schedule document
		frappe.call({
			method: 'frappe.client.insert',
			args: {
				doc: {
					doctype: 'Backup Schedule',
					schedule_name: values.schedule_name,
					enabled: values.enabled ? 1 : 0,
					frequency: values.frequency,
					time_of_day: values.time_of_day,
					day_of_week: values.frequency === 'Weekly' ? values.day_of_week : null,
					day_of_month: values.frequency === 'Monthly' ? values.day_of_month : null,
					specific_date: values.frequency === 'Specific Date' ? values.specific_date : null,
					export_format: values.export_format,
					doctypes_to_backup: doctypes_to_backup
				}
			},
			freeze: true,
			freeze_message: __('Creating backup schedule...'),
			callback: (r) => {
				if (r.message) {
					status_elem.html(
						`<span class="text-success">
							<span class="fa fa-check"></span>
							Schedule created successfully!
						</span>`
					);

					frappe.show_alert({
						message: __('Backup schedule created successfully'),
						indicator: 'green'
					});

					// Ask if user wants to view the schedule
					frappe.confirm(
						__('Backup schedule "{0}" has been created. Do you want to view it?', [values.schedule_name]),
						() => {
							frappe.set_route('Form', 'Backup Schedule', r.message.name);
						}
					);
				}
			},
			error: (r) => {
				status_elem.html('<span class="text-danger">Schedule creation failed</span>');

				// Show detailed error if available
				let error_msg = __('Error creating schedule.');
				if (r && r.message) {
					error_msg += '<br><br>' + r.message;
				} else if (r && r.exc) {
					error_msg += '<br><br>' + __('Please check the error log for details.');
				}

				frappe.msgprint({
					title: __('Error'),
					indicator: 'red',
					message: error_msg
				});
			}
		});
	}

	show_cli_help() {
		const help_dialog = new frappe.ui.Dialog({
			title: __('CLI Backup & Restore Commands'),
			size: 'extra-large',
			fields: [
				{
					fieldtype: 'HTML',
					options: `
						<div style="padding: 15px;">
							<h4><i class="fa fa-terminal"></i> For Large Backups (CLI Recommended)</h4>
							<p class="text-muted">When dealing with large datasets that cause timeout errors, use these CLI commands directly on the server.</p>

							<hr>

							<h5>1. Full Database Backup (MySQL Dump)</h5>
							<p>Backup entire site database to SQL file:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># Navigate to bench directory
cd /path/to/frappe-bench

# Full site backup (includes database, files, and private files)
bench --site [site-name] backup

# Database only backup
bench --site [site-name] backup --only-database

# Backup with specific path
bench --site [site-name] backup --backup-path /path/to/backup/folder
</code></pre>

							<h5>2. Partial Backup Using MySQL Commands</h5>
							<p>Export specific tables (DocTypes) directly:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># Get database credentials from site_config.json
cat sites/[site-name]/site_config.json

# Export specific tables (replace TABLE_NAME with actual table, e.g., tabCustomer)
mysqldump -u [db_user] -p[db_password] [db_name] tabDocTypeName1 tabDocTypeName2 > partial_backup.sql

# Example: Backup Customer and Sales Order tables
mysqldump -u root -p mydb tabCustomer "tabSales Order" > customer_orders_backup.sql

# Backup multiple tables with pattern
mysqldump -u root -p mydb --tables \`mysql -u root -p -Nse "SHOW TABLES LIKE 'tabCustom%'"\` > custom_doctypes.sql
</code></pre>

							<h5>3. Restore from SQL Backup</h5>
							<p>Restore a SQL backup file:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># Using bench restore
bench --site [site-name] restore /path/to/backup.sql

# Using MySQL directly
mysql -u [db_user] -p[db_password] [db_name] < backup.sql

# For large files, use pv to monitor progress
pv backup.sql | mysql -u [db_user] -p[db_password] [db_name]
</code></pre>

							<h5>4. Increase Nginx Timeout (For Web-based Large Operations)</h5>
							<p>If you still want to use the web interface for large operations:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># Edit nginx configuration
sudo nano /etc/nginx/nginx.conf

# Add these lines in http block:
client_max_body_size 500M;
proxy_read_timeout 300s;
proxy_connect_timeout 300s;
proxy_send_timeout 300s;
send_timeout 300s;

# Restart nginx
sudo systemctl restart nginx
sudo systemctl restart supervisor
</code></pre>

							<h5>5. Compressed Backups</h5>
							<p>Create compressed backups to save space:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># Backup and compress
bench --site [site-name] backup --compress

# Manual MySQL backup with compression
mysqldump -u [db_user] -p[db_password] [db_name] | gzip > backup.sql.gz

# Restore from compressed backup
gunzip < backup.sql.gz | mysql -u [db_user] -p[db_password] [db_name]
</code></pre>

							<h5>6. Find Backup Files</h5>
							<p>Locate existing backups:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># List all backups for a site
ls -lh sites/[site-name]/private/backups/

# Find recent backups
find sites/[site-name]/private/backups/ -name "*.sql.gz" -mtime -7

# Find backups created by partial backup tool
find sites/[site-name]/private/files/ -name "partial_backup_*.sql"
find sites/[site-name]/private/files/ -name "partial_backup_*.zip"
</code></pre>

							<hr>

							<div class="alert alert-info">
								<strong><i class="fa fa-info-circle"></i> Pro Tips:</strong>
								<ul>
									<li>Always test restore on a separate site before production restore</li>
									<li>Use <code>--verbose</code> flag with bench commands for detailed output</li>
									<li>Schedule automated backups using cron jobs</li>
									<li>Store backups on a different server for disaster recovery</li>
									<li>For very large databases (>10GB), consider incremental backups</li>
								</ul>
							</div>

							<div class="alert alert-warning">
								<strong><i class="fa fa-exclamation-triangle"></i> Important Notes:</strong>
								<ul>
									<li>Replace [site-name] with your actual site name</li>
									<li>Replace [db_user], [db_password], [db_name] with actual values from site_config.json</li>
									<li>Table names in Frappe have prefix "tab" (e.g., "tabCustomer" for Customer DocType)</li>
									<li>Child table names use space in quotes (e.g., "tabSales Order Item")</li>
									<li>Always backup before attempting restore operations</li>
								</ul>
							</div>
						</div>
					`
				}
			],
			primary_action_label: __('Close')
		});

		help_dialog.show();
	}
}
