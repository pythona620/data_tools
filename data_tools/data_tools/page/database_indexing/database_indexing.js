frappe.pages['database_indexing'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Database Indexing',
		single_column: true
	});

	new DatabaseIndexingPage(page);
}

class DatabaseIndexingPage {
	constructor(page) {
		this.page = page;
		this.indexes = [];
		this.suggestions = [];
		this.table_wise = [];
		this.current_tab = 'table_wise';
		this.filter_options = {apps: [], modules: [], doctypes: []};
		this.current_filters = {apps: [], modules: [], doctypes: []};
		this.filter_controls = {};
		this.make_page();
	}

	make_page() {
		// Add refresh button
		this.page.add_inner_button('Refresh', () => {
			this.load_data();
		});

		// Create page HTML
		this.page.main.html(`
			<div class="database-indexing-container">
				<div class="frappe-card">
					<div class="frappe-card-head">
						<h4>Database Index Management</h4>
						<p class="text-muted small" style="margin: 5px 0 0 0;">
							View current indexes, get suggestions, and optimize your database performance
						</p>
					</div>
					<div class="frappe-card-body">
						<!-- Tabs -->
						<div class="btn-group" role="group" style="margin-bottom: 20px;">
							<button type="button" class="btn btn-default" id="tab-table_wise">
								Table-wise View
							</button>
							<button type="button" class="btn btn-default" id="tab-indexes">
								All Indexes
							</button>
							<button type="button" class="btn btn-default" id="tab-suggestions">
								Suggestions
							</button>
						</div>

						<!-- Filters -->
						<div class="row" style="margin-bottom: 15px;">
							<div class="col-sm-4">
								<div class="form-group" style="margin-bottom: 0;">
									<label class="control-label" style="font-size: 11px; margin-bottom: 3px;">Apps</label>
									<div id="filter-apps-container"></div>
								</div>
							</div>
							<div class="col-sm-4">
								<div class="form-group" style="margin-bottom: 0;">
									<label class="control-label" style="font-size: 11px; margin-bottom: 3px;">Modules</label>
									<div id="filter-modules-container"></div>
								</div>
							</div>
							<div class="col-sm-4">
								<div class="form-group" style="margin-bottom: 0;">
									<label class="control-label" style="font-size: 11px; margin-bottom: 3px;">DocTypes</label>
									<div id="filter-doctypes-container"></div>
								</div>
							</div>
						</div>
						<div class="row" style="margin-bottom: 15px;">
							<div class="col-sm-12">
								<button class="btn btn-default btn-xs" id="clear-filters">
									<span class="fa fa-times"></span> Clear All Filters
								</button>
							</div>
						</div>

						<!-- Search -->
						<div class="row" style="margin-bottom: 15px;">
							<div class="col-sm-6">
								<input type="text" class="form-control" id="search-box" placeholder="Search by table or column name...">
							</div>
							<div class="col-sm-6">
								<div class="text-right">
									<span id="stats-display" class="text-muted"></span>
								</div>
							</div>
						</div>

						<!-- Content Area -->
						<div id="content-area"></div>
					</div>
				</div>
			</div>
		`);

		this.setup_handlers();
		this.load_filter_options();
		this.load_data();
	}

	setup_handlers() {
		// Tab switching
		this.page.main.find('#tab-table_wise').on('click', () => {
			this.switch_tab('table_wise');
		});

		this.page.main.find('#tab-indexes').on('click', () => {
			this.switch_tab('indexes');
		});

		this.page.main.find('#tab-suggestions').on('click', () => {
			this.switch_tab('suggestions');
		});

		// Clear filters
		this.page.main.find('#clear-filters').on('click', () => {
			this.clear_all_filters();
		});

		// Search
		this.page.main.find('#search-box').on('input', (e) => {
			this.filter_data(e.target.value);
		});

		// Set initial tab
		this.switch_tab('table_wise');
	}

	clear_all_filters() {
		this.current_filters = {apps: [], modules: [], doctypes: []};

		// Clear all multi-select controls
		if (this.filter_controls.apps) {
			this.filter_controls.apps.set_value([]);
		}
		if (this.filter_controls.modules) {
			this.filter_controls.modules.set_value([]);
		}
		if (this.filter_controls.doctypes) {
			this.filter_controls.doctypes.set_value([]);
		}

		// Reload filter options and data
		this.load_filter_options();
		this.load_data();
	}

