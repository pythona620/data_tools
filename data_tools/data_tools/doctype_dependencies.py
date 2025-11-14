"""
DocType Dependency Management Utilities

This module provides functions to:
1. Detect dependencies between DocTypes based on Link fields
2. Build dependency graphs
3. Perform topological sorting for correct restore order
4. Handle circular dependencies
"""

import frappe
from frappe import _
from collections import defaultdict, deque


def get_doctype_dependencies(doctype_name):
	"""
	Get all DocTypes that the given DocType depends on (via Link fields).

	Args:
		doctype_name (str): Name of the DocType to analyze

	Returns:
		list: List of DocType names that this DocType depends on
	"""
	try:
		meta = frappe.get_meta(doctype_name)
		dependencies = set()

		# Get all Link fields
		for field in meta.fields:
			if field.fieldtype == 'Link' and field.options:
				# Exclude self-references and common system doctypes
				if field.options != doctype_name and not is_system_doctype(field.options):
					dependencies.add(field.options)

			# Handle Table fields (child tables)
			elif field.fieldtype == 'Table' and field.options:
				# Child table dependencies will be handled separately
				# We don't add them as direct dependencies
				pass

		return list(dependencies)

	except Exception as e:
		frappe.log_error(f"Error getting dependencies for {doctype_name}: {str(e)}")
		return []


def get_all_dependencies_recursive(doctype_names, max_depth=10):
	"""
	Get all dependencies recursively for a list of DocTypes.

	Args:
		doctype_names (list): List of DocType names to analyze
		max_depth (int): Maximum recursion depth to prevent infinite loops

	Returns:
		dict: Dictionary with structure:
			{
				'dependencies': {doctype: [list of dependencies]},
				'all_doctypes': set of all doctypes including dependencies,
				'levels': {doctype: dependency_level}
			}
	"""
	dependencies = {}
	all_doctypes = set(doctype_names)
	visited = set()
	levels = {dt: 0 for dt in doctype_names}

	def explore(doctype, depth=0):
		if depth > max_depth or doctype in visited:
			return

		visited.add(doctype)
		deps = get_doctype_dependencies(doctype)
		dependencies[doctype] = deps

		for dep in deps:
			if dep not in all_doctypes:
				all_doctypes.add(dep)
				levels[dep] = depth + 1

			# Recursively explore dependencies
			if dep not in visited:
				explore(dep, depth + 1)

	# Explore all initial doctypes
	for doctype in doctype_names:
		explore(doctype)

	return {
		'dependencies': dependencies,
		'all_doctypes': all_doctypes,
		'levels': levels
	}


def build_dependency_tree(doctype_names):
	"""
	Build a complete dependency tree showing hierarchical relationships.

	Args:
		doctype_names (list): List of DocType names

	Returns:
		dict: Tree structure with dependency information
	"""
	result = get_all_dependencies_recursive(doctype_names)

	tree = {
		'selected': doctype_names,
		'dependencies': {},
		'new_dependencies': []
	}

	for doctype in doctype_names:
		deps = result['dependencies'].get(doctype, [])
		tree['dependencies'][doctype] = deps

		# Track new dependencies not in original selection
		for dep in deps:
			if dep not in doctype_names and dep not in tree['new_dependencies']:
				tree['new_dependencies'].append(dep)

	return tree


def topological_sort(doctype_names):
	"""
	Sort DocTypes in topological order based on dependencies.
	DocTypes with no dependencies come first, then those that depend on them.

	Args:
		doctype_names (list): List of DocType names to sort

	Returns:
		list: Sorted list of DocType names in correct restore order
	"""
	# Build adjacency list and in-degree count
	graph = defaultdict(list)
	in_degree = defaultdict(int)

	# Initialize all doctypes
	for doctype in doctype_names:
		if doctype not in in_degree:
			in_degree[doctype] = 0

	# Build graph
	for doctype in doctype_names:
		deps = get_doctype_dependencies(doctype)

		for dep in deps:
			# Only consider dependencies within our doctype list
			if dep in doctype_names:
				graph[dep].append(doctype)
				in_degree[doctype] += 1

	# Kahn's algorithm for topological sort
	queue = deque()

	# Add all nodes with no dependencies
	for doctype in doctype_names:
		if in_degree[doctype] == 0:
			queue.append(doctype)

	sorted_list = []

	while queue:
		current = queue.popleft()
		sorted_list.append(current)

		# Reduce in-degree for dependent doctypes
		for dependent in graph[current]:
			in_degree[dependent] -= 1
			if in_degree[dependent] == 0:
				queue.append(dependent)

	# Check for circular dependencies
	if len(sorted_list) != len(doctype_names):
		# There are circular dependencies - return with warning
		# Include remaining doctypes at the end
		remaining = [dt for dt in doctype_names if dt not in sorted_list]
		frappe.log_error(
			f"Circular dependencies detected among: {', '.join(remaining)}",
			"DocType Dependency Warning"
		)
		sorted_list.extend(remaining)

	return sorted_list


