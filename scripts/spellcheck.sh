#!/bin/bash

# This script checks all ReSt files in the documentation repository
# for spelling errors and prints unknown words.
#
# To regenerate the dictionary remove `spellcheck/dictionary.txt` and run
# this script with no arguments.

shopt -s nullglob

dict_filename=scripts/dictionary.txt
es_aspell_command="aspell --encoding utf-8 --master=es -M --ignore 3"

# FIXME: We are explicitly ignoring files from the igalians directory, because
# it contains JavaScript. This should figure out a way to strip out HTML
# Rst, perhaps by using pandoc.
readarray -d '' rst_sources < <(find CPEUM -name "*.rst" -print0)
mode="check"

# Error if running in list (CI) mode and there isn't a dictionary file;
# creating one in CI won't do any good :(
if [[ "$1" == "check" && ! -f "$dict_filename" ]]; then
    echo "No dictionary file found! A dictionary file is required in CI!"
    exit 1
fi

if [[ ! -f "$dict_filename" ]]; then
    # Pre-check mode: generates dictionary of words aspell consider typos.
    # After user validates that this file contains only valid words, we can
    # look for typos using this dictionary and some default aspell dictionary.
    echo "Scanning files to generate dictionary file '$dict_filename'."
    echo "Please check that it doesn't contain any misspellings."

    echo "personal_ws-1.1 es 0 utf-8" > "$dict_filename"
    cat "${rst_sources[@]}" | \
        $es_aspell_command list | \
        sort -u >> "$dict_filename"
fi

# List (default) mode: scan all files, report errors.
declare -i retval=0

echo " (      (            (      (                   )                     )  "
echo " )\ )   )\ )         )\ )   )\ )       (     ( /(           (      ( /(  "
echo "(()/(  (()/(   (    (()/(  (()/(       )\    )\\())  (       )\     )\\()) "
echo " /(_))  /(_))  )\    /(_))  /(_))    (((_)  ((_)\   )\    (((_)  |((_)\  "
echo "(_))   (_))   ((_)  (_))   (_))      )\___   _((_) ((_)   )\___  |_ ((_) "
echo "/ __|  | _ \  | __| | |    | |      ((/ __| | || | | __| ((/ __| | |/ /  "
echo "\__ \  |  _/  | _|  | |__  | |__     | (__  | __ | | _|   | (__    ' <   "
echo "|___/  |_|    |___| |____| |____|     \___| |_||_| |___|   \___|  _|\_\  "
echo "                                                                         "
for fname in "${rst_sources[@]}"; do
    command=$(cat $fname | \
        $es_aspell_command --personal\="./$dict_filename" list | \
        sort -u)
    if [[ -n "$command" ]]; then
        echo "Unknown words found in $fname:"
        for line in $command; do
            echo "    🡆  $line"
        done
        retval=1
    fi
done

exit "$retval"
