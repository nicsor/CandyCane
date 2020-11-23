import re
import pickle
import hashlib

def readFile(filename):
    with open(filename, 'rb') as file:
        blobData = file.read()
    return blobData

def extractEmails(text):
    emails = re.findall('([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)', text)
    emails = list(dict.fromkeys(emails))
    return emails

def getHashOfItem(item):
    h = hashlib.sha1()
    h.update(pickle.dumps(item))
    return int(h.hexdigest(), 16) % (1 << 63)