	switch_tab(tab) {
		this.current_tab = tab;

		// Update button states
		this.page.main.find('#tab-table_wise').removeClass('btn-primary').addClass('btn-default');
		this.page.main.find('#tab-indexes').removeClass('btn-primary').addClass('btn-default');
		this.page.main.find('#tab-suggestions').removeClass('btn-primary').addClass('btn-default');
		this.page.main.find(`#tab-${tab}`).removeClass('btn-default').addClass('btn-primary');

		// Render content
		this.render_content();
	}

	load_filter_options(selected_apps = null) {
		const args = {};
		if (selected_apps && selected_apps.length > 0) {
			args.apps = JSON.stringify(selected_apps);
		}

		frappe.call({
			method: 'data_tools.data_tools.page.database_indexing.database_indexing.get_filter_options',
			args: args,
			callback: (r) => {
				if (r.message) {
					this.filter_options = r.message;
					this.populate_filter_controls();
				}
			}
		});
	}

	populate_filter_controls() {
		// Create Apps multi-select
		if (!this.filter_controls.apps) {
			this.filter_controls.apps = frappe.ui.form.make_control({
				parent: this.page.main.find('#filter-apps-container'),
				df: {
					fieldtype: 'MultiSelect',
					options: (this.filter_options.apps || []).map(app => ({label: app, value: app})),
					change: () => {
						this.current_filters.apps = this.filter_controls.apps.get_value() || [];
						// Reload modules and doctypes based on selected apps
						this.load_filter_options(this.current_filters.apps);
						// Clear module and doctype selections
						this.current_filters.modules = [];
						this.current_filters.doctypes = [];
						this.load_data();
					}
				},
				render_input: true
			});
		} else {
			this.filter_controls.apps.df.options = (this.filter_options.apps || []).map(app => ({label: app, value: app}));
			this.filter_controls.apps.refresh();
		}

		// Create Modules multi-select
		if (!this.filter_controls.modules) {
			this.filter_controls.modules = frappe.ui.form.make_control({
				parent: this.page.main.find('#filter-modules-container'),
				df: {
					fieldtype: 'MultiSelect',
					options: (this.filter_options.modules || []).map(mod => ({label: mod, value: mod})),
					change: () => {
						this.current_filters.modules = this.filter_controls.modules.get_value() || [];
						this.load_data();
					}
				},
				render_input: true
			});
		} else {
			this.filter_controls.modules.df.options = (this.filter_options.modules || []).map(mod => ({label: mod, value: mod}));
			this.filter_controls.modules.refresh();
		}

		// Create DocTypes multi-select
		if (!this.filter_controls.doctypes) {
			this.filter_controls.doctypes = frappe.ui.form.make_control({
				parent: this.page.main.find('#filter-doctypes-container'),
				df: {
					fieldtype: 'MultiSelect',
					options: (this.filter_options.doctypes || []).map(dt => ({label: dt, value: dt})),
					change: () => {
						this.current_filters.doctypes = this.filter_controls.doctypes.get_value() || [];
						this.load_data();
					}
				},
				render_input: true
			});
		} else {
			this.filter_controls.doctypes.df.options = (this.filter_options.doctypes || []).map(dt => ({label: dt, value: dt}));
			this.filter_controls.doctypes.refresh();
		}
	}

