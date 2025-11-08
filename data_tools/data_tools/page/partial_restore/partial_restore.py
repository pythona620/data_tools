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

	except Exception as e:
		frappe.log_error(f"Error parsing backup file: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def restore_backup(file_data, filename, selected_doctypes=None):
	"""Restore data from backup file"""
	try:
		if selected_doctypes and isinstance(selected_doctypes, str):
			selected_doctypes = json.loads(selected_doctypes)

		# Decode base64
		file_bytes = base64.b64decode(file_data.split(',')[1] if ',' in file_data else file_data)

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
		frappe.log_error(f"Error in restore_backup: {str(e)}")
		return {
			"success": False,
			"error": str(e)
		}
