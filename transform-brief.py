#!/usr/bin/env python3
# Last Modified: 2016.11.17 /coding: utf-8
# Copyright: © 2016 Landon Bouma.
#  vim:tw=0:ts=4:sw=4:noet

# Should already be installed:
#  sudo apt-get install -y python-pycurl python3-pycurl

# Consume output of, e.g.,
#  ./hamster_briefs.sh -2 -E

import os
import sys

#import json
import re

# C [code] H[uman] JSON
#  https://github.com/landonb/chjson
import chjson

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

		#print(json.dumps(self.entries, sort_keys=True, indent=4))
		print(chjson.encode(self.entries, sort_keys=True, indent=4))

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
			#self.entries = json.loads(briefs_f.read())
			self.entries = chjson.decode(briefs_f.read())

		# Do 2 passes, so in case we cannot parse something or otherwise
		# fail, we won't have sent any POST requests to JIRA.
		forreal = False
		self.errs = []
		self.update_entries(forreal)
		if not self.errs:
			forreal = True
			self.update_entries(forreal)
		else:
			print("ERROR: Found %d error(s)." % (len(self.errs),))
			for err in self.errs:
				print(err)
			sys.exit(1)

	def output_header_tempo(self, forreal):
		print('#########################################################################')
		if not forreal:
			print('PASS 1/2 Checking JSON')
		else:
			print('PASS 2/2 Tickling TEMPO')
		print('#########################################################################')

	def update_entries(self, forreal):
		self.output_header_tempo(forreal)

		#print(self.entries)
		##print(json.dumps(self.entries, sort_keys=True, indent=4))
		#print(chjson.encode(self.entries, sort_keys=True, indent=4))

		proj_id_parser = re.compile(r'.* \[(\d+):(\d+):([-a-zA-Z0-9]+)\]\w*')

		total_secs = 0

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
			# a tag should contain the item_key. Format is:
			#   exo__CLIENT-TICKETNUMBER__JIRAKEYID
			if entry['tags']:
				# The user can use more than one tag, which hamster, er,
				# sqlite3 (hamster_briefs) combines with commas.
				tags = entry['tags'].split(',')
				for tag in tags:
					try:
						prefix, item_key, item_id = tag.split('__')
						#prefix, item_key, proj_id = tag.split('__')
					except ValueError as err:
						# Not an encoded tag; ignore.
						pass

			curr_entry = {
				"dateStarted": "%sT00:00:00.000+0000" % (entry['year_month_day'],),
				"timeSpentSeconds": "%d" % (int(60 * 60 * entry['time_spent']),),
				"comment": "\n\n".join(entry['desctimes']),
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
				#json.dumps(curr_entry)
				chjson.encode(curr_entry)
				#print(curr_entry)
				print("Entry: date: %s / time: %s" % (
					curr_entry['dateStarted'],
					curr_entry['timeSpentSeconds'],
				))
				total_secs += int(curr_entry['timeSpentSeconds'])
			else:
				print('POST: Key: %s / Date: %s / Time: %s' % (
					curr_entry['issue']['key'],
					curr_entry['dateStarted'],
					curr_entry['timeSpentSeconds'],
				))
				print(curr_entry)
				req = requests.post(
					self.cli_opts.tempo_url + '/rest/tempo-timesheets/3/worklogs',
					auth=(self.cli_opts.username, self.cli_opts.password),
					#data=json.dumps(curr_entry),
					data=chjson.encode(curr_entry),
					headers=headers,
				)
				# req.text/req.content is the server response, which
				# on 200 OK is the full JSON on the new worklog entry.
				# Note that req.ok when (req.status_code == 200).
				if not req.ok:
					print(
						'ERROR: Tempo error: status_code: %s / text: %s'
						% (req.status_code, req.text,)
					)
					#import pdb;pdb.set_trace()
					pass
					sys.exit(1)

		if not forreal:
			print('-------------------------------------------------------------------------')
			print(
				"update_entries: total_secs: %s / total_hrs: %.2f"
				% (total_secs, total_secs / 60.0 / 60.0,)
			)
		else:
			print('-------------------------------------------------------------------------')
			print('Success!')
			print()
			# FIXME: Can/Should we automate submit-for-approval?
			print("REMEMBER: Logon and submit your timesheet.")
			# FIXME: Encode 'period' so the correct week is displayed.
			#  https://i.exosite.com/jira/secure/TempoUserBoard!timesheet.jspa?period=07112016
			print("  %s/secure/TempoUserBoard!timesheet.jspa" % (self.cli_opts.tempo_url,))
			print()

if (__name__ == '__main__'):
	hr = Transformer()
	hr.go()

