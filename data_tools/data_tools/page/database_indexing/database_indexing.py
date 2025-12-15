# -*- coding: utf-8 -*-
# Copyright (c) 2025, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import logging

logger = logging.getLogger(__name__)


@frappe.whitelist()
def get_all_indexes():
	"""Get all indexes in the database with their statistics

	Returns:
		list: List of indexes with their details
	"""
	try:
		site_db = frappe.conf.db_name

		# Get all indexes from information_schema
		indexes = frappe.db.sql("""
			SELECT
				TABLE_NAME as table_name,
				INDEX_NAME as index_name,
				COLUMN_NAME as column_name,
				SEQ_IN_INDEX as seq_in_index,
				NON_UNIQUE as non_unique,
				INDEX_TYPE as index_type,
				CARDINALITY as cardinality,
				NULLABLE as nullable
			FROM information_schema.STATISTICS
			WHERE TABLE_SCHEMA = %(db)s
				AND TABLE_NAME LIKE 'tab%%'
			ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
		""", {"db": site_db}, as_dict=True)

		# Group indexes by table and index name
		grouped_indexes = {}
		for idx in indexes:
			key = f"{idx['table_name']}.{idx['index_name']}"
			if key not in grouped_indexes:
				grouped_indexes[key] = {
					'table_name': idx['table_name'],
					'index_name': idx['index_name'],
					'columns': [],
					'non_unique': idx['non_unique'],
					'index_type': idx['index_type'],
					'cardinality': idx['cardinality']
				}
			grouped_indexes[key]['columns'].append({
				'column_name': idx['column_name'],
				'seq': idx['seq_in_index'],
				'nullable': idx['nullable']
			})

		return list(grouped_indexes.values())

	except Exception as e:
		frappe.log_error(f"Error getting indexes: {str(e)}", "Database Indexing Error")
		return []


@frappe.whitelist()
def get_filter_options(apps=None):
	"""Get available filter options for apps, modules, and doctypes

	Args:
		apps: JSON string of selected apps to filter modules and doctypes

	Returns:
		dict: Available apps, modules, and doctypes
	"""
	try:
		import json

		# Parse apps if provided
		selected_apps = None
		if apps:
			try:
				selected_apps = json.loads(apps) if isinstance(apps, str) else apps
				if not isinstance(selected_apps, list):
					selected_apps = [selected_apps]
			except:
				selected_apps = None

		# Get all installed apps
		all_apps = frappe.get_installed_apps()

		# Build filters for modules and doctypes based on selected apps
		doctype_filters = {'istable': 0}
		if selected_apps:
			doctype_filters['app'] = ['in', selected_apps]

		# Get filtered doctypes
		doctypes = frappe.get_all('DocType',
			filters=doctype_filters,
			fields=['name', 'module', 'app'],
			order_by='name'
		)

		# Extract unique modules from filtered doctypes
		module_set = set()
		doctype_list = []
		for dt in doctypes:
			doctype_list.append(dt['name'])
			if dt.get('module'):
				module_set.add(dt['module'])

		module_list = sorted(list(module_set))

		return {
			'apps': all_apps,
			'modules': module_list,
			'doctypes': doctype_list
		}

	except Exception as e:
		frappe.log_error(f"Error getting filter options: {str(e)}", "Database Indexing Error")
		return {'apps': [], 'modules': [], 'doctypes': []}


