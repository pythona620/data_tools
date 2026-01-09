# -*- coding: utf-8 -*-
# Copyright (c) 2025, Admin and contributors
# For license information, please see license.txt

import frappe
import json
import os
from frappe import _
from frappe.model.document import get_controller
import zipfile
from io import BytesIO, StringIO
import base64
import uuid
from frappe.utils.background_jobs import enqueue
import shutil
from pathlib import Path
import logging
import csv
from data_tools.data_tools.doctype_dependencies import (
	get_dependency_summary,
	get_dependency_graph,
	topological_sort
)

logger = logging.getLogger(__name__)


@frappe.whitelist()
def get_all_doctypes():
	"""Get all DocTypes with their modules for filtering"""
	doctypes = frappe.db.sql("""
		SELECT
			name,
			module,
			COALESCE(custom, 0) as is_custom,
			COALESCE(issingle, 0) as is_single
		FROM `tabDocType`
		WHERE
			istable = 0
		ORDER BY module, name
	""", as_dict=True)

	return doctypes


@frappe.whitelist()
def get_modules():
	"""Get unique modules for filtering"""
	modules = frappe.db.sql("""
		SELECT DISTINCT module
		FROM `tabDocType`
		WHERE istable = 0
		ORDER BY module
	""", as_list=True)

	return [m[0] for m in modules if m[0]]


@frappe.whitelist()
def get_apps():
	"""Get all installed apps for filtering"""
	apps = frappe.get_installed_apps()
	return apps


@frappe.whitelist()
def get_doctype_fields(doctype):
	"""Get all fields for a specific DocType

	Args:
		doctype: Name of the DocType

	Returns:
		list: List of field names with their labels
	"""
	try:
		meta = frappe.get_meta(doctype)
		fields = []

		# Add standard fields
		standard_fields = [
			{'fieldname': 'name', 'label': 'ID/Name'},
			{'fieldname': 'owner', 'label': 'Owner'},
			{'fieldname': 'creation', 'label': 'Creation'},
			{'fieldname': 'modified', 'label': 'Modified'},
			{'fieldname': 'modified_by', 'label': 'Modified By'},
			{'fieldname': 'docstatus', 'label': 'Document Status'}
		]

		# Add custom fields from DocType
		for field in meta.fields:
			if field.fieldtype not in ['Table', 'Section Break', 'Column Break', 'Tab Break', 'HTML', 'Button']:
				fields.append({
					'fieldname': field.fieldname,
					'label': field.label or field.fieldname,
					'fieldtype': field.fieldtype
				})

		# Combine and return
		all_fields = standard_fields + fields
		return all_fields

	except Exception as e:
		frappe.log_error(f"Error getting fields for {doctype}: {str(e)}")
		return []


@frappe.whitelist()
def get_doctypes_by_app(app_names):
	"""Get all DocTypes belonging to specific app(s)

	Args:
		app_names: String (single app) or JSON array of app names
	"""
	if not app_names:
		return get_all_doctypes()

	# Parse app_names if it's a JSON string
	if isinstance(app_names, str):
		try:
			# Try to parse as JSON first
			parsed = json.loads(app_names)
			if isinstance(parsed, list):
				app_names = parsed
			else:
				app_names = [str(parsed)]
		except (json.JSONDecodeError, ValueError):
			# If it's not JSON, treat it as a single app name
			app_names = [app_names]

	# Ensure it's a list
	if not isinstance(app_names, list):
		app_names = [app_names]

	# Log for debugging
	logger.info(f"Getting DocTypes for apps: {app_names}")

	# Get modules for all selected apps
	all_modules = []
	for app_name in app_names:
		try:
			app_modules = frappe.get_module_list(app_name)
			logger.info(f"App '{app_name}' has modules: {app_modules}")
			all_modules.extend(app_modules)
		except Exception as e:
			# If we can't get modules for the app, skip it
			logger.warning(f"Error getting modules for app '{app_name}': {str(e)}")
			continue

	# Remove duplicates
	all_modules = list(set(all_modules))

	logger.info(f"Total unique modules: {len(all_modules)}")

	if not all_modules:
		logger.warning("No modules found for selected apps")
		return []

	doctypes = frappe.db.sql("""
		SELECT
			name,
			module,
			COALESCE(custom, 0) as is_custom,
			COALESCE(issingle, 0) as is_single
		FROM `tabDocType`
		WHERE
			istable = 0
			AND module IN %(modules)s
		ORDER BY module, name
	""", {"modules": all_modules}, as_dict=True)

	logger.info(f"Found {len(doctypes)} DocTypes")

	return doctypes


@frappe.whitelist()
def get_doctype_dependencies(doctypes):
	"""Get dependency information for selected DocTypes

	Args:
		doctypes: List of DocType names or JSON string

	Returns:
		dict: Dependency summary including all dependent DocTypes
	"""
	if isinstance(doctypes, str):
		doctypes = json.loads(doctypes)

	if not doctypes or not isinstance(doctypes, list):
		return {
			'selected_doctypes': [],
			'selected_count': 0,
			'dependencies_by_doctype': {},
			'all_new_dependencies': [],
			'new_dependency_count': 0,
			'total_with_dependencies': 0,
			'has_dependencies': False
		}

	return get_dependency_summary(doctypes)


@frappe.whitelist()
def get_dependency_graph_data(doctypes):
	"""Get dependency graph data for visualization

	Args:
		doctypes: List of DocType names or JSON string

	Returns:
		dict: Graph data with nodes and edges
	"""
	if isinstance(doctypes, str):
		doctypes = json.loads(doctypes)

	if not doctypes or not isinstance(doctypes, list):
		return {'nodes': [], 'edges': [], 'selected_count': 0, 'dependency_count': 0, 'total_count': 0}

	return get_dependency_graph(doctypes)


@frappe.whitelist()
def sort_doctypes_by_dependencies(doctypes):
	"""Sort DocTypes in correct order based on dependencies

	Args:
		doctypes: List of DocType names or JSON string

	Returns:
		list: Sorted list of DocTypes
	"""
	if isinstance(doctypes, str):
		doctypes = json.loads(doctypes)

	if not doctypes or not isinstance(doctypes, list):
		return []

	return topological_sort(doctypes)


