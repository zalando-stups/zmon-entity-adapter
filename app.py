#!/usr/bin/env python3
import collections
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

ENTITY_STATS = collections.defaultdict(int)


def normalized_dict(d):
    try:
        return json.loads(json.dumps(d))
    except:
        # As a safe fallback!
        return d


def new_or_updated_entity(entity, existing_entities_dict):
    # check if new entity
    if entity['id'] not in existing_entities_dict:
        return True

    entity.pop('last_modified', None)
    existing_entities_dict[entity['id']].pop('last_modified', None)

    return normalized_dict(entity) != normalized_dict(existing_entities_dict[entity['id']])


def push_entity(entity, access_token):
    logging.info('Pushing {type} entity {id}..'.format(**entity))
    body = json.dumps(entity)
    response = requests.put(os.getenv('ZMON_URL') + '/entities/', body,
                            headers={'Content-Type': 'application/json',
                                     'Authorization': 'Bearer {}'.format(access_token)})
    response.raise_for_status()
    ENTITY_STATS[entity['type']] += 1


def get_entities(types, access_token):
    query = [{'type': _type} for _type in types]
    r = requests.get(os.getenv('ZMON_URL') + '/entities', params={'query': json.dumps(query)}, timeout=10,
                     headers={'Authorization': 'Bearer {}'.format(access_token)})
    r.raise_for_status()
    entities = {}
    for ent in r.json():
        entities[ent['id']] = ent
    return entities


def sync_apps(entities, kio_url, access_token):
    response = requests.get(kio_url + '/apps', headers={'Authorization': 'Bearer {}'.format(access_token)})
    response.raise_for_status()
    apps = response.json()
    logging.info('Syncing {} Kio applications..'.format(len(apps)))
    for app in apps:
        entity = app.copy()
        entity['id'] = '{}[kio]'.format(app['id'])
        entity['application_id'] = app['id']
        entity['type'] = 'kio_application'
        entity['url'] = app['service_url']
        entity['active'] = str(entity['active'])
        if new_or_updated_entity(entity, entities):
            push_entity(entity, access_token)


def sync_teams(entities, team_service_url, access_token):
    aws_consolidated_billing_account_id = os.getenv('AWS_CONSOLIDATED_BILLING_ACCOUNT_ID')

    response = requests.get(team_service_url + '/api/teams',
                            headers={'Authorization': 'Bearer {}'.format(access_token)})
    response.raise_for_status()
    teams = response.json()
    logging.info('Syncing {} teams..'.format(len(teams)))
    for team in teams:
        if not team['id']:
            continue
        entity = {}
        entity['id'] = 'team-{}[team]'.format(team['team_id'])
        entity['name'] = team['id']
        entity['long_name'] = team.get('id_name') or team['id']
        entity['type'] = 'team'
        if new_or_updated_entity(entity, entities):
            push_entity(entity, access_token)

        try:
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
                entity['owner'] = infra.get('owner')
                # NOTE: all entity values need to be strings!
                entity['disabled'] = str(infra.get('disabled', False))
                if new_or_updated_entity(entity, entities):
                    push_entity(entity, access_token)

                if aws_consolidated_billing_account_id and infra['type'] == 'aws':
                    entity = {}
                    entity['id'] = 'aws-bill-{}[aws:{}]'.format(infra['name'], aws_consolidated_billing_account_id)
                    entity['type'] = 'aws_billing'
                    entity['account_id'] = infra['id']
                    entity['name'] = infra['name']
                    entity['infrastructure_account'] = 'aws:{}'.format(aws_consolidated_billing_account_id)
                    if new_or_updated_entity(entity, entities):
                        push_entity(entity, access_token)
        except:
            logging.exception('Failed to update team {}'.format(team['id']))


def sync_clusters(entities, cluster_registry_url, access_token):
    response = requests.get(cluster_registry_url + '/kubernetes-clusters',
                            headers={'Authorization': 'Bearer {}'.format(access_token)})
    response.raise_for_status()
    clusters = response.json()['items']
    logging.info('Syncing {} Kubernetes clusters..'.format(len(clusters)))
    for cluster in clusters:
        entity = {}
        entity['id'] = '{}[kubernetes-cluster]'.format(cluster['id'])
        entity['api_server_url'] = cluster['api_server_url']
        entity['type'] = 'kubernetes_cluster'
        if new_or_updated_entity(entity, entities):
            push_entity(entity, access_token)


def run_update(signum):
    if uwsgi.is_locked(signum):
        return
    uwsgi.lock(signum)
    try:
        tokens.manage('zmon-entity-adapter', ['uid'])
        access_token = tokens.get('zmon-entity-adapter')
        entities = get_entities(('kio_application', 'team', 'infrastructure_account', 'aws_billing', 'kubernetes_cluster'), access_token)
        sync_apps(entities, os.getenv('KIO_URL'), access_token)
        sync_teams(entities, os.getenv('TEAM_SERVICE_URL'), access_token)
        sync_clusters(entities, os.getenv('CLUSTER_REGISTRY_URL'), access_token)
        logging.info('Update finished. Pushed entities: {}'.format(ENTITY_STATS))
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

try:
    import uwsgi
    signum = 1
    uwsgi.register_signal(signum, "", run_update)
    uwsgi.add_timer(signum, int(os.getenv('UPDATE_INTERVAL_SECONDS', '300')))
except Exception as e:
    print(e)

if __name__ == '__main__':
    app.run(port=8080)
