#!/usr/bin/env python3
"""Build/publish/deploy applications only. No CloudFormation write operations."""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import zipfile
import boto3

ROOT = Path(__file__).resolve().parents[1]

def run(*args, cwd=ROOT, **kwargs):
    subprocess.run(args, cwd=cwd, check=True, **kwargs)

def outputs(stack):
    data = boto3.client('cloudformation').describe_stacks(StackName=stack)['Stacks'][0]
    return {v['OutputKey']:v['OutputValue'] for v in data['Outputs']}

def clean_task(task, image):
    # Only fields accepted by RegisterTaskDefinition; do not copy AWS read-only fields.
    allowed = {'family','taskRoleArn','executionRoleArn','networkMode','containerDefinitions',
               'volumes','placementConstraints','requiresCompatibilities','cpu','memory',
               'pidMode','ipcMode','proxyConfiguration','inferenceAccelerators',
               'ephemeralStorage','runtimePlatform'}
    result = {k:v for k,v in task.items() if k in allowed}
    if len(result['containerDefinitions']) != 1:
        raise ValueError('Expected one application container per service')
    result['containerDefinitions'] = [dict(result['containerDefinitions'][0], image=image)]
    return result

def wait_ecs(ecs, cluster, desired):
    ecs.get_waiter('services_stable').wait(cluster=cluster, services=list(desired),
                                         WaiterConfig={'Delay':15,'MaxAttempts':80})
    services = ecs.describe_services(cluster=cluster, services=list(desired))['services']
    # services_stable can succeed after automatic rollback; explicitly verify the release.
    if len(services) != len(desired) or any(s['taskDefinition'] != desired[s['serviceName']] for s in services):
        raise RuntimeError('ECS is stable but the requested revision did not deploy')

def smoke_test(url):
    if not url.startswith('https://'):
        raise ValueError('Use the HTTPS application hostname matching the ACM certificate')
    last_error = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url.rstrip('/')+'/api/ready', timeout=10) as response:
                result = json.load(response)
                if result.get('status') != 'ready':
                    raise RuntimeError('Application readiness probe failed')
            with urllib.request.urlopen(url.rstrip('/')+'/', timeout=10) as response:
                if b'Deployment check' not in response.read():
                    raise RuntimeError('Frontend smoke check failed')
            return
        except Exception as exc:
            last_error = exc
            time.sleep(3)
    raise RuntimeError('End-to-end HTTPS smoke test failed') from last_error

def deploy_ecs(runtime, images, url):
    ecs = boto3.client('ecs'); cluster = runtime['Cluster']
    old, new = {}, {}
    for component in ['Frontend','Backend']:
        service = runtime[component+'Service']
        current = ecs.describe_services(cluster=cluster, services=[service])['services'][0]
        old[service] = current['taskDefinition']
        task = ecs.describe_task_definition(taskDefinition=current['taskDefinition'])['taskDefinition']
        new[service] = ecs.register_task_definition(**clean_task(task, images[component]))['taskDefinition']['taskDefinitionArn']
    try:
        for service, task in new.items():
            ecs.update_service(cluster=cluster, service=service, taskDefinition=task)
        wait_ecs(ecs, cluster, new)
        smoke_test(url)
    except Exception:
        for service, task in old.items():
            ecs.update_service(cluster=cluster, service=service, taskDefinition=task)
        wait_ecs(ecs, cluster, old)
        raise
    return {'cluster':cluster,'previous':old,'deployed':new}

def build_images(foundation, revision):
    ecr=boto3.client('ecr')
    auth=ecr.get_authorization_token()['authorizationData'][0]
    username,password=base64.b64decode(auth['authorizationToken']).decode().split(':',1)
    run('docker','login','--username',username,'--password-stdin',auth['proxyEndpoint'], input=password.encode())
    images={}
    for component in ['Frontend','Backend']:
        repository=foundation[component+'Repository']; uri=foundation[component+'RepositoryUri']
        try:
            detail=ecr.describe_images(repositoryName=repository,imageIds=[{'imageTag':revision}])['imageDetails'][0]
        except ecr.exceptions.ImageNotFoundException:
            run('docker','build','--platform','linux/amd64','-t',uri+':'+revision,str(ROOT/'apps'/component.lower()))
            run('docker','push',uri+':'+revision)
            detail=ecr.describe_images(repositoryName=repository,imageIds=[{'imageTag':revision}])['imageDetails'][0]
        images[component]=uri+'@'+detail['imageDigest']
    return images

