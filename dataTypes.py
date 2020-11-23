class Message():
    def __init__(self):
        self.message_id      = 0
        self.sender          = ""
        self.recipients      = ""
        self.subject         = ""
        self.date            = ""
        self.content         = ""
        self.rich_content    = ""
        self.has_attachments = 0
        self.category        = ""
        self.is_conversation = 0

    def __str__(self):
        return 'Message[' + str(self.message_id) + '] = {' + str(self.sender) + ', ' + str(self.sender) + ', ' + str(self.subject) + '}'

class Content():
    def __init__(self):
        self.message_id = 0
        self.content    = ""

class Messages(Message):
    def __init__(self):
        super(Messages, self).__init__()

class Conversation():
    def __init__(self):
        self.thread_id       = 0
        self.conversation_id = 0
        self.date            = ""
        self.participants    = ""
        self.content         = ""

    def __str__(self):
        return 'Conversation[' + str(self.thread_id) + ', ' + str(self.conversation_id) + ']'

class Conversations(Message):
    def __init__(self):
        super(Conversations, self).__init__()

class Attachment():
    def __init__(self):
        self.message_id    = 0
        self.attachment_id = ""
        self.data          = ""

    def __str__(self):
        return 'Attachment[' + str(self.message_id) + '] = {' + self.attachment_id + '}'

databaseAttrTypes = {
    "message_id"      : "BIGINT",
    "conversation_id" : "BIGINT",
    "thread_id"       : "BIGINT",
    "has_attachments" : "INTEGER",
    "has_attachments" : "INTEGER"
}

databaseTables = [
    'Message',
    'Conversation',
    'Attachment',
    'Content',
    'Messages',
    'Conversations'
]
