# Copyright (c) 2026, PMG Team and contributors
# For license information, please see license.txt

import json
import os
import frappe

def execute():
	"""Syncs the AMP workspace layout and links directly into the database on bench migrate"""
	workspace_path = frappe.get_app_path("amp", "amp", "workspace", "amp", "amp.json")
	if not os.path.exists(workspace_path):
		return

	with open(workspace_path, "r") as f:
		data = json.load(f)

	if frappe.db.exists("Workspace", "AMP"):
		doc = frappe.get_doc("Workspace", "AMP")
	else:
		doc = frappe.new_doc("Workspace")
		doc.name = "AMP"
		doc.label = "AMP"

	doc.title = data.get("title", "AMP")
	doc.icon = data.get("icon", "project")
	doc.indicator_color = data.get("indicator_color", "blue")
	doc.is_hidden = 0
	doc.public = 1
	doc.content = data.get("content")

	doc.shortcuts = []
	for s in data.get("shortcuts", []):
		doc.append("shortcuts", s)

	doc.links = []
	for l in data.get("links", []):
		doc.append("links", l)

	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True
	doc.flags.ignore_validate = True
	doc.save(ignore_permissions=True)

	frappe.clear_cache()
