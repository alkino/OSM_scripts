#! /usr/bin/env python
# vim: set fileencoding=utf8 :

# This script is python 3 and depends on requests library.

# It is waiting 5 arguments:
# 1) Your OSM email address
# 2) Your OSM password
# 3) A title for PM
# 4) A file with a message for PM
# 5) A file with a message for comment
# You can have variable subsitued in last 3 arguments
# {user} will be replace with the name of user
# {changeset} will be replace by the number of the changeset
# Be aware of never put {XXX} in your message!

# It will not post comment is there i already some comments or if a review is requested. But PM will be sent.

# You can launch it with cron every week.
# @weekly python3 /path/to/welcome_newcomers.py $user $password "Welcome {user}!" $file1 $file2

import re
import sys
import requests
import xml.etree.ElementTree as ET

def login(session, user, passwd):
    r = session.get('https://www.openstreetmap.org/login')
    if r.status_code != 200:
        raise Exception('OSM login status ' + str(r.status_code))
    root = ET.fromstring(r.text)
    fields = {}
    token = root.findall(".//form[@id='login_form']//input")
    for t in token:
        fields[t.attrib['name']] = t.attrib.get('value', None)
    fields['username'] = user
    fields['password'] = passwd
    r = session.post('https://www.openstreetmap.org/login', data = fields)
    if r.status_code != 200:
        raise Exception('OSM login POST status ' + str(r.status_code))
    print('You are connected as "{}".'.format(user))

def sendusermsg(session, user, changeset, msgtitle, msg):
    msgtitle = msgtitle.format(user = user, changeset = changeset)
    msg = msg.format(user = user, changeset = changeset)

    r = session.get('https://www.openstreetmap.org/message/new/' + user)
    if r.status_code != 200:
        raise Exception('OSM status ' + str(r.status_code))
    root = ET.fromstring(r.text.replace('<br>', '<br />'))
    fields = {}
    token = root.findall(".//form[@id='new_message']//input")
    for t in token:
        fields[t.attrib['name']] = t.attrib.get('value', None)
    fields['message[title]'] = msgtitle
    fields['message[body]'] = msg
    r = session.post('https://www.openstreetmap.org/messages', data = fields)
    if r.status_code != 200:
        raise Exception('OSM POST status ' + str(r.status_code))
    if r.text.find('id="error"') > -1:
        raise Exception('You sent too many messages, throttled')
    if not r.url.find('/inbox'):
        raise Exception('Did not get redirected to our Inbox, ' +
                'something likely went wrong and you ' +
                'need to retry.')
    print('Message sent to "{}"'.format(user))

def commentchangeset(session, user, changeset, msg):
    msg = msg.format(user = user, changeset = changeset)

    r = session.get('https://www.openstreetmap.org/changeset/'+str(changeset))
    if r.status_code != 200:
        raise Exception('OSM status ' + str(r.status_code))

    fields = {}
    fields['text'] = msg
    r = session.post('https://www.openstreetmap.org/api/0.6/changeset/'+str(changeset)+'/comment', data = fields)
    if r.status_code != 200:
        raise Exception('OSM POST status ' + str(r.status_code))
    print('Comment posted on changeset "'+str(changeset)+'".')

def changesetisvalid(session, changeset):
    r = session.get('https://www.openstreetmap.org/api/0.6/changeset/'+str(changeset))
    if r.status_code != 200:
        raise Exception('OSM POST status ' + str(r.status_code))

    root = ET.fromstring(r.text)
    token = root.find("./changeset")
    if token.attrib.get('comments_count', '0') != '0':
        return False

    token = root.find(".//tag[@k='review_requested']")
    return token is None or token.attrib.get('v', 'no') != 'yes'

def getuserlist(url):
    regex = re.compile('https://openstreetmap.org/changeset/([0-9]+)')
    r = requests.get("http://resultmaps.neis-one.org/newestosmcountryfeed?c=France")

    root = ET.fromstring(r.text)

    for child in root.findall('./{http://www.w3.org/2005/Atom}entry'):
        username = child.find('./{http://www.w3.org/2005/Atom}id').text[len('http://www.openstreetmap.org/user/'):].strip()
        changeset = regex.search(child.find('./{http://www.w3.org/2005/Atom}content').text).group(1)
        yield username, changeset

if __name__ == "__main__":

    user = sys.argv[1]
    password = sys.argv[2]
    title = sys.argv[3]
    message_PM = sys.argv[4]
    message_comment = sys.argv[5]
    with open(message_PM, 'r') as h:
        PM = h.read()
    with open(message_comment, 'r') as h:
        comment = h.read()

    s = requests.Session()
    s.auth = (user, password) # auth for API
    login(s, user, password)  # login for PM
    for user, changeset in getuserlist("http://resultmaps.neis-one.org/newestosmcountryfeed?c=France"):
        sendusermsg(s, user, changeset, title, PM)
        if not changesetisvalid(s, changeset):
            continue
        commentchangeset(s, user, int(changeset), comment)

