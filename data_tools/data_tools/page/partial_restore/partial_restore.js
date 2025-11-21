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
		this.selected_doctypes = [];
		this.make_page();
	}

	make_page() {
		// Add "CLI Help" button
		this.page.add_inner_button('CLI Restore Commands', () => {
			this.show_cli_help();
		});

		this.page.main.html(`
			<div class="partial-restore-container">
				<div class="frappe-card">
					<div class="frappe-card-head">
						<h4>Upload Backup File</h4>
						<p class="text-muted small" style="margin: 5px 0 0 0;">
							No file size limit! For very large backups (100GB+), use <a href="#" id="cli-help-link">CLI commands</a> to avoid timeout errors
						</p>
					</div>
					<div class="frappe-card-body">
						<div class="form-group">
							<label>Select Backup File (.zip or .sql)</label>
							<div id="file-upload"></div>
							<p class="help-box small text-muted">
								Upload a backup file in ZIP format (JSON metadata) or SQL format (database dump).
								<strong>File size restriction removed</strong> - you can upload files larger than 25MB.
							</p>
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
				options: {
					restrictions: {
						max_file_size: null, // Remove file size restriction
						allowed_file_types: ['.zip', '.sql', '.gz'] // Only allow backup files
					}
				},
				onchange: () => {
					const file = this.file_upload.get_value();
					if (file) {
						this.handle_file_upload(file);
					}
				}
			},
			render_input: true
		});

		// Override the file input to remove size restrictions
		setTimeout(() => {
			const file_input = container.find('input[type="file"]');
			if (file_input.length) {
				// Remove any size restrictions by handling file directly
				file_input.off('change').on('change', (e) => {
					const file = e.target.files[0];
					if (file) {
						this.handle_direct_file_upload(file);
					}
				});
			}
		}, 100);
	}

	handle_direct_file_upload(file) {
		// Handle file directly without size restrictions
		this.filename = file.name;

		// Show loading message with file size
		const file_size_mb = (file.size / (1024 * 1024)).toFixed(2);
		frappe.show_alert({
			message: __(`Reading file: ${this.filename} (${file_size_mb} MB)`),
			indicator: 'blue'
		}, 5);

		const reader = new FileReader();
		reader.onload = (e) => {
			this.file_data = e.target.result;
			frappe.show_alert({
				message: __('File loaded successfully'),
				indicator: 'green'
			}, 3);
			this.parse_backup_file();
		};

		reader.onerror = (e) => {
			frappe.msgprint(__('Error reading file. Please try again.'));
		};

		reader.readAsDataURL(file);
	}

	handle_file_upload(file_url) {
		// Get file from the URL (fallback method)
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
		const file_type = this.backup_data.file_type || 'json';

		// Show backup info with file type indicator
		const info_html = `
			<div class="alert alert-info" style="margin-bottom: 15px;">
				<strong>File Type:</strong> ${file_type.toUpperCase()}
				${file_type === 'sql' ? '(Database Dump)' : '(JSON Metadata)'}
			</div>
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

		// Show DocTypes table with selection checkboxes
		const table_html = `
			<div style="margin-bottom: 10px;">
				<label>
					<input type="checkbox" id="select-all-doctypes" style="margin-right: 5px;">
					<strong>Select All DocTypes</strong>
				</label>
				<span class="text-muted small" style="margin-left: 10px;">
					(Select specific DocTypes to restore, or restore all)
				</span>
			</div>
			<table class="table table-bordered" style="margin-top: 15px;">
				<thead>
					<tr>
						<th width="40">
							<input type="checkbox" id="header-checkbox" style="display: none;">
						</th>
						<th>DocType</th>
						<th>Records</th>
					</tr>
				</thead>
				<tbody>
					${doctypes.map((dt, idx) => `
						<tr>
							<td>
								<input type="checkbox" class="doctype-checkbox"
									data-doctype="${dt.doctype}"
									id="doctype-${idx}">
							</td>
							<td><label for="doctype-${idx}" style="margin: 0; cursor: pointer;">${dt.doctype}</label></td>
							<td>${dt.record_count}</td>
						</tr>
					`).join('')}
				</tbody>
				<tfoot>
					<tr>
						<th></th>
						<th>Total: ${doctypes.length} DocTypes</th>
						<th>${doctypes.reduce((sum, dt) => sum + dt.record_count, 0)} Records</th>
					</tr>
				</tfoot>
			</table>
		`;
		this.page.main.find('#doctype-list').html(table_html);

		// Setup checkbox handlers
		this.setup_checkbox_handlers();

		// Show preview card
		this.page.main.find('#preview-card').show();
	}

	setup_checkbox_handlers() {
		const page = this;

		// Select all checkbox
		this.page.main.find('#select-all-doctypes').on('change', function() {
			const is_checked = $(this).is(':checked');
			page.page.main.find('.doctype-checkbox').prop('checked', is_checked);
			page.update_selected_doctypes();
		});

		// Individual checkboxes
		this.page.main.find('.doctype-checkbox').on('change', function() {
			page.update_selected_doctypes();

			// Update select-all checkbox state
			const total = page.page.main.find('.doctype-checkbox').length;
			const checked = page.page.main.find('.doctype-checkbox:checked').length;
			page.page.main.find('#select-all-doctypes').prop('checked', total === checked);
		});
	}

	update_selected_doctypes() {
		this.selected_doctypes = [];
		this.page.main.find('.doctype-checkbox:checked').each((i, elem) => {
			this.selected_doctypes.push($(elem).data('doctype'));
		});
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
		// Check if user selected specific doctypes
		if (this.selected_doctypes && this.selected_doctypes.length > 0) {
			// User selected specific doctypes - check for dependencies
			frappe.call({
				method: 'data_tools.data_tools.page.partial_restore.partial_restore.get_doctype_dependencies',
				args: {
					doctypes: this.selected_doctypes
				},
				callback: (r) => {
					if (r.message && r.message.has_dependencies) {
						// Show dependency dialog
						this.show_dependency_dialog(r.message);
					} else {
						// No dependencies, proceed directly
						this.confirm_and_restore();
					}
				}
			});
		} else {
			// No specific selection - restore all
			this.confirm_and_restore();
		}
	}

	confirm_and_restore() {
		const restore_message = this.selected_doctypes && this.selected_doctypes.length > 0
			? __(`Are you sure you want to restore ${this.selected_doctypes.length} selected DocType(s)? This will import records from the backup file.`)
			: __('Are you sure you want to restore this backup? This will import all records from the backup file.');

		frappe.confirm(
			restore_message,
			() => {
				const status_elem = this.page.main.find('#restore-status');
				status_elem.html('<span class="text-primary"><span class="fa fa-spinner fa-spin"></span> Starting restore job...</span>');

				// Start background job
				frappe.call({
					method: 'data_tools.data_tools.page.partial_restore.partial_restore.start_restore_job',
					args: {
						file_data: this.file_data,
						filename: this.filename,
						selected_doctypes: this.selected_doctypes.length > 0 ? this.selected_doctypes : null
					},
					callback: (r) => {
						if (r.message && r.message.success && r.message.job_id) {
							this.job_id = r.message.job_id;
							status_elem.html(
								`<span class="text-primary">
									<span class="fa fa-spinner fa-spin"></span>
									Restore in progress... Please wait.
								</span>`
							);

							// Start polling for job status
							this.poll_restore_job_status();
						} else {
							status_elem.html('<span class="text-danger">Failed to start restore job</span>');
							frappe.msgprint(__('Error starting restore. Please try again.'));
						}
					},
					error: () => {
						status_elem.html('<span class="text-danger">Failed to start restore job</span>');
						frappe.msgprint(__('Error starting restore. Please check the error log.'));
					}
				});
			}
		);
	}

	poll_restore_job_status() {
		const status_elem = this.page.main.find('#restore-status');

		const check_status = () => {
			frappe.call({
				method: 'data_tools.data_tools.page.partial_restore.partial_restore.get_restore_job_status',
				args: {
					job_id: this.job_id
				},
				callback: (r) => {
					if (r.message) {
						const job_data = r.message;

						if (job_data.status === 'completed') {
							// Job completed successfully
							const result = job_data.result;
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
							}, 5);

						} else if (job_data.status === 'failed') {
							// Job failed
							status_elem.html('<span class="text-danger">Restore failed</span>');
							frappe.msgprint(__('Error restoring backup: ' + (job_data.error || 'Unknown error')));

						} else if (job_data.status === 'running' || job_data.status === 'queued') {
							// Job still running - update progress and poll again
							const progress_msg = job_data.progress || 'Processing...';
							status_elem.html(
								`<span class="text-primary">
									<span class="fa fa-spinner fa-spin"></span>
									${progress_msg}
								</span>`
							);

							// Poll again after 2 seconds
							setTimeout(check_status, 2000);

						} else {
							// Unknown status
							status_elem.html('<span class="text-warning">Unknown job status</span>');
						}
					}
				},
				error: () => {
					status_elem.html('<span class="text-danger">Error checking job status</span>');
				}
			});
		};

		// Start polling
		check_status();
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
			dep_checkboxes_html += '<div style="margin-bottom: 10px;"><label style="font-weight: normal;"><input type="checkbox" id="select-all-deps-restore" style="margin-right: 5px;"><strong>Select All</strong></label></div>';
			dep_checkboxes_html += '<hr style="margin: 5px 0;">';

			dep_list.forEach(dep => {
				dep_checkboxes_html += `<div class="checkbox" style="margin: 5px 0;">
					<label style="font-weight: normal; display: flex; align-items: center;">
						<input type="checkbox" class="dep-checkbox-restore" data-doctype="${dep}" checked style="margin-right: 8px;">
						<span>${dep}</span>
					</label>
				</div>`;
			});
		} else {
			dep_checkboxes_html += '<p class="text-muted">No dependencies found.</p>';
		}

		dep_checkboxes_html += '</div>';
		dep_checkboxes_html += '<p class="text-muted small" style="margin-top: 5px;"><strong>Note:</strong> You can uncheck dependencies, but this may cause restore errors if the dependent DocTypes need them.</p>';
		dep_checkboxes_html += '</div>';

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
				dep_dialog.$wrapper.find('.dep-checkbox-restore:checked').each(function() {
					selected_deps.push($(this).data('doctype'));
				});

				dep_dialog.hide();

				// Add selected dependencies to selection
				if (selected_deps.length > 0) {
					const all_doctypes = [...this.selected_doctypes, ...selected_deps];
					// Remove duplicates
					this.selected_doctypes = [...new Set(all_doctypes)];
					frappe.show_alert({
						message: __(`Added ${selected_deps.length} dependent DocType(s) to restore`),
						indicator: 'green'
					}, 3);
				} else if (dep_list.length > 0) {
					// User unchecked all dependencies
					frappe.show_alert({
						message: __('Proceeding without dependencies. This may cause restore errors.'),
						indicator: 'orange'
					}, 5);
				}

				// Proceed with restore
				this.confirm_and_restore();
			}
		});

		// Add select all functionality after dialog is shown
		dep_dialog.show();

		// Setup select all checkbox handler
		dep_dialog.$wrapper.find('#select-all-deps-restore').on('change', function() {
			const isChecked = $(this).is(':checked');
			dep_dialog.$wrapper.find('.dep-checkbox-restore').prop('checked', isChecked);
		});

		// Update select all checkbox when individual checkboxes change
		dep_dialog.$wrapper.find('.dep-checkbox-restore').on('change', function() {
			const totalCheckboxes = dep_dialog.$wrapper.find('.dep-checkbox-restore').length;
			const checkedCheckboxes = dep_dialog.$wrapper.find('.dep-checkbox-restore:checked').length;
			dep_dialog.$wrapper.find('#select-all-deps-restore').prop('checked', totalCheckboxes === checkedCheckboxes);
		});
	}

	reset() {
		this.backup_data = null;
		this.file_data = null;
		this.filename = null;
		this.selected_doctypes = [];
		this.page.main.find('#preview-card').hide();
		this.page.main.find('#log-card').hide();
		this.file_upload.set_value('');
	}

	show_cli_help() {
		const help_dialog = new frappe.ui.Dialog({
			title: __('CLI Restore Commands & Server Configuration'),
			size: 'extra-large',
			fields: [
				{
					fieldtype: 'HTML',
					options: `
						<div style="padding: 15px;">
							<h4><i class="fa fa-terminal"></i> Restore Large Backups via CLI</h4>
							<p class="text-muted">For large backups that cause nginx timeout errors, use these CLI commands on your server.</p>

							<div class="alert alert-info">
								<strong><i class="fa fa-info-circle"></i> Note:</strong> File size restrictions have been removed from this page.
								However, you may need to configure your server for very large files (see Server Configuration section below).
							</div>

							<hr>

							<h5><i class="fa fa-cog"></i> 0. Server Configuration for Large File Uploads</h5>
							<p>Configure these settings to handle large file uploads via web interface:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># 1. Nginx Configuration
# Edit nginx site config
sudo nano /etc/nginx/sites-available/frappe-bench

# Add in server block (0 = unlimited):
client_max_body_size 0;
proxy_read_timeout 3600s;
proxy_connect_timeout 3600s;
proxy_send_timeout 3600s;

# Reload nginx
sudo systemctl reload nginx

# 2. Frappe Site Configuration
# Edit site_config.json
nano sites/[site-name]/site_config.json

# Add (10GB limit example):
{
  "max_file_size": 10485760000,
  "http_timeout": 3600
}

# 3. Gunicorn Configuration (if using)
# Edit gunicorn config
nano config/gunicorn_config.py

# Add/update:
timeout = 3600
worker_class = "sync"

# Restart services
bench restart
</code></pre>

							<hr>

							<h5>1. Restore Full Site Backup</h5>
							<p>Restore a complete site backup created with bench backup:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># Navigate to bench directory
cd /path/to/frappe-bench

# Restore database, files, and private files
bench --site [site-name] restore /path/to/backup/[timestamp]-[site-name]-database.sql.gz

# Restore with force (skip confirmation)
bench --site [site-name] --force restore /path/to/backup.sql.gz

# Restore specific components
bench --site [site-name] restore /path/to/database.sql.gz --with-public-files /path/to/files.tar
bench --site [site-name] restore /path/to/database.sql.gz --with-private-files /path/to/private-files.tar
</code></pre>

							<h5>2. Restore SQL Backup (Direct MySQL)</h5>
							<p>Import SQL file directly to database:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># Get database credentials
cat sites/[site-name]/site_config.json

# Restore SQL file
mysql -u [db_user] -p[db_password] [db_name] < backup.sql

# Restore compressed SQL file
gunzip < backup.sql.gz | mysql -u [db_user] -p[db_password] [db_name]

# With progress monitoring (requires pv)
pv backup.sql | mysql -u [db_user] -p[db_password] [db_name]

# Restore with verbose output
mysql -u [db_user] -p[db_password] [db_name] -v < backup.sql
</code></pre>

							<h5>3. Restore Partial Backup (Specific Tables)</h5>
							<p>Import only specific tables from a partial backup:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># Restore partial backup SQL file
mysql -u [db_user] -p[db_password] [db_name] < partial_backup.sql

# Check which tables are in the backup
grep "CREATE TABLE" partial_backup.sql

# Extract and restore specific table only
sed -n '/CREATE TABLE \`tabCustomer\`/,/UNLOCK TABLES/p' partial_backup.sql | mysql -u [db_user] -p[db_password] [db_name]
</code></pre>

							<h5>4. Restore with Error Handling</h5>
							<p>Handle errors during restore:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># Force restore (ignore errors)
mysql -u [db_user] -p[db_password] [db_name] --force < backup.sql

# Log errors to file
mysql -u [db_user] -p[db_password] [db_name] < backup.sql 2> restore_errors.log

# Skip foreign key checks (useful for partial restores)
mysql -u [db_user] -p[db_password] [db_name] -e "SET FOREIGN_KEY_CHECKS=0; SOURCE backup.sql; SET FOREIGN_KEY_CHECKS=1;"
</code></pre>

							<h5>5. Post-Restore Tasks</h5>
							<p>After restoring via CLI:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># Clear cache
bench --site [site-name] clear-cache

# Rebuild search index
bench --site [site-name] build-search-index

# Migrate if needed
bench --site [site-name] migrate

# Restart services
sudo systemctl restart supervisor
</code></pre>

							<h5>6. Troubleshooting</h5>
							<p>Common issues and solutions:</p>
							<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto;"><code># If restore hangs, check MySQL processlist
mysql -u root -p -e "SHOW PROCESSLIST;"

# Check MySQL error log
tail -f /var/log/mysql/error.log

# Check available disk space
df -h

# Monitor memory usage during restore
watch -n 1 free -m

# If out of memory, increase swap or use smaller batch sizes
# Edit backup SQL to reduce INSERT batch sizes before restore
</code></pre>

							<hr>

							<div class="alert alert-info">
								<strong><i class="fa fa-info-circle"></i> Best Practices:</strong>
								<ul>
									<li>Always create a backup before restoring</li>
									<li>Test restore on development/staging site first</li>
									<li>Use <code>--force</code> flag with bench restore for automated scripts</li>
									<li>Monitor disk space - ensure you have 2x backup size available</li>
									<li>For very large databases, restore during off-peak hours</li>
									<li>Use <code>screen</code> or <code>tmux</code> for long-running operations</li>
								</ul>
							</div>

							<div class="alert alert-warning">
								<strong><i class="fa fa-exclamation-triangle"></i> Important:</strong>
								<ul>
									<li>Replace [site-name] with actual site name</li>
									<li>Replace [db_user], [db_password], [db_name] from site_config.json</li>
									<li>Ensure SET FOREIGN_KEY_CHECKS=0 is used for partial restores</li>
									<li>Always run migrations after restore: <code>bench --site [site-name] migrate</code></li>
									<li>Restore may drop and recreate tables - existing data will be lost</li>
								</ul>
							</div>

							<div class="alert alert-success">
								<strong><i class="fa fa-lightbulb-o"></i> Pro Tip:</strong><br>
								For massive databases (100GB+), consider using:
								<ul>
									<li><code>mydumper/myloader</code> - parallel dump and restore tool</li>
									<li>Percona XtraBackup - hot backup without locking</li>
									<li>Database replication for minimal downtime</li>
								</ul>
							</div>
						</div>
					`
				}
			],
			primary_action_label: __('Close')
		});

		help_dialog.show();

		// Add click handler for inline help link
		setTimeout(() => {
			this.page.main.find('#cli-help-link').on('click', (e) => {
				e.preventDefault();
				this.show_cli_help();
			});
		}, 100);
	}
}
