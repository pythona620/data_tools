# Data Tools

A comprehensive Frappe app for creating partial backups, restoring specific DocTypes, and managing DocType schemas. This tool allows you to selectively backup and restore data, as well as export and import DocType definitions without affecting the entire database.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Data Tools provides a flexible and user-friendly interface for managing partial backups and DocType schemas in Frappe applications. Whether you need to migrate specific modules, backup critical data, restore selective DocTypes, or transfer DocType structures between sites, this app streamlines the entire process.

## Features

### 1. Partial Backup

Create selective backups of specific DocTypes with an intuitive interface:

- **Multi-select Interface**: Easy selection of multiple DocTypes
- **Module Filtering**: Filter DocTypes by module for organized selection
- **Search Functionality**: Quickly find DocTypes using the search bar
- **Select/Deselect All**: Bulk selection controls for efficiency
- **Compressed Output**: Generates ZIP files for optimal storage
- **Complete Data Export**: Includes both schema and all records

**What's Included in Backups:**
- DocType definitions (complete schema)
- All records for selected DocTypes
- Metadata (creator, date, Frappe version)
- Record counts for each DocType

![Partial Backup Interface](C:\Users\CaratRED\Desktop\backup_.png)

### 2. Partial Restore

Restore data from backup files with preview and control:

- **File Upload**: Simple drag-and-drop or browse interface
- **Backup Preview**: View contents before restoring
- **Detailed Information**: See DocTypes and record counts
- **Smart Restoration**: Automatic DocType creation if missing
- **Duplicate Handling**: Skip existing records to prevent conflicts
- **Comprehensive Logging**: Detailed restore log with success/error tracking
- **Summary Statistics**: Overview of imported records and errors

