#!/usr/bin/env python
"""
Put migrated assets to server.

Usage:
    upload.py (-h | --help)
    upload.py [--verbose] [--token=TOKEN] [--output=FILE] <endpoint> <document>...

Options:

    --verbose, -v           Increase output verbosity.

    --token=TOKEN           Bearer token to use for authoirisation.

    --output=FILE           Output upload report.
    <endpoint>              IAR endpoint.
    <document>              YAML document(s) containing asset records.

"""
import logging
import sys

import docopt
import yaml
import requests


LOG = logging.getLogger()


def main():
    opts = docopt.docopt(__doc__)
    logging.basicConfig(level=logging.INFO if opts['--verbose'] else logging.WARN)

    session = requests.Session()
    if opts['--token']:
        session.headers.update({'Authorization': 'Bearer ' + opts['--token']})

    endpoint = opts['<endpoint>']

    # Generator for loading all the input asset documents
    def load_docs():
        for docfile in opts['<document>']:
            LOG.info('Loading %s...', docfile)
            with open(docfile) as infile:
                for doc in yaml.load_all(infile):
                    if 'type' not in doc or doc['type'] != 'asset':
                        continue
                    yield doc

    with open_from_opt(opts['--output'], 'w') as outfile:
        yaml.dump_all(
            process_documents(session, endpoint, load_docs()), outfile, default_flow_style=False)


def process_documents(session, endpoint, docs):
    """Process an individual asset document."""
    for doc in docs:
        asset = doc['asset']
        report = {'source_id': asset['id'], 'type': 'upload'}
        r = session.post(endpoint, json=asset)
        report['status_code'] = r.status_code

        try:
            r.raise_for_status()
        except requests.HTTPError:
            LOG.error('Saving asset failed: %s', r.json())
            LOG.error('Original asset: %s', asset)
            report['error'] = r.json()
            yield report
            continue

        response = r.json()
        LOG.info('Saved asset: %s as %s', asset['id'], response['id'])
        report['dest_id'] = response['id']
        yield report


def open_from_opt(opt, mode='r'):
    """Open a file given an option value."""
    if opt is None or opt == '-':
        return sys.stdout if 'w' in mode else sys.stdin
    return open(opt, mode)


if __name__ == '__main__':
    main()
