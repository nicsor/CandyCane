import dataTypes
import sqlite3

from dataTypes import *

class Database():
    def __init__(self, database = ':memory:'):
        self.connection = sqlite3.connect(database)
        self.insertQueries = {}

        with self.connection:

            for table in databaseTables:
                constructor = globals()[table]
                instance = constructor()

                primaryKeys = []
                attributes  = []

                for attribute, value in instance.__dict__.items():
                    # We'll set the attribute by default as text
                    attributeType = 'TEXT'

                    if attribute.endswith('_id'):
                        primaryKeys.append(attribute)

                    if attribute in databaseAttrTypes.keys():
                        attributeType = databaseAttrTypes[attribute]

                    attributes.append('%s %s' % (attribute, attributeType))

                query = 'CREATE TABLE IF NOT EXISTS %s(\n\t' % table
                query = query + ',\n\t'.join(attributes)

                if len(primaryKeys) > 0:
                    query = query + ', PRIMARY KEY (%s)\n' % ', '.join(primaryKeys)

                query =  query + ')'

                self.connection.execute(query)

                # Prepare insert query
                placeholders = ', '.join(['?'] * len(instance.__dict__))
                columns      = ', '.join(instance.__dict__.keys())
                query = 'INSERT INTO %s (%s) VALUES (%s)' % (table, columns, placeholders)
                self.insertQueries[table] = query

    def __del__(self):
        self.connection.commit()
        self.connection.close()

    def saveToFile(self, filename):
        targetDB = sqlite3.connect(filename)

        with targetDB:
            self.connection.backup(targetDB)

        targetDB.close()

    def insert(self, data):
        table        = type(data).__name__
        self.connection.execute(self.insertQueries[table], list(vars(data).values()))

    def cleanTable(self, tableName):
        query = 'DELETE FROM %s' % (tableName)
        self.connection.execute(query)

    def getMessages(self, category = "", recipients = "", sender = "", subject = "", content = ""):
        parameters = locals()
        query = 'SELECT message_id, sender, recipients, subject, date, has_attachments FROM Message '
        #query = 'SELECT * FROM Message '
        queryFilter = ''

        for parameter in parameters:
            value = parameters[parameter]
            if value and isinstance(value, str):
                queryFilter += '' if (not queryFilter) else ' and '
                queryFilter += parameter + " like '%" + value + "%'"

        query += '' if (not queryFilter) else (' where ' + queryFilter)
        query +=' order by date DESC'

        return self.connection.execute(query)

    def getContent(self, message_id):
        parameters = locals()
        query = 'SELECT rich_content, content FROM Message'
        query += ' where message_id = ' + str(message_id)

        for row in self.connection.execute(query):
            return (row[0], row[1])

        return ('', '')

    def getCategories(self):
        query = 'SELECT distinct(category) FROM Message'

        self.connection.row_factory = lambda cursor, row: row[0]
        cursor = self.connection.cursor()
        categories = cursor.execute(query).fetchall()
        self.connection.row_factory = None
        return categories

    def getConversationIds(self):
        query = 'SELECT thread_id, conversation_id FROM Conversation'

        self.connection.row_factory = lambda cursor, row: (row[0], row[1])
        cursor = self.connection.cursor()
        categories = cursor.execute(query).fetchall()
        self.connection.row_factory = None
        return categories

    def getMessageIds(self):
        query = 'SELECT message_id FROM Message'

        self.connection.row_factory = lambda cursor, row: row[0]
        cursor = self.connection.cursor()
        categories = cursor.execute(query).fetchall()
        self.connection.row_factory = None
        return categories

    def getAttachementNames(self, message_id):
        query = 'SELECT attachment_id FROM Attachment '
        query += ' where message_id = ' + str(message_id)

        self.connection.row_factory = lambda cursor, row: row[0]
        cursor = self.connection.cursor()
        attachments = cursor.execute(query).fetchall()
        self.connection.row_factory = None
        return attachments

    def getAttachmentData(self, message_id, attachment_name):
        query = 'SELECT data FROM Attachment '
        query += ' where message_id = "' + str(message_id) + '" and'
        query += ' attachment_id = "' + attachment_name + '"'

        for row in self.connection.execute(query):
            return row[0]

        return None

    def groupConversations(self):
        self.cleanTable('Messages')

        # Assumption is that all conversations have only two participants,
        # therefore we expect distinct fields to be set for sender and receiver.
        # If only the sender is set, then it's the other participant.
        # If neither is set then there is an old Client and I have no clue how to get that data.
        # Maybe there is another file with that info... pam pam. Meanwhile, play guess the conversation.
        query = "insert into Messages \
                   select thread_id, '', group_concat(participants), 'Conversation from ' || date, date, '', \
                      group_concat(content,''), 0, '/Conversations', 1 from Conversation group by thread_id order by conversation_id DESC"
        self.connection.execute(query)

        # Clean up the receiveres so that we would see uniques
        query = "SELECT distinct(recipients) FROM Messages"

        for row in self.connection.execute(query):
            receivers = row[0].split(',')
            temp = dict.fromkeys(receivers)
            temp.pop('', None)
            temp.pop('roscin@gmail.com', None)
            unique_receivers = list(temp)
            unique_receivers.sort()
            self.connection.execute("UPDATE Messages set recipients = '" + ','.join(unique_receivers) +"' where recipients = '" + row[0] + "'")

        # Delete the current conversation messages as we will recreate them
        query = "DELETE FROM Message where is_conversation <> 0"
        self.connection.execute(query)

        # Don't group threads by participant, only the conversations
        query = "insert into Message select * from Messages"
        self.connection.execute(query)

        # Group threads together by participants
        #query = "insert into Message \
        #           select message_id, sender, recipients, subject, date, '', group_concat(rich_content, ''), 0, '/Conversations', 1 from Messages \
        #              where recipients <> 'other' and recipients <> 'me,other' and recipients <> '' group by recipients order by date DESC"
        #self.connection.execute(query)
        #query = "insert into Message select * from Messages where recipients = 'other' or recipients = 'me,other' or recipients = ''"
        #self.connection.execute(query)

        # Single conversation Thread
        #query = "insert into Message \
        #           select message_id, sender, recipients, subject, date, '', group_concat(rich_content, ''), 0, '/Conversations', 1 from Messages \
        #              group by sender order by date ASC"
        #self.connection.execute(query)

        self.cleanTable('Messages')

        return None
