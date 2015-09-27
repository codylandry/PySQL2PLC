__author__ = 'LandrCod'

"""
CLI Program designed to collect data from PLCs via their associated OPC Server software
and store the data in a relational database.
"""


from collections import OrderedDict, namedtuple
import time
from datetime import datetime as dt
import signal
import sys
from csv import reader as csv_reader
from os import path, getcwd
from optparse import OptionParser
from easygui import filesavebox, fileopenbox
from smtplib import SMTP as smtp
from email.mime.text import MIMEText
from sqlite3 import OperationalError

from web2py_dal import DAL, Field

import OpenOPC


# <editor-fold desc="Constants">
OPC_TAG = 0
OPC_VALUE = 1
OPC_QUALITY = 2
OPC_TS = 3
OPC_STA_NAME = 4
OPC_PRD_LINE = 5
OPC_STATION = 6
CSV_TAG = 0
CSV_NAME = 1
TRIGGERS = {'VALUE_CHANGE': 1,
            'RISING_EDGE': 2,
            'FALLING_EDGE': 3,
            'DEADBAND': 4,
            'IN_BAND': 5,
            'OUT_BAND': 6,
            'HIGH_LIMIT': 7,
            'LOW_LIMIT': 8,
            'TIME': 9}

PASSWORD = 'Password'
SUCCESS = "--------->Success\n"
LINE = '=' * 140
# </editor-fold>


# <editor-fold desc="Sys Argument Parser">

# handle CLI options and switches
# <editor-fold desc="Options Parser Help File">
USAGE = """
-------------------------------------------------------------------------------------------------------------------
PyPLC2SQL
-------------------------------------------------------------------------------------------------------------------

OVERVIEW:

    This program takes data from PLC's via OPC servers and writes 'change of state' events to the database.
    The program relies on five tables in the SQL database, which it will create if not already present:

PLC_Tag_Type

    Purpose:
        Contains information unique to each tag.
    Fields:
        id - a unique identifier for each datapoint
                    (ex. 1, 4, 45938, any positive integer)
        tag_type - a parameter given to a tag to identify its purpose
                    (ex. ESTOP, LINE RUNNING, ALARM #2)

PLC_Equipment

    Purpose:
        Contains information unique to each tag.
    Fields:
        id - a unique identifier for each datapoint
                    (ex. 1, 4, 45938, any positive integer)
        equipment - a parameter given to a tag to identify its purpose
                    (ex. LINE 1, PRESS 15, CAVITY FURNACE)

PLC_Tags

    Purpose:
        Contains information unique to each tag.
    Fields:
        id - a unique identifier for each datapoint
                    (ex. 1, 4, 45938, any positive integer)
        tag - the actual PLC tag that the values are read from
                    (ex. '[topic]Program:MyProgram.Tag[arrayelement].tagelement')
        name - a name that represents the datapoint
                    (ex. 'station 2')
        tag_type_id - the associated tag_type id in the PLC_Tag_Type table
        equipment_id - the associated equipment id in the PLC_Equipment table

PLC_Hist_Data

    Purpose:
        Contains historical time and value data for each change in value.
    Fields:
        id - a unique identifier for each datapoint
                    (ex. 1, 4, 45938, any positive integer)
        tag - a foreign key that references a tag 'id' in the PLC_Tags table
                    (ex. 1, 4, 45938, any positive integer)
        val - the value being stored. This may be any data less than 50 characters
                    (ex. 1, 0, 34.232143, 'motor running')
        time_stamp - the time of the datachange event.

PLC_Live_Data

    Purpose:
        Contains live time and value data for each change in value.
    Fields:
        id - a unique identifier for each datapoint
                    (ex. 1, 4, 45938, any positive integer)
        tag - a foreign key that references a tag 'id' in the PLC_Tags table
                    (ex. 1, 4, 45938, any positive integer)
        val - the value being stored. This may be any data less than 50 characters
                    (ex. 1, 0, 34.232143, 'motor running')
        time_stamp - the time of the most recent data change event.

--------------------------------------------------------------------------------------------------------------------

CONFIG File:

        The program uses a CONFIG file to store several essential parameters for OPC and database server connections.
    This file is in the application root directory and is named:  CONFIG_FILE.cfg

    WARNING:
        - Changes to this file may result in application crashes!
        - This file must be closed when starting the application!
    Notes:
        The following sections describe the parameters in the CONFIG_FILE.cfg

--------------------------------------------------------------------------------------------------------------------

SQL DATABASE SERVER:

    To connect to the database, the program needs a string such as:

        sqlite://storage.db

    You can provide your own string as well.  Here are some examples for some popular databases:

        SQLite              sqlite://storage.db
        MySQL               mysql://username:password@localhost/test
        PostgreSQL          postgres://username:password@localhost/test
        MSSQL (legacy)      mssql://username:password@localhost/test
        MSSQL (>=2005)      mssql3://username:password@localhost/test
        MSSQL (>=2012)      mssql4://username:password@localhost/test
        FireBird            firebird://username:password@localhost/test
        Oracle              oracle://username/password@test
        DB2                 db2://username:password@test
        Ingres              ingres://username:password@localhost/test
        Sybase              sybase://username:password@localhost/test
        Informix            informix://username:password@test
        Teradata            teradata://DSN=dsn;UID=user;PWD=pass;DATABASE=test
        Cubrid              cubrid://username:password@localhost/test
        SAPDB               sapdb://username:password@localhost/test
        IMAP                imap://user:password@server:port
        MongoDB             mongodb://username:password@localhost/test
        Google/SQL          google:sql://project:instance/database
        Google/NoSQL        google:datastore
        Google/NoSQL/NDB    google:datastore+ndb

    Configuration File Entry Example:

        DB_STRING>sqlite://storage.db

    Notes:

        (See http://web2py.com/books/default/chapter/29/06/the-database-abstraction-layer for more details)

--------------------------------------------------------------------------------------------------------------------
OPC SERVER:

        This program utilizes a library called OpenOPC to communicate with OPC Servers like RSLinx.  If the OPC
    server resides on the same machine as this application, no change to the default configuration is necessary.
    If the OPC server is on a remote machine, an application called OpenOPC Gateway (see notes) must be installed on
    that machine. Here is an example configuration for the OPC server in the CONFIG_FILE:

    Configuration File Entry Example:

        OPC_HOST>localhost
        OPC_PORT>None

    Notes:

        OPC_PORT is ignored if 'localhost' is used.
        See http://openopc.sourceforge.net/ for more details.

--------------------------------------------------------------------------------------------------------------------
"""
# </editor-fold>

