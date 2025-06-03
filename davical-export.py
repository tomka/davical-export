#!/usr/bin/python
#
# davical-export.py attempts to export all davical collections into individual
# files, one per collection (tied each to a user). Run it as a user that can
# connect to the database (e.g. postgres).
#
# Calendars (VCALENDAR) and events (VTODO, VEVENT, VJOURNAL) are stored as .ics
# files. Contacts are stored as .vcf files. Each files is named
# "<user>-<collection>.<extension>".
#
# This software is provided as-is and is licensed under the GPLv3 license.

import argparse
import codecs
import json
import os
import sys
import subprocess
from collections import defaultdict

parser = argparse.ArgumentParser(
                    prog='davical export',
                    description='Export all DAViCal collections to the export '
                        'folder. Each collection of each user is stored as its '
                        'own .ics/.vcf file. Those collections can then be '
                        'imported into other DAV stores likee .g. Nextcloud. '
                        'Make sure the target directory is writable by the '
                        'user running the script (usually postgres).',
                    epilog='Text at the bottom of help')
parser.add_argument('--target-dir', default='/tmp/dav-export')
parser.add_argument('--one-file-per-entry', '-s',  action='store_true', default=False)
args = parser.parse_args()

print('Exporting DAV collections to directory "' + args.target_dir + '"\n')

collection_data_json = subprocess.check_output(['psql', 'davical', '-Atc',
    "select json_agg(d) from ("
    "select split_part(dav_name, '/', 2) as user, split_part(dav_name, '/', 3) as collection, "
    "split_part(dav_name, '/', 4) as filename, caldav_type, caldav_data from caldav_data) d;"])
collection_data = json.loads(collection_data_json)

# Collect user-colllection lists
calendars = defaultdict(list)
addresses = defaultdict(list)
events = defaultdict(list)

n_fixed_events = 0

for row in collection_data:
   collection_id = row["user"] + '-' + row["collection"]
   data_type = row["caldav_type"].lower()
   data = row["caldav_data"]
   if data_type == 'vcard':
       addresses[collection_id].append(row)
   elif data_type == 'vevent':
       calendars[collection_id].append(row)
   elif data_type == 'vtodo':
       # Extract VEVENTs, VTODOs, and VJOURNALs from th enclosing VCALENDAR
       filtered_data = []
       valid_starts = ['begin:vevent', 'begin:vtodo', 'begin:vjournal']
       valid_ends = ['end:vevent', 'end:vtodo', 'end:vjournal']
       in_section = False
       fixed = False
       for line in data.split('\n'):
            line = line.strip('\r')
            test_line = line.lower()
            if test_line in valid_starts:
                in_section = True
            elif not in_section:
                fixed = True
                continue
            if test_line in valid_ends and in_section:
                in_section = False
            filtered_data.append(line)
       if fixed:
           n_fixed_events += 1

       if not filtered_data:
           raise Exception("No valid event data found: " + str(row))
       row['caldav_data'] = '\n'.join(filtered_data)
       events[collection_id].append(row)
   else:
       raise Exception('Unknown data type: ' + data_type)

print("Address collections:")
print(', '.join(addresses.keys()))
print('')
print("Calendar collections:")
print(', '.join((calendars.keys())))
print('')
print("Event collections (fixed " + str(n_fixed_events) + "):")
print(', '.join((events.keys())))
print('')

if not os.path.exists(args.target_dir):
    os.makedirs(args.target_dir)

def write_collection_files(entries, extension='ics'):
    n_entries = 0
    for collection_id, collection_entries in entries.items():
        collection_filename = collection_id + '.' + extension
        with codecs.open(os.path.join(args.target_dir, collection_filename), 'w', 'utf-8') as collection_file:
            collection_file.write(''.join(map(lambda x: x['caldav_data'], collection_entries)))
            n_entries += len(collection_entries)
    return n_entries

def write_collection_item_files(entries, data_type, extension='ics'):
    n_entries = 0
    for collection_id, collection_entries in entries.items():
        target_dir = os.path.join(args.target_dir, collection_id + '-' + data_type)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        for entry in collection_entries:
            item_filename = collection_id + '-' + entry['filename']
            if not item_filename.endswith(extension):
                item_filename += '.' + extension
            item_path = os.path.join(target_dir, item_filename)
            with codecs.open(item_path, 'w', 'utf-8') as item_file:
                item_file.write(entry['caldav_data'])
                n_entries += 1
    return n_entries

# Export into collection files
if args.one_file_per_entry:
    n_calendars = write_collection_item_files(calendars, 'calendar', 'ics')
    n_addresses = write_collection_item_files(addresses, 'addresses', 'vcf')
    n_events = write_collection_item_files(events, 'events', 'ics')
else:
    n_calendars = write_collection_files(calendars, 'ics')
    n_addresses = write_collection_files(addresses, 'vcf')
    n_events = write_collection_files(events, 'ics')

n_exported_collections = n_calendars + n_addresses + n_events
print('Finished - exported ' + str(n_exported_collections) +
   ' entries out of ' + str(len(collection_data)) +  ' total entries')
