#!/usr/bin/env python3
"""Explicit application rollback from a recorded successful release manifest."""
import argparse,json
import boto3
from deploy_app import outputs,wait_ecs
p=argparse.ArgumentParser()
p.add_argument('--runtime',required=True);p.add_argument('--manifest',required=True)
a=p.parse_args();r=json.load(open(a.manifest));runtime=outputs(a.runtime)
if r['mode']=='ecs':
    if r['cluster'] != runtime['Cluster']:raise ValueError('Manifest cluster does not match runtime')
    ecs=boto3.client('ecs')
    for service,task in r['previous'].items():
        if service not in (runtime['FrontendService'],runtime['BackendService']):raise ValueError('Unexpected service')
        ecs.update_service(cluster=r['cluster'],service=service,taskDefinition=task)
    wait_ecs(ecs,r['cluster'],r['previous'])
else:
    client=boto3.client('codedeploy');previous=r.get('previousDeploymentId')
    if not previous:raise ValueError('First release has no earlier successful deployment')
    old=client.get_deployment(deploymentId=previous)['deploymentInfo']
    if old['applicationName']!=runtime['DeploymentApplication'] or old['deploymentGroupName']!=runtime['DeploymentGroup']:
        raise ValueError('Manifest deployment does not match runtime')
    deployment=client.create_deployment(applicationName=runtime['DeploymentApplication'],deploymentGroupName=runtime['DeploymentGroup'],revision=old['revision'],description='Operator rollback')['deploymentId']
    client.get_waiter('deployment_successful').wait(deploymentId=deployment,WaiterConfig={'Delay':15,'MaxAttempts':120})
print('Application rollback completed')
