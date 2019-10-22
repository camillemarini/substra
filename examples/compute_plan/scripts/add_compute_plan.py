import json
import os
import uuid
import zipfile

import substra

current_directory = os.path.dirname(__file__)
assets_keys_path = os.path.join(current_directory, '../../titanic/assets_keys.json')
compute_plan_keys_path = os.path.join(current_directory, '../compute_plan_keys.json')

with open(os.path.join(current_directory, '../../config.json'), 'r') as f:
    config = json.load(f)

client = substra.Client()
client.add_profile(config['profile_name'], config['username'], config['password'],  config['url'])
client.login()

print(f'Loading existing asset keys from {os.path.abspath(assets_keys_path)}...')
with open(assets_keys_path, 'r') as f:
    assets_keys = json.load(f)

train_data_sample_keys = assets_keys['train_data_sample_keys']
objective_key = assets_keys['objective_key']
dataset_key = assets_keys['dataset_key']

print('Adding algo...')
algo_directory = os.path.join(current_directory, '../assets/algo_sgd')
archive_path = 'algo_sgd.zip'
with zipfile.ZipFile(archive_path, 'w') as z:
    for filename in ['algo.py', 'Dockerfile']:
        z.write(os.path.join(algo_directory, filename), arcname=filename)

algo_key = client.add_algo({
    'name': 'SGD classifier death predictor',
    'file': archive_path,
    'description': os.path.join(algo_directory, 'description.md')
}, exist_ok=True)['pkhash']


print(f'Generating compute plan...')
traintuples = []
testtuples = []
previous_id = None
for train_data_sample_key in train_data_sample_keys:
    traintuple = {
        'data_manager_key': dataset_key,
        'train_data_sample_keys': [train_data_sample_key],
        'traintuple_id': uuid.uuid4().hex,
        'in_models_ids': [previous_id] if previous_id else [],
    }
    testtuple = {
        'traintuple_id': traintuple['traintuple_id']
    }
    traintuples.append(traintuple)
    testtuples.append(testtuple)
    previous_id = traintuple['traintuple_id']


print('Adding compute plan...')
compute_plan = client.add_compute_plan({
    "algo_key": algo_key,
    "objective_key": objective_key,
    "traintuples": traintuples,
    "testtuples": testtuples,
})
compute_plan_id = compute_plan.get('computePlanID')

with open(compute_plan_keys_path, 'w') as f:
    json.dump(compute_plan, f, indent=2)

print(f'Compute plan keys have been saved to {os.path.abspath(compute_plan_keys_path)}')
