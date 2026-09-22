#!/usr/bin/env python3
"""Create reviewable change sets; execute separately by exact change-set ARN."""
import argparse,json,time
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from deploy_app import outputs
p=argparse.ArgumentParser()
p.add_argument('--environment',choices=['dev','staging','prod'],required=True)
p.add_argument('--component',choices=['foundation','ecs','ec2'],required=True)
p.add_argument('--execution-role',required=True)
a=p.parse_args();root=Path(__file__).resolve().parents[1]
stack=f'coditude-{a.environment}-{a.component}'
params=json.loads((root/f'infra/environments/{a.environment}.json').read_text())[a.component]
cfn=boto3.client('cloudformation'); exists=False
try:
    current=cfn.describe_stacks(StackName=stack)['Stacks'][0]
    exists=True
except ClientError as exc:
    if exc.response['Error']['Code']!='ValidationError' or 'does not exist' not in str(exc):raise
if exists and a.component=='ecs':
    # Preserve images from RUNNING service revisions, not stale CloudFormation image parameters.
    out=outputs(stack);ecs=boto3.client('ecs')
    for component in ['Frontend','Backend']:
        service=ecs.describe_services(cluster=out['Cluster'],services=[out[component+'Service']])['services'][0]
        task=ecs.describe_task_definition(taskDefinition=service['taskDefinition'])['taskDefinition']
        params[component+'Image']=task['containerDefinitions'][0]['image']
if any('REPLACE_' in str(v) for v in params.values()):
    raise ValueError('Replace environment-specific certificate/image values in parameter JSON first')
change=cfn.create_change_set(StackName=stack,TemplateBody=(root/f'infra/{a.component}.yaml').read_text(),
    Parameters=[{'ParameterKey':k,'ParameterValue':str(v)} for k,v in params.items()],
    Capabilities=['CAPABILITY_IAM'],RoleARN=a.execution_role,
    ChangeSetName=f'review-{int(time.time())}',ChangeSetType='UPDATE' if exists else 'CREATE',
    Description='Reviewed infrastructure change; application images preserved')
try:cfn.get_waiter('change_set_create_complete').wait(ChangeSetName=change['Id'])
except Exception:
    print(json.dumps(cfn.describe_change_set(ChangeSetName=change['Id']),default=str,indent=2));raise
print(json.dumps(cfn.describe_change_set(ChangeSetName=change['Id']),default=str,indent=2))
print('REVIEW then execute this exact change-set ARN: '+change['Id'])
