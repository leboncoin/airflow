#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import pytest
import werkzeug

from airflow.models import DagBag, DagRun, TaskInstance
from airflow.security import permissions
from airflow.utils import timezone
from airflow.utils.session import create_session
from airflow.www.views import DagRunModelView
from tests.test_utils.api_connexion_utils import create_user, delete_roles, delete_user
from tests.test_utils.www import check_content_in_response, client_with_login
from tests.www.views.test_views_tasks import _get_appbuilder_pk_string


@pytest.fixture(scope="module")
def client_dr_without_dag_edit(app):
    create_user(
        app,
        username="all_dr_permissions_except_dag_edit",
        role_name="all_dr_permissions_except_dag_edit",
        permissions=[
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_DAG),
            (permissions.ACTION_CAN_CREATE, permissions.RESOURCE_DAG_RUN),
            (permissions.ACTION_CAN_READ, permissions.RESOURCE_DAG_RUN),
            (permissions.ACTION_CAN_EDIT, permissions.RESOURCE_DAG_RUN),
            (permissions.ACTION_CAN_DELETE, permissions.RESOURCE_DAG_RUN),
            (permissions.ACTION_CAN_ACCESS_MENU, permissions.RESOURCE_DAG_RUN),
        ],
    )

    yield client_with_login(
        app,
        username="all_dr_permissions_except_dag_edit",
        password="all_dr_permissions_except_dag_edit",
    )

    delete_user(app, username="all_dr_permissions_except_dag_edit")  # type: ignore
    delete_roles(app)


@pytest.fixture(scope="module", autouse=True)
def init_blank_dagrun():
    """Make sure there are no runs before we test anything.

    This really shouldn't be needed, but tests elsewhere leave the db dirty.
    """
    with create_session() as session:
        session.query(DagRun).delete()
        session.query(TaskInstance).delete()


@pytest.fixture(autouse=True)
def reset_dagrun():
    yield
    with create_session() as session:
        session.query(DagRun).delete()
        session.query(TaskInstance).delete()


def test_create_dagrun_permission_denied(session, client_dr_without_dag_edit):
    data = {
        "state": "running",
        "dag_id": "example_bash_operator",
        "execution_date": "2018-07-06 05:06:03",
        "run_id": "test_list_dagrun_includes_conf",
        "conf": '{"include": "me"}',
    }

    with pytest.raises(werkzeug.test.ClientRedirectError):
        client_dr_without_dag_edit.post('/dagrun/add', data=data, follow_redirects=True)


def test_clear_dag_runs_action(session, admin_client):
    dag = DagBag().get_dag("example_bash_operator")
    task0 = dag.get_task("runme_0")
    task1 = dag.get_task("runme_1")
    execution_date = timezone.datetime(2016, 1, 9)
    tis = [
        TaskInstance(task0, execution_date, state="success"),
        TaskInstance(task1, execution_date, state="failed"),
    ]
    session.bulk_save_objects(tis)
    dr = dag.create_dagrun(
        state="running",
        execution_date=execution_date,
        run_id="test_clear_dag_runs_action",
        session=session,
    )

    data = {"action": "clear", "rowid": [dr.id]}
    resp = admin_client.post("/dagrun/action_post", data=data, follow_redirects=True)
    check_content_in_response("1 dag runs and 2 task instances were cleared", resp)
    assert [ti.state for ti in session.query(TaskInstance).all()] == [None, None]


@pytest.fixture()
def running_dag_run(session):
    dag = DagBag().get_dag("example_bash_operator")
    task0 = dag.get_task("runme_0")
    task1 = dag.get_task("runme_1")
    execution_date = timezone.datetime(2016, 1, 9)
    dr = dag.create_dagrun(
        state="running",
        execution_date=execution_date,
        run_id="test_clear_dag_runs_action",
        session=session,
    )
    session.add(dr)
    tis = [
        TaskInstance(task0, execution_date, state="success"),
        TaskInstance(task1, execution_date, state="failed"),
    ]
    session.bulk_save_objects(tis)
    session.flush()
    return dr


def test_delete_dagrun(session, admin_client, running_dag_run):
    composite_key = _get_appbuilder_pk_string(DagRunModelView, running_dag_run)
    assert session.query(DagRun).filter(DagRun.dag_id == running_dag_run.dag_id).count() == 1
    admin_client.post(f"/dagrun/delete/{composite_key}", follow_redirects=True)
    assert session.query(DagRun).filter(DagRun.dag_id == running_dag_run.dag_id).count() == 0


def test_delete_dagrun_permission_denied(session, client_dr_without_dag_edit, running_dag_run):
    composite_key = _get_appbuilder_pk_string(DagRunModelView, running_dag_run)

    assert session.query(DagRun).filter(DagRun.dag_id == running_dag_run.dag_id).count() == 1
    resp = client_dr_without_dag_edit.post(f"/dagrun/delete/{composite_key}", follow_redirects=True)
    assert resp.status_code == 404  # If it doesn't fully succeed it gives a 404.
    assert session.query(DagRun).filter(DagRun.dag_id == running_dag_run.dag_id).count() == 1


@pytest.mark.parametrize(
    "action",
    ["clear", "set_success", "set_failed", "set_running"],
    ids=["clear", "success", "failed", "running"],
)
def test_set_dag_runs_action_permission_denied(client_dr_without_dag_edit, running_dag_run, action):
    running_dag_id = running_dag_run.id
    resp = client_dr_without_dag_edit.post(
        "/dagrun/action_post",
        data={"action": action, "rowid": [str(running_dag_id)]},
        follow_redirects=True,
    )
    check_content_in_response(f"Access denied for dag_id {running_dag_run.dag_id}", resp)