	load_data() {
		const content_area = this.page.main.find('#content-area');
		content_area.html('<p class="text-muted"><span class="fa fa-spinner fa-spin"></span> Loading...</p>');

		// Build filter args
		const filter_args = {};
		if (this.current_filters.apps && this.current_filters.apps.length > 0) {
			filter_args.apps = JSON.stringify(this.current_filters.apps);
		}
		if (this.current_filters.modules && this.current_filters.modules.length > 0) {
			filter_args.modules = JSON.stringify(this.current_filters.modules);
		}
		if (this.current_filters.doctypes && this.current_filters.doctypes.length > 0) {
			filter_args.doctypes = JSON.stringify(this.current_filters.doctypes);
		}

		// Load table-wise indexes
		frappe.call({
			method: 'data_tools.data_tools.page.database_indexing.database_indexing.get_table_wise_indexes',
			args: filter_args,
			callback: (r) => {
				if (r.message) {
					this.table_wise = r.message;
					if (this.current_tab === 'table_wise') {
						this.render_content();
					}
				}
			}
		});

		// Load indexes
		frappe.call({
			method: 'data_tools.data_tools.page.database_indexing.database_indexing.get_all_indexes',
			callback: (r) => {
				if (r.message) {
					this.indexes = r.message;
					if (this.current_tab === 'indexes') {
						this.render_content();
					}
				}
			}
		});

		// Load suggestions
		frappe.call({
			method: 'data_tools.data_tools.page.database_indexing.database_indexing.get_index_suggestions',
			args: filter_args,
			callback: (r) => {
				if (r.message) {
					this.suggestions = r.message;
					if (this.current_tab === 'suggestions') {
						this.render_content();
					}
				}
			}
		});
	}

	filter_data(search_term) {
		this.search_term = search_term.toLowerCase();
		this.render_content();
	}

	render_content() {
		const content_area = this.page.main.find('#content-area');

		if (this.current_tab === 'table_wise') {
			this.render_table_wise(content_area);
		} else if (this.current_tab === 'indexes') {
			this.render_indexes(content_area);
		} else {
			this.render_suggestions(content_area);
		}
	}

	render_table_wise(container) {
		container.empty();

		// Filter tables
		let filtered = this.table_wise;
		if (this.search_term) {
			filtered = this.table_wise.filter(table =>
				table.table_name.toLowerCase().includes(this.search_term) ||
				table.doctype.toLowerCase().includes(this.search_term)
			);
		}

		// Update stats
		this.page.main.find('#stats-display').text(`Total: ${filtered.length} tables`);

		if (filtered.length === 0) {
			container.html('<p class="text-muted">No tables found</p>');
			return;
		}

		// Create accordion for tables
		let html = '<div style="max-height: 600px; overflow-y: auto;">';

		filtered.forEach(table => {
			const stats = table.statistics || {};
			const indexes_list = Object.values(table.indexes || {});
			const index_count = indexes_list.length;

			html += `
				<div class="card" style="margin-bottom: 10px;">
					<div class="card-header" style="cursor: pointer; background-color: #f8f9fa;">
						<div class="row" onclick="$(this).closest('.card').find('.card-body').slideToggle()">
							<div class="col-sm-6">
								<h5 style="margin: 0;">
									<strong>${table.doctype}</strong>
									<span class="badge badge-info">${index_count} indexes</span>
								</h5>
								<small class="text-muted">
									<code>${table.table_name}</code>
									${table.module ? `<span class="badge badge-light">${table.module}</span>` : ''}
									${table.app ? `<span class="badge badge-secondary">${table.app}</span>` : ''}
								</small>
							</div>
							<div class="col-sm-6 text-right">
								<div class="text-muted small">
									${stats.row_count ? `<strong>${stats.row_count.toLocaleString()}</strong> rows` : ''}
									${stats.total_size_mb ? `| <strong>${stats.total_size_mb} MB</strong>` : ''}
								</div>
							</div>
						</div>
					</div>
					<div class="card-body" style="display: none; padding: 15px;">
						<h6>Indexes:</h6>
						<table class="table table-sm table-bordered">
							<thead>
								<tr>
									<th>Index Name</th>
									<th>Columns</th>
									<th>Type</th>
									<th>Unique</th>
									<th>Cardinality</th>
									<th>Actions</th>
								</tr>
							</thead>
							<tbody>
			`;

			indexes_list.forEach(idx => {
				const columns_str = idx.columns.map(c => c.column_name).join(', ');
				const is_unique = idx.non_unique === 0 ? 'Yes' : 'No';
				const can_drop = idx.index_name !== 'PRIMARY';

				html += `
					<tr>
						<td><strong>${idx.index_name}</strong></td>
						<td><code>${columns_str}</code></td>
						<td>${idx.index_type}</td>
						<td>${is_unique}</td>
						<td>${idx.cardinality || 'N/A'}</td>
						<td>
							${can_drop ? `
								<button class="btn btn-xs btn-danger drop-index-btn"
									data-table="${table.table_name}"
									data-index="${idx.index_name}">
									<span class="fa fa-trash"></span>
								</button>
							` : '-'}
						</td>
					</tr>
				`;
			});

			html += `
							</tbody>
						</table>
						<div class="text-right" style="margin-top: 10px;">
							<button class="btn btn-sm btn-default analyze-table-btn"
								data-table="${table.table_name}">
								<span class="fa fa-refresh"></span> Analyze Table
							</button>
						</div>
					</div>
				</div>
			`;
		});

		html += '</div>';

		container.html(html);

		// Bind action handlers
		container.find('.drop-index-btn').on('click', (e) => {
			e.stopPropagation();
			const btn = $(e.currentTarget);
			this.drop_index(btn.data('table'), btn.data('index'));
		});

		container.find('.analyze-table-btn').on('click', (e) => {
			e.stopPropagation();
			const btn = $(e.currentTarget);
			this.analyze_table(btn.data('table'));
		});
	}

