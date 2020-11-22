#!/usr/bin/python3

from mailbox import mbox
from email import policy
from email.header import Header, decode_header
from email.parser import BytesParser

from dateutil.parser import parse

import pickle
import pathlib
import hashlib
import sqlite3
import json
import re
import os


class EmailBase():
    def __init__(self, data):
        self.message = data
        self.body_html = ""
        self.body_plain = ""
        self._update_payload(self.message)

    def isConversation(self):
        return False

    def getId(self):
        h = hashlib.sha1()
        h.update(pickle.dumps(self.message))
        return h.hexdigest()

    def getProperties(self):
        data = {}
        for item in self.message.keys():
            data[item] = self.message[item]

        return json.dumps(data)

    def extractEmails(self, text):
        emails = re.findall('([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)', text)
        emails = list(dict.fromkeys(emails)) # remove duplicates
        return emails

    def getAttachmentData(self, name):
        raise Exception('Not implemented')

    def getAttachmentNames(self):
        raise Exception('Not implemented')

    def getPayloadHtml(self):
        return self.body_html

    def getPayloadPlain(self):
        return self.body_plain

    def getSender(self):
        return str(self.message["from"])

    def getReceivers(self):
        return str(self.message["to"])

    def getSubject(self):
        return self._decode_entry(self.message["Subject"])

    def getDate(self):
        dt = parse(self.message["Date"])
        return str(dt.date()) + " " + str(dt.time())

    def _update_payload(self, message):
        raise Exception('Not implemented')

    def _decode_entry(self, entry):
        if entry is None:
            entry = ""
        else:
            result = ''
            for part in decode_header(entry):
                if isinstance(part[0], str):
                    result += part[0]
                else:
                    encoding = part[1]
                    result += part[0].decode(encoding)

            entry = result

        return entry

    def _decode_body(self, entry):
        try:
            entry = entry.decode('utf-8')
        except UnicodeDecodeError:
            entry = entry.decode('latin-1')

        return entry


class Eml(EmailBase):
    def __init__(self, data):
        super(Eml, self).__init__(data)

    def getAttachmentData(self, name):
        for part in self.message.walk():
            if 'content-disposition' not in part:
                continue

            cdisp = part['content-disposition'].split(';')
            cdisp = [x.strip() for x in cdisp]

            if cdisp[0].lower() != 'attachment':
                continue
            parsed = {}

            for kv in cdisp[1:]:
               if kv.startswith("filename="):
                   key, _, val = kv.partition('=')

                   if val.startswith('"'):
                       val = val.strip('"')
                   elif val.startswith("'"):
                       val = val.strip("'")

                   if (name == val):
                       return part.get_payload(decode=True)

        return None

    def getAttachmentNames(self):
        found = []

        for part in self.message.walk():
            if 'content-disposition' not in part:
                continue

            cdisp = part['content-disposition'].split(';')
            cdisp = [x.strip() for x in cdisp]

            if cdisp[0].lower() != 'attachment':
                continue
            parsed = {}

            for kv in cdisp[1:]:
               if kv.startswith("filename="):
                   key, _, val = kv.partition('=')

                   if val.startswith('"'):
                       val = val.strip('"')
                   elif val.startswith("'"):
                       val = val.strip("'")

                   found.append(val)

        return found

    def _update_payload(self, message):
        if (self.message.get_body('html') != None):
            self.body_html = self._decode_body(self.message.get_body('html').get_payload(decode=True))

        if (self.message.get_body('plain') != None):
            self.body_plain = self._decode_body(self.message.get_body('plain').get_payload(decode=True))

