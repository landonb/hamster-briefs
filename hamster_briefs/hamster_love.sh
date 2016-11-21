#!/bin/bash
# Last Modified: 2016.11.21
# Copyright: © 2016 Landon Bouma.

source_db=$1
target_db=$2

# Set EPREFIX to indent all the output.
EPREFIX=" "

echo_usage () {
  echo "USAGE: $0 path/to/most-recent-hamster.db path/to/an-older-hamster.db"
}

# Script inputs.

if [[ -z $source_db || -z $target_db ]]; then
  echo_usage
  exit 1
fi

# Files exist.

if [[ ! -f $source_db ]]; then
  echo "${EPREFIX}Failed: Not a file: $source_db"
  exit 1
fi
if [[ ! -f $target_db ]]; then
  echo "${EPREFIX}Failed: Not a file: $target_db"
  exit 1
fi

# Basic diff lets us exit real early.

diff $source_db $target_db &> /dev/null
if [[ $? -eq 0 ]]; then
  echo "${EPREFIX}  src: $source_db"
  echo "${EPREFIX}  dst: $target_db"
  echo "${EPREFIX}No-op: Nothing changed -- clean diff."
  exit 0
fi

# Target not younger than source; source updated more recently than target.

# Compare the modifications times of the files' timestamps.
if [[ $target_db -nt $source_db ]]; then
  echo "${EPREFIX}Skipping: Not gonna happen: the seedee/target is newer than the seeder/source."
  echo "${EPREFIX}- Source (older): $source_db"
  echo "${EPREFIX}- Target (newer): $target_db"
  exit 1
fi

# VERSION versions.

source_vers=$(echo "SELECT version FROM version;" | sqlite3 ${source_db} 2> /dev/null)
target_vers=$(echo "SELECT version FROM version;" | sqlite3 ${target_db} 2> /dev/null)

if false; then
  echo $source_vers
  echo $target_vers
fi

if [[ -z $source_vers || -z $target_vers ]]; then
  echo "${EPREFIX}Failed: Unable to read one or both database versions:"
  echo "${EPREFIX}  source_vers: $source_vers / target_vers: $target_vers"
  exit 1
fi

if [[ $source_vers != $target_vers ]]; then
  echo "${EPREFIX}Failed: Version mismatch:"
  echo "${EPREFIX}  source_vers ($source_vers) "'!'"= target_vers ($target_vers)"
  exit 1
fi

# FACTS ids.

source_max_fact_id=$(echo "SELECT MAX(id) FROM facts;" | sqlite3 ${source_db} 2> /dev/null)
target_max_fact_id=$(echo "SELECT MAX(id) FROM facts;" | sqlite3 ${target_db} 2> /dev/null)

if false; then
  echo $source_max_fact_id
  echo $target_max_fact_id
fi

if [[ -z $source_max_fact_id || -z $target_max_fact_id ]]; then
  echo "${EPREFIX}Failed: Unable to read one or both max fact ids:"
  echo "${EPREFIX}  source_max_fact_id: $source_max_fact_id / target_max_fact_id: $target_max_fact_id"
  exit 1
fi

if [[ $source_max_fact_id == $target_max_fact_id ]]; then
  echo "${EPREFIX}No-op: Facts match"'!'
  echo "${EPREFIX}  source_max_fact_id ($source_max_fact_id) == target_max_fact_id ($target_max_fact_id)"
# FIXME: This might not really be the appropriate response.
  exit 0
fi

if [[ $source_max_fact_id -lt $target_max_fact_id ]]; then
  echo "${EPREFIX}Failed: What gives, dude? The source max fact ID ($source_max_fact_id)"
  echo "${EPREFIX}        is less than the target max fact ID ($target_max_fact_id)"
  exit 1
elif [[ $source_max_fact_id -eq $target_max_fact_id ]]; then
  echo "${EPREFIX}Failed: BEWILDERMENT: How is one not less than the other when we already confirmed they're not equal?"
  exit 2
# else, we're good: $source_max_fact_id -gt $target_max_fact_id
fi