@frappe.whitelist()
def create_partial_backup(doctypes, export_format='json', include_files=False, field_transformations=None, table_transformations=None):
	"""Create a partial backup of selected DocTypes

	Args:
		doctypes: List of DocType names to backup
		export_format: 'json' or 'sql' (default: 'json')
		include_files: Boolean to include file attachments (default: False)
		field_transformations: Optional list of field transformation rules (JSON string or list)
			Format: [{"doctype": "Employee", "field": "company", "old_value": "Test", "new_value": "caratred"}]
		table_transformations: Optional list of table name transformation rules (JSON string or list)
			Format: [{"old_table_name": "tabCompeny", "new_table_name": "tabCompany"}]
	"""
	if isinstance(doctypes, str):
		doctypes = json.loads(doctypes)

	if not doctypes or not isinstance(doctypes, list) or len(doctypes) == 0:
		frappe.throw(_("Please select at least one DocType"))

	# Convert include_files to boolean
	if isinstance(include_files, str):
		include_files = include_files.lower() in ['true', '1', 'yes']

	# Parse field_transformations if it's a JSON string
	if isinstance(field_transformations, str):
		try:
			field_transformations = json.loads(field_transformations)
		except (json.JSONDecodeError, ValueError):
			field_transformations = None

	# Parse table_transformations if it's a JSON string
	if isinstance(table_transformations, str):
		try:
			table_transformations = json.loads(table_transformations)
		except (json.JSONDecodeError, ValueError):
			table_transformations = None

	if export_format == 'sql':
		return create_sql_backup(doctypes, include_files, None, field_transformations, table_transformations)
	elif export_format == 'csv':
		return create_csv_backup(doctypes, include_files, None, field_transformations)
	else:
		return create_json_backup(doctypes, include_files, None, field_transformations, table_transformations)


@frappe.whitelist()
def start_backup_job(doctypes, export_format='json', include_files=False, field_transformations=None, table_transformations=None):
	"""Start a background job for backup creation

	Args:
		doctypes: List of DocType names to backup
		export_format: 'json' or 'sql' (default: 'json')
		include_files: Boolean to include file attachments (default: False)
		field_transformations: Optional list of field transformation rules (JSON string or list)
		table_transformations: Optional list of table name transformation rules (JSON string or list)

	Returns:
		dict: Contains job_id for tracking
	"""
	if isinstance(doctypes, str):
		doctypes = json.loads(doctypes)

	if not doctypes or not isinstance(doctypes, list) or len(doctypes) == 0:
		frappe.throw(_("Please select at least one DocType"))

	# Convert include_files to boolean
	if isinstance(include_files, str):
		include_files = include_files.lower() in ['true', '1', 'yes']

	# Parse field_transformations if it's a JSON string
	if isinstance(field_transformations, str):
		try:
			field_transformations = json.loads(field_transformations)
		except (json.JSONDecodeError, ValueError):
			field_transformations = None

	# Parse table_transformations if it's a JSON string
	if isinstance(table_transformations, str):
		try:
			table_transformations = json.loads(table_transformations)
		except (json.JSONDecodeError, ValueError):
			table_transformations = None

	# Generate unique job ID
	job_id = str(uuid.uuid4())

	# Store job metadata in cache
	job_data = {
		'status': 'queued',
		'progress': 'Starting backup...',
		'doctypes': doctypes,
		'export_format': export_format,
		'include_files': include_files,
		'field_transformations': field_transformations,
		'table_transformations': table_transformations,
		'created_by': frappe.session.user,
		'created_at': frappe.utils.now()
	}
	# Extended cache expiration to match job timeout (12 hours + 2 hour buffer = 14 hours)
	frappe.cache().set_value(f'backup_job_{job_id}', json.dumps(job_data), expires_in_sec=50400)

	# Enqueue the backup job with extended timeout for very large datasets
	# Increased to 43200 (12 hours) to handle 200+ doctypes with 100GB+ data
	enqueue(
		method=execute_backup_job,
		queue='long',
		timeout=43200,
		backup_job_id=job_id,
		doctypes=doctypes,
		export_format=export_format,
		include_files=include_files,
		field_transformations=field_transformations,
		table_transformations=table_transformations
	)

	return {
		'job_id': job_id,
		'status': 'queued'
	}


def execute_backup_job(backup_job_id, doctypes, export_format='json', include_files=False, field_transformations=None, table_transformations=None):
	"""Execute the backup job in background

	Args:
		backup_job_id: Unique job identifier
		doctypes: List of DocType names to backup
		export_format: 'json' or 'sql'
		include_files: Boolean to include file attachments
		field_transformations: Optional list of field transformation rules
		table_transformations: Optional list of table name transformation rules
	"""
	try:
		# Get job data to retrieve user
		job_data = json.loads(frappe.cache().get_value(f'backup_job_{backup_job_id}') or '{}')

		# Set user context for the background job
		if job_data.get('created_by'):
			frappe.set_user(job_data.get('created_by'))

		# Update job status to running
		job_data['status'] = 'running'
		job_data['progress'] = 'Initializing backup...'
		frappe.cache().set_value(f'backup_job_{backup_job_id}', json.dumps(job_data), expires_in_sec=50400)

		# Initialize status tracking for all doctypes
		initialize_all_doctype_status(backup_job_id, doctypes)

		# Create backup
		if export_format == 'sql':
			result = create_sql_backup(doctypes, include_files, backup_job_id, field_transformations, table_transformations)
		elif export_format == 'csv':
			result = create_csv_backup(doctypes, include_files, backup_job_id, field_transformations)
		else:
			result = create_json_backup(doctypes, include_files, backup_job_id, field_transformations, table_transformations)

		# Save backup file to temp location
		backup_dir = frappe.get_site_path('private', 'files', 'partial_backups')
		os.makedirs(backup_dir, exist_ok=True)

		file_path = os.path.join(backup_dir, f"{backup_job_id}_{result['filename']}")

		# Decode and save file
		file_content = base64.b64decode(result['file_data'])
		with open(file_path, 'wb') as f:
			f.write(file_content)

		# Verify file was created
		if not os.path.exists(file_path):
			raise Exception(f"Failed to create backup file at {file_path}")

		file_size = os.path.getsize(file_path)
		logger.info(f"Backup job {backup_job_id} completed. File: {file_path} ({file_size} bytes)")

		# Update job status to completed
		job_data['status'] = 'completed'
		job_data['progress'] = 'Backup completed successfully'
		job_data['file_path'] = file_path
		job_data['filename'] = result['filename']
		job_data['total_doctypes'] = result['total_doctypes']
		job_data['total_records'] = result['total_records']
		job_data['total_files'] = result.get('total_files', 0)
		job_data['completed_at'] = frappe.utils.now()

		# Save to cache with extended expiration (14 hours)
		cache_key = f'backup_job_{backup_job_id}'
		cache_value = json.dumps(job_data)
		frappe.cache().set_value(cache_key, cache_value, expires_in_sec=50400)

		# Verify cache was set
		verify = frappe.cache().get_value(cache_key)
		if not verify:
			logger.error(f"Failed to set cache for {cache_key}")
			frappe.log_error(f"Cache Error: {cache_key}", "Backup Cache Failed")

		frappe.db.commit()

	except Exception as e:
		# Update job status to failed
		frappe.log_error(f"Backup job {backup_job_id} failed: {str(e)}", "Backup Job Error")
		job_data = json.loads(frappe.cache().get_value(f'backup_job_{backup_job_id}') or '{}')
		job_data['status'] = 'failed'
		job_data['error'] = str(e)
		job_data['failed_at'] = frappe.utils.now()
		frappe.cache().set_value(f'backup_job_{backup_job_id}', json.dumps(job_data), expires_in_sec=50400)
		frappe.db.commit()


