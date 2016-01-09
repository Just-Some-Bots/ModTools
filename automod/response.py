class Response(object):
    def __init__(self, content, reply=False, delete_incoming=False, pm=False, trigger=False):
        self.content = content
        self.reply = reply
        self.delete_incoming = delete_incoming
        self.pm = pm
        self.trigger = trigger