# Last FACTS.

# FIXME: MAKE BACKLOG item: If last rows don't match, merge differences.
#        In Timesheet Hamster, you would have to compare rows in reverse
#        by ID until you find an exact match, and then you know that
#        all earlier rows match (you could write additional code to
#        verify this), and then you can merge all the later rows from
#        each db -- in the app, you'd separate the times from each db
#        and have the user perform some sort of merge.

# FIXME: This code assumes it'll find at least two rows in each table,
#        but I'm developing this, and my hamster.db has plenty of rows.

# This block is useless. If you leave one machine with an open fact, and
# then on the other machine edit that fact, the fact gets a new ID, and
# what's then the last_common_id is no longer used by any fact in source.
if false; then

  # Use the max target fact ID, which is less than the max source fact ID.
  last_common_id=$target_max_fact_id
  source_last_common_fact=$(echo "SELECT * FROM facts WHERE id = $last_common_id;" \
    | sqlite3 ${source_db} 2> /dev/null)
  target_last_common_fact=$(echo "SELECT * FROM facts WHERE id = $last_common_id;" \
    | sqlite3 ${target_db} 2> /dev/null)

  if false; then
    echo $source_last_common_fact
    echo $target_last_common_fact
  fi

  if [[ -z $source_last_common_fact || -z $target_last_common_fact ]]; then
    echo "${EPREFIX}Failed: Hrm. Either or both of the last common facts is missing?"
    echo "${EPREFIX}       source_max_fact_id: $source_max_fact_id"
    echo "${EPREFIX}       target_max_fact_id: $target_max_fact_id"
    echo "${EPREFIX}           last_common_id: $last_common_id"
    echo "${EPREFIX}  source_last_common_fact: $source_last_common_fact"
    echo "${EPREFIX}  target_last_common_fact: $target_last_common_fact"
    exit 1
  fi
fi

# MEH: This is a cxpx of the last bit of code.
source_penultimate_fact_id=$(echo "SELECT MAX(id) FROM facts WHERE id < $target_max_fact_id;" \
  | sqlite3 ${source_db} 2> /dev/null)
target_penultimate_fact_id=$(echo "SELECT MAX(id) FROM facts WHERE id < $target_max_fact_id;" \
  | sqlite3 ${target_db} 2> /dev/null)
if [[ -z $source_penultimate_fact_id || -z $target_penultimate_fact_id ]]; then
  echo "${EPREFIX}Failed: Unable to read one or both penultimate fact ids:"
  echo "${EPREFIX}  source_penultimate_fact_id: $source_penultimate_fact_id"
  echo "${EPREFIX}  target_penultimate_fact_id: $target_penultimate_fact_id"
  exit 1
fi
if [[ $source_penultimate_fact_id -eq $target_penultimate_fact_id ]]; then
  penultimate_id=$source_penultimate_fact_id
elif [[ $source_penultimate_fact_id == $target_penultimate_fact_id ]]; then
  echo "${EPREFIX}Failed: Unexpected code path"'!'" penultimate_fact_id not -eq but ==?"
  exit 1
elif [[ $source_penultimate_fact_id -lt $target_penultimate_fact_id ]]; then
  penultimate_id=$source_penultimate_fact_id
elif [[ $source_penultimate_fact_id -gt $target_penultimate_fact_id ]]; then
  penultimate_id=$target_penultimate_fact_id
else
  echo "${EPREFIX}Failed: Unexpected code path"'!'" penultimate_fact_ids not any of: ==, -eq, -lt, -gt??"
  exit 1
fi
source_penultimate_fact=$(echo "SELECT * FROM facts WHERE id = $penultimate_id;" \
  | sqlite3 ${source_db} 2> /dev/null)
target_penultimate_fact=$(echo "SELECT * FROM facts WHERE id = $penultimate_id;" \
  | sqlite3 ${target_db} 2> /dev/null)
if false; then
  echo $source_penultimate_fact
  echo $target_penultimate_fact