@frappe.whitelist()
def get_job_status(job_id):
	"""Get the status of a backup job

	Args:
		job_id: Unique job identifier

	Returns:
		dict: Job status information
	"""
	job_data = frappe.cache().get_value(f'backup_job_{job_id}')

	if not job_data:
		return {
			'status': 'not_found',
			'error': 'Job not found or expired'
		}

	job_info = json.loads(job_data)

	return {
		'status': job_info.get('status'),
		'progress': job_info.get('progress'),
		'error': job_info.get('error'),
		'total_doctypes': job_info.get('total_doctypes'),
		'total_records': job_info.get('total_records'),
		'total_files': job_info.get('total_files', 0)
	}


@frappe.whitelist()
def download_backup(job_id):
	"""Download a completed backup file

	Args:
		job_id: Unique job identifier

	Returns:
		dict: File URL for download or file data for small files
	"""
	try:
		logger.info(f"Download request for job {job_id}")
		job_data = frappe.cache().get_value(f'backup_job_{job_id}')

		if not job_data:
			logger.error(f"Job {job_id} not found in cache")
			frappe.throw(_("Job not found or expired"))

		job_info = json.loads(job_data)
		logger.info(f"Job {job_id} status: {job_info.get('status')}")

		if job_info.get('status') != 'completed':
			status = job_info.get('status', 'unknown')
			logger.error(f"Job {job_id} status is {status}, not completed")
			frappe.throw(_("Backup is not completed yet. Status: {0}").format(status))

		file_path = job_info.get('file_path')
		if not file_path:
			logger.error(f"Job {job_id} has no file_path")
			frappe.throw(_("Backup file path not found"))

		logger.info(f"Job {job_id} file path: {file_path}")

		if not os.path.exists(file_path):
			logger.error(f"Job {job_id} file does not exist at {file_path}")
			frappe.throw(_("Backup file not found at expected location"))

		# Get file size
		file_size = os.path.getsize(file_path)
		logger.info(f"Job {job_id} file size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")

		# For large files (>10MB), use direct file serving instead of base64
		if file_size > 10 * 1024 * 1024:  # 10 MB
			logger.info(f"Large file detected, using direct download method")

			# Move file to private/files for download
			filename = job_info.get('filename')
			download_folder = frappe.get_site_path('private', 'files', 'downloads')
			os.makedirs(download_folder, exist_ok=True)

			download_path = os.path.join(download_folder, filename)

			# Move the file
			shutil.move(file_path, download_path)
			logger.info(f"Moved file to {download_path}")

			# Return download URL
			return {
				'success': True,
				'use_url': True,
				'download_url': f'/api/method/data_tools.data_tools.page.partial_backup.partial_backup.serve_backup_file?filename={filename}',
				'filename': filename,
				'total_doctypes': job_info.get('total_doctypes'),
				'total_records': job_info.get('total_records'),
				'total_files': job_info.get('total_files', 0),
				'file_size': file_size
			}
		else:
			# For small files, use the old method (base64 encoding)
			logger.info(f"Small file, using base64 encoding")
			with open(file_path, 'rb') as f:
				file_content = f.read()

			file_data = base64.b64encode(file_content).decode()
			logger.info(f"Job {job_id} file read successfully, size: {len(file_content)} bytes")

			# Clean up the file after download
			try:
				os.remove(file_path)
				logger.info(f"Job {job_id} file cleaned up")
			except Exception as e:
				logger.warning(f"Error removing file {file_path}: {str(e)}")

			return {
				'success': True,
				'use_url': False,
				'file_data': file_data,
				'filename': job_info.get('filename'),
				'total_doctypes': job_info.get('total_doctypes'),
				'total_records': job_info.get('total_records'),
				'total_files': job_info.get('total_files', 0),
				'file_size': file_size
			}

	except Exception as e:
		logger.error(f"Error downloading backup {job_id}: {str(e)}")
		frappe.log_error(f"Download failed: {str(e)}", f"Backup Download Error")
		raise


@frappe.whitelist()
def serve_backup_file(filename):
	"""Serve a backup file for download

	Args:
		filename: Name of the backup file to serve
	"""
	try:
		download_folder = frappe.get_site_path('private', 'files', 'downloads')
		file_path = os.path.join(download_folder, filename)

		if not os.path.exists(file_path):
			frappe.throw(_("Backup file not found"))

		# Serve the file
		frappe.local.response.filename = filename
		frappe.local.response.filecontent = open(file_path, 'rb').read()
		frappe.local.response.type = "download"

		# Clean up after serving
		try:
			os.remove(file_path)
			logger.info(f"Cleaned up downloaded file: {filename}")
		except Exception as e:
			logger.warning(f"Error removing file {file_path}: {str(e)}")

	except Exception as e:
		logger.error(f"Error serving backup file {filename}: {str(e)}")
		frappe.throw(_("Error downloading file"))


def apply_table_transformation(table_name, table_transformations):
	"""Apply table name transformation if matching rule exists

	Args:
		table_name: Original table name (e.g., "tabCompeny")
		table_transformations: List of transformation rules
			Format: [{"old_table_name": "tabCompeny", "new_table_name": "tabCompany"}]

	Returns:
		str: Transformed table name or original if no match
	"""
	if not table_transformations:
		return table_name

	for transform in table_transformations:
		old_name = transform.get('old_table_name')
		new_name = transform.get('new_table_name')

		if old_name and new_name and table_name == old_name:
			logger.info(f"Transforming table name: '{old_name}' → '{new_name}'")
			return new_name

	return table_name


