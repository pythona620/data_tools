# -*- coding: utf-8 -*-
# Copyright (c) 2025, Admin and contributors
# For license information, please see license.txt

import frappe
import json
import os
from frappe import _
from frappe.model.document import get_controller
import zipfile
from io import BytesIO
import base64
import uuid
from frappe.utils.background_jobs import enqueue
import shutil
from pathlib import Path
import logging

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
			AND name NOT LIKE 'DocType%'
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
			AND name NOT LIKE 'DocType%%'
			AND module IN %(modules)s
		ORDER BY module, name
	""", {"modules": all_modules}, as_dict=True)

	logger.info(f"Found {len(doctypes)} DocTypes")

	return doctypes


@frappe.whitelist()
def create_partial_backup(doctypes, export_format='json', include_files=False):
	"""Create a partial backup of selected DocTypes

	Args:
		doctypes: List of DocType names to backup
		export_format: 'json' or 'sql' (default: 'json')
		include_files: Boolean to include file attachments (default: False)
	"""
	if isinstance(doctypes, str):
		doctypes = json.loads(doctypes)

	if not doctypes or not isinstance(doctypes, list) or len(doctypes) == 0:
		frappe.throw(_("Please select at least one DocType"))

	# Convert include_files to boolean
	if isinstance(include_files, str):
		include_files = include_files.lower() in ['true', '1', 'yes']

	if export_format == 'sql':
		return create_sql_backup(doctypes, include_files)
	else:
		return create_json_backup(doctypes, include_files)


@frappe.whitelist()
def start_backup_job(doctypes, export_format='json', include_files=False):
	"""Start a background job for backup creation

	Args:
		doctypes: List of DocType names to backup
		export_format: 'json' or 'sql' (default: 'json')
		include_files: Boolean to include file attachments (default: False)

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

	# Generate unique job ID
	job_id = str(uuid.uuid4())

	# Store job metadata in cache
	job_data = {
		'status': 'queued',
		'progress': 'Starting backup...',
		'doctypes': doctypes,
		'export_format': export_format,
		'include_files': include_files,
		'created_by': frappe.session.user,
		'created_at': frappe.utils.now()
	}
	frappe.cache().set_value(f'backup_job_{job_id}', json.dumps(job_data), expires_in_sec=7200)

	# Enqueue the backup job
	enqueue(
		method=execute_backup_job,
		queue='long',
		timeout=3600,
		backup_job_id=job_id,
		doctypes=doctypes,
		export_format=export_format,
		include_files=include_files
	)

	return {
		'job_id': job_id,
		'status': 'queued'
	}


def execute_backup_job(backup_job_id, doctypes, export_format='json', include_files=False):
	"""Execute the backup job in background

	Args:
		backup_job_id: Unique job identifier
		doctypes: List of DocType names to backup
		export_format: 'json' or 'sql'
		include_files: Boolean to include file attachments
	"""
	try:
		# Get job data to retrieve user
		job_data = json.loads(frappe.cache().get_value(f'backup_job_{backup_job_id}') or '{}')

		# Set user context for the background job
		if job_data.get('created_by'):
			frappe.set_user(job_data.get('created_by'))

		# Update job status to running
		job_data['status'] = 'running'
		job_data['progress'] = 'Backup in progress...'
		frappe.cache().set_value(f'backup_job_{backup_job_id}', json.dumps(job_data), expires_in_sec=7200)

		# Create backup
		if export_format == 'sql':
			result = create_sql_backup(doctypes, include_files, backup_job_id)
		else:
			result = create_json_backup(doctypes, include_files, backup_job_id)

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

		# Save to cache
		cache_key = f'backup_job_{backup_job_id}'
		cache_value = json.dumps(job_data)
		frappe.cache().set_value(cache_key, cache_value, expires_in_sec=7200)

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
		frappe.cache().set_value(f'backup_job_{backup_job_id}', json.dumps(job_data), expires_in_sec=7200)
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
		dict: File data for download
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

		# Read file and encode
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
			'file_data': file_data,
			'filename': job_info.get('filename'),
			'total_doctypes': job_info.get('total_doctypes'),
			'total_records': job_info.get('total_records'),
			'total_files': job_info.get('total_files', 0)
		}

	except Exception as e:
		logger.error(f"Error downloading backup {job_id}: {str(e)}")
		frappe.log_error(f"Download failed: {str(e)}", f"Backup Download Error")
		raise