fi
if [[ -z $source_penultimate_fact || -z $target_penultimate_fact ]]; then
  echo "${EPREFIX}Failed: Hrm. Either or both of the last common facts is missing?"
  echo "${EPREFIX}  source_penultimate_fact: $source_penultimate_fact"
  echo "${EPREFIX}  target_penultimate_fact: $target_penultimate_fact"
  exit 1
fi

# Tell user about what matches or not.
if [[ $source_last_common_fact != $target_last_common_fact ]]; then
  echo
  echo "${EPREFIX}BE CAREFUL: The last common rows do not match."
  echo
  echo "${EPREFIX}  source_penultimate_fact: $source_penultimate_fact"
  echo "${EPREFIX}  target_penultimate_fact: $target_penultimate_fact"
  echo "${EPREFIX}  source_last_common_fact: $source_last_common_fact"
  echo "${EPREFIX}  target_last_common_fact: $target_last_common_fact"
  echo
fi
if [[ $source_penultimate_fact != $target_penultimate_fact ]]; then
  echo
  echo "${EPREFIX}BE CAREFUL: The next-to-last/second-to-last/second-last common rows do not match."
  echo
  echo "${EPREFIX}  id: $penultimate_id"
  echo "${EPREFIX}  source_penultimate_fact: $source_penultimate_fact"
  echo "${EPREFIX}  target_penultimate_fact: $target_penultimate_fact"
  echo
fi

# FIXME/ts-n: Here's where we just ask for permission now.
# For Timesheet Hamster, we'll have to do this without user interaction.

echo "${EPREFIX}Ready to update hamster.db."
echo
echo "${EPREFIX}   /bin/cat \\"
echo "${EPREFIX}      $source_db \\"
echo "${EPREFIX}    > $target_db"
echo
echo -n "Ready? [y/n] "
read -e YES_OR_NO

echo OK

if [[ ${YES_OR_NO^^} != "Y" ]]; then
  echo "${EPREFIX}Stopping due to user lack of interest."
  exit 0
fi

# Kill_hamster_processes.
echo "Killalling hamster-service hamster-indicator..."
#sudo killall hamster-service hamster-indicator
killall hamster-service hamster-indicator
function errexit_cleanup() {
  # Do we get the exit code? Not sure...
echo "FIXME: Cleanup this fcn. (errexit_cleanup)"
  echo "${EPREFIX}\$?: $?"
  echo "${EPREFIX}\$*: $*"
  echo "${EPREFIX}\$1: $1"
  #hamster-indicator &
  hamster-indicator &> /dev/null &
  # Return exit code if we got it...
  #exit $*
  exit 1
}
trap errexit_cleanup EXIT

# Make backups. Just in case.
# 2016-10-09: This fcn. is not that important if you use git.
#             But it's harmless enough to ignore.
manage_hamster_backups () {
  dbfile=$1
  dbname=$(basename $dbfile)
  dbpath=$(dirname $dbfile)
  mkdir -p $dbpath/hamster.bkups
  n_backup=2
  if [[ -f $dbpath/hamster.bkups/$dbname-$n_backup ]]; then
    /bin/rm $dbpath/hamster.bkups/$dbname-$n_backup
  fi
  p_backup=$(($n_backup-1))
  while [[ $n_backup -gt 1 ]]; do
    if [[ -f $dbpath/hamster.bkups/$dbname-$p_backup ]]; then
      /bin/mv -f \
        $dbpath/hamster.bkups/$dbname-$p_backup \
        $dbpath/hamster.bkups/$dbname-$n_backup
    fi
    n_backup=$(($n_backup-1))
    p_backup=$(($n_backup-1))
  done
  /bin/cp -a $dbfile $dbpath/hamster.bkups/$dbname-$n_backup
}
manage_hamster_backups $target_db

# Inline overwrite -- hamster-applet doesn't need to be restarted,
# but if you're looking at the overview, you might need to change
# days and back to see changes.
/bin/cat $source_db > $target_db

# Start-hamster-service.
#hamster-indicator &
hamster-indicator &> /dev/null &

# Unhook errexit_cleanup.
trap - EXIT