def apply_field_transformations(records, doctype_name, transformations):
	"""Apply field value transformations to records

	Args:
		records: List of record dictionaries
		doctype_name: Name of the DocType being processed
		transformations: List of transformation rules
			Format: [
				{
					"doctype": "Employee",
					"field": "company",
					"old_value": "Test",
					"new_value": "caratred"
				}
			]

	Returns:
		list: Records with transformations applied
	"""
	if not transformations or not records:
		return records

	# Filter transformations for this doctype
	doctype_transformations = [
		t for t in transformations
		if t.get('doctype', '').lower() == doctype_name.lower()
	]

	if not doctype_transformations:
		return records

	logger.info(f"Applying {len(doctype_transformations)} transformation(s) to {doctype_name}")
	logger.info(f"Transformations: {doctype_transformations}")
	logger.info(f"Number of records: {len(records)}")

	# Log first record's keys for debugging
	if records:
		logger.info(f"Sample record keys: {list(records[0].keys())}")

	# Apply transformations to each record
	for record in records:
		for transform in doctype_transformations:
			field_name = transform.get('field')
			old_value = transform.get('old_value')
			new_value = transform.get('new_value')

			if not field_name:
				continue

			# Find the actual field name (case-insensitive match)
			actual_field_name = None
			for key in record.keys():
				if key.lower() == field_name.lower():
					actual_field_name = key
					break

			# Check if field exists in record
			if actual_field_name:
				current_value = record[actual_field_name]

				# Apply transformation if value matches
				# Treat None or empty string as "replace all values"
				should_replace = (
					old_value is None or
					old_value == '' or
					str(current_value) == str(old_value)
				)

				if should_replace:
					record[actual_field_name] = new_value
					logger.info(f"Transformed {doctype_name}.{actual_field_name}: '{current_value}' → '{new_value}'")
			else:
				logger.warning(f"Field '{field_name}' not found in {doctype_name} record. Available fields: {list(record.keys())}")

	return records


def create_json_backup(doctypes, include_files=False, job_id=None, field_transformations=None, table_transformations=None):
	"""Create JSON backup of selected DocTypes

	Args:
		doctypes: List of DocType names to backup
		include_files: Boolean to include file attachments
		job_id: Optional job ID for progress tracking
		field_transformations: Optional list of field transformation rules
		table_transformations: Optional list of table name transformation rules
	"""
	backup_data = {
		"backup_info": {
			"created_by": frappe.session.user,
			"creation_date": frappe.utils.now(),
			"frappe_version": frappe.__version__,
			"total_doctypes": len(doctypes),
			"include_files": include_files
		},
		"doctypes": []
	}

	total_records = 0
	total_files = 0
	file_paths = []  # Track files to include in backup

	for idx, doctype_name in enumerate(doctypes):
		try:
			# Get table size information
			table_info = get_table_size(doctype_name)

			# Update progress and status if job_id is provided
			if job_id:
				update_job_progress(job_id, f"Processing {doctype_name} ({idx+1}/{len(doctypes)}) - Size: {table_info['size_mb']}MB, Rows: {table_info['row_count']}")
				update_doctype_status(job_id, doctype_name, 'processing', table_info['size_mb'], 0)

			# Get DocType definition
			doctype_doc = frappe.get_doc("DocType", doctype_name)
			doctype_json = doctype_doc.as_dict()

			# Get all records for this DocType
			records = []
			if doctype_doc.issingle:
				# Single DocType - get the single document
				if frappe.db.exists(doctype_name, doctype_name):
					doc = frappe.get_doc(doctype_name, doctype_name)
					records.append(doc.as_dict())
			else:
				# Regular DocType - get all documents efficiently in batches
				# Use bulk fetching to reduce database round trips
				batch_size = 500  # Fetch 500 records at a time
				doc_names = frappe.get_all(doctype_name, pluck='name')

				# Process in batches to optimize memory and speed
				for i in range(0, len(doc_names), batch_size):
					batch_names = doc_names[i:i + batch_size]
					for name in batch_names:
						try:
							doc = frappe.get_doc(doctype_name, name)
							records.append(doc.as_dict())
						except Exception as e:
							frappe.log_error(f"Error fetching {doctype_name} - {name}: {str(e)}")

					# Update progress for large doctypes
					if job_id and len(doc_names) > batch_size:
						progress_pct = ((i + len(batch_names)) / len(doc_names)) * 100
						update_job_progress(job_id, f"Processing {doctype_name} ({idx+1}/{len(doctypes)}) - {progress_pct:.1f}% ({i + len(batch_names)}/{len(doc_names)} records)...")

			# Apply field transformations if specified
			if field_transformations:
				records = apply_field_transformations(records, doctype_name, field_transformations)

			# Collect file attachments if requested
			doctype_files = []
			if include_files:
				doctype_files = get_doctype_files(doctype_name, records)
				file_paths.extend(doctype_files)
				total_files += len(doctype_files)

			backup_data["doctypes"].append({
				"doctype": doctype_name,
				"definition": doctype_json,
				"records": records,
				"record_count": len(records),
				"file_count": len(doctype_files) if include_files else 0
			})

			total_records += len(records)

			# Mark doctype as completed
			if job_id:
				update_doctype_status(job_id, doctype_name, 'completed', table_info['size_mb'], len(records))

		except Exception as e:
			error_msg = str(e)
			frappe.log_error(f"Error backing up {doctype_name}: {error_msg}", "JSON Backup Error")

			# Mark doctype as failed
			if job_id:
				update_doctype_status(job_id, doctype_name, 'failed', 0, 0, error_msg)

			# Continue with other doctypes

	backup_data["backup_info"]["total_records"] = total_records
	backup_data["backup_info"]["total_files"] = total_files

	# Ensure all doctypes in the backup are marked as completed
	if job_id:
		finalize_backup_status(job_id, doctypes, backup_data["doctypes"])

	# Update progress
	if job_id:
		update_job_progress(job_id, "Creating backup archive...")

	# Create ZIP file
	zip_buffer = BytesIO()
	with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
		# Add JSON data to ZIP
		json_data = json.dumps(backup_data, indent=2, default=str)
		zip_file.writestr('backup_data.json', json_data)

		# Add metadata file
		metadata = {
			"doctypes": [dt["doctype"] for dt in backup_data["doctypes"]],
			"total_records": total_records,
			"total_files": total_files,
			"include_files": include_files,
			"created_by": frappe.session.user,
			"creation_date": frappe.utils.now()
		}
		zip_file.writestr('metadata.json', json.dumps(metadata, indent=2, default=str))

		# Add files to ZIP
		if include_files and file_paths:
			if job_id:
				update_job_progress(job_id, f"Adding {len(file_paths)} files to backup...")

			files_added = 0
			files_failed = 0

			for file_info in file_paths:
				try:
					# Handle both absolute and relative paths
					file_url = file_info['file_path']

					# Get the actual file path on disk
					if file_url.startswith('/files/'):
						# Public file
						file_path = frappe.get_site_path('public', 'files', file_url.replace('/files/', ''))
					elif file_url.startswith('/private/files/'):
						# Private file
						file_path = frappe.get_site_path('private', 'files', file_url.replace('/private/files/', ''))
					else:
						# Try direct path
						file_path = frappe.get_site_path() + file_url

					if os.path.exists(file_path):
						# Add file with relative path in zip
						arcname = f"files{file_url}"
						zip_file.write(file_path, arcname)
						files_added += 1
						logger.debug(f"Added file: {file_url}")
					else:
						logger.warning(f"File not found: {file_path}")
						files_failed += 1
				except Exception as e:
					logger.error(f"Error adding file {file_info.get('file_path')}: {str(e)}")
					files_failed += 1

			logger.info(f"Files added: {files_added}, failed: {files_failed}")

	# Encode to base64 for download
	zip_buffer.seek(0)
	file_data = base64.b64encode(zip_buffer.getvalue()).decode()

	return {
		"success": True,
		"file_data": file_data,
		"filename": f"partial_backup_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip",
		"total_doctypes": len(backup_data["doctypes"]),
		"total_records": total_records,
		"total_files": total_files
	}