@frappe.whitelist()
def get_table_wise_indexes(apps=None, modules=None, doctypes=None):
	"""Get indexes grouped by table with statistics

	Args:
		apps: JSON string or list of app names
		modules: JSON string or list of module names
		doctypes: JSON string or list of doctype names

	Returns:
		list: List of tables with their indexes and statistics
	"""
	try:
		import json
		site_db = frappe.conf.db_name

		# Parse filter parameters
		def parse_filter(param):
			if not param:
				return None
			if isinstance(param, str):
				try:
					parsed = json.loads(param)
					return parsed if isinstance(parsed, list) else [parsed]
				except:
					return [param]
			elif isinstance(param, list):
				return param
			else:
				return [param]

		apps_list = parse_filter(apps)
		modules_list = parse_filter(modules)
		doctypes_list = parse_filter(doctypes)

		# Build doctype filters
		doctype_filters = {}
		if modules_list:
			doctype_filters['module'] = ['in', modules_list]
		if apps_list:
			doctype_filters['app'] = ['in', apps_list]
		if doctypes_list:
			doctype_filters['name'] = ['in', doctypes_list]

		# Get filtered doctypes
		if doctype_filters:
			filtered_doctypes = frappe.get_all('DocType',
				filters=doctype_filters,
				fields=['name', 'module', 'app']
			)
			allowed_tables = [f"tab{dt['name']}" for dt in filtered_doctypes]
			if not allowed_tables:
				return []
		else:
			allowed_tables = None

		# Get all indexes
		indexes = frappe.db.sql("""
			SELECT
				TABLE_NAME as table_name,
				INDEX_NAME as index_name,
				COLUMN_NAME as column_name,
				SEQ_IN_INDEX as seq_in_index,
				NON_UNIQUE as non_unique,
				INDEX_TYPE as index_type,
				CARDINALITY as cardinality
			FROM information_schema.STATISTICS
			WHERE TABLE_SCHEMA = %(db)s
				AND TABLE_NAME LIKE 'tab%%'
			ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
		""", {"db": site_db}, as_dict=True)

		# Get table statistics
		table_stats = frappe.db.sql("""
			SELECT
				TABLE_NAME as table_name,
				TABLE_ROWS as row_count,
				DATA_LENGTH as data_size,
				INDEX_LENGTH as index_size,
				ROUND(((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024), 2) AS total_size_mb
			FROM information_schema.TABLES
			WHERE TABLE_SCHEMA = %(db)s
				AND TABLE_NAME LIKE 'tab%%'
		""", {"db": site_db}, as_dict=True)

		# Create lookup for table stats
		stats_lookup = {stat['table_name']: stat for stat in table_stats}

		# Get doctype metadata for module and app info
		doctype_meta = {}
		all_doctypes = frappe.get_all('DocType',
			fields=['name', 'module', 'app'],
			order_by='name'
		)
		for dt in all_doctypes:
			doctype_meta[f"tab{dt['name']}"] = {
				'module': dt.get('module'),
				'app': dt.get('app')
			}

		# Group indexes by table
		table_wise = {}
		for idx in indexes:
			table = idx['table_name']

			# Apply filter if specified
			if allowed_tables and table not in allowed_tables:
				continue

			if table not in table_wise:
				meta = doctype_meta.get(table, {})
				table_wise[table] = {
					'table_name': table,
					'doctype': table.replace('tab', ''),
					'module': meta.get('module', ''),
					'app': meta.get('app', ''),
					'indexes': {},
					'statistics': stats_lookup.get(table, {})
				}

			index_name = idx['index_name']
			if index_name not in table_wise[table]['indexes']:
				table_wise[table]['indexes'][index_name] = {
					'index_name': index_name,
					'columns': [],
					'non_unique': idx['non_unique'],
					'index_type': idx['index_type'],
					'cardinality': idx['cardinality']
				}

			table_wise[table]['indexes'][index_name]['columns'].append({
				'column_name': idx['column_name'],
				'seq': idx['seq_in_index']
			})

		# Convert to list and sort by table size
		result = list(table_wise.values())
		result = sorted(result, key=lambda x: x['statistics'].get('total_size_mb', 0) or 0, reverse=True)

		return result

	except Exception as e:
		frappe.log_error(f"Error getting table-wise indexes: {str(e)}", "Database Indexing Error")
		return []


