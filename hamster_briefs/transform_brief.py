#!/usr/bin/env python3
# Last Modified: 2017.08.01 /coding: utf-8
# Copyright: © 2016-2017 Landon Bouma.
#  vim:tw=0:ts=4:sw=4:noet

# FIXME/2016-11-18: Rename this file to reflect that it's really tempo-specific?
#
# FIXME/2016-10-10: New feature to skip comments after EOF or RAMBLING
#                   (make new switch).
#
# FIXME/2016-10-10: hamster-briefs.py: Fix multi-word -a option.
#                   Doesn't work: time-exo.sh -2 -r all -a "Genie - Billable"

# Prerequisites
# -------------
#
# Often already be installed:
#   sudo apt-get install -y python-pycurl python3-pycurl

# Usage
# -----

# Generate a report from Hamster-briefs:
#
#   ./hamster-briefs.sh -2 -E > last_weeks_time.raw
#
# Convert the report to HJSON that you can edit
# and comment (and store for posterity).
#
#   ./transform-brief.py -r last_weeks_time.raw > last_weeks_time.json
#
# Lob your curated timesheet at the Tempo API.
#
#   ./transform-brief.py \
#       -T "https://path.to/jira" \
#       -u "USERNAME" \
#       -p "PASSWORD" \
#       last_weeks_time.json

# Refs
# ----
#
# You can find the relatively simple JIRA Tempo API at tempo.io:
#
#   http://tempo.io/doc/core/api/rest/latest/
#
#   http://tempo.io/doc/timesheets/api/rest/latest/#848933329
#
# The call is basically GET and POST to
#
#   http://{JIRA_BASE_URL}/rest/tempo-timesheets/3/worklogs
#
# and you can also deal with approvals via
#
#   http://{JIRA_BASE_URL}/rest/tempo-timesheets/3/timesheet-approval/
#
# but we're just pushing time.
#
# We don't need to get anything, or to approve anything.

# Manually testing Tempo
# ----------------------
#
#    curl https://path.to/jira/rest/tempo-timesheets/3/worklogs \
#        -D- -u USERNAME:PASSWORD \
#        -H "Content-Type: application/json; charset=UTF-8" \
#        -X POST \
#        -d '{
#              "dateStarted": "2016-10-24T00:00:00.000+0000",
#              "timeSpentSeconds": "3600",
#              "comment": "Tempo Training. \n\nTesting newlines in comment.",
#              "issue": {
#                "projectId": "12310",
#                "key": "INT-7"
#              },
#              "author": {
#                "name": "yourname"
#              }
#            }'

import os
import sys

import datetime
import re

import json
try:
	# C [code] H[uman] JSON
	#  https://github.com/landonb/chjson
	import chjson
	json_encode = chjson.encode
	json_decode = chjson.decode
except ImportError:
	json_encode = json.dumps
	json_decode = json.loads

# Requests refs:
#  http://docs.python-requests.org/en/master/
import requests

import pyoiler_argparse

import logging
import pyoiler_logging
pyoiler_logging.init_logging(logging.DEBUG, log_to_console=True)
log = logging.getLogger('transform-brief')

SCRIPT_DESC = 'Hamster Brief Transformation Tool'
#SCRIPT_VERS = '0.1a'
import hamster_briefs.version_hamster

# 2016-11-17: This script is a little green, and there's nothing
# coded to quickly remove rogue entries, so ask user if the input
# exceeds this many entries.
#NUM_ENTRIES_LIMIT_ASK = 20
# 2017-08-01: This should be relaxed... I often have way more...
NUM_ENTRIES_LIMIT_ASK = 50

