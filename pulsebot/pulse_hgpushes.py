# encoding: utf-8
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import unicode_literals

import logging
import requests
import traceback
import unittest
from collections import OrderedDict
from pulse import PulseListener


class PulseHgPushes(PulseListener):
    def __init__(self, config):
        super(PulseHgPushes, self).__init__(
            config.pulse.user,
            config.pulse.password,
            'exchange/hgpushes/v1',
            '#',
            config.pulse.applabel
            if config.parser.has_option('pulse', 'applabel') else None
        )

    def __iter__(self):
        for message in super(PulseHgPushes, self).__iter__():
            for push in self.get_pushes_info(message):
                yield push

    @staticmethod
    def get_pushes_info(pulse_message):
        # Sanity checks
        try:
            payload = pulse_message.get('payload', {})
            repo = payload.get('repo_url')
            pushes = payload.get('pushlog_pushes')
            if not (repo and pushes):
                return
        except Exception:
            return

        for push in pushes:
            push_url = push.get('push_full_json_url')
            if not push_url:
                continue

            try:
                r = requests.get(push_url)
                if r.status_code == 500:
                    # If we got an error 500, try again once.
                    r = requests.get(push_url)
                if r.status_code != 200:
                    r.raise_for_status()

                data = r.json(object_pairs_hook=OrderedDict)

                for id, d in data.get('pushes', {}).iteritems():
                    id = int(id)
                    push_data = {
                        'pushlog': '%s/pushloghtml?startID=%d&endID=%d'
                        % (repo, id - 1, id),
                        'changesets': [],
                    }

                    for cs in d.get('changesets', ()):
                        short_node = cs['node'][:12]
                        revlink = '%s/rev/%s' \
                            % (repo, short_node)

                        push_data['changesets'].append({
                            'revlink': revlink,
                            'desc': cs['desc'].splitlines()[0].strip(),
                            'author': cs['author'].split(' <')[0].strip(),
                        })

                    yield push_data

            except:
                logger = logging.getLogger('pulsebot.hgpushes')
                logger.error("Failure on %s", push_url)
                for line in traceback.format_exc().splitlines():
                    logger.debug(line)
                logger.debug("Message data was: %r", pulse_message)
                continue


class TestPushesInfo(unittest.TestCase):
    def test_pushes_info(self):
        # Not ideal: this relies on actual live data.
        results = [{
            'pushlog':
                'https://hg.mozilla.org/integration//mozilla-inbound/'
                'pushloghtml?startID=5&endID=6',
            'changesets': [{
                'author': 'Rafael Ávila de Espíndola',
                'revlink':
                    'https://hg.mozilla.org/integration//mozilla-inbound/'
                    'rev/685f5ae6e7de',
                'desc':
                    'Bug 657653. Check for libstdc++ versions in '
                    'stdc++compat.cpp; r=ted,glandium',
            }],
        }, {
            'pushlog':
                'https://hg.mozilla.org/integration//mozilla-inbound/'
                'pushloghtml?startID=6&endID=7',
            'changesets': [{
                'author': "Robert O'Callahan",
                'revlink':
                    'https://hg.mozilla.org/integration//mozilla-inbound/'
                    'rev/63c8f645cc1c',
                'desc':
                    'Bug 661471. Part 6.1: Expose '
                    'cairo_win32_get_system_text_quality. r=jfkthame',
            }, {
                'author': "Robert O'Callahan",
                'revlink':
                    'https://hg.mozilla.org/integration//mozilla-inbound/'
                    'rev/3eb99af46b93',
                'desc':
                    'Bug 661471. Part 6.2: Handle dynamic changes to '
                    'Cleartype enabled/disabled. r=jfkthame',
            }, {
                'author': 'Jonathan Kew',
                'revlink':
                    'https://hg.mozilla.org/integration//mozilla-inbound/'
                    'rev/1ccc676a3a2c',
                'desc':
                    'Bug 661471. Part 6.3: Ensure that force_gdi_classic '
                    "doesn't make us use ClearType when ClearType is "
                    'disabled. r=roc',
            }, {
                'author': 'Jonathan Kew',
                'revlink':
                    'https://hg.mozilla.org/integration//mozilla-inbound/'
                    'rev/5607cca3f7bf',
                'desc':
                    'Bug 661471. Part 7: Let gfxDWriteFonts know whether '
                    "we are honouring 'GDI classic' overrides. r=roc",
            }],
        }]

        message = {'payload': {
            'repo_url':
                'https://hg.mozilla.org/integration//mozilla-inbound',
            'pushlog_pushes': [
                {'push_full_json_url':
                    'https://hg.mozilla.org/integration/mozilla-inbound/'
                    'json-pushes?version=2&full=1&startID=6&endID=7'},
            ],
        }}

        pushes = list(PulseHgPushes.get_pushes_info(message))

        self.maxDiff = None
        self.assertEquals(pushes, [results[1]])

        message = {'payload': {
            'repo_url':
                'https://hg.mozilla.org/integration//mozilla-inbound',
            'pushlog_pushes': [
                {'push_full_json_url':
                    'https://hg.mozilla.org/integration/mozilla-inbound/'
                    'json-pushes?version=2&full=1&startID=5&endID=6'},
                {'push_full_json_url':
                    'https://hg.mozilla.org/integration/mozilla-inbound/'
                    'json-pushes?version=2&full=1&startID=6&endID=7'},
            ],
        }}

        pushes = list(PulseHgPushes.get_pushes_info(message))

        self.assertEquals(pushes, results)

        message = {'payload': {
            'repo_url':
                'https://hg.mozilla.org/integration//mozilla-inbound',
            'pushlog_pushes': [
                {'push_full_json_url':
                    'https://hg.mozilla.org/integration/mozilla-inbound/'
                    'json-pushes?version=2&full=1&startID=5&endID=7'},
            ],
        }}

        pushes = list(PulseHgPushes.get_pushes_info(message))

        self.maxDiff = None
        self.assertEquals(pushes, results)