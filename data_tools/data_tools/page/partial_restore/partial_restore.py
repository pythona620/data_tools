# -*- coding: utf-8 -*-
# Copyright (c) 2025, Admin and contributors
# For license information, please see license.txt

import frappe
import json
import zipfile
from frappe import _
from io import BytesIO
import base64
import uuid
from frappe.utils.background_jobs import enqueue
from data_tools.data_tools.doctype_dependencies import (
	topological_sort,
	validate_restore_order
)


@frappe.whitelist()
def parse_backup_file(file_data, filename):
	"""Parse uploaded backup file and return metadata"""
	try:
		# Decode base64
		file_bytes = base64.b64decode(file_data.split(',')[1] if ',' in file_data else file_data)

		# Check if it's a SQL file or ZIP file
		if filename.endswith('.sql'):
			return parse_sql_file(file_bytes, filename)
		else:
			return parse_json_backup(file_bytes, filename)

	except Exception as e:
		frappe.log_error(f"Error parsing backup file: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}


def parse_json_backup(file_bytes, filename):
	"""Parse JSON backup file (ZIP format)"""
	# Extract from ZIP
	zip_buffer = BytesIO(file_bytes)
	with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
		# Read metadata
		metadata_content = zip_file.read('metadata.json').decode('utf-8')
		metadata = json.loads(metadata_content)

		# Read full backup data
		backup_content = zip_file.read('backup_data.json').decode('utf-8')
		backup_data = json.loads(backup_content)

	return {
		"success": True,
		"file_type": "json",
		"metadata": metadata,
		"backup_info": backup_data.get("backup_info", {}),
		"doctypes": [
			{
				"doctype": dt["doctype"],
				"record_count": dt["record_count"]
			}
			for dt in backup_data.get("doctypes", [])
		]
	}


def parse_sql_file(file_bytes, filename):
	"""Parse SQL backup file and extract metadata"""
	sql_content = file_bytes.decode('utf-8')

	# Extract metadata from SQL comments
	doctypes = []
	total_records = 0
	created_by = "Unknown"
	creation_date = "Unknown"
	frappe_version = "Unknown"

	lines = sql_content.split('\n')
	current_doctype = None
	for line in lines:
		line = line.strip()
		if line.startswith('-- Created by:'):
			created_by = line.split(':', 1)[1].strip()
		elif line.startswith('-- Creation date:'):
			creation_date = line.split(':', 1)[1].strip()
		elif line.startswith('-- Frappe version:'):
			frappe_version = line.split(':', 1)[1].strip()
		elif line.startswith('-- DocType:'):
			current_doctype = line.split(':', 1)[1].strip()
		elif line.startswith('-- Records exported:') and current_doctype:
			record_count = int(line.split(':')[1].strip())
			doctypes.append({
				"doctype": current_doctype,
				"record_count": record_count
			})
			total_records += record_count
			current_doctype = None

	return {
		"success": True,
		"file_type": "sql",
		"metadata": {
			"doctypes": [dt["doctype"] for dt in doctypes],
			"total_records": total_records,
			"created_by": created_by,
			"creation_date": creation_date
		},
		"backup_info": {
			"created_by": created_by,
			"creation_date": creation_date,
			"frappe_version": frappe_version,
			"total_doctypes": len(doctypes),
			"total_records": total_records
		},
		"doctypes": doctypes
	}


@frappe.whitelist()
def start_restore_job(file_data, filename, selected_doctypes=None):
	"""Start a background job for restore operation

	Args:
		file_data: Base64 encoded file data
		filename: Name of the backup file
		selected_doctypes: List of DocTypes to restore (optional)

	Returns:
		dict: Job information including job_id
	"""
	job_id = str(uuid.uuid4())

	# Store file data in cache for background job
	cache_key = f"restore_job_{job_id}"
	frappe.cache().set_value(
		cache_key,
		{
			'file_data': file_data,
			'filename': filename,
			'selected_doctypes': selected_doctypes,
			'status': 'queued',
			'progress': 'Restore job queued...'
		},
		expires_in_sec=7200  # 2 hours
	)

	# Enqueue background job
	enqueue(
		execute_restore_job,
		queue='long',
		timeout=3600,  # 1 hour timeout
		job_id=job_id,
		restore_job_id=job_id,
		file_data=file_data,
		filename=filename,
		selected_doctypes=selected_doctypes
	)

	return {
		'success': True,
		'job_id': job_id,
		'message': 'Restore job started'
	}


def execute_restore_job(restore_job_id, file_data, filename, selected_doctypes=None):
	"""Execute restore operation in background

	Args:
		restore_job_id: Unique job identifier
		file_data: Base64 encoded file data
		filename: Name of the backup file
		selected_doctypes: List of DocTypes to restore (optional)
	"""
	try:
		update_job_progress(restore_job_id, 'Processing restore...')

		# Perform restore
		result = restore_backup_sync(file_data, filename, selected_doctypes, restore_job_id)

		# Store result in cache
		cache_key = f"restore_job_{restore_job_id}"
		frappe.cache().set_value(
			cache_key,
			{
				'status': 'completed' if result.get('success') else 'failed',
				'progress': 'Restore completed',
				'result': result
			},
			expires_in_sec=7200
		)

	except Exception as e:
		frappe.log_error(f"Error in restore job {restore_job_id}: {str(e)}")
		cache_key = f"restore_job_{restore_job_id}"
		frappe.cache().set_value(
			cache_key,
			{
				'status': 'failed',
				'progress': 'Restore failed',
				'error': str(e)
			},
			expires_in_sec=7200
		)


def update_job_progress(job_id, message):
	"""Update restore job progress in cache

	Args:
		job_id: Job identifier
		message: Progress message
	"""
	cache_key = f"restore_job_{job_id}"
	job_data = frappe.cache().get_value(cache_key) or {}
	job_data['progress'] = message
	job_data['status'] = 'running'
	frappe.cache().set_value(cache_key, job_data, expires_in_sec=7200)


@frappe.whitelist()
def get_restore_job_status(job_id):
	"""Get status of restore job

	Args:
		job_id: Job identifier

	Returns:
		dict: Job status and progress
	"""
	cache_key = f"restore_job_{job_id}"
	job_data = frappe.cache().get_value(cache_key)

	if not job_data:
		return {
			'status': 'not_found',
			'message': 'Job not found'
		}

	return job_data


@frappe.whitelist()
def restore_backup(file_data, filename, selected_doctypes=None):
	"""Restore data from backup file (wrapper that calls background job)"""
	if selected_doctypes and isinstance(selected_doctypes, str):
		selected_doctypes = json.loads(selected_doctypes)

	# Start background job for restore
	return start_restore_job(file_data, filename, selected_doctypes)


def restore_backup_sync(file_data, filename, selected_doctypes=None, job_id=None):
	"""Restore data from backup file (synchronous - used by background job)

	Args:
		file_data: Base64 encoded file data
		filename: Backup filename
		selected_doctypes: List of DocTypes to restore
		job_id: Job ID for progress tracking
	"""
	try:
		if selected_doctypes and isinstance(selected_doctypes, str):
			selected_doctypes = json.loads(selected_doctypes)

		# Decode base64
		file_bytes = base64.b64decode(file_data.split(',')[1] if ',' in file_data else file_data)

		# Check if it's a SQL file or ZIP file
		if filename.endswith('.sql'):
			return restore_sql_backup(file_bytes, filename, selected_doctypes, job_id)
		else:
			return restore_json_backup(file_bytes, filename, selected_doctypes, job_id)

	except Exception as e:
		frappe.log_error(f"Error in restore_backup_sync: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}


def restore_json_backup(file_bytes, filename, selected_doctypes=None, job_id=None):
	"""Restore JSON backup file with dependency-aware ordering

	Args:
		file_bytes: Backup file bytes
		filename: Backup filename
		selected_doctypes: List of DocTypes to restore
		job_id: Job ID for progress tracking
	"""
	try:
		if job_id:
			update_job_progress(job_id, 'Extracting backup data...')

		# Extract from ZIP
		zip_buffer = BytesIO(file_bytes)
		with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
			backup_content = zip_file.read('backup_data.json').decode('utf-8')
			backup_data = json.loads(backup_content)

		restore_log = []
		success_count = 0
		error_count = 0

		# Get list of doctypes in backup
		doctypes_in_backup = [dt["doctype"] for dt in backup_data.get("doctypes", [])]

		# Filter by selected doctypes if specified
		if selected_doctypes:
			doctypes_to_restore = [dt for dt in doctypes_in_backup if dt in selected_doctypes]
		else:
			doctypes_to_restore = doctypes_in_backup

		# Sort doctypes by dependencies (topological sort)
		if job_id:
			update_job_progress(job_id, 'Analyzing dependencies and determining restore order...')

		sorted_doctypes = topological_sort(doctypes_to_restore)

		# Log the restore order
		restore_log.append({
			"doctype": "System",
			"status": "info",
			"message": f"Restore order determined: {' → '.join(sorted_doctypes)}"
		})

		# Create a lookup dictionary for quick access
		doctype_data_map = {dt["doctype"]: dt for dt in backup_data.get("doctypes", [])}

		# Restore in sorted order
		for idx, doctype_name in enumerate(sorted_doctypes, 1):
			if job_id:
				update_job_progress(job_id, f'Restoring {doctype_name} ({idx}/{len(sorted_doctypes)})...')

			dt_data = doctype_data_map.get(doctype_name)
			if not dt_data:
				continue

			try:
				# Check if DocType exists
				if not frappe.db.exists("DocType", doctype_name):
					# Create DocType from definition
					restore_log.append({
						"doctype": doctype_name,
						"status": "warning",
						"message": f"DocType doesn't exist. Creating from backup..."
					})

					try:
						doctype_def = dt_data["definition"]
						# Create the DocType
						dt_doc = frappe.get_doc(doctype_def)
						dt_doc.insert()
						frappe.db.commit()

						restore_log.append({
							"doctype": doctype_name,
							"status": "success",
							"message": f"DocType created successfully"
						})
					except Exception as e:
						restore_log.append({
							"doctype": doctype_name,
							"status": "error",
							"message": f"Failed to create DocType: {str(e)}"
						})
						error_count += 1
						continue

				# Restore records
				records = dt_data.get("records", [])
				imported_count = 0
				skipped_count = 0
				record_errors = 0

				for record in records:
					try:
						doc_name = record.get("name")

						# Check if document already exists
						if frappe.db.exists(doctype_name, doc_name):
							# Skip or update based on strategy
							skipped_count += 1
							continue

						# Remove system fields that shouldn't be imported
						record.pop("owner", None)
						record.pop("modified_by", None)
						record.pop("creation", None)
						record.pop("modified", None)

						# Insert document
						doc = frappe.get_doc(record)
						doc.insert()
						imported_count += 1

					except Exception as e:
						record_errors += 1
						frappe.log_error(
							f"Error importing {doctype_name} - {record.get('name')}: {str(e)}"
						)

				# Commit after each DocType
				frappe.db.commit()

				if record_errors == 0:
					restore_log.append({
						"doctype": doctype_name,
						"status": "success",
						"message": f"Imported {imported_count} records, Skipped {skipped_count} (already exist)",
						"imported": imported_count,
						"skipped": skipped_count
					})
					success_count += 1
				else:
					restore_log.append({
						"doctype": doctype_name,
						"status": "partial",
						"message": f"Imported {imported_count} records, Skipped {skipped_count}, Errors {record_errors}",
						"imported": imported_count,
						"skipped": skipped_count,
						"errors": record_errors
					})
					error_count += 1

			except Exception as e:
				frappe.log_error(f"Error restoring {doctype_name}: {str(e)}")
				restore_log.append({
					"doctype": doctype_name,
					"status": "error",
					"message": str(e)
				})
				error_count += 1

		return {
			"success": True,
			"restore_log": restore_log,
			"summary": {
				"total_doctypes": len(restore_log),
				"success": success_count,
				"errors": error_count
			}
		}

	except Exception as e:
		frappe.log_error(f"Error in restore_json_backup: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}


def restore_sql_backup(file_bytes, filename, selected_doctypes=None, job_id=None):
	"""Restore SQL backup file

	Args:
		file_bytes: Backup file bytes
		filename: Backup filename
		selected_doctypes: List of DocTypes to restore (note: SQL restore is all-or-nothing)
		job_id: Job ID for progress tracking
	"""
	try:
		if job_id:
			update_job_progress(job_id, 'Parsing SQL backup...')

		sql_content = file_bytes.decode('utf-8')

		restore_log = []
		success_count = 0
		error_count = 0

		# If selective restore is enabled, we need to filter SQL statements
		if selected_doctypes:
			restore_log.append({
				"doctype": "System",
				"status": "warning",
				"message": "Note: SQL restore does not support selective restore. All data will be restored. Use JSON format for selective restore."
			})

		# Execute SQL statements
		# Split by semicolon but be careful with statements
		statements = []
		current_statement = []
		in_insert = False

		for line in sql_content.split('\n'):
			line = line.strip()

			# Skip comments and empty lines
			if not line or line.startswith('--'):
				continue

			current_statement.append(line)

			# Check if we're in an INSERT statement
			if line.upper().startswith('INSERT INTO'):
				in_insert = True

			# Statement ends with semicolon
			if line.endswith(';'):
				statements.append('\n'.join(current_statement))
				current_statement = []
				in_insert = False

		# Execute each statement
		try:
			for statement in statements:
				if statement.strip():
					# Extract DocType name from statement if possible
					doctype_name = None
					if 'DROP TABLE' in statement.upper() or 'CREATE TABLE' in statement.upper() or 'INSERT INTO' in statement.upper():
						# Try to extract table name
						import re
						match = re.search(r'`tab([^`]+)`', statement)
						if match:
							doctype_name = match.group(1)

					try:
						frappe.db.sql(statement)
					except Exception as e:
						error_msg = f"Error executing SQL statement: {str(e)}"
						if doctype_name:
							error_msg = f"Error with {doctype_name}: {str(e)}"
						frappe.log_error(error_msg)
						restore_log.append({
							"doctype": doctype_name or "Unknown",
							"status": "error",
							"message": error_msg
						})
						error_count += 1

			# Commit all changes
			frappe.db.commit()

			# Parse the SQL file to get DocType list for summary
			doctypes_info = parse_sql_file(file_bytes, filename)
			for dt in doctypes_info.get("doctypes", []):
				# Check if there were any errors for this DocType
				has_error = any(log["doctype"] == dt["doctype"] and log["status"] == "error"
							   for log in restore_log)

				if not has_error:
					restore_log.append({
						"doctype": dt["doctype"],
						"status": "success",
						"message": f"SQL statements executed successfully ({dt['record_count']} records)"
					})
					success_count += 1

			return {
				"success": True,
				"restore_log": restore_log,
				"summary": {
					"total_doctypes": len(restore_log),
					"success": success_count,
					"errors": error_count
				}
			}

		except Exception as e:
			frappe.db.rollback()
			frappe.log_error(f"Error executing SQL backup: {str(e)}")
			return {
				"success": False,
				"error": str(e)
			}

	except Exception as e:
		frappe.log_error(f"Error in restore_sql_backup: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}