def get_dependency_graph(doctype_names):
	"""
	Get a complete dependency graph with metadata for UI display.

	Args:
		doctype_names (list): List of DocType names

	Returns:
		dict: Graph data including nodes, edges, and metadata
	"""
	result = get_all_dependencies_recursive(doctype_names)

	nodes = []
	edges = []

	for doctype in result['all_doctypes']:
		is_selected = doctype in doctype_names
		is_dependency = not is_selected

		nodes.append({
			'id': doctype,
			'label': doctype,
			'is_selected': is_selected,
			'is_dependency': is_dependency,
			'level': result['levels'].get(doctype, 0)
		})

	# Build edges
	for doctype, deps in result['dependencies'].items():
		for dep in deps:
			edges.append({
				'from': doctype,
				'to': dep,
				'label': 'depends on'
			})

	return {
		'nodes': nodes,
		'edges': edges,
		'selected_count': len(doctype_names),
		'dependency_count': len(result['all_doctypes']) - len(doctype_names),
		'total_count': len(result['all_doctypes'])
	}


def is_system_doctype(doctype_name):
	"""
	Check if a DocType is a system DocType that should be excluded from dependencies.

	Args:
		doctype_name (str): DocType name to check

	Returns:
		bool: True if it's a system DocType
	"""
	system_doctypes = [
		'User', 'Role', 'Role Profile', 'User Type',
		'DocType', 'DocField', 'DocPerm',
		'File', 'Communication', 'Comment', 'Version',
		'Email Queue', 'Email Account', 'Notification Log',
		'Activity Log', 'Error Log', 'Scheduled Job Log',
		'Print Format', 'Custom Field', 'Property Setter',
		'Workflow', 'Workflow State', 'Workflow Action',
		'Assignment Rule', 'Server Script', 'Client Script',
		'Module Def', 'Domain', 'Domain Settings'
	]

	return doctype_name in system_doctypes


def get_dependency_summary(doctype_names):
	"""
	Get a summary of dependencies for display in UI.

	Args:
		doctype_names (list): List of selected DocType names

	Returns:
		dict: Summary information including dependency list and counts
	"""
	result = get_all_dependencies_recursive(doctype_names)

	dependencies_by_doctype = {}
	all_new_deps = set()

	for doctype in doctype_names:
		deps = result['dependencies'].get(doctype, [])
		new_deps = [d for d in deps if d not in doctype_names]

		if new_deps:
			dependencies_by_doctype[doctype] = new_deps
			all_new_deps.update(new_deps)

	return {
		'selected_doctypes': doctype_names,
		'selected_count': len(doctype_names),
		'dependencies_by_doctype': dependencies_by_doctype,
		'all_new_dependencies': sorted(list(all_new_deps)),
		'new_dependency_count': len(all_new_deps),
		'total_with_dependencies': len(doctype_names) + len(all_new_deps),
		'has_dependencies': len(all_new_deps) > 0
	}


def validate_restore_order(doctype_names):
	"""
	Validate if the given order of DocTypes is valid for restore.

	Args:
		doctype_names (list): List of DocTypes in the order they will be restored

	Returns:
		dict: Validation result with issues if any
	"""
	issues = []
	processed = set()

	for i, doctype in enumerate(doctype_names):
		deps = get_doctype_dependencies(doctype)

		# Check if dependencies that are in the list come before this doctype
		for dep in deps:
			if dep in doctype_names and dep not in processed:
				issues.append({
					'doctype': doctype,
					'position': i,
					'missing_dependency': dep,
					'message': f"{doctype} depends on {dep} but {dep} comes later or is missing"
				})

		processed.add(doctype)

	return {
		'is_valid': len(issues) == 0,
		'issues': issues,
		'issue_count': len(issues)
	}