def create_csv_backup(doctypes, include_files=False, job_id=None, field_transformations=None):
	"""Create CSV backup of selected DocTypes (records only)

	Args:
		doctypes: List of DocType names to backup
		include_files: Boolean to include file attachments
		job_id: Optional job ID for progress tracking
		field_transformations: Optional list of field transformation rules
	"""
	total_records = 0
	total_files = 0
	file_paths = []
	doctype_record_counts = {}  # Track record count per doctype for status finalization

	# Create ZIP file to hold multiple CSV files
	zip_buffer = BytesIO()
	with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
		for idx, doctype_name in enumerate(doctypes):
			try:
				# Get table size information
				table_info = get_table_size(doctype_name)

				# Update progress and status if job_id is provided
				if job_id:
					update_job_progress(job_id, f"Processing {doctype_name} ({idx+1}/{len(doctypes)}) - Size: {table_info['size_mb']}MB, Rows: {table_info['row_count']}")
					update_doctype_status(job_id, doctype_name, 'processing', table_info['size_mb'], 0)

				# Get DocType definition
				doctype_doc = frappe.get_doc("DocType", doctype_name)

				# Get all records for this DocType
				records = []
				if doctype_doc.issingle:
					# Single DocType - get the single document
					if frappe.db.exists(doctype_name, doctype_name):
						doc = frappe.get_doc(doctype_name, doctype_name)
						records.append(doc.as_dict())
				else:
					# Regular DocType - get all documents efficiently in batches
					batch_size = 500  # Fetch 500 records at a time
					doc_names = frappe.get_all(doctype_name, pluck='name')

					# Process in batches to optimize memory and speed
					for i in range(0, len(doc_names), batch_size):
						batch_names = doc_names[i:i + batch_size]
						for name in batch_names:
							try:
								doc = frappe.get_doc(doctype_name, name)
								records.append(doc.as_dict())
							except Exception as e:
								frappe.log_error(f"Error fetching {doctype_name} - {name}: {str(e)}")

						# Update progress for large doctypes
						if job_id and len(doc_names) > batch_size:
							progress_pct = ((i + len(batch_names)) / len(doc_names)) * 100
							update_job_progress(job_id, f"Processing {doctype_name} ({idx+1}/{len(doctypes)}) - {progress_pct:.1f}% ({i + len(batch_names)}/{len(doc_names)} records)...")

				# Apply field transformations if specified
				if field_transformations:
					records = apply_field_transformations(records, doctype_name, field_transformations)

				# Generate CSV for this DocType
				if records:
					csv_buffer = StringIO()

					# Get all field names from first record
					fieldnames = list(records[0].keys())

					# Create CSV writer
					writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
					writer.writeheader()

					# Write all records
					for record in records:
						# Convert None values to empty strings and handle complex types
						clean_record = {}
						for key, value in record.items():
							if value is None:
								clean_record[key] = ''
							elif isinstance(value, (dict, list)):
								clean_record[key] = json.dumps(value)
							else:
								clean_record[key] = str(value)
						writer.writerow(clean_record)

					# Add CSV file to ZIP
					csv_content = csv_buffer.getvalue()
					zip_file.writestr(f"{doctype_name}.csv", csv_content)

					total_records += len(records)
					logger.info(f"Added {len(records)} records for {doctype_name} to CSV backup")

				# Collect file attachments if requested
				if include_files and records:
					doctype_files = get_doctype_files(doctype_name, records)
					file_paths.extend(doctype_files)
					total_files += len(doctype_files)

				# Track record count for this doctype
				record_count = len(records) if records else 0
				doctype_record_counts[doctype_name] = record_count

				# Mark doctype as completed
				if job_id:
					update_doctype_status(job_id, doctype_name, 'completed', table_info['size_mb'], record_count)

			except Exception as e:
				error_msg = f"Error backing up {doctype_name}: {str(e)}"
				frappe.log_error(error_msg, "CSV Backup Error")
				logger.error(error_msg)

				# Mark doctype as failed
				if job_id:
					update_doctype_status(job_id, doctype_name, 'failed', 0, 0, error_msg)

		# Add metadata file
		metadata = {
			"export_format": "csv",
			"doctypes": doctypes,
			"total_records": total_records,
			"total_files": total_files,
			"include_files": include_files,
			"created_by": frappe.session.user,
			"creation_date": frappe.utils.now()
		}
		zip_file.writestr('metadata.json', json.dumps(metadata, indent=2, default=str))

		# Add files to ZIP if requested
		if include_files and file_paths:
			if job_id:
				update_job_progress(job_id, f"Adding {len(file_paths)} files to backup...")

			files_added = 0
			files_failed = 0

			for file_info in file_paths:
				try:
					file_url = file_info['file_path']

					# Get the actual file path on disk
					if file_url.startswith('/files/'):
						file_path = frappe.get_site_path('public', 'files', file_url.replace('/files/', ''))
					elif file_url.startswith('/private/files/'):
						file_path = frappe.get_site_path('private', 'files', file_url.replace('/private/files/', ''))
					else:
						file_path = frappe.get_site_path() + file_url

					if os.path.exists(file_path):
						arcname = f"files{file_url}"
						zip_file.write(file_path, arcname)
						files_added += 1
					else:
						logger.warning(f"File not found: {file_path}")
						files_failed += 1
				except Exception as e:
					logger.error(f"Error adding file {file_info.get('file_path')}: {str(e)}")
					files_failed += 1

			logger.info(f"CSV backup - Files added: {files_added}, failed: {files_failed}")

	# Finalize status for all successfully processed doctypes
	if job_id:
		finalize_sql_backup_status(job_id, doctypes, doctype_record_counts)

	# Encode to base64 for download
	zip_buffer.seek(0)
	file_data = base64.b64encode(zip_buffer.getvalue()).decode()

	return {
		"success": True,
		"file_data": file_data,
		"filename": f"partial_backup_csv_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip",
		"total_doctypes": len(doctypes),
		"total_records": total_records,
		"total_files": total_files
	}


