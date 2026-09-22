"""Offline contract checks. Complements cfn-lint, does not prove AWS deployment."""
from pathlib import Path
import ast
import json
import subprocess
import yaml
root=Path(__file__).resolve().parents[1]
for path in (root/'infra').glob('*.yaml'):
    document=yaml.safe_load(path.read_text())
    assert document.get('AWSTemplateFormatVersion')=='2010-09-09',path
    for name, resource in document.get('Resources', {}).items():
        if resource.get('Type') == 'AWS::IAM::Role':
            for policy in resource['Properties'].get('Policies', []):
                assert policy['PolicyDocument']['Statement'], f'{path}:{name} has an empty IAM policy'
for path in (root/'.github/workflows').glob('*.yml'):
    document=yaml.load(path.read_text(),Loader=yaml.BaseLoader)
    assert 'on' in document and 'jobs' in document,path
for path in (root/'infra/environments').glob('*.json'):json.loads(path.read_text())
for directory in ['scripts','apps/backend','tests']:
    for path in (root/directory).rglob('*.py'):ast.parse(path.read_text(),filename=str(path))
for path in (root/'deploy/ec2/hooks').glob('*.sh'):subprocess.run(['bash','-n',str(path)],check=True)
source=(root/'scripts/deploy_app.py').read_text()
for forbidden in ['create_stack(', 'update_stack(', 'create_change_set(', 'execute_change_set(', 'delete_stack(']:
    assert forbidden not in source,'Application deployment contains infrastructure writes'
assert 'services_stable' in source and "s['taskDefinition'] != desired[s['serviceName']]" in source
for name in ['application.yml','infrastructure.yml']:
    doc=yaml.load((root/'.github/workflows'/name).read_text(),Loader=yaml.BaseLoader)
    paths=doc['on']['push']['paths']
    assert ('infra/**' in paths)==(name=='infrastructure.yml')
print('PASS: templates/YAML/JSON/Python/shell parse; app/infra path separation and release verification contracts')