# CLI options parser configuration
parser = OptionParser(USAGE)
parser.add_option('-v', '--verbose', action='store_true', default=False, dest='verbose',
                  help='This option will print out a running table of any entry made to the database.')
parser.add_option('-i', '--initialize_db', action='store_true', default=False, dest='init',
                  help='This option will load the values for all tags '
                       'once before switching to only record data changes'
                       'use this when there are gaps in your data due to server'
                       'maintenance, etc.')
parser.add_option('-r', '--reset_db', action='store_true', default=False, dest='reset_db',
                  help="This option will restore all tags, tag types and equipment for the database.  This option "
                       "should be used with care as it will delete all the rows in these tables and replace it with"
                       "the data in the TAG_IMPORT.csv file.")
parser.add_option('-e', '--export_db', action='store_true', default=False, dest='export_db',
                  help="This option will create a database backup that can be used to restore or initialize a "
                       "database if needed.")

(options, args) = parser.parse_args()

app = None
# </editor-fold>


def is_outside_deadband(prev, current, deadband):
    """
    takes a previous value, current value and a deadband percentage and computes
    whether the current value is outside a deadband of the previous value
    """
    # handle case where user puts in a whole percentage (ex 70%) or a decimal number (ex .70)
    if deadband > 1:
        deadband /= 100.0

    # find the upper/lower limits
    prev = float(prev)
    upper = prev + prev * deadband
    lower = prev - prev * deadband

    # if inside the limits, return True
    return lower < current < upper


def restart():
    """
    Attempts to restart the application.
    After 3 restart attempts in 30 minutes, send an email
    """
    global options, app, restarts
    try:
        app.opc_disconnect()
        del app
    except Exception:
        pass
    print LINE
    print 'RESTARTING APPLICATION'
    print LINE
    time.sleep(1)
    options.init = True
    app = PyPLC2SQL(options)
    app.run()