class TxTl_Argparser(pyoiler_argparse.ArgumentParser_Wrap):

	def __init__(self):
		pyoiler_argparse.ArgumentParser_Wrap.__init__(self,
			description=SCRIPT_DESC,
			script_name=None,
			script_version=hamster_briefs.version_hamster.SCRIPT_VERS,
			usage=None)

	def prepare(self):
		pyoiler_argparse.ArgumentParser_Wrap.prepare(self)

		self.add_argument(metavar='briefs-file',
			type=str, dest='briefs_file',
			help="a file created by ./hamster-briefs -E",
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

		self.add_argument('--delimiter', dest='comment_delimiter', type=str,
			# 2016-12-20: Using newlines makes the Tempo content on an
			#   individual ticket really long.
			#default="\n\n",
			default=" / ",
		)

	def verify(self):
		ok = pyoiler_argparse.ArgumentParser_Wrap.verify(self)

		return ok

class Transformer(pyoiler_argparse.Simple_Script_Base):

	def __init__(self, argparser=TxTl_Argparser):
		pyoiler_argparse.Simple_Script_Base.__init__(self, argparser)

	def go_main(self):
		log.debug('go_main: cli_opts: %s' % (self.cli_opts,))

		if self.cli_opts.tempo_url:
			self.upload_to_tempo()
		elif self.cli_opts.read_hamster_brief:
			self.read_briefs()
		else:
			print("Good job!")

	# *** Hamster.db fcns.

	def read_briefs(self):
		self.entries = []
		with open(self.cli_opts.briefs_file, 'r') as briefs_f:
			for line in briefs_f:
				line = line.strip()
				if line:
					self.read_brief_line(line)

		#print(json_encode(self.entries))
		print(json.dumps(self.entries, sort_keys=True, indent=4))

	# Read a line of SQL output (whose cells are pipe|separated).
	def read_brief_line(self, line):
		try:
			num_fields = 8
			(
			year_month_day,
			time_spent,
			category,
			activity_name,
			activity_id,
			fact_id,
			tags,
			desc_time_tuples,
			) = line.split("|", num_fields-1)
		except Exception as err:
			log.fatal('read_briefs: invalid line: %s' % (line,))
			# YOU deal with this.
			#import pdb;pdb.set_trace()
			raise

		# The descriptions and times are comma-separated two-ples.
		desc_time_tuples = desc_time_tuples.strip('"')
		dnts = desc_time_tuples.split('","')
		assert((len(dnts) % 2) == 0)

		# 2016-12-20: Combine the same-named facts into a single fact.
		comments = []
		desc_times = {}
		idx = 0
		while idx < (len(dnts) / 2):
			ridx = idx * 2
			# FIXME/2017-04-10: Double-quotes in comments are not always delimited.
			#   E.g., if a comment is this: "I quoted something," says I.
			#   Then in the dump file you'll see: ""I quoted something," says I."
			#   And in the JSON file you'll see: I quoted something,\" says I.
			#   Note the missing leading double quote.
			fact_comment = dnts[ridx].replace('\\n\\n', '\n')
			fact_duration = float(dnts[ridx + 1])
			try:
				desc_times[fact_comment] += fact_duration
			except KeyError:
				comments.append(fact_comment)
				desc_times[fact_comment] = fact_duration
			idx += 1

		desctimes = []
		for comment in comments:
			total_duration = round(desc_times[comment], 3)
			desctimes.append("%s [%s]" % (comment, total_duration,))

		# NOTE: These get alphabetized when writ to file.
		new_entry = {
			"year_month_day": year_month_day,
			"time_spent": round(float(time_spent), 3),
			"category": category,
			"activity_name": activity_name,
			"activity_id": activity_id,
			"fact_ids": fact_id,
			"tags": tags,
			"desctimes": desctimes,
		}
		self.entries.append(new_entry)

	# *** Agnostic Upload fcns.
	#
	#     The fcns. are named tempo but could be separated
	#     from the real Tempo fcns., below, if we create a
	#     class factory and made separate classes to impl.
	#     multiple timesheet APIs.

	def upload_to_tempo(self):
		self.entries = []
		with open(self.cli_opts.briefs_file, 'r') as briefs_f:
			self.entries = json_decode(briefs_f.read())

		# Ask for permission when there are lots of entries.
		self.check_if_oh_so_many()

		# Do 2 passes, so in case we cannot parse something or otherwise
		# fail, we won't have sent any POST requests to JIRA.
		forreal = False
		self.parse_errs = []
		self.failed_reqs = []
		self.update_entries(forreal)
		self.upload_forreal()
		self.check_failed_reqs()

	def upload_to_tempo(self):
		if not self.parse_errs:
			forreal = True
			self.update_entries(forreal)
		else:
			print(
				"ERROR: Found %d error(s) you need to fix before you can upload."
				% (len(self.parse_errs),)
			)
			for err in self.parse_errs:
				print(err)
			sys.exit(1)

	def check_failed_reqs(self):
		if self.failed_reqs:
			if not self.cli_opts.testmode:
				self.write_fail_file_and_exit()
			else:
				self.alert_errors_on_test()

	def write_fail_file_and_exit(self):
		now = datetime.datetime.now()

		basename = self.cli_opts.briefs_file
		# FIXME/MAYBE: Anyone care about using a magic date format remover?
		basename = re.sub('[-_\.]?\d{4}[-_\.]?\d{2}[-_\.]?\d{2}[-_\.]?\d{6}\.json$', '', basename)
		# FIXME/MAYBE: Anyone care about using a MAGIC NAME?
		basename = re.sub('\.json$', '', basename)

		fail_file = "%s-%s-%02d%02d%02d.json" % (
			basename,
			datetime.date.today().isoformat(),
			now.hour,
			now.minute,
			now.second,
		)
		with open(fail_file, 'x') as fail_f:
			#for entry in self.failed_reqs:
			#	fail_f.write(json_encode(entry))
			fail_f.write(json.dumps(self.failed_reqs, sort_keys=True, indent=4))
		print(
			"ERROR: Encountered %d error(s) during upload."
			% (len(self.failed_reqs),)
		)
		print("Not all entries were submitted successfully.")
		print("Please fix the problems and try again on the new file:")
		print("  %s" % (fail_file,))
		sys.exit(2)

	def alert_errors_on_test(self):
		print(
			"ERROR: Encountered %d error(s) during preparation."
			% (len(self.failed_reqs),)
		)
		#?sys.exit(2)

	def check_if_oh_so_many(self):
		if len(self.entries) > NUM_ENTRIES_LIMIT_ASK:
			# MAYBE: An --uninteractive option?
			print()
			print("I'm not one to pry, but that's a lot of data.")
			try:
				answer = input(
					"Are you sure you want to upload %d new worklog entries? [y/N] "
					% len(self.entries)
				)
			except EOFError as err:
				# ^D path.
				print("Wha?")
				sys.exit(1)
			except KeyboardInterrupt:
				# ^C path.
				print("You don't have to be rude.")
				sys.exit(1)
			else:
				if (not answer) or (not 'yes'.startswith(answer.lower())):
					print("Alright, you're the boss!")
					sys.exit(1)

	def output_header(self, forreal):
		print('#########################################################################')
		if not forreal:
			print('PASS 1/2 Checking JSON')
		else:
			print('PASS 2/2 Tickling TEMPO')
		print('#########################################################################')

	# *** Tempo-specific fcns.

	def update_entries(self, forreal):
		self.output_header(forreal)

		#print(self.entries)
		#print(json.dumps(self.entries, sort_keys=True, indent=4))

		proj_id_parser = re.compile(r'.* \[(\d+):(\d+):([-a-zA-Z0-9]+)\]\w*')

		total_secs = 0

		for entry in self.entries:
			if not self.ensure_entry_keys(entry):
				next
			entry_secs = self.update_entry(entry, proj_id_parser, forreal)
			total_secs += entry_secs

		self.output_entry_results(total_secs, forreal)

	def update_entry(self, entry, proj_id_parser, forreal):
		proj_id, item_key = self.locate_entry_keys(entry, proj_id_parser)
		curr_entry = self.prepare_curr_entry(entry, proj_id, item_key)
		entry_secs = self.post_curr_entry(curr_entry, entry, forreal)
		return entry_secs

	def post_curr_entry(self, curr_entry, entry, forreal):
		headers = {'content-type': 'application/json'}
		if not forreal:
			json_encode(curr_entry)
			#print(curr_entry)
			print("Entry: date: %s / time: %s" % (
				curr_entry['dateStarted'],
				curr_entry['timeSpentSeconds'],
			))
			entry_secs = int(curr_entry['timeSpentSeconds'])
		else:
			entry_secs = 0
			print('POST: Key: %s / Date: %s / Time: %s' % (
				curr_entry['issue']['key'],
				curr_entry['dateStarted'],
				curr_entry['timeSpentSeconds'],
			))
			print(curr_entry)
			req = requests.post(
				self.cli_opts.tempo_url + '/rest/tempo-timesheets/3/worklogs',
				auth=(self.cli_opts.username, self.cli_opts.password),
				data=json_encode(curr_entry),
				headers=headers,
			)
			# req.text/req.content is the server response, which
			# on 200 OK is the full JSON on the new worklog entry.
			# Note that req.ok when (req.status_code == 200).
			if not req.ok:
				#import pdb;pdb.set_trace()
				self.failed_reqs.append(entry)
				print(
					'ERROR: Tempo error: status_code: %s / text: %s'
					% (req.status_code, req.text,)
				)
		return entry_secs

	def locate_entry_keys(self, entry, proj_id_parser):
		# The project ID and item key are encoded in the Activity name.
		mat = proj_id_parser.match(entry['activity_name'])

# FIXME: 
#			# 2017-08-01: New feature: Get Project ID and Issue ID from JIRA.
#			make lookup of Project name to Project ID, and Issue name to Issue ID.

		tup = mat.groups() if mat else None
		if not tup:
			self.parse_errs.append(
				"ERROR: Activity name missing JIRA IDs: %s"
				% (entry['activity_name'],)
			)
			continue
		try:
			proj_id, item_id, item_key = tup
		except ValueError as err:
			self.parse_errs.append(
				"ERROR: Failed to parse JIRA IDs [proj:item:key] in activity name: %s"
				% (entry['activity_name'],)
			)
			continue

		# For client-level Activities (sans ticket numbers),
		# a tag should contain the item_key. Format is:
		#   exo__CLIENT-TICKETNUMBER__JIRAKEYID
		if entry['tags']:
			# The user can use more than one tag, which hamster, er,
			# sqlite3 (hamster-briefs) combines with commas.
			tags = entry['tags'].split(',')
			for tag in tags:
				try:
					prefix, item_key, item_id = tag.split('__')[:3]
				except ValueError as err:
					# Not an encoded tag; ignore.
					pass

	def prepare_curr_entry(self, entry, proj_id, item_key):
		curr_entry = {
			"dateStarted": "%sT00:00:00.000+0000" % (entry['year_month_day'],),
			"timeSpentSeconds": "%d" % (int(60 * 60 * entry['time_spent']),),
			"comment": self.cli_opts.comment_delimiter.join(entry['desctimes']),
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
		return curr_entry

	def output_entry_results(self, total_secs, forreal):
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

	def ensure_entry_keys(self, entry):
		okay = True
		required_keys = [
			'activity_name',
			'year_month_day',
			'time_spent',
			'desctimes',
		]
		missing_keys = []
		for key in required_keys:
			try:
				entry[key]
			except KeyError:
				missing_keys.append(key)
		if missing_keys:
			okay = False
			print('ERROR: Entry missing mandatory key(s): %s' % (missing_keys,))
			self.failed_reqs.append(entry)
		# Optional keys.
		entry.setdefault('tags', '')
		return okay

def main():
	hr = Transformer()
	hr.go()

if (__name__ == '__main__'):
	main()