def create_json_backup(doctypes, include_files=False, job_id=None):
	"""Create JSON backup of selected DocTypes

	Args:
		doctypes: List of DocType names to backup
		include_files: Boolean to include file attachments
		job_id: Optional job ID for progress tracking
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
			# Update progress if job_id is provided
			if job_id:
				update_job_progress(job_id, f"Processing {doctype_name} ({idx+1}/{len(doctypes)})...")

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
				# Regular DocType - get all documents
				doc_names = frappe.get_all(doctype_name, pluck='name')
				for name in doc_names:
					try:
						doc = frappe.get_doc(doctype_name, name)
						records.append(doc.as_dict())
					except Exception as e:
						frappe.log_error(f"Error fetching {doctype_name} - {name}: {str(e)}")

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

		except Exception as e:
			frappe.log_error(f"Error backing up {doctype_name}: {str(e)}")
			# Continue with other doctypes

	backup_data["backup_info"]["total_records"] = total_records
	backup_data["backup_info"]["total_files"] = total_files

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


def create_sql_backup(doctypes, include_files=False, job_id=None):
	"""Create SQL backup of selected DocTypes

	Args:
		doctypes: List of DocType names to backup
		include_files: Boolean to include file attachments
		job_id: Optional job ID for progress tracking
	"""
	sql_statements = []
	total_records = 0
	total_files = 0
	file_paths = []

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
			# Update progress if job_id is provided
			if job_id:
				update_job_progress(job_id, f"Processing {doctype_name} ({idx+1}/{len(doctypes)})...")

			# Get DocType definition
			doctype_doc = frappe.get_doc("DocType", doctype_name)
			table_name = f"tab{doctype_name}"

			sql_statements.append(f"\n-- ==========================================")
			sql_statements.append(f"-- DocType: {doctype_name}")
			sql_statements.append(f"-- Module: {doctype_doc.module}")
			sql_statements.append(f"-- ==========================================\n")

			# Get table structure
			create_table_sql = frappe.db.sql(f"SHOW CREATE TABLE `{table_name}`", as_dict=True)
			if create_table_sql:
				sql_statements.append(f"DROP TABLE IF EXISTS `{table_name}`;")
				sql_statements.append(create_table_sql[0]['Create Table'] + ";")
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
						records_count = len(records)
						insert_sql = generate_insert_statements(table_name, records)
						sql_statements.extend(insert_sql)
			else:
				# Regular DocType - get all documents
				records = frappe.db.get_all(
					doctype_name,
					fields=['*'],
					as_list=False
				)
				if records:
					records_count = len(records)
					insert_sql = generate_insert_statements(table_name, records)
					sql_statements.extend(insert_sql)

			# Collect file attachments if requested
			if include_files and records:
				doctype_files = get_doctype_files(doctype_name, records)
				file_paths.extend(doctype_files)
				total_files += len(doctype_files)

			total_records += records_count
			sql_statements.append(f"-- Records exported: {records_count}\n")

		except Exception as e:
			error_msg = f"Error backing up {doctype_name}: {str(e)}"
			frappe.log_error(error_msg)
			sql_statements.append(f"-- ERROR: {error_msg}\n")

	sql_statements.append(f"\nSET FOREIGN_KEY_CHECKS=1;")
	sql_statements.append(f"\n-- Total records exported: {total_records}")
	sql_statements.append(f"-- Total files: {total_files}")
	sql_statements.append(f"-- Backup completed: {frappe.utils.now()}\n")

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
			frappe.cache().set_value(f'backup_job_{job_id}', json.dumps(job_data), expires_in_sec=7200)
	except Exception as e:
		frappe.log_error(f"Error updating job progress: {str(e)}")
