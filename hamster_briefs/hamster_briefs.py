#!/usr/bin/env python3.5
# (Using py3.5 for subprocess.run().)
# Last Modified: 2016.11.20 /coding: utf-8
# Copyright: © 2016 Landon Bouma.
#  vim:tw=0:ts=4:sw=4:noet

# FIXME: Distinguish btw. SQLite3 versions to decide whether
#        to run subprocess or not.
#        Problem is, on Mint 18 (Ubuntu 14.04), Python's SQLite3
#        is too-old version, and it's not easy (nor wise) to
#        fiddle with Python's built-ins (you trust building Python
#        from scratch? Not that you can't do it, but that you wouldn't
#        mess something else up?).
#        (MAYBE: OR: Don't case. Just use subprocess. Simplify.)

import os
import sys

import datetime
import re
import sqlite3
import subprocess
import time

import pyoiler_argparse

import logging
import pyoiler_logging
pyoiler_logging.init_logging(pyoiler_logging.DEBUG, log_to_console=True)
log = logging.getLogger('hamster-briefs')

import hamster_briefs.version_hamster

SCRIPT_DESC = '''verb / 3rd person present: briefs / 1. instruct or inform (someone) thoroughly, especially in preparation for a task.'''

# DEVs: Set to True for better error message if sqlite3 query fails.
#       Include stderr messages, including, e.g.,
#         -- Loading resources from ~/.sqliterc
LEAK_SQLITE3_ERRORS=False
#LEAK_SQLITE3_ERRORS=True

