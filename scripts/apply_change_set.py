import os
import boto3
arn=os.environ['CHANGE_SET_ARN'];expected=os.environ['EXPECTED_STACK']
if ':changeSet/review-' not in arn:raise ValueError('Supply the exact reviewed change set ARN')
client=boto3.client('cloudformation');change=client.describe_change_set(ChangeSetName=arn)
if change['StackName']!=expected or change['Status']!='CREATE_COMPLETE' or change['ExecutionStatus']!='AVAILABLE':
    raise ValueError('Change set is unavailable or belongs to a different stack')
stack=client.describe_stacks(StackName=expected)['Stacks'][0]
creating=stack['StackStatus']=='REVIEW_IN_PROGRESS'
client.execute_change_set(ChangeSetName=arn)
client.get_waiter('stack_create_complete' if creating else 'stack_update_complete').wait(StackName=expected,WaiterConfig={'Delay':30,'MaxAttempts':120})
print('Reviewed infrastructure change applied successfully')
