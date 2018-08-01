#!/usr/bin/env python3
# Last Modified: 2017.11.21 /coding: utf-8
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
from http import HTTPStatus
import re
import subprocess
import xml.etree.ElementTree as ET

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
from termcolor import colored, cprint

import logging
import pyoiler_logging
#pyoiler_logging.init_logging(logging.DEBUG, log_to_console=True)
#pyoiler_logging.init_logging(logging.DEBUG, log_to_stderr=True)
pyoiler_logging.init_logging(logging.WARNING, log_to_stderr=True)
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


# ***

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

		self.add_argument('-t', '--test', dest='testmode',
			action='store_true', default=False,
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

# ***

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
			# The user can use either the name or tags to specify the issue key.
			"activity_name": activity_name,
			"tags": tags,
			# fact_ids are used in error output to help user find entries.
			"fact_ids": fact_id,
			# The date of the entry, how much time was spent, and a description.
			"year_month_day": year_month_day,
			"time_spent": round(float(time_spent), 3),
			"desctimes": desctimes,
			# 2017-08-02: activity_id is pretty meaningless to us.
			#"activity_id": activity_id,
			# 2017-08-02: category doesn't matter to this script.
			#"category": category,
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
			try:
				self.entries = json_decode(briefs_f.read())
			except chjson.DecodeError as err:
				self.highlight(
					'ERROR: Could not decode JSON in %s'
					% (self.cli_opts.briefs_file,)
				)
				print(err)
				#cprint('"%s"' % (err,), 'yellow', 'on_red', attrs=['bold'])
				sys.exit(1)

		# Ask for permission when there are lots of entries.
		self.check_if_oh_so_many()

		# Do 2 passes, so in case we cannot parse something or otherwise
		# fail, we won't have sent any POST requests to JIRA.
		self.issue_meta = {}
		self.resolutions = {}
		self.parse_errs = []
		self.failed_reqs = []
		self.update_entries(forreal=False)
		if not self.cli_opts.testmode:
			self.upload_forreal_or_die()
		else:
			self.write_fail_file(forreal=False)

	def add_parse_err(self, entry, msg):
		if not self.parse_errs:
			self.print_splitter()
		self.highlight(
			#'ERROR: In: "%s" (%s) / %s'
			'ERROR: In: "%s" (%s)\n  %s'
			#?% (entry['activity_name'], entry['fact_ids'], msg,)
			% (
				entry['activity_name'] or '[Nameless Activity]',
				entry['fact_ids'] or '[IDless Facts]',
				msg,
			)
		)
		self.parse_errs.append(entry)

	def upload_forreal_or_die(self):
		self.update_entries(forreal=True)
		self.die_on_failed_reqs()
		self.print_final_success()

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

	# *** Tempo-specific fcns.

	def update_entries(self, forreal):
		self.print_header(forreal)

		#print(self.entries)
		#print(json.dumps(self.entries, sort_keys=True, indent=4))

		if not forreal:
			self.prepare_entries()
		else:
			self.re_open_issues_maybe()
			for entry in self.entries:
				#self.print_post_req(entry)
				self.post_tempo_payload(entry)
			self.close_re_opened_issues()

	def prepare_entries(self):
		total_time_spent = 0
		daily_time_spent = {}
		for entry in self.entries:
			# FIXME/2017-08-02: entry should maybe be its own class...
			self.ensure_defaults(entry)
#			self.print_entry_brief(entry)
			if not self.ensure_entry_keys(entry):
				continue
			project_id, issue_key = self.locate_entry_keys(entry)
			if project_id and issue_key:
				self.prepare_tempo_payload(entry)
				self.query_tempo_resolution(entry)
				#self.print_entry_payload_brief(entry)
				secs = int(entry['payload']['timeSpentSeconds'])
				total_time_spent += secs
				ymd = entry['year_month_day']
				daily_time_spent.setdefault(ymd, 0)
				daily_time_spent[ymd] += secs
			self.print_entry_brief(entry)
		self.print_total_time(total_time_spent, daily_time_spent)
		self.die_on_parse_errs()

	ILLEGAL_KEYS = [
		# Gleaned and/or Verified with Tempo:
		'project_key',
		'project_id',
		'issue_key',
		'issue_id',
		'issue_resolution',
		# The Tempo POST payload.
		'payload',
	]

	def ensure_entry_keys(self, entry):
		okay = True
		okay |= self.ensure_item_key_field(entry)
		okay |= self.ensure_required_keys(entry)
		okay |= self.desure_illegal_keys(entry)
		return okay

	def ensure_defaults(self, entry):
		entry.setdefault('activity_name', '')
		entry.setdefault('tags', '')
		entry.setdefault('fact_ids', '')
		entry.setdefault('year_month_day', '')
		entry.setdefault('time_spent', '')
		entry.setdefault('desctimes', '')
#		entry.setdefault('issue_key', '')
#		entry.setdefault('issue_resolution', '')

	def ensure_item_key_field(self, entry):
		# We need the item key (e.g., PROJ-123) which can be in either
		# the activity_name or the tags.
		okay = True
		if not entry['activity_name'] and not entry['tags']:
			okay = False
			self.add_parse_err(
				entry, 'Entry missing item key key(s): "activity_name" and/or "tags"'
			)
		return okay

	def ensure_required_keys(self, entry):
		required_keys = [
			'year_month_day',
			'time_spent',
			'desctimes',
		]
		missing_keys = []
		for key in required_keys:
			if not entry[key]:
				missing_keys.append(key)
		okay = True
		if missing_keys:
			okay = False
			self.add_parse_err(
				entry, 'Entry missing mandatory key(s): %s' % (missing_keys,)
			)
		return okay

	def desure_illegal_keys(self, entry):
		# Illegal keys (used to store internal data).
		invalid_keys = []
		for key in Transformer.ILLEGAL_KEYS:
			try:
				entry[key]
				invalid_keys.append(key)
			except KeyError:
				#entry[key] = None
				pass
			finally:
				entry[key] = None
		okay = True
		if invalid_keys:
			#okay = False
			err_msg = 'Entry contains illegal key(s): %s' % (invalid_keys,)
			#self.add_parse_err(entry, err_msg)
			print("Ignoring: %s" % (err_msg,)
			)
		return okay

	def locate_entry_keys(self, entry):
		invalid = self.query_ids_from_tempo_service(entry)
		if not invalid:
			if not entry['project_id'] and not entry['issue_key'] and not entry['issue_id']:
				msg = (
					'JIRA identifiers not found in tags or activity name: tags: "%s"'
					% (entry['tags'],)
				)
				self.add_parse_err(entry, msg)
		return entry['project_id'], entry['issue_key']

	# >>> re.compile(r'.*(?:-|\s|^)([A-Z0-9]+)-(\d+)(?!-|\w)').match('zoom-zoom ddd-ABC-123,XYZ-233').groups()
	# ('ABC', '123')
	# 
	# >>> re.compile(r'(?:-|\s|^)([A-Z0-9]+)-(\d+)(?!-|\w)').findall('zoom-zoom ddd-ABC-123, XYZ-233')
	# [('ABC', '123'), ('XYZ', '233')]
	#
	# >>> re.compile(r'(?:-|\s|^)([A-Z0-9]+)-(\d+)(?!\d)').findall(
	#       'zoom-zoom ddd-ABC-123-JJJ-123-something XYZ-233')
	# [('ABC', '123'), ('JJJ', '123'), ('XYZ', '233')]
	# E.g., USER-PREFIX_Don't-Care-ALLCAPSPROJECTKEY123-456
	#PROJ_KEY_PARSER = re.compile(r'(?:-|\s|^)([A-Z0-9]+)-(\d+)(?!\d)')
	# Allow `:` before item key, e.g., blah:PROJ-123
	#PROJ_KEY_PARSER = re.compile(r'(?:-|:|\s|^)([A-Z0-9]+)-(\d+)(?!\d)')
	# Allow `_` before item key, e.g., blah_PROJ-123
	#PROJ_KEY_PARSER = re.compile(r'(?:-|:|_|\s|^)([A-Z0-9]+)-(\d+)(?!\d)')
	# Allow `[` before item key, e.g., [PROJ-123] (NOTE: [ needs to be \delimited.)
	PROJ_KEY_PARSER = re.compile(r'(?:-|:|_|\[|\s|^)([A-Z0-9]+)-(\d+)(?!\d)')

	#ISSUE_KEY_PARSER = re.compile(r'^([A-Z0-9]+)-(\d+)$')

	def query_ids_from_tempo_service(self, entry):
		try:
			name_matches = Transformer.PROJ_KEY_PARSER.findall(entry['activity_name'])
		except KeyError:
			name_matches = []
		tags_matches = []
		for tag in self.entry_tags(entry):
			matches = Transformer.PROJ_KEY_PARSER.findall(tag)
			tags_matches.extend(matches)
		project_key, item_number, invalid = self.find_keys_match(entry, name_matches, tags_matches)
		if project_key and item_number:
			self.set_entry_issue_meta(entry, project_key, item_number)
		return invalid

	def set_entry_issue_meta(self, entry, project_key, item_number):
		try:
			entry['project_id'], entry['issue_key'], entry['issue_id'] = (
				self.issue_meta[project_key][item_number]
			)
		except KeyError:
			self.get_issue_meta(entry, project_key, item_number)

	def get_issue_meta(self, entry, project_key, item_number):
		issue_key = '%s-%s' % (project_key, item_number,)
		endpoint = (
			'/si/jira.issueviews:issue-xml/%s/%s.xml'
			% (issue_key, issue_key,)
		)
		req = requests.get(
			self.cli_opts.tempo_url + endpoint,
			auth=(self.cli_opts.username, self.cli_opts.password),
		)
		if req.ok:
			try:
				tree = ET.fromstring(req.text)
				# import xml.dom.minidom
				# xml = xml.dom.minidom.parseString(req.text)
				# pretty_xml_as_string = xml.toprettyxml()
			except ET.ParseError as err:
				if '<title>Log in - Exosite</title>' in req.text:
					self.add_parse_err(entry, 'Logon Failed!')
				else:
					self.add_parse_err(entry, 'Parse error: Tempo Parse XML: %s' % (err,))
			except Exception as err:
				self.add_parse_err(entry, 'Unknown error: Tempo Parse XML: %s' % (err,))
			else:
				self.parse_issue_meta(entry, tree, issue_key, project_key, item_number)
		elif req.status_code != HTTPStatus.NOT_FOUND:
			self.add_parse_err(
				entry,
				'Tempo GET XML: status_code: %s / endpoint: %s / text: %s' % (
					req.status_code, endpoint, req.text,
				)
			)
		else:
			self.add_parse_err(entry, 'Tempo Item Not Found: endpoint: %s' % (endpoint,))

	PROJ_ID_PARSER = re.compile(r'^\d{5}$')

	def parse_issue_meta(self, entry, tree, issue_key, project_key, item_number):
		try:
			item_elem = tree.find('channel').find('item')
			#
			proj_elem = item_elem.find('project')
			doc_project_key = proj_elem.get('key')
			doc_project_id = proj_elem.get('id')
			#
			key_elem = item_elem.find('key')
			doc_issue_key = key_elem.text
			doc_issue_id = key_elem.get('id')

			status_elem = item_elem.find('status').get('id')
			# Get the Issue status, e.g.,
			# <status id="1" description="This is an issue that requires attention">Open</status>
			# <status id="10626" description="">Not Needed - Closed</status>
			# <status id="11026" description="">Ready for Release to Production</status>
			if status_elem.lower().find('closed') != -1:
				self.add_parse_err(
					entry,
					'Project Closed: "%s": Repoen the project to log time against issues' % (
						issue_key
					)
				)
		except KeyError as err:
			self.add_parse_err(
				entry,
				'Unexpected: could not locate XML keys: err: "%s"' % (err,)
			)
		else:
			if project_key != doc_project_key:
				self.add_parse_err(
					entry,
					'Unexpected: project_key mismatch: "%s": "%s" != "%s"' % (
						issue_key, project_key, doc_project_key,
					)
				)
			else:
				mat = Transformer.PROJ_ID_PARSER.match(doc_project_id)
				if not mat:
					self.add_parse_err(
						entry,
						'Unexpected: project_id mismatch: "%s" !~ "%s"' % (
							doc_project_id, Transformer.PROJ_ID_PARSER.pattern,
						)
					)
				else:
					(
						entry['project_key'],
						entry['project_id'],
						entry['issue_key'],
						entry['issue_id'],
					) = (
						doc_project_key,
						doc_project_id,
						doc_issue_key,
						doc_issue_id,
					)
					self.issue_meta.setdefault(project_key, {})
					self.issue_meta[project_key][item_number] = (
						doc_project_id, doc_issue_key, doc_issue_id,
					)

	def find_keys_match(self, entry, name_matches, tags_matches):
		project_key, item_number = None, None
		okay = self.validate_id_matches(entry, name_matches, tags_matches)
		if okay:
			if name_matches:
				project_key, item_number = name_matches[0]
			elif tags_matches:
				project_key, item_number = tags_matches[0]
			# else, someone up stack will raise the alarm.
		return project_key, item_number, not okay

	def validate_id_matches(self, entry, name_matches, tags_matches):
		okay = True

		# 2017-09-08: It's okay if the same ISSUE-XXX is specified more
		# than once. This lets the user put the same ID in both the
		# Activity name and in the Fact tag.
		keynums = set()
		for key, num in name_matches:
			keynums.add((key, num))
		for key, num in tags_matches:
			keynums.add((key, num))
		if len(keynums) <= 1:
			return okay

		# 2017-08-01: For now, not allowed to specify more than one issue key.
		# Really just curious if I'll ever run into this and want to change it,
		# say, make the tags issue key override the activity name key, or vice
		# versa.
		if name_matches and tags_matches:
			okay = False
			self.add_parse_err(
				entry,
				'%s: acty: %s / tags: %s / on: %s / desc: %s' % (
					'Issue Keys are in both activity name and keys',
					name_matches,
					tags_matches,
					entry['year_month_day'],
					entry['desctimes'],
				)
			)
		elif len(name_matches) > 1:
			okay = False
			self.add_parse_err(
				entry,
				'Too many Issue Keys found in activity name: acty: %s' % (
					name_matches,
				)
			)
		# FIXME/2017-08-02: Allow multiple tags. Could split time equally between them!
		elif len(tags_matches) > 1:
			okay = False
			self.add_parse_err(
				entry,
				'Too many Issue Keys found in tags: %s' % (
					tags_matches,
				)
			)
		# else, either only 1 match, or none.
		return okay

	def entry_tags(self, entry):
		try:
			if entry['tags']:
				# The user can use more than one tag, which hamster, er,
				# sqlite3 (hamster-briefs) combines with commas.
				tags = entry['tags'].split(',')
			else:
				tags = []
		except KeyError:
			tags = []
		return tags

	def prepare_tempo_payload(self, entry):
		tempo_payload = {
			"author": {
				"name": self.cli_opts.username,
			},
			# NOTE: In the XML, the issue is called the item.
			"issue": {
				"projectId": entry['project_id'],
				"key": entry['issue_key'],
				# 2017-08-01: What!? Now I tell myself... I've been manually
				#   grabbing the Issue ID!! And I tell me I don't need it??!!!
				#   Whenever I figured this out, and commented out this code,
				#   I should have fixed all my hamster tags!!
				# Not needed:
				#item_id? itemId? hrmm: entry['issue_id'],
			},
			"dateStarted": "%sT00:00:00.000+0000" % (entry['year_month_day'],),
			"timeSpentSeconds": "%d" % (int(60 * 60 * entry['time_spent']),),
			"comment": self.cli_opts.comment_delimiter.join(entry['desctimes']),
		}
		entry['payload'] = tempo_payload

	def post_tempo_payload(self, entry):
		headers = {'content-type': 'application/json'}
		req = requests.post(
			self.cli_opts.tempo_url + '/rest/tempo-timesheets/3/worklogs',
			auth=(self.cli_opts.username, self.cli_opts.password),
			#data=json_encode(entry['payload']),
			# 2017-11-21: I tried uploading an entry that had unicode in it and got:
			#  UnicodeEncodeError: 'latin-1' codec can't encode character '\u25bc'
			#    in position 219: Body ('▼') is not valid Latin-1.
			#    Use body.encode('utf-8') if you want to send it encoded in UTF-8.
			data=json_encode(entry['payload']).encode('utf-8'),
			headers=headers,
		)
		# req.text/req.content is the server response, which
		# on 200 OK is the full JSON on the new worklog entry.
		# Note that req.ok when (req.status_code == 200).
		if not req.ok:
			#import pdb;pdb.set_trace()
			self.failed_reqs.append(entry)
			print(
				'ERROR: Tempo POST Worklog: status_code: %s / text: %s'
				% (req.status_code, req.text,)
			)

	# ***

	def query_tempo_resolution(self, entry):
		if entry['issue_key'] in self.resolutions.keys():
			entry['issue_resolution'] = self.resolutions[entry['issue_key']]

		# FIXME: 2018-08-01 05:45: Hahaha. Why am I using jira tool and not,
		#        say, accessing API directly (i.e., via requests.get)?
		proc = subprocess.Popen(
			['jira', 'view', entry['issue_key'], '-t', 'debug',],
			stdout=subprocess.PIPE,
		)
		(stdout_data, stderr_data) = proc.communicate()
		resp = json_decode(stdout_data.decode())
		entry['issue_resolution'] = ''
		if resp['fields']['resolution']:
			entry['issue_resolution'] = resp['fields']['resolution']['name']
			self.resolutions[entry['issue_key']] = entry['issue_resolution']

	def re_open_issues_maybe(self):
		for issue_key, _resolution in self.resolutions.items():
			self.re_open_issue(issue_key)

	def re_open_issue(self, issue_key):
		# FIXME: 2018-08-01 05:45: Hahaha. Why am I using jira tool and not,
		#        say, accessing API directly (i.e., via requests.post)?
		proc = subprocess.Popen(
			['jira', 'in-progress', issue_key,],
			stdout=subprocess.PIPE,
		)
		(stdout_data, stderr_data) = proc.communicate()
		# FIXME: What about checking err code nonzero instead of parsing text??
		stdout_data = stdout_data.decode() if stdout_data else ''
		stderr_data = stderr_data.decode() if stderr_data else ''
		if not stdout_data.startswith('OK {}'.format(issue_key)):
#
			import pdb;pdb.set_trace()
			
			print(
				"ERROR: Could not re-open issue: {}: {} / {}".format(
					issue_key, stdout_data, stderr_data,
				)
			)

	def close_re_opened_issues(self):
		for issue_key, resolution in self.resolutions.items():
			self.close_re_opened_issue(issue_key, resolution)

	def close_re_opened_issue(self, issue_key, resolution):
		# FIXME: 2018-08-01 05:45: Hahaha. Why am I using jira tool and not,
		#        say, accessing API directly (i.e., via requests.post)?
		proc = subprocess.Popen(
			[
				'jira',
				'close',
				'--resolution',
				resolution,
				issue_key,
			],
			stdout=subprocess.PIPE,
		)
		(stdout_data, stderr_data) = proc.communicate()
		# FIXME: What about checking err code nonzero instead of parsing text??
		stdout_data = stdout_data.decode()
		if not stdout_data.startswith('OK {}'.format(issue_key)):
			print(
				"ERROR: Could not close re-opened issue: {}: {} / {}".format(
					issue_key, stdout_data, stderr_data.decode(),
				)
			)

	# *** Deadly fcns.

	def die_on_parse_errs(self):
		if self.parse_errs:
			self.print_splitter()
			print(
				"ERROR: Found %d error(s) you need to fix before you can upload."
				% (len(self.parse_errs),)
			)
			#for err in self.parse_errs:
			#	print(err)
			sys.exit(2)

	def die_on_failed_reqs(self):
		if self.failed_reqs:
			self.write_fail_file(forreal=True)
			sys.exit(2)

	def write_fail_file(self, forreal):
		basename = self.cli_opts.briefs_file
		# FIXME/MAYBE: Anyone care about using a magic date format remover?
		basename = re.sub(
			'[-_\.]?\d{4}[-_\.]?\d{2}[-_\.]?\d{2}[-_\.]?\d{6}\.json$', '', basename
		)
		# FIXME/MAYBE: Anyone care about using a MAGIC NAME?
		basename = re.sub('\.json$', '', basename)

		if forreal:
			now = datetime.datetime.now()
			fail_file = "%s-%s-%02d%02d%02d.json" % (
				basename,
				datetime.date.today().isoformat(),
				now.hour,
				now.minute,
				now.second,
			)
			file_mode = 'x'
		else:
			fail_file = "%s-%s-TESTMODE.json" % (
				basename,
				datetime.date.today().isoformat(),
			)
			file_mode = 'w'

		with open(fail_file, file_mode) as fail_f:
			#for entry in self.failed_reqs:
			#	fail_f.write(json_encode(entry))
			if self.failed_reqs:
				records = self.failed_reqs
			else:
				records = self.entries
			if not self.cli_opts.testmode:
				for record in records:
					for key in Transformer.ILLEGAL_KEYS:
						record.pop(key, None)
			fail_f.write(json.dumps(records, sort_keys=True, indent=4))

		if forreal:
			print(
				"ERROR: Encountered %d error(s) during upload."
				% (len(self.failed_reqs),)
			)
			print("Not all entries were submitted successfully.")
			print("Please fix the problems and try again on the new file:")
			print("  %s" % (fail_file,))
		else:
			print("A reprinted JSON file with prepared meta was writ for you:")
			#print("  %s" % (os.path.join(os.getcwd(), fail_file),))
			print("  %s" % (os.path.join(os.path.basename(os.getcwd()), fail_file),))

	# *** Print fcns.

	def highlight(self, msg):
		#print(colored('Hello, World!', 'red', attrs=['reverse', 'blink']))
		#cprint('Hello, World!', 'green', 'on_red')
		#for i in range(10):
		#	cprint(i, 'magenta', end=' ')
		#cprint(msg, 'red', 'on_cyan')
		cprint(msg, 'red', 'on_white', attrs=['bold'])

	def print_header(self, forreal):
		print('#########################################################################')
		if not forreal:
			print('PASS 1/2 Checking JSON')
		else:
			print('PASS 2/2 Tickling TEMPO')
		print('#########################################################################')

	def print_splitter(self):
		print('-' * 73)

	def print_entry_brief(self, entry):
		self.print_splitter()
		print("Entry: %s / %s / tags: %s" % (
			entry['year_month_day'],
			entry['issue_key'] or entry['activity_name'] or '[Nameless Activity]',
			#entry['fact_ids'] or '[No ref. PKs]',  # (lb): Not at all important.
			entry['tags'] or '<no tags>',
		))
		if entry['issue_resolution']:
			print("  Resolution: %s" % (
				#entry['payload']['issue']['key'],
				entry['issue_resolution'],
			))

	def print_entry_payload_brief(self, entry):
		tempo_payload = entry['payload']
		json_encode(tempo_payload)
		#print(tempo_payload)
		if False:
			print("  %s / Date: %s / Time: %s / %s (%s)" % (
				entry['payload']['issue']['key'],
				tempo_payload['dateStarted'],
				tempo_payload['timeSpentSeconds'],
				entry['activity_name'] or '[Nameless Activity]',
				entry['fact_ids'] or '[IDless Facts]',
			))
		print("  %s / Resolution: %s" % (
			entry['payload']['issue']['key'],
			entry['issue_resolution'],
		))

	def print_total_time(self, total_time_spent, daily_time_spent={}):
		self.print_splitter()
		print(
			"Total Fact time: %.2f hours"
			% (total_time_spent / 60.0 / 60.0,)
		)

		dailies = []
		for date in sorted(daily_time_spent.keys()):
			dailies.append("  {}: {:.2f} hrs.".format(
				date, daily_time_spent[date] / 60.0 / 60.0,
			))
		#print(' / '.join(dailies))
		print("\n".join(dailies))

	def print_post_req(self, entry):
		print('POST: Key: %s / Date: %s / Time: %s' % (
			entry['payload']['issue']['key'],
			entry['payload']['dateStarted'],
			entry['payload']['timeSpentSeconds'],
		))
		print(entry['payload'])

	def print_final_success(self):
		self.print_splitter()
		print('Success!')
		print()
		# FIXME: Can/Should we automate submit-for-approval?
		print("REMEMBER: Logon and submit your timesheet.")
		# FIXME: Encode 'period' so the correct week is displayed.
		#  https://domain/jira/secure/TempoUserBoard!timesheet.jspa?period=07112016
		print("  %s/secure/TempoUserBoard!timesheet.jspa" % (self.cli_opts.tempo_url,))
		print()

# ***


def main():
	hr = Transformer()
	hr.go()


if (__name__ == '__main__'):
	main()

