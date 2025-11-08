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
def create_partial_backup(doctypes):
	"""Create a partial backup of selected DocTypes"""
	if isinstance(doctypes, str):
		doctypes = json.loads(doctypes)

	if not doctypes or not isinstance(doctypes, list) or len(doctypes) == 0:
		frappe.throw(_("Please select at least one DocType"))

	backup_data = {
		"backup_info": {
			"created_by": frappe.session.user,
			"creation_date": frappe.utils.now(),
			"frappe_version": frappe.__version__,
			"total_doctypes": len(doctypes)
		},
		"doctypes": []
	}

	total_records = 0

	for doctype_name in doctypes:
		try:
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

			backup_data["doctypes"].append({
				"doctype": doctype_name,
				"definition": doctype_json,
				"records": records,
				"record_count": len(records)
			})

			total_records += len(records)

		except Exception as e:
			frappe.log_error(f"Error backing up {doctype_name}: {str(e)}")
			frappe.msgprint(_("Error backing up {0}: {1}").format(doctype_name, str(e)))

	backup_data["backup_info"]["total_records"] = total_records

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
			"created_by": frappe.session.user,
			"creation_date": frappe.utils.now()
		}
		zip_file.writestr('metadata.json', json.dumps(metadata, indent=2, default=str))

	# Encode to base64 for download
	zip_buffer.seek(0)
	file_data = base64.b64encode(zip_buffer.getvalue()).decode()

	return {
		"success": True,
		"file_data": file_data,
		"filename": f"partial_backup_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.zip",
		"total_doctypes": len(backup_data["doctypes"]),
		"total_records": total_records
	}
