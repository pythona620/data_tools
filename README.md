# Data Tools

A comprehensive Frappe app for creating partial backups and restoring specific DocTypes. This tool allows you to selectively backup and restore data without affecting the entire database.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Data Tools provides a flexible and user-friendly interface for managing partial backups in Frappe applications. Whether you need to migrate specific modules, backup critical data, or restore selective DocTypes, this app streamlines the entire process.

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

### Error Handling

- **Logging**: All errors are logged to Error Log
- **Non-blocking**: Errors in one DocType don't stop the entire process
- **Detailed Messages**: User-friendly error messages in restore log
- **Transaction Safety**: Each DocType is restored in its own transaction

## Use Cases

1. **Module Migration**: Move specific modules between instances
2. **Data Transfer**: Copy master data to new sites
3. **Testing**: Create test data sets for development
4. **Disaster Recovery**: Backup critical DocTypes regularly
5. **Selective Restore**: Restore only what you need without full database restore
6. **Data Archival**: Create snapshots of specific data for compliance

## Permissions

Both Partial Backup and Partial Restore pages require **System Manager** role by default.

To customize permissions, you can modify the page JSON files:
- `data_tools/data_tools/page/partial_backup/partial_backup.json`
- `data_tools/data_tools/page/partial_restore/partial_restore.json`

## Best Practices

1. **Regular Backups**: Schedule regular backups of critical DocTypes
2. **Test Restores**: Verify backups by testing restore on a development instance
3. **Version Compatibility**: Ensure Frappe versions match between backup and restore sites
4. **Storage**: Store backup files in a secure, backed-up location
5. **Documentation**: Keep track of what's in each backup file
6. **Validation**: Always review the preview before restoring

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

### Version 1.0.0
- Initial release
- Partial Backup functionality
- Partial Restore functionality
- Module filtering
- Search functionality
- Detailed restore logging

---

**Built with Frappe Framework**
