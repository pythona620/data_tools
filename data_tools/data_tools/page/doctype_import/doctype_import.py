# -*- coding: utf-8 -*-
# Copyright (c) 2025, Admin and contributors
# For license information, please see license.txt

import frappe
import json
import os
from frappe import _
import zipfile
from io import BytesIO
import base64
import logging

logger = logging.getLogger(__name__)


@frappe.whitelist()
def parse_export_file(file_data, filename):
	"""Parse and preview DocType export file

	Args:
		file_data: Base64 encoded file content
		filename: Name of the uploaded file

	Returns:
		dict: Preview information about the export
	"""
	try:
		# Decode base64 file data
		file_content = base64.b64decode(file_data)

		# Check if it's a ZIP file
		if filename.endswith('.zip'):
			# Extract ZIP file
			with zipfile.ZipFile(BytesIO(file_content), 'r') as zip_file:
				# Read the main data file
				if 'doctype_schemas.json' in zip_file.namelist():
					data_content = zip_file.read('doctype_schemas.json')
					export_data = json.loads(data_content.decode('utf-8'))
				else:
					frappe.throw(_("Invalid export file: doctype_schemas.json not found"))
		else:
			frappe.throw(_("Invalid file format. Please upload a ZIP file"))

		# Extract information for preview
		export_info = export_data.get('export_info', {})
		doctypes = export_data.get('doctypes', [])

		preview = {
			"export_info": {
				"created_by": export_info.get('created_by'),
				"creation_date": export_info.get('creation_date'),
				"frappe_version": export_info.get('frappe_version'),
				"total_doctypes": len(doctypes),
				"export_type": export_info.get('export_type', 'unknown')
			},
			"doctypes": []
		}

		# Add DocType information
		for dt in doctypes:
			doctype_name = dt.get('doctype')
			exists = frappe.db.exists('DocType', doctype_name)

			preview["doctypes"].append({
				"doctype": doctype_name,
				"module": dt.get('module'),
				"is_custom": dt.get('is_custom'),
				"is_single": dt.get('is_single'),
				"exists": exists,
				"status": "Will update" if exists else "Will create"
			})

		return {
			"success": True,
			"preview": preview,
			"file_data": file_data  # Store for later use
		}

	except Exception as e:
		frappe.log_error(f"Error parsing export file: {str(e)}")
		frappe.throw(_("Error parsing export file: {0}").format(str(e)))


@frappe.whitelist()
def import_doctypes(file_data, filename, selected_doctypes=None):
	"""Import DocType schemas from export file

	Args:
		file_data: Base64 encoded file content
		filename: Name of the uploaded file
		selected_doctypes: Optional list of specific DocTypes to import (JSON string or list)

	Returns:
		dict: Import results with success/error information
	"""
	try:
		# Parse selected_doctypes if provided
		if selected_doctypes:
			if isinstance(selected_doctypes, str):
				selected_doctypes = json.loads(selected_doctypes)
			if not isinstance(selected_doctypes, list):
				selected_doctypes = None

		# Decode base64 file data
		file_content = base64.b64decode(file_data)

		# Extract ZIP file
		with zipfile.ZipFile(BytesIO(file_content), 'r') as zip_file:
			if 'doctype_schemas.json' in zip_file.namelist():
				data_content = zip_file.read('doctype_schemas.json')
				export_data = json.loads(data_content.decode('utf-8'))
			else:
				frappe.throw(_("Invalid export file: doctype_schemas.json not found"))

		doctypes_to_import = export_data.get('doctypes', [])

		# Filter if specific DocTypes selected
		if selected_doctypes:
			doctypes_to_import = [dt for dt in doctypes_to_import if dt.get('doctype') in selected_doctypes]

		import_log = []
		success_count = 0
		error_count = 0

		for dt_data in doctypes_to_import:
			doctype_name = dt_data.get('doctype')
			definition = dt_data.get('definition')

			try:
				# Check if DocType exists
				exists = frappe.db.exists('DocType', doctype_name)

				if exists:
					# Update existing DocType
					existing_doc = frappe.get_doc('DocType', doctype_name)

					# Update fields from definition
					# Note: Be careful with system DocTypes
					if existing_doc.custom:
						# Safe to update custom DocTypes
						for key, value in definition.items():
							if key not in ['name', 'owner', 'creation', 'modified', 'modified_by']:
								setattr(existing_doc, key, value)

						existing_doc.save()
						frappe.db.commit()

						import_log.append({
							"doctype": doctype_name,
							"status": "success",
							"action": "updated",
							"message": f"DocType '{doctype_name}' updated successfully"
						})
						success_count += 1
					else:
						# Standard DocType - skip to avoid issues
						import_log.append({
							"doctype": doctype_name,
							"status": "skipped",
							"action": "skipped",
							"message": f"Skipped standard DocType '{doctype_name}' (cannot update standard DocTypes)"
						})
				else:
					# Create new DocType
					# Remove system fields
					for field in ['owner', 'creation', 'modified', 'modified_by']:
						definition.pop(field, None)

					# Create the DocType
					new_doc = frappe.get_doc(definition)
					new_doc.insert()
					frappe.db.commit()

					import_log.append({
						"doctype": doctype_name,
						"status": "success",
						"action": "created",
						"message": f"DocType '{doctype_name}' created successfully"
					})
					success_count += 1

			except Exception as e:
				error_msg = str(e)
				frappe.log_error(f"Error importing {doctype_name}: {error_msg}")
				import_log.append({
					"doctype": doctype_name,
					"status": "error",
					"action": "failed",
					"message": f"Error: {error_msg}"
				})
				error_count += 1
				frappe.db.rollback()

		return {
			"success": True,
			"import_log": import_log,
			"summary": {
				"total": len(doctypes_to_import),
				"success": success_count,
				"errors": error_count,
				"skipped": len([log for log in import_log if log["status"] == "skipped"])
			}
		}

	except Exception as e:
		frappe.log_error(f"Error importing DocTypes: {str(e)}")
		frappe.throw(_("Error importing DocTypes: {0}").format(str(e)))
