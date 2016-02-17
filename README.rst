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

You'll also want the hamster applet:
https://projecthamster.wordpress.com/

(And I've got a fork of the project with a few tweaks here:
https://github.com/landonb/hamster-applet.)

Options
=======

.. code-block:: text

    $ hamster_briefs.py --help

    usage: Hamster.db Analysis Tool [-h] [-v] [-b BEG_DATE] [-e END_DATE]
                                    [-c CATEGORY] [-a ACTIVITY] [-t TAG] [-X] [-0]
                                    [-1] [-2] [-4] [-5] [-r REPORT_TYPE] [-A] [-S]
                                    [-vv] [-w DAY_WEEK_STARTS]
                                    [-W FIRST_SPRINT_WEEK_NUM]
                                    [-D HAMSTER_DB_PATH]

    optional arguments:
      -h, --help            show this help message and exit
      -v, --version         show program's version number and exit
      -b BEG_DATE, --beg BEG_DATE
      -e END_DATE, --end END_DATE
      -c CATEGORY, --category CATEGORY
      -a ACTIVITY, --activity ACTIVITY
      -t TAG, --tag TAG
      -X, --and             if True, must match activities AND tags names, else OR
      -0, --today
      -1, --this-week
      -2, --last-two-weeks
      -4, --this-month
      -5, --last-two-months
      -r REPORT_TYPE, --report-types REPORT_TYPE
      -A, --list-all
      -S, --show-sql
      -vv, --verbose
      -w DAY_WEEK_STARTS, --day-week-starts DAY_WEEK_STARTS
      -W FIRST_SPRINT_WEEK_NUM, --first-sprint-week-num FIRST_SPRINT_WEEK_NUM
      -D HAMSTER_DB_PATH, --data HAMSTER_DB_PATH