**Restore Features:**
- DocType creation (if doesn't exist)
- Record import with duplicate detection
- Transaction-based restoration for data integrity
- Detailed restore log with status indicators
- Error handling without stopping entire process

![Partial Restore Interface](C:\Users\CaratRED\Desktop\Restore.png)

### 3. DocType Export

Export only DocType schemas (definitions) without data:

- **Schema-Only Export**: Export just the DocType structure, not the data
- **Multi-select Interface**: Select multiple DocTypes for export
- **App & Module Filtering**: Filter DocTypes by app or module
- **Search Functionality**: Quickly find specific DocTypes
- **Compressed Output**: Generates ZIP files containing DocType definitions

**What's Included in Exports:**
- DocType definitions (complete schema including fields, permissions, etc.)
- DocType metadata (module, custom flag, single flag)
- Export information (creator, date, Frappe version)
- NO data records (use Partial Backup for data export)

**Use Cases:**
- Migrate DocType structures from development to production
- Share custom DocType templates with other installations
- Backup custom DocType configurations
- Transfer data models between sites

### 4. DocType Import

Import DocType schemas from export files:

- **File Upload**: Upload DocType export ZIP files
- **Preview Before Import**: View all DocTypes in the export file
- **Selective Import**: Choose which DocTypes to import
- **Smart Handling**: Creates new DocTypes or updates existing custom DocTypes
- **Safety Features**: Skips standard DocTypes to prevent system issues
- **Detailed Logging**: See exactly what was imported, updated, or skipped

**Import Behavior:**
- Standard DocTypes: Skipped (cannot modify system DocTypes)
- Custom DocTypes (existing): Updated with new definition
- Custom DocTypes (new): Created
- Detailed log showing success/errors/skipped items

**Use Cases:**
- Import DocType structures from other Frappe sites
- Deploy custom DocTypes to production
- Restore DocType configurations from backups
- Share and reuse custom data models

## Installation

### Prerequisites
- Frappe Framework (v13 or higher recommended)
- Bench setup

### Steps

1. Navigate to your Frappe bench directory:
```bash
cd frappe-bench
```

2. Get the app (if not already in apps directory):
```bash
bench get-app data_tools [repository-url]
```

3. Install the app on your site:
```bash
bench --site [site-name] install-app data_tools
```

4. Build assets:
```bash
bench build --app data_tools
```

5. Clear cache and restart:
```bash
bench --site [site-name] clear-cache
bench restart
```

## Usage

### Creating a Partial Backup

1. **Access the Page**
   - Navigate to **Partial Backup** page from the Desk
   - Or search for "Partial Backup" in the Awesome Bar

2. **Filter and Select DocTypes** (Optional)
   - Use the **Module Filter** dropdown to narrow down DocTypes by module
   - Use the **Search** box to find specific DocTypes
   - Select DocTypes using checkboxes

3. **Bulk Selection**
   - Click **Select All** to select all visible DocTypes
   - Click **Deselect All** to clear selections

4. **Create Backup**
   - Click the **Create Backup** button
   - Wait for the backup process to complete
   - The backup file will be automatically downloaded as a ZIP file
   - File naming format: `partial_backup_YYYYMMDD_HHMMSS.zip`

5. **Review Status**
   - Check the status message showing:
     - Number of DocTypes backed up
     - Total records exported

### Restoring from Backup

1. **Access the Page**
   - Navigate to **Partial Restore** page from the Desk
   - Or search for "Partial Restore" in the Awesome Bar

2. **Upload Backup File**
   - Click on the file upload control
   - Select your backup ZIP file
   - Or drag and drop the file

3. **Preview Backup**
   - Review the backup information:
     - Created by (user who created the backup)
     - Creation date
     - Frappe version
     - Total records
   - View the table showing:
     - List of DocTypes
     - Record count for each DocType
     - Total statistics

4. **Restore Data**
   - Click the **Restore Backup** button
   - Confirm the restoration when prompted
   - Wait for the restore process to complete

5. **Review Restore Log**
   - Check the detailed restore log showing:
     - **Success**: DocTypes imported successfully
     - **Errors**: Any DocTypes that failed to restore
     - **Skipped Records**: Existing records that were not overwritten
   - View summary statistics:
     - Total successful restorations
     - Total errors

### Exporting DocType Schemas

1. **Access the Page**
   - Navigate to **DocType Export** page from the Desk
   - Or search for "DocType Export" in the Awesome Bar

2. **Filter and Select DocTypes** (Optional)
   - Use the **App Filter** to filter DocTypes by application
   - Use the **Module Filter** dropdown to filter by module
   - Use the **Search** box to find specific DocTypes
   - Select DocTypes using checkboxes

3. **Export DocTypes**
   - Click the **Export DocTypes** button
   - The export file will be automatically downloaded as a ZIP file
   - File naming format: `doctype_export_YYYYMMDD_HHMMSS.zip`

4. **What Gets Exported**
   - DocType schema/definition only (no data records)
   - DocType fields and their configurations
   - Permissions and roles
   - DocType metadata

### Importing DocType Schemas

1. **Access the Page**
   - Navigate to **DocType Import** page from the Desk
   - Or search for "DocType Import" in the Awesome Bar

2. **Upload Export File**
   - Click on the file upload control
   - Select your DocType export ZIP file
   - The file will be automatically parsed and previewed

3. **Preview Export Contents**
   - Review the export information:
     - Created by (user who created the export)
     - Creation date
     - Frappe version
     - Total DocTypes
   - View the DocType list showing:
     - DocType names
     - Module information
     - Status (Will create/Will update)
     - Custom vs Standard flag

4. **Select DocTypes to Import**
   - All DocTypes are selected by default
   - Deselect any DocTypes you don't want to import
   - Use **Select All** or **Deselect All** buttons for bulk selection

5. **Import DocTypes**
   - Click the **Import Selected DocTypes** button
   - Wait for the import process to complete

6. **Review Import Log**
   - Check the detailed import log showing:
     - **Success**: DocTypes created or updated successfully
     - **Errors**: Any DocTypes that failed to import
     - **Skipped**: Standard DocTypes that were skipped for safety
   - View summary statistics:
     - Total DocTypes processed
     - Successful imports
     - Errors
     - Skipped items

## Technical Details

### Backup Format

**File Structure:**
```
partial_backup_YYYYMMDD_HHMMSS.zip
├── backup_data.json     # Complete backup with DocType definitions and records
└── metadata.json        # Quick metadata for preview
```

**JSON Structure:**
```json
{
  "backup_info": {
    "created_by": "user@example.com",
    "creation_date": "2025-01-15 10:30:00",
    "frappe_version": "15.0.0",
    "total_doctypes": 5,
    "total_records": 150
  },
  "doctypes": [
    {
      "doctype": "Customer",
      "definition": { /* DocType schema */ },
      "records": [ /* Array of documents */ ],
      "record_count": 50
    }
  ]
}
```

### DocType Export Format

**File Structure:**
```
doctype_export_YYYYMMDD_HHMMSS.zip
├── doctype_schemas.json    # DocType definitions only (no data)
└── metadata.json            # Quick metadata for preview
```

**JSON Structure:**
```json
{
  "export_info": {
    "created_by": "user@example.com",
    "creation_date": "2025-11-14 10:30:00",
    "frappe_version": "15.0.0",
    "total_doctypes": 3,
    "export_type": "doctype_schemas_only"
  },
  "doctypes": [
    {
      "doctype": "My Custom DocType",
      "definition": { /* Complete DocType schema */ },
      "module": "Custom Module",
      "is_custom": 1,
      "is_single": 0
    }
  ]
}
```

**Key Differences from Partial Backup:**
- NO data records included
- Smaller file size (only schemas)
- Faster export/import
- Ideal for migrating DocType structures
- Safe to share (no sensitive data)

### Data Handling

**Backup Process:**
- Fetches DocType schema from database
- Exports all records for each selected DocType
- Handles Single DocTypes differently (one document per DocType)
- Compresses data using ZIP deflate algorithm
- Encodes to base64 for download

**Restore Process:**
- Parses ZIP file and extracts JSON data
- Creates missing DocTypes from backup definitions
- Imports records with duplicate checking
- Removes system fields before import (owner, modified_by, creation, modified)
- Uses transactions for data integrity
- Logs all operations for audit trail

### Restore Behavior

| Scenario | Action |
|----------|--------|
| DocType doesn't exist | Creates DocType from backup definition |
| Record already exists | Skips record (no overwrite) |
| Import error occurs | Logs error and continues with next record |
| Critical error | Rolls back transaction for that DocType |

### DocType Import Behavior

| Scenario | Action |
|----------|--------|
| Custom DocType (new) | Creates DocType from definition |
| Custom DocType (exists) | Updates DocType with new definition |
| Standard DocType | Skipped (safety - cannot modify system DocTypes) |
| Import error occurs | Logs error and continues with next DocType |
| Critical error | Rolls back transaction for that DocType |

### Error Handling

- **Logging**: All errors are logged to Error Log
- **Non-blocking**: Errors in one DocType don't stop the entire process
- **Detailed Messages**: User-friendly error messages in restore log
- **Transaction Safety**: Each DocType is restored in its own transaction

## Use Cases

### Partial Backup & Restore
1. **Module Migration**: Move specific modules with data between instances
2. **Data Transfer**: Copy master data to new sites
3. **Testing**: Create test data sets for development
4. **Disaster Recovery**: Backup critical DocTypes regularly
5. **Selective Restore**: Restore only what you need without full database restore
6. **Data Archival**: Create snapshots of specific data for compliance

### DocType Export & Import
1. **Development to Production**: Deploy custom DocTypes from dev to production
2. **Multi-site Deployment**: Share DocType structures across multiple installations
3. **DocType Templates**: Create and share reusable DocType templates
4. **Configuration Backup**: Backup custom DocType configurations
5. **Team Collaboration**: Share data models with team members
6. **Version Control**: Track changes to DocType structures over time

## Permissions

All pages require **System Manager** role by default.

To customize permissions, you can modify the page JSON files:
- `data_tools/data_tools/page/partial_backup/partial_backup.json`
- `data_tools/data_tools/page/partial_restore/partial_restore.json`
- `data_tools/data_tools/page/doctype_export/doctype_export.json`
- `data_tools/data_tools/page/doctype_import/doctype_import.json`

## Best Practices

### For Partial Backup & Restore
1. **Regular Backups**: Schedule regular backups of critical DocTypes
2. **Test Restores**: Verify backups by testing restore on a development instance
3. **Version Compatibility**: Ensure Frappe versions match between backup and restore sites
4. **Storage**: Store backup files in a secure, backed-up location
5. **Documentation**: Keep track of what's in each backup file
6. **Validation**: Always review the preview before restoring

### For DocType Export & Import
1. **Test First**: Always test imports on a development site first
2. **Custom Only**: Only export/import custom DocTypes when possible
3. **Document Changes**: Keep track of what DocTypes you're deploying
4. **Version Control**: Store export files in version control for tracking
5. **Review Before Import**: Always review the preview before importing
6. **Backup First**: Create a backup before importing DocTypes to production

## Troubleshooting

### Common Issues

**Issue: Backup file download fails**
- Check browser console for errors
- Verify disk space available
- Check server error logs

**Issue: Restore fails for specific DocTypes**
- Check Error Log for detailed errors
- Verify DocType compatibility with target site
- Ensure no permission restrictions

**Issue: Records show as "Skipped"**
- This is normal behavior for existing records
- Records are identified by their `name` field
- Backup does not overwrite existing data

## Development

### File Structure
```
data_tools/
├── data_tools/
│   ├── data_tools/
│   │   └── page/
│   │       ├── partial_backup/
│   │       │   ├── partial_backup.py      # Backend logic for backup
│   │       │   ├── partial_backup.js      # Frontend interface
│   │       │   └── partial_backup.json    # Page definition
│   │       └── partial_restore/
│   │           ├── partial_restore.py     # Backend logic for restore
│   │           ├── partial_restore.js     # Frontend interface
│   │           └── partial_restore.json   # Page definition
│   └── hooks.py                           # App configuration
└── README.md
```

### API Methods

**Backup Methods:**
- `get_all_doctypes()` - Fetch all available DocTypes
- `get_modules()` - Fetch unique modules for filtering
- `create_partial_backup(doctypes)` - Create backup ZIP file

**Restore Methods:**
- `parse_backup_file(file_data, filename)` - Parse and preview backup
- `restore_backup(file_data, filename, selected_doctypes)` - Restore data

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues, questions, or feature requests:
- Create an issue in the repository
- Contact the maintainer at admin@example.com

## License

MIT License

Copyright (c) 2025 Admin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Changelog

### Version 1.1.0
- **NEW**: DocType Export - Export only DocType schemas without data
- **NEW**: DocType Import - Import DocType schemas with preview and selective import
- Enhanced app filtering for all pages
- Improved documentation and usage guides
- Safety features for standard DocType protection

### Version 1.0.0
- Initial release
- Partial Backup functionality
- Partial Restore functionality
- Module filtering
- Search functionality
- Detailed restore logging

---

**Built with Frappe Framework**
