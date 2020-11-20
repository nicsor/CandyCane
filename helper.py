#!/usr/bin/python3

from email import policy
from email.parser import BytesParser

from dateutil.parser import parse

import pathlib
import hashlib
import sqlite3
import json
import re

class Eml():
    def __init__(self, data):
        self.message = BytesParser(policy=policy.default).parsebytes(data)

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

    def getPayloadHtml(self):
        if (self.message.get_body('html') != None):
            return self.message.get_body('html').get_payload(decode=True)#.decode('latin-1')
        return ""

    def getPayloadPlain(self):
        if (self.message.get_body('plain') != None):
            return self.message.get_body('plain').get_payload(decode=True)#.decode('latin-1')
        return ""

    def getSender(self):
        return str(self.message["from"])

    def getReceivers(self):
        return str(self.message["to"])

    def getSubject(self):
        return str(self.message["Subject"])

    def getDate(self):
        dt = parse(self.message["Date"])
        return str(dt.date()) + " " + str(dt.time())


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

    def addEMLEntry(self, emlFile, metaFile = ''):
        meta = ""
        eml = self.readFile(emlFile)

        if metaFile != "" and pathlib.Path(metaFile).exists():
            meta = self.readFile(metaFile)

        emlHash = self.getHash(eml)

        try:
            with self.connection:
                emlParser = Eml(eml)

                receivers   = ','.join(emlParser.extractEmails(emlParser.getReceivers()))
                sender      = ','.join(emlParser.extractEmails(emlParser.getSender()))
                subject     = emlParser.getSubject()
                date        = emlParser.getDate()
                html        = emlParser.getPayloadHtml()
                plain       = emlParser.getPayloadPlain()
                attachments = emlParser.getAttachmentNames()
                path = ""
                properties  = emlParser.getProperties()
                metaInfo    = {}

                for attachment in attachments:
                    data = emlParser.getAttachmentData(attachment)

                    dataTuple = (emlHash, attachment, data)
                    self.connection.execute('INSERT INTO attachments VALUES (?, ?, ?)', dataTuple)

                if meta != "":
                    metaInfo = json.loads(meta.decode("utf-8"))

                    if "Path" in metaInfo:
                        path = metaInfo["Path"]

                dataTuple = (emlHash, sender, receivers, subject, date, html, plain, path, ','.join(attachments), str(properties), str(metaInfo))
                self.connection.execute('INSERT INTO processed VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', dataTuple)

        #except (sqlite3.OperationalError, sqlite3.IntegrityError) as e:
        except Exception as e:
            print("Problem while processing eml=[{0:s}], meta=[{1:s}], id=[{2:s}] \
                       SKIPPED: {3:s}".format(emlFile, metaFile, emlHash, str(e)))

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
            html = row[0]

            # Try to use html text
            if html == "":
                html = row[1]

            return html

    def getAttachements(self, entryId):
        query = "SELECT attachments FROM processed where id = '" + str(entryId) + "'"

        for row in self.connection.execute(query):
            if row[0] == "":
                return []
            return row[0].split(',')

    def downloadAttachment(self, entryId, name):
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

