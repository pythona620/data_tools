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
			app_names = json.loads(app_names)
		except:
			# If it's not JSON, treat it as a single app name
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
		except:
			# If we can't get modules for the app, skip it
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
			AND name NOT LIKE 'DocType%%'
			AND module IN %(modules)s
		ORDER BY module, name
	""", {"modules": all_modules}, as_dict=True)

	return doctypes


@frappe.whitelist()
def create_partial_backup(doctypes, export_format='json'):
	"""Create a partial backup of selected DocTypes

	Args:
		doctypes: List of DocType names to backup
		export_format: 'json' or 'sql' (default: 'json')
	"""
	if isinstance(doctypes, str):
		doctypes = json.loads(doctypes)

	if not doctypes or not isinstance(doctypes, list) or len(doctypes) == 0:
		frappe.throw(_("Please select at least one DocType"))

	if export_format == 'sql':
		return create_sql_backup(doctypes)
	else:
		return create_json_backup(doctypes)


def create_json_backup(doctypes):
	"""Create JSON backup of selected DocTypes"""
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


def create_sql_backup(doctypes):
	"""Create SQL backup of selected DocTypes"""
	sql_statements = []
	total_records = 0

	# Add header comment
	sql_statements.append(f"""-- Partial Backup SQL Export
-- Created by: {frappe.session.user}
-- Creation date: {frappe.utils.now()}
-- Frappe version: {frappe.__version__}
-- Total DocTypes: {len(doctypes)}
--
-- This file contains SQL statements to backup selected DocTypes
-- WARNING: This will DROP and recreate tables!
--

SET FOREIGN_KEY_CHECKS=0;

""")

	for doctype_name in doctypes:
		try:
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

			total_records += records_count
			sql_statements.append(f"-- Records exported: {records_count}\n")

		except Exception as e:
			error_msg = f"Error backing up {doctype_name}: {str(e)}"
			frappe.log_error(error_msg)
			sql_statements.append(f"-- ERROR: {error_msg}\n")

	sql_statements.append(f"\nSET FOREIGN_KEY_CHECKS=1;")
	sql_statements.append(f"\n-- Total records exported: {total_records}")
	sql_statements.append(f"-- Backup completed: {frappe.utils.now()}\n")

	# Combine all SQL statements
	sql_content = "\n".join(sql_statements)

	# Encode to base64 for download
	file_data = base64.b64encode(sql_content.encode('utf-8')).decode()

	return {
		"success": True,
		"file_data": file_data,
		"filename": f"partial_backup_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.sql",
		"total_doctypes": len(doctypes),
		"total_records": total_records
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
