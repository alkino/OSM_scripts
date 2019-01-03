#! /usr/bin/env python
# vim: set fileencoding=utf8 :

# This script is python 3 and depends on requests library.

# You can have variable subsitued in title, pm and comment.
# {user} will be replace with the name of user
# {changeset} will be replace by the number of the changeset

# It will not post comment is there i already some comments or if a review is requested. But PM will be sent.

# You can launch it with cron every week.
# @weekly python3 /path/to/welcome_newcomers.py $user $password "Welcome {user}!" $file1 $file2

import re
import sys
import argparse
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

def sendusermsg(session, user, changeset, msgtitle, msg, dry_run):
    msgtitle = msgtitle.format(user = user, changeset = changeset)
    msg = msg.format(user = user, changeset = changeset)

    if not dry_run:
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
    print('Message sent to "{}" with title "{}"'.format(user, msgtitle))

def commentchangeset(session, user, changeset, msg, dry_run):
    if not dry_run:
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

def getuserlist(country):
    regex = re.compile('https://openstreetmap.org/changeset/([0-9]+)')
    r = requests.get("http://resultmaps.neis-one.org/newestosmcountryfeed?c="+country)

    root = ET.fromstring(r.text)

    for child in root.findall('./{http://www.w3.org/2005/Atom}entry'):
        username = child.find('./{http://www.w3.org/2005/Atom}id').text[len('http://www.openstreetmap.org/user/'):].strip()
        changeset = regex.search(child.find('./{http://www.w3.org/2005/Atom}content').text).group(1)
        yield username, changeset

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user', help='Username to connect to osm.org', required=True)
    parser.add_argument('-p', '--password', help='Password associated to user for connection', required=True, type=argparse.FileType('r'))
    parser.add_argument('-t', '--title', help='Title of the PM', default='Welcome to you!')
    parser.add_argument('--pm-file', help='File of message for PM', type=argparse.FileType('r'))
    parser.add_argument('--comment-file', help='File of message for comment', type=argparse.FileType('r'))
    parser.add_argument('-c', '--country', help='Country for welcome new members', default='France')
    parser.add_argument('-n', '--dry-run', help='Only print, but do not really send message', action='store_true')
    parser.add_argument('--always-send-PM', help='Send PM event if changeset is considered invalid', action='store_true')
    args = parser.parse_args()

    password = args.password.read().strip()

    s = requests.Session()
    s.auth = (args.user, password) # auth for API
    login(s, args.user, password)  # login for PM
    for user, changeset in getuserlist(args.country):
        if changesetisvalid(s, changeset):
            if args.pm_file:
                sendusermsg(s, user, changeset, args.title, args.pm_file.read(), args.dry_run)
            if args.comment_file:
                commentchangeset(s, user, int(changeset), args.comment_file.read(), args.dry_run)
        elif args.always_send_PM and args.pm_file:
            sendusermsg(s, user, changeset, args.title, args.pm_file.read(), args.dry_run)