def create_sql_backup(doctypes, include_files=False, job_id=None, field_transformations=None, table_transformations=None):
	"""Create SQL backup of selected DocTypes

	Args:
		doctypes: List of DocType names to backup
		include_files: Boolean to include file attachments
		job_id: Optional job ID for progress tracking
		field_transformations: Optional list of field transformation rules
		table_transformations: Optional list of table name transformation rules
	"""
	sql_statements = []
	total_records = 0
	total_files = 0
	file_paths = []
	doctype_record_counts = {}  # Track record count per doctype for status finalization

	# Add header comment
	sql_statements.append(f"""-- Partial Backup SQL Export
-- Created by: {frappe.session.user}
-- Creation date: {frappe.utils.now()}
-- Frappe version: {frappe.__version__}
-- Total DocTypes: {len(doctypes)}
-- Include Files: {include_files}
--
-- This file contains SQL statements to backup selected DocTypes
-- WARNING: This will DROP and recreate tables!
--

SET FOREIGN_KEY_CHECKS=0;

""")

	for idx, doctype_name in enumerate(doctypes):
		try:
			# Get table size information
			table_info = get_table_size(doctype_name)

			# Update progress and status if job_id is provided
			if job_id:
				update_job_progress(job_id, f"Processing {doctype_name} ({idx+1}/{len(doctypes)}) - Size: {table_info['size_mb']}MB, Rows: {table_info['row_count']}")
				update_doctype_status(job_id, doctype_name, 'processing', table_info['size_mb'], 0)

			# Get DocType definition
			doctype_doc = frappe.get_doc("DocType", doctype_name)
			table_name = f"tab{doctype_name}"

			# Apply table name transformation if specified
			transformed_table_name = apply_table_transformation(table_name, table_transformations)

			sql_statements.append(f"\n-- ==========================================")
			sql_statements.append(f"-- DocType: {doctype_name}")
			sql_statements.append(f"-- Module: {doctype_doc.module}")
			if transformed_table_name != table_name:
				sql_statements.append(f"-- Table Name Transformation: {table_name} → {transformed_table_name}")
			sql_statements.append(f"-- ==========================================\n")

			# Get table structure
			create_table_sql = frappe.db.sql(f"SHOW CREATE TABLE `{table_name}`", as_dict=True)
			if create_table_sql:
				sql_statements.append(f"DROP TABLE IF EXISTS `{transformed_table_name}`;")
				# Replace table name in CREATE TABLE statement
				create_stmt = create_table_sql[0]['Create Table']
				create_stmt = create_stmt.replace(f"`{table_name}`", f"`{transformed_table_name}`", 1)
				sql_statements.append(create_stmt + ";")
				sql_statements.append("")

			# Get all records
			records_count = 0
			records = []
			if doctype_doc.issingle:
				# Single DocType
				if frappe.db.exists(doctype_name, doctype_name):
					records = frappe.db.get_all(
						doctype_name,
						fields=['*'],
						as_list=False
					)
					if records:
						# Apply field transformations if specified
						if field_transformations:
							records = apply_field_transformations(records, doctype_name, field_transformations)

						records_count = len(records)
						insert_sql = generate_insert_statements(transformed_table_name, records)
						sql_statements.extend(insert_sql)
			else:
				# Regular DocType - get all documents in batches for large datasets
				batch_size = 5000  # Process 5000 records at a time for SQL
				offset = 0
				records_count = 0
				all_records = []  # Collect for file attachment processing

				while True:
					# Fetch batch of records
					batch_records = frappe.db.get_all(
						doctype_name,
						fields=['*'],
						as_list=False,
						limit_start=offset,
						limit_page_length=batch_size
					)

					if not batch_records:
						break

					# Apply field transformations if specified
					if field_transformations:
						batch_records = apply_field_transformations(batch_records, doctype_name, field_transformations)

					records_count += len(batch_records)
					insert_sql = generate_insert_statements(transformed_table_name, batch_records)
					sql_statements.extend(insert_sql)

					# Collect records if files need to be included
					if include_files:
						all_records.extend(batch_records)

					# Update progress for large doctypes
					if job_id and records_count % (batch_size * 2) == 0:
						update_job_progress(job_id, f"Processing {doctype_name} ({idx+1}/{len(doctypes)}) - {records_count} records exported...")

					offset += batch_size

					# If we got fewer records than batch_size, we've reached the end
					if len(batch_records) < batch_size:
						break

				# Set records for file collection
				if include_files:
					records = all_records

			# Collect file attachments if requested
			if include_files and records_count > 0:
				doctype_files = get_doctype_files(doctype_name, records)
				file_paths.extend(doctype_files)
				total_files += len(doctype_files)

			total_records += records_count
			sql_statements.append(f"-- Records exported: {records_count}\n")

			# Track record count for this doctype
			doctype_record_counts[doctype_name] = records_count

			# Mark doctype as completed
			if job_id:
				update_doctype_status(job_id, doctype_name, 'completed', table_info['size_mb'], records_count)

		except Exception as e:
			error_msg = f"Error backing up {doctype_name}: {str(e)}"
			frappe.log_error(error_msg, "SQL Backup Error")
			sql_statements.append(f"-- ERROR: {error_msg}\n")

			# Mark doctype as failed
			if job_id:
				update_doctype_status(job_id, doctype_name, 'failed', 0, 0, error_msg)

	sql_statements.append(f"\nSET FOREIGN_KEY_CHECKS=1;")
	sql_statements.append(f"\n-- Total records exported: {total_records}")
	sql_statements.append(f"-- Total files: {total_files}")
	sql_statements.append(f"-- Backup completed: {frappe.utils.now()}\n")

	# Finalize status for all successfully processed doctypes
	if job_id:
		finalize_sql_backup_status(job_id, doctypes, doctype_record_counts)

	# Combine all SQL statements
	sql_content = "\n".join(sql_statements)

	# If files are included, create a ZIP with SQL + files
	if include_files and file_paths:
		if job_id:
			update_job_progress(job_id, f"Creating archive with {len(file_paths)} files...")

		zip_buffer = BytesIO()
		with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
			# Add SQL file
			zip_file.writestr('backup.sql', sql_content)

			# Add files
			files_added = 0
			files_failed = 0

			for file_info in file_paths:
				try:
					# Handle both absolute and relative paths
					file_url = file_info['file_path']

					# Get the actual file path on disk
					if file_url.startswith('/files/'):
						# Public file
						file_path = frappe.get_site_path('public', 'files', file_url.replace('/files/', ''))
					elif file_url.startswith('/private/files/'):
						# Private file
						file_path = frappe.get_site_path('private', 'files', file_url.replace('/private/files/', ''))
					else:
						# Try direct path
						file_path = frappe.get_site_path() + file_url

					if os.path.exists(file_path):
						arcname = f"files{file_url}"
						zip_file.write(file_path, arcname)
						files_added += 1
						logger.debug(f"Added file: {file_url}")
					else:
						logger.warning(f"File not found: {file_path}")
						files_failed += 1
				except Exception as e:
					logger.error(f"Error adding file {file_info.get('file_path')}: {str(e)}")
					files_failed += 1

			logger.info(f"SQL backup - Files added: {files_added}, failed: {files_failed}")

		zip_buffer.seek(0)
		file_data = base64.b64encode(zip_buffer.getvalue()).decode()
		filename = f"partial_backup_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip"
	else:
		# Just SQL file
		file_data = base64.b64encode(sql_content.encode('utf-8')).decode()
		filename = f"partial_backup_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.sql"

	return {
		"success": True,
		"file_data": file_data,
		"filename": filename,
		"total_doctypes": len(doctypes),
		"total_records": total_records,
		"total_files": total_files
	}


