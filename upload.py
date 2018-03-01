#!/usr/bin/env python
"""
Put migrated assets to server.

Usage:
    upload.py (-h | --help)
    upload.py [--verbose] [--token=TOKEN] [--previous-report=FILE] [--output=FILE]
        <endpoint> <document>...

Options:

    --verbose, -v           Increase output verbosity.

    --token=TOKEN           Bearer token to use for authoirisation.

    --output=FILE           Output upload report.
    --previous-report=FILE  Previous upload report. Used to find existing assets.

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
    if not endpoint.endswith('/'):
        raise RuntimeError('Endpoint should have terminating slash')

    # Mapping from source id to dest id if an existing upload happened
    id_map = {}

    previous_report = opts['--previous-report']
    if previous_report is not None:
        with open(previous_report) as infile:
            for doc in yaml.load_all(infile):
                if 'type' not in doc or doc['type'] != 'upload':
                    continue
                id_map[doc['source_id']] = doc['dest_id']

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
            process_documents(session, endpoint, load_docs(), id_map),
            outfile, default_flow_style=False
        )


def process_documents(session, endpoint, docs, id_map):
    """Process an individual asset document."""
    for doc in docs:
        original_asset = doc['asset']

        if original_asset['name'] == '' or original_asset['name'] is None:
            LOG.warn('Skipping asset {} with empty name'.format(original_asset['id']))

        asset = {}
        asset.update(original_asset)
        del asset['id']  # since it is going to be different
        report = {'source_id': original_asset['id'], 'type': 'upload'}

        dest_id = id_map.get(original_asset['id'])

        already_exists = dest_id is not None
        if already_exists:
            url = endpoint + dest_id + '/'
            r = session.get(url)
            if r.status_code == 404:
                already_exists = False
                LOG.warn('asset {} not found (original id {})'.format(
                    dest_id, original_asset['id']))

        if already_exists:
            report['method'] = 'PUT'
            report['url'] = url
            r = session.put(url, json=asset)
        else:
            report['method'] = 'POST'
            r = session.post(endpoint, json=asset)

        try:
            r.raise_for_status()
        except requests.HTTPError:
            LOG.error('Saving asset failed: %s', r.content)
            LOG.error('Original asset: %s', asset)
            report['error'] = r.content
            yield report
            continue

        response = r.json()
        LOG.info('Saved asset: %s as %s', original_asset['id'], response['id'])
        report['dest_id'] = response['id']
        yield report


def open_from_opt(opt, mode='r'):
    """Open a file given an option value."""
    if opt is None or opt == '-':
        return sys.stdout if 'w' in mode else sys.stdin
    return open(opt, mode)


if __name__ == '__main__':
    main()
