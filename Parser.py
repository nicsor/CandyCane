from EmlParser import parse_eml
from MboxParser import parse_mbox
from dataTypes import *
import pathlib

def parseEmailFile(path, fileType):
    if fileType == 'eml':
        return parse_eml(path)
    elif fileType == 'mbox':
        return parse_mbox(path)

def parseEmailFolder(db, dirname, entryType):
    failed = []

    messageIds = set(db.getMessageIds())
    conversationsIds = set(db.getConversationIds())

    for path in pathlib.Path(dirname).rglob('*.' + entryType):
        # Iup, seems like a redundant parameter :)
        entries = parseEmailFile(str(path), entryType)

        for entry in entries:

            # Filter inserted id's to avoid the sql unique id error
            # Should make sure the id's I'm using are ok and probably
            # avoid these checks for emls
            if isinstance(entry, Message) or isinstance(entry, Attachment):
               if entry.message_id in messageIds:
                   continue
               # Ugly trick to share the same list. (attachments are added before)
               if isinstance(entry, Message):
                   messageIds.add(entry.message_id)

            if isinstance(entry, Conversation):
               id = (int(entry.thread_id), int(entry.conversation_id))

               if id in conversationsIds:
                   continue

               conversationsIds.add(id)
              
            try:
                db.insert(entry)
            except Exception as err:
                print("Back to the drawing board: {0} for {1}".format(err, entry))

    if len(failed) > 0:
        print ("Failed adding : " + ','.join(failed))

    if entryType == 'mbox':
        db.groupConversations()
