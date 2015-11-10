#!/usr/bin/env python3

# Just a quick hack for now
# Usage:
# zign token -n zmon-entity-adapter
# ./hack.py <KIO-URL> <TEAM-URL>

import json
import os
import yaml
import requests
import sys
import zign.api

kio_url = sys.argv[1]
team_service_url = sys.argv[2]

with open(os.path.expanduser('~/.zmon-cli.yaml')) as fd:
    config = yaml.safe_load(fd)

token = zign.api.get_existing_token('zmon-entity-adapter')
access_token = token['access_token']

def push_entity(entity):
    body = json.dumps(entity)
    response = requests.put(config['url'] + '/entities/', body, auth=(config['user'], config['password']), headers={'Content-Type': 'application/json'})
    print(response.text)


response = requests.get(kio_url + '/apps', headers={'Authorization': 'Bearer {}'.format(access_token)})
apps = response.json()
for app in apps:
    print(app)
    entity = app.copy()
    entity['id'] = '{}[kio]'.format(app['id'])
    entity['application_id'] = app['id']
    entity['type'] = 'kio_application'
    entity['url'] = app['service_url']
    entity['active'] = str(entity['active'])
    push_entity(entity)
response = requests.get(team_service_url, headers={'Authorization': 'Bearer {}'.format(access_token)})
teams = response.json()
for team in teams:
    print(team)
    entity = team.copy()
    entity['id'] = '{}[team-service]'.format(team['id'])
    entity['team_id'] = team['id']
    entity['type'] = 'team'
    push_entity(entity)
