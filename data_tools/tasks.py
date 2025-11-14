# -*- coding: utf-8 -*-
# Copyright (c) 2025, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime, get_datetime


def process_scheduled_backups():
	"""
	Process all enabled backup schedules that are due to run.
	This function is called by the scheduler every hour.
	"""
	try:
		# Get all enabled schedules that are due
		now = now_datetime()

		schedules = frappe.get_all(
			"Backup Schedule",
			filters={
				"enabled": 1,
				"next_run": ["<=", now]
			},
			fields=["name"]
		)

		if not schedules:
			return

		frappe.log_error(
			f"Processing {len(schedules)} scheduled backup(s)",
			"Scheduled Backup Processing"
		)

		# Process each schedule
		for schedule_data in schedules:
			try:
				schedule = frappe.get_doc("Backup Schedule", schedule_data.name)

				# Execute the backup
				schedule.execute_backup()

				frappe.db.commit()

			except Exception as e:
				frappe.log_error(
					f"Error processing schedule '{schedule_data.name}': {str(e)}",
					"Scheduled Backup Error"
				)
				frappe.db.rollback()

	except Exception as e:
		frappe.log_error(
			f"Error in scheduled backup processor: {str(e)}",
			"Scheduled Backup Processor Error"
		)


def check_backup_schedules():
	"""
	Check for schedules that need next_run calculation.
	This is a maintenance task that runs daily.
	"""
	try:
		# Get all enabled schedules without next_run
		schedules = frappe.get_all(
			"Backup Schedule",
			filters={
				"enabled": 1,
				"next_run": ["is", "not set"]
			},
			fields=["name"]
		)

		for schedule_data in schedules:
			try:
				schedule = frappe.get_doc("Backup Schedule", schedule_data.name)
				schedule.calculate_next_run()
				schedule.save(ignore_permissions=True)
				frappe.db.commit()

			except Exception as e:
				frappe.log_error(
					f"Error calculating next run for '{schedule_data.name}': {str(e)}",
					"Backup Schedule Maintenance Error"
				)
				frappe.db.rollback()

	except Exception as e:
		frappe.log_error(
			f"Error in backup schedule maintenance: {str(e)}",
			"Backup Schedule Maintenance Error"
		)