class HR_Argparser(pyoiler_argparse.ArgumentParser_Wrap):

	all_report_types = set([
		'all',
		'egg',
		'gross',
		'weekly-summary',
		'sprint-summary',
		#'weekly-tight',
		#'sprint-tight',
		'daily',
		'weekly',
		'activity',
		'category',
		'totals',
		'satsun',
		'sprint',
		'daily-activity',
		'daily-category',
		'daily-totals',
		'weekly-satsun',
		'weekly-sprint',
		'weekly-activity',
		'weekly-category',
		'weekly-totals',
		'weekly-activity-satsun',
		'weekly-category-satsun',
		'weekly-totals-satsun',
		'weekly-activity-sprint',
		'weekly-category-sprint',
		'weekly-totals-sprint',
		'gross-activity',
		'gross-category',
		'gross-totals',
		'report',
		'report-activity',
	])

	gross_report = [
		'gross-activity',
		'gross-category',
		'gross-totals',
	]

	weekly_report = [
		'daily-activity',
		'daily-category',
		'daily-totals',
		'weekly-activity-satsun',
		'weekly-category-satsun',
		'weekly-totals-satsun',
	]

	sprint_report = [
		'daily-activity',
		'daily-category',
		'daily-totals',
		'weekly-activity-sprint',
		'weekly-category-sprint',
		'weekly-totals-sprint',
	]

	# 0 is Sunday; 6 is Saturday.
	weekday_lookup_1_char = {
		#'s': 0,
		'm': 1,
		#'t': 2,
		'w': 3,
		#'t': 4,
		'f': 5,
		#'s': 6,
	}
	weekday_lookup_2_chars = {
		'su': 0,
		'mo': 1,
		'tu': 2,
		'we': 3,
		'th': 4,
		'fr': 5,
		'sa': 6,
	}

	def __init__(self):
		pyoiler_argparse.ArgumentParser_Wrap.__init__(self,
			description=SCRIPT_DESC,
			script_name=None,
			script_version=hamster_briefs.version_hamster.SCRIPT_VERS,
			usage=None)

	def prepare(self):
		pyoiler_argparse.ArgumentParser_Wrap.prepare(self)

		self.add_argument('-b', '--beg', dest='time_beg',
			type=str, metavar='BEG_DATE', default=None
		)
		self.add_argument('-e', '--end', dest='time_end',
			type=str, metavar='END_DATE', default=None
		)

		self.add_argument('-c', '--category', dest='categories',
			action='append', type=str, metavar='CATEGORY',
		)

		self.add_argument('-a', '--activity', dest='activities',
			action='append', type=str, metavar='ACTIVITY',
		)

		self.add_argument('-t', '--tag', dest='tags',
			action='append', type=str, metavar='TAG',
		)

		self.add_argument('--and', dest='and_acts_and_tags',
			action='store_true', default=False,
			help="Match activities AND tags names, else just OR",
		)

		self.add_argument('-0', '--today', dest='prev_weeks',
			action='store_const', const=0,
		)
		self.add_argument('-1', '--this-week', dest='prev_weeks',
			action='store_const', const=1,
		)
		self.add_argument('-2', '--last-week', dest='prev_weeks',
			action='store_const', const=2,
		)
		self.add_argument('-3', '--last-two-weeks', dest='prev_weeks',
			action='store_const', const=3,
		)
		self.add_argument('-4', '--this-month', dest='prev_weeks',
			action='store_const', const=4,
		)
		self.add_argument('-5', '--last-two-months', dest='prev_weeks',
			action='store_const', const=5,
		)

		self.add_argument('-l', '--quick-list', dest='quick_list',
			action='store_true', default=False,
		)

		self.add_argument('-r', '--report-types', dest='do_list_types',
			action='append', type=str, metavar='REPORT_TYPE',
			choices=HR_Argparser.all_report_types, default=[],
		)

		self.add_argument('-A', '--list-all', dest='do_list_all',
			action='store_true', default=False,
		)

		self.add_argument('-E', '--eggregate', dest='do_aggregate',
			action='store_true', default=False,
			help="Format as daily activity-tag aggregate with fact descriptions [and fact times]",
		)

		self.add_argument('-S', '--show-sql', dest='show_sql',
			action='store_true', default=False,
		)

		self.add_argument('-vv', '--verbose', dest='be_verbose',
			action='store_true', default=False,
		)

		self.add_argument('-w', '--day-week-starts', dest='week_starts',
			type=str, metavar='DAY_WEEK_STARTS', default=None
		)
		self.add_argument('-W', '--first-sprint-week-num', dest='first_sprint_week_num',
			type=int, metavar='FIRST_SPRINT_WEEK_NUM', default=0,
			help="Apply offset to sprint week (julianweek since Jan 1st)",
		)

		self.add_argument('-D', '--data', dest='hamster_db_path',
			type=str, metavar='HAMSTER_DB_PATH', default=None
		)

		# MEH: Only one output function honors this setting.
		self.add_argument('-s', '--split-days', dest='output_split_days',
			action='store_true', default=False,
			help="Print newline between days. NOTE: Not honored by all report types.",
		)

		# MAYBE/#XXXs: A few new features.
		if False:
			self.prepare_add_stubs()

	def prepare_add_stubs(self):

		# LATER/#XXX: Check for gaps feature.
		self.add_argument('-g', '--gaps', dest='check_gaps',
			action='store_true', default=False,
		)

		# LATER/MAYBE/#XXX: day-starts feature. I.e., other than at midnight.
		self.add_argument('-d', '--time-day-starts', dest='day_starts',
			type=str, metavar='TIME_DAY_STARTS', default=None
		)

		# MAYBE/#XXX: Need a search-description option?
		self.add_argument('--description', dest='description',
			action='append', type=str, metavar='DESCRIPTION',
		)

		# MAYBE/#XXX: Need a generic, search-all-fields query?
		self.add_argument('-s', '--search', '-q', '--query', dest='query',
			action='append', type=str, metavar='QUERY',
		)

		# LATER/#ts-178: Add 'deleted' column to 'fact' table.
		#
		#                Because if you put wrong time/date in GUI,
		#                you can destroy or modify existing facts
		#                without warning.
		#
		#                And there's no undo other than recreating
		#                said facts, or restoring a backup of hamster.db.

	def verify(self):
		ok = pyoiler_argparse.ArgumentParser_Wrap.verify(self)

		self.cli_opts.cli_optsless = False

		if self.cli_opts.be_verbose:
			log.setLevel(pyoiler_logging.DEBUG)
		elif self.cli_opts.show_sql:
			log.setLevel(pyoiler_logging.INFO)
		else:
			log.setLevel(pyoiler_logging.WARNING)

		if self.cli_opts.week_starts:
			try:
				self.cli_opts.week_starts = int(self.cli_opts.week_starts)
				if (
					(self.cli_opts.week_starts < 0)
					or (self.cli_opts.week_starts > 6)
					):
						log.fatal('"%s" is not a valid weekday number (0-6)' % (
							self.cli_opts.week_starts,)
						)
						ok = False
			except ValueError:
				if len(self.cli_opts.week_starts) == 1:
					try:
						self.cli_opts.week_starts = HR_Argparser.weekday_lookup_1_char[
							self.cli_opts.week_starts.lower()
						]
					except KeyError:
						log.fatal('"%s" is not a valid weekday' % (
							self.cli_opts.week_starts,)
						)
						ok = False
				else:
					week_abbrev = self.cli_opts.week_starts.lower()[:2]
					try:
						self.cli_opts.week_starts = HR_Argparser.weekday_lookup_2_chars[
							week_abbrev
						]
					except KeyError:
						log.fatal('"%s" is not a valid weekday' % (week_abbrev,))
						ok = False
		else:
			self.cli_opts.week_starts = 0

		# LATER/#XXX: Implement this feature.
		if False:
			if self.cli_opts.day_starts:
				# day_starts is the time of day that each 24 hours starts.
				# Default to midnight in your local timezone.
				log.fatal('LATER/#XXX: Implement this feature.')
				ok = False

		if self.cli_opts.hamster_db_path is None:
			self.cli_opts.hamster_db_path = (
				'%s/.local/share/hamster-applet/hamster.db'
				% (os.path.expanduser('~'),)
			)

		# 0: today, 1: this week, 2: this week and last, 4: month, 5: 2 months.
		#today = time.time()
		today = datetime.date.today()

		# Python says Monday is 0 and Sunday is 6;
		# Sqlite3 says Sunday 0 and Saturday 6.
		weekday = (today.weekday() + 1) % 7
		days_ago = weekday - self.cli_opts.week_starts

		if self.cli_opts.quick_list:
			# This display is nice for copy-pasting to another entry system,
			# like plan.io/redmine; it lists the number of hours per activity
			# per day with other lite stats for last full sprint week.
			if not self.cli_opts.do_list_types:
				self.cli_opts.do_list_types = ['report-activity',]
				self.cli_opts.output_split_days = True
			if self.cli_opts.prev_weeks is None:
				# If first day of new sprint, but this week and last (e.g.,
				# it's timesheet day!). If into the sprint, print just
				# current week.
				if days_ago <= 1:
					self.cli_opts.prev_weeks = 2
				else:
					self.cli_opts.prev_weeks = 1

		if self.cli_opts.do_aggregate:
			self.cli_opts.do_list_types += ['egg',]

		if self.cli_opts.prev_weeks is not None:
			if self.cli_opts.time_end is not None:
				log.fatal('Overriding time_end with today because prev_weeks.')
			# FIXME: This makes -0 return zero results, i.e., nothing hits for
			#        today. Which probably means < time_end and not <=, is that okay?
			#self.cli_opts.time_end = today.isoformat()
			self.cli_opts.time_end = today + datetime.timedelta(1)
			if self.cli_opts.time_beg is not None:
				log.fatal('Overriding time_beg with calculated because prev_weeks.')

			if self.cli_opts.prev_weeks == 0:
				#start_date = today - datetime.timedelta(1)
				##start_date = today
				self.cli_opts.time_beg = today.isoformat()
				##self.cli_opts.time_beg = start_date.isoformat()
				if not self.cli_opts.do_list_types:
					self.cli_opts.do_list_types = ['daily',]
			else:
				#self.cli_opts.time_end = today.isoformat()
				if days_ago < 0:
					days_ago += 7
				if self.cli_opts.prev_weeks == 1:
					# Calculate back to week start.
					start_date = today - datetime.timedelta(days_ago)
				elif self.cli_opts.prev_weeks == 2:
					# Last week.
					start_date = today - datetime.timedelta(7 + days_ago)
					self.cli_opts.time_end = today - datetime.timedelta(days_ago)
				elif self.cli_opts.prev_weeks == 3:
					# Calculate to two weeks backs ago.
					start_date = today - datetime.timedelta(7 + days_ago)
				elif self.cli_opts.prev_weeks == 4:
					start_date = today.replace(day=1)
				elif self.cli_opts.prev_weeks == 5:
					year = today.year
					month = today.month - 1
					if not month:
						year -= 1
						month = 12
					start_date = datetime.date(year, month, 1)
				else:
					log.fatal(
						'Precanned time span value should be one of: 0, 1, 2, 4, 5; not %s'
						% (self.cli_opts.prev_weeks,)
					)
				self.cli_opts.time_beg = start_date.isoformat()

		add_list_types = []
		if (not self.cli_opts.do_list_types
			and self.cli_opts.prev_weeks is None
			and self.cli_opts.time_beg
			and self.cli_opts.time_end
		):
			time_beg = HR_Argparser.str2datetime(self.cli_opts.time_beg)
			time_end = HR_Argparser.str2datetime(self.cli_opts.time_end)
			if time_beg and time_end:
				# The the datetime.timedelta.
				time_diff = time_end - time_beg
				# We could check seconds if we cared for more precision.
				if time_diff.days == 0:
					self.cli_opts.do_list_types = ['daily',]
				elif time_diff.days > 7:
					add_list_types += ['gross',]
		if not self.cli_opts.do_list_types:
			if self.cli_opts.week_starts:
				if self.cli_opts.prev_weeks in [1,2,3,]:
					self.cli_opts.do_list_types = ['sprint-report',]
				else:
					self.cli_opts.do_list_types = ['sprint-summary',]
			else:
				if self.cli_opts.prev_weeks in [1,2,3,]:
					self.cli_opts.do_list_types = ['weekly-report',]
				else:
					# THIS_IS_THE_DEFAULT_BEHAVIOUR: This happens if user uses no CLI opts.
					#self.cli_opts.do_list_types = ['weekly-summary',]
					# 2016-03-16: After months of hundreds of new facts since
					# first writing this script, a weekly-summary seems too much.
					# Ideally, we'd see what's in the db already and tailor the
					# response to that, but people don't run no-opts very often.
					# We should probably show some help....
					self.cli_opts.cli_optsless = True
					self.cli_opts.do_list_types = ['gross',]
			self.cli_opts.do_list_types += add_list_types
		self.setup_do_list_types()

		return ok

	# MEH: This is really more of a utility class method...
	@staticmethod
	def str2datetime(time_str):
		dtobj_1 = None
		dtobj_2 = None
		date_parser = re.compile(r'(\d+)[^\d]+(\d+)[^\d]+(\d+)\s+(\d+)[^\d]+(\d+)')
		rem = date_parser.match(time_str)
		tup = rem.groups() if rem else None
		if tup:
			try:
				strpfmt = '%Y-%m-%d %H:%M'
				dtobj_1 = datetime.datetime.strptime('%s-%s-%s %s:%s' % tup, strpfmt)
				# params: year, month, day, hour=0, minute=0, second=0, microsecond=0, tzinfo=None
				dtobj_2 = datetime.datetime(*[int(x) for x in tup])
			except ValueError:
				pass # The SQL date parser will try harder to decode it.
			#assert_soft(dtobj_1 == dtobj_2)
		return dtobj_2

	def setup_do_list_types_add(self, list_type):
		if list_type not in self.setup_seen_types:
			self.setup_seen_types.add(list_type)
			self.setup_list_types.append(list_type)

	def setup_do_list_types(self):
		ok = True
		self.setup_seen_types = set()
		self.setup_list_types = []

		for list_type in self.cli_opts.do_list_types:
			# Ignoring: list_type == 'all'
			#  See: self.cli_opts.do_list_all
			# Hahaha, this block is ridiculous.
			if list_type == 'gross':
				self.setup_do_list_types_add('gross-activity')
				self.setup_do_list_types_add('gross-category')
				self.setup_do_list_types_add('gross-totals')
			elif list_type == 'weekly-summary':
				for report_type in HR_Argparser.weekly_report:
					self.setup_do_list_types_add(report_type)
			elif list_type == 'sprint-summary':
				for report_type in HR_Argparser.sprint_report:
					self.setup_do_list_types_add(report_type)
			elif list_type == 'weekly-report':
				self.setup_do_list_types_add('daily-activity')
				self.setup_do_list_types_add('daily-totals')
				self.setup_do_list_types_add('weekly-category-satsun')
				self.setup_do_list_types_add('weekly-totals-satsun')
			elif list_type == 'sprint-report':
				self.setup_do_list_types_add('daily-activity')
				self.setup_do_list_types_add('daily-totals')
				self.setup_do_list_types_add('weekly-category-sprint')
				self.setup_do_list_types_add('weekly-totals-sprint')
			elif list_type == 'daily':
				#self.setup_do_list_types_add('daily-activity')
				#self.setup_do_list_types_add('daily-category')
				self.setup_do_list_types_add('daily-totals')
				self.setup_do_list_types_add('daily-category')
				self.setup_do_list_types_add('daily-activity')
			elif list_type == 'weekly':
				self.setup_do_list_types_add('weekly-activity-satsun')
				self.setup_do_list_types_add('weekly-category-satsun')
				self.setup_do_list_types_add('weekly-totals-satsun')
				self.setup_do_list_types_add('weekly-activity-sprint')
				self.setup_do_list_types_add('weekly-category-sprint')
				self.setup_do_list_types_add('weekly-totals-sprint')
			elif list_type == 'activity':
				self.setup_do_list_types_add('daily-activity')
				self.setup_do_list_types_add('weekly-activity-satsun')
				self.setup_do_list_types_add('weekly-activity-sprint')
			elif list_type == 'category':
				self.setup_do_list_types_add('daily-category')
				self.setup_do_list_types_add('weekly-category-satsun')
				self.setup_do_list_types_add('weekly-category-sprint')
			elif list_type == 'totals':
				self.setup_do_list_types_add('daily-totals')
				self.setup_do_list_types_add('weekly-totals-satsun')
				self.setup_do_list_types_add('weekly-totals-sprint')
			elif list_type in ['satsun', 'weekly-satsun',]:
				self.setup_do_list_types_add('weekly-activity-satsun')
				self.setup_do_list_types_add('weekly-category-satsun')
				self.setup_do_list_types_add('weekly-totals-satsun')
			elif list_type in ['sprint', 'weekly-sprint',]:
				self.setup_do_list_types_add('weekly-activity-sprint')
				self.setup_do_list_types_add('weekly-category-sprint')
				self.setup_do_list_types_add('weekly-totals-sprint')
			elif list_type == 'weekly-activity':
				self.setup_do_list_types_add('weekly-activity-satsun')
				self.setup_do_list_types_add('weekly-activity-sprint')
			elif list_type == 'weekly-category':
				self.setup_do_list_types_add('weekly-category-satsun')
				self.setup_do_list_types_add('weekly-category-sprint')
			elif list_type == 'weekly-totals':
				self.setup_do_list_types_add('weekly-totals-satsun')
				self.setup_do_list_types_add('weekly-totals-sprint')
			elif list_type == 'weekly-totals':
				self.setup_do_list_types_add('weekly-totals-satsun')
				self.setup_do_list_types_add('weekly-totals-sprint')
			elif list_type in ['report', 'report-activity',]:
				# See also: self.cli_opts.quick_list
				self.setup_do_list_types_add('daily-activity')
				self.setup_do_list_types_add('weekly-category-sprint')
				self.setup_do_list_types_add('daily-totals')
				self.setup_do_list_types_add('weekly-totals-sprint')
			else:
				# Not a group type.
				self.setup_do_list_types_add(list_type)
		# end: for list_type in self.cli_opts.do_list_types
		self.cli_opts.do_list_types = self.setup_list_types
		return ok
		# end: setup_do_list_types