def package_ec2(revision):
    frontend=ROOT/'apps/frontend'
    run('npm','ci',cwd=frontend);run('npm','run','build',cwd=frontend)
    stage=ROOT/'dist'/('ec2-'+revision)
    if stage.exists():shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copytree(frontend/'.next/standalone',stage/'frontend')
    shutil.copytree(frontend/'.next/static',stage/'frontend/.next/static',dirs_exist_ok=True)
    shutil.copytree(ROOT/'apps/backend',stage/'backend',ignore=shutil.ignore_patterns('__pycache__','.venv'))
    shutil.copytree(ROOT/'deploy/ec2/hooks',stage/'hooks')
    shutil.copytree(ROOT/'deploy/ec2/systemd',stage/'systemd')
    shutil.copy(ROOT/'deploy/ec2/appspec.yml',stage/'appspec.yml')
    (stage/'certs').mkdir()
    urllib.request.urlretrieve('https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem',stage/'certs/global-bundle.pem')
    (stage/'REVISION').write_text(revision+'\n')
    # ZIP paths must be at artifact root for CodeDeploy.
    archive=ROOT/'dist'/('ec2-'+revision+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in stage.rglob('*'):
            if file.is_file():z.write(file,file.relative_to(stage))
    return archive

def deploy_ec2(runtime, foundation, archive, revision, url):
    bucket=foundation['Artifacts']; key=f'releases/{revision}/application.zip'
    s3=boto3.client('s3');s3.upload_file(str(archive),bucket,key)
    version=s3.head_object(Bucket=bucket,Key=key)['VersionId']
    client=boto3.client('codedeploy')
    group=client.get_deployment_group(applicationName=runtime['DeploymentApplication'],deploymentGroupName=runtime['DeploymentGroup'])['deploymentGroupInfo']
    previous=group.get('lastSuccessfulDeployment',{}).get('deploymentId')
    deployment=client.create_deployment(applicationName=runtime['DeploymentApplication'],deploymentGroupName=runtime['DeploymentGroup'],
        revision={'revisionType':'S3','s3Location':{'bucket':bucket,'key':key,'bundleType':'zip','version':version}},
        description='Git revision '+revision)['deploymentId']
    client.get_waiter('deployment_successful').wait(deploymentId=deployment,WaiterConfig={'Delay':15,'MaxAttempts':120})
    try:
        smoke_test(url)
    except Exception:
        if previous:
            old = client.get_deployment(deploymentId=previous)['deploymentInfo']
            rollback = client.create_deployment(applicationName=runtime['DeploymentApplication'],
                deploymentGroupName=runtime['DeploymentGroup'], revision=old['revision'],
                description='Automatic rollback after HTTPS smoke failure')['deploymentId']
            client.get_waiter('deployment_successful').wait(deploymentId=rollback,
                WaiterConfig={'Delay':15,'MaxAttempts':120})
        raise
    return {'deploymentId':deployment,'previousDeploymentId':previous,'bucket':bucket,'key':key,'version':version}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--foundation',required=True);p.add_argument('--runtime')
    p.add_argument('--mode',choices=['ecs','ec2'],required=True)
    p.add_argument('--url',help='HTTPS application origin required for deployment')
    p.add_argument('--revision',required=True);p.add_argument('--build-only',action='store_true')
    args=p.parse_args()
    if not args.revision.isalnum() or len(args.revision)>64:raise ValueError('Revision must be an alphanumeric Git SHA')
    if not args.build_only and not args.runtime:p.error('--runtime is required for deployment')
    if not args.build_only and not args.url:p.error('--url is required for the end-to-end smoke test')
    foundation=outputs(args.foundation)
    result={'revision':args.revision,'mode':args.mode}
    if args.mode=='ecs':
        images=build_images(foundation,args.revision);result['images']=images
        if not args.build_only:result.update(deploy_ecs(outputs(args.runtime),images,args.url))
    else:
        archive=package_ec2(args.revision);result['archive']=str(archive.relative_to(ROOT))
        if not args.build_only:result.update(deploy_ec2(outputs(args.runtime),foundation,archive,args.revision,args.url))
    (ROOT/'dist').mkdir(exist_ok=True)
    (ROOT/'dist/release.json').write_text(json.dumps(result,indent=2)+'\n')
    if not args.build_only:
        boto3.client('s3').put_object(Bucket=foundation['Artifacts'],Key=f'releases/{args.revision}/{args.mode}-release.json',Body=json.dumps(result).encode(),ContentType='application/json')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
