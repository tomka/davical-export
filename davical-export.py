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
       addresses[collection_id].append(data)
   elif data_type == 'vevent':
       calendars[collection_id].append(data)
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
       events[collection_id].append('\n'.join(filtered_data))
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

# Export into collection files
n_calendars = 0
for collection_id, calendar_entries in calendars.items():
    ics_filename = collection_id + '.ics'
    with codecs.open(os.path.join(args.target_dir, ics_filename), 'w', 'utf-8') as ics_file:
        ics_file.write(''.join(calendar_entries))
        n_calendars += len(calendar_entries)
n_addresses = 0
for collection_id, address_entries in addresses.items():
    vcf_filename = collection_id + '.vcf'
    with codecs.open(os.path.join(args.target_dir, vcf_filename), 'w', 'utf-8') as vcf_file:
        vcf_file.write(''.join(address_entries))
        n_addresses += len(address_entries)
n_events = 0
for collection_id, event_entries in events.items():
    ics_filename = collection_id + '-events.ics'
    with codecs.open(os.path.join(args.target_dir, ics_filename), 'w', 'utf-8') as ics_file:
        ics_file.write(''.join(event_entries))
        n_events += len(event_entries)

n_exported_collections = n_calendars + n_addresses + n_events
print('Finished - exported ' + str(n_exported_collections) +
   ' entries out of ' + str(len(collection_data)) +  ' total entries')