class Hamsterer(pyoiler_argparse.Simple_Script_Base):

	def __init__(self, argparser=HR_Argparser):
		pyoiler_argparse.Simple_Script_Base.__init__(self, argparser)

	def go_main(self):
		log.debug('go_main: cli_opts: %s' % (self.cli_opts,))

		try:
			self.conn = sqlite3.connect(self.cli_opts.hamster_db_path)
			self.curs = self.conn.cursor()
		except Exception as err:
			log.fatal('Report failed: %s' % (str(err),))
			sys.exit(1)

		self.check_integrity()

		# See THIS_IS_THE_DEFAULT_BEHAVIOUR for the default behavior.

		if ((self.cli_opts.do_list_all)
			or ('all' in self.cli_opts.do_list_types)
		):
			self.list_all()

		list_types_set = set(self.cli_opts.do_list_types)
		unknown_types = list_types_set.difference(HR_Argparser.all_report_types)
		if unknown_types:
			log.warning('Unknown print list display output types: %s' % (unknown_types,))

		for list_type in self.cli_opts.do_list_types:
			self.process_list_type(list_type)

		self.conn.close()
		self.curs = None
		self.conn = None

		if self.cli_opts.cli_optsless:
			# Just a silly helper for newbies who run without options.
			# (Generally, after lots of usage, users will want to use
			# common sets of options; e.g., see [lb]'s time-lnb.sh.)
			print('')
			print('Using default report format. To see more options, try')
			print('  %s -r list' % (sys.argv[0],))
			print('For more general help, try')
			print('  %s --help' % (sys.argv[0],))

	def check_integrity(self):
		sql_select = "SELECT COUNT(*) FROM facts WHERE end_time IS NULL"
		try:
			self.curs.execute(sql_select)
			count = self.curs.fetchone()
			if count[0] not in (0, 1):
				log.fatal('DATA ERROR: Unexpected count: %s / query: %s' % (count[0], sql_select,))
				sql_select = "SELECT * FROM facts WHERE end_time IS NULL"
				self.print_output_generic_fcn_name(sql_select)
				print('You must fix one or more records to continue.')
				sys.exit(1)
		except Exception as err:
			log.fatal('SQL statement failed: %s' % (str(err),))
			log.fatal('sql_select: %s' % (sql_select,))

		# FIXME/LATER/#XXX: Check for gaps. If lots of facts, maybe just check
		# facts in specified time.

	def process_list_type(self, list_type):
		if list_type == 'gross-activity':
			self.list_gross_per_activity()
		elif list_type == 'gross-category':
			self.list_gross_per_category()
		elif list_type == 'gross-totals':
			self.list_gross_totals()
		elif list_type == 'daily-activity':
			self.list_daily_per_activity()
		elif list_type == 'daily-category':
			self.list_daily_per_category()
		elif list_type == 'daily-totals':
			self.list_daily_totals()
		elif list_type == 'weekly-activity-satsun':
			self.list_satsun_weekly_per_activity()
		elif list_type == 'weekly-category-satsun':
			self.list_satsun_weekly_per_category()
		elif list_type == 'weekly-totals-satsun':
			self.list_satsun_weekly_totals()
		elif list_type == 'weekly-activity-sprint':
			self.list_sprint_weekly_per_activity()
		elif list_type == 'weekly-category-sprint':
			self.list_sprint_weekly_per_category()
		elif list_type == 'weekly-totals-sprint':
			self.list_sprint_weekly_totals()
		elif list_type == 'egg':
			self.list_aggregate_results_report()
		elif list_type == 'all':
			# Already handled by list_all().
			pass
		else:
			log.warning('Not a list_type: %s' % (list_type,))

	# All the SQL functions fit to output.

	# NOTE: Ideally, we'd not trust user input and all self.curs.execute
	#       with a SQL command containing '?'s, and the user input would
	#       be passed as a list of strings so sqlite3 can defend against
	#       injection.
	#
	#       Alas, the python3.4 sqlite3 library on Mint 17.2 is:
	#
	#         >>> import sqlite3 ; print(sqlite3.sqlite_version)
	#         3.8.2
	#
	#       but we're really running
	#
	#         $ sqlite3 --version
	#         3.10.1 2016-01-13 21:41:56
	#
	#       and the printf command was added in 3.8.3. tl;dr missed it by 1!
	#       (And python3.5 from deadsnakes also uses 3.8.2.)
	#
	#       Linux Mint 18: import sqlite3 ; print(sqlite3.sqlite_version): 3.11.0.
	#

	SQL_EXTERNAL = True
	sqlite_v = sqlite3.sqlite_version.split('.')
	if (
		(int(sqlite_v[0]) > 3)
		or (int(sqlite_v[1]) > 8)
		or ((int(sqlite_v[1]) == 8) and (int(sqlite_v[2]) > 2))
	):
		SQL_EXTERNAL = False

	# FIXME/2016-09-26: Linux Mint 18: accessing sqlite3 internally not working.
	#                   In fact, nothing being returned, it feels like.
	# 2016-11-13/MEH: Since there's no easy way to update Python sqlite3
	#                 library (part of the core of python), might as well
	#                 stick to using the external binaries.
	SQL_EXTERNAL = True

	# A hacky way to add leading spaces/zeros: use substr.
	# CAVEAT: This hack will strip characters if number of characters exceeds
	# the substr bounds. So leave one more than expected -- if you don't see
	# a leading blank, be suspicious.
	SQL_DURATION = "substr('       ' || printf('%.3f', sum(duration)), -8, 8)"

	SQL_CATEGORY_FMTS = "substr('            ' || category_name, -12, 12)"

	def setup_sql_day_of_week(self):
		self.sql_day_of_week = (
			"""
			CASE CAST(strftime('%w', start_time) AS INTEGER)
				WHEN 0 THEN 'sun'
				WHEN 1 THEN 'mon'
				WHEN 2 THEN 'tue'
				WHEN 3 THEN 'wed'
				WHEN 4 THEN 'thu'
				WHEN 5 THEN 'fri'
					   ELSE 'sat'
			END AS day_of_week
			"""
		)
		self.str_params['SQL_DAY_OF_WEEK'] = self.sql_day_of_week

	def setup_sql_week_starts(self):
		self.str_params['SQL_WEEK_STARTS'] = self.cli_opts.week_starts

	def setup_sql_categories(self):
		self.sql_categories = ''
		self.sql_categories_ = ''
		if self.cli_opts.categories:
#			print('categories: %s' % (self.cli_opts.categories,))
			assert(isinstance(self.cli_opts.categories, list))
#
# FIXME: extend, not append?
#			self.sql_params.append(self.cli_opts.categories)
			self.sql_params.extend(self.cli_opts.categories)

			qmark_list = ','.join(['?' for x in self.cli_opts.categories])
			self.sql_categories = (
				#"AND categories.name IN (%s)" % (qmark_list,)
				"AND categories.search_name IN (%s)" % (qmark_list,)
			)
			name_list = ','.join(["'%s'" % (x,) for x in self.cli_opts.categories])
			self.sql_categories_ = (
				#" AND categories.name IN (%s)" % (name_list,)
				" AND categories.search_name IN (%s)" % (name_list,)
			)
		if not Hamsterer.SQL_EXTERNAL:
			self.str_params['REPORT_CATEGORIES'] = self.sql_categories
		else:
			self.str_params['REPORT_CATEGORIES'] = self.sql_categories_

	def setup_sql_dates(self):
		self.sql_beg_date = ''
		self.sql_beg_date_ = ''
		if self.cli_opts.time_beg:
#			print('time_beg: %s' % (self.cli_opts.time_beg,))
			assert(not isinstance(self.cli_opts.time_beg, list))
			self.sql_params.append(self.cli_opts.time_beg)
			self.sql_beg_date = "AND facts.start_time >= datetime(?)"
			self.sql_beg_date_ = (
				"AND facts.start_time >= datetime('%s')"
				% (self.cli_opts.time_beg,)
			)
		if not Hamsterer.SQL_EXTERNAL:
			self.str_params['SQL_BEG_DATE'] = self.sql_beg_date
		else:
			self.str_params['SQL_BEG_DATE'] = self.sql_beg_date_

		self.sql_end_date = ''
		self.sql_end_date_ = ''
		if self.cli_opts.time_end:
#			print('time_end: %s' % (self.cli_opts.time_end,))
			assert(not isinstance(self.cli_opts.time_end, list))
			self.sql_params.append(self.cli_opts.time_end)
			self.sql_end_date = "AND facts.start_time < datetime(?)"
			self.sql_end_date_ = (
				"AND facts.start_time < datetime('%s')"
				% (self.cli_opts.time_end,)
			)
		if not Hamsterer.SQL_EXTERNAL:
			self.str_params['SQL_END_DATE'] = self.sql_end_date
		else:
			self.str_params['SQL_END_DATE'] = self.sql_end_date_

	def setup_sql_activities(self):
		self.sql_activities = ''
		self.sql_activities_ = ''
		if self.cli_opts.activities:
#			print('activities: %s' % (self.cli_opts.activities,))
# FIXME: extend, not append?
			assert(isinstance(self.cli_opts.activities, list))
			self.sql_params.append(self.cli_opts.activities)
			qmark_list = ','.join(['?' for x in self.cli_opts.activities])
			# We probably don't need/want to be strict:
			#	self.sql_activities = (
			#		"AND activities.name in (%s)" % (qmark_list,)
			#		#"AND activities.search_name in (%s)" % (qmark_list,)
			#	)
			self.sql_activities = (
				"""
				(0
					%s
				)
				"""
				% (''.join(["OR activities.name LIKE '%%?%%'"
							for x in self.cli_opts.activities]),
				)
			)
			# We probably don't need/want to be strict:
			#name_list = ','.join(["'%s'" % (x,) for x in self.cli_opts.activities])
			#	self.sql_activities_ = (
			#		" AND activities.name in (%s)" % (name_list,)
			#		#" AND activities.search_name in (%s)" % (name_list,)
			#	)
			self.sql_activities_ = (
				"""
				(0
					%s
				)
				"""
				% (''.join(["OR activities.name LIKE '%%%s%%'" % (x,)
							for x in self.cli_opts.activities]),
				)
			)
		if not Hamsterer.SQL_EXTERNAL:
			self.str_params['SQL_ACTIVITY_NAME'] = self.sql_activities
		else:
			self.str_params['SQL_ACTIVITY_NAME'] = self.sql_activities_

	def setup_sql_tag_names(self):
		self.sql_tag_names = ''
		self.sql_tag_names_ = ''
		if self.cli_opts.tags:
#			print('tags: %s' % (self.cli_opts.tags,))
# FIXME: extend, not append?
			assert(isinstance(self.cli_opts.tags, list))
			self.sql_params.append(self.cli_opts.tags)
			qmark_list = ','.join(['?' for x in self.cli_opts.tags])
			self.sql_tag_names = (
				"""
				(0
					%s
				)
				"""
				% (''.join(["OR tags.name LIKE '%%?%%'"
							for x in self.cli_opts.tags]),
				)
			)
			self.sql_tag_names_ = (
				"""
				(0
					%s
				)
				"""
				% (''.join(["OR tags.name LIKE '%%%s%%'" % (x,)
							for x in self.cli_opts.tags]),
				)
			)
		if not Hamsterer.SQL_EXTERNAL:
			self.str_params['SQL_TAG_NAMES'] = self.sql_tag_names
		else:
			self.str_params['SQL_TAG_NAMES'] = self.sql_tag_names_

	def setup_sql_activities_and_tag_names(self):
		self.setup_sql_activities()
		self.setup_sql_tag_names()
		relation = ''
		if (self.str_params['SQL_ACTIVITY_NAME']
			and self.str_params['SQL_TAG_NAMES']
		):
			relation = ' OR ' if not self.cli_opts.and_acts_and_tags else ' AND '
		self.str_params['SQL_ACTS_AND_TAGS'] = '%s%s%s' % (
			self.str_params['SQL_ACTIVITY_NAME'],
			relation,
			self.str_params['SQL_TAG_NAMES'],
		)
		if self.str_params['SQL_ACTS_AND_TAGS']:
			self.str_params['SQL_ACTS_AND_TAGS'] = 'AND (%s)' % (
				self.str_params['SQL_ACTS_AND_TAGS'],
			)

	def print_output_generic_fcn_name(
		self,
		sql_select,
		use_header=False,
		output_split_days=False,
	):
		errs_found = False

		if self.cli_opts.show_sql:
			log.info(sql_select)

		if not Hamsterer.SQL_EXTERNAL:
# !!!!!
			log.fatal('sql_select: %s' % (sql_select,))
			log.fatal('sql_params: %s' % (self.sql_params,))
# WRONG ? substitution order!
# Mon, 26 Sep 2016 12:28:41 CRIT pyoiler_argparse # sql_params: ['exosite', '2016-09-17', datetime.date(2016, 9, 27)]


			try:
				self.curs.execute(sql_select, self.sql_params)
				print(self.curs.fetchall())
			except Exception as err:
				log.fatal('SQL statement failed: %s' % (str(err),))
				log.fatal('sql_select: %s' % (sql_select,))
				log.fatal('sql_params: %s' % (self.sql_params,))
		else:
			# sqlite3 output options: -column -csv -html -line -list
			try:
				sql_args = ['sqlite3',]
				if use_header:
					sql_args.append('-header')
				sql_args += [
					self.cli_opts.hamster_db_path,
					#'"%s;"' % (sql_select,),
					'%s;' % (sql_select,),
				]
				# Send stderr to /dev/null to suppress:
				#   -- Loading resources from /home/landonb/.sqliterc
				#   Error: near line 11: libspatialite.so.5.so: cannot open shared object file:
				#    No such file or directory
				# Hrm, I thought you could capture output in ret to process it
				# with run(), but shell=True dumps me on the sqlite3 prompt.
				if False:
					ret = subprocess.run(sql_args, stderr=subprocess.DEVNULL)
				if LEAK_SQLITE3_ERRORS:
					# We could use check_output to collect output lines.
					#ret = subprocess.check_output(sql_args, stderr=subprocess.DEVNULL)
					# DEBUGGING: Run without stderr redirected.
					# FIXME: Redirect STDERR so it doesn't print but so can can complain
					ret = subprocess.check_output(sql_args)
					ret = ret.decode("utf-8")
					lines = ret.split('\n')
					n_facts = 0
					for line in lines:
						if line:
							print(line)
							n_facts += 1
					#print('No. facts found: %d' % (n_facts,))
				else: # not LEAK_SQLITE3_ERRORS
					# ret.stdout will be None because everything goes to stdout.
					#ret = subprocess.run(sql_args, stderr=subprocess.PIPE)
					# Or we can capture stdout instead and strip that first blank line.
					ret = subprocess.run(sql_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

					curr_first_col = None
					last_first_col = None
					# Process stdout.
					outlns = ret.stdout.decode("utf-8").split('\n')
					for outln in outlns:
						if outln:
							if output_split_days:
								curr_first_col = outln[:outln.index('|')]
								#try:
								#	curr_first_col = outln[:outln.index('|')]
								#except ValueError:
								#	curr_first_col = None
								if ((last_first_col is not None)
									and (last_first_col != curr_first_col)
								):
									print('')
							print(outln)
							last_first_col = curr_first_col

					# Process errors.
					errlns = ret.stderr.decode("utf-8").split('\n')
					# These are some stderrs [lb's] .sqliterc trigger...
					re_loading_resource = re.compile(r'^-- Loading resources from /home/.*/.sqliterc$')
					re_error_libspatialite = re.compile(
	r'^Error: near line .*: libspatialite.*: cannot open shared object file: No such file or directory$'
					)
					for errln in errlns:
						if errln and not (
							re_loading_resource.match(errln)
							or re_error_libspatialite.match(errln)
						):
							errs_found = True
					if errs_found:
						print('Errors found!')
						print(errlns)
			except subprocess.CalledProcessError as err:
				log.fatal('Sql no bueno: %s' % (sql_select,))
				# Why isn't this printing by itself?
				log.fatal('err.output: %s' % (err.output,))
				raise

		return errs_found

	def setup_sql_setup(self):
		self.sql_params = []
		self.str_params = {}
		self.str_params['SQL_CATEGORY_FMTS'] = Hamsterer.SQL_CATEGORY_FMTS

	def list_all(self):
		self.setup_sql_setup()
		self.setup_sql_day_of_week()
		self.setup_sql_categories()
		self.setup_sql_dates()
		self.setup_sql_activities_and_tag_names()
		sql_select = """
			SELECT
				%(SQL_DAY_OF_WEEK)s
				, strftime('%%Y-%%m-%%d', facts.start_time)
				, strftime('%%H:%%M', facts.start_time)
				, strftime('%%H:%%M', facts.end_time)
				, substr(' ' || printf('%%.3f',
					24.0 * (julianday(facts.end_time) - julianday(facts.start_time))
					), -10, 10)
				AS duration
				, activities.name AS activity_name
				, tags.name
				, facts.description
				--, strftime('%%Y-%%j', facts.start_time) AS yrjul
			FROM facts
			JOIN activities ON (activities.id = facts.activity_id)
			JOIN categories ON (categories.id = activities.category_id)
			LEFT OUTER JOIN fact_tags ON (facts.id = fact_tags.fact_id)
			LEFT OUTER JOIN tags ON (fact_tags.tag_id = tags.id)
			WHERE 1
				%(REPORT_CATEGORIES)s
				%(SQL_BEG_DATE)s
				%(SQL_END_DATE)s
				%(SQL_ACTS_AND_TAGS)s
			ORDER BY facts.start_time, facts.id desc
		;
		""" % self.str_params
		print()
		print('ALL FACTS')
		#print('=========')
		print('===============================================================')
		self.print_output_generic_fcn_name(sql_select)

	def setup_sql_fact_durations(self):
		self.setup_sql_setup()
		self.setup_sql_day_of_week()
		self.setup_sql_week_starts()
		self.setup_sql_categories()
		self.setup_sql_dates()
		self.setup_sql_activities_and_tag_names()
		# Note: julianday returns a float, so multiple by units you want,
		#       *24 gives you hours, or *86400 gives you seconds.
		# Note: The current activity's end_time is NULL, so put in NOW.
		# Note: To avoid overlapping rows (bad data), an inner select
		#       figures out the max facts.id
		self.sql_fact_durations = """
			SELECT
				--strftime('%%Y-%%m-%%d', facts.start_time) AS yrjul
				strftime('%%Y-%%j', facts.start_time) AS yrjul
				, CAST(strftime('%%w', facts.start_time) AS integer) AS day_of_week
				--, CAST(julianday(start_time) AS integer) AS julian_day_group
				, CASE WHEN (CAST(strftime('%%w', facts.start_time) AS integer) - %(SQL_WEEK_STARTS)s) >= 0
				  THEN (CAST(strftime('%%w', facts.start_time) AS integer) - %(SQL_WEEK_STARTS)s)
				  ELSE (7 - %(SQL_WEEK_STARTS)s + CAST(strftime('%%w', facts.start_time) AS integer))
				  END AS pseudo_week_offset
				, facts.start_time
				, CASE WHEN facts.end_time IS NOT NULL
				  THEN 24.0 * (julianday(facts.end_time) - julianday(facts.start_time))
				  ELSE 24.0 * (julianday('now', 'localtime') - julianday(facts.start_time))
				  END AS duration
				, categories.search_name AS category_name
				--, categories.name AS category_name
				, activities.name AS activity_name
				--, activities.search_name AS activity_name
				, facts.activity_id
				, tag_names
				, facts.description
			--FROM facts
			FROM (
				SELECT
					max(facts.id) AS max_id
					, group_concat(tags.name) AS tag_names
				FROM facts
				JOIN activities ON (activities.id = facts.activity_id)
				LEFT OUTER JOIN fact_tags ON (facts.id = fact_tags.fact_id)
				LEFT OUTER JOIN tags ON (fact_tags.tag_id = tags.id)
				WHERE 1
					%(SQL_BEG_DATE)s
					%(SQL_END_DATE)s
					%(SQL_ACTS_AND_TAGS)s
				GROUP BY start_time, tags.id
			) AS max
			JOIN facts ON (max.max_id = facts.id)
			JOIN activities ON (activities.id = facts.activity_id)
			JOIN categories ON (categories.id = activities.category_id)
			WHERE 1
				%(REPORT_CATEGORIES)s
			GROUP BY facts.id
			ORDER BY facts.start_time
		""" % self.str_params
		self.str_params['SQL_FACT_DURATIONS'] = self.sql_fact_durations
		self.str_params['SQL_DURATION'] = Hamsterer.SQL_DURATION

	def list_gross_wrap(self, subtitle, cats, acts):
		print()
		print('GROSS %s TOTALS' % (subtitle,))
		print('===============================================================')
		self.list_weekly_wrap(
			group_by_categories=cats, group_by_activities=acts,
		)

	def list_gross_per_activity(self):
		self.list_gross_wrap('ACTIVITY', True, True)

	def list_gross_per_category(self):
		self.list_gross_wrap('CATEGORY', True, False)

	def list_gross_totals(self):
		self.list_gross_wrap('GROSS', False, False)

	def list_daily_per_activity(self):
		print()
		print('DAILY ACTIVITY TOTALS')
		#print('=====================')
		print('===============================================================')
		self.setup_sql_fact_durations()
		sql_select = """
			SELECT
				%(SQL_DAY_OF_WEEK)s
				, strftime('%%Y-%%m-%%d', min(julianday(start_time)))
				, %(SQL_DURATION)s as duration
				--, category_name
				, %(SQL_CATEGORY_FMTS)s
				, activity_name
				, tag_names
			FROM (%(SQL_FACT_DURATIONS)s) AS project_time
			GROUP BY yrjul, activity_id
			ORDER BY start_time, activity_name
		""" % self.str_params
		self.print_output_generic_fcn_name(sql_select, output_split_days=self.cli_opts.output_split_days)

	def list_daily_per_category(self):
		print()
		print('DAILY CATEGORY TOTALS')
		#print('=====================')
		print('===============================================================')
		self.setup_sql_fact_durations()
		sql_select = """
        SELECT
			%(SQL_DAY_OF_WEEK)s
            , strftime('%%Y-%%m-%%d', min(julianday(start_time))) AS start_time
            , %(SQL_DURATION)s AS duration
			, %(SQL_CATEGORY_FMTS)s
			, tag_names
        FROM (%(SQL_FACT_DURATIONS)s) AS project_time
        GROUP BY yrjul, category_name
        ORDER BY start_time, category_name
		""" % self.str_params
		self.print_output_generic_fcn_name(sql_select)

	def list_daily_totals(self):
		print()
		print('DAILY TOTALS')
		#print('============')
		print('===============================================================')
		self.setup_sql_fact_durations()
		sql_select = """
        SELECT
			%(SQL_DAY_OF_WEEK)s
            , strftime('%%Y-%%m-%%d', min(julianday(start_time)))
            , %(SQL_DURATION)s AS duration
			, tag_names
        FROM (%(SQL_FACT_DURATIONS)s) AS project_time
        GROUP BY yrjul
        ORDER BY start_time
		""" % self.str_params
		self.print_output_generic_fcn_name(sql_select)

	SQL_WEEK_START_JDAY = (
		"""
		julianday(start_time)
		- pseudo_week_offset
		+ 7
		"""
	)

	def list_weekly_wrap(self,
		group_by_categories=False,
		group_by_activities=False,
		sql_julian_day_of_year=None,
		week_num_unit='sprint_num',
	):
		group_bys = []
		self.setup_sql_fact_durations()
		if sql_julian_day_of_year:
			self.str_params['SQL_JULIAN_WEEK_INNER'] = (
				", CAST((%s) / 7 as integer) AS julianweek"
				% (sql_julian_day_of_year,)
			)
			self.str_params['FIRST_SPRINT_WEEK_NUM'] = self.cli_opts.first_sprint_week_num
			self.str_params['WEEK_NUM_UNIT'] = week_num_unit
			self.str_params['SQL_JULIAN_WEEK_OUTER'] = (
				", julianweek - %(FIRST_SPRINT_WEEK_NUM)s AS %(WEEK_NUM_UNIT)s"
				% self.str_params
			)
			group_bys.append('julianweek')
			header_cols = 'wkd|start_date|w|duration'
			header_dash = '---|----------|-|--------'
		else:
			# Don't group by a time interval.
			self.str_params['SQL_JULIAN_WEEK_INNER'] = ''
			self.str_params['SQL_JULIAN_WEEK_OUTER'] = ''
			header_cols = 'wkd|start_date|duration'
			header_dash = '---|----------|--------'
		sql_select_extra = ''
		sql_order_by_extra = ''
		#if self.cli_opts.categories or self.cli_opts.query:
		if group_by_activities:
			group_bys.append('tag_names')
		if group_by_categories:
			group_bys.append('category_name')
			sql_select_extra += ", %(SQL_CATEGORY_FMTS)s" % self.str_params
			header_cols += '|category_nom'
			header_dash += '|------------'
			sql_order_by_extra += ', category_name'
		if group_by_activities:
			group_bys.append('activity_name')
			sql_select_extra += ', activity_name'
			header_cols += '|activitiy_name'
			header_dash += '|--------------'
			sql_order_by_extra += ', activity_name'
		if False: # Something like this?:
			if self.cli_opts.activities or self.cli_opts.query:
				group_bys.append('activity')
			if self.cli_opts.tags or self.cli_opts.query:
				group_bys.append('tags')
			if self.cli_opts.query:
				group_bys.append('query')
		if group_by_activities:
			sql_select_extra += ', tag_names'
			header_cols += '|tag_names'
			header_dash += '|---------'
		sql_group_by = "GROUP BY %s" % (', '.join(group_bys),) if group_bys else ''
		self.str_params['SELECT_EXTRA'] = sql_select_extra
		self.str_params['ORDER_BY_EXTRA'] = sql_order_by_extra
		self.str_params['SQL_GROUP_BY'] = sql_group_by
		sql_select = """
			SELECT
				%(SQL_DAY_OF_WEEK)s
				-- This might be weekly ordering look funny:
				, strftime('%%Y-%%m-%%d', start_time) AS start_date
				-- So maybe try this:
				--, strftime('%%Y-%%m-%%d', start_week) AS start_date
				----, julianweek
				--, strftime('%%Y-%%m-%%d', start_week) AS start_week
				%(SQL_JULIAN_WEEK_OUTER)s
				, duration
				%(SELECT_EXTRA)s
			FROM (
				SELECT
					min(julianday(start_time)) AS real_start_time
					, julianday(start_time) - pseudo_week_offset AS start_time
					%(SQL_JULIAN_WEEK_INNER)s
					, %(SQL_DURATION)s AS duration
					, tag_names
					%(ORDER_BY_EXTRA)s
				FROM (%(SQL_FACT_DURATIONS)s) AS inner
				%(SQL_GROUP_BY)s
			) AS project_time
			ORDER BY start_date %(ORDER_BY_EXTRA)s
			""" % self.str_params
		##self.print_output_generic_fcn_name(sql_select, use_header=True)
		#print('wkd|start_date|w|duration|category_nom|activitiy_name|tag_names')
		#print('---|----------|-|--------|------------|--------------|---------')
		print(header_cols)
		print(header_dash)
		#      tue|2016-02-09|6|   0.167|    personal|Bathroom|
		self.print_output_generic_fcn_name(sql_select, use_header=False)

	SQL_WEEK_START_DNUM_SATSUN = (
		# LATER/#XXX: Add clock time to stamp for self.cli_opts.day_starts
		"""
		julianday(start_time)
		- julianday(strftime('%Y-01-01', start_time))
		+ CAST(strftime('%w', strftime('%Y-01-01', start_time)) AS integer)
		"""
	)

	def list_satsun_weekly_wrap(self, subtitle, cats, acts):
		print()
		print('SUN-SAT WEEKLY %s TOTALS' % (subtitle,))
		#print('===============%s=======' % ('=' * len(subtitle),))
		print('===============================================================')
		sql_julian_day_of_year = Hamsterer.SQL_WEEK_START_DNUM_SATSUN
		self.list_weekly_wrap(
			group_by_categories=cats,
			group_by_activities=acts,
			sql_julian_day_of_year=sql_julian_day_of_year,
			week_num_unit='week_num'
		)

	def list_satsun_weekly_per_activity(self):
		self.list_satsun_weekly_wrap('ACTIVITY', True, True)

	def list_satsun_weekly_per_category(self):
		self.list_satsun_weekly_wrap('CATEGORY', True, False)

	def list_satsun_weekly_totals(self):
		self.list_satsun_weekly_wrap('TOTAL', False, False)

	SQL_WEEK_START_DNUM_SPRINT = (
		"%s - julianday(strftime('%%Y-01-01', start_time))"
		% (SQL_WEEK_START_JDAY,)
	)

	def list_sprint_weekly_wrap(self, subtitle, cats, acts):
		print()
		print('SPRINT WEEKLY %s TOTALS' % (subtitle,))
		#print('==============%s=======' % ('=' * len(subtitle),))
		print('===============================================================')
		sql_julian_day_of_year = Hamsterer.SQL_WEEK_START_DNUM_SPRINT
		self.list_weekly_wrap(
			group_by_categories=cats,
			group_by_activities=acts,
			sql_julian_day_of_year=sql_julian_day_of_year,
			week_num_unit='sprint_num'
		)

	def list_sprint_weekly_per_activity(self):
		self.list_sprint_weekly_wrap('ACTIVITY', True, True)

	def list_sprint_weekly_per_category(self):
		self.list_sprint_weekly_wrap('CATEGORY', True, False)

	def list_sprint_weekly_totals(self):
		self.list_sprint_weekly_wrap('TOTAL', False, False)

	# 2016-11-13: Aggregate daily reporting.
	# See also the Tempo timesheet script that consumes the output of this.
	def list_aggregate_results_report(self):
		self.setup_sql_fact_durations()
		if False:
			self.print_output_generic_fcn_name(
				self.sql_fact_durations,
				output_split_days=self.cli_opts.output_split_days
			)
			return


		sql_select = """
			SELECT
				  fact_day
				, SUM(duration) AS duration
				, category_name
				, activity_name
				, activity_id
				, tag_names
				, GROUP_CONCAT(desc_and_durn, ",") AS eggregate
			FROM (
				SELECT
					  strftime('%%Y-%%m-%%d', start_time) AS fact_day
					, duration
					, category_name
					, activity_id
					, activity_name
					, tag_names
					--, '"' || description || ' [' || duration || ']"' AS desc_and_durn
					--, CASE
					--	WHEN description IS NULL THEN '"Misc. [' || duration || ']"'
					--	ELSE '"' || description || ' [' || duration || ']"'
					, CASE
						WHEN description IS NULL THEN '"Misc.","' || duration || '"'
						ELSE '"' || description || '","' || duration || '"'
					END AS desc_and_durn
				FROM (%(SQL_FACT_DURATIONS)s) AS project_time
			)
			GROUP BY fact_day, activity_id, tag_names
			ORDER BY fact_day, activity_id, tag_names
		""" % self.str_params
		self.print_output_generic_fcn_name(
			sql_select, output_split_days=self.cli_opts.output_split_days
		)

def main():
	hr = Hamsterer()
	hr.go()

if (__name__ == '__main__'):
	main()

