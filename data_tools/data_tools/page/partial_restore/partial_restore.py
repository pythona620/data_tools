# -*- coding: utf-8 -*-
# Copyright (c) 2025, Admin and contributors
# For license information, please see license.txt

import frappe
import json
import zipfile
from frappe import _
from io import BytesIO
import base64


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
def restore_backup(file_data, filename, selected_doctypes=None):
	"""Restore data from backup file"""
	try:
		if selected_doctypes and isinstance(selected_doctypes, str):
			selected_doctypes = json.loads(selected_doctypes)

		# Decode base64
		file_bytes = base64.b64decode(file_data.split(',')[1] if ',' in file_data else file_data)

		# Check if it's a SQL file or ZIP file
		if filename.endswith('.sql'):
			return restore_sql_backup(file_bytes, filename, selected_doctypes)
		else:
			return restore_json_backup(file_bytes, filename, selected_doctypes)

	except Exception as e:
		frappe.log_error(f"Error in restore_backup: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}


def restore_json_backup(file_bytes, filename, selected_doctypes=None):
	"""Restore JSON backup file"""
	try:
		# Extract from ZIP
		zip_buffer = BytesIO(file_bytes)
		with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
			backup_content = zip_file.read('backup_data.json').decode('utf-8')
			backup_data = json.loads(backup_content)

		restore_log = []
		success_count = 0
		error_count = 0

		for dt_data in backup_data.get("doctypes", []):
			doctype_name = dt_data["doctype"]

			# Skip if not selected (if selective restore)
			if selected_doctypes and doctype_name not in selected_doctypes:
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


def restore_sql_backup(file_bytes, filename, selected_doctypes=None):
	"""Restore SQL backup file"""
	try:
		sql_content = file_bytes.decode('utf-8')

		restore_log = []
		success_count = 0
		error_count = 0

		# If selective restore is enabled, we need to filter SQL statements
		if selected_doctypes:
			frappe.msgprint(_("Selective restore for SQL files will restore all data. " +
							"Use JSON format for selective restore."),
							indicator='orange')

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
