# IAR migration scripts

This repository contains scripts to migrate the existing IAR spreadsheet
semi-automatically to the new backend.

## Installation

```console
$ pip install -r requirements.txt
```

## Migration

The ``migrate.py`` script takes a CSV export from the spreadsheet and writes a
series of YAML documents to an output. The documents correspond to migrated
assets and a migration report.

Run via:

```console
$ ./migrate.py --output=assets.yaml input.csv
```

This must be run on a machine within the CUDN since it uses Lookup to attempt to
reconcile the free-form "department" field with a Lookup instid. Any fields
which cannot be reconciled are left blank.

Each asset migration document has the following form:

```yaml
type: asset
asset:
  id: string # Generated UUID
  department: string
  name: string
  personal_data: boolean
  private: boolean
  purpose: string
  risk_type: list of strings
errors: # optional can have zero or more of the following errors
- code: E001
  message: Department could not be resolved
original:
  # extracted original fields from the CSV. Preserved to aid manual
  # reconciliation
```

The migration report document has the following form:

```yaml
type: report
original_dept_mapping:
  # List of instid/original mappings giving the orignal input in the spreadsheet
  # and the inferred lookup instid. Mappings which could not be inferred have
  # an instid of null.
- original: Biochemistry
  instid: BIOCH
  # ...
```

## Uploading

Once the asset documents are prepared, they may be uploaded *en mass* via the
``upload.py`` script:

```console
$ ./upload.py --output=upload-report.yaml assets.yaml
```

The upload script generates a file with one YAML document per upload of the
following form:

```yaml
type: upload
status_code: integer # HTTP status code of response
source_id: string # id of asset from input assets file
dest_id: string # on success, assigned if of asset from IAR backend
error: object # on error, body of response from server
```
