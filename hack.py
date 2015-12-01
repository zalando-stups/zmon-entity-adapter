#!/usr/bin/env python3

# Just a quick hack for now
# Usage:
# ./hack.py <KIO-URL> <TEAM-URL>

import json
import os
import yaml
import logging
import requests
import sys
import zign.api

sess = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
sess.mount('https://', adapter)
requests = sess

kio_url = sys.argv[1]
team_service_url = sys.argv[2]

with open(os.path.expanduser('~/.zmon-cli.yaml')) as fd:
    config = yaml.safe_load(fd)

access_token = zign.api.get_token('zmon-entity-adapter', ['uid'])


def push_entity(entity):
    logging.info('Pushing {type} entity {id}..'.format(**entity))
    body = json.dumps(entity)
    response = requests.put(config['url'] + '/entities/', body, auth=(config['user'], os.getenv('ZMON_PASSWORD')),
                            headers={'Content-Type': 'application/json'})
    response.raise_for_status()


def sync_apps(kio_url, access_token):
    response = requests.get(kio_url + '/apps', headers={'Authorization': 'Bearer {}'.format(access_token)})
    response.raise_for_status()
    apps = response.json()
    for app in apps:
        entity = app.copy()
        entity['id'] = '{}[kio]'.format(app['id'])
        entity['application_id'] = app['id']
        entity['type'] = 'kio_application'
        entity['url'] = app['service_url']
        entity['active'] = str(entity['active'])
        push_entity(entity)


def sync_teams(team_service_url, access_token):

    aws_consolidated_billing_account_id = os.getenv('AWS_CONSOLIDATED_BILLING_ACCOUNT_ID')

    response = requests.get(team_service_url + '/api/teams',
                            headers={'Authorization': 'Bearer {}'.format(access_token)})
    response.raise_for_status()
    teams = response.json()
    for team in teams:
        if not team['id']:
            continue
        entity = {}
        entity['id'] = 'team-{}[team]'.format(team['team_id'])
        entity['name'] = team['id']
        entity['long_name'] = team.get('id_name') or team['id']
        entity['type'] = 'team'
        push_entity(entity)

        r = requests.get(team_service_url + '/api/teams/' + team['id'],
                         headers={'Authorization': 'Bearer {}'.format(access_token)})
        r.raise_for_status()
        data = r.json()
        for infra in data.get('infrastructure-accounts', []):
            entity = {}
            entity['id'] = '{}-{}[infrastructure-account]'.format(infra['type'], infra['id'])
            entity['type'] = 'infrastructure_account'
            entity['account_type'] = infra['type']
            entity['account_id'] = infra['id']
            entity['name'] = infra['name']
            push_entity(entity)

            if aws_consolidated_billing_account_id and infra['type'] == 'aws':
                entity = {}
                entity['id'] = 'aws-bill-{}[aws:{}]'.format(infra['name'], aws_consolidated_billing_account_id)
                entity['type'] = 'aws_billing'
                entity['account_id'] = infra['id']
                entity['name'] = infra['name']
                entity['infrastructure_account'] = 'aws:{}'.format(aws_consolidated_billing_account_id)
                push_entity(entity)


logging.basicConfig(level=logging.INFO)
#sync_apps(kio_url, access_token)
sync_teams(team_service_url, access_token)