@frappe.whitelist()
def get_index_suggestions(apps=None, modules=None, doctypes=None):
	"""Analyze database and suggest missing indexes

	Args:
		apps: JSON string or list of app names
		modules: JSON string or list of module names
		doctypes: JSON string or list of doctype names

	Returns:
		list: List of suggested indexes
	"""
	try:
		import json
		suggestions = []

		# Parse filter parameters
		def parse_filter(param):
			if not param:
				return None
			if isinstance(param, str):
				try:
					parsed = json.loads(param)
					return parsed if isinstance(parsed, list) else [parsed]
				except:
					return [param]
			elif isinstance(param, list):
				return param
			else:
				return [param]

		apps_list = parse_filter(apps)
		modules_list = parse_filter(modules)
		doctypes_list = parse_filter(doctypes)

		# Build doctype filters
		doctype_filters = {'istable': 0}
		if modules_list:
			doctype_filters['module'] = ['in', modules_list]
		if apps_list:
			doctype_filters['app'] = ['in', apps_list]
		if doctypes_list:
			doctype_filters['name'] = ['in', doctypes_list]

		# Get filtered DocTypes
		all_doctypes = frappe.get_all('DocType', filters=doctype_filters, fields=['name', 'module', 'app'])

		for dt in all_doctypes:
			try:
				meta = frappe.get_meta(dt.name)
				table_name = f"tab{dt.name}"

				# Get table row count for priority calculation
				row_count = get_table_row_count(table_name)

				# Check for Link fields without indexes
				for field in meta.fields:
					if field.fieldtype == 'Link' and field.options:
						index_exists = check_index_exists(table_name, field.fieldname)

						if not index_exists:
							priority = 'High' if row_count > 1000 else 'Medium'
							suggestions.append({
								'table_name': table_name,
								'doctype': dt.name,
								'module': dt.get('module', ''),
								'app': dt.get('app', ''),
								'column_name': field.fieldname,
								'reason': f'Link field to {field.options} without index',
								'priority': priority,
								'type': 'Single Column',
								'estimated_benefit': 'Faster JOIN operations and filtering',
								'row_count': row_count
							})

				# Check for Select fields with many options
				for field in meta.fields:
					if field.fieldtype in ['Select', 'Data'] and field.fieldname in ['status', 'workflow_state']:
						index_exists = check_index_exists(table_name, field.fieldname)

						if not index_exists:
							priority = 'High' if row_count > 5000 else 'Medium'
							suggestions.append({
								'table_name': table_name,
								'doctype': dt.name,
								'module': dt.get('module', ''),
								'app': dt.get('app', ''),
								'column_name': field.fieldname,
								'reason': f'Frequently filtered {field.fieldtype} field',
								'priority': priority,
								'type': 'Single Column',
								'estimated_benefit': 'Faster filtering and grouping',
								'row_count': row_count
							})

				# Check for date fields that are commonly filtered
				for field in meta.fields:
					if field.fieldtype in ['Date', 'Datetime'] and field.fieldname not in ['creation', 'modified']:
						index_exists = check_index_exists(table_name, field.fieldname)

						if not index_exists and row_count > 2000:
							suggestions.append({
								'table_name': table_name,
								'doctype': dt.name,
								'module': dt.get('module', ''),
								'app': dt.get('app', ''),
								'column_name': field.fieldname,
								'reason': f'Date field for range queries',
								'priority': 'Medium',
								'type': 'Single Column',
								'estimated_benefit': 'Faster date range filtering',
								'row_count': row_count
							})

				# Suggest composite indexes for common Frappe patterns
				composite_patterns = [
					{
						'columns': 'owner,creation',
						'reason': 'Common pattern: queries by user and date',
						'benefit': 'Faster user activity queries',
						'priority': 'Low'
					},
					{
						'columns': 'modified_by,modified',
						'reason': 'Common pattern: last modified tracking',
						'benefit': 'Faster modified queries',
						'priority': 'Low'
					},
					{
						'columns': 'docstatus,modified',
						'reason': 'Common pattern: document status with timeline',
						'benefit': 'Faster status-based queries',
						'priority': 'Medium' if row_count > 3000 else 'Low'
					}
				]

				for pattern in composite_patterns:
					if not check_index_exists(table_name, pattern['columns']) and row_count > 1000:
						suggestions.append({
							'table_name': table_name,
							'doctype': dt.name,
							'module': dt.get('module', ''),
							'app': dt.get('app', ''),
							'column_name': pattern['columns'],
							'reason': pattern['reason'],
							'priority': pattern['priority'],
							'type': 'Composite',
							'estimated_benefit': pattern['benefit'],
							'row_count': row_count
						})

				# Check for child table parent field indexes
				if meta.istable:
					if not check_index_exists(table_name, 'parent'):
						suggestions.append({
							'table_name': table_name,
							'doctype': dt.name,
							'module': dt.get('module', ''),
							'app': dt.get('app', ''),
							'column_name': 'parent',
							'reason': 'Child table parent field without index',
							'priority': 'Critical',
							'type': 'Single Column',
							'estimated_benefit': 'Essential for child table queries',
							'row_count': row_count
						})

			except Exception as e:
				logger.warning(f"Error analyzing {dt.name}: {str(e)}")
				continue

		# Remove duplicates and sort by priority
		priority_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
		suggestions = sorted(suggestions, key=lambda x: (priority_order.get(x['priority'], 4), -x.get('row_count', 0)))

		return suggestions[:100]  # Limit to top 100 suggestions

	except Exception as e:
		frappe.log_error(f"Error getting suggestions: {str(e)}", "Index Suggestions Error")
		return []


def get_table_row_count(table_name):
	"""Get approximate row count for a table

	Args:
		table_name: Name of the table

	Returns:
		int: Row count
	"""
	try:
		result = frappe.db.sql(f"SELECT COUNT(*) as count FROM `{table_name}`", as_dict=True)
		return result[0]['count'] if result else 0
	except Exception:
		return 0


