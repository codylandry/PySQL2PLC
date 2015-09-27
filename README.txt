
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
        value - the value being stored. This may be any data less than 50 characters
                    (ex. 1, 0, 34.232143, 'motor running')
        timestamp - the time of the datachange event.

PLC_Live_Data

    Purpose:
        Contains live time and value data for each change in value.
    Fields:
        id - a unique identifier for each datapoint
                    (ex. 1, 4, 45938, any positive integer)
        tag - a foreign key that references a tag 'id' in the PLC_Tags table
                    (ex. 1, 4, 45938, any positive integer)
        value - the value being stored. This may be any data less than 50 characters
                    (ex. 1, 0, 34.232143, 'motor running')
        timestamp - the time of the most recent data change event.

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