	render_indexes(container) {
		container.empty();

		// Filter indexes
		let filtered = this.indexes;
		if (this.search_term) {
			filtered = this.indexes.filter(idx =>
				idx.table_name.toLowerCase().includes(this.search_term) ||
				idx.index_name.toLowerCase().includes(this.search_term) ||
				idx.columns.some(col => col.column_name.toLowerCase().includes(this.search_term))
			);
		}

		// Update stats
		this.page.main.find('#stats-display').text(`Total: ${filtered.length} indexes`);

		if (filtered.length === 0) {
			container.html('<p class="text-muted">No indexes found</p>');
			return;
		}

		// Create table
		let html = `
			<div style="max-height: 600px; overflow-y: auto;">
				<table class="table table-bordered table-hover">
					<thead>
						<tr>
							<th>Table</th>
							<th>Index Name</th>
							<th>Columns</th>
							<th>Type</th>
							<th>Unique</th>
							<th>Cardinality</th>
							<th>Actions</th>
						</tr>
					</thead>
					<tbody>
		`;

		filtered.forEach(idx => {
			const columns_str = idx.columns.map(c => c.column_name).join(', ');
			const is_unique = idx.non_unique === 0 ? 'Yes' : 'No';
			const can_drop = idx.index_name !== 'PRIMARY';

			html += `
				<tr>
					<td><code>${idx.table_name}</code></td>
					<td><strong>${idx.index_name}</strong></td>
					<td><code>${columns_str}</code></td>
					<td>${idx.index_type}</td>
					<td>${is_unique}</td>
					<td>${idx.cardinality || 'N/A'}</td>
					<td>
						${can_drop ? `
							<button class="btn btn-xs btn-danger drop-index-btn"
								data-table="${idx.table_name}"
								data-index="${idx.index_name}">
								<span class="fa fa-trash"></span> Drop
							</button>
						` : '<span class="text-muted">-</span>'}
						<button class="btn btn-xs btn-default analyze-table-btn"
							data-table="${idx.table_name}">
							<span class="fa fa-refresh"></span> Analyze
						</button>
					</td>
				</tr>
			`;
		});

		html += `
					</tbody>
				</table>
			</div>
		`;

		container.html(html);

		// Bind action handlers
		container.find('.drop-index-btn').on('click', (e) => {
			const btn = $(e.currentTarget);
			this.drop_index(btn.data('table'), btn.data('index'));
		});

		container.find('.analyze-table-btn').on('click', (e) => {
			const btn = $(e.currentTarget);
			this.analyze_table(btn.data('table'));
		});
	}

