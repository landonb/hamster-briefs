##############
HAMSTER BRIEFS
##############

*hamster.db time reporting and summarization tool.*

Usage
=====

Show what you've been working on today:

.. code-block:: bash

    hamster-briefs --today

    # Or more simply:

    hamster-briefs -0

Summarize just the time spent working on a specific category this week.

.. code-block:: bash

    hamster-briefs -c "category" --this-week

    # Or more simply:

    hamster-briefs -c "category" -1

Show a summary of time spent on certain activities for the current month.

.. code-block:: bash

    hamster-briefs -a "activity" -a "another" --this-month

Show hours you've spent on different activities for the current sprint for some
given client. The ``-w 'sat'`` indicates that the sprint started on Saturday.

.. code-block:: bash

    hamster-briefs \
        -c 'some_client' \
        -c 'client-tickets' \
        -w 'sat' \
        -1

Prepare last week's time sheet. First output the entries from the
sprint, aggregated by activity, tags, and day. This includes all
your priceless comments.

.. code-block:: bash

    hamster-briefs -2 -E > last_weeks_time.raw

Convert the SQLite3 output to a JSON file that you can verify
and edit, if you want, before uploading it to a time tracking
service, such as Atlassian JIRA Tempo.

.. code-block:: bash

    ./transform-brief.py -r last_weeks_time.raw > last_weeks_time.json

Edit ``last_weeks_time.json``.

And then send the work log entries to JIRA Tempo.

.. code-block:: bash

    ./transform-brief.py \
        -T https://some.jira.service \
        -u my-user-name \
        -p my-pass-word \
        > last_weeks_time.json

Or write your own shim to some other API.

See ``hamster-briefs --help`` for all the options.

Installation
============

Pip!
----

Install ``hamster-briefs`` with ``pip``::

    pip3 install --user git+https://github.com/landonb/hamster-briefs \
        -r https://raw.githubusercontent.com/landonb/hamster-briefs/master/requirements.txt

NOTE: This populates a local directory, ``src/``, with the dependencies,
which are git repositories.

You can choose another path for the cloned git repos using ``--src``, e.g.,::

    pip3 install --user git+https://github.com/landonb/hamster-briefs \
        -r https://raw.githubusercontent.com/landonb/hamster-briefs/master/requirements.txt \
        --src /path/to/a/different/source/checkout/src

(I'll get this project on `PyPI <https://pypi.python.org/pypi>`__
someday and then you won't have to do this dance.)

Devs
----

If you'd like to check out the source and install that, try:

.. code-block:: bash

    cd /animalia/chordata/mammalia/rodentia/cricetidae/cricetinae

    git clone https://github.com/landonb/hamster-briefs.git

    cd hamster-briefs

    pip3 install --user -r requirements.txt .

    # Or, if you're adventurous:
    #
    #  sudo pip3 install -r requirements.txt .

But you probably don't want the dependencies under ``hamster-briefs``,
so grab them first and *then* install ``hamster-briefs``.:

.. code-block:: bash

    cd /hamstercraft

    git clone https://github.com/landonb/pyoiler-argparse.git
    git clone https://github.com/landonb/pyoiler-inflector.git
    git clone https://github.com/landonb/pyoiler-logging.git
    git clone https://github.com/landonb/pyoiler-timedelta.git
    git clone https://github.com/landonb/termcolor.git

    while IFS= read -r -d '' pyoiler_path; do
        pushd ${pyoiler_path}
        python setup.py sdist
        popd
    done < <(find . -maxdepth 1 -type d -name "pyoiler-*" -print0)

    git clone https://github.com/landonb/hamster-briefs.git

    cd /hamstercraft/hamster-briefs

    pip install \
        --find-links /hamstercraft/pyoiler-argparse/dist \
        --find-links /hamstercraft/pyoiler-inflector/dist \
        --find-links /hamstercraft/pyoiler-logging/dist \
        --find-links /hamstercraft/pyoiler-timedelta/dist \
        --find-links /hamstercraft/termcolor/dist \
        --user \
        --verbose \
        -e .

Or better yet:

.. code-block:: bash

    source_pyoilers_editable_user_install () {
        while IFS= read -r -d '' pyoiler_path; do
            echo "============================================"
            echo "Preparing ${pyoiler_path}"
            echo "============================================"
            pushd ${pyoiler_path} &> /dev/null
            pip3 install --user -e .
            popd &> /dev/null
        done < <(find . -maxdepth 1 -type d -name "pyoiler-*" -print0)
    }

    cd /pyoilerplate
    source_pyoilers_editable_user_install
    cd /pyoilerplate/termcolor
    pip3 install --user -e .

    # MAYBE/2016-11-28: Having issues in 14.04 (where py3.5 comes from deadsnakes).
    # Is this necessary:
    #  sudo pip3 install setuptools

    cd /hamstercraft/hamster-briefs
    pip3 install --user -v -e .

Dependencies
============

Python >=3.5
------------

Requires Python >= 3.5 (for ``subprocess.run``).

If your distro doesn't include Python 3.5, grab it from ``deadsnakes``.

.. code-block:: bash

    sudo add-apt-repository -y ppa:fkrull/deadsnakes
    sudo apt-get update -y
    sudo apt-get install -y python3.5

SQLite3
-------

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

Hamster Applet
--------------

- You'll also want the hamster applet:

  https://projecthamster.wordpress.com/

- I've got a fork of the project with a few (GUI) tweaks here:

  https://github.com/landonb/hamster-applet

Chjson
------

If you're like me and like to add comments to JSON, install ``chjson``.

I curate my timesheets before submitting them, and I store them for
all eternity, so it's nice to be able to mark 'em up with comments.

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

