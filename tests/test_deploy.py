import copy
import pathlib
import sys
import pytest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from deploy_app import clean_task,wait_ecs

def test_task_revision_preserves_runtime_config_and_strips_response_fields():
    task={'family':'api','revision':8,'status':'ACTIVE','taskDefinitionArn':'old',
          'containerDefinitions':[{'name':'backend','image':'old','environment':[{'name':'DB_HOST','value':'private-db'}]}],
          'cpu':'256','memory':'512','taskRoleArn':'app-role','executionRoleArn':'pull-role'}
    original=copy.deepcopy(task)
    result=clean_task(task,'repo@sha256:new')
    assert result['containerDefinitions'][0]['image']=='repo@sha256:new'
    assert result['containerDefinitions'][0]['environment']==task['containerDefinitions'][0]['environment']
    assert 'revision' not in result and 'taskDefinitionArn' not in result
    assert task==original

def test_rejects_ambiguous_multiple_containers():
    with pytest.raises(ValueError):clean_task({'containerDefinitions':[{},{}]},'image')

class FakeEcs:
    def get_waiter(self,name):return self
    def wait(self,**kwargs):pass
    def describe_services(self,**kwargs):return {'services':[{'serviceName':'api','taskDefinition':'rolled-back'}]}

def test_automatic_rollback_is_not_reported_as_release_success():
    with pytest.raises(RuntimeError,match='requested revision'):
        wait_ecs(FakeEcs(),'cluster',{'api':'new-release'})
