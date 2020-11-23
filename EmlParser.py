#!/usr/bin/python3

from email import policy
from email.header import decode_header
from email.parser import BytesParser
from dateutil.parser import parse

import pathlib
import json
import sys

from dataTypes import Attachment
from dataTypes import Message

from commons import readFile
from commons import extractEmails
from commons import getHashOfItem

class EmlParser():
    def __init__(self, fileName):
        self.message = BytesParser(policy=policy.default).parsebytes(readFile(fileName))

    def getId(self):
        return getHashOfItem(self.message)

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
               if kv.startswith('filename='):
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
               if kv.startswith('filename='):
                   key, _, val = kv.partition('=')

                   if val.startswith('"'):
                       val = val.strip('"')
                   elif val.startswith("'"):
                       val = val.strip("'")

                   found.append(val)

        return found

    def getPayloadHtml(self):
        body = self.message.get_body('html')

        if (body):
           return self._decode_body(body.get_payload(decode=True))

        return ''

    def getPayloadPlain(self):
        body = self.message.get_body('plain')

        if (body):
           return self._decode_body(body.get_payload(decode=True))

        return ''

    def getSender(self):
        return extractEmails(str(self.message['from']))

    def getReceivers(self):
        return extractEmails(str(self.message['to']))

    def getSubject(self):
        return self._decode_entry(self.message['Subject'])

    def getDate(self):
        dt = parse(self.message['Date'])
        return str(dt.date()) + " " + str(dt.time())

    def _decode_entry(self, entry):
        if entry is None:
            entry = ''
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

def parse_eml(fileName):
    message  = EmlParser(fileName)
    result   = []
    category = ''

    metaFile = fileName + '.meta'
    if pathlib.Path(metaFile).exists():
        meta = json.loads(readFile(metaFile))
        if 'Path' in meta:
            category = meta['Path']

    attachments = message.getAttachmentNames()

    msg = Message()
    msg.message_id      = message.getId()
    msg.sender          = ','.join(message.getSender())
    msg.recipients      = ','.join(message.getReceivers())
    msg.subject         = message.getSubject()
    msg.date            = message.getDate()
    msg.content         = message.getPayloadPlain()
    msg.rich_content    = message.getPayloadHtml()
    msg.has_attachments = len(attachments)
    msg.category        = category

    for attachmentName in attachments:
        attachment = Attachment()
        attachment.message_id    = msg.message_id
        attachment.attachment_id = attachmentName
        attachment.data          = message.getAttachmentData(attachmentName)
        result.append(attachment)
    result.append(msg)

    return result

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: ' + sys.argv[0] + ' filename.eml')
        exit(-1)

    print(parse_eml(sys.argv[1]))