class MailBoxEml(EmailBase):
    def __init__(self, data):
        super(MailBoxEml, self).__init__(data)

    def isConversation(self):
        if "X-Gmail-Labels" in self.message.keys():
            if "Chat" in self.message["X-Gmail-Labels"].split(","):
                return True

        return False

    def getAttachmentData(self, name):
        for part in self.message.get_payload():
            if str(part.get_filename()) == 'None':
                continue

            foundName = self._decode_entry(part.get_filename())
            if foundName != name:
                continue

            return part.get_payload(decode=True)

        return None

    def getAttachmentNames(self):
        found = []

        for part in self.message.get_payload():
            if str(part.get_filename()) == 'None':
                continue

            found.append(self._decode_entry(part.get_filename()))

        return found

    def _update_payload(self, message):
        if message.is_multipart():
            for part in message.get_payload():
                self._update_payload(part)
        else:
            contentType = message.get_content_type()

            if ('text/plain' in contentType) or ('text/html' in contentType):
                body = self._decode_body(message.get_payload(decode=True))

                if 'text/html' in contentType:
                    self.body_html = body
                else:
                    self.body_plain = body


class Sql():
    def __init__(self, database = ':memory:'):
        self.connection = sqlite3.connect(database)

        with self.connection:
            self.connection.execute(
                'CREATE TABLE IF NOT EXISTS processed(            \
                    id          VARCHAR(40) NOT NULL PRIMARY KEY, \
                    sender      TEXT,                   \
                    receivers   TEXT,                   \
                    subject     TEXT,                   \
                    date        TEXT,                   \
                    body_html   TEXT,                   \
                    body_plain  TEXT,                   \
                    path        TEXT,                   \
                    attachments TEXT,                   \
                    properties  TEXT,                   \
                    meta        TEXT)')

            self.connection.execute(
                'CREATE TABLE IF NOT EXISTS attachments(\
                    emailId     VARCHAR(40),            \
                    name        TEXT,                   \
                    data        TEXT,                   \
                    PRIMARY KEY (emailId, name))')

    def __del__(self):
        self.connection.commit()
        self.connection.close()

    def saveToFile(self, filename):
        targetDB = sqlite3.connect(filename)
        with targetDB:
            self.connection.backup(targetDB)
        targetDB.close()

    def readFile(self, filename):
        with open(filename, 'rb') as file:
            blobData = file.read()
        return blobData

    def getHash(self, data):
        h = hashlib.sha1()
        h.update(data)
        return h.hexdigest()

    def _addEntry(self, message, metaInfo):
        with self.connection:
            # Skip conversations
            if message.isConversation():
                return

            emlHash     = str(message.getId())
            receivers   = ','.join(message.extractEmails(message.getReceivers()))
            sender      = ','.join(message.extractEmails(message.getSender()))
            subject     = message.getSubject()
            date        = message.getDate()
            html        = message.getPayloadHtml()
            plain       = message.getPayloadPlain()
            attachments = message.getAttachmentNames()
            path = ""
            properties  = message.getProperties()

            for attachment in attachments:
                data = message.getAttachmentData(attachment)

                dataTuple = (emlHash, attachment, data)
                self.connection.execute('INSERT INTO attachments VALUES (?, ?, ?)', dataTuple)

            if "Path" in metaInfo:
                path = metaInfo["Path"]

            dataTuple = (emlHash, sender, receivers, subject, date, html, plain, path, ','.join(attachments), str(properties), str(metaInfo))
            self.connection.execute('INSERT INTO processed VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', dataTuple)

    def addEntry(self, emailType, fileName):
        meta = "{}"

        if emailType == "eml":
            eml = BytesParser(policy=policy.default).parsebytes(self.readFile(fileName))
            msg = Eml(eml)
            # We assume there might be a meta file associated with the current input
            metaFile = fileName + ".meta"

            if pathlib.Path(metaFile).exists():
                meta = self.readFile(metaFile)

            try:
                self._addEntry(msg, json.loads(meta))
            except Exception as e:
                print("Problem while processing file=[{0:s}], meta=[{1:s}], \
                       SKIPPED: {2:s}".format(fileName, emailType, str(e)))

        elif emailType == "mbox":
            messages = mbox(fileName)
            base     = os.path.basename(fileName)
            metaPath = ('.').join(base.split('.')[:-1])
            meta     = '{"Path":"/MailBox/' + metaPath + '"}'

            for message in messages:
                msg = MailBoxEml(message)
                try:
                    self._addEntry(msg, json.loads(meta))
                except Exception as e:
                    print("Problem while processing file=[{0:s}], meta=[{1:s}], \
                           SKIPPED: {2:s}".format(fileName, emailType, str(e)))
        else:
            raise Exception('Not implemented')

    def __dictionary_factory(self, cursor, row):
        dictionary = {}
        for index, column in enumerate(cursor.description):
            dictionary[column[0]] = row[index]
        return dictionary

    def getEnries(self, path = "", receivers = "", sender = "", subject = "", content = ""):
        query = "SELECT id, sender, receivers, subject, date, attachments FROM processed"

        if (receivers != "") or (sender != "") or (subject != "") or (content != "") or (path != ""):
            queryFilter = ""

            if path != "":
                if queryFilter != "":
                   queryFilter = queryFilter + " and "
                queryFilter = queryFilter + " path like '" + path + "%'"

            if receivers != "":
                if queryFilter != "":
                   queryFilter = queryFilter + " and "
                queryFilter = queryFilter + " receivers like '" + receivers + "'"

            if sender != "":
                if queryFilter != "":
                   queryFilter = queryFilter + " and "
                queryFilter = queryFilter + " sender like '" + sender + "'"

            if subject != "":
                if queryFilter != "":
                   queryFilter = queryFilter + " and "
                queryFilter = queryFilter + " subject like '" + subject + "'"

            if content != "":
                if queryFilter != "":
                   queryFilter = queryFilter + " and "
                queryFilter = queryFilter + " body_plain like '" + content + "'"

            query = query + " where " + queryFilter

        query = query + " order by date DESC"

        self.connection.row_factory = None
        return self.connection.execute(query)
        #self.connection.row_factory = self.__dictionary_factory
        #cursor = self.connection.cursor()
        #return cursor.execute(query).fetchall()

    def getCategories(self, receivers = "", sender = "", subject = "", content = ""):
        query = "SELECT distinct(path) FROM processed"

        if (receivers != "") or (sender != "") or (subject != "") or (content != ""):
            queryFilter = ""

            if receivers != "":
                if queryFilter != "":
                   queryFilter = queryFilter + " and "
                queryFilter = queryFilter + " receivers like '" + receivers + "'"

            if sender != "":
                if queryFilter != "":
                   queryFilter = queryFilter + " and "
                queryFilter = queryFilter + " sender like '" + sender + "'"

            if subject != "":
                if queryFilter != "":
                   queryFilter = queryFilter + " and "
                queryFilter = queryFilter + " subject like '" + subject + "'"

            if content != "":
                if queryFilter != "":
                   queryFilter = queryFilter + " and "
                queryFilter = queryFilter + " body_plain like '" + content + "'"

            query = query + " where " + queryFilter

        self.connection.row_factory = lambda cursor, row: row[0]
        cursor = self.connection.cursor()
        return cursor.execute(query).fetchall()

    def getContent(self, entryId):
        query = "SELECT body_html, body_plain FROM processed where id = '" + str(entryId) + "'"

        for row in self.connection.execute(query):
            return (row[0], row[1])

        return None

    def getAttachementNames(self, entryId):
        query = "SELECT attachments FROM processed where id = '" + str(entryId) + "'"

        for row in self.connection.execute(query):
            if row[0] == "":
                return []
            return row[0].split(',')

    def getAttachmentData(self, entryId, name):
        query = "SELECT data FROM attachments where emailId = '" + str(entryId) + "' and name = '" + name + "'"

        self.connection.row_factory = None
        for row in self.connection.execute(query):
            return row[0]

        return None

if __name__ == '__main__':
    #sql = Sql("database.db")
    #sql.addEMLEntry('input/test2.eml', 'input/test2.eml.meta')
    #sql.saveToFile("database.db")

    emlData = ""
    with open('input/test2.eml', 'rb') as file:
        emlData = file.read()

    eml = Eml(emlData)
    eml.getProperties()


    #sql.downloadAttachment('31a454320a46d0ca8f13a3cd13d364a5f71e2e49', 'xpact quiz.docx', '1.docx')

    #for row in sql.getEnries():
    #    print(row)