def generate_insert_statements(table_name, records):
	"""Generate INSERT statements from records"""
	if not records:
		return []

	statements = []

	# Get column names from first record
	columns = list(records[0].keys())
	column_list = ", ".join([f"`{col}`" for col in columns])

	# Generate INSERT statements in batches
	batch_size = 100
	for i in range(0, len(records), batch_size):
		batch = records[i:i + batch_size]
		values_list = []

		for record in batch:
			values = []
			for col in columns:
				value = record.get(col)
				if value is None:
					values.append("NULL")
				elif isinstance(value, (int, float)):
					values.append(str(value))
				else:
					# Escape string values
					escaped_value = str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")
					values.append(f"'{escaped_value}'")
			values_list.append(f"({', '.join(values)})")

		insert_stmt = f"INSERT INTO `{table_name}` ({column_list}) VALUES\n  "
		insert_stmt += ",\n  ".join(values_list) + ";"
		statements.append(insert_stmt)
		statements.append("")

	return statements


def get_doctype_files(doctype_name, records):
	"""Get all file attachments for a DocType's records

	Args:
		doctype_name: Name of the DocType
		records: List of record dictionaries

	Returns:
		list: List of file info dictionaries with file_path
	"""
	file_list = []
	seen_files = set()  # Track unique files

	if not records:
		logger.info(f"No records for {doctype_name}")
		return file_list

	# Get all record names
	record_names = [r.get('name') for r in records if r.get('name')]

	if not record_names:
		logger.warning(f"No record names found for {doctype_name}")
		return file_list

	logger.info(f"Getting files for {doctype_name}, {len(record_names)} records")

	try:
		# Method 1: Query File doctype for attachments linked to these records
		files = frappe.get_all(
			'File',
			filters={
				'attached_to_doctype': doctype_name,
				'attached_to_name': ['in', record_names]
			},
			fields=['name', 'file_url', 'file_name', 'attached_to_name']
		)

		logger.info(f"Found {len(files)} files in File doctype for {doctype_name}")

		for file_doc in files:
			if file_doc.file_url:
				# Convert URL to file path
				file_url = file_doc.file_url
				if file_url.startswith('/files/') or file_url.startswith('/private/files/'):
					if file_url not in seen_files:
						file_list.append({
							'file_path': file_url,
							'file_name': file_doc.file_name,
							'attached_to': file_doc.attached_to_name
						})
						seen_files.add(file_url)

		# Method 2: Check for Attach and Attach Image fields in DocType
		doctype_meta = frappe.get_meta(doctype_name)
		attach_fields = []

		for field in doctype_meta.fields:
			if field.fieldtype in ['Attach', 'Attach Image']:
				attach_fields.append(field.fieldname)

		if attach_fields:
			logger.info(f"{doctype_name} has attach fields: {attach_fields}")

			# Check each record for file URLs in attach fields
			for record in records:
				for field_name in attach_fields:
					file_url = record.get(field_name)
					if file_url and isinstance(file_url, str):
						if file_url.startswith('/files/') or file_url.startswith('/private/files/'):
							if file_url not in seen_files:
								file_list.append({
									'file_path': file_url,
									'file_name': os.path.basename(file_url),
									'attached_to': record.get('name'),
									'field': field_name
								})
								seen_files.add(file_url)

	except Exception as e:
		logger.error(f"Error getting files for {doctype_name}: {str(e)}")
		frappe.log_error(f"File collection error: {str(e)}", f"Get Files - {doctype_name}")

	logger.info(f"Total files collected for {doctype_name}: {len(file_list)}")
	return file_list


def update_job_progress(job_id, progress_message):
	"""Update the progress message for a job

	Args:
		job_id: Unique job identifier
		progress_message: Progress message to display
	"""
	try:
		job_data = json.loads(frappe.cache().get_value(f'backup_job_{job_id}') or '{}')
		if job_data:
			job_data['progress'] = progress_message
			frappe.cache().set_value(f'backup_job_{job_id}', json.dumps(job_data), expires_in_sec=50400)
	except Exception as e:
		frappe.log_error(f"Error updating job progress: {str(e)}")


def get_table_size(doctype_name):
	"""Get the size of a table in MB

	Args:
		doctype_name: Name of the DocType

	Returns:
		dict: Dictionary with table size information
	"""
	try:
		table_name = f"tab{doctype_name}"
		result = frappe.db.sql(f"""
			SELECT
				table_name,
				ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb,
				table_rows
			FROM information_schema.TABLES
			WHERE table_schema = %s
			AND table_name = %s
		""", (frappe.conf.db_name, table_name), as_dict=True)

		if result:
			return {
				'table_name': result[0]['table_name'],
				'size_mb': result[0]['size_mb'] or 0,
				'row_count': result[0]['table_rows'] or 0
			}
		return {'table_name': table_name, 'size_mb': 0, 'row_count': 0}
	except Exception as e:
		frappe.log_error(f"Error getting table size for {doctype_name}: {str(e)}")
		return {'table_name': f"tab{doctype_name}", 'size_mb': 0, 'row_count': 0}


def initialize_all_doctype_status(job_id, doctypes):
	"""Initialize status tracking for all doctypes at the start of backup

	Args:
		job_id: Unique job identifier
		doctypes: List of all DocType names to backup
	"""
	try:
		status_key = f'backup_job_{job_id}_status'
		status_data = {'doctypes': []}

		# Initialize all doctypes with 'pending' status
		for doctype_name in doctypes:
			# Get table size information upfront
			table_info = get_table_size(doctype_name)

			status_data['doctypes'].append({
				'doctype': doctype_name,
				'table_name': f'tab{doctype_name}',
				'status': 'pending',
				'size_mb': table_info['size_mb'],
				'records': 0,
				'started_at': frappe.utils.now(),
				'updated_at': frappe.utils.now(),
				'error': None
			})

		# Save to cache with extended expiration
		frappe.cache().set_value(status_key, json.dumps(status_data), expires_in_sec=50400)
	except Exception as e:
		frappe.log_error(f"Error initializing doctype status: {str(e)}")


