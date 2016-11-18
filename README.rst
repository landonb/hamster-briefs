##############
HAMSTER BRIEFS
##############

*hamster.db time reporting and summarization tool.*

Usage
=====

Show what you've been working on today:

.. code-block:: bash

    ./hamster_briefs.py --today

    # Or more simply:

    ./hamster_briefs.py -0

Summarize just the time spent working on a specific category this week.

.. code-block:: bash

    ./hamster_briefs.py -c "category" --this-week

    # Or more simply:

    ./hamster_briefs.py -c "category" -1

Show a summary of time spent on certain activities for the current month.

.. code-block:: bash

    ./hamster_briefs.py -a "activity" -a "another" --this-month

Show hours you've spent on different activities for the current sprint
(which starts on a Saturday) for some given client.

.. code-block:: bash

    ./hamster_briefs.py \
        -c 'some_client' \
        -c 'client-tickets' \
        -w 'sat' \
        -1

Export last week's (last sprint's) entries as input to ``transform-brief.py``,
which lets you aggregate facts by activity, tags, and day, to be submitted
automatically to a timesheet service, like Atlassian's JIRA's Tempo.

.. code-block:: bash

    ./hamster_briefs.py \
        -c 'some_client' \
        -c 'client-tickets' \
        -w 'sat' \
        -2 \
        -E \
        > last_weeks_time.raw

Transform the aggregated facts in more easily editable, pretty-printed JSON:

.. code-block:: bash

    ./transform-brief.py \
        -r last_weeks_time.raw \
        > last_weeks_time.json

Edit ``last_weeks_time.json`` and then send it to JIRA Tempo.

.. code-block:: bash

    ./transform-brief.py \
        -T https://some.jira.service \
        -u my-user-name \
        -p my-pass-word \
        > last_weeks_time.json

Or write your own shim to some other API.

See ``./hamster_briefs.py --help`` for all the options.

Installation
============

Requires Python >= 3.5 (for ``subprocess.run``).

If your distro doesn't include Python 3.5, grab it from ``deadsnakes``.

.. code-block:: bash

    sudo add-apt-repository -y ppa:fkrull/deadsnakes
    sudo apt-get update -y
    sudo apt-get install -y python3.5

Python3 includes its own SQLite3 implementation, but if you'd like
to poke around your ``hamster.db``, install SQLite3.

.. code-block:: bash

    apt-cache install sqlite3 libsqlite3-dev

Also, Ubuntu 14.04 Python includes an older version of SQLite3
that doesn't support ``printf`` (added in 3.8.3), so if you're
on such a machine, install the latest version of sqlite3, e.g.,

.. code-block:: bash

    SQLITE_YEAR=2016
    SQLITE_BASE=sqlite-tools-linux-x86-3110100
    wget -N https://www.sqlite.org/${SQLITE_YEAR}/${SQLITE_BASE}.zip
    unzip -o -d ${SQLITE_BASE} ${SQLITE_BASE}.zip
    sudo /bin/cp -ar ${SQLITE_BASE}/${SQLITE_BASE}/sqlite3 /usr/bin/sqlite3
    sudo chmod 755 /usr/bin/sqlite3
    sudo chown root:root /usr/bin/sqlite3

... or you could install to some place on ``$PATH`` that precedes ``/usr/bin``.

- You'll also want the hamster applet:

  https://projecthamster.wordpress.com/

- I've got a fork of the project with a few (GUI) tweaks here:

  https://github.com/landonb/hamster-applet

Chjson
======

- You'll need the human JSON parser (because I like to comment JSON files, duh).

  https://github.com/landonb/chjson

  Follow the simple installation instructions on the ``chjson`` README.

Options
=======

.. code-block:: text

    $ hamster_briefs.py --help

    usage: verb / 3rd person present: briefs / 1.
    instruct or inform (someone) thoroughly, especially in preparation for a task.
           [-h] [-v] [-b BEG_DATE] [-e END_DATE] [-c CATEGORY] [-a ACTIVITY]
           [-t TAG] [--and] [-0] [-1] [-2] [-3] [-4] [-5] [-l] [-r REPORT_TYPE]
           [-A] [-E] [-S] [-vv] [-w DAY_WEEK_STARTS] [-W FIRST_SPRINT_WEEK_NUM]
           [-D HAMSTER_DB_PATH] [-s]

    optional arguments:
      -h, --help            show this help message and exit
      -v, --version         show program's version number and exit
      -b BEG_DATE, --beg BEG_DATE
      -e END_DATE, --end END_DATE
      -c CATEGORY, --category CATEGORY
      -a ACTIVITY, --activity ACTIVITY
      -t TAG, --tag TAG
      --and                 Match activities AND tags names, else just OR
      -0, --today
      -1, --this-week
      -2, --last-week
      -3, --last-two-weeks
      -4, --this-month
      -5, --last-two-months
      -l, --quick-list
      -r REPORT_TYPE, --report-types REPORT_TYPE
      -A, --list-all
      -E, --eggregate       Format as daily activity-tag aggregate with fact
                            descriptions [and fact times]
      -S, --show-sql
      -vv, --verbose
      -w DAY_WEEK_STARTS, --day-week-starts DAY_WEEK_STARTS
      -W FIRST_SPRINT_WEEK_NUM, --first-sprint-week-num FIRST_SPRINT_WEEK_NUM
                            Apply offset to sprint week (julianweek since Jan 1st)
      -D HAMSTER_DB_PATH, --data HAMSTER_DB_PATH
      -s, --split-days      Print newline between days. NOTE: Not honored by all
                            report types.

