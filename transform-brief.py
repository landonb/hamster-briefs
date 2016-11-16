#!/usr/bin/env python3
# Last Modified: 2016.11.15 /coding: utf-8
# Copyright: © 2016 Landon Bouma.
#  vim:tw=0:ts=4:sw=4:noet

# Should already be installed:
#  sudo apt-get install -y python-pycurl python3-pycurl

# Consume output of, e.g.,
#  ./hamster_briefs.sh -2 -E

import os
import sys

import json
import re

# Requests refs:
#  http://docs.python-requests.org/en/master/
import requests

sys.path.append('%s/lib' % (os.path.abspath(sys.path[0]),))
from lib import argparse_wrap

import logging
from lib import logging2
logging2.init_logging(logging.DEBUG, log_to_console=True)
log = logging.getLogger('transform-brief')

SCRIPT_DESC = 'Hamster Brief Transformation Tool'
SCRIPT_VERS = '0.1a'

class TxTl_Argparser(argparse_wrap.ArgumentParser_Wrap):

	def __init__(self):
		argparse_wrap.ArgumentParser_Wrap.__init__(self,
			description=SCRIPT_DESC,
			script_name=None,
			script_version=SCRIPT_VERS,
			usage=None)

	def prepare(self):
		argparse_wrap.ArgumentParser_Wrap.prepare(self)

		self.add_argument(metavar='briefs-file',
			type=str, dest='briefs_file',
			help="a file created by ./hamster_briefs -E",
		)

		self.add_argument('-r', '--read-brief', dest='read_hamster_brief',
			action='store_true', default=False,
		)

		self.add_argument('-T', '--tempo-url', dest='tempo_url',
			type=str,
		)

		self.add_argument('-u', '--user', dest='username',
			type=str, help="username",
		)

		self.add_argument('-p', '--pass', dest='password',
			type=str, help="password",
		)

	def verify(self):
		ok = argparse_wrap.ArgumentParser_Wrap.verify(self)

		return ok

class Transformer(argparse_wrap.Simple_Script_Base):

	def __init__(self, argparser=TxTl_Argparser):
		argparse_wrap.Simple_Script_Base.__init__(self, argparser)

	def go_main(self):
		log.debug('go_main: cli_opts: %s' % (self.cli_opts,))

		if self.cli_opts.tempo_url:
			self.upload_to_tempo()
		elif self.cli_opts.read_hamster_brief:
			self.read_briefs()
		else:
			print("Good job!")

	def read_briefs(self):
		self.entries = []
		with open(self.cli_opts.briefs_file, 'r') as briefs_f:
			for line in briefs_f:
				line = line.strip()
				if line:
					self.read_brief_line(line)

		print(json.dumps(self.entries, sort_keys=True, indent=4))

	def read_brief_line(self, line):
		try:
			(
			year_month_day,
			time_spent,
			category,
			activity_name,
			activity_id,
			tags,
			desc_time_tuples,
			) = line.split("|", 6)
		except Exception as err:
			log.fatal('read_briefs: invalid line: %s' % (line,))
			# YOU deal with this.
			#import pdb;pdb.set_trace()
			raise

		# The descriptions and times are comma-separated two-ples.
		desc_time_tuples = desc_time_tuples.strip('"')
		dnts = desc_time_tuples.split('","')
		assert((len(dnts) % 2) == 0)
		desctimes = []
		idx = 0
		while idx < (len(dnts) / 2):
			ridx = idx * 2
			desctimes.append("%s [%s]" % (dnts[ridx], round(float(dnts[ridx + 1]), 3),))
			idx += 1

		new_entry = {
			"year_month_day": year_month_day,
			"time_spent": round(float(time_spent), 3),
			"category": category,
			"activity_name": activity_name,
			"activity_id": activity_id,
			"tags": tags,
			"desctimes": desctimes,
		}
		self.entries.append(new_entry)

	def upload_to_tempo(self):

		self.entries = []
		with open(self.cli_opts.briefs_file, 'r') as briefs_f:
			self.entries = json.loads(briefs_f.read())

		# Do 2 passes, so in case we cannot parse something or otherwise
		# fail, we won't have sent any POST requests to JIRA.
		forreal = False
		self.errs = []
		self.update_entries(forreal)
		if not self.errs:
			forreal = True
# FIXME: Test this first.
#			self.update_entries(forreal)
		else:
			print("ERROR: Found %d error(s)." % (len(self.errs),))
			for err in self.errs:
				print(err)
			sys.exit(1)

	def update_entries(self, forreal):
		#print(self.entries)
		#print(json.dumps(self.entries, sort_keys=True, indent=4))

		proj_id_parser = re.compile(r'.* \[(\d+):(\d+):([-a-zA-Z0-9]+)\]\w*')

		for entry in self.entries:

			# The project ID and item key are encoded in the Activity name.
			mat = proj_id_parser.match(entry['activity_name'])
			tup = mat.groups() if mat else None
			if not tup:
				self.errs.append("ERROR: Activity name missing JIRA IDs: %s" % (entry['activity_name'],))
				continue
			try:
				proj_id, item_id, item_key = tup
			except ValueError as err:
				self.errs.append(
					"ERROR: Failed to parse JIRA IDs [proj:item:key] in activity name: %s"
					% (entry['activity_name'],)
				)
				continue

			# For client-level Activities (sans ticket numbers),
			# a tag should contain the item_key.
			if entry['tags']:
				tags = ','.split(entry['tags'])
				for tag in tags:
					try:
						prefix, item_key, item_id = '__'.split(tag)
					except ValueError as err:
						# Not an encoded tag; ignore.
						pass

			curr_entry = {
				"dateStarted": "%sT00:00:00.000+0000" % (entry['year_month_day'],),
				"timeSpentSeconds": "%d" % (int(60 * 60 * entry['time_spent']),),
				"comment": "\\n\\n".join(entry['desctimes']),
				"issue": {
					"projectId": proj_id,
					"key": item_key,
					# Not needed:
					#item_id
				},
				"author": {
					"name": self.cli_opts.username,
				},
			}


			headers = {'content-type': 'application/json',}
			if not forreal:
				json.dumps(curr_entry)
			else:
				print(curr_entry)
#
				continue
				req = requests.post(
					self.cli_opts.tempo_url + '/rest/tempo-timesheets/3/worklogs',
					auth=(self.cli_opts.username, self.cli_opts.password),
					data=json.dumps(curr_entry),
					headers=headers,
				)

# FIXME: TRY Just 1 for now.
#			sys.exit(0)


if (__name__ == '__main__'):
	hr = Transformer()
	hr.go()