def stop_signal_handler(signal, frame):
    """
    Handles Ctrl-C keyboard input from user.  Cleanly exits the program.
    """
    global app
    print "Logging Stopped by user"
    try:
        app._run = False
        app.opc_disconnect()
        del app
    except Exception, e:
        print "Error while closing program:", e
    sys.exit(0)


class PyPLC2SQL(object):
    """
    A full featured Data Acquisition class that takes data from PLC OPC Servers and pushes
    """

    def __init__(self, opts):

        print LINE
        print ("{: ^%i}" % len(LINE)).format('PyPLC2SQL')
        self.tag_file_path = None
        self._run = False
        self.db = None
        self._db_connected = False
        self._opc_connected = False
        self._current_state = {}
        self._prev_state = {}
        self._tags = []
        self.tag_file_path = ''
        self.plc_tags_dict = OrderedDict()

        self._CONFIG = None
        self._parse_config_file()

        self._options = opts
        self.connect_to_database()

        if self._options.export_db:
            self._export_database()
            sys.exit(0)

        if self._options.reset_db and self._db_connected:
            self._restore_database()
            sys.exit(0)

        # must open correct type of client (local or remote)
        if self._CONFIG.OPC_HOST == 'localhost':
            self._opc = OpenOPC.client()
        else:
            self._opc = OpenOPC.open_client(self._CONFIG.OPC_HOST, int(self._CONFIG.OPC_PORT))
        self.opc_connect()

    def _parse_config_file(self):
        try:
            with open("CONFIG_FILE.cfg", 'r') as config_file:
                conf_reader = csv_reader(config_file, delimiter=">")
                conf_dict = dict(conf_reader)
                self._CONFIG = namedtuple('Config', conf_dict.keys())(*conf_dict.values())
        except IOError:
            print "Problem accessing CONFIG_FILE.cfg", e

    def _email(self, msg1, msg2):
        try:
            COMMASPACE = ', '
            email_db = DAL(self._CONFIG.EMAIL_DB_STRING)
            # to_list = [row[1] for row in email_db.executesql(self._CONFIG.EMAIL_QUERY)]
            to_list = self._CONFIG.EMAIL_LIST
            email = smtp(self._CONFIG.EMAIL_HOST, self._CONFIG.EMAIL_PORT)
            with open('WARNING_EMAIL.html', 'r') as em:
                msg = em.read() % (msg1, msg2)
            msg = MIMEText(msg, 'html')
            msg['Subject'] = self._CONFIG.EMAIL_SUBJECT
            msg['From'] = self._CONFIG.EMAIL_SENDER
            msg['To'] = COMMASPACE.join(to_list)
            email.sendmail(self._CONFIG.EMAIL_SENDER, to_list, msg.as_string())
        except Exception, e:
            print "Problem while attempting to send email:", e

    def connect_to_database(self):
        """
        Create a database object and create/connect to table of concern.
        Update the tag state by reading from RSLinx
        """
        print LINE
        print 'SQL DATABASE CONNECTION\n'
        print "-Connecting to SQL Database @ %s" % self._CONFIG.DB_STRING
        # Database Connection
        self.db = DAL(self._CONFIG.DB_STRING, folder=self._CONFIG.DB_FOLDER)

        # Defining the db tables
        self.db.define_table('PLC_Tag_Type', Field('tag_type', 'string',
                                                   length=100, required=True,
                                                   unique=True, readable=True), migrate=True)

        self.db.define_table('PLC_Equipment', Field('equipment', 'string',
                                                    length=100, required=True,
                                                    unique=True, readable=True), migrate=True)
        self.db.define_table('PLC_Tags',
                             Field('tag_name', 'string', length=100, required=True, readable=True),
                             Field('name', 'string', length=50, readable=True),
                             Field('insert_trigger', 'integer', required=True, readable=True),
                             Field('trigger_setting', 'string'),
                             Field('log_hist', 'boolean', required=True, readable=True),
                             Field('tag_type_id', self.db.PLC_Tag_Type, readable=True),
                             Field('equipment_id', self.db.PLC_Equipment, readable=True), migrate=True)

        self.db.define_table('PLC_Hist_Data',
                             Field('tag_id', self.db.PLC_Tags, readable=True),
                             Field('time_stamp', 'datetime', readable=True),
                             Field('val', 'string', length=50, readable=True), migrate=True)

        self.db.define_table('PLC_Live_Data',
                             Field('tag_id', self.db.PLC_Tags, readable=True),
                             Field('time_stamp', 'datetime', readable=True),
                             Field('val', 'string', length=50, readable=True), migrate=True)

        self.db.define_table('PLC_Events',
                             Field('tag_id', self.db.PLC_Tags, readable=True),
                             Field('start_time', 'datetime', readable=True),
                             Field('end_time', 'datetime', readable=True),
                             Field('duration', 'string', length=30, readable=True))
        print SUCCESS
        self._db_connected = True

    def _export_database(self):
        """
        exports the entire database to a csv file
        """
        print LINE
        print 'DATABASE EXPORT'
        print '-Exporting database to csv file. Select location in popup menu.'
        file_name = filesavebox('Export as CSV.', 'Database Export',
                                default=path.join(path.abspath(getcwd()), '\\exports\\db_bkup.csv'),
                                filetypes='*.csv')
        try:
            with open(file_name, 'w') as export_file:
                self.db.export_to_csv_file(export_file)
            print SUCCESS
        except Exception, e:
            print e, 'Database Export Failed'

    def opc_connect(self):
        print LINE
        print 'OPC SERVER CONNECTION\n'
        # Connection to OPC client
        try:
            print "-Connecting to %s @%s:%s." % (self._CONFIG.OPC_SERVER, self._CONFIG.OPC_HOST, self._CONFIG.OPC_PORT)
            self._opc.connect(self._CONFIG.OPC_SERVER)
            print SUCCESS
            print "-Available OPC Servers:"
            for server in self._opc.servers():
                print "\t" + server
            self._opc_connected = True
            # build list of tags to read from the OPC server
            rows = self.db().select(self.db.PLC_Tags.tag_name)
            self._tags = [row.tag_name for row in rows]
            print "\n-Building OPC group in %s. Please wait..." % self._CONFIG.OPC_SERVER
            # Initialize the tag value states
            self._current_state = self.read_tags()
            self._prev_state = self._current_state.copy()
            print SUCCESS
        except OperationalError, e:
            print 'sqlite Operational Error:', e, '\nWhile attempting to read tags for OPC Group.'
            restart()
        except Exception, e:
            print 'Error during attempt to read tags for OPC Group:', e
            restart()

    def _tag_table_data_update(self):
        # copy tags table from db into memory so we can use it if the db locks up
        plc_tags_rows = self.db().select(self.db.PLC_Tags.ALL)
        plc_tags_dict = OrderedDict()
        for row in plc_tags_rows:
            row.trigger_setting = row.trigger_setting.split('/')
            row.time = time.time()
            row.flag = 0
            plc_tags_dict[row['tag_name']] = row
        self._tags = [row.tag_name for row in self.db().select(self.db.PLC_Tags.tag_name)]
        return plc_tags_dict

    def _restore_database(self):
        """
        Completely wipes out the database and imports from a csv file
        """
        print LINE
        print 'DATABASE RESET\n'
        confirm = raw_input('-WARNING!!!\n'
                            '\tThis will completely clear the database and load\n'
                            '\tin the tag information from the TAG_IMPORT.csv \n'
                            '\tfile. This cannot be undone.\n\n'
                            '-Are you sure you want to reset the database? (y/n): ')
        if confirm.upper() == 'Y':
            time.sleep(1)
            entered_pw = raw_input('Please enter the admin password:')
            tries = 3
            while (tries > 0) and (entered_pw != PASSWORD):
                tries -= 1
                entered_pw = raw_input('Incorrect. Please Try Again:')

            if entered_pw == PASSWORD:
                try:
                    self.tag_file_path = fileopenbox('Select a file to import into the database.',
                                                     'Select a file to import.',
                                                     default=path.join(path.abspath(getcwd()), 'TAG_IMPORT.csv'),
                                                     filetypes='*.csv')

                    print '\n-Importing Tag CSV File:', self.tag_file_path

                    self.db.import_from_csv_file(open(self.tag_file_path, 'r'), restore=True)
                    self.db.commit()
                    print SUCCESS
                except Exception, e:
                    print '\nCSV file import failed:', e
            else:
                print 'Too many incorrect password guesses.'
        else:
            print '\nReset Aborted.\n'
        time.sleep(2)

    def opc_disconnect(self):
        try:
            self._opc.remove(self._opc.groups())
            self._opc.close()
        except Exception, e:
            pass

    def read_tags(self):
        try:
            # Get the tags from the file, load them into an OPC group
            output_data = OrderedDict((k, (v[OPC_VALUE], v[OPC_QUALITY])) for k, v in
                                      zip(self._tags, self._opc.read(self._tags, group="PyPLC2SQL")))
            return output_data
        except OpenOPC.OPCError, e:
            print 'OpenOPC Error:', e
            restart()

    def trigger_detect(self, tag_id):
        """
        detects trigger conditions for tag states read from the PLC and returns whether the tag should be logged

        Depending on the value of 'insert_trigger', the values contained in 'trigger_settings' will have
        different meanings:
            'VALUE_CHANGE': no arguments needed
            'RISING_EDGE': no arguments needed
            'FALLING_EDGE': no arguments needed
            'DEADBAND': percent (will log when current value is x% outside of previous value)
            'IN_BAND': min/max (will log when value is inside these bounds)
            'OUT_BAND': min/max (will log when value is outside these bounds)
            'HIGH_LIMIT': high limit (will log when value is above this)
            'LOW_LIMIT': low limit value (will log when value is below this)
            'TIME': time interval between logs (seconds)
        """
        tag_row = self.plc_tags_dict[tag_id]
        trigger = tag_row.insert_trigger
        setting = map(float, tag_row.trigger_setting)
        cur_val, quality = self._current_state[tag_row.tag_name]
        prev_val = self._prev_state[tag_row.tag_name][0]
        if ((self._options.init
             or trigger == TRIGGERS['VALUE_CHANGE'] and not (cur_val != prev_val)
             or trigger == TRIGGERS['DEADBAND'] and not (is_outside_deadband(prev_val, cur_val, setting[0]))
             or trigger == TRIGGERS['RISING_EDGE'] and not (cur_val == 1)
             or trigger == TRIGGERS['FALLING_EDGE'] and not (cur_val == 0)
             or trigger == TRIGGERS['IN_BAND'] and not (setting[0] < cur_val < setting[1])
             or trigger == TRIGGERS['OUT_BAND'] and (setting[0] > cur_val or cur_val > setting[1])
             or trigger == TRIGGERS['HIGH_LIMIT'] and not (cur_val > setting[0])
             or trigger == TRIGGERS['LOW_LIMIT'] and not (cur_val < setting[0])
             or trigger == TRIGGERS['TIME'] and not (time.time() > tag_row.time + setting[0]))
            and self.plc_tags_dict[tag_id].flag):
            # for rising and falling edge triggers, reset the flag
            self.plc_tags_dict[tag_id].flag = False

        if ((self._options.init
             or trigger == TRIGGERS['VALUE_CHANGE'] and cur_val != prev_val
             or trigger == TRIGGERS['DEADBAND'] and is_outside_deadband(prev_val, cur_val, setting[0])
             or trigger == TRIGGERS['RISING_EDGE'] and cur_val == 1
             or trigger == TRIGGERS['FALLING_EDGE'] and cur_val == 0
             or trigger == TRIGGERS['IN_BAND'] and setting[0] <= cur_val <= setting[1]
             or trigger == TRIGGERS['OUT_BAND'] and not (setting[0] <= cur_val <= setting[1])
             or trigger == TRIGGERS['HIGH_LIMIT'] and cur_val >= setting[0]
             or trigger == TRIGGERS['LOW_LIMIT'] and cur_val <= setting[0]
             or trigger == TRIGGERS['TIME'] and (time.time() >= tag_row.time + setting[0]))
            and not self.plc_tags_dict[tag_id].flag):

            if trigger == TRIGGERS['RISING_EDGE'] or trigger == TRIGGERS['FALLING_EDGE']:
                # set a flag indicating that we've already logged this value
                self.plc_tags_dict[tag_id].flag = True
            self.plc_tags_dict[tag_id].time = time.time()
            return True
        else:
            return False

    def run(self, skip=False):
        """
        Starts a while loop that performs asynchronous reads on RSLinx and loads any changes to the database
        """
        self._run = True
        # formatting for the header and data for the data table
        header_format = "|{}{: ^55}|{: ^30}|{: ^20}|{: ^20}|{: ^25}|{: ^20}|"
        data_format = "|{}{: <55}|{: ^30}|{: ^20}|{: ^20}|{: ^25}|{: ^20}|"
        header_titles = header_format.format("", *['Tag', 'Name', 'Description', 'Equipment', 'Timestamp', 'Value'])
        header = '\n' + '\n'.join(['-' * len(header_titles), header_titles, '-' * len(header_titles)])
        now = dt.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3:]
        hist_query = ((self.db.PLC_Hist_Data.tag_id == self.db.PLC_Tags.id) &
         (self.db.PLC_Tags.tag_type_id == self.db.PLC_Tag_Type.id) &
         (self.db.PLC_Tags.equipment_id == self.db.PLC_Equipment.id))

        print LINE
        print 'DATA COLLECTION\n'
        print "-The system is gathering data. \n\n" \
              "\tPlease, do not close with the 'X' at the top of the window.\n" \
              "\tThis will cause OPC groups to be left in RSLinx.\n\n" \
              "-Press Ctrl-C to stop.\n"
        time.sleep(1)

        # prints the header for a table of all the data points written to the database
        if self._options.verbose:
            print header

        # copy tags table from db into memory so we can use it if the db locks up
        try:
            plc_tags_rows = self.db().select(self.db.PLC_Tags.ALL)
            for row in plc_tags_rows:
                row.trigger_setting = row.trigger_setting.split('/')
                row.time = time.time()
                row.flag = False
                self.plc_tags_dict[row['id']] = row
        except OperationalError, e:
            print 'sqlite Operational Error during run method:', e
            restart()

        self._prev_state = self._current_state
        while self._run:
            #self.plc_tags_dict = self._tag_table_data_update()
            self._current_state = self.read_tags()

            for id_ in self.plc_tags_dict.keys():
                now = dt.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3:]
                this_tag_row = self.plc_tags_dict[id_]
                cur_val, quality = self._current_state[this_tag_row.tag_name]
                if self.trigger_detect(id_):
                    try:
                        # if not self._opc.ping():
                        #     raise Exception('OPC server not communicating.')
                        if quality != 'Good':
                            raise Exception('OPC Data Quality Not Good.')
                        if this_tag_row.log_hist:
                            self.db.PLC_Hist_Data.insert(tag_id=this_tag_row.id, time_stamp=now, val=cur_val)

                            if this_tag_row.insert_trigger == 1 and cur_val == 0:
                                start = self.db(hist_query &
                                               (self.db.PLC_Hist_Data.val == '1') &
                                               (self.db.PLC_Hist_Data.time_stamp < now) &
                                               (self.db.PLC_Hist_Data.tag_id == id_)).select(self.db.PLC_Hist_Data.ALL,
                                                                     orderby=~self.db.PLC_Hist_Data.time_stamp).first()
                                if start:
                                    delta = dt.now() - start.time_stamp
                                    self.db.PLC_Events.insert(tag_id=id_,
                                                              start_time=start.time_stamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3:],
                                                              end_time=now,
                                                              duration=delta)

                        self.db.PLC_Live_Data.update_or_insert(self.db.PLC_Live_Data.tag_id == this_tag_row.id,
                                                               tag_id=this_tag_row.id,
                                                               time_stamp=now,
                                                               val=cur_val)

                        if self._options.verbose:
                            print data_format.format("", *[this_tag_row.tag_name,
                                                           this_tag_row.name,
                                                           self.db.PLC_Tag_Type[this_tag_row.tag_type_id].tag_type,
                                                           self.db.PLC_Equipment[this_tag_row.equipment_id].equipment,
                                                           now,
                                                           cur_val])
                        self.db.commit()

                    except OperationalError, e:
                        print 'sqlite3 Operational Error: ', e
                        self._run = False
                    except Exception, e:
                        print this_tag_row.tag_name, now, quality, 'Exception:', e

            self._options.init = False
            self._prev_state = self._current_state
            time.sleep(float(self._CONFIG.PERIOD))

        restart()


if __name__ == "__main__":
    # set up signal handler for Ctrl-C clean exit
    signal.signal(signal.SIGINT, stop_signal_handler)

    # run the program
    app = PyPLC2SQL(options)
    app.run()