def check_index_exists(table_name, column_name):
	"""Check if an index exists for a column or columns

	Args:
		table_name: Name of the table
		column_name: Column name or comma-separated column names

	Returns:
		bool: True if index exists
	"""
	try:
		site_db = frappe.conf.db_name
		columns = [c.strip() for c in column_name.split(',')]

		# Get all indexes for this table
		indexes = frappe.db.sql("""
			SELECT
				INDEX_NAME,
				GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) as columns
			FROM information_schema.STATISTICS
			WHERE TABLE_SCHEMA = %(db)s
				AND TABLE_NAME = %(table)s
			GROUP BY INDEX_NAME
		""", {"db": site_db, "table": table_name}, as_dict=True)

		# Check if any index matches our columns
		for idx in indexes:
			idx_columns = [c.strip() for c in idx['columns'].split(',')]
			if idx_columns == columns or idx_columns[0] == columns[0]:
				return True

		return False

	except Exception as e:
		logger.error(f"Error checking index: {str(e)}")
		return False


@frappe.whitelist()
def create_index(table_name, column_names, index_name=None):
	"""Create an index on specified columns

	Args:
		table_name: Name of the table
		column_names: Column name or comma-separated column names
		index_name: Optional custom index name

	Returns:
		dict: Success status and message
	"""
	try:
		# Validate table name (security check)
		if not table_name.startswith('tab'):
			frappe.throw(_("Invalid table name"))

		# Generate index name if not provided
		if not index_name:
			columns = [c.strip() for c in column_names.split(',')]
			index_name = f"idx_{'_'.join(columns)}"

		# Check if index already exists
		if check_index_exists(table_name, column_names):
			return {
				'success': False,
				'message': _("Index already exists")
			}

		# Create the index
		columns_list = ', '.join([f"`{c.strip()}`" for c in column_names.split(',')])
		sql = f"CREATE INDEX `{index_name}` ON `{table_name}` ({columns_list})"

		frappe.db.sql(sql)
		frappe.db.commit()

		logger.info(f"Created index {index_name} on {table_name}({column_names})")

		return {
			'success': True,
			'message': _("Index created successfully")
		}

	except Exception as e:
		frappe.db.rollback()
		error_msg = str(e)
		frappe.log_error(f"Error creating index: {error_msg}", "Create Index Error")
		return {
			'success': False,
			'message': _("Error creating index: {0}").format(error_msg)
		}


@frappe.whitelist()
def drop_index(table_name, index_name):
	"""Drop an index

	Args:
		table_name: Name of the table
		index_name: Name of the index to drop

	Returns:
		dict: Success status and message
	"""
	try:
		# Validate table name (security check)
		if not table_name.startswith('tab'):
			frappe.throw(_("Invalid table name"))

		# Don't allow dropping PRIMARY key
		if index_name == 'PRIMARY':
			frappe.throw(_("Cannot drop PRIMARY key"))

		# Drop the index
		sql = f"DROP INDEX `{index_name}` ON `{table_name}`"
		frappe.db.sql(sql)
		frappe.db.commit()

		logger.info(f"Dropped index {index_name} from {table_name}")

		return {
			'success': True,
			'message': _("Index dropped successfully")
		}

	except Exception as e:
		frappe.db.rollback()
		error_msg = str(e)
		frappe.log_error(f"Error dropping index: {error_msg}", "Drop Index Error")
		return {
			'success': False,
			'message': _("Error dropping index: {0}").format(error_msg)
		}


@frappe.whitelist()
def analyze_table(table_name):
	"""Run ANALYZE TABLE to update index statistics

	Args:
		table_name: Name of the table

	Returns:
		dict: Success status and message
	"""
	try:
		# Validate table name (security check)
		if not table_name.startswith('tab'):
			frappe.throw(_("Invalid table name"))

		# Run ANALYZE TABLE
		result = frappe.db.sql(f"ANALYZE TABLE `{table_name}`", as_dict=True)
		frappe.db.commit()

		logger.info(f"Analyzed table {table_name}")

		return {
			'success': True,
			'message': _("Table analyzed successfully"),
			'result': result
		}

	except Exception as e:
		error_msg = str(e)
		frappe.log_error(f"Error analyzing table: {error_msg}", "Analyze Table Error")
		return {
			'success': False,
			'message': _("Error analyzing table: {0}").format(error_msg)
		}
