#!/usr/bin/env python3
import connexion
import json
import logging
import os
import requests
import tokens

sess = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
sess.mount('https://', adapter)
requests = sess


def push_entity(entity):
    logging.info('Pushing {type} entity {id}..'.format(**entity))
    body = json.dumps(entity)
    if os.getenv('ZMON_USER'):
        auth = (os.getenv('ZMON_USER'), os.getenv('ZMON_PASSWORD'))
    else:
        auth = None
    response = requests.put(os.getenv('ZMON_URL') + '/entities/', body,
                            auth=auth,
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


def run_update(signum):
    if uwsgi.is_locked(signum):
        return
    uwsgi.lock(signum)
    try:
        tokens.manage('zmon-entity-adapter', ['uid'])
        access_token = tokens.get('zmon-entity-adapter')
        sync_apps(os.getenv('KIO_URL'), access_token)
        sync_teams(os.getenv('TEAM_SERVICE_URL'), access_token)
    finally:
        uwsgi.unlock(signum)


def get_health():
    return True


logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
app = connexion.App(__name__)
app.add_api('swagger.yaml')
# set the WSGI application callable to allow using uWSGI:
# uwsgi --http :8080 -w app
application = app.app
logging.info('TEST')

try:
    import uwsgi
    signum = 1
    uwsgi.register_signal(signum, "", run_update)
    uwsgi.add_timer(signum, 10)
except Exception as e:
    print(e)

if __name__ == '__main__':
    app.run(port=8080)
