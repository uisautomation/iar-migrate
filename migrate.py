#!/usr/bin/env python
"""
Migrate old IAR spreadsheet to new format

Usage:
    migrate.py (-h | --help)
    migrate.py [--verbose] [--skip-rows=NUM] [--skip-cols=NUM] [--output=FILE]
        [--fixups=FILE] [<csv>]

Options:

    --verbose, -v           Increase output verbosity.

    --output=FILE           Output YAML dump file. Use "-" for standard input [default: -]
    <csv>                   Input CSV. Use "-" for standard output. [default: -]

    --skip-rows=NUM         Number of rows to skip in input CSV. [default: 6]
    --skip-cols=NUM         Number of initial columns to skip in input CSV. [default: 1]

    --fixups=FILE           Load fixups from file

"""
import csv
import logging
import sys
import uuid

import docopt
import yaml
import ucamlookup.ibisclient as ibisclient


LOG = logging.getLogger()

MIGRATION_NS = uuid.UUID('d04a3354-2935-4247-b7c7-f9c505bb8634')


class Context:
    def __init__(self, cli_opts):
        self._ibis_conn = ibisclient.createConnection()
        self._cached_insts = {}

        self.cli_opts = cli_opts
        self.departments = set()
        self.fixups = {
            'institutions': []
        }

    def resolve_institution(self, inst_name):
        for record in self.fixups['institutions']:
            if record['original'] == inst_name:
                return record['instid']

        if inst_name in self._cached_insts:
            return self._cached_insts[inst_name]

        # Hunt for institution
        im = ibisclient.InstitutionMethods(self._ibis_conn)
        self._cached_insts[inst_name] = None

        # Look for foo, Department of foo and Faculty of foo from a simple entry of "foo". An exact
        # match always wins. A single approximate match wins.
        for prefix in ['', 'Department of ', 'Faculty of ']:
            search = prefix + inst_name
            matches = im.search(search, approxMatches=True)

            # Look for exact matches
            exact_matches = [inst for inst in matches if inst.name == search]

            # An exact match succeeds
            if len(exact_matches) == 1:
                self._cached_insts[inst_name] = exact_matches[0].instid
                break

            # If there is not exactly one approximate match, give up
            if len(matches) != 1:
                continue

            # Found one, done!
            self._cached_insts[inst_name] = matches[0].instid
            break

        return self._cached_insts[inst_name]


def main():
    opts = docopt.docopt(__doc__)
    logging.basicConfig(level=logging.INFO if opts['--verbose'] else logging.WARN)

    context = Context(cli_opts=opts)

    if opts['--fixups'] is not None:
        with open_from_opt(opts['--fixups']) as fixups:
            context.fixups.update(yaml.load(fixups))

    with open_from_opt(opts['<csv>']) as infile, open_from_opt(opts['--output'], 'w') as outfile:
        in_reader = csv.reader(infile)
        for _ in range(int(opts['--skip-rows'])):
            next(in_reader)
        yaml.dump_all(migrate_rows(in_reader, context), outfile, default_flow_style=False)


def extract_row(row, context):
    """Given a row from the CSV, extract the named fields we care about."""
    # Skip any initial columns
    row = row[int(context.cli_opts['--skip-cols']):]
    return {
        'faculty_dept_inst': row[1],
        'name': row[8],
        'purpose': row[9],
        'application': row[10],
        'owners': row[11],
        'availability_impact': row[12],
        'confidentiality_impact': row[13],
        'integrity_impact': row[14],
        'personal_data': row[15:20],
        'animal': row[22],
        'animal_s24': row[23],
        'recipients': row[29],
        'within_eea': row[32],
        'where_stored': row[35],
        'password_or_locked': row[36],
        'encryption_or_doubled_locked': row[37],
        'retention': row[38],
        'backup': row[42],
        'backup_off_site': row[46],
        'backup_off_site_regime': row[48],
        'backup_off_site_location': row[49],
    }


def to_bool(text):
    """Heuristically map a free-form text to boolean or None if we cannot."""
    text = text.lower()
    if text == 'y' or text == 'yes':
        return True

    if text == 'n' or text == 'no':
        return False

    return None


def migrate_rows(rows, context):
    for index, row in enumerate(rows):
        yield migrate_row(index, row, context)

    yield {
        'type': 'report',
        'original_dept_mapping': [
            {'original': dept, 'instid': context.resolve_institution(dept)}
            for dept in sorted(list(context.departments))
        ],
    }


def migrate_row(index, row, context):
    """Migrate an individual spreadsheet row."""

    # Extract original columns we care about
    original = extract_row(row, context)
    context.departments.add(original['faculty_dept_inst'])

    asset_id = str(uuid.uuid5(
        MIGRATION_NS, original['name'] if original['name'] != '' else str(index)))

    risks = []
    if original['availability_impact'] != '':
        risks.append('operational')
    if original['confidentiality_impact'] != '':
        risks.append('reputational')
    if original['integrity_impact'] != '':
        risks.append('financial')

    # Perform easy migration to initialise asset
    asset = {
        'id': asset_id,
        'name': original['name'], 'purpose': original['purpose'],
        'department': context.resolve_institution(original['faculty_dept_inst']),
        'personal_data': any([to_bool(v) for v in original['personal_data']]),
        'private': any([to_bool(v) for v in [original['animal'], original['animal_s24']]]),
        'risk_type': risks,
    }

    errors = []
    if asset['department'] is None:
        errors.append({'code': 'E001', 'message': 'Department could not be resolved'})

    return_val = {'type': 'asset', 'asset': asset, 'original': original}
    if len(errors) > 0:
        return_val['errors'] = errors

    return return_val


def open_from_opt(opt, mode='r'):
    """Open a file given an option value."""
    if opt is None or opt == '-':
        return sys.stdout if 'w' in mode else sys.stdin
    return open(opt, mode)


if __name__ == '__main__':
    main()
