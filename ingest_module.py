#This file is part of the Hypertimeline Project
#February 2024

import argparse
import csv
import datetime
import itertools as it
import locale
import os
import sys
from typedb.driver import *


cols = []
datatypes = []
coincidences = []
precedences = []


parser = argparse.ArgumentParser(description='Inserts time domains and time domain entries into the database.')
parser.add_argument('filename', metavar='f', help='the .tsv file that contains the time domains and their entries')
parser.add_argument('time_domains', nargs="+", help="Specify which columns contain time domains and their data type, e.g., 1=datetime 2=long", metavar="COL_NUMBER=TYPE")
parser.add_argument('-db', '--database', dest='database_name', help="Specify the database's name", default="Hypertimelining_III")
parser.add_argument('-c', '--coincidence', dest='coincidences_string', help="Specify the time domains with coincidence using a,b,c")
parser.add_argument('-p', '--precedence', dest='precedences_string', help="Specify the time domains with precedence using a<b")
parser.add_argument('-e', '--encoding', dest='encoding', default="utf-16", help="Specify the encoding used in the .tsv file, default: utf-16")
parser.add_argument('-t', '--timestamp-format', dest='timestamp_format_string', default="%d/%m/%Y  %H:%M:%S", help="Specify the format string used for the timestamps in the .tsv file, default: %d/%m/%Y  %H:%M:%S, shortcut for sqlite-file-example: 'firefox'")
parser.add_argument('-m', '--metadata-col', dest='meta_data_col', type=int, help="Column index (0-based) for the metadata string")



args = parser.parse_args()
print(args)

database_name = args.database_name
timestamp_format_string = ""
if args.timestamp_format_string == "firefox":
    timestamp_format_string = "%Y-%m-%d %H:%M:%S"
else:
    timestamp_format_string = args.timestamp_format_string


tsv_f = open(args.filename, encoding=args.encoding)
tsv_file = csv.reader(tsv_f, delimiter="\t")
tsv_lines = []
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8') #To have comma-separated numbers as numbers

for domain in args.time_domains:
    col_and_type = domain.split("=")
    cols.append(locale.atoi(col_and_type[0]))
    if len(col_and_type) != 2:
        print("Error: Please specify each time domain in the following format: Column-number=datatype ; example: 1=long")
        sys.exit(1)
    datatype = col_and_type[1]
    if datatype == "long" or datatype == "datetime":
        datatypes.append(col_and_type[1])
    elif datatype == "l":
        datatypes.append("long")
    elif datatype == "t" or datatype == "d":
        datatypes.append("datetime")
    else:
        print("Error: Could not determine datatype for col {}. Should be long (l) or datetime (t)".format(col_and_type[0]))
        sys.exit(1)

if args.coincidences_string == "" and args.precedences_string == "":
    print("Warning: Neither precedences nor coincidences specified. This might not be what you want as reasoning will not give much more information.".format(col_and_type[0]))
    sys.exit(1)
    

if args.coincidences_string:
    coincidences_string_arr = args.coincidences_string.split(",")
    #print(coincidences_string_arr)
    coincidences = [locale.atoi(x) for x in coincidences_string_arr]
    coincidences = list(it.combinations(coincidences, 2)) #would also be enough to insert them in a pair-wise chain and not every combination, but this is a one-liner
else:
    coincidences = []
print("Coincidences: {}".format(coincidences))

if args.precedences_string:
    precedences_string_arr = args.precedences_string.split(",")
    #print(precedences_string_arr)
    for prec_str in precedences_string_arr:
        if "<" in prec_str:
            prec_pair = prec_str.split("<")
            precedences.append((locale.atoi(prec_pair[0]), locale.atoi(prec_pair[1])))
        elif ">" in prec_str:
            prec_str.split(">")
            precedences.append((locale.atoi(prec_pair[1]), locale.atoi(prec_pair[0])))
        else:
            print("Parsing Error: Please specify  precedence in the format of: col_A<col_B,col_B<col_C")
else:
    precedences = []
print("Precedence: {}".format(precedences))

meta_data_col = args.meta_data_col
print(f"Meta-Data: {meta_data_col}")

for line in tsv_file:
    tsv_lines.append(line)
tsv_header = tsv_lines.pop(0)

print(tsv_lines)

