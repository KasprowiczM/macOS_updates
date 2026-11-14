"""Small pure helpers and fallback labels for the terminal workspace."""

import re


UI_EN = {
    "nav_about": "About",
    "preview_button": "Preview",
    "run_button": "Run",
    "help_button": "Help",
    "exit_button": "Exit",
    "send_button": "Send",
    "cancel_button": "Cancel",
    "output_button": "Output",
    "controls_hint": "Tab: controls   Arrows: select   Space: checkbox   Enter: button   F1: help",
    "disabled_control": "This control is unavailable while another operation is active.",
    "inventory_search": "Search applications",
    "inventory_source": "Source",
    "inventory_sort": "Sort",
    "inventory_reload": "Refresh list",
    "inventory_save": "Save selection",
    "inventory_empty": "No matching applications. Build the local inventory or change the filter.",
    "inventory_unavailable": "Saved inventory is unavailable. Build the local inventory first.",
    "inventory_scope_note": "Checkboxes include or exclude an observed application. They never install, uninstall or approve updates.",
    "inventory_changes": "Unsaved selection changes: {count}",
    "inventory_save_first": "Save or discard the pending inventory changes before previewing or running updates.",
    "inventory_discard": "Discard the unsaved selection changes and refresh the list?",
    "inventory_column_name": "Application",
    "inventory_column_version": "Version",
    "inventory_column_status": "State",
    "inventory_column_activity": "Activity",
    "inventory_column_elapsed": "Time",
    "interrupt_button": "Interrupt",
    "inventory_source_vendor": "Vendor source",
    "inventory_source_conflict": "Conflicting sources",
    "inventory_source_managed": "Managed by your organization",
    "inventory_all_sources": "All sources",
    "inventory_sort_name": "Name",
    "inventory_sort_version": "Version",
    "inventory_sort_source": "Source",
    "inventory_sort_status": "Policy",
    "inventory_status_enabled": "Included",
    "inventory_status_excluded": "Excluded",
    "inventory_status_manual": "Manual",
    "inventory_status_blocked": "Blocked",
    "inventory_reason_evidence": "Inventory or identity evidence is incomplete. No automatic update is authorized.",
    "inventory_reason_conflict": "Sources conflict. Review the installation source before updating.",
    "inventory_reason_manual": "Manual policy or an unaccepted recipe prevents automatic updates.",
    "inventory_reason_excluded": "This target is excluded. Re-enabling requires separate update consent.",
    "inventory_reason_consent": "An explicit decision is required before an update can run.",
    "inventory_reason_running": "The application is running or its state cannot be confirmed.",
    "inventory_reason_deferred": "The target is deferred by the saved policy.",
    "inventory_reason_review": "Review the source and capability before enabling execution.",
    "about_author": "Author: Michał Kasprowicz",
    "about_version": "Toolkit version: {version}",
    "about_website": "Website: https://macos-updates.64bit.site",
    "about_source": "Source: https://github.com/KasprowiczM/macOS_updates",
    "toolkit_check": "Check toolkit updates",
    "toolkit_preview": "Preview toolkit update",
    "toolkit_apply": "Apply toolkit update",
    "toolkit_idle": "Check the official source on request. Local code changes block automatic replacement; private settings stay local.",
    "toolkit_checking": "Checking the official source...",
    "toolkit_result": "Toolkit update: {status}",
    "prompt_pending": "This operation needs your answer. Review the question, then choose Send or Cancel.",
    "prompt_cancelled": "Answer editor closed. No answer was sent; the operation is still waiting.",
    "preview_notice": "Preview only. No application updates or new permissions are applied.",
    "activity_unknown": "Working; total progress is unknown",
    "phase_progress": "Observed phase progress",
    'internet_mode': 'Internet mode',
    'internet_mode_automatic': 'Automatic batch',
    'internet_mode_per_app': 'Per-app choices',
    'internet_batch_hint': 'Review the exact automatic batch before approving. Its eligible app windows may start concurrently. DeepSeek stays manual. No mode switch grants permission.',
    'internet_per_app_hint': 'Per-app mode keeps saved automatic or manual choices. Use Review update permissions to change individual targets. Save in Settings to remember this mode.',
    'internet_mode_changed': 'Requested mode changed. Save in Settings to remember it; update consent is still separate.',
    'native_pending': 'Unconfirmed',
    'native_pending_detail': 'The vendor updater may still be working outside this workflow. Its completion is unconfirmed.',
    'native_observing_detail': 'Watching the installed version after launch. Total progress is unknown.',
    'native_version_changed_detail': 'The installed version changed. Latest-release status and vendor helper completion remain unconfirmed.',
    'legacy_unconfirmed_detail': 'The handler returned, but vendor helper completion and the latest version remain unconfirmed.',
    'inventory_reason_unsupported': 'No supported automatic update method exists for this app. Update it manually.',
    'inventory_reason_owner_manual': 'This app is intentionally manual by your choice.',
    'context_title': 'Help and status',
    'context_workflow': 'Workflow: {status}',
    'context_navigation': 'Tab moves between panes. Arrows select. Enter opens a button. F1 opens help.',
    'context_answer': 'Read the scope. Type an answer; Enter sends it. Esc closes without sending. PgUp reviews earlier text.',
    'context_confirm': 'Cancel is selected first. Tab chooses a button; Enter activates it. Confirm only the scope you reviewed.',
    'context_wizard': 'Choose an option, then Next. Back returns. Navigation does not install or approve updates.',
}


def natural_key(value):
    return tuple((1, int(piece)) if piece.isdigit() else (0, piece.casefold())
                 for piece in re.split(r"(\d+)", str(value)))


def inventory_rows(rows, query="", source="all", sort="source"):
    query = query.casefold().strip()
    values = [row for row in rows if (source == "all" or row.get("source") == source)
              and (not query or query in " ".join(str(row.get(k, "")) for k in ("name", "version", "source", "path")).casefold())]
    field = {"name": "name", "version": "version", "source": "source", "status": "status"}.get(sort, "name")
    return sorted(values, key=lambda row: (str(row.get("source", "unknown")).casefold(),
                                         natural_key(row.get(field, "")), natural_key(row.get("name", ""))))


def panel_sizes(width):
    """Keep contextual help visible even in the minimum supported terminal."""
    return (28, 32) if width >= 120 else (20, 26) if width >= 100 else (18, 26)
