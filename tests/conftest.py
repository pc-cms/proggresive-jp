import os
os.environ['DATABASE_URL']='postgresql://postgres:local-test-only@127.0.0.1:55432/progressive_test'
os.environ['REQUIRE_TLS']='1'
import pytest
from fastapi.testclient import TestClient
from app.db import connection
from app.bootstrap import initialize
from app.main import app

@pytest.fixture
def env():
    with connection() as c:
        assert c.execute('SELECT current_database() AS d').fetchone()['d']=='progressive_test'
        c.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public')
    initialize('unique-test-password-123')
    client=TestClient(app,base_url='https://testserver')
    token=client.post('/api/v1/login',json={'name':'admin','password':'unique-test-password-123'}).json()['token']
    client.headers['Authorization']='Bearer '+token
    return client