with TypeDB.core_driver("localhost:1729") as driver:
    print("Connecting to the server")

    datatypes_dict = {}
    for i in range(0, len(cols)):
    	datatypes_dict[cols[i]] = datatypes[i]

    with driver.session(database_name, SessionType.DATA) as session:
        print("Connecting to the `{}` database".format(database_name))
        ## session is open
        get_domain_query = "match $td isa time_domain, has time_domain_reference \"{}\"; get $td;"
        insert_domain_query = "insert $td isa time_domain, has time_domain_reference \"{}\";"
        get_datetime_entry_query = "match $entry isa time_domain_entry, has time_domain_reference \"{}\", has value_datetime {}; get $entry;"
        # Add is_active=true to all time_domain_entry
        insert_datetime_entry_query = "insert $entry isa time_domain_entry, has time_domain_reference \"{}\", has value_datetime {}, has is_active true, has meta_data \"{}\";"
        get_long_entry_query = "match $entry isa time_domain_entry, has time_domain_reference \"{}\" , has value_long {}; get $entry;" 
        # Add is_active=true to all time_domain_entry
        insert_long_entry_query = "insert $entry isa time_domain_entry, has time_domain_reference \"{}\" , has value_long {}, has is_active true, has meta_data \"{}\";" 
        add_domain_to_entries_query = "match $entry isa time_domain_entry, has time_domain_reference \"{}\"; $domain isa time_domain, has time_domain_reference \"{}\"; insert $inside_relation (entry:$entry, time_domain:$domain) isa entry_of_domain;"
        add_long_timestamp_relation_query = "match $entry isa time_domain_entry, has time_domain_reference $domain_name, has value_long $ts; insert $rel (entry:$entry, time_data:$ts) isa time_data_in_entry;";
        add_datetime_timestamp_relation_query = "match $entry isa time_domain_entry, has time_domain_reference $domain_name, has value_datetime $ts; insert $rel (entry:$entry, time_data:$ts) isa time_data_in_entry;";
        insert_equals_query = "match $left isa time_domain_entry, has time_domain_reference \"{}\"; $right isa time_domain_entry, has time_domain_reference \"{}\"; $ts_left isa attribute; $ts_right isa attribute; $ts_left == {}; $ts_right == {}; $rel_left (entry:$left, time_data:$ts_left) isa time_data_in_entry; $rel_right (entry:$right, time_data:$ts_right) isa time_data_in_entry;  insert $global_equality (left:$left, right:$right) isa global_equality;"
        insert_ordering_query = "match $left isa time_domain_entry, has time_domain_reference \"{}\"; $right isa time_domain_entry, has time_domain_reference \"{}\"; $ts_left isa attribute; $ts_right isa attribute; $ts_left == {}; $ts_right == {}; $rel_left (entry:$left, time_data:$ts_left) isa time_data_in_entry; $rel_right (entry:$right, time_data:$ts_right) isa time_data_in_entry;  insert $precedence_ordering (earlier:$left, later:$right) isa precedence_ordering;"
        

        
        print("Request #1: Insert Time Domains")
        with session.transaction(TransactionType.WRITE) as write_transaction:
            for idx, col in enumerate(cols):
                #print(insert_domain_query.format(tsv_header[col]))
                #Only insert them if they do not exist yet!
                answer_iterator = write_transaction.query.get(get_domain_query.format(tsv_header[col]))
                concepts = [ans.get("td") for ans in answer_iterator]
                if len(concepts) == 0:
                    answer_iterator = write_transaction.query.insert(insert_domain_query.format(tsv_header[col]))
                    concepts = [ans.get("td") for ans in answer_iterator]
                print("Inserted: {0}".format(concepts[0].as_entity().get_iid()))
                
                ## to persist changes, write transaction must always be committed (closed)
            write_transaction.commit()
            #transaction is closed
        
        print("Request #2: Insert Time Domain Entries")
        with session.transaction(TransactionType.WRITE) as write_transaction:
            for idx, col in enumerate(cols):
                print("Request #2a: Insert time domain entries of {}".format(tsv_header[col]))
                if datatypes[idx] == "long":
                    for line in tsv_lines:
                        if line[col] == "":
                            continue
                        timestamp = locale.atoi(line[col])
                        answer_iterator = write_transaction.query.get(get_long_entry_query.format(tsv_header[col], timestamp))
                        concepts = [ans.get("entry") for ans in answer_iterator]
                        #Only insert them if they do not exist yet! Future Work: Integrate proveniance
                        if len(concepts) == 0:
                            meta_data = line[meta_data_col] if meta_data_col is not None and len(line) > meta_data_col else ""
                            answer_iterator = write_transaction.query.insert(insert_long_entry_query.format(tsv_header[col], timestamp, meta_data))
                            concepts = [ans.get("entry") for ans in answer_iterator]
                    print("Inserted all values of time domain {}".format(tsv_header[col]))
                elif datatypes[idx] == "datetime":
                    for line in tsv_lines:
                        if line[col] == "":
                            continue
                        datetime_object = datetime.strptime(line[col], timestamp_format_string)
                        timestamp = datetime.isoformat(datetime_object)
                        print(get_datetime_entry_query.format(tsv_header[col], timestamp))
                        answer_iterator = write_transaction.query.get(get_datetime_entry_query.format(tsv_header[col], timestamp))
                        concepts = [ans.get("entry") for ans in answer_iterator]
                        #Only insert them if they do not exist yet! Future Work: Proveniance
                        if len(concepts) == 0:
                            meta_data = line[meta_data_col] if meta_data_col is not None and len(line) > meta_data_col else ""
                            answer_iterator = write_transaction.query.insert(insert_datetime_entry_query.format(tsv_header[col], timestamp, meta_data))
                            concepts = [ans.get("entry") for ans in answer_iterator]
                    print("Inserted all values of time domain {}".format(tsv_header[col]))
                else:
                    print("Error: could not determine datatype of time domain {}; ignored".format(tsv_header[col]))
                    continue
                
                print("Request #2b: Insert relation between {} and the time domain entries".format(tsv_header[col]))
                #query inserts adds relation to all time domain entries at once
                answer_iterator = write_transaction.query.insert(add_domain_to_entries_query.format(tsv_header[col], tsv_header[col]))
                concepts = [ans.get("inside_relation") for ans in answer_iterator]
                for concept in concepts:
                    print("Inserted: {0}".format(concepts[0].as_relation().get_iid()))
                
                print("Request #2c: Insert relation between time data (e.g. time data) and time domain entry") 
                #This is currently a workaround as TypeDB does not offer one abstract attribute type that can have attributes with different types inherited
                answer_iterator = write_transaction.query.insert(add_long_timestamp_relation_query)
                concepts = [ans.get("rel") for ans in answer_iterator]
                for concept in concepts:
                    print("Inserted: {0}".format(concepts[0].as_relation().get_iid()))
                
                answer_iterator = write_transaction.query.insert(add_datetime_timestamp_relation_query)
                concepts = [ans.get("rel") for ans in answer_iterator]
                for concept in concepts:
                    print("Inserted: {0}".format(concepts[0].as_relation().get_iid()))
            ## to persist changes, write transaction must always be committed (closed)
            write_transaction.commit()
            #transaction is closed
                    
        print("Request #3: Insert Global Equality Relations for the rows due to coincidence") 
        with session.transaction(TransactionType.WRITE) as write_transaction:
            for line in tsv_lines:
                for col_pair in coincidences:
                    print(col_pair)
                    left_value = ""
                    right_value = ""
                    if line[col_pair[0]] == "":
                        continue
                    elif datatypes_dict[col_pair[0]] == "long":
                        left_value = locale.atoi(line[col_pair[0]])
                    elif datatypes_dict[col_pair[0]] == "datetime":
                        datetime_object = datetime.strptime(line[col_pair[0]], timestamp_format_string)
                        left_value = datetime.isoformat(datetime_object)
                    else:
                        print("Could not determine datatype of {}", tsv_header[col_pair[0]])
                    if line[col_pair[1]] == "":
                        continue;
                    elif datatypes_dict[col_pair[1]] == "long":
                        right_value = locale.atoi(line[col_pair[1]])
                    elif datatypes_dict[col_pair[1]] == "datetime":
                        datetime_object = datetime.strptime(line[col_pair[1]], timestamp_format_string)
                        right_value = datetime.isoformat(datetime_object)
                    else:
                        print("Could not determine datatype of {}", tsv_header[col_pair[1]])
                    answer_iterator = write_transaction.query.insert(insert_equals_query.format(tsv_header[col_pair[0]], tsv_header[col_pair[1]], left_value, right_value))
                    concepts = [ans.get("global_equality") for ans in answer_iterator]
                    print("Inserted: {0}".format(concepts[0].as_relation().get_iid()))
            write_transaction.commit()
        
        
        print("Request #4: Insert Global Ordering Relations for the rows due to precedence") 
        with session.transaction(TransactionType.WRITE) as write_transaction:
            for line in tsv_lines:
                for col_pair in precedences:
                    left_value = ""
                    right_value = ""
                    if line[col_pair[0]] == "":
                        continue
                    elif datatypes_dict[col_pair[0]] == "long":
                        left_value = locale.atoi(line[col_pair[0]])
                    elif datatypes_dict[col_pair[0]] == "datetime":
                        datetime_object = datetime.strptime(line[col_pair[0]], timestamp_format_string)
                        left_value = datetime.isoformat(datetime_object)
                    else:
                        print("Could not determine datatype of {}", tsv_header[col_pair[0]])
                    if line[col_pair[1]] == "":
                        continue;
                    elif datatypes_dict[col_pair[1]] == "long":
                        right_value = locale.atoi(line[col_pair[1]])
                    elif datatypes_dict[col_pair[1]] == "datetime":
                        datetime_object = datetime.strptime(line[col_pair[1]], timestamp_format_string)
                        right_value = datetime.isoformat(datetime_object)
                    else:
                        print("Could not determine datatype of {}", tsv_header[col_pair[1]])
                    #print(insert_ordering_query.format(tsv_header[col_pair[0]], tsv_header[col_pair[1]], left_value, right_value))
                    answer_iterator = write_transaction.query.insert(insert_ordering_query.format(tsv_header[col_pair[0]], tsv_header[col_pair[1]], left_value, right_value))
                    concepts = [ans.get("precedence_ordering") for ans in answer_iterator]
                    print("Inserted: {0}".format(concepts[0].as_relation().get_iid()))
            write_transaction.commit()

