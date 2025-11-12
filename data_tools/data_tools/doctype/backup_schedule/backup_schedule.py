# -*- coding: utf-8 -*-
# Copyright (c) 2025, Admin and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime, add_days, add_months, getdate, get_time
from datetime import datetime, timedelta
import json


class BackupSchedule(Document):
	def validate(self):
		"""Validate schedule configuration"""
		# Validate frequency-specific fields
		if self.frequency == "Weekly" and not self.day_of_week:
			frappe.throw("Day of Week is required for weekly schedules")

		if self.frequency == "Monthly":
			if not self.day_of_month:
				frappe.throw("Day of Month is required for monthly schedules")
			if self.day_of_month < 1 or self.day_of_month > 31:
				frappe.throw("Day of Month must be between 1 and 31")

		if self.frequency == "Specific Date" and not self.specific_date:
			frappe.throw("Specific Date is required for specific date schedules")

		# Validate doctypes
		if not self.doctypes_to_backup or len(self.doctypes_to_backup) == 0:
			frappe.throw("Please select at least one DocType to backup")

		# Calculate next run if enabled
		if self.enabled:
			self.calculate_next_run()

	def calculate_next_run(self):
		"""Calculate the next run time based on frequency"""
		now = now_datetime()

		if self.frequency == "Specific Date":
			# For specific date, use the specific date and time
			specific_datetime = get_datetime(f"{self.specific_date} {self.time_of_day}")
			if specific_datetime > now:
				self.next_run = specific_datetime
			else:
				# If specific date has passed, disable the schedule
				self.enabled = 0
				self.next_run = None

		elif self.frequency == "Daily":
			# Calculate next daily run
			today = getdate()
			next_run = get_datetime(f"{today} {self.time_of_day}")

			# If today's time has passed, schedule for tomorrow
			if next_run <= now:
				next_run = add_days(next_run, 1)

			self.next_run = next_run

		elif self.frequency == "Weekly":
			# Calculate next weekly run
			today = getdate()
			current_weekday = today.weekday()  # Monday is 0

			# Map day names to numbers
			day_map = {
				"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
				"Friday": 4, "Saturday": 5, "Sunday": 6
			}
			target_weekday = day_map.get(self.day_of_week, 0)

			# Calculate days until target day
			days_ahead = target_weekday - current_weekday
			if days_ahead < 0:  # Target day already happened this week
				days_ahead += 7
			elif days_ahead == 0:  # Target day is today
				# Check if time has passed
				next_run = get_datetime(f"{today} {self.time_of_day}")
				if next_run <= now:
					days_ahead = 7

			next_run_date = add_days(today, days_ahead)
			self.next_run = get_datetime(f"{next_run_date} {self.time_of_day}")

		elif self.frequency == "Monthly":
			# Calculate next monthly run
			today = getdate()
			current_day = today.day

			# Try this month first
			try:
				next_run_date = today.replace(day=self.day_of_month)
				next_run = get_datetime(f"{next_run_date} {self.time_of_day}")

				if next_run <= now:
					# Move to next month
					next_run = add_months(next_run, 1)

				self.next_run = next_run
			except ValueError:
				# Day doesn't exist in current month, try next month
				next_month = add_months(today, 1)
				try:
					next_run_date = next_month.replace(day=self.day_of_month)
					self.next_run = get_datetime(f"{next_run_date} {self.time_of_day}")
				except ValueError:
					frappe.throw(f"Invalid day of month: {self.day_of_month}")

	def execute_backup(self):
		"""Execute the backup for this schedule"""
		try:
			# Get list of doctypes
			doctype_list = [d.doctype_name for d in self.doctypes_to_backup]

			# Import the backup function
			from data_tools.data_tools.page.partial_backup.partial_backup import create_partial_backup

			# Create backup
			result = create_partial_backup(doctypes=doctype_list, export_format=self.export_format)

			if result.get("success"):
				# Save backup file
				from frappe.utils.file_manager import save_file
				import base64

				file_data = base64.b64decode(result.get("file_data"))
				file_doc = save_file(
					fname=result.get("filename"),
					content=file_data,
					dt=self.doctype,
					dn=self.name,
					is_private=1
				)

				# Update status
				self.last_run = now_datetime()
				self.last_status = "Success"
				self.error_log = f"Backup created successfully: {result.get('filename')}\nTotal DocTypes: {result.get('total_doctypes')}\nTotal Records: {result.get('total_records')}"

				# Calculate next run
				self.calculate_next_run()
				self.save(ignore_permissions=True)

				frappe.log_error(
					f"Scheduled backup '{self.name}' completed successfully",
					"Scheduled Backup Success"
				)

				return True
			else:
				raise Exception("Backup creation failed")

		except Exception as e:
			# Update error status
			self.last_run = now_datetime()
			self.last_status = "Failed"
			self.error_log = str(e)
			self.save(ignore_permissions=True)

			frappe.log_error(
				f"Scheduled backup '{self.name}' failed: {str(e)}",
				"Scheduled Backup Error"
			)

			return False


@frappe.whitelist()
def run_backup_now(schedule_name):
	"""Manually trigger a backup schedule"""
	schedule = frappe.get_doc("Backup Schedule", schedule_name)

	if not schedule.enabled:
		frappe.throw("This schedule is disabled. Please enable it first.")

	success = schedule.execute_backup()

	if success:
		frappe.msgprint("Backup executed successfully!")
	else:
		frappe.throw("Backup execution failed. Check the error log for details.")

	return schedule.as_dict()