	render_suggestions(container) {
		container.empty();

		// Filter suggestions
		let filtered = this.suggestions;
		if (this.search_term) {
			filtered = this.suggestions.filter(sug =>
				sug.table_name.toLowerCase().includes(this.search_term) ||
				sug.column_name.toLowerCase().includes(this.search_term) ||
				sug.doctype.toLowerCase().includes(this.search_term)
			);
		}

		// Update stats
		this.page.main.find('#stats-display').text(`Total: ${filtered.length} suggestions`);

		if (filtered.length === 0) {
			container.html('<p class="text-muted">No suggestions found</p>');
			return;
		}

		// Create cards for suggestions
		let html = '<div style="max-height: 600px; overflow-y: auto;">';

		filtered.forEach(sug => {
			const priority_colors = {
				'Critical': 'danger',
				'High': 'danger',
				'Medium': 'warning',
				'Low': 'info'
			};
			const color = priority_colors[sug.priority] || 'default';

			html += `
				<div class="card" style="margin-bottom: 15px; border-left: 4px solid var(--bs-${color});">
					<div class="card-body">
						<div class="row">
							<div class="col-sm-8">
								<h5 style="margin-top: 0;">
									<strong>${sug.doctype}</strong>
									<span class="badge badge-${color}">${sug.priority} Priority</span>
									<span class="badge badge-secondary">${sug.type}</span>
									${sug.row_count ? `<span class="badge badge-light">${sug.row_count.toLocaleString()} rows</span>` : ''}
								</h5>
								<p class="text-muted" style="margin-bottom: 5px;">
									<strong>Table:</strong> <code>${sug.table_name}</code>
									${sug.module ? `| <strong>Module:</strong> ${sug.module}` : ''}
									${sug.app ? `| <strong>App:</strong> ${sug.app}` : ''}
								</p>
								<p class="text-muted" style="margin-bottom: 5px;">
									<strong>Column(s):</strong> <code>${sug.column_name}</code>
								</p>
								<p style="margin-bottom: 5px;">
									<strong>Reason:</strong> ${sug.reason}
								</p>
								<p class="text-success" style="margin-bottom: 0;">
									<strong>Benefit:</strong> ${sug.estimated_benefit}
								</p>
							</div>
							<div class="col-sm-4 text-right">
								<button class="btn btn-primary create-index-btn"
									data-table="${sug.table_name}"
									data-columns="${sug.column_name}"
									data-doctype="${sug.doctype}">
									<span class="fa fa-plus"></span> Create Index
								</button>
							</div>
						</div>
					</div>
				</div>
			`;
		});

		html += '</div>';

		container.html(html);

		// Bind action handlers
		container.find('.create-index-btn').on('click', (e) => {
			const btn = $(e.currentTarget);
			this.create_index(btn.data('table'), btn.data('columns'));
		});
	}

	create_index(table_name, column_names) {
		frappe.confirm(
			`Create index on <strong>${table_name}</strong> for column(s): <code>${column_names}</code>?`,
			() => {
				frappe.call({
					method: 'data_tools.data_tools.page.database_indexing.database_indexing.create_index',
					args: {
						table_name: table_name,
						column_names: column_names
					},
					callback: (r) => {
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: __('Index created successfully'),
								indicator: 'green'
							}, 3);
							this.load_data();
						} else {
							frappe.msgprint({
								title: __('Error'),
								indicator: 'red',
								message: r.message ? r.message.message : __('Failed to create index')
							});
						}
					}
				});
			}
		);
	}

	drop_index(table_name, index_name) {
		frappe.confirm(
			`Are you sure you want to drop index <strong>${index_name}</strong> from <strong>${table_name}</strong>?<br><br>
			<span class="text-danger">This action cannot be undone!</span>`,
			() => {
				frappe.call({
					method: 'data_tools.data_tools.page.database_indexing.database_indexing.drop_index',
					args: {
						table_name: table_name,
						index_name: index_name
					},
					callback: (r) => {
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: __('Index dropped successfully'),
								indicator: 'green'
							}, 3);
							this.load_data();
						} else {
							frappe.msgprint({
								title: __('Error'),
								indicator: 'red',
								message: r.message ? r.message.message : __('Failed to drop index')
							});
						}
					}
				});
			}
		);
	}

	analyze_table(table_name) {
		frappe.call({
			method: 'data_tools.data_tools.page.database_indexing.database_indexing.analyze_table',
			args: {
				table_name: table_name
			},
			callback: (r) => {
				if (r.message && r.message.success) {
					frappe.show_alert({
						message: __('Table analyzed successfully'),
						indicator: 'green'
					}, 3);
					this.load_data();
				} else {
					frappe.msgprint({
						title: __('Error'),
						indicator: 'red',
						message: r.message ? r.message.message : __('Failed to analyze table')
					});
				}
			}
		});
	}
}
