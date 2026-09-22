#!/usr/bin/env python3
"""One-time DB login creation, executed by a separate privileged bootstrap project."""
import json,os,urllib.request
import boto3,psycopg
from psycopg import sql
client=boto3.client('secretsmanager')
admin=json.loads(client.get_secret_value(SecretId=os.environ['ADMIN_SECRET_ARN'])['SecretString'])
app=json.loads(client.get_secret_value(SecretId=os.environ['APP_SECRET_ARN'])['SecretString'])
ca='/tmp/rds-ca.pem'
urllib.request.urlretrieve('https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem',ca)
with psycopg.connect(host=os.environ['DB_HOST'],dbname=os.environ['DB_NAME'],user=admin['username'],password=admin['password'],sslmode='verify-full',sslrootcert=ca,connect_timeout=10) as connection:
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(7348291)')
        cursor.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(app['username'],))
        operation='ALTER ROLE' if cursor.fetchone() else 'CREATE ROLE'
        cursor.execute(sql.SQL(operation+' {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE').format(sql.Identifier(app['username']),sql.Literal(app['password'])))
        cursor.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(os.environ['DB_NAME']),sql.Identifier(app['username'])))
        cursor.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
print('Dedicated database login initialized; no credentials printed.')
