#!/usr/bin/python3

from mailbox import mbox
from email.header import decode_header
from dateutil.parser import parse

import os
import sys

from dataTypes import Conversation
from dataTypes import Attachment
from dataTypes import Message

from commons import readFile
from commons import extractEmails

class MboxParser():
    def __init__(self, data):
        self.message    = data
        self.body_html  = ""
        self.body_plain = ""
        self._update_payload(self.message)

    def getId(self):
        fromInfo = str(self.message.get_from())
        length = fromInfo.find('@')

        if length != -1:
            return fromInfo[0:length]

        return None

    def getThreadId(self):
        if 'X-GM-THRID' in self.message.keys():
            return self.message['X-GM-THRID']

        return None

    def isLabelSet(self, label):
        if 'X-Gmail-Labels' in self.message.keys():
            if label in self.message['X-Gmail-Labels'].split(','):
                return True

        return False

    def getAttachmentData(self, name):
        for part in self.message.get_payload():
            if isinstance(part, str) or str(part.get_filename()) == 'None':
                continue

            foundName = self._decode_entry(part.get_filename())
            if foundName != name:
                continue

            return part.get_payload(decode=True)

        return None

    def getAttachmentNames(self):
        found = []

        for part in self.message.get_payload():
            if isinstance(part, str) or str(part.get_filename()) == 'None':
                continue

            found.append(self._decode_entry(part.get_filename()))

        return found

    def getPayloadHtml(self):
        return self.body_html

    def getPayloadPlain(self):
        return self.body_plain

    def getSender(self):
        return extractEmails(str(self.message['from']))

    def getReceivers(self):
        return extractEmails(str(self.message['to']))

    def getSubject(self):
        return self._decode_entry(self.message['Subject'])


    def getDate(self):
        fromInfo = str(self.message.get_from())
        length = fromInfo.find(' ')

        if length != -1:
            dt = parse(fromInfo[length+1:])
            return str(dt.date()) + ' ' + str(dt.time())
        else:
            print('TODO date')
            dt = parse(self.message['Date'])
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
                    if (encoding is None) or (encoding == "unknown-8bit"):
                        result += self._decode_body(part[0])
                    else:
                        result += part[0].decode(encoding)

            entry = result

        return entry

    def _decode_body(self, entry):
        try:
            entry = entry.decode('utf-8')
        except UnicodeDecodeError:
            entry = entry.decode('latin-1')

        return entry

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

def _parse_message(message, category):
    result   = []

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

def _parse_conversation(message):
    conversation = Conversation()
    conversation.conversation_id = message.getId()
    conversation.thread_id       = message.getThreadId()
    conversation.date            = message.getDate()

    participants    = message.getSender()
    participants.extend(message.getReceivers())

    sender   = ','.join(message.getSender())
    receiver = ','.join(message.getReceivers())
    # Some data is missing from archive file ...
    # different storage strategy based on used client
    if (not receiver) and (not sender):
        sender = 'me' if message.isLabelSet('Sent') else 'other'
        participants.append(sender)

    conversation.participants = ','.join(list(dict.fromkeys(participants)))

    # Let's beautify it slightly
    content = message.getPayloadHtml()
    if (not content.strip()):
        content = "<div><span style=display:block;float:left;color:#888>"
        content += conversation.date + "&nbsp;&nbsp;&nbsp;&nbsp;</span>"
        content += "<span style=display:block;padding-left:6em;text-indent:-1em>"
        content += "<SPAN>"
        content += "<SPAN style=\"font-weight:bold\">" + sender + ": </SPAN>"
        content += message.getPayloadPlain()
        content += "</SPAN></span></div>"

    # Let's add some extra information to the first message on the thread
    if conversation.thread_id == conversation.conversation_id:
        content = "</div><table cellpadding=0 cellspacing=1><tr><td style=font-size:1;width:100%> \
                   <hr noshade size=1 color=#cccccc><td nowrap style=font-size:80%;color:#aaa>" + \
                   conversation.date + "</td></td></tr></table><div>" + content

    conversation.content = content

    return conversation

def parse_mbox(fileName):
    result   = []

    messages = mbox(fileName)
    base     = os.path.basename(fileName)
    category = '/MailBox/' + ('.').join(base.split('.')[:-1])

    for entry in messages:
        message = MboxParser(entry)

        if (message.isLabelSet('Chat')):
            result.append(_parse_conversation(message))
        else:
            result.extend(_parse_message(message, category))

    return result

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: ' + sys.argv[0] + ' filename.eml')
        exit(-1)

    print(parse_mbox(sys.argv[1]))