def update_doctype_status(job_id, doctype_name, status, size_mb=0, records=0, error_msg=None):
	"""Update the status of a specific doctype in the backup job

	Args:
		job_id: Unique job identifier
		doctype_name: Name of the DocType
		status: Status (processing, completed, failed)
		size_mb: Size of the table in MB
		records: Number of records
		error_msg: Error message if failed
	"""
	try:
		# Get or create detailed status tracking
		status_key = f'backup_job_{job_id}_status'
		status_data = frappe.cache().get_value(status_key)

		if status_data:
			status_data = json.loads(status_data)
		else:
			status_data = {'doctypes': []}

		# Find existing entry or create new one
		existing_entry = None
		for entry in status_data['doctypes']:
			if entry['doctype'] == doctype_name:
				existing_entry = entry
				break

		if existing_entry:
			existing_entry['status'] = status
			if size_mb > 0:
				existing_entry['size_mb'] = size_mb
			existing_entry['records'] = records
			existing_entry['updated_at'] = frappe.utils.now()
			if error_msg:
				existing_entry['error'] = error_msg
		else:
			status_data['doctypes'].append({
				'doctype': doctype_name,
				'table_name': f'tab{doctype_name}',
				'status': status,
				'size_mb': size_mb,
				'records': records,
				'started_at': frappe.utils.now(),
				'updated_at': frappe.utils.now(),
				'error': error_msg
			})

		# Save back to cache with extended expiration
		frappe.cache().set_value(status_key, json.dumps(status_data), expires_in_sec=50400)
	except Exception as e:
		frappe.log_error(f"Error updating doctype status: {str(e)}")


def finalize_backup_status(job_id, selected_doctypes, backed_up_doctypes):
	"""Finalize status for all doctypes that were successfully backed up (JSON format)

	This function ensures all doctypes that made it into the backup are marked as completed,
	even if their individual status updates didn't persist properly during processing.

	Args:
		job_id: Unique job identifier
		selected_doctypes: List of doctype names that were selected for backup
		backed_up_doctypes: List of doctype entries from the backup data
	"""
	try:
		status_key = f'backup_job_{job_id}_status'
		status_data = frappe.cache().get_value(status_key)

		if status_data:
			status_data = json.loads(status_data)
		else:
			status_data = {'doctypes': []}

		# Create a map of backed up doctypes with their record counts
		backed_up_map = {}
		for dt_entry in backed_up_doctypes:
			doctype_name = dt_entry.get('doctype')
			record_count = dt_entry.get('record_count', 0)
			backed_up_map[doctype_name] = record_count

		# Update status for all doctypes that were successfully backed up
		for entry in status_data['doctypes']:
			doctype_name = entry['doctype']
			# If this doctype is in the backup and not already marked as completed/failed
			if doctype_name in backed_up_map and entry['status'] not in ['completed', 'failed']:
				entry['status'] = 'completed'
				entry['records'] = backed_up_map[doctype_name]
				entry['updated_at'] = frappe.utils.now()

		# Save updated status
		frappe.cache().set_value(status_key, json.dumps(status_data), expires_in_sec=50400)

		logger.info(f"Finalized backup status for job {job_id}: {len(backed_up_map)} doctypes")

	except Exception as e:
		frappe.log_error(f"Error finalizing backup status: {str(e)}")


def finalize_sql_backup_status(job_id, doctypes, record_counts):
	"""Finalize status for SQL/CSV backups - mark all non-failed doctypes as completed with record counts

	Args:
		job_id: Unique job identifier
		doctypes: List of all doctype names that were in the backup
		record_counts: Dictionary mapping doctype names to their record counts
	"""
	try:
		status_key = f'backup_job_{job_id}_status'
		status_data = frappe.cache().get_value(status_key)

		if status_data:
			status_data = json.loads(status_data)
		else:
			status_data = {'doctypes': []}

		# Mark all doctypes that aren't already failed as completed with proper record counts
		for entry in status_data['doctypes']:
			doctype_name = entry['doctype']
			if entry['status'] not in ['completed', 'failed']:
				entry['status'] = 'completed'
				entry['updated_at'] = frappe.utils.now()
				# Update with actual record count if available
				if doctype_name in record_counts:
					entry['records'] = record_counts[doctype_name]

		# Save updated status
		frappe.cache().set_value(status_key, json.dumps(status_data), expires_in_sec=50400)

		logger.info(f"Finalized SQL/CSV backup status for job {job_id}: {len(doctypes)} doctypes, total {sum(record_counts.values())} records")

	except Exception as e:
		frappe.log_error(f"Error finalizing SQL backup status: {str(e)}")


@frappe.whitelist()
def get_detailed_status(job_id):
	"""Get detailed status of backup job including per-doctype information

	Args:
		job_id: Unique job identifier

	Returns:
		dict: Detailed status information
	"""
	try:
		# Get main job data
		job_data = json.loads(frappe.cache().get_value(f'backup_job_{job_id}') or '{}')

		# Get detailed doctype status
		status_key = f'backup_job_{job_id}_status'
		status_data = frappe.cache().get_value(status_key)

		if status_data:
			status_data = json.loads(status_data)
		else:
			status_data = {'doctypes': []}

		# Calculate summary statistics
		total_doctypes = len(status_data.get('doctypes', []))
		completed = sum(1 for d in status_data.get('doctypes', []) if d['status'] == 'completed')
		failed = sum(1 for d in status_data.get('doctypes', []) if d['status'] == 'failed')
		processing = sum(1 for d in status_data.get('doctypes', []) if d['status'] == 'processing')
		pending = sum(1 for d in status_data.get('doctypes', []) if d['status'] == 'pending')
		total_size_mb = sum(d.get('size_mb', 0) for d in status_data.get('doctypes', []))
		total_records = sum(d.get('records', 0) for d in status_data.get('doctypes', []))

		return {
			'success': True,
			'job_data': job_data,
			'detailed_status': status_data.get('doctypes', []),
			'summary': {
				'total_doctypes': total_doctypes,
				'completed': completed,
				'failed': failed,
				'processing': processing,
				'pending': pending,
				'total_size_mb': round(total_size_mb, 2),
				'total_records': total_records
			}
		}
	except Exception as e:
		frappe.log_error(f"Error getting detailed status: {str(e)}")
		return {'success': False, 'error': str(e)}
