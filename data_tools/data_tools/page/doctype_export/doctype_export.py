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
			parsed = json.loads(app_names)
			if isinstance(parsed, list):
				app_names = parsed
			else:
				app_names = [str(parsed)]
		except (json.JSONDecodeError, ValueError):
			app_names = [app_names]

	# Ensure it's a list
	if not isinstance(app_names, list):
		app_names = [app_names]

	# Get modules for all selected apps
	all_modules = []
	for app_name in app_names:
		try:
			app_modules = frappe.get_module_list(app_name)
			all_modules.extend(app_modules)
		except Exception as e:
			logger.warning(f"Error getting modules for app '{app_name}': {str(e)}")
			continue

	# Remove duplicates
	all_modules = list(set(all_modules))

	if not all_modules:
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

	return doctypes


@frappe.whitelist()
def export_doctypes(doctypes):
	"""Export only DocType schemas (definitions) without data

	Args:
		doctypes: List of DocType names to export

	Returns:
		dict: Contains file_data (base64 encoded ZIP) and filename
	"""
	if isinstance(doctypes, str):
		doctypes = json.loads(doctypes)

	if not doctypes or not isinstance(doctypes, list) or len(doctypes) == 0:
		frappe.throw(_("Please select at least one DocType"))

	export_data = {
		"export_info": {
			"created_by": frappe.session.user,
			"creation_date": frappe.utils.now(),
			"frappe_version": frappe.__version__,
			"total_doctypes": len(doctypes),
			"export_type": "doctype_schemas_only"
		},
		"doctypes": []
	}

	for doctype_name in doctypes:
		try:
			# Get DocType definition
			doctype_doc = frappe.get_doc("DocType", doctype_name)
			doctype_json = doctype_doc.as_dict()

			# Add to export data (schema only, no records)
			export_data["doctypes"].append({
				"doctype": doctype_name,
				"definition": doctype_json,
				"module": doctype_doc.module,
				"is_custom": doctype_doc.custom,
				"is_single": doctype_doc.issingle
			})

		except Exception as e:
			frappe.log_error(f"Error exporting {doctype_name}: {str(e)}")
			# Continue with other doctypes

	# Create ZIP file
	zip_buffer = BytesIO()
	with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
		# Add JSON data to ZIP
		json_data = json.dumps(export_data, indent=2, default=str)
		zip_file.writestr('doctype_schemas.json', json_data)

		# Add metadata file for preview
		metadata = {
			"doctypes": [dt["doctype"] for dt in export_data["doctypes"]],
			"total_doctypes": len(export_data["doctypes"]),
			"export_type": "doctype_schemas_only",
			"created_by": frappe.session.user,
			"creation_date": frappe.utils.now(),
			"frappe_version": frappe.__version__
		}
		zip_file.writestr('metadata.json', json.dumps(metadata, indent=2, default=str))

	# Encode to base64 for download
	zip_buffer.seek(0)
	file_data = base64.b64encode(zip_buffer.getvalue()).decode()

	return {
		"success": True,
		"file_data": file_data,
		"filename": f"doctype_export_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip",
		"total_doctypes": len(export_data["doctypes"])
	}
